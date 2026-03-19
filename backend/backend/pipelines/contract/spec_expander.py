"""Spec Expander stage (Stage 1) — converts a raw user prompt into a RichGameSpec.

Takes the user's game idea and expands it into a detailed specification with
entity-level detail, interactions, scene structure, and win/fail conditions.
"""

from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.pipelines.contract.models import RichGameSpec

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"

_SPEC_EXPANDER_SYSTEM_PROMPT = """\
You are a game design assistant. Given a user's raw game idea, expand it into a \
detailed game specification.

Your job:
- Identify all game entities needed (player, enemies, projectiles, platforms, \
items, UI elements, etc.) with their Godot node types and behaviors.
- Describe interactions between entities (collisions, signals, group membership).
- Describe the scene structure (what nodes are needed, hierarchy).
- Specify win and fail conditions.
- Flesh out implicit mechanics — if the user says "platformer", think about \
gravity, jumping, platforms, hazards, etc.
- Choose a genre that best fits the game idea.
- Suggest visual hints (art style, color palette, mood).

Respond with a JSON object matching this schema:
{
  "title": "string — creative game title",
  "genre": "string — game genre (platformer, shooter, puzzle, etc.)",
  "mechanics": ["list of core gameplay mechanics"],
  "visual_hints": ["list of visual style descriptors"],
  "entities": [
    {
      "name": "string — entity name (e.g. Player, Enemy, Coin)",
      "type": "string — Godot node type (CharacterBody2D, Area2D, StaticBody2D, etc.)",
      "behavior": "string — what this entity does"
    }
  ],
  "interactions": ["list of entity interaction descriptions"],
  "scene_structure": "string — description of the scene hierarchy and layout",
  "win_condition": "string — how the player wins",
  "fail_condition": "string — how the player loses"
}

Think carefully about what entities are needed and how they interact. \
Do NOT include markdown code fences. Respond with raw JSON only.\
"""


async def run_spec_expander(
    client: AsyncAnthropic,
    prompt: str,
    emit: EmitFn,
) -> RichGameSpec:
    """Expand a raw user prompt into a detailed RichGameSpec via LLM.

    Args:
        client: Anthropic async client.
        prompt: Raw user game idea/prompt.
        emit: Async callback for progress events.

    Returns:
        A validated RichGameSpec with entity-level detail.
    """
    await emit(ProgressEvent(type="stage_start", message="Expanding game concept..."))

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=4096,
        system=_SPEC_EXPANDER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    parsed = json.loads(raw)
    result = RichGameSpec.model_validate(parsed)

    return result
