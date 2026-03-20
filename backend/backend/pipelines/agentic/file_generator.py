"""File Generator — tool definitions, dispatch, and multi-turn generation loop.

Defines the write_file and read_file tools that the LLM agent calls via
the Anthropic tool_use API, the dispatch function that executes them, and
the run_file_generation loop that drives the multi-turn conversation.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from anthropic import AsyncAnthropic

from backend.pipelines.agentic.models import AgenticGameSpec
from backend.pipelines.agentic.tripo_client import TripoAssetGenerator, TripoError
from backend.pipelines.assets import (
    CONTROL_SNIPPET_PATHS,
    PALETTE_PATHS,
    PARTICLE_PATHS_2D,
    PARTICLE_PATHS_3D,
    SHADER_PATHS,
)
from backend.pipelines.base import EmitFn, ProgressEvent, SoftTimeout

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

GENERATE_3D_ASSET_TOOL = {
    "name": "generate_3d_asset",
    "description": (
        "Generate a 3D model asset from a text description using AI. "
        "Returns the res:// path of the generated .glb file in assets/models/. "
        "Use ONLY for key visual elements (player character, enemies, vehicles, "
        "collectibles, weapons) — NOT for simple geometry like floors, walls, or "
        "platforms which should use built-in meshes (BoxMesh, SphereMesh, etc.). "
        "Maximum 5 assets per game. Each call takes ~30-60 seconds."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_name": {
                "type": "string",
                "description": (
                    "Short snake_case name for the asset file, e.g. "
                    "'space_ship', 'treasure_chest', 'dragon'."
                ),
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Detailed description of the 3D model to generate. "
                    "Be specific about shape, style, color, and size. "
                    "E.g. 'A low-poly cartoon wooden treasure chest with "
                    "gold trim and a rounded lid, game-ready style'."
                ),
            },
        },
        "required": ["asset_name", "prompt"],
    },
}

AGENT_TOOLS_BASE = [WRITE_FILE_TOOL, READ_FILE_TOOL]
AGENT_TOOLS = AGENT_TOOLS_BASE  # default (2D or no API key)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENERATOR_MODEL = "claude-sonnet-4-6"
MAX_TURNS_PER_ITERATION = 30
MAX_3D_ASSETS = 5

# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


async def _dispatch_tool(
    tool_name: str,
    tool_input: dict,
    game_dir: Path,
    generated_files: dict[str, str],
    *,
    tripo: TripoAssetGenerator | None = None,
    asset_counter: list[int] | None = None,
) -> str:
    """Execute a tool call and return the result string for tool_result.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Input dict from the LLM tool call.
        game_dir: Path to the game project directory.
        generated_files: Mutable dict tracking filename -> content for all
            files written during this generation iteration.
        tripo: Optional Tripo client for 3D asset generation.
        asset_counter: Mutable single-element list tracking assets generated.

    Returns:
        A string result to send back as tool_result content.
    """
    if tool_name == "write_file":
        filename = tool_input.get("filename")
        content = tool_input.get("content")
        if not filename or content is None:
            return "ERROR: write_file requires 'filename' and 'content' parameters"
        try:
            (game_dir / filename).write_text(content)
            generated_files[filename] = content
            return f"OK: wrote {filename} ({len(content)} chars)"
        except Exception as e:
            logger.error("write_file failed for %s: %s", filename, e)
            return f"ERROR: {e}"

    elif tool_name == "read_file":
        filename = tool_input.get("filename", "")
        if not filename:
            return "ERROR: read_file requires a 'filename' parameter"
        if filename in generated_files:
            return generated_files[filename]
        path = game_dir / filename
        if path.exists():
            return path.read_text()
        return f"ERROR: file not found: {filename}"

    elif tool_name == "generate_3d_asset":
        if tripo is None:
            return "ERROR: 3D asset generation not available (no API key configured)"

        counter = asset_counter or [0]
        if counter[0] >= MAX_3D_ASSETS:
            return (
                f"ERROR: asset budget exhausted ({MAX_3D_ASSETS}/{MAX_3D_ASSETS} used). "
                "Use built-in meshes (BoxMesh, SphereMesh, etc.) for remaining objects."
            )

        asset_name = tool_input.get("asset_name", "")
        prompt = tool_input.get("prompt", "")
        if not asset_name or not prompt:
            return "ERROR: generate_3d_asset requires 'asset_name' and 'prompt' parameters"
        dest = game_dir / "assets" / "models" / f"{asset_name}.glb"

        try:
            await tripo.generate_3d_asset(prompt=prompt, dest=dest)
            counter[0] += 1
            remaining = MAX_3D_ASSETS - counter[0]
            res_path = f"res://assets/models/{asset_name}.glb"
            return (
                f"OK: generated {res_path} ({dest.stat().st_size} bytes). "
                f"{remaining} asset(s) remaining.\n"
                f"Load in GDScript:\n"
                f'  var scene = load("{res_path}").instantiate()\n'
                f"  scene.scale = Vector3(1, 1, 1)  # adjust as needed\n"
                f"  add_child(scene)"
            )
        except TripoError as e:
            logger.error("generate_3d_asset failed for %s: %s", asset_name, e)
            return (
                f"ERROR: 3D generation failed for '{asset_name}': {e}. "
                "Fall back to built-in meshes (BoxMesh, SphereMesh, etc.)."
            )
        except Exception as e:
            logger.error("generate_3d_asset unexpected error for %s: %s", asset_name, e)
            return (
                f"ERROR: unexpected failure generating '{asset_name}': {e}. "
                "Fall back to built-in meshes."
            )

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
    if perspective == "3D":
        particle_paths = PARTICLE_PATHS_3D
        lines.append("Particles (GPUParticles3D — preload and instance in 3D scenes):")
    else:
        particle_paths = PARTICLE_PATHS_2D
        lines.append("Particles (GPUParticles2D — preload and instance):")
    for name, path in particle_paths.items():
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

3D ASSET GENERATION (generate_3d_asset tool):
You have access to an AI 3D model generator. You SHOULD use it to make the game visually
appealing — games with real 3D models for key objects look dramatically better than games
using only primitive meshes. Plan to use 3-5 assets per game for the most important entities.
- Use for key game elements: player character, enemies, collectibles, vehicles, weapons
- Do NOT waste assets on simple geometry (floors, walls, platforms) — use built-in meshes for those
- Maximum 5 assets per game — budget them for the most visually important elements
- Each asset is a .glb placed in res://assets/models/
- Load and use in GDScript:
    var scene = load("res://assets/models/asset_name.glb").instantiate()
    scene.scale = Vector3(1, 1, 1)  # adjust scale as needed
    add_child(scene)
- The loaded scene is a full Node3D subtree — position, scale, and rotate it as needed
- Generation takes ~30-60 seconds per asset — generate GDScript files first, call generate_3d_asset
  for key assets, then generate .tscn scene files that reference the assets
- If generation fails, the tool returns an error — fall back to built-in meshes
- In .tscn files, do NOT reference .glb files as ext_resource — load them via GDScript at runtime

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
- Use only ASCII characters in UI text (Label.text, Button.text, etc.). Godot's default \
font does not include Unicode symbols in WASM exports, so non-ASCII characters render as \
missing glyphs.

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


def _build_initial_prompt(spec: AgenticGameSpec, *, has_3d_assets: bool = False) -> str:
    """Build the initial user message from the game spec."""
    spec_json = json.dumps(spec.model_dump(), indent=2)
    asset_hint = ""
    if has_3d_assets:
        asset_hint = (
            " After writing the core scripts, use generate_3d_asset to create "
            "3D models for the key entities (player, enemies, collectibles, etc.) "
            "before generating scene files."
        )
    return (
        f"Generate all files for this Godot 4 game project.\n\n"
        f"Game Specification:\n{spec_json}\n\n"
        f"Start generating files now. Call write_file for each file, "
        f"one at a time. Begin with the main gameplay scripts, then "
        f"scene files (.tscn), then any auxiliary files.{asset_hint}"
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
    tripo: TripoAssetGenerator | None = None,
    asset_counter: list[int] | None = None,
    soft_timeout: SoftTimeout | None = None,
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
        tripo: Optional Tripo client for 3D asset generation.
        asset_counter: Mutable single-element list tracking total assets
            generated across iterations (shared with caller).

    Returns:
        Tuple of (generated_files dict, conversation messages list).
    """
    generated_files: dict[str, str] = dict(existing_files) if existing_files else {}

    # Determine tools available for this run
    use_3d_assets = tripo is not None and spec.perspective == "3D"
    tools = AGENT_TOOLS_BASE + ([GENERATE_3D_ASSET_TOOL] if use_3d_assets else [])

    # Build initial messages — use fix_context if provided (targeted fix iteration)
    if fix_context is not None:
        initial_content = fix_context
    else:
        initial_content = _build_initial_prompt(spec, has_3d_assets=use_3d_assets)
    messages: list[dict] = [{"role": "user", "content": initial_content}]

    for turn in range(MAX_TURNS_PER_ITERATION):
        # NOTE: No soft timeout check here — once a file generation iteration
        # starts, it runs to completion so the LLM can finish all its fixes.
        # The soft timeout is checked at the pipeline level between iterations.

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
            tools=tools,
            # thinking={"type": "adaptive"},
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
                # Emit a stage event before 3D asset generation (takes 30-60s)
                if block.name == "generate_3d_asset":
                    asset_name = block.input.get("asset_name", "unknown")
                    await emit(
                        ProgressEvent(
                            type="stage_start",
                            message=f"Generating 3D asset: {asset_name}...",
                        )
                    )

                result_str = await _dispatch_tool(
                    block.name,
                    block.input,
                    game_dir,
                    generated_files,
                    tripo=tripo,
                    asset_counter=asset_counter,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )
                # Emit progress for asset generation calls
                if block.name == "generate_3d_asset":
                    asset_name = block.input.get("asset_name", "unknown")
                    await emit(
                        ProgressEvent(
                            type="asset_generated",
                            message=f"Generated 3D asset: {asset_name}",
                            data={"asset_name": asset_name},
                        )
                    )
                # Emit progress for write_file calls
                if block.name == "write_file":
                    filename = block.input.get("filename", "unknown")
                    content = block.input.get("content", "")
                    line_count = content.count("\n") + 1 if content else 0
                    logger.info(
                        "file_generated: %s — content length=%d, lines=%d",
                        filename,
                        len(content),
                        line_count,
                    )
                    await emit(
                        ProgressEvent(
                            type="file_generated",
                            message=f"Generated {filename}",
                            data={"filename": filename, "line_count": line_count},
                        )
                    )

        # Defensive: no tool results means nothing to continue with
        if not tool_results:
            break

        # Append user turn with tool results
        messages.append({"role": "user", "content": tool_results})

    return generated_files, messages
