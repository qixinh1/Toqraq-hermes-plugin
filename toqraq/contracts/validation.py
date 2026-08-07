"""Shared reduction of framework validation issues to one safe failure."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ..core.errors import InvalidRequestError

_MAX_VALIDATION_ISSUES = 16
_MAX_LOCATION_LENGTH = 128
_MAX_VALIDATION_TYPE_LENGTH = 64


def invalid_request(issues: Sequence[Mapping[str, object]]) -> InvalidRequestError:
    """Reduce Pydantic or FastAPI issues to the identical safe error shape."""
    public_issues: list[dict[str, str]] = []
    for issue in issues[:_MAX_VALIDATION_ISSUES]:
        location = _location(issue.get("loc"))
        issue_type = issue.get("type")
        public_issues.append(
            {
                "location": location[:_MAX_LOCATION_LENGTH],
                "type": (
                    issue_type[:_MAX_VALIDATION_TYPE_LENGTH]
                    if isinstance(issue_type, str)
                    else "invalid"
                ),
            }
        )
    return InvalidRequestError(
        parameters={"issue_count": len(issues)},
        details={
            "issues": tuple(public_issues),
            "truncated": len(issues) > _MAX_VALIDATION_ISSUES,
        },
    )


def _location(value: object) -> str:
    """Normalize framework locations and remove HTTP's transport prefix."""
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ""
    parts = list(value)
    if parts and parts[0] == "body":
        parts.pop(0)
    return ".".join(_location_part(part) for part in parts)


def _location_part(value: object) -> str:
    """Convert only framework-defined location scalars."""
    if isinstance(value, str):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:d}"
    return "unknown"
