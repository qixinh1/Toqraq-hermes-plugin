"""Hermes package loading, registration, and Dashboard sharing contracts."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

PLUGIN_ROOT = Path(__file__).parents[2]
PLUGIN_MODULE = "hermes_plugins.toqraq"


def _load_package(name: str, entry: Path, package_dir: Path) -> ModuleType:
    """Load one package exactly below its declared import namespace."""
    spec = importlib.util.spec_from_file_location(
        name,
        entry,
        submodule_search_locations=[str(package_dir)],
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_entry() -> ModuleType:
    """Load the repository root under the package shape Hermes uses."""
    for name in tuple(sys.modules):
        if name == PLUGIN_MODULE or name.startswith(f"{PLUGIN_MODULE}."):
            del sys.modules[name]
    parent = sys.modules.get("hermes_plugins")
    if parent is None:
        parent = ModuleType("hermes_plugins")
        parent.__path__ = []  # type: ignore[attr-defined]
        sys.modules["hermes_plugins"] = parent
    return _load_package(PLUGIN_MODULE, PLUGIN_ROOT / "__init__.py", PLUGIN_ROOT)


def load_dashboard() -> ModuleType:
    """Load the API through the same namespaced plugin root."""
    package_name = f"{PLUGIN_MODULE}.dashboard"
    _load_package(
        package_name, PLUGIN_ROOT / "dashboard" / "__init__.py", PLUGIN_ROOT / "dashboard"
    )
    module_name = f"{package_name}.plugin_api"
    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_ROOT / "dashboard" / "plugin_api.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_entry_and_dashboard_share_the_namespaced_container() -> None:
    load_entry()
    dashboard = load_dashboard()
    registration = sys.modules[f"{PLUGIN_MODULE}.toqraq.hermes.registration"]

    assert dashboard.get_container is registration.get_container


def test_successful_disposal_rebuilds_the_graph_in_the_same_module() -> None:
    entry = load_entry()
    containers = sys.modules[f"{PLUGIN_MODULE}.toqraq.services.container"]

    class Context:
        def __init__(self) -> None:
            self.disposer: Any = None

        def register_tool(self, **_kwargs: Any) -> None:
            return

        def register_hook(self, _name: str, _callback: Any) -> None:
            return

        def register_disposer(self, disposer: Any) -> None:
            self.disposer = disposer

        def register_skill(self, _name: str, _path: Path, _description: str = "") -> None:
            return

    first_context = Context()
    entry.register(first_context)
    first = containers.get_container()
    asyncio.run(first_context.disposer())

    second_context = Context()
    entry.register(second_context)
    second = containers.get_container()

    assert second is not first
    asyncio.run(second_context.disposer())


def test_register_wires_tools_and_session_finalization(monkeypatch) -> None:
    entry = load_entry()
    registration = sys.modules[f"{PLUGIN_MODULE}.toqraq.hermes.registration"]
    tool_declarations = sys.modules[f"{PLUGIN_MODULE}.toqraq.hermes.tools"]
    setup_contracts = sys.modules[f"{PLUGIN_MODULE}.toqraq.contracts.setup"]
    setup_result = setup_contracts.SetupResult.model_construct(
        action=setup_contracts.SetupAction.ENGINE_UNAVAILABLE
    )
    tool_names: list[str] = []
    handlers: dict[str, Any] = {}
    hooks: dict[str, Any] = {}
    disposers: list[Any] = []
    skills: list[tuple[str, Path, str]] = []
    finalized: list[str] = []
    cleared: list[str] = []
    closed: list[bool] = []

    class Context:
        def register_tool(self, *, name: str, handler: Any, **_kwargs: Any) -> None:
            tool_names.append(name)
            handlers[name] = handler

        def register_hook(self, name: str, callback: Any) -> None:
            hooks[name] = callback

        def register_disposer(self, disposer: Any) -> None:
            disposers.append(disposer)

        def register_skill(
            self,
            name: str,
            path: Path,
            description: str = "",
        ) -> None:
            skills.append((name, path, description))

    class Sessions:
        @staticmethod
        def find(_session_id: str) -> None:
            return None

        async def finalize(self, session_id: str) -> None:
            finalized.append(session_id)

    class Container:
        session_service = Sessions()

        class WorkspaceContexts:
            @staticmethod
            def find(_session_id: str) -> None:
                return None

            @staticmethod
            def clear(_session_id: str) -> None:
                cleared.append(_session_id)

        workspace_context_service = WorkspaceContexts()

        @staticmethod
        async def close() -> None:
            closed.append(True)

        class SetupService:
            @staticmethod
            async def check(_request: object):
                return setup_result

        setup_service = SetupService()

    monkeypatch.setattr(registration, "get_container", Container)
    entry.register(Context())
    assert hooks["pre_llm_call"](task_id="hermes-1") is None
    asyncio.run(hooks["on_session_finalize"](session_id="hermes-1"))
    asyncio.run(disposers[0]())

    assert tuple(tool_names) == tuple(spec.name for spec in tool_declarations.TOOL_SPECS)
    assert [name for name, _path, _description in skills] == [
        "game-development",
        "asset-workflow",
        "balance",
        "playtest-debug",
    ]
    assert all(path.is_file() and path.name == "SKILL.md" for _name, path, _description in skills)
    assert json.loads(asyncio.run(handlers["toqraq_project_setup"]({}))) == {
        "action": "engine_unavailable"
    }
    assert finalized == ["hermes-1"]
    assert cleared == ["hermes-1"]
    assert closed == [True]


@pytest.mark.parametrize(
    ("session_id", "reason"),
    [
        (None, "finalization_session_id_missing"),
        ("", "finalization_session_id_missing"),
        ("invalid\nidentifier", "finalization_session_id_invalid"),
    ],
)
def test_finalizer_rejects_invalid_host_identity_before_changing_owners(
    monkeypatch: pytest.MonkeyPatch,
    session_id: object,
    reason: str,
) -> None:
    """A host contract failure cannot silently leave an unknown game owner running."""
    entry = load_entry()
    registration = sys.modules[f"{PLUGIN_MODULE}.toqraq.hermes.registration"]
    finalized: list[str] = []
    cleared: list[str] = []

    class Container:
        class Sessions:
            async def finalize(self, owner_id: str) -> None:
                finalized.append(owner_id)

        session_service = Sessions()

        class WorkspaceContexts:
            @staticmethod
            def clear(owner_id: str) -> None:
                cleared.append(owner_id)

        workspace_context_service = WorkspaceContexts()

        @staticmethod
        async def close() -> None:
            return

    monkeypatch.setattr(registration, "get_container", Container)

    class Context:
        def register_tool(self, **_kwargs: Any) -> None:
            return

        def register_hook(self, name: str, callback: Any) -> None:
            if name == "on_session_finalize":
                self.finalizer = callback

        def register_disposer(self, _disposer: Any) -> None:
            return

        def register_skill(self, _name: str, _path: Path, _description: str = "") -> None:
            return

    context = Context()
    entry.register(context)

    with pytest.raises(registration.SessionStateError) as captured:
        asyncio.run(context.finalizer(session_id=session_id))

    assert captured.value.details == {"reason": reason}
    assert finalized == []
    assert cleared == []
