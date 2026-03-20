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

        files, conversation = await run_file_generation(client, SAMPLE_SPEC, tmp_path, emit)

        assert "player.gd" in files
        assert files["player.gd"] == "extends Node2D"

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

        files, conversation = await run_file_generation(client, SAMPLE_SPEC, tmp_path, emit)

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

        files, conversation = await run_file_generation(client, SAMPLE_SPEC, tmp_path, emit)

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

        files, conversation = await run_file_generation(client, SAMPLE_SPEC, tmp_path, emit, context_strategy="stateless")

        # In stateless mode, second call's first message should be a fresh stateless prompt
        # (not the accumulated history from the first call).
        # Note: the messages list is mutated after the API call (assistant appended),
        # so we check the first entry is a fresh user prompt containing "Files already generated".
        second_call_kwargs = client.messages.create.call_args_list[1].kwargs
        messages = second_call_kwargs["messages"]
        assert messages[0]["role"] == "user"
        assert "Files already generated" in messages[0]["content"]
        assert "a.gd" in messages[0]["content"]


# ---------------------------------------------------------------------------
# Verifier tests
# ---------------------------------------------------------------------------

import json


class TestRunVerifier:
    @pytest.mark.anyio
    async def test_verifier_zero_tasks(self):
        """Mocked LLM returning zero tasks produces VerifierResult with empty list."""
        from backend.pipelines.agentic.verifier import run_verifier

        response_json = {"tasks": [], "summary": "All good"}
        client = AsyncMock()
        mock_resp = _make_response(
            [_make_tool_use_block("submit_verification", response_json)],
            stop_reason="tool_use",
        )
        client.messages.create = AsyncMock(return_value=mock_resp)
        emit = AsyncMock()

        result = await run_verifier(
            client, SAMPLE_SPEC, {"player.gd": "extends Node2D"}, emit
        )

        assert result.has_critical_tasks is False
        assert len(result.tasks) == 0
        assert result.summary == "All good"

    @pytest.mark.anyio
    async def test_verifier_with_edit_and_create_tasks(self):
        """Mocked LLM returning edit + create tasks produces correct VerifierResult."""
        from backend.pipelines.agentic.verifier import run_verifier

        response_json = {
            "tasks": [
                {
                    "action": "edit",
                    "file": "player.gd",
                    "description": "Missing colon on line 5",
                    "severity": "critical",
                },
                {
                    "action": "create",
                    "file": "enemy.gd",
                    "description": "Enemy AI script missing — spec requires enemies that patrol",
                    "severity": "critical",
                },
            ],
            "summary": "2 tasks identified",
        }
        client = AsyncMock()
        mock_resp = _make_response(
            [_make_tool_use_block("submit_verification", response_json)],
            stop_reason="tool_use",
        )
        client.messages.create = AsyncMock(return_value=mock_resp)
        emit = AsyncMock()

        result = await run_verifier(
            client, SAMPLE_SPEC, {"player.gd": "extends Node2D"}, emit
        )

        assert result.has_critical_tasks is True
        assert len(result.tasks) == 2
        assert result.tasks[0].action == "edit"
        assert result.tasks[0].file == "player.gd"
        assert result.tasks[1].action == "create"
        assert result.tasks[1].file == "enemy.gd"

    @pytest.mark.anyio
    async def test_verifier_emits_stage_start(self):
        """Verifier emits a stage_start ProgressEvent."""
        from backend.pipelines.agentic.verifier import run_verifier

        response_json = {"tasks": [], "summary": "Clean"}
        client = AsyncMock()
        mock_resp = _make_response(
            [_make_tool_use_block("submit_verification", response_json)],
            stop_reason="tool_use",
        )
        client.messages.create = AsyncMock(return_value=mock_resp)
        emit = AsyncMock()

        await run_verifier(client, SAMPLE_SPEC, {"a.gd": "x"}, emit)

        first_event: ProgressEvent = emit.call_args_list[0][0][0]
        assert first_event.type == "stage_start"
        assert "erif" in first_event.message.lower()  # "Verifying" or "Verif..."


class TestBuildVerifierPrompt:
    def test_prompt_includes_files(self):
        """Verifier prompt includes all filenames and their contents."""
        from backend.pipelines.agentic.verifier import _build_verifier_prompt

        files = {
            "player.gd": "extends CharacterBody2D\nfunc _ready():\n\tpass",
            "Main.tscn": '[gd_scene load_steps=2]\n[node name="Main"]',
        }
        prompt = _build_verifier_prompt(SAMPLE_SPEC, files)

        assert "player.gd" in prompt
        assert "Main.tscn" in prompt
        assert "extends CharacterBody2D" in prompt
        assert "gd_scene" in prompt
        assert "Asteroid Dodger" in prompt


# ---------------------------------------------------------------------------
# AgenticPipeline orchestrator tests
# ---------------------------------------------------------------------------

from backend.pipelines.agentic.models import VerifierTask, VerifierResult


def _make_verifier_result(
    critical_files: list[str] | None = None,
    create_files: list[tuple[str, str]] | None = None,
) -> VerifierResult:
    """Create a VerifierResult, optionally with critical edit/create tasks.

    Args:
        critical_files: Files needing critical edits.
        create_files: List of (filename, description) for critical create tasks.
    """
    tasks: list[VerifierTask] = []
    if critical_files:
        tasks.extend(
            VerifierTask(
                action="edit",
                file=f,
                description=f"Error in {f}",
                severity="critical",
            )
            for f in critical_files
        )
    if create_files:
        tasks.extend(
            VerifierTask(
                action="create",
                file=f,
                description=desc,
                severity="critical",
            )
            for f, desc in create_files
        )
    if not tasks:
        return VerifierResult(tasks=[], summary="All good")
    return VerifierResult(tasks=tasks, summary=f"{len(tasks)} critical tasks")


class TestAgenticPipelineGenerate:
    @pytest.mark.anyio
    async def test_generate_full_flow(self, tmp_path: Path):
        """Pipeline calls spec -> generate -> verify (pass) -> export in order."""
        from unittest.mock import patch, call

        from backend.pipelines.agentic.pipeline import AgenticPipeline
        from backend.pipelines.exporter import GAMES_DIR

        pipeline = AgenticPipeline()
        emit = AsyncMock()

        mock_spec = SAMPLE_SPEC
        mock_files = {"player.gd": "extends Node2D", "Main.tscn": "[gd_scene]"}
        mock_conversation = [{"role": "user", "content": "test"}]
        mock_verifier = _make_verifier_result()  # no errors
        mock_game_result = MagicMock()
        mock_game_result.job_id = "test-game"
        mock_game_result.wasm_path = "/games/test/export/index.html"
        mock_game_result.controls = []

        with (
            patch("backend.pipelines.agentic.pipeline.run_spec_generator", new_callable=AsyncMock, return_value=mock_spec) as mock_spec_gen,
            patch("backend.pipelines.agentic.pipeline.run_file_generation", new_callable=AsyncMock, return_value=(mock_files, mock_conversation)) as mock_file_gen,
            patch("backend.pipelines.agentic.pipeline.run_verifier", new_callable=AsyncMock, return_value=mock_verifier) as mock_verify,
            patch("backend.pipelines.agentic.pipeline.run_exporter", new_callable=AsyncMock, return_value=mock_game_result) as mock_export,
            patch("backend.pipelines.agentic.pipeline.GAMES_DIR", tmp_path),
        ):
            result = await pipeline.generate("make a game", "job-1", emit)

        assert result is mock_game_result
        mock_spec_gen.assert_awaited_once()
        mock_file_gen.assert_awaited_once()
        mock_verify.assert_awaited_once()
        mock_export.assert_awaited_once()

    @pytest.mark.anyio
    async def test_iteration_dirs(self, tmp_path: Path):
        """Intermediate dirs created per iteration when save_intermediate=True."""
        from unittest.mock import patch

        from backend.pipelines.agentic.pipeline import AgenticPipeline

        pipeline = AgenticPipeline()
        emit = AsyncMock()

        mock_files = {"player.gd": "extends Node2D"}
        mock_conversation = [{"role": "user", "content": "test"}]
        mock_verifier = _make_verifier_result()
        mock_game_result = MagicMock()
        mock_game_result.job_id = "test"
        mock_game_result.wasm_path = "/games/test/export/index.html"
        mock_game_result.controls = []

        with (
            patch("backend.pipelines.agentic.pipeline.run_spec_generator", new_callable=AsyncMock, return_value=SAMPLE_SPEC),
            patch("backend.pipelines.agentic.pipeline.run_file_generation", new_callable=AsyncMock, return_value=(mock_files, mock_conversation)),
            patch("backend.pipelines.agentic.pipeline.run_verifier", new_callable=AsyncMock, return_value=mock_verifier),
            patch("backend.pipelines.agentic.pipeline.run_exporter", new_callable=AsyncMock, return_value=mock_game_result),
            patch("backend.pipelines.agentic.pipeline.GAMES_DIR", tmp_path),
        ):
            await pipeline.generate("make a game", "job-1", emit, save_intermediate=True)

        # Find the game directory (slug + timestamp)
        game_dirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        assert len(game_dirs) == 1
        intermediate = game_dirs[0] / "intermediate"
        assert intermediate.exists()
        assert (intermediate / "1_agentic_spec.json").exists()
        assert (intermediate / "iteration_1" / "files").exists()
        assert (intermediate / "iteration_1" / "verifier.json").exists()

    @pytest.mark.anyio
    async def test_max_iterations_exit(self, tmp_path: Path):
        """Loop runs exactly MAX_ITERATIONS times when verifier always returns critical errors."""
        from unittest.mock import patch

        from backend.pipelines.agentic.pipeline import AgenticPipeline, MAX_ITERATIONS

        pipeline = AgenticPipeline()
        emit = AsyncMock()

        mock_files = {"player.gd": "extends Node2D"}
        mock_conversation = [{"role": "user", "content": "test"}]
        mock_verifier_bad = _make_verifier_result(["player.gd"])
        mock_game_result = MagicMock()
        mock_game_result.job_id = "test"
        mock_game_result.wasm_path = "/games/test/export/index.html"
        mock_game_result.controls = []

        with (
            patch("backend.pipelines.agentic.pipeline.run_spec_generator", new_callable=AsyncMock, return_value=SAMPLE_SPEC),
            patch("backend.pipelines.agentic.pipeline.run_file_generation", new_callable=AsyncMock, return_value=(mock_files, mock_conversation)) as mock_file_gen,
            patch("backend.pipelines.agentic.pipeline.run_verifier", new_callable=AsyncMock, return_value=mock_verifier_bad) as mock_verify,
            patch("backend.pipelines.agentic.pipeline.run_exporter", new_callable=AsyncMock, return_value=mock_game_result),
            patch("backend.pipelines.agentic.pipeline.GAMES_DIR", tmp_path),
        ):
            result = await pipeline.generate("make a game", "job-1", emit)

        # Verifier called MAX_ITERATIONS times
        assert mock_verify.await_count == MAX_ITERATIONS
        # File generation called MAX_ITERATIONS times (first + fixes)
        assert mock_file_gen.await_count == MAX_ITERATIONS
        # Still proceeds to export
        assert result is mock_game_result

    @pytest.mark.anyio
    async def test_targeted_fix(self, tmp_path: Path):
        """Second iteration passes fix context for only the flagged file."""
        from unittest.mock import patch

        from backend.pipelines.agentic.pipeline import AgenticPipeline

        pipeline = AgenticPipeline()
        emit = AsyncMock()

        # First iteration: verifier flags player.gd
        mock_files_1 = {"player.gd": "extends Node2D\n# broken", "Main.tscn": "[gd_scene]"}
        mock_files_2 = {"player.gd": "extends Node2D\n# fixed"}
        mock_verifier_bad = _make_verifier_result(["player.gd"])
        mock_verifier_good = _make_verifier_result()  # no errors
        mock_game_result = MagicMock()
        mock_game_result.job_id = "test"
        mock_game_result.wasm_path = "/games/test/export/index.html"
        mock_game_result.controls = []

        file_gen_calls = []

        async def mock_file_gen(client, spec, game_dir, emit_fn, *, context_strategy="full_history", fix_context=None, existing_files=None, tripo=None, asset_counter=None):
            file_gen_calls.append({"fix_context": fix_context})
            conversation = [{"role": "user", "content": "test"}]
            if fix_context is None:
                return mock_files_1, conversation
            return mock_files_2, conversation

        with (
            patch("backend.pipelines.agentic.pipeline.run_spec_generator", new_callable=AsyncMock, return_value=SAMPLE_SPEC),
            patch("backend.pipelines.agentic.pipeline.run_file_generation", side_effect=mock_file_gen),
            patch("backend.pipelines.agentic.pipeline.run_verifier", new_callable=AsyncMock, side_effect=[mock_verifier_bad, mock_verifier_good]),
            patch("backend.pipelines.agentic.pipeline.run_exporter", new_callable=AsyncMock, return_value=mock_game_result),
            patch("backend.pipelines.agentic.pipeline.GAMES_DIR", tmp_path),
        ):
            await pipeline.generate("make a game", "job-1", emit)

        # First call: no fix_context
        assert file_gen_calls[0]["fix_context"] is None
        # Second call: fix_context includes player.gd
        assert file_gen_calls[1]["fix_context"] is not None
        assert "player.gd" in file_gen_calls[1]["fix_context"]

    @pytest.mark.anyio
    async def test_expand_input_map_called_when_project_godot_present(self, tmp_path: Path):
        """When project.godot is in generated files, expand_input_map is called before export."""
        from unittest.mock import patch

        from backend.pipelines.agentic.pipeline import AgenticPipeline

        pipeline = AgenticPipeline()
        emit = AsyncMock()

        # project.godot with simplified input format
        project_godot_content = (
            "[rendering]\n\n"
            "[display]\n\n"
            "[input]\n"
            "move_left=arrow_left\n"
            "move_right=arrow_right\n"
        )
        mock_files = {
            "player.gd": "extends Node2D",
            "project.godot": project_godot_content,
        }
        mock_conversation = [{"role": "user", "content": "test"}]
        mock_verifier = _make_verifier_result()  # no errors
        mock_game_result = MagicMock()
        mock_game_result.job_id = "test"
        mock_game_result.wasm_path = "/games/test/export/index.html"
        mock_game_result.controls = []

        captured_export_files = {}

        async def capture_exporter(game_dir, files, controls, emit_fn, *, perspective="2D"):
            captured_export_files.update(files)
            return mock_game_result

        with (
            patch("backend.pipelines.agentic.pipeline.run_spec_generator", new_callable=AsyncMock, return_value=SAMPLE_SPEC),
            patch("backend.pipelines.agentic.pipeline.run_file_generation", new_callable=AsyncMock, return_value=(mock_files, mock_conversation)),
            patch("backend.pipelines.agentic.pipeline.run_verifier", new_callable=AsyncMock, return_value=mock_verifier),
            patch("backend.pipelines.agentic.pipeline.run_exporter", side_effect=capture_exporter),
            patch("backend.pipelines.agentic.pipeline.GAMES_DIR", tmp_path),
        ):
            await pipeline.generate("make a game", "job-1", emit)

        # The project.godot passed to exporter should contain expanded Object() format
        assert "project.godot" in captured_export_files
        expanded = captured_export_files["project.godot"]
        assert "Object(InputEventKey" in expanded
        # Should NOT contain simplified format
        assert "move_left=arrow_left" not in expanded
        assert "move_right=arrow_right" not in expanded

    @pytest.mark.anyio
    async def test_pipeline_completes_without_project_godot(self, tmp_path: Path):
        """When project.godot is NOT in generated files, pipeline completes without error."""
        from unittest.mock import patch

        from backend.pipelines.agentic.pipeline import AgenticPipeline

        pipeline = AgenticPipeline()
        emit = AsyncMock()

        # No project.godot in generated files
        mock_files = {"player.gd": "extends Node2D", "Main.tscn": "[gd_scene]"}
        mock_conversation = [{"role": "user", "content": "test"}]
        mock_verifier = _make_verifier_result()
        mock_game_result = MagicMock()
        mock_game_result.job_id = "test"
        mock_game_result.wasm_path = "/games/test/export/index.html"
        mock_game_result.controls = []

        with (
            patch("backend.pipelines.agentic.pipeline.run_spec_generator", new_callable=AsyncMock, return_value=SAMPLE_SPEC),
            patch("backend.pipelines.agentic.pipeline.run_file_generation", new_callable=AsyncMock, return_value=(mock_files, mock_conversation)),
            patch("backend.pipelines.agentic.pipeline.run_verifier", new_callable=AsyncMock, return_value=mock_verifier),
            patch("backend.pipelines.agentic.pipeline.run_exporter", new_callable=AsyncMock, return_value=mock_game_result),
            patch("backend.pipelines.agentic.pipeline.GAMES_DIR", tmp_path),
            patch("backend.pipelines.agentic.pipeline.expand_input_map") as mock_expand,
        ):
            result = await pipeline.generate("make a game", "job-1", emit)

        # Pipeline completes successfully
        assert result is mock_game_result
        # expand_input_map should NOT have been called
        mock_expand.assert_not_called()


# ---------------------------------------------------------------------------
# Exporter template selection tests
# ---------------------------------------------------------------------------

from backend.pipelines.exporter import get_template_dir, TEMPLATE_DIR_2D, TEMPLATE_DIR_3D


class TestGetTemplateDir:
    def test_get_template_dir_2d(self):
        result = get_template_dir("2D")
        assert result == TEMPLATE_DIR_2D
        assert result.name == "base_2d"

    def test_get_template_dir_3d(self):
        result = get_template_dir("3D")
        assert result == TEMPLATE_DIR_3D
        assert result.name == "base_3d"

    def test_get_template_dir_default(self):
        """2D is the default path — same as TEMPLATE_DIR_2D."""
        assert get_template_dir("2D") == TEMPLATE_DIR_2D
