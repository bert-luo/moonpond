"""Unit tests asserting GENERATOR_SYSTEM_PROMPT content after Phase 08 rewrite."""

from __future__ import annotations

from backend.pipelines.agentic.file_generator import (
    GENERATOR_SYSTEM_PROMPT,
    build_generator_system_prompt,
)
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


# ---------------------------------------------------------------------------
# 3D prompt tests
# ---------------------------------------------------------------------------


def test_3d_prompt_contains_3d_node_types():
    prompt = build_generator_system_prompt("3D")
    assert "CharacterBody3D" in prompt
    assert "Camera3D" in prompt
    assert "MeshInstance3D" in prompt
    assert "Node3D" in prompt


def test_3d_prompt_contains_camera_requirement():
    prompt = build_generator_system_prompt("3D")
    assert "Camera3D" in prompt
    assert "MUST include" in prompt or "must include" in prompt.lower()


def test_3d_prompt_contains_lighting_requirement():
    prompt = build_generator_system_prompt("3D")
    assert "DirectionalLight3D" in prompt or "OmniLight3D" in prompt
    assert "lighting" in prompt.lower()


def test_3d_prompt_contains_vector3_guidance():
    prompt = build_generator_system_prompt("3D")
    assert "Vector3" in prompt
    assert "NOT Vector2" in prompt


def test_3d_prompt_contains_mesh_types():
    prompt = build_generator_system_prompt("3D")
    assert "BoxMesh" in prompt
    assert "SphereMesh" in prompt


def test_3d_prompt_stretch_mode_disabled():
    prompt = build_generator_system_prompt("3D")
    assert 'mode="disabled"' in prompt
    assert 'mode="canvas_items"' not in prompt


def test_3d_prompt_root_node3d():
    prompt = build_generator_system_prompt("3D")
    assert "root Node3D" in prompt
    assert "root Node2D" not in prompt


def test_3d_prompt_no_control_snippets_as_usable():
    prompt = build_generator_system_prompt("3D")
    # Control snippets should be marked as 2D only / not applicable
    assert "2D only" in prompt or "not applicable" in prompt
    # Should NOT list individual control snippet paths as usable assets
    first_snippet = next(iter(CONTROL_SNIPPET_PATHS.values()))
    assert first_snippet not in prompt


def test_3d_prompt_shader_annotation():
    prompt = build_generator_system_prompt("3D")
    # Shaders annotated as not for 3D mesh materials
    assert "NOT to 3D mesh materials" in prompt


def test_3d_prompt_particle_annotation():
    prompt = build_generator_system_prompt("3D")
    assert "GPUParticles3D" in prompt


def test_2d_prompt_particle_annotation():
    assert "GPUParticles2D" in GENERATOR_SYSTEM_PROMPT


def test_2d_prompt_unchanged():
    """build_generator_system_prompt('2D') matches the module-level constant."""
    assert build_generator_system_prompt("2D") == GENERATOR_SYSTEM_PROMPT
