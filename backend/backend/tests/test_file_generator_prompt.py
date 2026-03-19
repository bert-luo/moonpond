"""Unit tests asserting GENERATOR_SYSTEM_PROMPT content after Phase 08 rewrite."""

from __future__ import annotations

from backend.pipelines.agentic.file_generator import GENERATOR_SYSTEM_PROMPT
from backend.pipelines.assets import (
    CONTROL_SNIPPET_PATHS,
    PALETTE_PATHS,
    PARTICLE_PATHS,
    SHADER_PATHS,
)


# ---------------------------------------------------------------------------
# project.godot generation instructions
# ---------------------------------------------------------------------------


def test_no_prohibition():
    """Prompt must NOT contain the old 'Do NOT generate project.godot' line."""
    assert "Do NOT generate project.godot" not in GENERATOR_SYSTEM_PROMPT


def test_must_generate_project_godot():
    assert "You MUST generate project.godot" in GENERATOR_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Skeleton sections
# ---------------------------------------------------------------------------


def test_rendering_section():
    assert "[rendering]" in GENERATOR_SYSTEM_PROMPT
    assert "gl_compatibility" in GENERATOR_SYSTEM_PROMPT


def test_display_section():
    assert "[display]" in GENERATOR_SYSTEM_PROMPT
    assert "1152" in GENERATOR_SYSTEM_PROMPT
    assert "648" in GENERATOR_SYSTEM_PROMPT


def test_autoload_example():
    assert "[autoload]" in GENERATOR_SYSTEM_PROMPT


def test_input_simplified_format():
    assert "[input]" in GENERATOR_SYSTEM_PROMPT
    # Should show at least one simplified example
    assert "move_left=arrow_left" in GENERATOR_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Asset paths surfaced from assets.py
# ---------------------------------------------------------------------------


def test_contains_shader_path():
    first_shader = next(iter(SHADER_PATHS.values()))
    assert first_shader in GENERATOR_SYSTEM_PROMPT


def test_contains_palette_path():
    first_palette = next(iter(PALETTE_PATHS.values()))
    assert first_palette in GENERATOR_SYSTEM_PROMPT


def test_contains_particle_path():
    first_particle = next(iter(PARTICLE_PATHS.values()))
    assert first_particle in GENERATOR_SYSTEM_PROMPT


def test_contains_control_snippet_path():
    first_snippet = next(iter(CONTROL_SNIPPET_PATHS.values()))
    assert first_snippet in GENERATOR_SYSTEM_PROMPT
