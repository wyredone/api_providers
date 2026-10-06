"""Toolkit-independent public data types."""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


class AIError(Exception):
    """Safe error message with a stable machine-readable category."""
    def __init__(self, message: str, category: str = "provider", status: Optional[int] = None):
        super().__init__(message)
        self.category = category
        self.status = status


@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AIResponse:
    text: str
    provider: str
    model: str
    usage: Dict[str, Any] = field(default_factory=dict)
    finish_reason: Optional[str] = None


@dataclass(frozen=True)
class StreamEvent:
    text: str = ""
    done: bool = False
    usage: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    message: str
    latency_ms: float
