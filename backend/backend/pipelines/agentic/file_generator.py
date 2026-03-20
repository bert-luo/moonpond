"""File Generator — tool definitions, dispatch, and multi-turn generation loop.

Defines the write_file and read_file tools that the LLM agent calls via
the Anthropic tool_use API, the dispatch function that executes them, and
the run_file_generation loop that drives the multi-turn conversation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from anthropic import AsyncAnthropic

from backend.pipelines.agentic.models import AgenticGameSpec
from backend.pipelines.assets import (
    CONTROL_SNIPPET_PATHS,
    PALETTE_PATHS,
    PARTICLE_PATHS,
    SHADER_PATHS,
)
from backend.pipelines.base import EmitFn, ProgressEvent

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool_use API format)
# ---------------------------------------------------------------------------

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": (
        "Write a complete file to the game project. "
        "Call this exactly once per turn with one complete file. "
        "filename must be a bare filename (e.g. 'player.gd', 'Main.tscn') "
        "with no directory prefix."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Filename only, no path. E.g. 'player.gd' or 'Main.tscn'.",
            },
            "content": {
                "type": "string",
                "description": "Complete file content as a string.",
            },
        },
        "required": ["filename", "content"],
    },
}

READ_FILE_TOOL = {
    "name": "read_file",
    "description": (
        "Read the current content of a file already written to the game project. "
        "Use this to inspect previously written files before "
        "generating a file that depends on them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Filename to read (bare filename, no path).",
            },
        },
        "required": ["filename"],
    },
}

AGENT_TOOLS = [WRITE_FILE_TOOL, READ_FILE_TOOL]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENERATOR_MODEL = "claude-sonnet-4-6"
MAX_TURNS_PER_ITERATION = 30

# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


async def _dispatch_tool(
    tool_name: str,
    tool_input: dict,
    game_dir: Path,
    generated_files: dict[str, str],
) -> str:
    """Execute a tool call and return the result string for tool_result.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Input dict from the LLM tool call.
        game_dir: Path to the game project directory.
        generated_files: Mutable dict tracking filename -> content for all
            files written during this generation iteration.

    Returns:
        A string result to send back as tool_result content.
    """
    if tool_name == "write_file":
        filename = tool_input["filename"]
        content = tool_input["content"]
        try:
            (game_dir / filename).write_text(content)
            generated_files[filename] = content
            return f"OK: wrote {filename} ({len(content)} chars)"
        except Exception as e:
            logger.error("write_file failed for %s: %s", filename, e)
            return f"ERROR: {e}"

    elif tool_name == "read_file":
        filename = tool_input["filename"]
        if filename in generated_files:
            return generated_files[filename]
        path = game_dir / filename
        if path.exists():
            return path.read_text()
        return f"ERROR: file not found: {filename}"

    else:
        return f"ERROR: unknown tool {tool_name}"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------


def _build_asset_section(perspective: str = "2D") -> str:
    """Build the available-assets block from imported constants.

    Args:
        perspective: "2D" or "3D". Controls shader annotation and
            control snippet inclusion.
    """
    lines = ["AVAILABLE ASSETS (use these instead of generating placeholders):"]

    if perspective == "3D":
        lines.append(
            "Shaders (apply to CanvasLayer or UI elements — NOT to 3D mesh materials):"
        )
    else:
        lines.append("Shaders (apply via ShaderMaterial):")
    for name, path in SHADER_PATHS.items():
        lines.append(f"  {name}: {path}")

    lines.append("")
    lines.append(
        "Palettes (Gradient resources, sample via GameManager.get_palette_color(t)):"
    )
    for name, path in PALETTE_PATHS.items():
        lines.append(f"  {name}: {path}")

    lines.append("")
    lines.append("Particles (preload and instance):")
    for name, path in PARTICLE_PATHS.items():
        lines.append(f"  {name}: {path}")

    if perspective == "2D":
        lines.append("")
        lines.append("Control snippets (attach as script to any Node2D):")
        for name, path in CONTROL_SNIPPET_PATHS.items():
            lines.append(f"  {name}: {path}")
    else:
        lines.append("")
        lines.append("Control snippets (2D only, not applicable to 3D games):")

    return "\n".join(lines)


def build_generator_system_prompt(perspective: str = "2D") -> str:
    """Build the file-generator system prompt, branching on perspective.

    Args:
        perspective: "2D" or "3D".

    Returns:
        The full system prompt string for the file-generation agent.
    """
    dim = perspective  # "2D" or "3D"

    # Mission statement
    mission = (
        f"You are an expert Godot 4 game developer. Your job is to generate all files "
        f"for a complete, playable {dim} game project one at a time by calling write_file."
    )

    # Entity node types
    if perspective == "3D":
        entity_types = "(Node3D, CharacterBody3D, Area3D, MeshInstance3D, Camera3D, DirectionalLight3D, etc.)"
    else:
        entity_types = "(Node2D, CharacterBody2D, Area2D, etc.)"

    # Main scene root
    if perspective == "3D":
        root_node = "The main scene is always Main.tscn with a root Node3D."
    else:
        root_node = "The main scene is always Main.tscn with a root Node2D."

    # Display config
    if perspective == "3D":
        display_section = (
            "[display]\n"
            "window/size/viewport_width=1152\n"
            "window/size/viewport_height=648\n"
            'window/stretch/mode="disabled"'
        )
    else:
        display_section = (
            "[display]\n"
            "window/size/viewport_width=1152\n"
            "window/size/viewport_height=648\n"
            'window/stretch/mode="canvas_items"\n'
            'window/stretch/aspect="expand"'
        )

    # 3D essentials (only for 3D)
    essentials_3d = ""
    if perspective == "3D":
        essentials_3d = """
3D ESSENTIALS — every 3D game MUST include:
- A Camera3D node in the main scene (without one, the screen is blank)
- At least one light source (DirectionalLight3D or OmniLight3D) — without lighting, everything renders black
- Use Vector3 for all positions and velocities (NOT Vector2)
- Use move_and_slide() on CharacterBody3D the same way as 2D, but with 3D vectors
- For simple visuals without imported models, use MeshInstance3D with built-in meshes:
  BoxMesh, SphereMesh, CapsuleMesh, CylinderMesh, PlaneMesh, QuadMesh
  Example: var mesh_instance = MeshInstance3D.new(); mesh_instance.mesh = BoxMesh.new()
- Set up a WorldEnvironment node with an Environment resource for ambient light and sky

"""

    prompt = (
        f"""\
{mission}

TARGET ENGINE: Godot 4.5.1. You MUST generate code compatible with Godot 4.5.

CRITICAL — Variant type issues: In Godot 4.5, functions like lerp(), ceil(), \
floor(), clamp(), randf(), randf_range(), randi_range(), abs(), min(), max(), \
snapped(), load(), preload(), get_node(), and any custom method without an \
explicit return type annotation ALL return Variant.

Two patterns cause PARSE ERRORS:
  var x := lerp(a, b, t)        # `:=` with Variant — PARSE ERROR
  var x: float = lerp(a, b, t)  # explicit type annotation with Variant — PARSE ERROR

Use UNTYPED `var` for any Variant-returning function:
  var x = lerp(a, b, t)              # untyped — CORRECT
  var scene = load(...)               # untyped — CORRECT
Or use the typed variants where available:
  var x = lerpf(a, b, t)             # returns float — CORRECT
  var x = clampf(val, lo, hi)        # returns float — CORRECT
  var x = floorf(val)                 # returns float — CORRECT

CRITICAL — Dynamic node spawning: When instantiating nodes at runtime, ALWAYS \
set global_position BEFORE calling add_child(). Godot's _ready() fires during \
add_child(), so any position-dependent logic in _ready() will see the default \
(0,0) position if you set position after add_child().
  CORRECT:
    var e = enemy_scene.instantiate()
    e.global_position = spawn_pos        # position FIRST
    get_tree().current_scene.add_child(e) # then add to tree
  WRONG:
    var e = enemy_scene.instantiate()
    get_tree().current_scene.add_child(e) # _ready() fires with pos=(0,0)
    e.global_position = spawn_pos         # too late — _ready() already ran

IMPORTANT RULES:
- Generate files in this order: main .gd scripts first, then scene files (.tscn), then auxiliary files.
- You MUST generate project.godot as one of your files. Do NOT generate export_presets.cfg or .import files.
- Use Godot 4 GDScript syntax: @onready, @export, signal declarations with "signal name", \
typed variables with "var x: Type", super() instead of .func(), etc.
- For .tscn files, use Godot 4 text scene format with [gd_scene], [ext_resource], \
[sub_resource], and [node] sections. Use type="Script" for GDScript ext_resources.
- Each write_file call should contain a COMPLETE file — never partial content.
- Use read_file to inspect previously written files when generating dependent files.
- When all files are complete, spec is satisfied, and the game is ready to play, STOP calling tools. \
Simply respond with a text summary of what you built.
- All entity scripts should extend appropriate Godot node types {entity_types}.
- Connect signals in _ready() using connect() — do NOT rely on editor signal connections.
- {root_node}
- You MUST generate every script file that you register as an autoload in project.godot.
- Do NOT generate audio, sound effects, or music. No AudioStreamPlayer, AudioStreamWAV, \
AudioStreamGenerator, or AudioManager. The pipeline has no audio asset support — audio \
code wastes tokens and may cause runtime errors.

PROJECT.GODOT — when generating project.godot, ALWAYS include these sections verbatim:

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"

{display_section}

For [autoload], list every singleton script you generate, e.g.:
[autoload]
GameManager="*res://game_manager.gd"

For [input], use simplified format — one action per line:
[input]
move_left=arrow_left
move_right=arrow_right
jump=space
shoot=z
(Supported keys: arrow_left, arrow_right, arrow_up, arrow_down, \
space, enter, escape, shift, ctrl, tab, backspace, a-z, 0-9, f1-f12)

"""
        + essentials_3d
        + _build_asset_section(perspective)
        + "\n"
    )
    return prompt


# Backward-compatible module-level constant (equals 2D prompt)
GENERATOR_SYSTEM_PROMPT = build_generator_system_prompt("2D")


# ---------------------------------------------------------------------------
# Multi-turn file generation loop
# ---------------------------------------------------------------------------


def _build_initial_prompt(spec: AgenticGameSpec) -> str:
    """Build the initial user message from the game spec."""
    spec_json = json.dumps(spec.model_dump(), indent=2)
    return (
        f"Generate all files for this Godot 4 game project.\n\n"
        f"Game Specification:\n{spec_json}\n\n"
        f"Start generating files now. Call write_file for each file, "
        f"one at a time. Begin with the main gameplay scripts, then "
        f"scene files (.tscn), then any auxiliary files."
    )


def _build_stateless_prompt(
    spec: AgenticGameSpec, existing_files: dict[str, str]
) -> str:
    """Build a fresh prompt listing spec and existing file names.

    In stateless mode, each turn starts fresh. The prompt includes the spec
    and existing file names (not contents — agent uses read_file for that).
    """
    spec_json = json.dumps(spec.model_dump(), indent=2)
    file_list = (
        "\n".join(f"  - {f}" for f in existing_files)
        if existing_files
        else "  (none yet)"
    )
    return (
        f"You are generating files for a Godot 4 game project.\n\n"
        f"Game Specification:\n{spec_json}\n\n"
        f"Files already generated:\n{file_list}\n\n"
        f"Continue generating the next file. Use read_file to inspect "
        f"any existing file if needed. Call write_file with the next file. "
        f"If all files are complete, respond with a text summary."
    )


async def run_file_generation(
    client: AsyncAnthropic,
    spec: AgenticGameSpec,
    game_dir: Path,
    emit: EmitFn,
    *,
    context_strategy: str = "full_history",
    fix_context: str | None = None,
    existing_files: dict[str, str] | None = None,
) -> tuple[dict[str, str], list[dict]]:
    """Run the multi-turn file generation agent loop.

    The LLM calls write_file/read_file tools to build up the game project
    iteratively. The loop continues until the LLM stops calling tools
    (end_turn) or MAX_TURNS_PER_ITERATION is reached.

    Args:
        client: Anthropic async client.
        spec: The game specification to implement.
        game_dir: Path to the game project directory.
        emit: Async callback for progress events.
        context_strategy: "full_history" accumulates messages,
            "stateless" resets each turn with a fresh prompt.
        existing_files: Pre-seed generated_files with files from prior
            iterations so read_file can access them during fix iterations.

    Returns:
        Tuple of (generated_files dict, conversation messages list).
    """
    generated_files: dict[str, str] = dict(existing_files) if existing_files else {}

    # Build initial messages — use fix_context if provided (targeted fix iteration)
    if fix_context is not None:
        initial_content = fix_context
    else:
        initial_content = _build_initial_prompt(spec)
    messages: list[dict] = [{"role": "user", "content": initial_content}]

    for turn in range(MAX_TURNS_PER_ITERATION):
        # In stateless mode, reset messages each turn (after first)
        if context_strategy == "stateless" and turn > 0:
            messages = [
                {
                    "role": "user",
                    "content": _build_stateless_prompt(spec, generated_files),
                }
            ]

        response = await client.messages.create(
            model=GENERATOR_MODEL,
            max_tokens=8192,
            system=build_generator_system_prompt(spec.perspective),
            tools=AGENT_TOOLS,
            messages=messages,
        )

        # Append assistant turn with full content list
        messages.append({"role": "assistant", "content": response.content})

        # Exit on end_turn
        if response.stop_reason == "end_turn":
            break

        # Process tool_use blocks
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result_str = await _dispatch_tool(
                    block.name, block.input, game_dir, generated_files
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )
                # Emit progress for write_file calls
                if block.name == "write_file":
                    filename = block.input.get("filename", "unknown")
                    await emit(
                        ProgressEvent(
                            type="file_generated",
                            message=f"Generated {filename}",
                            data={"filename": filename},
                        )
                    )

        # Defensive: no tool results means nothing to continue with
        if not tool_results:
            break

        # Append user turn with tool results
        messages.append({"role": "user", "content": tool_results})

    return generated_files, messages
