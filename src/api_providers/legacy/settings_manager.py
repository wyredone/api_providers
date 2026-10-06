import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from .constants import CONFIG_DIR, CONFIG_FILE
from .encryption import encrypt_key, decrypt_key


class SettingsManager:
    """Manages provider settings persistence with encryption."""

    def __init__(self):
        """Initialize settings manager and load configuration."""
        self.config = self._load_config()
        self.cache_ttl = 3600  # 1 hour cache

    def _load_config(self) -> Dict:
        """Load configuration from file or return defaults."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "providers": {},
            "default_provider": None,
            "model_cache": {},
            "recently_used_models": []
        }

    def _save_config(self) -> None:
        """Save configuration to file with secure permissions."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2)
        if hasattr(os, 'chmod'):
            os.chmod(CONFIG_FILE, 0o600)

    def save_provider(self, name: str, settings: Dict) -> None:
        """Save provider settings with encrypted API key."""
        provider_settings = settings.copy()
        if "api_key" in provider_settings and provider_settings["api_key"]:
            provider_settings["api_key"] = encrypt_key(provider_settings["api_key"])

        self.config["providers"][name] = provider_settings
        self._save_config()

    def load_provider(self, name: str) -> Optional[Dict]:
        """Load provider settings with decrypted API key."""
        if name not in self.config["providers"]:
            return None

        settings = self.config["providers"][name].copy()
        if "api_key" in settings and settings["api_key"]:
            settings["api_key"] = decrypt_key(settings["api_key"])

        return settings

    def delete_provider(self, name: str) -> None:
        """Delete provider settings."""
        if name in self.config["providers"]:
            del self.config["providers"][name]
            if self.config.get("default_provider") == name:
                self.config["default_provider"] = None
            if name in self.config.get("model_cache", {}):
                del self.config["model_cache"][name]
            self._save_config()

    def list_providers(self) -> List[str]:
        """Return list of saved providers."""
        return list(self.config["providers"].keys())

    def set_default_provider(self, name: str) -> None:
        """Set default provider."""
        if name in self.config["providers"] or name is None:
            self.config["default_provider"] = name
            self._save_config()

    def get_default_provider(self) -> Optional[str]:
        """Get default provider name."""
        return self.config.get("default_provider")

    def export_settings(self, filepath: str) -> None:
        """Export all settings to file."""
        export_config = {"providers": {}, "default_provider": self.config.get("default_provider")}

        for name, settings in self.config["providers"].items():
            export_config["providers"][name] = settings.copy()

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(export_config, f, indent=2)

    def import_settings(self, filepath: str, merge: bool = True) -> None:
        """Import settings from file."""
        try:
            with open(filepath, 'r') as f:
                imported = json.load(f)

            if not merge:
                self.config = {
                    "providers": {},
                    "default_provider": None,
                    "model_cache": {},
                    "recently_used_models": []
                }

            if "providers" in imported:
                self.config["providers"].update(imported["providers"])

            if "default_provider" in imported and imported["default_provider"]:
                self.config["default_provider"] = imported["default_provider"]

            self._save_config()
        except Exception:
            pass

    def cache_models(self, provider: str, models: List[Dict]) -> None:
        """Cache models for a provider."""
        if "model_cache" not in self.config:
            self.config["model_cache"] = {}
        self.config["model_cache"][provider] = {
            "models": models,
            "timestamp": time.time()
        }
        self._save_config()

    def get_cached_models(self, provider: str) -> Optional[List[Dict]]:
        """Get cached models if not expired."""
        cache = self.config.get("model_cache", {}).get(provider)
        if cache and (time.time() - cache.get("timestamp", 0)) < self.cache_ttl:
            return cache.get("models")
        return None

    def add_recently_used_model(self, provider: str, model_id: str) -> None:
        """Add model to recently used list."""
        if "recently_used_models" not in self.config:
            self.config["recently_used_models"] = []

        entry = {"provider": provider, "model_id": model_id, "timestamp": time.time()}
        self.config["recently_used_models"] = [
            m for m in self.config["recently_used_models"]
            if not (m["provider"] == provider and m["model_id"] == model_id)
        ]
        self.config["recently_used_models"].insert(0, entry)
        self.config["recently_used_models"] = self.config["recently_used_models"][:10]
        self._save_config()

    def get_recently_used_models(self, provider: str) -> List[str]:
        """Get recently used models for a provider."""
        return [
            m["model_id"] for m in self.config.get("recently_used_models", [])
            if m["provider"] == provider
        ]

    def delete_all_providers(self) -> None:
        """Delete all saved providers."""
        self.config["providers"] = {}
        self.config["default_provider"] = None
        self.config["model_cache"] = {}
        self._save_config()

    def export_favorites(self, filepath: str, favorite_providers: List[str]) -> None:
        """Export only selected providers."""
        export_config = {"providers": {}, "default_provider": self.config.get("default_provider")}

        for name in favorite_providers:
            if name in self.config["providers"]:
                export_config["providers"][name] = self.config["providers"][name].copy()

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(export_config, f, indent=2)
