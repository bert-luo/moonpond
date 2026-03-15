"""Pydantic models for pipeline stage inputs and outputs."""

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


# ---------------------------------------------------------------------------
# Template asset path constants (shared across stages)
# ---------------------------------------------------------------------------

INPUT_ACTIONS = [
    "move_left",
    "move_right",
    "move_up",
    "move_down",
    "jump",
    "shoot",
    "interact",
    "pause",
]

SHADER_PATHS = {
    "pixel_art": "res://assets/shaders/pixel_art.gdshader",
    "glow": "res://assets/shaders/glow.gdshader",
    "scanlines": "res://assets/shaders/scanlines.gdshader",
    "chromatic_aberration": "res://assets/shaders/chromatic_aberration.gdshader",
    "screen_distortion": "res://assets/shaders/screen_distortion.gdshader",
}

PALETTE_PATHS = {
    "neon": "res://assets/palettes/neon.tres",
    "retro": "res://assets/palettes/retro.tres",
    "pastel": "res://assets/palettes/pastel.tres",
    "monochrome": "res://assets/palettes/monochrome.tres",
}

PARTICLE_PATHS = {
    "explosion": "res://assets/particles/explosion.tscn",
    "dust": "res://assets/particles/dust.tscn",
    "sparkle": "res://assets/particles/sparkle.tscn",
    "trail": "res://assets/particles/trail.tscn",
}

CONTROL_SNIPPET_PATHS = {
    "mouse_follow": "res://assets/control_snippets/mouse_follow.gd",
    "click_to_move": "res://assets/control_snippets/click_to_move.gd",
    "drag": "res://assets/control_snippets/drag.gd",
    "point_and_shoot": "res://assets/control_snippets/point_and_shoot.gd",
}
