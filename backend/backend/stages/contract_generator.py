"""Contract Generator stage (Stage 2) — converts a RichGameSpec into a typed GameContract.

Takes the expanded game specification and produces precise interface contracts
for every node, defining methods, signals, groups, dependencies, control scheme,
and visual style. The GameContract is the single source of truth consumed by
all parallel node generators.
"""

from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.stages.contract_models import GameContract, RichGameSpec

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-20250514"

_CONTRACT_GENERATOR_SYSTEM_PROMPT = """\
You are a Godot 4 game architect. Given a detailed game specification (RichGameSpec), \
produce a precise GameContract that defines every node's interface.

Your job:
- Define all node scripts needed with their exact method signatures, signal names, \
and group memberships.
- Specify the dependency graph: which scripts reference which others via the \
dependencies list on each NodeContract.
- Define GameManager enum extensions (e.g. GameState variants) and properties \
(score, lives, etc.).
- Determine the control_scheme (wasd, click_to_move, drag, mouse_follow, \
point_and_shoot) and controls mapping.
- Select visual_style with palette (neon, retro, pastel, monochrome), \
shader (pixel_art, glow, scanlines, chromatic_aberration, screen_distortion), \
and mood.

CRITICAL RULES:
- Do NOT include game_manager.gd as a node — it is a pre-existing autoload. \
Reference it via GameManager.set_state(), GameManager.score, etc.
- Every method, signal, and group name you define here is a binding contract. \
All node generators will implement EXACTLY these interfaces.
- Nodes with empty dependencies lists are leaf nodes that can be generated in parallel.
- Nodes that depend on other nodes' scripts must list those script_paths in dependencies.

Available palettes: neon, retro, pastel, monochrome
Available shaders: pixel_art, glow, scanlines, chromatic_aberration, screen_distortion
Available input actions: move_left, move_right, move_up, move_down, jump, shoot, interact, pause

Respond with a JSON object matching this GameContract schema:
{
  "title": "string",
  "nodes": [
    {
      "script_path": "string — e.g. player.gd",
      "scene_path": "string | null — e.g. Player.tscn",
      "node_type": "string — Godot node type (CharacterBody2D, Area2D, etc.)",
      "description": "string — what this node does",
      "methods": ["list of method signatures, e.g. shoot(), take_damage(amount: int)"],
      "signals": ["list of signal names, e.g. died, health_changed"],
      "groups": ["list of group names"],
      "dependencies": ["list of script_paths this node depends on"]
    }
  ],
  "game_manager_enums": {"EnumName": ["VARIANT1", "VARIANT2"]},
  "game_manager_properties": ["list of property names"],
  "autoloads": ["list of autoload names"],
  "main_scene": "Main.tscn",
  "control_scheme": "string — one of wasd, click_to_move, drag, mouse_follow, point_and_shoot",
  "controls": [{"key": "string", "action": "string"}],
  "visual_style": {"palette": "string", "shader": "string", "mood": "string"}
}

Do NOT include markdown code fences. Respond with raw JSON only.\
"""


async def run_contract_generator(
    client: AsyncAnthropic,
    spec: RichGameSpec,
    emit: EmitFn,
) -> GameContract:
    """Convert a RichGameSpec into a typed GameContract via LLM.

    Args:
        client: Anthropic async client.
        spec: The expanded game specification from Stage 1.
        emit: Async callback for progress events.

    Returns:
        A validated GameContract with node interface contracts.
    """
    await emit(
        ProgressEvent(type="stage_start", message="Generating interface contracts...")
    )

    user_message = (
        f"RichGameSpec:\n{spec.model_dump_json(indent=2)}\n\n"
        "Convert this specification into a precise GameContract. "
        "Define NodeContract entries for every game entity with their "
        "methods, signals, groups, and dependencies. "
        "Include game_manager_enums, game_manager_properties, control_scheme, "
        "controls, and visual_style."
    )

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=8192,
        system=_CONTRACT_GENERATOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text
    parsed = json.loads(raw)
    result = GameContract.model_validate(parsed)

    return result
