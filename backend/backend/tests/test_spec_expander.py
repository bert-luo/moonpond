"""Unit tests for the Spec Expander stage (Stage 1 of contract pipeline)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipelines.base import ProgressEvent
from backend.stages.contract_models import RichGameSpec
from backend.stages.spec_expander import run_spec_expander

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SPEC_JSON = {
    "title": "Robot Runner",
    "genre": "platformer",
    "mechanics": ["jump", "dodge", "collect coins"],
    "visual_hints": ["neon", "pixel art"],
    "entities": [
        {"name": "Player", "type": "CharacterBody2D", "behavior": "Player-controlled robot that runs and jumps"},
        {"name": "Spike", "type": "StaticBody2D", "behavior": "Damages player on contact"},
        {"name": "Coin", "type": "Area2D", "behavior": "Collectible item, disappears on pickup"},
    ],
    "interactions": [
        "Player collides with Spike -> lose health",
        "Player overlaps Coin -> collect, add score",
    ],
    "scene_structure": "Single scrolling level with platforms, spikes, and coins",
    "win_condition": "Reach the end of the level",
    "fail_condition": "Health reaches zero",
}


def _make_mock_client(response_json: dict) -> AsyncMock:
    """Create a mock AsyncAnthropic client that returns the given JSON."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_content_block = MagicMock()
    mock_content_block.text = json.dumps(response_json)
    mock_response.content = [mock_content_block]
    client.messages.create = AsyncMock(return_value=mock_response)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spec_expander_emits_stage_start():
    """run_spec_expander emits a ProgressEvent with type='stage_start' containing 'Expanding'."""
    client = _make_mock_client(SAMPLE_SPEC_JSON)
    emit = AsyncMock()

    await run_spec_expander(client, "Make a robot platformer", emit)

    emit.assert_called()
    first_call = emit.call_args_list[0]
    event: ProgressEvent = first_call[0][0]
    assert event.type == "stage_start"
    assert "Expanding" in event.message or "expanding" in event.message.lower()


@pytest.mark.asyncio
async def test_spec_expander_returns_rich_game_spec_with_entities():
    """run_spec_expander returns a RichGameSpec with populated entities list."""
    client = _make_mock_client(SAMPLE_SPEC_JSON)
    emit = AsyncMock()

    result = await run_spec_expander(client, "Make a robot platformer", emit)

    assert isinstance(result, RichGameSpec)
    assert len(result.entities) > 0
    assert result.title == "Robot Runner"


@pytest.mark.asyncio
async def test_spec_expander_passes_prompt_to_llm():
    """run_spec_expander passes user prompt to LLM with system prompt."""
    client = _make_mock_client(SAMPLE_SPEC_JSON)
    emit = AsyncMock()
    prompt = "Make a robot platformer with neon visuals"

    await run_spec_expander(client, prompt, emit)

    client.messages.create.assert_called_once()
    call_kwargs = client.messages.create.call_args
    # The user prompt should appear in the messages
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    assert any(prompt in str(m.get("content", "")) for m in messages)
    # Should have a system prompt
    system = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")
    assert system is not None and len(system) > 0


@pytest.mark.asyncio
async def test_spec_expander_parses_llm_json_response():
    """run_spec_expander handles LLM JSON response parsing into RichGameSpec."""
    client = _make_mock_client(SAMPLE_SPEC_JSON)
    emit = AsyncMock()

    result = await run_spec_expander(client, "Make a robot platformer", emit)

    assert result.genre == "platformer"
    assert result.mechanics == ["jump", "dodge", "collect coins"]
    assert result.win_condition == "Reach the end of the level"
    assert result.fail_condition == "Health reaches zero"
