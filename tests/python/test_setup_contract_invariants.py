"""Cross-field invariants for the public Setup result contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from toqraq.contracts.setup import (
    EngineChoiceResult,
    EngineSetupResult,
    HostSetupResult,
    ProjectSetupResult,
    ProjectState,
    SelectedRuntimeResult,
    SetupAction,
    SetupResult,
)

_COMPONENT_RELEASE_ID = "1" * 64


def _engine_for_setup_action(action: SetupAction) -> EngineSetupResult:
    """Build the valid engine projection required by one runtime action."""
    if action is SetupAction.SELECT_VERSION:
        return EngineSetupResult(
            id="godot",
            runtime=None,
            available_versions=("4.7.1",),
            required_component_release_ids=(),
            runtime_install_required=False,
        )
    if action in {SetupAction.INSTALL, SetupAction.START}:
        return EngineSetupResult(
            id="godot",
            runtime=SelectedRuntimeResult(version="4.7.1"),
            available_versions=(),
            required_component_release_ids=(_COMPONENT_RELEASE_ID,),
            runtime_install_required=action is SetupAction.INSTALL,
        )
    return EngineSetupResult(
        id="godot",
        runtime=None,
        available_versions=(),
        required_component_release_ids=(),
        runtime_install_required=False,
    )


def _setup_host() -> HostSetupResult:
    """Return stable host facts for contract-only setup tests."""
    return HostSetupResult(platform="windows", native_display=True)


@pytest.mark.parametrize(
    ("state", "path", "probed_engine_ids"),
    [
        (ProjectState.UNCHECKED, "D:/game", ("godot",)),
        (ProjectState.MISSING, None, ("godot",)),
        (ProjectState.INVALID, "D:/game", ("godot",)),
        (ProjectState.NOT_DETECTED, "D:/game", ()),
        (ProjectState.AMBIGUOUS, "D:/game", ("godot",)),
        (ProjectState.READY, "D:/game", ()),
        (ProjectState.READY, "D:/game", ("godot", "unity")),
    ],
)
def test_project_setup_rejects_state_incoherent_probe_evidence(
    state: ProjectState,
    path: str | None,
    probed_engine_ids: tuple[str, ...],
) -> None:
    with pytest.raises(ValidationError, match="probe"):
        ProjectSetupResult(
            path=path,
            state=state,
            viewport_size=None,
            probed_engine_ids=probed_engine_ids,
        )


def test_engine_choices_require_the_exact_ordered_probe_evidence() -> None:
    project = ProjectSetupResult(
        path="D:/game",
        state=ProjectState.AMBIGUOUS,
        viewport_size=None,
        probed_engine_ids=("godot", "unity"),
    )
    matching_choices = (
        EngineChoiceResult(id="godot", declared_version=None, confidence=90),
        EngineChoiceResult(id="unity", declared_version=None, confidence=80),
    )

    valid = SetupResult(
        host=_setup_host(),
        engine=None,
        project=project,
        engine_choices=matching_choices,
        action=SetupAction.SELECT_ENGINE,
    )

    assert tuple(choice.id for choice in valid.engine_choices) == project.probed_engine_ids
    with pytest.raises(ValidationError, match="match probed engines in order"):
        SetupResult(
            host=_setup_host(),
            engine=None,
            project=project,
            engine_choices=tuple(reversed(matching_choices)),
            action=SetupAction.SELECT_ENGINE,
        )


@pytest.mark.parametrize(
    "action",
    [
        SetupAction.RUNTIME_UNAVAILABLE,
        SetupAction.SELECT_VERSION,
        SetupAction.INSTALL,
        SetupAction.START,
        SetupAction.UNSUPPORTED_HOST,
    ],
)
def test_runtime_actions_require_the_selected_engine_as_the_only_probe(
    action: SetupAction,
) -> None:
    matching = ProjectSetupResult(
        path="D:/game",
        state=ProjectState.READY,
        viewport_size=None,
        probed_engine_ids=("godot",),
    )
    mismatched = ProjectSetupResult(
        path="D:/game",
        state=ProjectState.READY,
        viewport_size=None,
        probed_engine_ids=("unity",),
    )
    engine = _engine_for_setup_action(action)

    assert (
        SetupResult(
            host=_setup_host(),
            engine=engine,
            project=matching,
            engine_choices=(),
            action=action,
        ).action
        is action
    )
    with pytest.raises(ValidationError, match="must match the probed project engine"):
        SetupResult(
            host=_setup_host(),
            engine=engine,
            project=mismatched,
            engine_choices=(),
            action=action,
        )


@pytest.mark.parametrize(
    "engine",
    [
        EngineSetupResult(
            id="godot",
            runtime=SelectedRuntimeResult(version="4.7.1"),
            available_versions=(),
            required_component_release_ids=(_COMPONENT_RELEASE_ID,),
            runtime_install_required=False,
        ),
        EngineSetupResult(
            id="godot",
            runtime=SelectedRuntimeResult(version="4.7.1"),
            available_versions=(),
            required_component_release_ids=(_COMPONENT_RELEASE_ID,),
            runtime_install_required=True,
        ),
        EngineSetupResult(
            id="godot",
            runtime=None,
            available_versions=("4.7.1",),
            required_component_release_ids=(),
            runtime_install_required=False,
        ),
    ],
)
def test_unsupported_host_cannot_offer_runtime_preparation(
    engine: EngineSetupResult,
) -> None:
    with pytest.raises(ValidationError, match="cannot offer preparation"):
        SetupResult(
            host=_setup_host(),
            engine=engine,
            project=ProjectSetupResult(
                path="D:/game",
                state=ProjectState.READY,
                viewport_size=None,
                probed_engine_ids=("godot",),
            ),
            engine_choices=(),
            action=SetupAction.UNSUPPORTED_HOST,
        )
