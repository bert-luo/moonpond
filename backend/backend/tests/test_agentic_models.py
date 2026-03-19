"""Unit tests for agentic pipeline models, spec generator, and tool dispatch."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from backend.pipelines.agentic.models import (
    AgenticGameSpec,
    VerifierError,
    VerifierResult,
)
from backend.pipelines.agentic.spec_generator import run_spec_generator
from backend.pipelines.base import ProgressEvent

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

VALID_SPEC_DICT = {
    "title": "Asteroid Dodger",
    "genre": "arcade",
    "mechanics": ["dodge", "collect"],
    "entities": [
        {"name": "Player", "type": "CharacterBody2D", "behavior": "Moves left/right"},
        {"name": "Asteroid", "type": "Area2D", "behavior": "Falls from top"},
    ],
    "scene_description": "Single screen with player at bottom, asteroids falling",
    "win_condition": "Survive 60 seconds",
    "fail_condition": "Hit by asteroid",
}

# ---------------------------------------------------------------------------
# AgenticGameSpec tests
# ---------------------------------------------------------------------------


class TestAgenticGameSpec:
    def test_validates_well_formed_dict(self):
        spec = AgenticGameSpec.model_validate(VALID_SPEC_DICT)
        assert spec.title == "Asteroid Dodger"
        assert spec.genre == "arcade"
        assert len(spec.mechanics) == 2
        assert len(spec.entities) == 2
        assert spec.scene_description != ""
        assert spec.win_condition == "Survive 60 seconds"
        assert spec.fail_condition == "Hit by asteroid"

    def test_rejects_missing_required_fields(self):
        incomplete = {"title": "Test", "genre": "puzzle"}
        with pytest.raises(ValidationError):
            AgenticGameSpec.model_validate(incomplete)


# ---------------------------------------------------------------------------
# VerifierError tests
# ---------------------------------------------------------------------------


class TestVerifierError:
    def test_validates_well_formed_dict(self):
        err = VerifierError.model_validate(
            {
                "file_path": "player.gd",
                "error_type": "syntax",
                "description": "Missing colon",
                "severity": "critical",
            }
        )
        assert err.file_path == "player.gd"
        assert err.error_type == "syntax"
        assert err.severity == "critical"

    def test_rejects_invalid_error_type(self):
        with pytest.raises(ValidationError):
            VerifierError.model_validate(
                {
                    "file_path": "x.gd",
                    "error_type": "unknown_type",
                    "description": "Bad",
                    "severity": "critical",
                }
            )

    def test_rejects_invalid_severity(self):
        with pytest.raises(ValidationError):
            VerifierError.model_validate(
                {
                    "file_path": "x.gd",
                    "error_type": "syntax",
                    "description": "Bad",
                    "severity": "info",
                }
            )


# ---------------------------------------------------------------------------
# VerifierResult tests
# ---------------------------------------------------------------------------


class TestVerifierResult:
    def test_validates_well_formed_dict(self):
        result = VerifierResult.model_validate(
            {
                "errors": [
                    {
                        "file_path": "player.gd",
                        "error_type": "syntax",
                        "description": "Missing colon",
                        "severity": "critical",
                    }
                ],
                "summary": "1 error found",
            }
        )
        assert len(result.errors) == 1
        assert result.summary == "1 error found"

    def test_has_critical_errors_true_when_critical(self):
        result = VerifierResult(
            errors=[
                VerifierError(
                    file_path="a.gd",
                    error_type="syntax",
                    description="Bad",
                    severity="critical",
                ),
                VerifierError(
                    file_path="b.gd",
                    error_type="logic",
                    description="Meh",
                    severity="warning",
                ),
            ],
            summary="Mixed",
        )
        assert result.has_critical_errors is True

    def test_has_critical_errors_false_when_all_warnings(self):
        result = VerifierResult(
            errors=[
                VerifierError(
                    file_path="a.gd",
                    error_type="logic",
                    description="Minor",
                    severity="warning",
                ),
            ],
            summary="Warnings only",
        )
        assert result.has_critical_errors is False

    def test_has_critical_errors_false_when_empty(self):
        result = VerifierResult(errors=[], summary="Clean")
        assert result.has_critical_errors is False


# ---------------------------------------------------------------------------
# Spec generator tests
# ---------------------------------------------------------------------------


def _make_mock_client(response_json: dict) -> AsyncMock:
    """Create a mock AsyncAnthropic client that returns the given JSON."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_content_block = MagicMock()
    mock_content_block.text = json.dumps(response_json)
    mock_response.content = [mock_content_block]
    client.messages.create = AsyncMock(return_value=mock_response)
    return client


class TestRunSpecGenerator:
    @pytest.mark.anyio
    async def test_returns_agentic_game_spec(self):
        client = _make_mock_client(VALID_SPEC_DICT)
        emit = AsyncMock()

        result = await run_spec_generator(client, "Make an asteroid game", emit)

        assert isinstance(result, AgenticGameSpec)
        assert result.title == "Asteroid Dodger"

    @pytest.mark.anyio
    async def test_emits_stage_start(self):
        client = _make_mock_client(VALID_SPEC_DICT)
        emit = AsyncMock()

        await run_spec_generator(client, "Make an asteroid game", emit)

        emit.assert_called()
        first_event: ProgressEvent = emit.call_args_list[0][0][0]
        assert first_event.type == "stage_start"

    @pytest.mark.anyio
    async def test_calls_llm_with_correct_params(self):
        client = _make_mock_client(VALID_SPEC_DICT)
        emit = AsyncMock()

        await run_spec_generator(client, "Make an asteroid game", emit)

        client.messages.create.assert_called_once()
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"
        assert call_kwargs["max_tokens"] == 4096
        assert "user" in str(call_kwargs["messages"][0]["role"])
        assert "asteroid" in call_kwargs["messages"][0]["content"].lower()


# ---------------------------------------------------------------------------
# Tool dispatch tests
# ---------------------------------------------------------------------------

from pathlib import Path

from backend.pipelines.agentic.file_generator import (
    WRITE_FILE_TOOL,
    READ_FILE_TOOL,
    AGENT_TOOLS,
    _dispatch_tool,
    GENERATOR_MODEL,
    MAX_TURNS_PER_ITERATION,
)


class TestToolDefinitions:
    def test_write_file_tool_schema(self):
        assert WRITE_FILE_TOOL["name"] == "write_file"
        schema = WRITE_FILE_TOOL["input_schema"]
        assert "filename" in schema["properties"]
        assert "content" in schema["properties"]
        assert "filename" in schema["required"]
        assert "content" in schema["required"]

    def test_read_file_tool_schema(self):
        assert READ_FILE_TOOL["name"] == "read_file"
        schema = READ_FILE_TOOL["input_schema"]
        assert "filename" in schema["properties"]
        assert "filename" in schema["required"]

    def test_agent_tools_list(self):
        assert len(AGENT_TOOLS) == 2
        names = {t["name"] for t in AGENT_TOOLS}
        assert names == {"write_file", "read_file"}

    def test_constants(self):
        assert GENERATOR_MODEL == "claude-sonnet-4-6"
        assert MAX_TURNS_PER_ITERATION == 30


class TestDispatchTool:
    @pytest.mark.anyio
    async def test_write_file_creates_file_and_updates_dict(self, tmp_path: Path):
        generated_files: dict[str, str] = {}
        result = await _dispatch_tool(
            "write_file",
            {"filename": "player.gd", "content": "extends Node2D"},
            tmp_path,
            generated_files,
        )
        assert "OK" in result
        assert "player.gd" in result
        assert (tmp_path / "player.gd").read_text() == "extends Node2D"
        assert generated_files["player.gd"] == "extends Node2D"

    @pytest.mark.anyio
    async def test_read_file_from_generated_files_dict(self, tmp_path: Path):
        generated_files = {"player.gd": "extends Node2D"}
        result = await _dispatch_tool(
            "read_file",
            {"filename": "player.gd"},
            tmp_path,
            generated_files,
        )
        assert result == "extends Node2D"

    @pytest.mark.anyio
    async def test_read_file_missing_returns_error(self, tmp_path: Path):
        result = await _dispatch_tool(
            "read_file",
            {"filename": "missing.gd"},
            tmp_path,
            {},
        )
        assert "ERROR" in result
        assert "missing.gd" in result

    @pytest.mark.anyio
    async def test_read_file_falls_back_to_disk(self, tmp_path: Path):
        (tmp_path / "on_disk.gd").write_text("extends Sprite2D")
        result = await _dispatch_tool(
            "read_file",
            {"filename": "on_disk.gd"},
            tmp_path,
            {},
        )
        assert result == "extends Sprite2D"

    @pytest.mark.anyio
    async def test_unknown_tool_returns_error(self, tmp_path: Path):
        result = await _dispatch_tool(
            "unknown_tool",
            {},
            tmp_path,
            {},
        )
        assert "ERROR" in result
        assert "unknown_tool" in result
