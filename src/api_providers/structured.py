"""Dependency-free JSON response extraction and lightweight shape validation."""
import json
from .types import AIError


def parse_json_response(response, *, required=(), expected_type=dict):
    """Parse a response object or raw text; enforce top-level type and required keys.

    This is deliberately not JSON Schema validation. Hosts needing schema
    validation can install a separate validator.
    """
    text = response.text if hasattr(response, "text") else response
    if not isinstance(text, str):
        raise AIError("Structured response must be text.", "validation")
    try:
        value = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise AIError("Model response is not valid JSON.", "validation") from exc
    if not isinstance(value, expected_type):
        raise AIError("Model response has an unexpected JSON type.", "validation")
    if required:
        if not isinstance(value, dict):
            raise AIError("Required keys need a JSON object.", "validation")
        missing = [key for key in required if key not in value]
        if missing:
            raise AIError("Model response is missing required keys: " + ", ".join(missing), "validation")
    return value
