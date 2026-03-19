"""Spec Generator — first conversation turn of the agentic pipeline.

Converts a raw user prompt into an AgenticGameSpec via a single LLM call.
Follows the project convention: client.messages.create + json.loads + model_validate.
"""

from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.pipelines.agentic.models import AgenticGameSpec

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"

SPEC_SYSTEM_PROMPT = """\
You are a game design assistant. Given a user's raw game idea, produce a \
detailed game specification as a JSON object.

Your job:
- Choose a creative title for the game.
- Identify the genre (platformer, shooter, puzzle, arcade, etc.).
- List the core gameplay mechanics.
- Identify all game entities needed (player, enemies, projectiles, platforms, \
items, UI elements, etc.) with their Godot node types and behaviors.
- Describe the scene layout and visual structure.
- Specify win and fail conditions.

Respond with a JSON object matching this exact schema:
{
  "title": "string - creative game title",
  "genre": "string - game genre",
  "mechanics": ["list of core gameplay mechanics"],
  "entities": [
    {
      "name": "string - entity name (e.g. Player, Enemy, Coin)",
      "type": "string - Godot node type (CharacterBody2D, Area2D, etc.)",
      "behavior": "string - what this entity does"
    }
  ],
  "scene_description": "string - description of the scene layout and visual structure",
  "win_condition": "string - how the player wins",
  "fail_condition": "string - how the player loses"
}

Respond ONLY with valid JSON. Do NOT include markdown code fences or any other text.\
"""


async def run_spec_generator(
    client: AsyncAnthropic,
    prompt: str,
    emit: EmitFn,
) -> AgenticGameSpec:
    """Generate a rich game spec from a raw user prompt via LLM.

    Args:
        client: Anthropic async client.
        prompt: Raw user game idea/prompt.
        emit: Async callback for progress events.

    Returns:
        A validated AgenticGameSpec with entity-level detail.
    """
    await emit(ProgressEvent(type="stage_start", message="Generating game specification..."))

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=4096,
        system=SPEC_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    parsed = json.loads(raw)
    result = AgenticGameSpec.model_validate(parsed)

    return result
