# Project Inventory Contract

This document owns Toqraq's first detailed project-file perception operation.
It is a bounded metadata inventory for the calling Hermes task, not a project
database, search engine, file API, or engine-support claim.

## Public operation

Hermes exposes one owner-bound tool:

```text
toqraq_project_read_inventory
```

The model may select an optional project-relative scope, an optional set of
categories, an opaque continuation cursor, and a page limit. It cannot supply a
task ID, project root, engine ID, runtime version, or another session selector.
There is no REST or Desktop surface for this operation.

The result contains only:

- the recognized engine ID and binding source (`live` or `workspace`);
- one opaque inventory-shape revision;
- the canonical scope and effective category selection;
- fixed observed counts for all six categories;
- visited entries and directories, policy and link exclusions, unreadable and
  unclassified counts, and completeness;
- the filtered total count, one stable page, truncation, and next cursor;
- project-relative entry path, category, and an optional declaration name.

It never returns an absolute path, source body, configuration value, file byte
size, timestamp, permission, link target, engine executable, or credential.

## Binding and ownership

One read resolves exactly one project incarnation for the caller's Hermes
`task_id`:

1. use the current live `EngineSession` when that task owns one;
2. otherwise use the exact recognized `WorkspaceContextSnapshot` object;
3. otherwise raise `project.not_bound`;
4. look up the `EngineProjectFormat` for that binding's engine ID;
5. run its inventory reader against the captured immutable project root;
6. re-resolve the preferred binding after the scan and require the same source
   and exact owner object.

The final identity comparison prevents a stopped or replaced game, workspace
replacement, live-game appearance during a workspace read, and ABA return to
the same path from publishing stale facts. A replacement raises the existing
`perception.stale` failure. Task A can never select or observe task B's
binding.

The service remains usable with `EngineCatalog(())`: project recognition and
inventory belong to `ProjectFormatCatalog`, not runtime admission.

## Engine boundary

Every `EngineProjectFormat` contains one stable engine ID, one `ProjectProbe`,
and one `ProjectInventoryReader`. Composition rejects a mismatched or missing
port. The reader synchronously returns one immutable bounded snapshot:

```text
ProjectInventoryReader.scan(project_root, scope, cancellation)
  -> ProjectInventorySnapshot(engine_id, entries, statistics)
```

Core owns the pure values, reader protocol, categories, lexical validators,
and global limits. The reader owns engine-native scope confinement,
classification, exclusions, and scan statistics. The service owns task
binding, worker lifetime, stable order, category filtering, shape revision,
strict stateless cursor decoding, and pagination. The Hermes presenter only
validates, routes, and serializes the strict Pydantic contracts.

## Categories

The initial closed metadata categories are:

| Category | Meaning |
| --- | --- |
| `scene` | engine scene or level source |
| `script` | executable project script source |
| `resource` | engine resource or imported media source |
| `setting` | project configuration file or declared key name |
| `dependency` | extension, plugin, or autoload declaration |
| `input` | declared input action name |

An entry is unique by `(path, category, name)`. `name` is absent for an ordinary
file and may identify a declaration whose value remains private. Common code
does not infer categories from extensions; each format reader does.

## Scope, order, revision, and pagination

Paths use `/`, are relative to the captured project root, contain no empty,
`.` or `..` segment, and obey the Core UTF-8 byte limit. Scope uses the same
lexical form and reaches the reader before traversal. The reader checks every
segment without following links, requires a policy-visible directory, and
scans only that subtree. It cannot select a file, unreadable directory, link,
or reparse point. No scope means the complete policy-visible inventory. Root
marker declarations therefore do not appear under a nested scope.

The service canonicalizes category selection in the declared category order
and sorts entries by Unicode path, category, then declaration name. It computes
the shape revision from the engine ID, completeness, and the complete sorted
unfiltered entry identities. File-content-only changes do not change an
inventory-shape revision.

A continuation cursor is canonical unpadded base64url containing one fixed,
versioned JSON object. It binds shape revision, canonical scope, effective
categories, and next offset. A process secret adds no authorization because a
cursor selects only metadata already visible to its task and every field is
validated, so there is no HMAC or server cache. A malformed schema, different
query, out-of-range offset, or changed inventory raises `perception.stale`; the
service never guesses a page. Every continuation performs a new bounded scan
and verifies its revision.

Category and total counts are exact for observed records. They are complete
policy-visible counts when `complete` is true and lower bounds otherwise.
Policy and link exclusions have distinct counters and do not make a scan
incomplete. Reaching a scan bound stops with `complete=false`; page `truncated`
means only that another revision-bound page exists.

The global policy limits are code-owned and directly tested:

- 64 entries per page, with a default of 32;
- 16,384 classified records and 16,384 visited filesystem entries;
- 2,048 opened directories and 64 directory levels;
- 512 UTF-8 bytes per relative path;
- 256 UTF-8 bytes per declaration name;
- 1,024 bytes per opaque cursor.

## Worker cancellation

Filesystem scanning runs in one named `asyncio.to_thread` task so it never
blocks the host event loop. The service owns that task and a thread-safe
cancellation event. Caller cancellation sets the event, continues to observe
the worker through completion despite repeated cancellation, then re-raises
the caller cancellation. The reader checks cancellation before each directory,
entry, and marker declaration. The scan has no detached thread, background
index, watcher, cache, or cleanup resource after the call returns.

## Godot 4 reader

The Godot reader uses explicit `os.scandir` traversal without following links.
It rejects or excludes symbolic links and Windows reparse points before
descending or classifying. It excludes generated and VCS trees, hidden paths,
Godot import sidecars, and secret-like filenames. Inaccessible nested entries
are omitted and make the snapshot incomplete without exposing their paths.

`project.godot` is the only file opened for declaration metadata. The reader
requires a regular non-reparse marker, uses `O_NOFOLLOW` where the operating
system provides it, applies the existing 16 MiB bound, and compares its
`lstat` and opened `fstat` identities before and after the read. Windows has no
equivalent standard-library atomic no-follow open, so an adversarial exchange
between those checks remains an operating-system limitation; no bytes or
values from a mismatched identity are published. The reader decodes UTF-8 with
BOM support and reuses `GodotProjectFile.parse`. It emits key names but never
values. Input section keys become `input`; autoload and editor-plugin keys
become `dependency`. General configuration keys are not expanded; the marker
file itself is the `setting` entry.

Godot scenes, scripts, resources, extension files, plugin manifests, and
configuration files are classified from an explicit engine-owned extension or
filename table. Unknown files are not promoted to an invented common kind.

## Failures

- `project.not_bound`: the caller owns neither a live game nor a recognized
  workspace.
- `project.invalid`: the bound root, scope, or marker cannot be scanned safely.
- `engine.not_found`: the binding names no registered project format.
- `perception.stale`: the binding, inventory shape, query, cursor, or offset is
  no longer the one that created the page.
- `request.invalid`: the public request violates its strict Pydantic schema.

Only `project.not_bound` is new. All failures use the shared safe error
envelope; arbitrary operating-system text and paths do not enter error details.

## Acceptance

Focused tests prove task isolation, live-session priority, workspace fallback,
replacement and ABA rejection, cooperative cancellation, deterministic order,
category and scope filtering, boundary pages, strict contract invariants,
cursor schema/query/revision rejection, engine-ID composition, Hermes schema
and owner routing, and Godot handling of links, Windows reparse points,
unreadable paths, generated paths, marker value sentinels, and secret-like
names. Platform-specific junction and ACL cases run only where the operating
system can create them and are reported explicitly when unavailable.
