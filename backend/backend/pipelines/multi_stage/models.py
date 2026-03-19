"""Pydantic models for multi-stage pipeline inputs and outputs."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ControlScheme(str, Enum):
    """Supported control schemes for generated games."""

    WASD = "wasd"
    MOUSE_FOLLOW = "mouse_follow"
    CLICK_TO_MOVE = "click_to_move"
    DRAG = "drag"
    POINT_AND_SHOOT = "point_and_shoot"


class ControlMapping(BaseModel):
    """Maps a human-readable key label to a game action description."""

    key: str
    action: str


class SceneSpec(BaseModel):
    """Specification for a single game scene."""

    name: str
    description: str
    nodes: list[str]


class VisualStyle(BaseModel):
    """Visual style selection for the game."""

    palette: str
    shader: str
    mood: str


class GameSpec(BaseModel):
    """Output of the Prompt Enhancer stage — enriched game specification."""

    title: str
    genre: str
    mechanics: list[str]
    visual_hints: list[str]


class GameDesign(BaseModel):
    """Output of the Game Designer stage — full game design document."""

    title: str
    genre: str
    scenes: list[SceneSpec]
    visual_style: VisualStyle
    mechanics: list[str]
    control_scheme: ControlScheme
    controls: list[ControlMapping]
    win_condition: str
    fail_condition: str
