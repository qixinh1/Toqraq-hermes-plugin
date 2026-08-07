"""Pure Godot launch-planning tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from toqraq.core.bridge import BridgeListenerEndpoint
from toqraq.core.engine_contribution import ProjectDescription
from toqraq.core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessEnvironmentVariable,
)
from toqraq.core.runtime import (
    PreparedRuntime,
    RuntimeEntryPoint,
    RuntimeEntryPointBinding,
    RuntimeIdentity,
    RuntimeRelease,
)
from toqraq.engines.godot.launch_planner import (
    GODOT_BRIDGE_URL_ENVIRONMENT,
    GODOT_PROJECT_ARGUMENT,
    GodotGameLaunchPlanner,
)

_COMPONENT_RELEASE_ID = "1" * 64
_PRIVATE_BOOTSTRAP = b'\x00{"credential":"private"}'


class _Resource:
    async def close(self) -> None:
        return None


def _project(root: Path, *, engine_id: str = "godot") -> ProjectDescription:
    return ProjectDescription(
        engine_id=engine_id,
        project_root=root,
        marker_path=root / "project.godot",
        confidence=100,
        declared_version="4.7.1-stable",
    )


def _runtime(root: Path, *, engine_id: str = "godot") -> PreparedRuntime:
    release = RuntimeRelease(
        identity=RuntimeIdentity(
            engine_id=engine_id,
            version="4.7.1-stable",
            build_id="toqraq.windows.x86_64.release",
            distribution_id="toqraq",
            platform="windows",
            architecture="x86_64",
        ),
        component_release_ids=(_COMPONENT_RELEASE_ID,),
        entry_point_bindings=(
            RuntimeEntryPointBinding(
                name="editor",
                component_release_id=_COMPONENT_RELEASE_ID,
                component_entry_point_name="editor",
            ),
        ),
        bridge_id=f"toqraq.{engine_id}.bridge",
        bridge_protocol="1.0",
    )
    return PreparedRuntime(
        release=release,
        entry_points=(RuntimeEntryPoint(name="editor", path=root / "godot.exe"),),
        owned_resources=(_Resource(),),
    )


def test_plan_preserves_exact_runtime_and_private_bootstrap(tmp_path: Path) -> None:
    project = _project(tmp_path)
    runtime = _runtime(tmp_path)
    endpoint = BridgeListenerEndpoint(port=49152)
    environment = ProcessEnvironment(
        variables=(ProcessEnvironmentVariable(name="LANG", value="en_US.UTF-8"),)
    )
    bootstrap = ProcessBootstrap(payload=_PRIVATE_BOOTSTRAP)

    launch = GodotGameLaunchPlanner().plan(
        project,
        runtime,
        endpoint,
        environment,
        bootstrap,
    )

    assert launch.executable == runtime.entry_point("editor")
    assert launch.arguments == (GODOT_PROJECT_ARGUMENT, str(tmp_path))
    assert launch.working_directory == tmp_path
    assert launch.bootstrap is bootstrap
    assert launch.environment.variables == (
        environment.variables[0],
        ProcessEnvironmentVariable(
            name=GODOT_BRIDGE_URL_ENVIRONMENT,
            value=endpoint.url,
        ),
    )


def test_plan_never_places_private_bootstrap_in_public_launch_fields(tmp_path: Path) -> None:
    bootstrap = ProcessBootstrap(payload=_PRIVATE_BOOTSTRAP)

    launch = GodotGameLaunchPlanner().plan(
        _project(tmp_path),
        _runtime(tmp_path),
        BridgeListenerEndpoint(port=49153),
        ProcessEnvironment(variables=()),
        bootstrap,
    )

    public_text = "\n".join(
        (
            str(launch.executable),
            *launch.arguments,
            *(variable.value for variable in launch.environment.variables),
        )
    ).encode()
    assert _PRIVATE_BOOTSTRAP not in public_text
    assert "--remote-debug" not in launch.arguments
    assert "--resolution" not in launch.arguments


def test_plan_rejects_cross_engine_values_and_endpoint_override(tmp_path: Path) -> None:
    planner = GodotGameLaunchPlanner()
    endpoint = BridgeListenerEndpoint(port=49154)
    environment = ProcessEnvironment(variables=())
    bootstrap = ProcessBootstrap(payload=_PRIVATE_BOOTSTRAP)

    with pytest.raises(ValueError, match="project"):
        planner.plan(
            _project(tmp_path, engine_id="unity"),
            _runtime(tmp_path),
            endpoint,
            environment,
            bootstrap,
        )
    with pytest.raises(ValueError, match="runtime"):
        planner.plan(
            _project(tmp_path),
            _runtime(tmp_path, engine_id="unity"),
            endpoint,
            environment,
            bootstrap,
        )
    with pytest.raises(ValueError, match="duplicated"):
        planner.plan(
            _project(tmp_path),
            _runtime(tmp_path),
            endpoint,
            ProcessEnvironment(
                variables=(
                    ProcessEnvironmentVariable(
                        name=GODOT_BRIDGE_URL_ENVIRONMENT,
                        value="ws://127.0.0.1:1/toqraq/bridge",
                    ),
                )
            ),
            bootstrap,
        )


def test_native_module_and_host_use_one_bridge_environment_name() -> None:
    native_launch = (
        Path(__file__).parents[2] / "engine" / "godot" / "modules" / "toqraq" / "toqraq_launch.cpp"
    ).read_text(encoding="utf-8")

    assert f'BRIDGE_ENVIRONMENT = "{GODOT_BRIDGE_URL_ENVIRONMENT}"' in native_launch
