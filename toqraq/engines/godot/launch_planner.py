"""Pure launch planning for one exact managed Godot runtime."""

from __future__ import annotations

from ...core.bridge import BridgeListenerEndpoint
from ...core.engine_contribution import GameLaunchPlanner, ProjectDescription
from ...core.process_tree import (
    ProcessBootstrap,
    ProcessEnvironment,
    ProcessEnvironmentVariable,
    ProcessLaunch,
)
from ...core.runtime import PreparedRuntime
from .identity import GODOT_EDITOR_ENTRY_POINT, GODOT_ENGINE_ID

GODOT_BRIDGE_URL_ENVIRONMENT = "TOQRAQ_BRIDGE_URL"
GODOT_PROJECT_ARGUMENT = "--path"


class GodotGameLaunchPlanner(GameLaunchPlanner):
    """Translate validated Godot launch facts without acquiring resources."""

    @property
    def engine_id(self) -> str:
        """Return the contribution engine identifier."""
        return GODOT_ENGINE_ID

    def plan(
        self,
        project: ProjectDescription,
        runtime: PreparedRuntime,
        endpoint: BridgeListenerEndpoint,
        environment: ProcessEnvironment,
        bootstrap: ProcessBootstrap,
    ) -> ProcessLaunch:
        """Return the sole Godot command accepted by the platform launcher."""
        _require_godot_launch(project, runtime)
        if not isinstance(endpoint, BridgeListenerEndpoint):
            raise ValueError("Godot bridge endpoint is invalid")
        if not isinstance(environment, ProcessEnvironment):
            raise ValueError("Godot launch environment is invalid")
        if not isinstance(bootstrap, ProcessBootstrap):
            raise ValueError("Godot launch bootstrap is invalid")

        child_environment = ProcessEnvironment(
            variables=(
                *environment.variables,
                ProcessEnvironmentVariable(
                    name=GODOT_BRIDGE_URL_ENVIRONMENT,
                    value=endpoint.url,
                ),
            )
        )
        return ProcessLaunch(
            executable=runtime.entry_point(GODOT_EDITOR_ENTRY_POINT),
            arguments=(GODOT_PROJECT_ARGUMENT, str(project.project_root)),
            working_directory=project.project_root,
            environment=child_environment,
            bootstrap=bootstrap,
        )


def _require_godot_launch(
    project: ProjectDescription,
    runtime: PreparedRuntime,
) -> None:
    """Reject cross-engine values before constructing an executable command."""
    if not isinstance(project, ProjectDescription) or project.engine_id != GODOT_ENGINE_ID:
        raise ValueError("Godot project description is invalid")
    if (
        not isinstance(runtime, PreparedRuntime)
        or runtime.release.identity.engine_id != GODOT_ENGINE_ID
    ):
        raise ValueError("Godot prepared runtime is invalid")
