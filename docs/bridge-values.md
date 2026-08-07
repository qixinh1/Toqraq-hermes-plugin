# Engine Bridge Value Baseline

This document owns the exact common read-value and capture bounds carried by
the authenticated transport in [bridge.md](bridge.md). Engine contributions
may add namespaced typed facts but cannot weaken these limits.

All five read methods use the authenticated connection as their run scope; no
params or result can name another session or run. Object references, revisions,
and cursors are opaque ASCII tokens of 1 to 128 characters. They begin with an
ASCII letter or digit and contain only letters, digits, `.`, `_`, `:`, or `-`.
Timestamps are non-negative Unix milliseconds no greater than JavaScript's
exact integer maximum.

Engine extension data is a tuple of at most 32 facts with unique namespaced
field IDs. Each fact has an explicit `text`, `integer`, `number`, `boolean`, or
`reference` discriminator. Text is at most 1,024 UTF-8 bytes, integers are
cross-language exact, numbers are finite, and references use the same opaque
run-scoped value. There is no extension object, recursive value, or untyped
JSON field.

| Method | Required selection and bounds | Result |
| --- | --- | --- |
| `toqraq.hierarchy.read` | depth 0 through 16, optional root/name/native-type filters, optional revision/cursor pair, limit 1 through 256 | one page and its revision, observation time, exact returned count, explicit truncation, and continuation cursor |
| `toqraq.object.read` | 1 through 64 unique references, 1 through 4 selected field groups, optional revision, per-value bytes 1 through 16,384, total value bytes 1 through 262,144 | one snapshot containing only the selected property, component, resource, or extension groups and their explicit total counts/truncation |
| `toqraq.diagnostics.read` | explicit source and severity selections, optional revision/cursor pair, limit 1 through 200 | one strictly sequenced page, revision, observation time, truncation, and continuation cursor |
| `toqraq.metrics.read` | at least one selected group or metric name, optional revision, limit 1 through 128 | one timestamped typed snapshot, total available count, truncation, unavailable selections, and bounded collection cost |
| `toqraq.frame.capture` | maximum dimensions, `native` or contain scaling, and maximum 1 through 67,108,864 bytes | real viewport dimensions, capture time, then a fully validated fixed-PNG transfer |

The frame byte range above is the common contract ceiling. Each engine bridge
offers an intrinsic limit at or below that ceiling, and the host uses the
smaller negotiated value. The current Godot Windows candidate offers
33,554,432 PNG bytes; the 16-byte binary transfer prefix is not part of that
payload length.

A hierarchy cursor is valid only with the revision that created it. The same
rule applies to a diagnostic cursor. `truncated` is true exactly when a
continuation cursor exists. Hierarchy entries return a child count and a
bounded native component-type summary. Object results echo the selected field
groups; an omitted group is distinguishable from a selected empty group.

Object property values are limited to null, boolean, exact integer, finite
number, bounded text, opaque reference, or a bounded summary. Component and
resource relations use opaque references. Recursive engine values, large text,
and binary values become summaries; they never cross as JSON containers.

Metric names, groups, units, and unavailable selections are namespaced IDs.
Metric samples are explicitly boolean, integer, or finite number values and
carry their own observation time. A metrics snapshot is not paged across a
mutable revision: truncation is reported with the total available count and
the caller narrows its selection.

The frame JSON announcement contains no media bytes or base64 text. It has one
32-character lowercase hexadecimal transfer ID, `image/png` MIME type, encoded
dimensions, byte length, SHA-256 digest, and opaque frame revision. The exactly
matching binary frame must follow immediately. The capture call completes only
after the receiver validates its ID, length, digest, dimensions, and PNG bytes.
