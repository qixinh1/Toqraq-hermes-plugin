"""Tests for pure process-tree commands and observation values."""

from __future__ import annotations

from pathlib import Path

import pytest
from toqraq.core.process_tree import (
    MAX_PROCESS_BOOTSTRAP_BYTES,
    MAX_PROCESS_ENVIRONMENT_NAME_CHARACTERS,
    MAX_PROCESS_ENVIRONMENT_VALUE_CHARACTERS,
    MAX_PROCESS_ENVIRONMENT_VARIABLES,
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessEnvironmentVariable,
    ProcessLaunch,
    ProcessOutputChunk,
    ProcessOutputSnapshot,
    ProcessOutputStream,
)

_EMPTY_ENVIRONMENT = ProcessEnvironment(variables=())
_BOOTSTRAP = ProcessBootstrap(payload=b"test-bootstrap")


def test_process_launch_requires_normalized_absolute_paths(tmp_path: Path) -> None:
    executable = tmp_path / "engine.exe"
    command = ProcessLaunch(
        executable=executable,
        arguments=("--project", "value with spaces"),
        working_directory=tmp_path,
        environment=_EMPTY_ENVIRONMENT,
        bootstrap=_BOOTSTRAP,
    )

    assert command.executable == executable
    assert command.arguments == ("--project", "value with spaces")

    with pytest.raises(ValueError, match="executable"):
        ProcessLaunch(
            executable=Path("engine.exe"),
            arguments=(),
            working_directory=tmp_path,
            environment=_EMPTY_ENVIRONMENT,
            bootstrap=_BOOTSTRAP,
        )


@pytest.mark.parametrize("arguments", [["value"], ("bad\0value",)])
def test_process_launch_rejects_non_vector_or_native_invalid_arguments(
    tmp_path: Path,
    arguments: object,
) -> None:
    with pytest.raises(ValueError, match="argument"):
        ProcessLaunch(
            executable=tmp_path / "engine.exe",
            arguments=arguments,  # type: ignore[arg-type]
            working_directory=tmp_path,
            environment=_EMPTY_ENVIRONMENT,
            bootstrap=_BOOTSTRAP,
        )


def test_process_launch_requires_explicit_typed_environment(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="environment"):
        ProcessLaunch(
            executable=tmp_path / "engine.exe",
            arguments=(),
            working_directory=tmp_path,
            environment=(),  # type: ignore[arg-type]
            bootstrap=_BOOTSTRAP,
        )


def test_process_bootstrap_is_required_bounded_and_repr_redacted(tmp_path: Path) -> None:
    secret = b"credential-must-not-appear"
    bootstrap = ProcessBootstrap(payload=secret)

    assert secret.decode() not in repr(bootstrap)
    assert secret.decode() not in repr(
        ProcessLaunch(
            executable=tmp_path / "engine.exe",
            arguments=(),
            working_directory=tmp_path,
            environment=_EMPTY_ENVIRONMENT,
            bootstrap=bootstrap,
        )
    )
    with pytest.raises(ValueError, match="bootstrap"):
        ProcessBootstrap(payload=b"")
    with pytest.raises(ValueError, match="bootstrap"):
        ProcessBootstrap(payload=b"x" * (MAX_PROCESS_BOOTSTRAP_BYTES + 1))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("lowercase", "value"),
        ("HAS-DASH", "value"),
        ("A" * (MAX_PROCESS_ENVIRONMENT_NAME_CHARACTERS + 1), "value"),
        ("VALID", "bad\0value"),
        ("VALID", "x" * (MAX_PROCESS_ENVIRONMENT_VALUE_CHARACTERS + 1)),
    ],
)
def test_process_environment_variable_rejects_invalid_values(name: str, value: str) -> None:
    with pytest.raises(ValueError, match="environment variable"):
        ProcessEnvironmentVariable(name=name, value=value)


def test_process_environment_is_bounded_and_case_insensitively_unique() -> None:
    variable = ProcessEnvironmentVariable(name="SAFE_VALUE", value="yes")

    with pytest.raises(ValueError, match="duplicated"):
        ProcessEnvironment(variables=(variable, variable))
    with pytest.raises(ValueError, match="collection"):
        ProcessEnvironment(
            variables=tuple(
                ProcessEnvironmentVariable(name=f"VALUE_{index}", value="")
                for index in range(MAX_PROCESS_ENVIRONMENT_VARIABLES + 1)
            )
        )


def test_process_output_snapshot_requires_global_sequence_order() -> None:
    chunks = (
        ProcessOutputChunk(
            sequence=2,
            stream=ProcessOutputStream.STDOUT,
            text="later",
        ),
        ProcessOutputChunk(
            sequence=1,
            stream=ProcessOutputStream.STDERR,
            text="earlier",
        ),
    )

    with pytest.raises(ValueError, match="strictly sequenced"):
        ProcessOutputSnapshot(
            chunks=chunks,
            next_sequence=3,
            truncated=False,
            failed_streams=frozenset(),
        )
