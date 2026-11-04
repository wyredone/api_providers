"""Opt-in authenticated local FastAPI service, fixed to one application identity."""
import hmac
import os
from .client import AIClient

try:
    from pydantic import BaseModel, Field
except ImportError:
    BaseModel = None
    Field = None


if BaseModel is not None:
    class GenerateRequest(BaseModel):
        prompt: str = Field(min_length=1, max_length=200000)
        system: str = Field(default="", max_length=20000)
        max_tokens: int = Field(default=1024, ge=1, le=32768)


def create_app(*, app_id, access_token, client_factory=None):
    try:
        from fastapi import FastAPI, Header, HTTPException
    except ImportError as exc:
        raise RuntimeError("Install with: pip install 'api-providers[service]'") from exc
    if BaseModel is None:
        raise RuntimeError("The service extra requires Pydantic.")
    if not isinstance(app_id, str) or not app_id.strip():
        raise ValueError("A fixed application identity is required.")
    if not isinstance(access_token, str) or len(access_token) < 24:
        raise ValueError("Use a random service access token with at least 24 characters.")

    application = FastAPI(title="API Providers Service", version="0.1.0")
    factory = client_factory or (lambda: AIClient(app_id=app_id))

    def authenticate(authorization):
        expected = "Bearer " + access_token
        if not isinstance(authorization, str) or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Unauthorized")

    @application.get("/health")
    def health():
        return {"status": "ok"}

    @application.post("/v1/generate")
    def generate(payload: GenerateRequest, authorization: str = Header(default="")):
        authenticate(authorization)
        try:
            response = factory().generate(prompt=payload.prompt, system=payload.system,
                                          max_tokens=payload.max_tokens)
        except Exception:
            raise HTTPException(status_code=502, detail="Model request failed")
        return {"text": response.text, "provider": response.provider,
                "model": response.model, "usage": response.usage}

    return application


def main():
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("Install with: pip install 'api-providers[service]'") from exc
    token = os.environ.get("API_PROVIDERS_SERVICE_TOKEN", "")
    app_id = os.environ.get("API_PROVIDERS_APP_ID", "")
    uvicorn.run(create_app(app_id=app_id, access_token=token), host="127.0.0.1", port=8765)


if __name__ == "__main__":
    main()
