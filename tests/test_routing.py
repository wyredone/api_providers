"""Offline routing tests: no provider credentials or paid API calls."""
import unittest
from types import SimpleNamespace

from api_providers.routing import RouteTarget, RoutedClient, RoutingPolicy
from api_providers.structured import parse_json_response
from api_providers.types import AIError


class FakeClient:
    def __init__(self, failures=()):
        self.failures = list(failures)
        self.calls = []

    def generate(self, prompt=None, **kwargs):
        self.calls.append(kwargs["profile"])
        if self.failures:
            category = self.failures.pop(0)
            if category:
                raise AIError("simulated error", category)
        return SimpleNamespace(text='{"ok":true}', provider=kwargs["profile"], model="mock", usage={})

    def stream(self, prompt=None, **kwargs):
        self.calls.append(kwargs["profile"])
        yield SimpleNamespace(text="hello", done=False)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.targets = (RouteTarget("primary"), RouteTarget("backup"))

    def test_failover(self):
        fake = FakeClient(["timeout"])
        result = RoutedClient(fake, RoutingPolicy(self.targets)).generate("hi")
        self.assertEqual(result.provider, "backup")
        self.assertEqual(fake.calls, ["primary", "backup"])

    def test_authentication_is_not_retried(self):
        fake = FakeClient(["authentication"])
        with self.assertRaises(AIError):
            RoutedClient(fake, RoutingPolicy(self.targets)).generate("hi")
        self.assertEqual(fake.calls, ["primary"])

    def test_manual(self):
        fake = FakeClient(["timeout"])
        with self.assertRaises(AIError):
            RoutedClient(fake, RoutingPolicy(self.targets, mode="manual")).generate("hi")
        self.assertEqual(fake.calls, ["primary"])

    def test_cheapest_requires_explicit_prices(self):
        with self.assertRaises(AIError):
            RoutedClient(FakeClient(), RoutingPolicy(self.targets, mode="cheapest")).generate("hi")

    def test_cheapest(self):
        fake = FakeClient()
        prices = {("primary", None): 4.0, ("backup", None): 1.0}
        result = RoutedClient(fake, RoutingPolicy(self.targets, mode="cheapest"), prices).generate("hi")
        self.assertEqual(result.provider, "backup")

    def test_stream_never_fails_over(self):
        fake = FakeClient()
        list(RoutedClient(fake, RoutingPolicy(self.targets)).stream("hi"))
        self.assertEqual(fake.calls, ["primary"])

    def test_json(self):
        self.assertEqual(parse_json_response('{"a":1}', required=("a",)), {"a": 1})
        with self.assertRaises(AIError):
            parse_json_response('{"a":1}', required=("b",))
        with self.assertRaises(AIError):
            parse_json_response("not json")


if __name__ == "__main__":
    unittest.main()
