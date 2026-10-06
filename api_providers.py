"""Legacy filename launcher; delegates to the installed package."""
# A same-named script shadows the package from a source checkout. Remove its
# directory from import lookup so the installed package can be resolved.
import sys
from pathlib import Path

if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != script_dir]
    from api_providers.manager import main
    main()
else:
    # Support imports from the checkout without executing GUI startup.
    __path__ = [str(Path(__file__).resolve().parent / "src" / "api_providers")]
    from api_providers.client import AIClient
    from api_providers.storage import SettingsStore, KeyringSecrets
    from api_providers.types import AIError, AIResponse, ModelInfo, StreamEvent, ConnectionResult
    from api_providers.providers import register_provider

    __version__ = "2.0.0"

    def __getattr__(name):
        if name in ("ProviderSettingsPanel", "open_settings"):
            from api_providers import ui
            return getattr(ui, name)
        raise AttributeError(name)
