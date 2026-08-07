"""Structured reader for ``project.godot`` files.

The format is INI-like: a flat header of ``key=value`` pairs, then named
``[sections]`` with their own pairs. Values use Godot's textual Variant
notation; this reader types scalars (quoted strings, integers, floats,
booleans) and preserves everything else as raw text. It never writes.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from types import MappingProxyType
from typing import TypeAlias

from ...core.errors import ProjectIntrospectionError

GODOT_PROJECT_FILE_NAME = "project.godot"
MAX_GODOT_PROJECT_FILE_BYTES = 16 << 20
MAX_GODOT_PROJECT_LINES = 65_536
MAX_GODOT_PROJECT_RECORDS = 16_384

GodotProjectValue: TypeAlias = str | int | float | bool


@dataclass(slots=True)
class _VariantBalance:
    """Incremental delimiter state for one textual Variant value."""

    stack: list[str] = field(default_factory=list)
    quoted: bool = False
    escaped: bool = False

    def consume(self, fragment: str) -> None:
        """Consume one fragment exactly once and reject mismatched delimiters."""
        pairs = {"}": "{", "]": "[", ")": "("}
        for character in fragment:
            if self.quoted:
                if self.escaped:
                    self.escaped = False
                elif character == "\\":
                    self.escaped = True
                elif character == '"':
                    self.quoted = False
                continue
            if character == '"':
                self.quoted = True
            elif character in "{[(":
                self.stack.append(character)
            elif character in pairs and (not self.stack or self.stack.pop() != pairs[character]):
                raise ValueError("mismatched complex-value delimiter")

    @property
    def complete(self) -> bool:
        """Report whether quotes and all container delimiters are closed."""
        return not self.quoted and not self.stack


@dataclass(slots=True)
class _PendingProjectValue:
    """One multiline value accumulated once and joined only when complete."""

    target: dict[str, GodotProjectValue]
    key: str
    started_at: int
    parts: list[str]
    balance: _VariantBalance


@dataclass(frozen=True, slots=True, init=False)
class GodotProjectFile:
    """Parsed view of a ``project.godot`` file."""

    header: Mapping[str, GodotProjectValue]
    sections: Mapping[str, Mapping[str, GodotProjectValue]]

    def __init__(
        self,
        header: dict[str, GodotProjectValue],
        sections: dict[str, dict[str, GodotProjectValue]],
    ) -> None:
        """Freeze the complete parsed value graph at the decode boundary."""
        object.__setattr__(self, "header", MappingProxyType(header.copy()))
        object.__setattr__(
            self,
            "sections",
            MappingProxyType(
                {name: MappingProxyType(values.copy()) for name, values in sections.items()}
            ),
        )

    @classmethod
    def load(cls, project_dir: Path) -> GodotProjectFile:
        """Load and parse the project file of a directory.

        Args:
            project_dir: Directory expected to contain ``project.godot``.

        Returns:
            The parsed project file.

        Raises:
            ProjectIntrospectionError: If the file is missing or malformed.
        """
        path = project_dir / GODOT_PROJECT_FILE_NAME
        if not path.is_file():
            raise ProjectIntrospectionError(
                parameters={"engine": "godot"},
                details={"reason": "project_marker_missing"},
            )
        try:
            with path.open("rb") as stream:
                payload = stream.read(MAX_GODOT_PROJECT_FILE_BYTES + 1)
            if len(payload) > MAX_GODOT_PROJECT_FILE_BYTES:
                raise ProjectIntrospectionError(
                    parameters={"maximum_bytes": MAX_GODOT_PROJECT_FILE_BYTES},
                    details={"reason": "project_file_too_large"},
                )
            text = payload.decode("utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise ProjectIntrospectionError(
                details={"reason": "project_file_unreadable"},
                cause=exc,
            ) from exc
        return cls.parse(text)

    @classmethod
    def parse(
        cls,
        text: str,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> GodotProjectFile:
        """Parse project file text.

        Args:
            text: Raw file content.
            check_cancelled: Optional callback invoked before every input line.

        Returns:
            The parsed project file.

        Raises:
            ProjectIntrospectionError: If the text is malformed.
        """
        header: dict[str, GodotProjectValue] = {}
        sections: dict[str, dict[str, GodotProjectValue]] = {}
        current: dict[str, GodotProjectValue] | None = None
        pending: _PendingProjectValue | None = None
        records = 0
        for lineno, raw in enumerate(StringIO(text), start=1):
            if check_cancelled is not None:
                check_cancelled()
            if lineno > MAX_GODOT_PROJECT_LINES:
                raise ProjectIntrospectionError(
                    parameters={"maximum_lines": MAX_GODOT_PROJECT_LINES},
                    details={"reason": "project_file_too_many_lines"},
                )
            line = raw.strip()
            if pending is not None:
                pending = _continue_pending_value(pending, line)
                continue
            if not line or line.startswith((";", "#")):
                continue
            records += 1
            if records > MAX_GODOT_PROJECT_RECORDS:
                raise ProjectIntrospectionError(
                    parameters={"maximum_records": MAX_GODOT_PROJECT_RECORDS},
                    details={"reason": "project_file_too_many_records"},
                )
            if line.startswith("["):
                current = _start_section(line, lineno, sections)
                continue
            target = header if current is None else current
            pending = _parse_entry(line, lineno, target)
        if pending is not None:
            raise _malformed_value(
                pending.started_at,
                ValueError("unterminated complex value"),
            )
        return cls(header, sections)

    def value(self, section: str, key: str) -> GodotProjectValue | None:
        """Return one typed section value when present.

        Args:
            section: Section name.
            key: Key within the section.

        Returns:
            The parsed scalar or ``None`` when absent.
        """
        values = self.sections.get(section)
        return None if values is None else values.get(key)


def _continue_pending_value(
    pending: _PendingProjectValue,
    line: str,
) -> _PendingProjectValue | None:
    """Append one line and publish a multiline Variant once balanced."""
    try:
        pending.balance.consume("\n")
        pending.balance.consume(line)
    except ValueError as exc:
        raise _malformed_value(pending.started_at, exc) from exc
    pending.parts.append(line)
    if not pending.balance.complete:
        return pending
    _store_value(
        pending.target,
        pending.key,
        "\n".join(pending.parts),
        pending.started_at,
    )
    return None


def _start_section(
    line: str,
    lineno: int,
    sections: dict[str, dict[str, GodotProjectValue]],
) -> dict[str, GodotProjectValue]:
    """Validate and create one uniquely named section."""
    if not line.endswith("]"):
        raise ProjectIntrospectionError(
            parameters={"line": lineno},
            details={"reason": "malformed_section"},
        )
    section = line[1:-1].strip()
    if not section:
        raise ProjectIntrospectionError(
            parameters={"line": lineno},
            details={"reason": "empty_section"},
        )
    if section in sections:
        raise ProjectIntrospectionError(
            parameters={"line": lineno},
            details={"reason": "duplicate_section"},
        )
    created: dict[str, GodotProjectValue] = {}
    sections[section] = created
    return created


def _parse_entry(
    line: str,
    lineno: int,
    target: dict[str, GodotProjectValue],
) -> _PendingProjectValue | None:
    """Validate one unique entry and store or retain its bounded value."""
    key, separator, value = line.partition("=")
    if not separator:
        raise ProjectIntrospectionError(
            parameters={"line": lineno},
            details={"reason": "malformed_entry"},
        )
    key = key.strip()
    if not key:
        raise ProjectIntrospectionError(
            parameters={"line": lineno},
            details={"reason": "empty_key"},
        )
    if key in target:
        raise ProjectIntrospectionError(
            parameters={"line": lineno},
            details={"reason": "duplicate_key"},
        )
    value = value.strip()
    balance = _VariantBalance()
    try:
        balance.consume(value)
    except ValueError as exc:
        raise _malformed_value(lineno, exc) from exc
    if not balance.complete:
        return _PendingProjectValue(target, key, lineno, [value], balance)
    _store_value(target, key, value, lineno)
    return None


def _parse_value(raw: str) -> GodotProjectValue:
    """Type a scalar value, preserving complex values as raw text.

    Args:
        raw: The right-hand side of an entry.

    Returns:
        ``str`` for quoted strings, ``int``/``float``/``bool`` for scalars,
        otherwise the raw text.
    """
    if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
        try:
            decoded: object = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid quoted string") from exc
        if not isinstance(decoded, str):
            raise ValueError("quoted project value is not a string")
        return decoded
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        value = float(raw)
    except ValueError:
        pass
    else:
        return value if math.isfinite(value) else raw
    return raw


def _store_value(
    target: dict[str, GodotProjectValue],
    key: str,
    raw: str,
    lineno: int,
) -> None:
    """Parse one complete value and retain its source line on failure."""
    try:
        target[key] = _parse_value(raw)
    except ValueError as exc:
        raise _malformed_value(lineno, exc) from exc


def _malformed_value(lineno: int, cause: ValueError) -> ProjectIntrospectionError:
    """Create the one public-safe parser failure for a value starting at a line."""
    return ProjectIntrospectionError(
        parameters={"line": lineno},
        details={"reason": "malformed_value"},
        cause=cause,
    )
