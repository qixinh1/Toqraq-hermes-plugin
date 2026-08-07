"""Conditional bounded game or workspace context for one Hermes model turn."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeAlias

from ..contracts.sessions import SessionResult
from ..core.errors import ToqraqError
from ..services.workspace_context import WorkspaceContextSnapshot
from .skills import BUNDLED_SKILLS

if TYPE_CHECKING:
    from ..services.container import Container

MAX_CONTEXT_CAPSULE_CHARACTERS = 2_048
MAX_CONTEXT_PROJECT_CHARACTERS = 512
MAX_CONTEXT_CAPABILITY_CHARACTERS = 640

ContextHookResult: TypeAlias = dict[str, str] | None
ContextHook: TypeAlias = Callable[..., ContextHookResult]


def build_context_hook(container: Container) -> ContextHook:
    """Build a synchronous hook over cached session and workspace snapshots."""

    def provide(**kwargs: Any) -> ContextHookResult:
        owner = kwargs.get("task_id")
        if not isinstance(owner, str) or not owner:
            return None
        try:
            session = container.session_service.find(owner)
        except (ToqraqError, ValueError):
            return None
        if session is not None:
            return {"context": render_context_capsule(session)}
        try:
            workspace = container.workspace_context_service.find(owner)
        except (ToqraqError, ValueError):
            return None
        if workspace is None:
            return None
        return {"context": render_workspace_context_capsule(workspace)}

    return provide


def render_context_capsule(session: SessionResult) -> str:
    """Render only stable identity, readiness, geometry, and capability facts."""
    if not isinstance(session, SessionResult):
        raise ValueError("context session result is invalid")
    runtime = session.runtime
    lines = [
        "[Toqraq live game]",
        f"owner_task: {session.id}",
        f"run_revision: {session.run_revision}",
        f"project: {_quoted_tail(session.project_dir, MAX_CONTEXT_PROJECT_CHARACTERS)}",
        (
            "runtime: "
            f"{runtime.engine} {runtime.version} "
            f"({runtime.platform}/{runtime.architecture}; {runtime.build_id})"
        ),
        f"process: {session.process_state.value}",
        (
            "readiness: "
            f"preview={session.preview.state.value}, "
            f"perception={session.perception.state.value}, "
            f"control={session.control.state.value}"
        ),
    ]
    surface = session.preview.surface
    if surface is not None:
        lines.append(
            "preview: "
            f"{surface.kind.value} "
            f"{surface.viewport_size.width}x{surface.viewport_size.height}"
        )
    lines.extend(
        (
            f"capabilities: {_bounded_sequence(session.capabilities)}",
            "skills: " + ", ".join(f"toqraq:{name}" for name, _description in BUNDLED_SKILLS),
        )
    )
    rendered = "\n".join(lines)
    if len(rendered) > MAX_CONTEXT_CAPSULE_CHARACTERS:
        raise ValueError("context capsule exceeds its bound")
    return rendered


def render_workspace_context_capsule(snapshot: WorkspaceContextSnapshot) -> str:
    """Render only task-owned recognized-project facts observed by Desktop."""
    if not isinstance(snapshot, WorkspaceContextSnapshot):
        raise ValueError("workspace context snapshot is invalid")
    lines = [
        "[Toqraq workspace]",
        f"owner_task: {snapshot.owner_id}",
        f"project: {_quoted_tail(snapshot.project_path, MAX_CONTEXT_PROJECT_CHARACTERS)}",
        f"engine: {snapshot.engine_id}",
        f"setup: {snapshot.setup_action.value}",
    ]
    if snapshot.runtime_version is not None:
        lines.append(f"runtime: {snapshot.runtime_version}")
    if snapshot.viewport_size is not None:
        lines.append(f"viewport: {snapshot.viewport_size.width}x{snapshot.viewport_size.height}")
    lines.append("skills: " + ", ".join(f"toqraq:{name}" for name, _description in BUNDLED_SKILLS))
    rendered = "\n".join(lines)
    if len(rendered) > MAX_CONTEXT_CAPSULE_CHARACTERS:
        raise ValueError("context capsule exceeds its bound")
    return rendered


def _quoted_tail(value: str, maximum: int) -> str:
    """Quote untrusted path text and retain its longest fitting tail."""
    encoded = json.dumps(value, ensure_ascii=False)
    if len(encoded) <= maximum:
        return encoded
    lower = 0
    upper = len(value)
    selected = json.dumps("…", ensure_ascii=False)
    while lower <= upper:
        length = (lower + upper) // 2
        suffix = value[-length:] if length else ""
        candidate = json.dumps("…" + suffix, ensure_ascii=False)
        if len(candidate) <= maximum:
            selected = candidate
            lower = length + 1
        else:
            upper = length - 1
    return selected


def _bounded_sequence(values: tuple[str, ...]) -> str:
    """Fit sorted capability identifiers into one explicit character budget."""
    selected: list[str] = []
    used = 0
    for value in values:
        separator = 2 if selected else 0
        if used + separator + len(value) > MAX_CONTEXT_CAPABILITY_CHARACTERS:
            break
        selected.append(value)
        used += separator + len(value)
    omitted = len(values) - len(selected)
    rendered = ", ".join(selected)
    if omitted:
        rendered += f" (+{omitted} more)"
    return rendered or "none"
