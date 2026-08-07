"""Validated deterministic evidence values for one Godot candidate build."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from toqraq.components.content import ComponentTreeFingerprint
from toqraq.components.release import ComponentIdentity
from toqraq.core.capability_ids import (
    MANDATORY_BRIDGE_CAPABILITY_IDS,
    MANDATORY_ENGINE_CAPABILITY_IDS,
)
from toqraq.core.runtime import validate_opaque_runtime_id
from toqraq.engines.godot.identity import (
    GODOT_BRIDGE_ID,
    GODOT_BRIDGE_PROTOCOL,
    GODOT_EDITOR_ENTRY_POINT,
    GODOT_RUNTIME_DISTRIBUTION_ID,
)

CANDIDATE_PACKAGE_NAME = "engine.godot-windows-x86_64.zip"
CANDIDATE_PROVENANCE_NAME = "provenance.json"
CANDIDATE_CHECKSUM_NAME = "SHA256SUMS"
CANDIDATE_SCHEMA = "toqraq.godot-candidate.v2"
GODOT_CANDIDATE_SCONS_ARGUMENTS = (
    "platform=windows",
    "target=editor",
    "arch=x86_64",
    "production=yes",
    "d3d12=no",
    "accesskit=no",
    "winrt=no",
    "angle=no",
    "tests=yes",
)

_UPSTREAM_REPOSITORY = "https://github.com/godotengine/godot"
_STABLE_TAG = re.compile(r"^[0-9]+\.[0-9]+(?:\.[0-9]+)?-stable$")
_GIT_ID = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^[1-9][0-9]*$")
_SCONS_ARGUMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*=[A-Za-z0-9][A-Za-z0-9._+-]*$")


@dataclass(frozen=True, slots=True, kw_only=True)
class GodotCandidateBuildFacts:
    """Exact source and build facts supplied by the candidate workflow."""

    upstream_tag: str
    upstream_commit: str
    toqraq_commit: str
    module_git_tree: str
    recipe_sha256: str
    build_id: str
    distribution_id: str
    workflow_run_id: str
    workflow_run_attempt: int
    runner_image: str
    runner_image_version: str
    python_version: str
    scons_version: str
    scons_arguments: tuple[str, ...]

    def __post_init__(self) -> None:
        """Reject incomplete, path-bearing, or internally inconsistent facts."""
        _validate_candidate_identity(self)
        _validate_workflow_environment(self)
        _validate_scons_options(self.scons_arguments)
        _validate_derived_identity(self)


def _validate_candidate_identity(facts: GodotCandidateBuildFacts) -> None:
    """Validate immutable source, recipe, and embedded distribution identities."""
    if _STABLE_TAG.fullmatch(facts.upstream_tag) is None:
        raise ValueError("upstream tag must be one exact stable tag")
    for value in (facts.upstream_commit, facts.toqraq_commit, facts.module_git_tree):
        if _GIT_ID.fullmatch(value) is None:
            raise ValueError("source identities must be lowercase full Git object IDs")
    if _SHA256.fullmatch(facts.recipe_sha256) is None:
        raise ValueError("recipe digest must be lowercase SHA-256")
    validate_opaque_runtime_id(facts.build_id)
    if facts.distribution_id != GODOT_RUNTIME_DISTRIBUTION_ID:
        raise ValueError("candidate distribution does not match the Godot contribution")


def _validate_workflow_environment(facts: GodotCandidateBuildFacts) -> None:
    """Validate the exact workflow attempt and bounded runner facts."""
    if _RUN_ID.fullmatch(facts.workflow_run_id) is None:
        raise ValueError("workflow run ID must be a positive decimal string")
    if (
        isinstance(facts.workflow_run_attempt, bool)
        or not isinstance(facts.workflow_run_attempt, int)
        or facts.workflow_run_attempt <= 0
    ):
        raise ValueError("workflow run attempt must be a positive integer")
    for value in (
        facts.runner_image,
        facts.runner_image_version,
        facts.python_version,
        facts.scons_version,
    ):
        _validate_environment_fact(value)


def _validate_scons_options(arguments: tuple[str, ...]) -> None:
    """Require the one reviewed unique intrinsic option vector."""
    if not arguments:
        raise ValueError("candidate requires the reviewed SCons option vector")
    keys: list[str] = []
    for argument in arguments:
        if len(argument) > 256 or _SCONS_ARGUMENT.fullmatch(argument) is None:
            raise ValueError("SCons option is not a bounded key-value argument")
        keys.append(argument.partition("=")[0])
    if len(set(keys)) != len(keys):
        raise ValueError("SCons option keys must be unique")
    if arguments != GODOT_CANDIDATE_SCONS_ARGUMENTS:
        raise ValueError("SCons options must equal the reviewed candidate vector")


def _validate_derived_identity(facts: GodotCandidateBuildFacts) -> None:
    """Recompute the recipe and build IDs from their immutable inputs."""
    expected_recipe = candidate_recipe_sha256(
        facts.upstream_commit,
        facts.module_git_tree,
        facts.scons_arguments,
    )
    if facts.recipe_sha256 != expected_recipe:
        raise ValueError("recipe digest does not match source and SCons facts")
    expected_build = (
        f"gh.{facts.workflow_run_id}.{facts.workflow_run_attempt}.{facts.recipe_sha256}"
    )
    if facts.build_id != expected_build:
        raise ValueError("embedded build ID does not match workflow identity")


def candidate_recipe_sha256(
    upstream_commit: str,
    module_git_tree: str,
    scons_arguments: tuple[str, ...],
) -> str:
    """Return the workflow's canonical source-and-options recipe digest."""
    recipe = f"{upstream_commit}\n{module_git_tree}\n{' '.join(scons_arguments)}"
    return hashlib.sha256(recipe.encode("utf-8")).hexdigest()


def candidate_provenance(
    facts: GodotCandidateBuildFacts,
    identity: ComponentIdentity,
    fingerprint: ComponentTreeFingerprint,
    package_bytes: int,
) -> dict[str, object]:
    """Project validated build and component facts into the v2 evidence schema."""
    scons_arguments = [
        *facts.scons_arguments,
        f"toqraq_build_id={facts.build_id}",
        f"toqraq_distribution_id={facts.distribution_id}",
    ]
    return {
        "schema": CANDIDATE_SCHEMA,
        "source": {
            "upstream_repository": _UPSTREAM_REPOSITORY,
            "upstream_tag": facts.upstream_tag,
            "upstream_commit": facts.upstream_commit,
            "toqraq_commit": facts.toqraq_commit,
            "module_git_tree": facts.module_git_tree,
        },
        "build": {
            "recipe_sha256": facts.recipe_sha256,
            "scons_arguments": scons_arguments,
            "workflow_run_id": facts.workflow_run_id,
            "workflow_run_attempt": facts.workflow_run_attempt,
            "environment": {
                "runner_image": facts.runner_image,
                "runner_image_version": facts.runner_image_version,
                "python_version": facts.python_version,
                "scons_version": facts.scons_version,
            },
        },
        "component": {
            "identity": identity.model_dump(mode="json"),
            "package_file": CANDIDATE_PACKAGE_NAME,
            "package_bytes": package_bytes,
            "installed_bytes": fingerprint.total_bytes,
            "install_strategy": "archive.zip",
            "expected_tree_sha256": fingerprint.tree_sha256,
            "entry_points": [
                {
                    "name": GODOT_EDITOR_ENTRY_POINT,
                    "relative_path": "bin/godot.exe",
                    "executable": True,
                }
            ],
            "files": [
                {
                    "relative_path": value.relative_path,
                    "size": value.size,
                    "sha256": value.sha256,
                }
                for value in fingerprint.files
            ],
        },
        "runtime_contract": {
            "distribution_id": GODOT_RUNTIME_DISTRIBUTION_ID,
            "bridge_id": GODOT_BRIDGE_ID,
            "bridge_protocol": GODOT_BRIDGE_PROTOCOL,
            "capabilities": sorted(MANDATORY_ENGINE_CAPABILITY_IDS),
            "bridge_capabilities": sorted(MANDATORY_BRIDGE_CAPABILITY_IDS),
        },
    }


def canonical_candidate_json(value: object) -> bytes:
    """Encode deterministic evidence without environment-dependent whitespace."""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _validate_environment_fact(value: str) -> None:
    """Reject path-bearing or unbounded runner metadata."""
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
        or len(value) > 128
        or any(character in value for character in "/\\\r\n\0")
    ):
        raise ValueError("candidate environment fact is invalid")
