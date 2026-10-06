"""Reusable request settings, timing and provider-reported usage accounting."""
import math
import time
from dataclasses import dataclass, field, replace
from typing import Optional
from .types import AIError


@dataclass(frozen=True)
class RequestOptions:
    system: str = ""
    temperature: Optional[float] = None
    max_tokens: int = 1024
    timeout: float = 60
    streaming: bool = True

    def validate(self):
        if not isinstance(self.system, str) or not isinstance(self.streaming, bool):
            raise AIError("System instructions must be text and streaming must be boolean.", "configuration")
        if self.temperature is not None and (isinstance(self.temperature, bool) or not isinstance(self.temperature, (int, float)) or not math.isfinite(self.temperature) or not 0 <= self.temperature <= 2):
            raise AIError("Temperature must be 0–2 or blank.", "configuration")
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int) or self.max_tokens <= 0:
            raise AIError("Maximum output tokens must be a positive integer.", "configuration")
        if isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float)) or not math.isfinite(self.timeout) or not 0 < self.timeout <= 3600:
            raise AIError("Timeout must be positive and at most 3600 seconds.", "configuration")
        return self

    @classmethod
    def from_preferences(cls, prefs):
        return cls(**{key: prefs[key] for key in cls.__dataclass_fields__ if key in prefs}).validate()

    def preferences(self):
        return {key: getattr(self, key) for key in self.__dataclass_fields__}


@dataclass(frozen=True)
class RequestStats:
    profile: str
    model: str
    provider: str = ""
    elapsed: float = 0
    first_text: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    status: str = "running"
    usage: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RequestResult:
    text: str
    stats: RequestStats
    error: str = ""
    category: str = ""


def token_count(usage, *keys):
    for key in keys:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def account(stats, usage, elapsed, first_text, status="running"):
    incoming = token_count(usage, "prompt_tokens", "input_tokens")
    outgoing = token_count(usage, "completion_tokens", "output_tokens")
    # Total is a sum of reported counts only, never a tokenizer estimate.
    total = token_count(usage, "total_tokens")
    if total is None and incoming is not None and outgoing is not None:
        total = incoming + outgoing
    return replace(stats, elapsed=elapsed, first_text=first_text, prompt_tokens=incoming,
                   completion_tokens=outgoing, total_tokens=total, status=status, usage=dict(usage))


def run_request(client, messages, options, profile, model, cancel, on_text=None, on_stats=None, clock=time.monotonic):
    """Synchronous worker primitive; caller chooses threads and UI event delivery."""
    started = clock()
    stats = RequestStats(profile, model)
    usage, chunks, first_text = {}, [], None
    error, category = "", ""
    status = "complete"
    stream = None
    try:
        options.validate()
        if cancel.is_set():
            raise AIError("Request cancelled.", "cancelled")
        from .client import AIClient
        client = AIClient(client.app_id, client.store, options.timeout, client.session)
        provider = client.store.list_profiles().get(profile, {}).get("provider", "")
        stats = replace(stats, provider=provider)
        kwargs = dict(messages=messages, system=options.system, profile=profile, model=model,
                      temperature=options.temperature, max_tokens=options.max_tokens)
        if options.streaming:
            stream = client.stream(cancel=cancel, **kwargs)
            done = False
            for event in stream:
                if cancel.is_set():
                    raise AIError("Request cancelled.", "cancelled")
                if event.text:
                    if first_text is None:
                        first_text = clock() - started
                    chunks.append(event.text)
                    if on_text:
                        on_text(event.text)
                # Providers report cumulative snapshots; merge rather than add chunks.
                usage.update(event.usage)
                done = done or event.done
                if on_stats:
                    on_stats(account(stats, usage, clock() - started, first_text))
            if not done:
                raise AIError("Stream ended before completion.", "protocol")
        else:
            result = client.generate(**kwargs)
            chunks.append(result.text)
            usage.update(result.usage)
            stats = replace(stats, provider=result.provider, model=result.model)
            if not cancel.is_set() and on_text:
                on_text(result.text)
        if cancel.is_set():
            raise AIError("Request cancelled.", "cancelled")
        if not "".join(chunks).strip():
            raise AIError("Provider returned no text.", "protocol")
    except Exception as exc:
        error = str(exc) if isinstance(exc, AIError) else "Request failed; check provider configuration."
        category = exc.category if isinstance(exc, AIError) else "provider"
        status = "cancelled" if category == "cancelled" else "error"
    finally:
        if stream is not None:
            stream.close()
    final = account(stats, usage, clock() - started, first_text, status)
    if on_stats:
        on_stats(final)
    return RequestResult("".join(chunks), final, error, category)
