# API Providers: Modular integration foundation

This is an incremental compatibility-preserving addition to API Providers 2.0,
not an implementation of the entire long-term roadmap. Existing AIClient and
Tkinter entry points remain unchanged.

## Direct Python SDK

```python
from api_providers import AIClient
client = AIClient(app_id="my-app")
response = client.generate("Summarize this")
print(response.text)
```

## Configured failover

Profiles must first be configured in the existing provider manager. Routing
only replays safe text-generation requests. Authentication/configuration errors
fail closed; no failover is attempted after a partially streamed response.

```python
from api_providers import AIClient
from api_providers.routing import RouteTarget, RoutingPolicy, RoutedClient

client = RoutedClient(
    AIClient("my-app"),
    RoutingPolicy((
        RouteTarget("primary-openai"),
        RouteTarget("backup-ollama", model="llama3.2"),
    )),
)
print(client.generate("Summarize the inspection notes").text)
```

Manual and cheapest modes are available. Cheapest mode requires explicitly
supplied trusted price metadata; it never silently assumes current model prices.
There is no automatic model-capability check yet.

## Structured text

```python
from api_providers.structured import parse_json_response

response = client.generate("Return only JSON with a summary key")
data = parse_json_response(response, required=("summary",))
```

This is top-level JSON parsing and required-key validation, NOT full JSON
Schema enforcement, guaranteed provider JSON mode, or injection protection.

## Local service

```powershell
pip install -e ".[service]"
$env:API_PROVIDERS_APP_ID = "my-app"
$env:API_PROVIDERS_SERVICE_TOKEN = "<replace-with-random-secret-of-at-least-24-chars>"
python -m api_providers.service
```

The service listens on 127.0.0.1:8765, with public unauthenticated
`GET /health` and authenticated `POST /v1/generate`. A generation body
accepts `prompt`, optional `system`, and optional `max_tokens`.
Pass `Authorization: Bearer <service-token>`.

The fixed app identity uses the application's saved default profile/model.
The endpoint intentionally does not expose provider credentials or accept
client-controlled profile overrides. Treat the service token as sensitive.
Do not bind publicly or expose it to untrusted users. For remote deployments
add TLS, identity-based authorization, per-app scoping, rate limits, audits,
abuse mitigation, and request size limits at the ingress.

## Offline tests and local playground

```bash
python -m pip install -e ".[service]"
python -m unittest discover -s tests -v
python -m api_providers --demo
```

The test_routing suite uses a FakeClient and never sends paid API requests.
The existing GUI demo can perform real requests when explicitly activated.

## Roadmap: not yet implemented

- Capability-aware intelligent model ranking and policy-enforced data residency
- Multi-app service authentication, tenant isolation, budget enforcement
- Full JSON Schema provider-mode validation, tool calling and multimodal support
- Durable job queues, circuit breakers, instrumentation, usage accounting
- Memory/RAG, agent execution, governance and approval workflows
- Browser dashboard, encrypted cross-device sync and integration code generator

Add these behind optional extras while preserving the current import API.
