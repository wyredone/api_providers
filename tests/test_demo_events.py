"""Headless UI controller checks: exercise queue transitions without a display."""
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from api_providers.conversation import Conversation
from api_providers.ui.demo import DemoApp


class DemoEventTests(unittest.TestCase):
    def harness(self):
        app = SimpleNamespace(closed=False, events=queue.Queue(), cancel=threading.Event(),
                              conversation=Conversation(), dirty=False, chat_title=Mock(), prompt=Mock(),
                              cancel_button=Mock(), status=Mock(), append=Mock(), set_busy=Mock(), log=Mock(),
                              after=Mock(return_value="timer"), poll=Mock(), finish_error=Mock())
        return app

    def test_success_commits_completed_turn(self):
        app = self.harness()
        app.events.put(("text", "Hello"))
        app.events.put(("complete", "Hi", "Hello"))
        DemoApp.poll(app)
        self.assertEqual(app.conversation.messages, [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}])
        self.assertTrue(app.dirty)
        app.set_busy.assert_called_with(False)
        app.prompt.delete.assert_called_once_with("1.0", "end")

    def test_cancel_queued_completion_not_committed(self):
        app = self.harness()
        app.events.put(("complete", "Hi", "Hello"))
        app.cancel.set()
        DemoApp.poll(app)
        self.assertEqual(app.conversation.messages, [])
        app.finish_error.assert_called_once()

    def test_failed_turn_excluded(self):
        app = self.harness()
        app.events.put(("error", "Provider error"))
        DemoApp.poll(app)
        self.assertEqual(app.conversation.messages, [])
        app.finish_error.assert_called_once_with("Provider error")

    def test_closed_widget_not_polled(self):
        app = self.harness()
        app.closed = True
        DemoApp.poll(app)
        app.after.assert_not_called()

    def test_model_refresh_callback_runs_on_poll(self):
        app = self.harness()
        callback = Mock()
        app.events.put(("job", callback, ["model-a"], None))
        callback.assert_not_called()
        DemoApp.poll(app)
        callback.assert_called_once_with(["model-a"])
        app.set_busy.assert_called_once_with(False)


if __name__ == "__main__":
    unittest.main()
