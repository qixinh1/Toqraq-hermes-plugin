"""Compose Toqraq's public Hermes registrations."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from functools import partial

from ..core.bridge import validate_bridge_session_id
from ..core.errors import SessionStateError
from ..services.container import Container, dispose_container, get_container
from .context import HermesPluginContext
from .context_capsule import build_context_hook
from .skills import BUNDLED_SKILLS, register_skills
from .tools import build_tools

logger = logging.getLogger(__name__)
_TOOLSET = "toqraq"


def register(ctx: HermesPluginContext) -> None:
    """Register generated tools and lifecycle hooks with injected services."""
    container = get_container()
    registrations = build_tools(container)
    for tool in registrations:
        ctx.register_tool(
            name=tool.name,
            toolset=_TOOLSET,
            schema=tool.schema,
            handler=tool.handler,
            is_async=True,
        )
    ctx.register_hook("on_session_finalize", _finalizer(container))
    ctx.register_hook("pre_llm_call", build_context_hook(container))
    register_skills(ctx)
    ctx.register_disposer(partial(dispose_container, container))
    logger.info(
        "toqraq: registered %d tools and %d skills",
        len(registrations),
        len(BUNDLED_SKILLS),
    )


def _finalizer(container: Container) -> Callable[..., Awaitable[None]]:
    """Build the Hermes finalizer over the same registered service graph."""

    async def finalize(**kwargs: object) -> None:
        session_id = kwargs.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise SessionStateError(details={"reason": "finalization_session_id_missing"})
        try:
            validate_bridge_session_id(session_id)
        except ValueError as error:
            raise SessionStateError(
                details={"reason": "finalization_session_id_invalid"},
                cause=error,
            ) from error
        container.workspace_context_service.clear(session_id)
        await container.session_service.finalize(session_id)

    return finalize


__all__ = ["register"]
