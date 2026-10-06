import requests
import time
import json
from pathlib import Path
from typing import Tuple, List, Dict, Optional, TYPE_CHECKING
from .debug_logger import DebugLogger
from .constants import PROVIDERS, CONFIG_DIR

if TYPE_CHECKING:
    from .file_logger import FileLogger


class APIClient:
    """Static methods for API operations."""

    debug_logger: Optional[DebugLogger] = None
    file_logger: Optional['FileLogger'] = None
    ANTHROPIC_MODELS_FILE = CONFIG_DIR / "anthropic_models.json"

    @staticmethod
    def get_anthropic_models() -> List[str]:
        """Load Anthropic models from file or return defaults."""
        try:
            if APIClient.ANTHROPIC_MODELS_FILE.exists():
                with open(APIClient.ANTHROPIC_MODELS_FILE, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
        except Exception:
            pass
        # Fallback to hardcoded defaults
        return PROVIDERS["Anthropic"].get("models", [])

    @staticmethod
    def save_anthropic_models(models: List[str]) -> Tuple[bool, str]:
        """Save Anthropic models to file. Returns (success, message)."""
        try:
            with open(APIClient.ANTHROPIC_MODELS_FILE, 'w') as f:
                json.dump(models, f, indent=2)
            return True, f"Saved {len(models)} models"
        except Exception as e:
            return False, f"Error saving models: {str(e)}"

    @staticmethod
    def fetch_anthropic_models_from_url(url: str) -> Tuple[bool, str, List[str]]:
        """Fetch Anthropic models from a remote URL. Returns (success, message, models)."""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}", []
            data = response.json()
            if isinstance(data, list):
                return True, f"Fetched {len(data)} models", data
            elif isinstance(data, dict) and "models" in data:
                models = data["models"]
                if isinstance(models, list):
                    return True, f"Fetched {len(models)} models", models
            return False, "Invalid response format", []
        except Exception as e:
            return False, f"Error: {str(e)}", []

    @staticmethod
    def set_debug_logger(logger: DebugLogger) -> None:
        """Set debug logger instance."""
        APIClient.debug_logger = logger

    @staticmethod
    def set_file_logger(logger: 'FileLogger') -> None:
        """Set file logger instance."""
        APIClient.file_logger = logger

    @staticmethod
    def test_connection(base_url: str, api_key: str, provider: str = None) -> Tuple[bool, str, float]:
        """Test connection to API endpoint. Returns (success, message, latency_ms)."""
        if not base_url or not base_url.strip():
            return False, "Base URL cannot be empty", 0.0

        # For Anthropic, test with /messages endpoint instead of /models
        if provider == "Anthropic":
            url = f"{base_url.rstrip('/')}/messages"
            headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
        else:
            url = f"{base_url.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {api_key}"}

        if APIClient.debug_logger:
            APIClient.debug_logger.log_request("test", "GET", url, headers)
        if APIClient.file_logger:
            APIClient.file_logger.log_api_request("test_connection", "GET", url)

        try:
            start_time = time.time()
            response = requests.get(url, headers=headers, timeout=15)
            latency = (time.time() - start_time) * 1000

            if APIClient.debug_logger:
                APIClient.debug_logger.log_response("test", response.status_code, response.text[:500], latency)
            if APIClient.file_logger:
                APIClient.file_logger.log_api_response("test_connection", response.status_code, latency)

            if response.status_code == 401:
                return False, "Invalid API key (401)", latency
            elif response.status_code == 403:
                return False, "Access forbidden (403)", latency
            elif response.status_code == 404:
                return False, "Endpoint not found (404) - check base URL and /models path", latency
            elif response.status_code == 200:
                return True, f"Connection successful ({latency:.0f}ms)", latency
            else:
                return False, f"Error {response.status_code}", latency
        except requests.exceptions.Timeout:
            if APIClient.debug_logger:
                APIClient.debug_logger.log_error("test", "Request timeout (15s)")
            if APIClient.file_logger:
                APIClient.file_logger.log_api_error("test_connection", "Request timeout (15s)")
            return False, "Request timeout (15s)", 0.0
        except requests.exceptions.ConnectionError:
            if APIClient.debug_logger:
                APIClient.debug_logger.log_error("test", "Connection failed")
            if APIClient.file_logger:
                APIClient.file_logger.log_api_error("test_connection", "Connection failed")
            return False, "Connection failed", 0.0
        except Exception as e:
            if APIClient.debug_logger:
                APIClient.debug_logger.log_error("test", str(e))
            if APIClient.file_logger:
                APIClient.file_logger.log_api_error("test_connection", str(e))
            return False, f"Error: {str(e)}", 0.0

    @staticmethod
    def fetch_models(base_url: str, api_key: str, provider: str = None) -> Tuple[List[Dict], str, float]:
        """Fetch available models from API. Returns (models, error, latency_ms)."""
        if not base_url or not base_url.strip():
            return [], "Base URL cannot be empty", 0.0

        # For Anthropic, return models from file or defaults (API doesn't support model listing)
        if provider == "Anthropic":
            model_list = APIClient.get_anthropic_models()
            models = [{"id": m} for m in model_list]
            if APIClient.file_logger:
                APIClient.file_logger.log_model_fetched("fetch_models", len(models))
            return models, "", 0.0

        url = f"{base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {api_key}"}

        if APIClient.debug_logger:
            APIClient.debug_logger.log_request("fetch_models", "GET", url, headers)
        if APIClient.file_logger:
            APIClient.file_logger.log_api_request("fetch_models", "GET", url)

        try:
            start_time = time.time()
            response = requests.get(url, headers=headers, timeout=15)
            latency = (time.time() - start_time) * 1000

            if APIClient.debug_logger:
                APIClient.debug_logger.log_response("fetch_models", response.status_code, response.text[:1000], latency)
            if APIClient.file_logger:
                APIClient.file_logger.log_api_response("fetch_models", response.status_code, latency)

            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}"
                if APIClient.debug_logger:
                    APIClient.debug_logger.log_error("fetch_models", error_msg)
                if APIClient.file_logger:
                    APIClient.file_logger.log_api_error("fetch_models", error_msg)
                return [], error_msg, latency

            data = response.json()
            models = []

            if isinstance(data, dict):
                if "data" in data and isinstance(data["data"], list):
                    for item in data["data"]:
                        model_id = item.get("id") or item.get("model") or item.get("name")
                        if model_id:
                            models.append({"id": model_id})
                elif "models" in data and isinstance(data["models"], list):
                    for item in data["models"]:
                        model_id = item.get("id") or item.get("name")
                        if model_id:
                            models.append({"id": model_id})

            if not models and isinstance(data, list):
                for item in data:
                    model_id = item.get("id") or item.get("model") or item.get("name")
                    if model_id:
                        models.append({"id": model_id})

            if models:
                if APIClient.file_logger:
                    APIClient.file_logger.log_model_fetched("fetch_models", len(models))
                return models, "", latency
            else:
                error_msg = "No models found in response"
                if APIClient.debug_logger:
                    APIClient.debug_logger.log_error("fetch_models", error_msg)
                if APIClient.file_logger:
                    APIClient.file_logger.log_api_error("fetch_models", error_msg)
                return [], error_msg, latency

        except requests.exceptions.Timeout:
            error_msg = "Request timeout (15s)"
            if APIClient.debug_logger:
                APIClient.debug_logger.log_error("fetch_models", error_msg)
            if APIClient.file_logger:
                APIClient.file_logger.log_api_error("fetch_models", error_msg)
            return [], error_msg, 0.0
        except requests.exceptions.ConnectionError:
            error_msg = "Connection failed"
            if APIClient.debug_logger:
                APIClient.debug_logger.log_error("fetch_models", error_msg)
            if APIClient.file_logger:
                APIClient.file_logger.log_api_error("fetch_models", error_msg)
            return [], error_msg, 0.0
        except ValueError:
            error_msg = "Invalid JSON response"
            if APIClient.debug_logger:
                APIClient.debug_logger.log_error("fetch_models", error_msg)
            if APIClient.file_logger:
                APIClient.file_logger.log_api_error("fetch_models", error_msg)
            return [], error_msg, 0.0
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            if APIClient.debug_logger:
                APIClient.debug_logger.log_error("fetch_models", error_msg)
            if APIClient.file_logger:
                APIClient.file_logger.log_api_error("fetch_models", error_msg)
            return [], error_msg, 0.0
