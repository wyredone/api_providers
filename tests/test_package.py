import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock
import requests
from api_providers import AIClient, AIError, SettingsStore
from api_providers.providers import Adapter, AnthropicAdapter, OllamaAdapter


class Secrets:
    def __init__(self):
        self.values = {}
    def get(self, name):
        return self.values.get(name, "")
    def set(self, name, value):
        self.values[name] = value


def response(data=None, lines=(), status=200):
    value = Mock()
    value.status_code = status
    value.json.return_value = data
    value.iter_lines.return_value = iter(lines)
    return value


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "settings.json"
        self.secrets = Secrets()
        self.store = SettingsStore(self.path, self.secrets)
        self.session = Mock()

    def profile(self, provider="OpenRouter", model="model-one", key="secret-123"):
        from api_providers.providers import DEFAULTS
        self.store.save_profile("shared", provider, DEFAULTS[provider], key, model)
        self.store.set_app_preferences("host", profile="shared")
        return AIClient("host", self.store, session=self.session)

    def test_secrets_not_in_json(self):
        self.profile()
        self.assertNotIn("secret-123", self.path.read_text())
        self.assertEqual(self.store.load_profile("shared")["api_key"], "secret-123")

    def test_app_models_independent(self):
        self.profile()
        self.store.set_app_preferences("a", profile="shared", model="a-model")
        self.store.set_app_preferences("b", profile="shared", model="b-model")
        self.assertEqual(AIClient("a", self.store)._resolve()[1], "a-model")
        self.assertEqual(AIClient("b", self.store)._resolve()[1], "b-model")

    def test_preserve_key_on_save(self):
        self.profile()
        self.store.save_profile("shared", "OpenRouter", "https://openrouter.ai/api/v1")
        self.assertEqual(self.store.load_profile("shared")["api_key"], "secret-123")

    def test_endpoint_change_does_not_reuse_key(self):
        self.profile()
        with self.assertRaises(AIError):
            self.store.save_profile("shared", "OpenRouter", "https://other.example/v1")
        self.assertEqual(self.store.load_profile("shared")["base_url"], "https://openrouter.ai/api/v1")

    def test_export_excludes_credentials(self):
        self.profile()
        target = Path(self.temp.name) / "export.json"
        self.store.export_settings(target)
        exported = target.read_text()
        self.assertNotIn("secret-123", exported)
        self.assertNotIn("credential_ref", exported)
        imported = SettingsStore(Path(self.temp.name) / "other.json", Secrets())
        imported.import_settings(target)
        self.assertEqual(imported.load_profile("shared")["api_key"], "")

    def test_import_preserves_existing_key(self):
        self.profile()
        target = Path(self.temp.name) / "export.json"
        self.store.export_settings(target)
        self.store.import_settings(target)
        self.assertEqual(self.store.load_profile("shared")["api_key"], "secret-123")

    def test_import_bad_schema_no_write(self):
        self.profile()
        original = self.path.read_text()
        target = Path(self.temp.name) / "bad.json"
        target.write_text('{"version":2,"profiles":{"bad":null},"apps":{}}')
        with self.assertRaises(AIError):
            self.store.import_settings(target)
        self.assertEqual(original, self.path.read_text())

    def test_corrupt_config_preserved(self):
        self.path.write_text("broken")
        with self.assertRaises(AIError):
            self.store.set_app_preferences("a", model="x")
        self.assertEqual(self.path.read_text(), "broken")

    def test_concurrent_writes(self):
        def write(i):
            SettingsStore(self.path, self.secrets).set_app_preferences("app" + str(i), model=str(i))
        threads = [threading.Thread(target=write, args=(i,)) for i in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(json.loads(self.path.read_text())["apps"]), 20)

    def test_openai_generation(self):
        client = self.profile()
        self.session.request.return_value = response({"choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}], "usage": {"total_tokens": 4}})
        result = client.generate("hi", system="be helpful")
        self.assertEqual(result.text, "hello")
        args, kwargs = self.session.request.call_args
        self.assertEqual(args, ("POST", "https://openrouter.ai/api/v1/chat/completions"))
        self.assertEqual(kwargs["json"]["messages"][0]["role"], "system")
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(result.usage["total_tokens"], 4)

    def test_anthropic_generation(self):
        client = self.profile("Anthropic")
        self.session.request.return_value = response({"content": [{"type": "text", "text": "claude"}], "usage": {"input_tokens": 3}})
        self.assertEqual(client.generate("hi", system="instructions").text, "claude")
        args, kwargs = self.session.request.call_args
        self.assertTrue(args[1].endswith("/v1/messages"))
        self.assertEqual(kwargs["json"]["system"], "instructions")
        self.assertEqual(len(kwargs["json"]["messages"]), 1)
        self.assertEqual(kwargs["headers"]["x-api-key"], "secret-123")

    def test_ollama_generation(self):
        client = self.profile("Ollama", key=None)
        self.session.request.return_value = response({"message": {"content": "local"}, "eval_count": 8})
        self.assertEqual(client.generate("hi").usage["completion_tokens"], 8)
        args, kwargs = self.session.request.call_args
        self.assertTrue(args[1].endswith("/api/chat"))
        self.assertEqual(kwargs["headers"], {})

    def test_ollama_models(self):
        client = self.profile("Ollama", key=None)
        self.session.request.return_value = response({"models": [{"name": "local:latest"}]})
        self.assertEqual(client.list_models()[0].id, "local:latest")
        self.assertTrue(self.session.request.call_args.args[1].endswith("/api/tags"))

    def test_anthropic_models_paginate(self):
        client = self.profile("Anthropic")
        self.session.request.side_effect = [response({"data": [{"id": "a"}], "has_more": True, "last_id": "a"}), response({"data": [{"id": "b"}], "has_more": False})]
        self.assertEqual([x.id for x in client.list_models()], ["a", "b"])
        self.assertEqual(self.session.request.call_args.kwargs["params"]["after_id"], "a")

    def test_stream_sse(self):
        client = self.profile()
        value = response(lines=['data: {"choices":[{"delta":{"content":"Hi"}}]}', 'data: [DONE]'])
        self.session.request.return_value = value
        events = list(client.stream("hi"))
        self.assertEqual(events[0].text, "Hi")
        self.assertTrue(events[-1].done)
        value.close.assert_called_once()

    def test_stream_anthropic(self):
        client = self.profile("Anthropic")
        self.session.request.return_value = response(lines=['event: content_block_delta', 'data: {"type":"content_block_delta","delta":{"text":"Hey"}}', 'data: {"type":"message_stop"}'])
        self.assertEqual(list(client.stream("hi"))[0].text, "Hey")

    def test_stream_ollama(self):
        client = self.profile("Ollama", key=None)
        self.session.request.return_value = response(lines=['{"message":{"content":"Hello"},"done":false}', '{"message":{"content":""},"done":true,"eval_count":2}'])
        events = list(client.stream("hi"))
        self.assertEqual(events[0].text, "Hello")
        self.assertEqual(events[1].usage["completion_tokens"], 2)
        self.assertTrue(events[-1].done)

    def test_stream_usage_after_finish(self):
        client = self.profile()
        self.session.request.return_value = response(lines=[
            'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}',
            'data: {"choices":[],"usage":{"total_tokens":9}}',
            'data: [DONE]'])
        events = list(client.stream("hi"))
        self.assertEqual(events[0].usage["total_tokens"], 9)
        self.assertTrue(events[-1].done)

    def test_cancel_before_network(self):
        client = self.profile()
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(AIError) as context:
            list(client.stream("hi", cancel=cancel))
        self.assertEqual(context.exception.category, "cancelled")
        self.session.request.assert_not_called()

    def test_cancel_midstream_closes_response(self):
        client = self.profile()
        cancel = threading.Event()
        value = response(lines=['data: {"choices":[{"delta":{"content":"Hi"}}]}', 'data: [DONE]'])
        self.session.request.return_value = value
        stream = client.stream("hi", cancel=cancel)
        self.assertEqual(next(stream).text, "Hi")
        cancel.set()
        with self.assertRaises(AIError):
            next(stream)
        value.close.assert_called_once()

    def test_stream_truncation_error(self):
        client = self.profile()
        self.session.request.return_value = response(lines=[])
        with self.assertRaises(AIError):
            list(client.stream("hi"))

    def test_http_error_safe(self):
        client = self.profile()
        self.session.request.return_value = response(status=401)
        with self.assertRaises(AIError) as context:
            client.generate("hi")
        self.assertEqual(context.exception.category, "authentication")
        self.assertNotIn("secret", str(context.exception))
        self.assertEqual(self.session.request.call_count, 1)

    def test_timeout(self):
        client = self.profile()
        self.session.request.side_effect = requests.Timeout("sensitive details")
        with self.assertRaises(AIError) as context:
            client.generate("hi")
        self.assertEqual(context.exception.category, "timeout")
        self.assertNotIn("sensitive", str(context.exception))

    def test_invalid_response(self):
        client = self.profile()
        self.session.request.return_value = response({})
        with self.assertRaises(AIError):
            client.generate("hi")

    def test_missing_profile(self):
        with self.assertRaises(AIError):
            AIClient("host", self.store).generate("hi")

    def test_missing_model(self):
        client = self.profile(model="")
        with self.assertRaises(AIError):
            client.generate("hi")
        self.session.request.assert_not_called()

    def test_model_override_explicit_profile(self):
        client = self.profile()
        self.store.set_app_preferences("host", model="app-model")
        self.store.save_profile("other", "OpenRouter", "https://example.com/v1", None, "other-model")
        self.assertEqual(client._resolve("other")[1], "other-model")

    def test_local_legacy_migration_preserves_original(self):
        import base64
        import sys
        if sys.platform == "win32":
            self.skipTest("Non-Windows base64 migration fixture")
        legacy = Path(self.temp.name) / "providers.json"
        content = json.dumps({"providers": {"OpenRouter": {"base_url": "https://openrouter.ai/api/v1", "api_key": base64.b64encode(b"old-secret").decode(), "model": "old-model"}}, "default_provider": "OpenRouter"})
        legacy.write_text(content)
        self.assertEqual(self.store.migrate_legacy(legacy), 1)
        self.assertEqual(legacy.read_text(), content)
        self.assertEqual(self.store.load_profile("OpenRouter")["api_key"], "old-secret")
        self.assertEqual(self.store.migrate_legacy(legacy), 0)

    def test_auth_headers_redacted_in_legacy_log(self):
        from api_providers.legacy.debug_logger import DebugLogger
        logger = DebugLogger.__new__(DebugLogger)
        logger.logs, logger.max_logs = [], 100
        logger._write_to_file = Mock()
        logger.log_request("test", "GET", "https://example.com", {"Authorization": "secret", "X-API-Key": "secret"})
        self.assertNotIn("secret", json.dumps(logger.logs))


if __name__ == "__main__":
    unittest.main()
