"""Contract data models for the contract-first parallel pipeline.

These models define the typed interfaces between pipeline stages:
- RichGameSpec: expanded game specification (Stage 1 output)
- NodeContract: per-node interface contract
- GameContract: full game interface contract (Stage 2 output)
"""

from __future__ import annotations

from pydantic import BaseModel


class RichGameSpec(BaseModel):
    """Output of Stage 1 (Spec Expander) — enriched game specification.

    Extends the basic GameSpec with entity-level detail, interactions,
    and scene structure information needed by downstream stages.
    """

    title: str
    genre: str
    mechanics: list[str]
    visual_hints: list[str]
    entities: list[dict]
    interactions: list[str]
    scene_structure: str
    win_condition: str
    fail_condition: str


class NodeContract(BaseModel):
    """Per-node interface contract describing a single Godot node/script.

    Each node declares its public API (methods, signals), group memberships,
    and dependencies on other nodes' scripts. Nodes with empty dependencies
    are leaf nodes that can be generated in parallel.
    """

    script_path: str
    scene_path: str | None = None
    node_type: str
    description: str
    methods: list[str] = []
    signals: list[str] = []
    groups: list[str] = []
    dependencies: list[str] = []


class GameContract(BaseModel):
    """Full game interface contract — output of Stage 2 (Contract Generator).

    Describes every node, the game manager's enums and properties,
    autoloads, control scheme, and visual style. Downstream stages
    use this contract to generate code for each node independently.
    """

    title: str
    nodes: list[NodeContract]
    game_manager_enums: dict[str, list[str]] = {}
    game_manager_properties: list[str] = []
    autoloads: list[str] = []
    main_scene: str = "Main.tscn"
    control_scheme: str
    controls: list[dict] = []
    visual_style: dict = {}
