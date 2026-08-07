"""Read-only standard Godot project-format contribution."""

from ...core.engine_contribution import EngineProjectFormat
from .identity import GODOT_ENGINE_ID
from .project_inventory import GodotProjectInventoryReader
from .project_probe import GodotProjectProbe

GODOT_PROJECT_FORMAT = EngineProjectFormat(
    engine_id=GODOT_ENGINE_ID,
    project_probe=GodotProjectProbe(),
    project_inventory_reader=GodotProjectInventoryReader(),
)
