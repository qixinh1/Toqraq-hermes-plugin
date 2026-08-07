"""Shared configuration for immutable public contract models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Exact immutable model used at every public plugin boundary."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
        populate_by_name=True,
    )


class EmptyRequest(ContractModel):
    """Arguments for a command that intentionally accepts no fields."""


def freeze_sequence(value: object) -> object:
    """Convert an external JSON array to an immutable model sequence."""
    if isinstance(value, list):
        return tuple(value)
    return value
