"""Pure launch bootstrap identity for one engine-bridge run."""

from __future__ import annotations

from dataclasses import dataclass, field

from .bridge import (
    validate_bridge_credential,
    validate_bridge_run_revision,
    validate_bridge_session_id,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BridgeLaunchBootstrap:
    """Secret and owner identity delivered once through process standard input."""

    credential: str = field(repr=False)
    session_id: str
    run_revision: int

    def __post_init__(self) -> None:
        """Apply the exact validators shared with bridge authentication."""
        validate_bridge_credential(self.credential)
        validate_bridge_session_id(self.session_id)
        validate_bridge_run_revision(self.run_revision)
