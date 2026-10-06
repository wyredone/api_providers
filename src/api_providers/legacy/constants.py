from pathlib import Path

CONFIG_DIR = Path.home() / ".api_provider_manager"
CONFIG_FILE = CONFIG_DIR / "providers.json"

PROVIDERS = {
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_field": "api_key",
        "supports_models": True,
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "api_key_field": "api_key",
        "supports_models": True,
    },
    "Anthropic": {
        "base_url": "https://api.anthropic.com",
        "api_key_field": "api_key",
        "supports_models": False,
        "models": ["claude-opus-4-1", "claude-sonnet-4", "claude-3-5-sonnet", "claude-3-haiku"],
    },
    "Google Gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_field": "api_key",
        "supports_models": True,
    },
    "Ollama": {
        "base_url": "http://localhost:11434/api",
        "api_key_field": None,
        "supports_models": True,
    },
    "Strata": {
        "base_url": "http://localhost:8000",
        "api_key_field": "api_key",
        "supports_models": True,
    },
    "Custom": {
        "base_url": "",
        "api_key_field": "api_key",
        "supports_models": True,
    },
}
