"""Integration tests for agentic pipeline file generation loop and verifier."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipelines.agentic.models import AgenticGameSpec
from backend.pipelines.base import ProgressEvent


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

SAMPLE_SPEC = AgenticGameSpec(
    title="Asteroid Dodger",
    genre="arcade",
    mechanics=["dodge", "collect"],
    entities=[
        {"name": "Player", "type": "CharacterBody2D", "behavior": "Moves left/right"},
        {"name": "Asteroid", "type": "Area2D", "behavior": "Falls from top"},
    ],
    scene_description="Single screen with player at bottom, asteroids falling",
    win_condition="Survive 60 seconds",
    fail_condition="Hit by asteroid",
)


def _make_tool_use_block(tool_name: str, tool_input: dict, block_id: str = "toolu_1") -> MagicMock:
    """Create a mock tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = block_id
    return block


def _make_text_block(text: str) -> MagicMock:
    """Create a mock text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _make_response(content_blocks: list, stop_reason: str = "end_turn") -> MagicMock:
    """Create a mock Anthropic API response."""
    resp = MagicMock()
    resp.content = content_blocks
    resp.stop_reason = stop_reason
    resp.usage = MagicMock(input_tokens=100, output_tokens=200)
    return resp


# ---------------------------------------------------------------------------
# File generation loop tests
# ---------------------------------------------------------------------------


class TestRunFileGeneration:
    @pytest.mark.anyio
    async def test_message_accumulation(self, tmp_path: Path):
        """Mocked LLM returns one write_file then end_turn — verify role alternation."""
        from backend.pipelines.agentic.file_generator import run_file_generation

        # First call: assistant returns write_file tool_use
        resp1 = _make_response(
            [_make_tool_use_block("write_file", {"filename": "player.gd", "content": "extends Node2D"})],
            stop_reason="tool_use",
        )
        # Second call: assistant returns end_turn
        resp2 = _make_response(
            [_make_text_block("All files generated.")],
            stop_reason="end_turn",
        )

        client = AsyncMock()
        client.messages.create = AsyncMock(side_effect=[resp1, resp2])
        emit = AsyncMock()

        result = await run_file_generation(client, SAMPLE_SPEC, tmp_path, emit)

        assert "player.gd" in result
        assert result["player.gd"] == "extends Node2D"

        # Verify LLM was called twice
        assert client.messages.create.call_count == 2

        # Second call should have accumulated messages:
        # [user(initial), assistant(tool_use), user(tool_result)]
        second_call_kwargs = client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

    @pytest.mark.anyio
    async def test_max_turns_exit(self, tmp_path: Path):
        """Loop exits after MAX_TURNS_PER_ITERATION even if LLM keeps returning tool_use."""
        from backend.pipelines.agentic.file_generator import run_file_generation, MAX_TURNS_PER_ITERATION

        # Always return tool_use
        def make_tool_response(*args, **kwargs):
            return _make_response(
                [_make_tool_use_block("write_file", {"filename": "file.gd", "content": "x"})],
                stop_reason="tool_use",
            )

        client = AsyncMock()
        client.messages.create = AsyncMock(side_effect=make_tool_response)
        emit = AsyncMock()

        result = await run_file_generation(client, SAMPLE_SPEC, tmp_path, emit)

        # Should have stopped at max turns
        assert client.messages.create.call_count == MAX_TURNS_PER_ITERATION

    @pytest.mark.anyio
    async def test_write_file_emits_progress(self, tmp_path: Path):
        """Each write_file tool call emits a ProgressEvent with the filename."""
        from backend.pipelines.agentic.file_generator import run_file_generation

        resp1 = _make_response(
            [_make_tool_use_block("write_file", {"filename": "player.gd", "content": "extends Node2D"})],
            stop_reason="tool_use",
        )
        resp2 = _make_response(
            [_make_text_block("Done.")],
            stop_reason="end_turn",
        )

        client = AsyncMock()
        client.messages.create = AsyncMock(side_effect=[resp1, resp2])
        emit = AsyncMock()

        await run_file_generation(client, SAMPLE_SPEC, tmp_path, emit)

        # Find progress events that mention the filename
        progress_events = [
            call.args[0] for call in emit.call_args_list
            if isinstance(call.args[0], ProgressEvent) and "player.gd" in call.args[0].message
        ]
        assert len(progress_events) >= 1

    @pytest.mark.anyio
    async def test_stateless_mode_resets_messages(self, tmp_path: Path):
        """In stateless mode, messages are reset each turn."""
        from backend.pipelines.agentic.file_generator import run_file_generation

        resp1 = _make_response(
            [_make_tool_use_block("write_file", {"filename": "a.gd", "content": "extends Node"})],
            stop_reason="tool_use",
        )
        resp2 = _make_response(
            [_make_text_block("Done.")],
            stop_reason="end_turn",
        )

        client = AsyncMock()
        client.messages.create = AsyncMock(side_effect=[resp1, resp2])
        emit = AsyncMock()

        await run_file_generation(client, SAMPLE_SPEC, tmp_path, emit, context_strategy="stateless")

        # In stateless mode, second call's first message should be a fresh stateless prompt
        # (not the accumulated history from the first call).
        # Note: the messages list is mutated after the API call (assistant appended),
        # so we check the first entry is a fresh user prompt containing "Files already generated".
        second_call_kwargs = client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert "Files already generated" in messages[0]["content"]
        assert "a.gd" in messages[0]["content"]
