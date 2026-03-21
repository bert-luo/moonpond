"""File Generator — tool definitions, dispatch, and multi-turn generation loop.

Defines the write_file and read_file tools that the LLM agent calls via
the Anthropic tool_use API, the dispatch function that executes them, and
the run_file_generation loop that drives the multi-turn conversation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from anthropic import AsyncAnthropic

from backend.pipelines.agentic.image_gen_client import (
    ImageGenClient,
    ImageGenError,
    PostProcessConfig,
)
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
        "Maximum 5 assets per game. Each call takes ~30-60 seconds. "
        "You can call this tool multiple times in a single response to generate "
        "assets in parallel — this is strongly encouraged to save time."
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

GENERATE_2D_ASSET_TOOL = {
    "name": "generate_2d_asset",
    "description": (
        "Generate a 2D sprite asset from a text description using AI image generation. "
        "Returns the res:// path of the generated .png file in assets/sprites/. "
        "For animated entities, set spritesheet=true to generate a multi-frame spritesheet. "
        "Use for key visual elements (player, enemies, items, NPCs) — NOT for simple "
        "rectangles or shapes that can be drawn with ColorRect or draw_rect(). "
        "Maximum 8 assets per game. Each call takes ~10-30 seconds. "
        "You can call this tool multiple times in a single response to generate "
        "assets in parallel — this is strongly encouraged to save time."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "asset_name": {
                "type": "string",
                "description": (
                    "Short snake_case name for the asset file, e.g. "
                    "'player', 'coin', 'enemy_slime'."
                ),
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Detailed description of the sprite to generate. "
                    "Be specific about style, color, pose, and view angle. "
                    "E.g. 'A pixel art treasure chest with gold trim, "
                    "top-down view, 2D game style'."
                ),
            },
            "spritesheet": {
                "type": "boolean",
                "description": (
                    "If true, generates a multi-frame spritesheet (e.g. walk cycle). "
                    "The prompt should describe the animation. "
                    "Frames are laid out horizontally. Default false."
                ),
            },
            "num_frames": {
                "type": "integer",
                "description": (
                    "Number of frames for spritesheet mode (default 4, max 8). "
                    "Ignored if spritesheet is false."
                ),
            },
            "target_width": {
                "type": "integer",
                "description": (
                    "Target width in pixels for the final sprite (after trimming). "
                    "Use this to control the in-game size: e.g. 64 for small "
                    "collectibles, 128-256 for characters, 512+ for large backgrounds. "
                    "For spritesheets this is the per-frame width. Optional."
                ),
            },
            "target_height": {
                "type": "integer",
                "description": (
                    "Target height in pixels for the final sprite (after trimming). "
                    "For spritesheets this is the per-frame height. Optional."
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
MAX_2D_ASSETS = 8

# Asset generation tool names (eligible for parallel dispatch)
_ASSET_TOOLS = frozenset(("generate_3d_asset", "generate_2d_asset"))


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
    image_gen: ImageGenClient | None = None,
    asset_counter: list[int] | None = None,
    budget_remaining: int | None = None,
) -> str:
    """Execute a tool call and return the result string for tool_result.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Input dict from the LLM tool call.
        game_dir: Path to the game project directory.
        generated_files: Mutable dict tracking filename -> content for all
            files written during this generation iteration.
        tripo: Optional Tripo client for 3D asset generation.
        image_gen: Optional ImageGenClient for 2D sprite generation.
        asset_counter: Mutable single-element list tracking assets generated.
        budget_remaining: When not None, caller has already reserved a budget
            slot — skip the budget check/increment and use this value for the
            "remaining" message.  On failure the caller releases the slot.

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

        # Budget check — skip when caller pre-reserved a slot (parallel dispatch)
        if budget_remaining is None:
            counter = asset_counter or [0]
            if counter[0] >= MAX_3D_ASSETS:
                return (
                    f"ERROR: asset budget exhausted ({MAX_3D_ASSETS}/{MAX_3D_ASSETS} used). "
                    "Use built-in meshes (BoxMesh, SphereMesh, etc.) for remaining objects."
                )

        asset_name = tool_input.get("asset_name", "")
        prompt = tool_input.get("prompt", "")
        if not asset_name or not prompt:
            return (
                "ERROR: generate_3d_asset requires 'asset_name' and 'prompt' parameters"
            )
        dest = game_dir / "assets" / "models" / f"{asset_name}.glb"

        try:
            await tripo.generate_3d_asset(prompt=prompt, dest=dest)
            if budget_remaining is None:
                counter[0] += 1
                remaining = MAX_3D_ASSETS - counter[0]
            else:
                remaining = budget_remaining
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

    elif tool_name == "generate_2d_asset":
        if image_gen is None:
            return "ERROR: 2D asset generation not available (no API key configured)"

        # Budget check — skip when caller pre-reserved a slot (parallel dispatch)
        if budget_remaining is None:
            counter = asset_counter or [0]
            if counter[0] >= MAX_2D_ASSETS:
                return (
                    f"ERROR: asset budget exhausted ({MAX_2D_ASSETS}/{MAX_2D_ASSETS} used). "
                    "Use ColorRect or draw_rect() for remaining visuals."
                )

        asset_name = tool_input.get("asset_name", "")
        prompt = tool_input.get("prompt", "")
        is_spritesheet = tool_input.get("spritesheet", False)
        num_frames = tool_input.get("num_frames", 4)
        target_w = tool_input.get("target_width")
        target_h = tool_input.get("target_height")
        if not asset_name or not prompt:
            return (
                "ERROR: generate_2d_asset requires 'asset_name' and 'prompt' parameters"
            )

        # Build per-call post-process config with optional LLM-specified size
        post_process = PostProcessConfig(
            trim=True,
            target_size=(target_w, target_h) if target_w and target_h else None,
        )

        dest = game_dir / "assets" / "sprites" / f"{asset_name}.png"

        try:
            if is_spritesheet:
                asset = await image_gen.generate_spritesheet(
                    prompt=prompt,
                    dest=dest,
                    num_frames=min(num_frames, 6),
                    post_process=post_process,
                )
                if budget_remaining is None:
                    counter[0] += 1
                    remaining = MAX_2D_ASSETS - counter[0]
                else:
                    remaining = budget_remaining
                res_path = f"res://assets/sprites/{asset_name}.png"
                fw, fh = asset.frame_size
                n = asset.frame_count
                return (
                    f"OK: generated {res_path} ({asset.image.width}x{asset.image.height}, "
                    f"{n} frames, {fw}x{fh} each). "
                    f"{remaining} asset(s) remaining.\n"
                    f"Load in GDScript as AnimatedSprite2D:\n"
                    f"  var frames = SpriteFrames.new()\n"
                    f'  var tex = load("{res_path}")\n'
                    f"  for i in range({n}):\n"
                    f"      var atlas = AtlasTexture.new()\n"
                    f"      atlas.atlas = tex\n"
                    f"      atlas.region = Rect2(i * {fw}, 0, {fw}, {fh})\n"
                    f'      frames.add_frame("default", atlas)\n'
                    f"  var anim_sprite = AnimatedSprite2D.new()\n"
                    f"  anim_sprite.sprite_frames = frames\n"
                    f'  anim_sprite.play("default")\n'
                    f"  add_child(anim_sprite)"
                )
            else:
                asset = await image_gen.generate(
                    prompt=prompt,
                    dest=dest,
                    post_process=post_process,
                )
                if budget_remaining is None:
                    counter[0] += 1
                    remaining = MAX_2D_ASSETS - counter[0]
                else:
                    remaining = budget_remaining
                res_path = f"res://assets/sprites/{asset_name}.png"
                return (
                    f"OK: generated {res_path} ({asset.image.width}x{asset.image.height}). "
                    f"{remaining} asset(s) remaining.\n"
                    f"Load in GDScript:\n"
                    f"  var sprite = Sprite2D.new()\n"
                    f'  sprite.texture = load("{res_path}")\n'
                    f"  add_child(sprite)"
                )
        except ImageGenError as e:
            logger.error("generate_2d_asset failed for %s: %s", asset_name, e)
            return (
                f"ERROR: 2D generation failed for '{asset_name}': {e}. "
                "Fall back to ColorRect with a solid color."
            )
        except Exception as e:
            logger.error("generate_2d_asset unexpected error for %s: %s", asset_name, e)
            return (
                f"ERROR: unexpected failure generating '{asset_name}': {e}. "
                "Fall back to ColorRect."
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

    # 2D asset generation (only for 2D)
    essentials_2d = ""
    if perspective == "2D":
        essentials_2d = """
2D ASSET GENERATION (generate_2d_asset tool):
You have access to an AI image generator. You SHOULD use it to make the game visually
appealing — games with real sprite art look dramatically better than games using only
ColorRect and primitive shapes. Plan to use 3-5 assets per game for the most important entities.
- Use for key game elements: player character, enemies, collectibles, NPCs, items
- Do NOT waste assets on simple shapes (backgrounds, walls, floors) — use ColorRect or draw_rect()
- Maximum 8 assets per game — budget them for the most visually important elements
- Set spritesheet=true for animated entities (player walk cycle, enemy animation)
- Each asset is a .png in res://assets/sprites/
- For single sprites, load as:
    var sprite = Sprite2D.new()
    sprite.texture = load("res://assets/sprites/asset_name.png")
    add_child(sprite)
- For spritesheets, the tool returns frame count and size — use AtlasTexture to slice frames:
    var frames = SpriteFrames.new()
    var tex = load("res://assets/sprites/asset_name.png")
    for i in range(N):
        var atlas = AtlasTexture.new()
        atlas.atlas = tex
        atlas.region = Rect2(i * FRAME_W, 0, FRAME_W, FRAME_H)
        frames.add_frame("default", atlas)
    var anim_sprite = AnimatedSprite2D.new()
    anim_sprite.sprite_frames = frames
- Generation takes ~10-30 seconds per asset — generate GDScript files first, then call generate_2d_asset
  for ALL key entities in a SINGLE response (they run in parallel), then generate .tscn scene files
- If generation fails, the tool returns an error — fall back to ColorRect with a solid color
- In .tscn files, do NOT reference generated .png files as ext_resource — load them via GDScript at runtime

"""

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
- Generation takes ~30-60 seconds per asset — generate GDScript files first, then call generate_3d_asset
  for ALL key assets in a SINGLE response (they run in parallel), then generate .tscn scene files
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
        + essentials_2d
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


def _build_initial_prompt(
    spec: AgenticGameSpec,
    *,
    has_3d_assets: bool = False,
    has_2d_assets: bool = False,
) -> str:
    """Build the initial user message from the game spec."""
    spec_json = json.dumps(spec.model_dump(), indent=2)
    asset_hint = ""
    if has_3d_assets:
        asset_hint = (
            " After writing the core scripts, call generate_3d_asset for ALL key "
            "entities (player, enemies, collectibles, etc.) in a single response "
            "so they generate in parallel. Then generate scene files."
        )
    elif has_2d_assets:
        asset_hint = (
            " After writing the core scripts, call generate_2d_asset for ALL key "
            "entities (player, enemies, collectibles, etc.) in a single response "
            "so they generate in parallel. Use spritesheet=true for animated entities. "
            "Then generate scene files."
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
    image_gen: ImageGenClient | None = None,
    asset_counter: list[int] | None = None,
    soft_timeout: SoftTimeout | None = None,
    thinking: bool = False,
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
        image_gen: Optional ImageGenClient for 2D sprite generation.
        asset_counter: Mutable single-element list tracking total assets
            generated across iterations (shared with caller).
        thinking: If True, enable extended thinking on the file generation
            model (budget_tokens=8192, max_tokens doubled to 16384).

    Returns:
        Tuple of (generated_files dict, conversation messages list).
    """
    generated_files: dict[str, str] = dict(existing_files) if existing_files else {}

    # Determine tools available for this run
    use_3d_assets = tripo is not None and spec.perspective == "3D"
    use_2d_assets = image_gen is not None and spec.perspective == "2D"
    tools = AGENT_TOOLS_BASE[:]
    if use_2d_assets:
        tools.append(GENERATE_2D_ASSET_TOOL)
    if use_3d_assets:
        tools.append(GENERATE_3D_ASSET_TOOL)

    # Build initial messages — use fix_context if provided (targeted fix iteration)
    if fix_context is not None:
        initial_content = fix_context
    else:
        initial_content = _build_initial_prompt(
            spec,
            has_3d_assets=use_3d_assets,
            has_2d_assets=use_2d_assets,
        )
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

        api_kwargs: dict = dict(
            model=GENERATOR_MODEL,
            max_tokens=16384 if thinking else 8192,
            system=build_generator_system_prompt(spec.perspective),
            tools=tools,
            messages=messages,
        )
        if thinking:
            api_kwargs["thinking"] = {"type": "enabled", "budget_tokens": 8192}
        response = await client.messages.create(**api_kwargs)

        # Append assistant turn with full content list
        messages.append({"role": "assistant", "content": response.content})

        # Exit on end_turn
        if response.stop_reason == "end_turn":
            break

        # Process tool_use blocks — asset generation runs in parallel,
        # everything else (write_file, read_file) runs sequentially.
        tool_results: list[dict] = []
        asset_blocks: list = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name in _ASSET_TOOLS:
                asset_blocks.append(block)
            else:
                # Sequential dispatch for write_file / read_file
                result_str = await _dispatch_tool(
                    block.name,
                    block.input,
                    game_dir,
                    generated_files,
                    tripo=tripo,
                    image_gen=image_gen,
                    asset_counter=asset_counter,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )
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

        # --- Parallel asset generation ---
        if asset_blocks:
            counter = asset_counter or [0]
            is_3d = spec.perspective == "3D"
            max_assets = MAX_3D_ASSETS if is_3d else MAX_2D_ASSETS

            # Pre-reserve budget slots (no awaits here, so no race)
            approved: list[tuple] = []  # (block, remaining_after)
            for block in asset_blocks:
                if counter[0] < max_assets:
                    counter[0] += 1
                    remaining = max_assets - counter[0]
                    approved.append((block, remaining))
                else:
                    dim = "3D" if block.name == "generate_3d_asset" else "2D"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": (
                                f"ERROR: asset budget exhausted "
                                f"({max_assets}/{max_assets} used). "
                                + (
                                    "Use built-in meshes (BoxMesh, SphereMesh, etc.) "
                                    "for remaining objects."
                                    if dim == "3D"
                                    else "Use ColorRect or draw_rect() for remaining visuals."
                                )
                            ),
                        }
                    )

            if approved:
                # Emit stage_start for all approved assets upfront
                for block, _ in approved:
                    asset_name = block.input.get("asset_name", "unknown")
                    dim = "3D" if block.name == "generate_3d_asset" else "2D"
                    await emit(
                        ProgressEvent(
                            type="stage_start",
                            message=f"Generating {dim} asset: {asset_name}...",
                        )
                    )

                if len(approved) > 1:
                    logger.info(
                        "Dispatching %d asset generations in parallel",
                        len(approved),
                    )

                # Launch all approved asset generations concurrently
                gather_results = await asyncio.gather(
                    *(
                        _dispatch_tool(
                            block.name,
                            block.input,
                            game_dir,
                            generated_files,
                            tripo=tripo,
                            image_gen=image_gen,
                            asset_counter=asset_counter,
                            budget_remaining=remaining,
                        )
                        for block, remaining in approved
                    ),
                    return_exceptions=True,
                )

                for (block, _remaining), result in zip(approved, gather_results):
                    if isinstance(result, BaseException):
                        # Release the pre-reserved budget slot on failure
                        counter[0] -= 1
                        asset_name = block.input.get("asset_name", "unknown")
                        logger.error(
                            "Parallel asset generation failed for %s: %s",
                            asset_name,
                            result,
                        )
                        result_str = (
                            f"ERROR: asset generation failed for '{asset_name}': "
                            f"{result}. Fall back to primitives."
                        )
                    else:
                        result_str = result

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )
                    # Emit asset_generated for successful results
                    if not isinstance(result, BaseException):
                        asset_name = block.input.get("asset_name", "unknown")
                        dim = "3D" if block.name == "generate_3d_asset" else "2D"
                        await emit(
                            ProgressEvent(
                                type="asset_generated",
                                message=f"Generated {dim} asset: {asset_name}",
                                data={"asset_name": asset_name, "dim": dim},
                            )
                        )

        # Defensive: no tool results means nothing to continue with
        if not tool_results:
            break

        # Append user turn with tool results
        messages.append({"role": "user", "content": tool_results})

    return generated_files, messages
