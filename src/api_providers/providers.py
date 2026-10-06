"""Provider protocol adapters. No global clients, logging, or automatic retries."""
import json
from urllib.parse import urlparse
import requests
from .types import AIError, AIResponse, ModelInfo, StreamEvent

DEFAULTS = {
    "OpenRouter": "https://openrouter.ai/api/v1",
    "OpenAI": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com/v1",
    "Google Gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "Ollama": "http://localhost:11434/api",
    "Strata": "http://127.0.0.1:8080/v1",
    "Custom": "",
}


class Adapter:
    def __init__(self, provider, base_url, api_key="", timeout=60, session=None):
        parsed = urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment or parsed.username:
            raise AIError("Enter a valid HTTP(S) base URL without credentials or query parameters.", "configuration")
        if not 0 < timeout <= 3600:
            raise AIError("Timeout must be between 0 and 3600 seconds.", "configuration")
        self.provider, self.base_url, self.api_key = provider, base_url.rstrip("/"), api_key
        self.timeout = timeout
        self.session = session if session is not None else requests.Session()
        self.owns_session = session is None

    def close(self):
        if self.owns_session:
            self.session.close()

    def headers(self):
        return {"Authorization": "Bearer " + self.api_key} if self.api_key else {}

    def request(self, method, path, **kwargs):
        try:
            response = self.session.request(method, self.base_url + path, headers=self.headers(),
                                            timeout=self.timeout, allow_redirects=False, **kwargs)
        except requests.Timeout as exc:
            raise AIError("AI request timed out.", "timeout") from exc
        except requests.RequestException as exc:
            raise AIError("Could not connect to the AI provider.", "connection") from exc
        if not 200 <= response.status_code < 300:
            status = response.status_code
            response.close()
            category = "authentication" if status in (401, 403) else "rate_limit" if status == 429 else "provider"
            messages = {
                400: "Provider rejected the request (HTTP 400); check model and generation settings.",
                401: "Provider authentication failed (HTTP 401); check the profile's API key.",
                403: "Provider access denied (HTTP 403); check account and model permissions.",
                404: "Endpoint or model not found (HTTP 404); check base URL and model ID.",
                429: "Provider rate limit reached (HTTP 429); wait and retry manually.",
            }
            raise AIError(messages.get(status, "Provider returned HTTP %s; check provider availability." % status), category, status)
        return response

    @staticmethod
    def decode(response):
        try:
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError()
            if data.get("error"):
                raise AIError("Provider reported an error.", "provider")
            return data
        except ValueError as exc:
            raise AIError("Provider returned invalid JSON.", "protocol") from exc
        finally:
            response.close()

    def list_models(self):
        data = self.decode(self.request("GET", "/models"))
        return [ModelInfo(x["id"], x.get("name", x.get("display_name", x["id"])), x)
                for x in data.get("data", []) if isinstance(x, dict) and x.get("id")]

    def payload(self, model, messages, temperature, max_tokens, stream):
        data = {"model": model, "messages": messages, "stream": stream, "max_tokens": max_tokens}
        if temperature is not None:
            data["temperature"] = temperature
        return "/chat/completions", data

    def parse_response(self, data, model):
        choice = data["choices"][0]
        return AIResponse(choice["message"].get("content") or "", self.provider,
                          data.get("model", model), data.get("usage", {}), choice.get("finish_reason"))

    def generate(self, model, messages, temperature=None, max_tokens=1024):
        path, payload = self.payload(model, messages, temperature, max_tokens, False)
        data = self.decode(self.request("POST", path, json=payload))
        try:
            return self.parse_response(data, model)
        except (KeyError, IndexError, TypeError) as exc:
            raise AIError("Provider returned an unexpected response format.", "protocol") from exc

    def stream_event(self, data):
        choices = data.get("choices", [])
        choice = choices[0] if choices else {}
        return StreamEvent(choice.get("delta", {}).get("content") or "",
                           bool(choice.get("finish_reason")), data.get("usage") or {})

    def stream(self, model, messages, temperature=None, max_tokens=1024, cancel=None):
        if cancel is not None and cancel.is_set():
            raise AIError("Request cancelled.", "cancelled")
        path, payload = self.payload(model, messages, temperature, max_tokens, True)
        response = self.request("POST", path, json=payload, stream=True)
        ended = False
        try:
            for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                if cancel is not None and cancel.is_set():
                    raise AIError("Request cancelled.", "cancelled")
                if not line:
                    continue
                if isinstance(line, bytes):
                    line = line.decode("utf-8")
                if line.startswith("data:"):
                    line = line[5:].strip()
                elif not isinstance(self, OllamaAdapter):
                    continue
                if line == "[DONE]":
                    ended = True
                    break
                data = json.loads(line)
                if data.get("error"):
                    raise AIError("Provider reported a streaming error.", "provider")
                event = self.stream_event(data)
                if event.text or event.usage:
                    yield StreamEvent(event.text, False, event.usage)
                if event.done:
                    ended = True
                    if isinstance(self, (AnthropicAdapter, OllamaAdapter)):
                        break
            if not ended:
                raise AIError("Provider stream ended before completion.", "protocol")
            yield StreamEvent(done=True)
        except requests.RequestException as exc:
            raise AIError("Streaming connection interrupted.", "connection") from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise AIError("Invalid streaming response.", "protocol") from exc
        finally:
            response.close()


class AnthropicAdapter(Adapter):
    def __init__(self, provider, base_url, **kwargs):
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        super().__init__(provider, base_url, **kwargs)

    def headers(self):
        return {"x-api-key": self.api_key, "anthropic-version": "2023-06-01"}

    def list_models(self):
        models, cursor = [], None
        while True:
            params = {"limit": 100}
            if cursor:
                params["after_id"] = cursor
            data = self.decode(self.request("GET", "/models", params=params))
            models.extend(ModelInfo(x["id"], x.get("display_name", x["id"]), x) for x in data.get("data", []))
            if not data.get("has_more"):
                return models
            next_cursor = data.get("last_id")
            if not next_cursor or next_cursor == cursor:
                raise AIError("Invalid model pagination.", "protocol")
            cursor = next_cursor

    def payload(self, model, messages, temperature, max_tokens, stream):
        system = "\n\n".join(x["content"] for x in messages if x["role"] == "system")
        data = {"model": model, "messages": [x for x in messages if x["role"] != "system"],
                "max_tokens": max_tokens, "stream": stream}
        if system:
            data["system"] = system
        if temperature is not None:
            data["temperature"] = temperature
        return "/messages", data

    def parse_response(self, data, model):
        text = "".join(x.get("text", "") for x in data["content"] if x.get("type") == "text")
        return AIResponse(text, self.provider, data.get("model", model), data.get("usage", {}), data.get("stop_reason"))

    def stream_event(self, data):
        kind = data.get("type")
        usage = data.get("usage", data.get("message", {}).get("usage", {}))
        return StreamEvent(data.get("delta", {}).get("text", ""), kind == "message_stop", usage)


class OllamaAdapter(Adapter):
    def __init__(self, provider, base_url, **kwargs):
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/api"):
            base_url += "/api"
        super().__init__(provider, base_url, **kwargs)

    def list_models(self):
        data = self.decode(self.request("GET", "/tags"))
        return [ModelInfo(x["name"], x["name"], x) for x in data.get("models", [])]

    def payload(self, model, messages, temperature, max_tokens, stream):
        options = {"num_predict": max_tokens}
        if temperature is not None:
            options["temperature"] = temperature
        return "/chat", {"model": model, "messages": messages, "options": options, "stream": stream}

    def parse_response(self, data, model):
        usage = {key: data[source] for key, source in (("prompt_tokens", "prompt_eval_count"), ("completion_tokens", "eval_count")) if source in data}
        return AIResponse(data["message"].get("content", ""), self.provider, data.get("model", model), usage, data.get("done_reason"))

    def stream_event(self, data):
        usage = {key: data[source] for key, source in (("prompt_tokens", "prompt_eval_count"), ("completion_tokens", "eval_count")) if source in data} if data.get("done") else {}
        return StreamEvent(data.get("message", {}).get("content", ""), data.get("done", False), usage)


REGISTRY = {name: Adapter for name in DEFAULTS}
REGISTRY.update(Anthropic=AnthropicAdapter, Ollama=OllamaAdapter)


def register_provider(name, adapter_class, default_url=""):
    """Explicit extension hook. Adapter subclasses implement provider behavior."""
    if not issubclass(adapter_class, Adapter):
        raise TypeError("Provider adapters must subclass Adapter")
    REGISTRY[name] = adapter_class
    DEFAULTS[name] = default_url
