"""Reusable AI services; importing this module never imports a GUI or installs packages."""
from .client import AIClient
from .storage import SettingsStore, KeyringSecrets
from .types import AIError, AIResponse, ModelInfo, StreamEvent, ConnectionResult
from .providers import register_provider

__version__ = "2.0.0"
__all__ = ["AIClient", "SettingsStore", "KeyringSecrets", "AIError", "AIResponse", "ModelInfo",
           "StreamEvent", "ConnectionResult", "register_provider", "ProviderSettingsPanel", "open_settings"]


def __getattr__(name):
    if name in ("ProviderSettingsPanel", "open_settings"):
        from . import ui
        return getattr(ui, name)
    raise AttributeError(name)
