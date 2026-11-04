"""Reusable AI services; importing never launches a GUI or installs packages."""
from .client import AIClient
from .storage import SettingsStore, KeyringSecrets
from .types import AIError, AIResponse, ModelInfo, StreamEvent, ConnectionResult
from .providers import register_provider
from .routing import RouteTarget, RoutingPolicy, RoutedClient
from .structured import parse_json_response

__version__ = "2.1.0"
__all__ = ["AIClient", "SettingsStore", "KeyringSecrets", "AIError", "AIResponse", "ModelInfo",
           "StreamEvent", "ConnectionResult", "register_provider", "ProviderSettingsPanel",
           "open_settings", "RouteTarget", "RoutingPolicy", "RoutedClient", "parse_json_response"]


def __getattr__(name):
    if name in ("ProviderSettingsPanel", "open_settings"):
        from . import ui
        return getattr(ui, name)
    raise AttributeError(name)
