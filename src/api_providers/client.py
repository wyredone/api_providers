"""Public AI client with app-specific profile resolution."""
import time
from .providers import DEFAULTS, REGISTRY
from .storage import SettingsStore
from .types import AIError, ConnectionResult


class AIClient:
    def __init__(self, app_id="manager", store=None, timeout=60, session=None):
        self.app_id = app_id
        self.store = store if store is not None else SettingsStore()
        self.timeout = timeout
        self.session = session

    def _resolve(self, profile=None, model=None):
        prefs = self.store.app_preferences(self.app_id)
        name = profile or prefs.get("profile")
        if not name:
            raise AIError("Open AI Settings and select a profile for this app.", "configuration")
        config = self.store.load_profile(name)
        provider = config["provider"]
        if provider not in REGISTRY:
            raise AIError("Provider is not registered.", "configuration")
        selected = model or (prefs.get("model") if name == prefs.get("profile") else None) or config.get("model", "")
        adapter = REGISTRY[provider](provider, config["base_url"] or DEFAULTS[provider],
                                     api_key=config["api_key"], timeout=self.timeout, session=self.session)
        return adapter, selected, prefs

    def list_models(self, profile=None):
        adapter, _, _ = self._resolve(profile)
        try:
            return adapter.list_models()
        finally:
            adapter.close()

    def test_connection(self, profile=None):
        started = time.monotonic()
        try:
            self.list_models(profile)
            return ConnectionResult(True, "Model endpoint reachable; generation access is not tested.",
                                    (time.monotonic() - started) * 1000)
        except AIError as exc:
            return ConnectionResult(False, str(exc), (time.monotonic() - started) * 1000)

    @staticmethod
    def _messages(prompt=None, system="", messages=None):
        from .conversation import validate_messages
        if not isinstance(system, str):
            raise AIError("System instructions must be text.", "configuration")
        if messages is None:
            if not isinstance(prompt, str) or not prompt.strip():
                raise AIError("Prompt cannot be empty.", "configuration")
            history = [{"role": "user", "content": prompt}]
        else:
            if prompt is not None:
                raise AIError("Supply either a prompt or messages, not both.", "configuration")
            history = validate_messages(messages)
            if not history or history[-1]["role"] != "user":
                raise AIError("Conversation must end with a user message.", "configuration")
        return ([{"role": "system", "content": system}] if system else []) + history

    def generate(self, prompt=None, *, messages=None, system="", profile=None, model=None, temperature=None, max_tokens=None):
        messages = self._messages(prompt, system, messages)
        adapter, selected, prefs = self._resolve(profile, model)
        try:
            if not selected:
                raise AIError("Select a model in AI Settings.", "configuration")
            return adapter.generate(selected, messages, temperature if temperature is not None else prefs.get("temperature"),
                                    max_tokens if max_tokens is not None else prefs.get("max_tokens", 1024))
        finally:
            adapter.close()

    def stream(self, prompt=None, *, messages=None, system="", profile=None, model=None, temperature=None, max_tokens=None, cancel=None):
        messages = self._messages(prompt, system, messages)
        adapter, selected, prefs = self._resolve(profile, model)
        try:
            if not selected:
                raise AIError("Select a model in AI Settings.", "configuration")
            yield from adapter.stream(selected, messages, temperature if temperature is not None else prefs.get("temperature"),
                                      max_tokens if max_tokens is not None else prefs.get("max_tokens", 1024), cancel)
        finally:
            adapter.close()
