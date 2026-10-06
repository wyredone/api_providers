# API Providers 2.0

A reusable Python AI engine, embeddable Tkinter settings panel, and standalone
provider manager. Configure provider credentials once; each app chooses its own
profile and model. The engine has no GUI dependency and never installs packages
or launches windows during import.

## Quick start (Windows)

1. Install Python 3.9+ with Tkinter.
2. Run `launch.bat`. It creates a local virtual environment and installs the package.
3. Name a profile, choose its provider, enter the endpoint and key, then save.
4. Fetch models, select a model, and save again.
5. Run `launch.bat --demo` to test streaming generation.

Alternatively: `python -m pip install -e .`, then `python -m api_providers`.
An installed wheel also supplies `api-providers` and `api-providers-gui` launchers.

## Integrate into another app

Install this package into the host app's environment, pinning its version or Git
commit. Import `AIClient` and create it with a stable application ID such as
`folder-wizard`. Pass that client into app features rather than putting provider
HTTP logic into those features. The complete working host is
[`examples/tkinter_host.py`](examples/tkinter_host.py).

Public API:

| Object / method | Contract |
|---|---|
| `AIClient(app_id, store=None, timeout=60, session=None)` | Per-app client; optional injected store and HTTP session |
| `client.generate(prompt, system="", ...)` | Returns `AIResponse` with text, provider, model, usage and finish reason |
| `client.stream(prompt, cancel=event, ...)` | Yields `StreamEvent` text/usage deltas and a final done event |
| `client.list_models(profile=None)` | Returns `ModelInfo` items, including original provider metadata |
| `client.test_connection(profile=None)` | Returns `ConnectionResult`; tests model endpoint, not billable generation |
| `ProviderSettingsPanel(parent, client, on_saved=None)` | Embeddable `ttk.Frame`; host owns layout, theme and event loop |
| `open_settings(parent, client, on_saved=None)` | Opens a `Toplevel`; no additional root or nested mainloop |
| `SettingsStore(path=None, secrets=None)` | Shared profiles and isolated app preferences |
| `register_provider(name, adapter_class, default_url="")` | Explicit adapter extension hook |

Generation accepts `profile`, `model`, `temperature`, and `max_tokens` overrides.
A caller-supplied HTTP session belongs to the caller and is never closed by the
client; use separate sessions for concurrent requests. The default client opens
and closes a session per operation.

Keep network operations off the GUI thread. The supplied panel and demo use
worker threads and queues, updating widgets only from Tkinter's event loop.
The package does not alter the host's global Tkinter theme or shortcuts.
For Qt or other toolkits, use the same core client and write a toolkit wrapper.


## Integration playground

Run `launch.bat --demo` on Windows or `python -m api_providers --demo`.

1. **Chat:** multi-turn context, streaming or complete responses, cancellation,
   New Chat, Clear, Save Chat and Load Chat. Chat JSON contains completed text
   conversations only, never provider credentials. Failed, empty and cancelled
   turns are excluded from future context. Unsaved changes are checked before
   replacing an active chat through New/Clear/Load.
2. **Connection Status:** view the selected provider and endpoint, run an explicit
   connection test, and reload saved profiles. No request is sent at startup.
3. **Request Settings:** system instructions, temperature, output-token limit,
   timeout and streaming controls. All five are saved under the application ID
   with Save request preferences or when sending a chat request.
4. **Activity Log:** local operation status without credentials or chat contents.
   Timestamps use the computer's local timezone.
5. **Model Comparison:** select two saved profiles/model IDs, refresh either model
   list, enter a shared prompt, and explicitly click Run Comparison (2 requests).
   Both requests use the same system instructions, selected task preset, staged
   attachments and generation settings, but no existing chat history. Results appear side by side, with independent errors,
   status, timing and token usage. Cancel both requests with one button. Neither
   result is added to the main chat or changes its selected profile/model.
   Comparison uses independent HTTP sessions, even if the host injected a session.
   Each provider request may incur its own charge; there is no automatic comparison.

The top bar switches saved profiles and models without opening credential
settings. Refresh models retrieves the selected profile's available models;
manual model IDs are also supported. AI Settings edits profiles using the shared
panel. Switching providers retains chat history, so previous completed messages
will be sent to the newly selected provider on the next Send. New Chat resets
context. Generation snapshots profile/model/settings and disables switching
until completion or cancellation. Network work runs on worker threads; queue
results are applied by the UI event loop. Chats are explicitly saved/loaded,
not automatically recovered after closing the window.

For a host app with its own chat UI, `AIClient.generate(messages=history)` and
`AIClient.stream(messages=history)` accept alternating user/assistant text
messages ending in a user message. Pass system instructions separately through
`system=`. Supplying both `prompt` and `messages` raises a configuration error;
existing single-prompt integrations still work unchanged. The `Conversation`
helper in `api_providers.conversation` handles committed turns and chat files.
### Response tools, tasks and attachments

- **Copy Response / Save Response:** copy or export the latest original response
  as Markdown or plain text. Display formatting does not change the saved bytes
  apart from UTF-8 encoding. Partial responses from failed/cancelled requests
  can also be copied or saved. Comparison panels have independent Copy/Save.
- **Retry Last Request:** repeat the latest request's original profile/model,
  generation settings, effective system instructions, full context and staged
  file contents. Successful retries replace the last answer instead of adding
  a duplicate turn. Failure leaves the prior committed answer intact. Retry is
  reset by New/Clear/Load and is not reconstructed from saved chat files.
- **Format Markdown / Copy Code:** headings, emphasis, lists, quotes, links as
  display text, inline code and fenced code get readable Tkinter styles. Code
  is monospace with horizontal scrolling. Copy Code selects a fenced block and
  copies its original content. This is a basic Markdown renderer, not a full
  HTML renderer: no scripts, remote images, fetched links or code execution.
- **Task preset:** Custom, Summarize, Rewrite, Classify Files, Extract JSON and
  Explain Code. Preset instructions layer onto the user's system instructions
  for the next request; existing custom prompt text is preserved. Extract JSON
  requests JSON but does not yet validate generated responses or enforce a schema.
- **Attach Files / Manage Files:** load TXT, Markdown, JSON and CSV as source text,
  preview individual files, and remove staged files. Supports UTF-8 (optional
  BOM) and BOM-marked UTF-16. JSON must parse; CSV reports row/column counts and
  flags uneven rows. Binary/empty/unsupported inputs are rejected. Limits:
  five files, 1 MiB per source file and 2 MiB combined source/decoded text.
  Nothing is silently truncated. Legacy encodings, images, PDF, DOCX and file
  execution are not supported. Filenames are included; absolute paths are not.
- **Preview Request:** inspect the full logical request (effective system text,
  conversation, attached file contents, model and controls) and UTF-8 byte count
  before Send. It contains no API key. Files are loaded locally and sent only on
  Send or Run Comparison. Attachment contents are JSON-escaped user-message data,
  not system messages. Byte counts are not token estimates; provider context
  limits may still reject large requests. Snapshotted file content is preserved
  for retries even if the source file later changes.

Successful chat sends clear staged attachments, while their submitted contents
remain in chat history and explicitly saved chat JSON for later follow-ups.
Failed sends keep attachments staged. Preview/Copy/Save are local actions.
Comparison uses staged attachments without consuming or adding them to chat.

Request statistics show elapsed wall time, time to the first visible text chunk
(streaming only), selected provider/model/profile, reported input/output/total
counts, and completion/error/cancellation status. Elapsed timing includes setup
and network time and is updated while waiting. First-text time is not time to the
first network byte. Missing usage is displayed blank, not estimated as zero.
Totals are provider-reported or a sum of reported input/output counts. Provider
usage snapshots are merged rather than summed across stream chunks; partial
usage on errors/cancellation may be incomplete. No price estimates are made.
For non-streaming responses, first-text timing remains blank. These are client
measurements and are not a benchmark of server-only inference time.

The GUI-independent `api_providers.execution` module exposes `RequestOptions`,
`RequestStats`, `RequestResult`, and `run_request` for other integrations.
Generation settings are validated before requests; callbacks execute on the
calling worker thread and should enqueue UI updates. An explicitly supplied
`temperature=None` now omits temperature (provider default); leaving the argument
out still uses the application's saved temperature. Request timeout is respected
by the runner and cancellation remains cooperative.

Full chat history is sent on every follow-up; automatic context trimming and
provider-specific context-limit discovery are future work.

## Providers

| Provider | Protocol |
|---|---|
| OpenRouter, OpenAI, Google Gemini | OpenAI-compatible chat completions and model list |
| Anthropic | Native Messages API and paginated Models API |
| Ollama | Native `/api/chat` and `/api/tags`, optional authentication |
| Strata | OpenAI-compatible `/v1` endpoint; default `http://127.0.0.1:8080/v1` |
| Custom | User-supplied OpenAI-compatible endpoint |

The adapters provide text generation and streaming, not every provider feature.
Image inputs, tool execution, automatic capability filtering, model downloading,
Strata `/v1/status` discovery, price estimation and automatic provider fallback
are not implemented in this release. API keys are supplied by the user; this
package does not create provider accounts or purchase API access. Available
models depend on endpoint and account permissions. Some model families do not
support Chat Completions or optional generation parameters; provider errors are
returned without retrying or silently selecting another model.

## Settings and credentials

Default metadata file: `~/.api_provider_manager/profiles-v2.json`.
Each app's profile/model preferences live under its application ID in that file.
Profiles share endpoints and credentials. Profile changes affect every app using
that profile; model preferences remain specific to each app.

Credentials are stored with the OS-backed `keyring` library, not in JSON.
A missing credential backend raises an explicit error. There is no base64 or
plaintext fallback. Local endpoints without keys do not require a credential
backend. For testing, supply a secrets object implementing `get(name)` and
`set(name, value)`. Changing an authenticated endpoint requires re-entering its
credential, preventing accidental reuse at a different address.

Writes use atomic replacement and interprocess file locks. Every operation reads
fresh state inside the lock so independently running apps retain each other's
changes. Corrupt metadata is reported and preserved rather than overwritten.
Configuration import merges profiles and app preferences, preserving local keys.
Export excludes credentials and credential references. It is not a key backup.
The new engine logs neither authentication headers nor request contents.

Cancellation is cooperative: checked before sending and while receiving stream
chunks. It cannot instantly interrupt a blocked socket read; the configured
request timeout bounds that wait. It does not undo provider usage already billed.
There are no automatic retries or paid cloud fallbacks.

## Existing installations

Click **Migrate old settings** to explicitly import the v1 `providers.json`.
Migration keeps the original file, skips existing profile names, and puts decoded
credentials in the OS credential store. Windows DPAPI credentials must be
migrated under the original Windows user on the original machine. If migration
fails, earlier migrated profiles remain; repeat after correcting the problem.
The standalone manager remembers the old default provider; each host app still
chooses its own profile. Existing legacy backups are not v2 imports.

The former multi-file GUI is archived under `api_providers.legacy` and can be
opened with `python -m api_providers --legacy`. It does not write v2 profiles and
is not the recommended host integration. Its request logger redacts credential
headers; legacy key writes now require successful Windows DPAPI encryption.
The former duplicate monolithic application is replaced by a compatibility
launcher. `main.py` remains supported after installation.

## Development and validation

- Install: `python -m pip install -e .`
- Tests: `python -m unittest discover -s tests -v`
- Compile: `python -m compileall -q src examples`
- Wheel: `python -m pip wheel . --no-deps -w dist`
- Demo: `python -m api_providers --demo`

Tests use fake secrets and mocked HTTP responses; no real credentials or paid
requests are required. They cover provider payloads, streams, cancellation,
resource closure, errors, storage isolation, exports, imports and concurrent
writes. Live provider access and Windows credential integration should also be
checked on the target machine. Tool Core can later supply logging and job
conventions without becoming a mandatory dependency.
