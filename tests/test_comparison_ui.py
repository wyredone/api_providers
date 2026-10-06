"""Headless checks of explicit comparison launch and independent completion."""
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from api_providers.execution import RequestOptions, RequestResult, RequestStats
from api_providers.ui.demo import DemoApp


class ImmediateThread:
    def __init__(self, target, **kwargs):
        self.target = target
    def start(self):
        self.target()


class ComparisonTests(unittest.TestCase):
    def harness(self):
        store = Mock()
        store.list_profiles.return_value = {"shared": {"provider": "OpenRouter"}}
        variables = [Mock(), Mock()]
        for variable in variables:
            variable.get.return_value = "shared"
        models = [Mock(), Mock()]
        models[0].get.return_value, models[1].get.return_value = "model-a", "model-b"
        app = SimpleNamespace(busy=False, client=SimpleNamespace(app_id="demo", store=store),
                              compare_prompt=Mock(), preset=Mock(), attachments=[], compare_results={}, render_comparison=Mock(), request_options=Mock(return_value=RequestOptions()),
                              compare_profile_vars=variables, compare_model_vars=models, cancel=threading.Event(),
                              events=queue.Queue(), comparison_remaining=set(), comparison_started={}, comparison_stats={},
                              compare_outputs=[Mock(), Mock()], compare_stats_vars=[Mock(), Mock()],
                              compare_cancel=Mock(), set_busy=Mock(), status=Mock(), log=Mock(),
                              format_stats=DemoApp.format_stats, write_comparison=Mock())
        app.compare_prompt.get.return_value = "Same question"
        app.preset.get.return_value = "Custom"
        return app

    def test_launch_same_prompt_two_models_without_history(self):
        app = self.harness()
        result = RequestResult("answer", RequestStats("shared", "model-a", status="complete"))
        with patch("api_providers.ui.demo.threading.Thread", ImmediateThread), \
             patch("api_providers.ui.demo.AIClient") as clients, \
             patch("api_providers.ui.demo.run_request", return_value=result) as run:
            DemoApp.run_comparison(app)
        self.assertEqual(run.call_count, 2)
        self.assertEqual([call.args[4] for call in run.call_args_list], ["model-a", "model-b"])
        for call in run.call_args_list:
            self.assertEqual(call.args[1], [{"role": "user", "content": "Same question"}])
            self.assertIs(call.args[5], app.cancel)
        self.assertEqual(clients.call_count, 2)
        app.client.store.set_app_preferences.assert_not_called()

    def test_invalid_target_sends_no_request(self):
        app = self.harness()
        app.compare_model_vars[1].get.return_value = ""
        with patch("api_providers.ui.demo.run_request") as run:
            DemoApp.run_comparison(app)
        run.assert_not_called()
        app.set_busy.assert_not_called()

    def test_failed_a_does_not_stop_b(self):
        app = self.harness()
        app.comparison_remaining = {0, 1}
        failure = RequestResult("", RequestStats("shared", "model-a", status="error"), "HTTP 429", "rate_limit")
        DemoApp.comparison_ready(app, 0, failure)
        self.assertEqual(app.comparison_remaining, {1})
        app.set_busy.assert_not_called()
        success = RequestResult("answer", RequestStats("shared", "model-b", status="complete"))
        DemoApp.comparison_ready(app, 1, success)
        self.assertEqual(app.comparison_remaining, set())
        app.set_busy.assert_called_once_with(False)
        self.assertIn("A: error; B: complete", app.status.set.call_args.args[0])

    def test_cancel_both_uses_shared_event(self):
        app = self.harness()
        DemoApp.cancel_comparison(app)
        self.assertTrue(app.cancel.is_set())
        app.compare_cancel.configure.assert_called_once_with(state="disabled")

    def test_missing_stats_render_blank_zero_rendered(self):
        text = DemoApp.format_stats(RequestStats("p", "m", completion_tokens=0))
        self.assertIn("Output: 0", text)
        self.assertIn("Input:  |", text)
        self.assertNotIn("None", text)


if __name__ == "__main__":
    unittest.main()
