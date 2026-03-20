"""Template asset path constants shared across pipelines."""

from __future__ import annotations

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

PARTICLE_PATHS_2D = {
    "explosion": "res://assets/particles/explosion.tscn",
    "dust": "res://assets/particles/dust.tscn",
    "sparkle": "res://assets/particles/sparkle.tscn",
    "trail": "res://assets/particles/trail.tscn",
}

PARTICLE_PATHS_3D = {
    "explosion": "res://assets/particles/explosion.tscn",
    "dust": "res://assets/particles/dust.tscn",
    "sparkle": "res://assets/particles/sparkle.tscn",
    "trail": "res://assets/particles/trail.tscn",
}

# Backward-compatible alias (defaults to 2D)
PARTICLE_PATHS = PARTICLE_PATHS_2D

CONTROL_SNIPPET_PATHS = {
    "mouse_follow": "res://assets/control_snippets/mouse_follow.gd",
    "click_to_move": "res://assets/control_snippets/click_to_move.gd",
    "drag": "res://assets/control_snippets/drag.gd",
    "point_and_shoot": "res://assets/control_snippets/point_and_shoot.gd",
}
