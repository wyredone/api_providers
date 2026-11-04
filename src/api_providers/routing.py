"""Optional, toolkit-independent routing and failover for existing AIClient instances.

This module never repeats side-effecting tool calls. Only text generation requests
made through generate() are eligible for failover. Streaming fails closed.
"""
from dataclasses import dataclass
from typing import Optional, Tuple

from .types import AIError


@dataclass(frozen=True)
class RouteTarget:
    profile: str
    model: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.profile, str) or not self.profile.strip():
            raise ValueError("Route target requires a nonempty profile.")


@dataclass(frozen=True)
class RoutingPolicy:
    """Targets are ordered by preference. Modes: manual, failover, or cheapest.

    'cheapest' requires explicit trusted cost metadata supplied by the host app.
    No model pricing is inferred or fetched automatically.
    """
    targets: Tuple[RouteTarget, ...]
    mode: str = "failover"
    retry_categories: Tuple[str, ...] = ("connection", "timeout", "rate_limit")
    max_attempts: Optional[int] = None

    def __post_init__(self):
        if self.mode not in ("manual", "failover", "cheapest"):
            raise ValueError("Unsupported routing mode.")
        if not self.targets:
            raise ValueError("At least one route target is required.")
        if self.max_attempts is not None and self.max_attempts < 1:
            raise ValueError("max_attempts must be positive.")


class RoutedClient:
    """Wrap an AIClient without changing its existing public contract.

    Costs are optional host-supplied USD-per-million-token estimates keyed by
    (profile, model). A missing price makes a target ineligible for cheapest mode.
    """

    def __init__(self, client, policy, costs=None, on_attempt=None):
        self.client = client
        self.policy = policy
        self.costs = costs or {}
        self.on_attempt = on_attempt

    def _targets(self):
        targets = list(self.policy.targets)
        if self.policy.mode == "cheapest":
            missing = [t for t in targets if (t.profile, t.model) not in self.costs]
            if missing:
                raise AIError("Routing prices are missing for one or more targets.", "configuration")
            if any(self.costs[(t.profile, t.model)] < 0 for t in targets):
                raise AIError("Routing prices cannot be negative.", "configuration")
            targets.sort(key=lambda t: self.costs[(t.profile, t.model)])
        if self.policy.mode == "manual":
            targets = targets[:1]
        return targets[:self.policy.max_attempts] if self.policy.max_attempts else targets

    def generate(self, prompt=None, **kwargs):
        """Generate text. Compatible with AIClient.generate(prompt=..., messages=...)."""
        if "profile" in kwargs or "model" in kwargs:
            raise AIError("Routing owns profile/model selection.", "configuration")
        last_error = None
        for index, target in enumerate(self._targets()):
            try:
                result = self.client.generate(prompt, profile=target.profile, model=target.model, **kwargs)
                if self.on_attempt:
                    self.on_attempt(target, None)
                return result
            except AIError as exc:
                if self.on_attempt:
                    self.on_attempt(target, exc.category)
                last_error = exc
                if exc.category not in self.policy.retry_categories:
                    raise
        if last_error:
            raise last_error
        raise AIError("No routing targets configured.", "configuration")

    def stream(self, prompt=None, **kwargs):
        """Streaming uses only the first route; never replay a partial answer."""
        target = self._targets()[0]
        if "profile" in kwargs or "model" in kwargs:
            raise AIError("Routing owns profile/model selection.", "configuration")
        yield from self.client.stream(prompt, profile=target.profile, model=target.model, **kwargs)
