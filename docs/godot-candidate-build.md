# Godot Candidate Build

This document owns the build and admission path for an instrumented Godot
candidate. It does not describe a supported runtime or an end-user
installation source. Production registers only the read-only standard Godot
project format, with no engine contribution or certified component release.

## Outcome

Toqraq builds against an exact untouched Godot source revision while keeping
all Toqraq engine code in this repository. Updating Godot is therefore a new
checkout and conformance run, not a source merge into a long-lived fork.

The candidate workflow is
[godot-candidate.yml](../.github/workflows/godot-candidate.yml). It is manual
and requires both:

- one exact stable tag such as `4.7.1-stable`;
- the lowercase 40-character commit to which that tag resolves.

The workflow never discovers, ranks, or selects a latest tag. A tag/commit
mismatch fails before compilation.

## Recorded local candidate observation

The repository records an earlier local Windows Godot 4.7.1 editor observation
with `tests=yes` and the external Toqraq module, linked and executed using the
reviewed llvm-mingw/ThinLTO candidate toolchain. The recorded focused native
run passed 27 cases and 197 assertions. The production Python listener and
feature adapters then exercised that executable against the fixture project,
including all eight native capabilities, all five input families,
pause/two-frame step/resume, and 960x540 to 480x270 contain-scaled PNG capture
with byte length, SHA-256, and dimension validation.

No machine-readable report or candidate artifact from that run is committed.
The exact counts are therefore historical observation, not evidence that can
be reproduced from this repository revision alone.

This is recorded native-boundary history, not a catalog admission. The exercised
binary has no published immutable package URL, bundled digest-pinned component
record, clean-store lifecycle proof, or complete interactive standard-install
result. A recognized Godot project remains `runtime_unavailable` in ordinary
Setup.

## Source composition

The workflow checks out this repository and `godotengine/godot` into separate
directories. It passes the absolute `engine/godot/modules` collection through
Godot's official `custom_modules` SCons option. It never copies the module into
the upstream tree, patches an upstream file, creates a release branch, or
pushes to a fork.

The Windows candidate is built with the one reviewed argument set owned by the
workflow:

```text
platform=windows target=editor arch=x86_64 production=yes
d3d12=no accesskit=no winrt=no angle=no tests=yes
toqraq_build_id=<workflow-owned unique opaque ID>
toqraq_distribution_id=toqraq.godot.windows.x86_64
```

Optional SDK availability cannot silently change the candidate. A future
argument change updates this document, build evidence, component identity, and
conformance expectations together.

Before compilation the workflow hashes the exact upstream commit, Toqraq
module Git tree, and reviewed base argument string into a recipe digest. It
combines that digest with the immutable GitHub workflow run ID and attempt to
form `toqraq_build_id`. The value is compiled into the module and recorded in
provenance. The distribution ID is the fixed certified distribution target,
not a user-facing channel. The final executable digest remains the component
release identity; certification binds that digest to the embedded build ID.

The module rejects a build without both values or with a value outside the
shared opaque/symbolic identifier syntax. It derives the Godot version from the
compiled upstream version macros and never accepts runtime identity from the
launch bootstrap.

SCons is a build-only dependency pinned with a package digest in
`engine/godot/build-requirements.txt`. GitHub Actions are referenced by full
commit. The workflow has read-only repository permission and no release step.
Only after linking, it installs the closed hash-pinned candidate verification
set from `engine/godot/candidate-test-requirements.txt`; those wheels cannot
alter the engine binary and never enter the plugin runtime.

The three direct verification requirements live in
`engine/godot/candidate-test-requirements.in`. Regenerate the Windows CPython
3.12 closure with the reviewed lock generator; never edit its output:

```powershell
uv pip compile engine/godot/candidate-test-requirements.in --python-platform x86_64-pc-windows-msvc --python-version 3.12 --only-binary=:all: --generate-hashes --no-annotate --no-header --default-index https://pypi.org/simple --output-file engine/godot/candidate-test-requirements.txt
```
The `windows-latest` image and Python `3.12` selector can resolve differently
between runs. Provenance records the resulting runner image/version, Python
patch, and SCons version, but the candidate does not claim a byte-reproducible
engine build or complete compiler/SDK identity. Those facts remain admission
evidence even though the ZIP assembly itself is deterministic for equal inputs.

## Candidate package and evidence

The build-only `scripts/package_godot_candidate.py` produces one deterministic
ZIP without entering runtime composition:

```text
engine.godot-windows-x86_64.zip
|-- bin/godot.exe
`-- notices/
    |-- godot/LICENSE.txt
    |-- godot/COPYRIGHT.txt
    `-- toqraq/LICENSE.txt
```

It preserves the four input files byte-for-byte, emits no directory entries,
uses stored ZIP members with fixed names, order, timestamp, file type, mode,
and empty metadata, and never includes `component.json` or provenance inside
the component. It stages and fingerprints the tree with the production
component policy, writes the archive, extracts it with the production ZIP
reader, and requires the extracted fingerprint to be identical before
publishing the output directory. Existing output is never overwritten.

The build-only `scripts/verify_godot_candidate.py` independently reopens that
published directory. It accepts only its three exact privately owned files,
bounded canonical JSON without duplicate keys, the reviewed build vector, exact
checksums, and an archive whose production extraction reproduces every declared
file and tree fact. It returns the exact extracted executable and validated
identity to the Bridge integration test; it creates no component release or URL.

The candidate directory contains only the ZIP, canonical `provenance.json`,
and `SHA256SUMS`. Provenance schema `toqraq.godot-candidate.v2` records exact
source identities, recipe and reviewed SCons option vector, workflow/runner
facts, embedded build identity, package/file/tree digests and byte counts,
entry point, distribution, Bridge protocol, and sorted capability sets. It
contains no temporary or absolute build path. Candidate facts intentionally
omit package and provenance URLs; therefore they cannot be parsed as a
`ComponentRelease` or registered in a catalog.

The job:

1. validates the tag and commit syntax and proves they identify the same clean
   upstream tree;
2. builds through the external module collection;
3. runs the compiled Godot tests and version smoke check against the build
   output;
4. proves that no tracked upstream file changed;
5. packages the executable with Godot and Toqraq notices;
6. extracts the final ZIP, verifies its executable against the package evidence,
   and runs the production Python Bridge feature exercise against that exact
   extracted executable;
7. uploads the three-file uncertified candidate directory for seven days.

These facts identify and exercise a candidate; they do not certify it.

## Certification boundary

An uploaded candidate remains unusable by ordinary Setup and Start. It enters
the bundled component catalog only after the same bytes pass:

- common bridge handshake and adversarial protocol tests;
- project detection and exact-runtime preparation tests;
- process-tree, output, cancellation, and finalization tests;
- hierarchy, object, diagnostics, metrics, capture, pause, step, and input
  conformance;
- native preview discovery, attachment, aspect-fit resize, and restoration on
  an interactive Windows desktop;
- clean component-store installation, repair, interruption, and removal;
- license, notices, package layout, digest, and provenance review.

The candidate job does not construct a release record or substitute a local
response adapter for a published source. Certification still requires the same
ZIP from an immutable reviewed HTTPS origin, including clean-store install,
redirect, interruption, resume, verification, repair, lease, and removal
evidence.

Admission creates an immutable component release record in the same
Toqraq plugin revision whose adapter and tests passed. Publication is a
separate gated job; the candidate workflow cannot publish or label support.

## Upstream update

For a new Godot stable release:

1. inspect the official tag and resolve its full commit;
2. dispatch the candidate workflow with those exact values;
3. fix only the external Toqraq module or engine adapter when APIs changed;
4. rerun the complete candidate and conformance matrices;
5. add a catalog record only when every gate passes.

The upstream checkout remains replaceable and disposable. No upstream merge
or conflict-resolution branch is part of this process.

## Official basis

- [Godot custom C++ modules](https://docs.godotengine.org/en/stable/contributing/development/core_and_modules/custom_modules_in_cpp.html)
- [Godot custom-modules build option](https://docs.godotengine.org/en/stable/engine_details/development/compiling/introduction_to_the_buildsystem.html#custom-modules)
- [SCons on PyPI](https://pypi.org/project/SCons/)
