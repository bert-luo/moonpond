"""Prompt Enhancer stage — enriches a raw user prompt into a structured GameSpec."""

from __future__ import annotations

import json
import re

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.stages.models import GameSpec

HAIKU_MODEL = "claude-haiku-4-5"

SYSTEM_PROMPT = """\
You are a game design analyst. Given a short game idea from a user, produce a \
structured JSON object describing the game concept.

Respond ONLY with a valid JSON object (no markdown, no explanation) matching this schema:
{
  "title": "string — a catchy game title",
  "genre": "string — primary genre (e.g. platformer, shooter, puzzle, arcade, runner)",
  "mechanics": ["string — core gameplay mechanics, 2-5 items"],
  "visual_hints": ["string — visual style keywords, 2-4 items (e.g. neon, pixel art, retro, dark, vibrant)"]
}

Be creative but concise. Infer reasonable defaults when the user's prompt is vague.\
"""


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping any markdown code fences."""
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.strip().rstrip("`")
    return json.loads(cleaned)


async def run_prompt_enhancer(
    client: AsyncAnthropic,
    prompt: str,
    emit: EmitFn,
) -> GameSpec:
    """Enrich a raw user prompt into a structured GameSpec via LLM."""
    await emit(ProgressEvent(type="stage_start", message="Understanding your idea..."))

    response = await client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text
    data = _extract_json(raw)
    return GameSpec.model_validate(data)
