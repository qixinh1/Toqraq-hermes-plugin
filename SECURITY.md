# Security Policy

Toqraq launches user projects, downloads executable components, attaches native
windows, and exposes local engine observation and control. Security reports are
handled privately before public discussion.

## Reporting a vulnerability

Use the repository's private vulnerability reporting form in its **Security**
tab. If that form is unavailable, contact the repository maintainers through a
private channel listed by the repository owner. Do not place an exploit,
credential, private project content, or vendor authorization material in a
public issue.

Include, when available:

- affected Toqraq version or commit;
- Hermes Desktop version;
- engine, exact runtime build, bridge version, and operating system;
- whether the issue requires a malicious project, component, network response,
  media file, model tool call, or local process;
- minimal reproduction steps and expected impact;
- relevant trace or operation IDs with secrets removed;
- a suggested fix or boundary, if known.

The maintainers should acknowledge a complete private report, reproduce and
classify it, coordinate a fix and release, and credit the reporter when desired.
Public disclosure should wait until users have a practical update path.

## Supported versions

During the current redesign, only the latest repository revision receives
security fixes. A release policy will list supported published versions when
standard Hermes packaging and certified component releases are available.

An engine version is supported only when it appears in the certified release
records bundled with that Toqraq version and passes the required conformance
suite. A vendor's engine support policy remains separate from Toqraq's bridge
and component support.

## Security design

The normative trust boundaries, supply-chain, archive, process, bridge,
preview, media, path, secret, and test requirements live in
[docs/security.md](docs/security.md). Changes to those requirements update that
document before code.

Important invariants include:

- one Hermes session owns every game resource it creates;
- finalization releases the entire owned resource set;
- managed executables are selected by exact verified identity;
- bridge and web-preview connections are loopback-only and session
  authenticated;
- untrusted data is bounded before allocation or dispatch;
- Toqraq exposes focused operations, not arbitrary shell or engine-code
  execution;
- project mutations are explicit Hermes edits;
- secrets never enter project files, renderer storage, logs, events, command
  lines, or model context.

## Out of scope

The following are not Toqraq vulnerabilities unless Toqraq bypasses a stated
boundary or materially amplifies them:

- arbitrary behavior intentionally implemented by a user-run game project;
- a vulnerability in an engine or vendor installer with no Toqraq-specific
  impact;
- creative-model output quality;
- denial of service requiring the user to deliberately launch an obviously
  unbounded project after Toqraq enforces its documented limits;
- reports based only on an engine or Toqraq version outside the certified
  release records.

These cases may still warrant a private report when the boundary is unclear.
