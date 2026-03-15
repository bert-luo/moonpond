"""Game Designer stage — expands a GameSpec into a full GameDesign."""

from __future__ import annotations

import json
import re

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.stages.models import GameDesign, GameSpec

SONNET_MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are a game designer. Given a GameSpec (title, genre, mechanics, visual_hints), \
produce a complete GameDesign as a JSON object.

Respond ONLY with a valid JSON object (no markdown, no explanation) matching this schema:

{
  "title": "string",
  "genre": "string",
  "scenes": [
    {
      "name": "string — scene name (e.g. main, menu, game_over)",
      "description": "string — what happens in this scene",
      "nodes": ["string — Godot 4 node type names (e.g. CharacterBody2D, Sprite2D, Area2D, CollisionShape2D, Timer, Label)"]
    }
  ],
  "visual_style": {
    "palette": "one of: neon, retro, pastel, monochrome",
    "shader": "one of: pixel_art, glow, scanlines, chromatic_aberration, screen_distortion",
    "mood": "string — short mood description"
  },
  "mechanics": ["string — gameplay mechanics"],
  "control_scheme": "one of: wasd, mouse_follow, click_to_move, drag, point_and_shoot",
  "controls": [
    {
      "key": "string — human-readable input label (e.g. Arrow keys, WASD, Drag mouse, Click)",
      "action": "string — what this input does in the game (e.g. Move ship, Aim and fire)"
    }
  ],
  "win_condition": "string — how the player wins",
  "fail_condition": "string — how the player loses"
}

Control scheme guidelines:
- wasd: Traditional keyboard movement (platformers, top-down). Use for games needing 4/8-directional movement.
- mouse_follow: Player entity follows the mouse cursor. Good for avoid-enemies or collection games.
- click_to_move: Player clicks to set a target position. Good for strategy-like or point-and-click games.
- drag: Player drags objects directly. Good for puzzle games, drawing games.
- point_and_shoot: Aim with mouse, click to fire. Good for shooters and turret-defense games.

Include 1-3 scenes. The first scene should be the main gameplay scene. \
Keep the design focused and achievable for a simple 2D browser game.\
"""


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping any markdown code fences."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`")
    return json.loads(cleaned)


async def run_game_designer(
    client: AsyncAnthropic,
    game_spec: GameSpec,
    emit: EmitFn,
) -> GameDesign:
    """Expand a GameSpec into a full GameDesign via LLM."""
    await emit(
        ProgressEvent(type="stage_start", message="Designing game structure...")
    )

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": game_spec.model_dump_json()}],
    )

    raw = response.content[0].text
    data = _extract_json(raw)
    return GameDesign.model_validate(data)
