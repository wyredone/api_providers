"""Shared profiles, app preferences, atomic writes, and OS-backed secrets."""
import copy
import json
import os
import tempfile
from pathlib import Path
from typing import Optional
from filelock import FileLock
from .types import AIError


class KeyringSecrets:
    """No plaintext or base64 fallback. Caller may inject another secret backend."""
    def __init__(self, service="api-providers-v2"):
        self.service = service

    def get(self, name):
        import keyring
        try:
            return keyring.get_password(self.service, name) or ""
        except Exception as exc:
            raise AIError("OS credential store unavailable; configure a keyring backend.", "credentials") from exc

    def set(self, name, value):
        import keyring
        try:
            keyring.set_password(self.service, name, value)
        except Exception as exc:
            raise AIError("Cannot save credential to the OS credential store.", "credentials") from exc


class SettingsStore:
    def __init__(self, path: Optional[Path] = None, secrets=None):
        self.path = Path(path) if path else Path.home() / ".api_provider_manager" / "profiles-v2.json"
        self.secrets = secrets if secrets is not None else KeyringSecrets()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path) + ".lock", timeout=10)

    def _read(self):
        if not self.path.exists():
            return {"version": 2, "profiles": {}, "apps": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") != 2 or not isinstance(data.get("profiles"), dict) or not isinstance(data.get("apps"), dict):
                raise ValueError("Invalid settings schema")
            return data
        except (ValueError, OSError) as exc:
            raise AIError("Settings could not be read; existing file was preserved.", "configuration") from exc

    def _write(self, data):
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".profiles-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def list_profiles(self):
        with self.lock:
            return copy.deepcopy(self._read()["profiles"])

    def save_profile(self, name, provider, base_url, api_key=None, model=""):
        if not name.strip():
            raise AIError("Profile name is required.", "configuration")
        with self.lock:
            data = self._read()
            old = data["profiles"].get(name, {})
            # Use a stable account reference; secrets never enter the JSON file.
            if old.get("has_key") and api_key is None and (old.get("provider") != provider or old.get("base_url") != base_url.rstrip("/")):
                raise AIError("Provider or endpoint changed; enter its credential explicitly.", "credentials")
            ref = old.get("credential_ref", name)
            if api_key is not None:
                self.secrets.set(ref, api_key)
            data["profiles"][name] = {"provider": provider, "base_url": base_url.rstrip("/"),
                                      "model": model, "credential_ref": ref,
                                      "has_key": bool(api_key) if api_key is not None else old.get("has_key", False)}
            self._write(data)

    def load_profile(self, name):
        profile = self.list_profiles().get(name)
        if profile is None:
            raise AIError("Selected profile does not exist.", "configuration")
        profile["api_key"] = self.secrets.get(profile["credential_ref"]) if profile.get("has_key") else ""
        return profile

    def set_app_preferences(self, app_id, **values):
        allowed = {"profile", "model", "temperature", "max_tokens"}
        if set(values) - allowed:
            raise AIError("Unsupported application preference.", "configuration")
        with self.lock:
            data = self._read()
            data["apps"].setdefault(app_id, {}).update(values)
            self._write(data)

    def app_preferences(self, app_id):
        with self.lock:
            return copy.deepcopy(self._read()["apps"].get(app_id, {}))

    def export_settings(self, path):
        with self.lock:
            data = copy.deepcopy(self._read())
        for profile in data["profiles"].values():
            profile.pop("credential_ref", None)
            profile["has_key"] = False
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def import_settings(self, path):
        try:
            incoming = json.loads(Path(path).read_text(encoding="utf-8"))
            if incoming.get("version") != 2 or not isinstance(incoming.get("profiles"), dict) or not isinstance(incoming.get("apps"), dict):
                raise ValueError()
            profiles = {}
            for name, profile in incoming["profiles"].items():
                if not isinstance(name, str) or not name.strip() or not isinstance(profile, dict):
                    raise ValueError()
                if not all(isinstance(profile.get(k, ""), str) for k in ("provider", "base_url", "model")):
                    raise ValueError()
                profiles[name] = {k: profile.get(k, "") for k in ("provider", "base_url", "model")}
            apps = {}
            for name, prefs in incoming["apps"].items():
                if not isinstance(name, str) or not isinstance(prefs, dict):
                    raise ValueError()
                apps[name] = {k: v for k, v in prefs.items() if k in {"profile", "model", "temperature", "max_tokens"}}
        except (ValueError, TypeError, AttributeError, OSError) as exc:
            raise AIError("Invalid settings import; no changes made.", "configuration") from exc
        with self.lock:
            data = self._read()
            for name, profile in profiles.items():
                old = data["profiles"].get(name, {})
                profile.update(credential_ref=old.get("credential_ref", name), has_key=old.get("has_key", False))
                data["profiles"][name] = profile
            data["apps"].update(apps)
            self._write(data)

    def migrate_legacy(self, path=None):
        """Explicit migration; keep the original file, never run during import."""
        from .legacy.encryption import decrypt_key
        legacy = Path(path) if path else self.path.parent / "providers.json"
        try:
            data = json.loads(legacy.read_text(encoding="utf-8"))
            providers = data["providers"]
            if not isinstance(providers, dict):
                raise ValueError()
        except (OSError, ValueError, KeyError) as exc:
            raise AIError("Legacy settings could not be read.", "configuration") from exc
        count = 0
        for name, value in providers.items():
            if name in self.list_profiles():
                continue
            key = decrypt_key(value.get("api_key", "")) if value.get("api_key") else ""
            if value.get("api_key") and key == value["api_key"]:
                raise AIError("Legacy credential could not be decrypted; migrate on the original machine.", "credentials")
            self.save_profile(name, name, value.get("base_url", ""), key or None,
                              value.get("model", ""))
            count += 1
        default = data.get("default_provider")
        if default in self.list_profiles():
            self.set_app_preferences("manager", profile=default)
        return count
