# Errors and Internationalization

This document defines Toqraq's error, diagnostic, logging, and user-visible
text contracts. It applies to Python services, Hermes tools, FastAPI routes,
event sockets, Desktop contributions, component installers, media operations,
and engine bridges.

## Goals

The system must:

- give code and models stable machine-readable failures;
- show users concise localized actions inside Hermes Desktop;
- retain enough technical evidence to diagnose engine and component failures;
- never expose secrets, unsafe paths, implementation details, or unbounded
  engine output;
- use the same failure semantics through tools, HTTP, sockets, and setup UI;
- preserve original causes without making English exception prose a public
  contract.

## Error value

Every expected application failure is represented by a typed `ToqraqError`
carrying these fields:

| Field | Purpose |
| --- | --- |
| `code` | Stable namespaced machine identifier |
| `category` | Transport-neutral failure class |
| `parameters` | Safe values used for localization |
| `details` | Safe structured facts for tools and UI actions |
| `cause` | Original exception retained for logs only |
| `trace_id` | Correlation identifier for this failed operation |

The domain error does not contain preformatted user-interface prose.

Codes use lowercase dot-separated namespaces, for example:

```text
session.not_found
session.invalid_state
engine.not_detected
runtime.release_not_found
component.install_failed
bridge.handshake_mismatch
perception.capability_unavailable
component.checksum_mismatch
media.invalid_input
```

Code meanings are exact. A code is not reused for a different condition.
There are no aliases or alternate code spellings.

## Categories

Categories describe semantics rather than implementation classes:

| Category | Meaning | HTTP status |
| --- | --- | --- |
| `invalid` | Input or project data violates the contract | 400 |
| `unauthenticated` | Required session or component authentication is absent | 401 |
| `forbidden` | The authenticated caller may not perform the operation | 403 |
| `not_found` | Requested session, engine, version, object, or component is absent | 404 |
| `conflict` | Current ownership or state prevents the operation | 409 |
| `unavailable` | A declared capability or local prerequisite is unavailable | 424 |
| `timeout` | A bounded external operation missed its deadline | 504 |
| `upstream` | Engine, vendor, network, or media component failed | 502 |
| `internal` | Unexpected Toqraq implementation failure | 500 |

The HTTP presenter maps category to status. It does not import and enumerate
every concrete exception class. Hermes tool handlers return the same category
inside JSON and never raise an expected failure through the host boundary.

## Public envelope

All expected HTTP, Hermes tool, setup, and request-validation failures use one
shape:

```json
{
  "error": {
    "code": "runtime.release_not_found",
    "category": "not_found",
    "parameters": {
      "engine": "godot",
      "version": "4.x.y"
    },
    "details": {
      "engine": "godot",
      "version": "4.x.y"
    },
    "trace_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

Rules:

- `parameters` and `details` contain only bounded JSON-safe data.
- Integers stay within JavaScript's exact safe range,
  `-9007199254740991` through `9007199254740991`.
- The public envelope never contains `repr(exception)`, a traceback, secret,
  credential, arbitrary environment, or unrestricted process output.
- A path is included only when it is safe and useful to the current user. A
  managed cache path is normally omitted.
- An unexpected exception is converted at the outer boundary to
  `internal.unexpected`. Its type and bounded stack locations are logged under
  the trace ID; its arbitrary message, arguments, and local values are not.
- FastAPI/Pydantic request validation is converted to this envelope. Default
  framework 422 payloads do not cross the plugin API.
- Socket operation failures use the same `error` object inside the typed event
  envelope.

## Safe details

Details help the model or Desktop offer a concrete next action. Prefer typed
facts over prose:

```json
{
  "required_component": "engine.godot",
  "required_version": "4.x.y",
  "feature": "runtime.input",
  "retryable": true,
  "operation_id": "..."
}
```

Details must not become a generic dumping ground. Every detail key belongs to
the contract model for that error family and has an explicit bound.

## Exception translation

Translate failures once at each trust boundary:

```text
vendor or OS exception
  -> engine/component/platform typed error
  -> application error with trace ID
  -> HTTP/tool/event presenter
  -> localized Desktop message
```

- Adapters translate vendor exceptions they understand and preserve `cause`.
- Services add operation and ownership context without replacing an existing
  trace ID.
- Presenters serialize; they do not infer engine policy.
- Broad `Exception` catches are allowed only at outer boundaries, isolated
  callbacks, and owned task supervisors.
- Cancellation is not converted into an ordinary failure. Atomic ownership or
  publication settles first, then cancellation propagates.
- Cleanup may collect several failures, but the returned error identifies the
  resources still owned and safe retry action.

Programmer defects such as impossible states and invalid internal constructor
arguments are not converted early into user errors. They fail to the nearest
outer boundary, are logged, and become `internal.unexpected` publicly.

## Diagnostics are not application errors

Engine compiler output, runtime warnings, stack traces, import messages,
performance warnings, and media analyzer output are diagnostic records, not
`ToqraqError` values.

A diagnostic record contains bounded typed fields such as:

```text
sequence
timestamp
severity
source
location
code
summary
details
engine
runtime identity
```

- Diagnostics retain the engine's technical language and are not translated.
- Process stdout and stderr are captured into bounded, sequenced buffers; an
  explicit read projects only the latest 16,384-character combined tail.
- Diagnostic streams use cursor and limit. Process output has no history or
  cursor. Neither is placed wholesale in notifications or LLM context.
- Malformed bridge diagnostics are rejected or represented as a bounded
  `bridge.malformed_diagnostic` record without echoing the full payload.
- Desktop may localize labels around diagnostics, but not alter their source
  content.

## Trace IDs and operation IDs

A trace ID correlates one user-visible request through Tool/HTTP, service,
component, process, bridge, and native-window logs.

- Trace and operation IDs use canonical lowercase UUID4 text with the RFC 4122
  variant. A presenter accepts that exact host form when Hermes provides one;
  otherwise it generates a UUID4 with the Python standard library.
- Child operations retain the trace ID and may add an operation ID.
- Long installs, repairs, media transforms, and launches have stable operation
  IDs for progress and cancellation.
- Events include trace and operation IDs when related to an operation.
- Trace IDs are identifiers, not authorization tokens.

## Logging

Use Python `logging` and engine-native logging facilities. Do not add another
logging framework.

Every operation log should include the relevant subset of:

- trace ID and operation ID;
- Hermes session ID;
- engine ID and exact runtime identity;
- component ID and version;
- process ID;
- capability ID;
- outcome and elapsed time.

Logging rules:

- Never log session bridge credentials, API keys, provider tokens, cookies,
  authorization headers, full environment mappings, or source file contents.
- Log safe normalized paths only when needed to diagnose a local project
  operation.
- Do not log binary media or full bridge frames.
- Expected user errors are not logged with tracebacks.
- Unexpected errors and failed cleanup include trace IDs, exception type, and
  bounded stack frame locations without locals. They do not blindly log
  `str(exception)`, `repr(exception)`, exception arguments, or a traceback
  rendering that repeats those values.
- An adapter may attach a short technical diagnostic only after it has
  constructed that text from reviewed safe fields; arbitrary vendor or OS
  exception text is never promoted automatically.
- Repeated engine diagnostics are rate-limited or deduplicated without hiding
  their total count.

## Internationalization ownership

Hermes Desktop plugin i18n is the only owner of user-visible translations.
The Desktop entry registers Toqraq locale bundles through the public Hermes
plugin SDK.

The initial required locales are:

- English (`en`), which is the required default bundle;
- Simplified Chinese using the locale identifier expected by Hermes Desktop.

Additional locales can be added without changing service or error code logic.

The following text must use translation keys:

- pane, route, command, status, button, field, dialog, and settings labels;
- setup, progress, empty, failure, recovery, and confirmation messages;
- validation summaries rendered by Desktop;
- capability and component state labels;
- error messages and suggested user actions;
- accessibility labels, tooltips, and notification text.

The following remain technical English or source-native text:

- code symbols and protocol identifiers;
- comments and docstrings;
- structured logs;
- engine/compiler diagnostics;
- model-facing tool descriptions when Hermes does not provide a localized
  schema registration surface;
- vendor names, file names, and engine-defined property names.

## Translation keys

Keys are semantic and stable, not copies of English text:

```text
preview.actions.start
preview.state.bridge_connecting
components.actions.repair
settings.engines.default_version
errors.runtime.release_not_found
errors.bridge.handshake_mismatch
```

- Do not include punctuation, word order, or a locale name in a key.
- Do not build sentences by concatenating translated fragments.
- Interpolation parameters are named and typed by their caller.
- Plural and count-sensitive messages use the Hermes i18n mechanism rather
  than manual singular/plural branches.
- Engine and component descriptors provide message keys for labels that are
  Toqraq-owned. Vendor proper names may remain descriptor data.
- A translation key is removed when its last caller is deleted.

## Locale resolution and missing keys

Resolution follows the Hermes Desktop plugin contract:

1. active locale;
2. English bundle;
3. raw key as a development-visible failure.

Missing keys are test failures. Runtime resolution is a safety net, not an
accepted release state.

An application error code resolves directly to `errors.<code>`, for example
`runtime.release_not_found` resolves to
`errors.runtime.release_not_found`. The backend does not send a second
message-key identifier and Desktop does not maintain a manual code-to-key map.

English and Simplified Chinese bundles expose identical key sets and
interpolator parameter names. Error keys are mechanically derived from the
declared error-code set and checked statically. Other runtime-generated keys
are prohibited because their locale parity cannot be proven.

## Context injection

The `pre_llm_call` context capsule contains machine facts, not localized UI
copy:

- project and engine identity;
- exact runtime version;
- process and feature readiness;
- ready preview kind and size when available;
- capability IDs;
- relevant namespaced skill names.

It does not contain full errors, logs, trees, binary data, translation bundles,
diagnostics, recent failures, or repeated explanatory prose. Detailed evidence
remains behind an explicit tool request.

## Testing requirements

The error and i18n suite must prove:

- every expected exception has a unique code and category, and a matching
  `errors.<code>` translation key;
- category-to-HTTP mapping is complete;
- Tool and HTTP presenters emit the same error object;
- request validation uses the shared envelope;
- unexpected errors hide their cause publicly and log the trace ID;
- secret and unsafe path fixtures are redacted;
- locale bundles have identical keys and interpolation parameters;
- every referenced translation key exists;
- no Desktop user-visible literal bypasses i18n;
- diagnostics remain bounded and pageable;
- caller cancellation is not presented as an ordinary application error; the
  Bridge-only `request.cancelled` terminal settles its internal work owner.

The complete verification matrix lives in [testing.md](testing.md).
