"""Bounded standard Godot project-file parsing tests."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
from types import MappingProxyType
from typing import cast

import pytest
from toqraq.core.errors import ProjectIntrospectionError
from toqraq.engines.godot import project as project_module
from toqraq.engines.godot.project import GodotProjectFile


def test_multiline_variant_values_are_preserved_without_interpretation() -> None:
    project = GodotProjectFile.parse(
        """config_version=5
[input]
move={
"deadzone": 0.5,
"events": [Object(InputEventKey, "physical_keycode": 65)]
}
[display]
window/size/viewport_width=960
"""
    )

    assert project.header == {"config_version": 5}
    assert project.value("input", "move") == (
        '{\n"deadzone": 0.5,\n"events": [Object(InputEventKey, "physical_keycode": 65)]\n}'
    )
    assert project.value("display", "window/size/viewport_width") == 960
    assert project.value("missing", "value") is None
    assert isinstance(project.header, MappingProxyType)
    assert isinstance(project.sections["input"], MappingProxyType)


def test_scalar_values_are_typed_without_retaining_non_finite_numbers() -> None:
    project = GodotProjectFile.parse(
        """config_version=5
[values]
title="Toqraq"
enabled=true
count=-12
ratio=0.5
overflow=1e999
"""
    )

    assert project.sections["values"] == {
        "title": "Toqraq",
        "enabled": True,
        "count": -12,
        "ratio": 0.5,
        "overflow": "1e999",
    }


def test_parsed_project_values_are_immutable() -> None:
    project = GodotProjectFile.parse('config_version=5\n[application]\nname="Game"\n')

    with pytest.raises(FrozenInstanceError):
        project.header = {}  # type: ignore[misc]
    with pytest.raises(TypeError):
        cast(dict[str, object], project.header)["config_version"] = 6
    with pytest.raises(TypeError):
        cast(dict[str, object], project.sections["application"])["name"] = "Changed"


@pytest.mark.parametrize(
    "value",
    [
        '{\n"deadzone": 0.5',
        '{\n"events": []\n]',
        '"unterminated',
    ],
)
def test_malformed_multiline_values_report_their_start_line(value: str) -> None:
    with pytest.raises(ProjectIntrospectionError) as caught:
        GodotProjectFile.parse(f"config_version=5\n[input]\nmove={value}\n")

    assert caught.value.parameters == {"line": 3}
    assert caught.value.details == {"reason": "malformed_value"}


def test_large_multiline_variant_is_preserved() -> None:
    lines = ["items=[", *(f'"item-{index}",' for index in range(8_000)), "]"]

    project = GodotProjectFile.parse("\n".join(lines))

    value = project.header["items"]
    assert isinstance(value, str)
    assert value.startswith('[\n"item-0",')
    assert value.endswith('\n"item-7999",\n]')


def test_parser_checks_cancellation_before_each_line() -> None:
    calls = 0

    def check_cancelled() -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        GodotProjectFile.parse(
            "config_version=5\n[input]\njump=true\n",
            check_cancelled=check_cancelled,
        )

    assert calls == 3


@pytest.mark.parametrize(
    ("constant", "text", "reason"),
    [
        (
            "MAX_GODOT_PROJECT_LINES",
            "\n".join(("# first", "# second", "# third")),
            "project_file_too_many_lines",
        ),
        (
            "MAX_GODOT_PROJECT_RECORDS",
            "config_version=5\n[input]\njump=true",
            "project_file_too_many_records",
        ),
    ],
)
def test_parser_structure_bounds_reject_object_inflation(
    monkeypatch: pytest.MonkeyPatch,
    constant: str,
    text: str,
    reason: str,
) -> None:
    monkeypatch.setattr(project_module, constant, 2)

    with pytest.raises(ProjectIntrospectionError) as caught:
        GodotProjectFile.parse(text)

    assert caught.value.details == {"reason": reason}
