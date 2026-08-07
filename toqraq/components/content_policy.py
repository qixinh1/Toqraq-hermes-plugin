"""Engine-independent safety bounds for managed component trees."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComponentContentPolicy:
    """Trusted traversal, namespace, and byte limits for component content."""

    max_entries: int
    max_file_bytes: int
    max_total_bytes: int
    max_path_depth: int
    max_path_characters: int
    read_chunk_bytes: int

    def __post_init__(self) -> None:
        """Reject unusable content limits at composition time."""
        values = (
            self.max_entries,
            self.max_file_bytes,
            self.max_total_bytes,
            self.max_path_depth,
            self.max_path_characters,
            self.read_chunk_bytes,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values
        ):
            raise ValueError("component content limits must be positive integers")
        if self.max_file_bytes > self.max_total_bytes:
            raise ValueError("component file limit must not exceed the tree limit")
