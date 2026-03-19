"""Spec Generator — first conversation turn of the agentic pipeline.

Converts a raw user prompt into an AgenticGameSpec via a single LLM call.
Uses tool_choice to force structured JSON output.
"""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.pipelines.agentic.models import AgenticGameSpec

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"

SPEC_SYSTEM_PROMPT = """\
You are a game design assistant. Given a user's raw game idea, produce a \
detailed game specification.

Your job:
- Choose a creative title for the game.
- Identify the genre (platformer, shooter, puzzle, arcade, etc.).
- List the core gameplay mechanics.
- Identify all game entities needed (player, enemies, projectiles, platforms, \
items, UI elements, etc.) with their Godot node types and behaviors.
- Describe the scene layout and visual structure.
- Specify win and fail conditions.

Call the submit_spec tool with your game specification.\
"""

SUBMIT_SPEC_TOOL = {
    "name": "submit_spec",
    "description": "Submit the game specification.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Creative game title.",
            },
            "genre": {
                "type": "string",
                "description": "Game genre (platformer, shooter, puzzle, arcade, etc.).",
            },
            "mechanics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of core gameplay mechanics.",
            },
            "entities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Entity name (e.g. Player, Enemy, Coin).",
                        },
                        "type": {
                            "type": "string",
                            "description": "Godot node type (CharacterBody2D, Area2D, etc.).",
                        },
                        "behavior": {
                            "type": "string",
                            "description": "What this entity does.",
                        },
                    },
                    "required": ["name", "type", "behavior"],
                },
            },
            "scene_description": {
                "type": "string",
                "description": "Description of the scene layout and visual structure.",
            },
            "win_condition": {
                "type": "string",
                "description": "How the player wins.",
            },
            "fail_condition": {
                "type": "string",
                "description": "How the player loses.",
            },
        },
        "required": [
            "title",
            "genre",
            "mechanics",
            "entities",
            "scene_description",
            "win_condition",
            "fail_condition",
        ],
    },
}


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
        tools=[SUBMIT_SPEC_TOOL],
        tool_choice={"type": "tool", "name": "submit_spec"},
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract the tool call input — guaranteed by tool_choice
    tool_block = next(b for b in response.content if b.type == "tool_use")
    result = AgenticGameSpec.model_validate(tool_block.input)

    return result
