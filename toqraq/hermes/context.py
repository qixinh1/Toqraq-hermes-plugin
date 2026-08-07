"""Minimal public Hermes registration boundary used by Toqraq."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Protocol

ToolHandler = Callable[..., Awaitable[str]]
HookResult = None | str | dict[str, str]
HookHandler = Callable[..., HookResult | Awaitable[HookResult]]
Disposer = Callable[[], Awaitable[None] | None]


class HermesPluginContext(Protocol):
    """Host operations required while registering the base plugin."""

    def register_tool(
        self,
        *,
        name: str,
        toolset: str,
        schema: dict[str, Any],
        handler: ToolHandler,
        is_async: bool,
    ) -> None:
        """Register one asynchronous model tool."""
        ...

    def register_hook(self, name: str, callback: HookHandler) -> None:
        """Register one Hermes lifecycle hook."""
        ...

    def register_disposer(self, disposer: Disposer) -> None:
        """Register the cleanup owner for this loaded plugin instance."""
        ...

    def register_skill(
        self,
        name: str,
        path: Path,
        description: str = "",
    ) -> None:
        """Register one host-namespaced skill stored at an exact file path."""
        ...
