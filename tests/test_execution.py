import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock
from api_providers import AIClient, AIError, SettingsStore
from api_providers.execution import RequestOptions, RequestStats, account, run_request
from test_package import Secrets, response


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SettingsStore(Path(self.temp.name) / "settings.json", Secrets())
        self.store.save_profile("cloud", "OpenRouter", "https://openrouter.ai/api/v1", None, "m")
        self.store.set_app_preferences("demo", profile="cloud")
        self.session = Mock()
        self.client = AIClient("demo", self.store, session=self.session)
        self.messages = [{"role": "user", "content": "hi"}]

    def run_it(self, options=None, **kwargs):
        return run_request(self.client, self.messages, options or RequestOptions(), "cloud", "m",
                           kwargs.pop("cancel", threading.Event()), **kwargs)

    def test_full_settings_persist_and_reload(self):
        options = RequestOptions("Custom instructions", 0.7, 512, 35, False)
        self.store.set_app_preferences("demo", **options.preferences())
        other = SettingsStore(self.store.path, self.store.secrets)
        self.assertEqual(RequestOptions.from_preferences(other.app_preferences("demo")), options)
        self.assertEqual(other.app_preferences("different"), {})

    def test_settings_export_import_roundtrip(self):
        options = RequestOptions("Instructions", None, 99, 10, False)
        self.store.set_app_preferences("demo", **options.preferences())
        target = Path(self.temp.name) / "export.json"
        self.store.export_settings(target)
        other = SettingsStore(Path(self.temp.name) / "other.json", Secrets())
        other.import_settings(target)
        self.assertEqual(RequestOptions.from_preferences(other.app_preferences("demo")), options)

    def test_invalid_options_rejected(self):
        for overrides in ({"temperature": float("nan")}, {"temperature": 3}, {"temperature": True},
                          {"timeout": float("inf")}, {"timeout": 0}, {"max_tokens": 0},
                          {"max_tokens": 1.5}, {"max_tokens": True}, {"system": 3}, {"streaming": "yes"}):
            with self.subTest(overrides=overrides):
                with self.assertRaises(AIError):
                    RequestOptions(**overrides).validate()

    def test_invalid_settings_do_not_replace_file(self):
        before = self.store.path.read_text()
        with self.assertRaises(AIError):
            self.store.set_app_preferences("demo", timeout=-1)
        self.assertEqual(before, self.store.path.read_text())

    def test_nonstream_reported_usage_and_timeout(self):
        self.session.request.return_value = response({"choices": [{"message": {"content": "hello"}}],
                                                     "usage": {"prompt_tokens": 4, "completion_tokens": 2}})
        result = self.run_it(RequestOptions(timeout=12, streaming=False))
        self.assertEqual(result.text, "hello")
        self.assertEqual(result.stats.total_tokens, 6)
        self.assertIsNone(result.stats.first_text)
        self.assertEqual(self.session.request.call_args.kwargs["timeout"], 12)

    def test_usage_missing_remains_unavailable(self):
        self.session.request.return_value = response({"choices": [{"message": {"content": "hello"}}]})
        result = self.run_it(RequestOptions(streaming=False))
        self.assertIsNone(result.stats.total_tokens)
        self.assertIsNone(result.stats.prompt_tokens)
        self.assertIsNone(result.stats.completion_tokens)

    def test_usage_zero_preserved(self):
        stats = account(RequestStats("p", "m"), {"input_tokens": 0, "output_tokens": 0}, 1, None)
        self.assertEqual(stats.total_tokens, 0)

    def test_invalid_token_counts_not_displayed(self):
        stats = account(RequestStats("p", "m"), {"prompt_tokens": -1, "completion_tokens": "5", "total_tokens": True}, 1, None)
        self.assertIsNone(stats.total_tokens)
        self.assertIsNone(stats.prompt_tokens)
        self.assertIsNone(stats.completion_tokens)

    def test_stream_timing_and_cumulative_usage(self):
        now = [0.0]
        def lines():
            now[0] = 1
            yield 'data: {"choices":[{"delta":{"content":"Hi"}}],"usage":{"prompt_tokens":4}}'
            now[0] = 2
            yield 'data: {"choices":[{"delta":{"content":"!"}}],"usage":{"prompt_tokens":4,"completion_tokens":2,"total_tokens":6}}'
            now[0] = 3
            yield 'data: [DONE]'
        value = response()
        value.iter_lines.return_value = lines()
        self.session.request.return_value = value
        updates, text = [], []
        result = self.run_it(clock=lambda: now[0], on_text=text.append, on_stats=updates.append)
        self.assertEqual(result.text, "Hi!")
        self.assertEqual(result.stats.first_text, 1)
        self.assertEqual(result.stats.elapsed, 3)
        self.assertEqual(result.stats.total_tokens, 6)
        self.assertEqual(text, ["Hi", "!"])
        self.assertEqual(updates[-1].status, "complete")

    def test_anthropic_partial_usage_merged(self):
        self.store.save_profile("cloud", "Anthropic", "https://api.anthropic.com/v1", None, "m")
        self.session.request.return_value = response(lines=[
            'data: {"type":"message_start","message":{"usage":{"input_tokens":10,"output_tokens":0}}}',
            'data: {"type":"content_block_delta","delta":{"text":"Hello"}}',
            'data: {"type":"message_delta","usage":{"output_tokens":3}}',
            'data: {"type":"message_stop"}'])
        result = self.run_it()
        self.assertEqual(result.stats.prompt_tokens, 10)
        self.assertEqual(result.stats.completion_tokens, 3)
        self.assertEqual(result.stats.total_tokens, 13)

    def test_cancel_before_send(self):
        cancel = threading.Event()
        cancel.set()
        result = self.run_it(cancel=cancel)
        self.assertEqual(result.stats.status, "cancelled")
        self.session.request.assert_not_called()

    def test_cancel_midstream_retains_partial_stats(self):
        cancel = threading.Event()
        value = response(lines=['data: {"choices":[{"delta":{"content":"partial"}}],"usage":{"prompt_tokens":5}}', 'data: [DONE]'])
        self.session.request.return_value = value
        result = self.run_it(cancel=cancel, on_text=lambda text: cancel.set())
        self.assertEqual(result.text, "partial")
        self.assertEqual(result.stats.status, "cancelled")
        self.assertEqual(result.stats.prompt_tokens, 5)
        value.close.assert_called_once()

    def test_provider_failure_has_stats(self):
        self.session.request.return_value = response(status=401)
        result = self.run_it()
        self.assertEqual(result.stats.status, "error")
        self.assertEqual(result.category, "authentication")
        self.assertGreaterEqual(result.stats.elapsed, 0)

    def test_blank_temperature_overrides_saved_default(self):
        self.store.set_app_preferences("demo", temperature=0.8)
        self.session.request.return_value = response({"choices": [{"message": {"content": "ok"}}]})
        result = self.run_it(RequestOptions(streaming=False))
        self.assertEqual(result.stats.status, "complete")
        self.assertNotIn("temperature", self.session.request.call_args.kwargs["json"])
        self.assertEqual(self.store.app_preferences("demo")["temperature"], 0.8)

    def test_omitted_temperature_uses_saved_default(self):
        self.store.set_app_preferences("demo", temperature=0.8)
        self.session.request.return_value = response({"choices": [{"message": {"content": "ok"}}]})
        self.client.generate("hi")
        self.assertEqual(self.session.request.call_args.kwargs["json"]["temperature"], 0.8)

    def test_invalid_options_no_network(self):
        result = self.run_it(RequestOptions(timeout=-1))
        self.assertEqual(result.stats.status, "error")
        self.session.request.assert_not_called()

    def test_independent_concurrent_results(self):
        self.store.save_profile("local", "Ollama", "http://localhost:11434/api", None, "local-model")
        second_session = Mock()
        second_session.request.return_value = response({"message": {"content": "local success"}, "eval_count": 7})
        self.session.request.return_value = response(status=429)
        clients = [self.client, AIClient("demo", self.store, session=second_session)]
        targets = [("cloud", "m"), ("local", "local-model")]
        results = {}
        def worker(index):
            profile, model = targets[index]
            results[index] = run_request(clients[index], self.messages, RequestOptions(streaming=False), profile, model, threading.Event())
        threads = [threading.Thread(target=worker, args=(i,)) for i in (0, 1)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(results[0].stats.status, "error")
        self.assertEqual(results[1].stats.status, "complete")
        self.assertEqual(results[1].stats.model, "local-model")
        self.assertEqual(results[1].stats.completion_tokens, 7)
        self.assertEqual(self.store.app_preferences("demo"), {"profile": "cloud"})


if __name__ == "__main__":
    unittest.main()
