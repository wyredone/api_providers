import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from api_providers import AIClient, AIError, SettingsStore
from api_providers.conversation import Conversation, validate_messages
from test_package import Secrets, response


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "chat.json"

    def test_followup_context(self):
        chat = Conversation()
        chat.complete_turn("My name is Kevin", "Hi Kevin")
        messages = chat.request_messages("What is my name?")
        self.assertEqual([x["role"] for x in messages], ["user", "assistant", "user"])
        self.assertEqual(messages[0]["content"], "My name is Kevin")
        messages[0]["content"] = "changed"
        self.assertEqual(chat.messages[0]["content"], "My name is Kevin")

    def test_unfinished_turn_not_committed(self):
        chat = Conversation()
        chat.request_messages("failed request")
        self.assertEqual(chat.messages, [])
        self.assertEqual(chat.request_messages("retry"), [{"role": "user", "content": "retry"}])

    def test_empty_response_does_not_mutate_history(self):
        chat = Conversation()
        with self.assertRaises(AIError):
            chat.complete_turn("hi", "")
        self.assertEqual(chat.messages, [])

    def test_save_load_unicode_roundtrip(self):
        chat = Conversation()
        chat.complete_turn("Résumé 🔑", "こんにちは")
        chat.save(self.path)
        loaded = Conversation.load(self.path)
        self.assertEqual(loaded.messages, chat.messages)
        self.assertEqual(loaded.id, chat.id)
        self.assertEqual(loaded.title, "Résumé 🔑")
        self.assertNotIn("api_key", self.path.read_text())

    def test_clear_preserves_identity(self):
        chat = Conversation()
        identity = chat.id
        chat.complete_turn("hello", "hi")
        chat.clear()
        self.assertEqual(chat.id, identity)
        self.assertEqual(chat.messages, [])
        self.assertNotEqual(Conversation().id, identity)

    def test_invalid_document(self):
        for content in ("broken", "[]", '{"version":1}', '{"format":"api-providers-chat","version":2}'):
            with self.subTest(content=content):
                self.path.write_text(content)
                with self.assertRaises(AIError):
                    Conversation.load(self.path)

    def test_incomplete_saved_chat_rejected(self):
        chat = Conversation()
        chat.save(self.path)
        data = json.loads(self.path.read_text())
        data["messages"] = [{"role": "user", "content": "unfinished"}]
        self.path.write_text(json.dumps(data))
        with self.assertRaises(AIError):
            Conversation.load(self.path)

    def test_invalid_roles_and_content(self):
        for messages in (None, [{"role": "system", "content": "x"}], [{"role": "assistant", "content": "x"}],
                         [{"role": "user", "content": ""}], [{"role": "user", "content": 123}],
                         [{"role": "user", "content": "x"}, {"role": "user", "content": "y"}]):
            with self.subTest(messages=messages):
                with self.assertRaises(AIError):
                    validate_messages(messages)

    def client(self, provider):
        from api_providers.providers import DEFAULTS
        store = SettingsStore(Path(self.temp.name) / "settings.json", Secrets())
        store.save_profile("profile", provider, DEFAULTS[provider], None, "model")
        store.set_app_preferences("demo", profile="profile")
        session = Mock()
        return AIClient("demo", store, session=session), session

    def test_openai_history_payload(self):
        client, session = self.client("OpenRouter")
        session.request.return_value = response({"choices": [{"message": {"content": "Kevin"}}]})
        chat = Conversation()
        chat.complete_turn("My name is Kevin", "Hi")
        client.generate(messages=chat.request_messages("My name?"), system="Be brief")
        sent = session.request.call_args.kwargs["json"]["messages"]
        self.assertEqual([x["role"] for x in sent], ["system", "user", "assistant", "user"])

    def test_anthropic_history_payload(self):
        client, session = self.client("Anthropic")
        session.request.return_value = response({"content": [{"type": "text", "text": "Kevin"}]})
        chat = Conversation()
        chat.complete_turn("My name is Kevin", "Hi")
        client.generate(messages=chat.request_messages("My name?"), system="Be brief")
        sent = session.request.call_args.kwargs["json"]
        self.assertEqual(sent["system"], "Be brief")
        self.assertEqual([x["role"] for x in sent["messages"]], ["user", "assistant", "user"])

    def test_ollama_stream_history(self):
        client, session = self.client("Ollama")
        session.request.return_value = response(lines=['{"message":{"content":"Kevin"},"done":true}'])
        chat = Conversation()
        chat.complete_turn("My name is Kevin", "Hi")
        events = list(client.stream(messages=chat.request_messages("My name?")))
        self.assertEqual(events[0].text, "Kevin")
        self.assertEqual(len(session.request.call_args.kwargs["json"]["messages"]), 3)

    def test_prompt_and_messages_mutually_exclusive(self):
        client, session = self.client("OpenRouter")
        with self.assertRaises(AIError):
            client.generate("hi", messages=[{"role": "user", "content": "hi"}])
        session.request.assert_not_called()

    def test_history_must_end_with_user(self):
        client, session = self.client("OpenRouter")
        with self.assertRaises(AIError):
            client.generate(messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
        session.request.assert_not_called()

    def test_switch_profile_and_model(self):
        client, session = self.client("OpenRouter")
        client.store.save_profile("local", "Ollama", "http://localhost:11434/api", None, "local-model")
        client.store.set_app_preferences("demo", profile="local", model="selected-local")
        session.request.return_value = response({"message": {"content": "local"}})
        client.generate("hi")
        args, kwargs = session.request.call_args
        self.assertEqual(args[1], "http://localhost:11434/api/chat")
        self.assertEqual(kwargs["json"]["model"], "selected-local")
        self.assertEqual(kwargs["headers"], {})


if __name__ == "__main__":
    unittest.main()
