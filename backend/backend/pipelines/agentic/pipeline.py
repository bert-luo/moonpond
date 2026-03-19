"""Agentic Pipeline — top-level orchestrator for the agent-loop pipeline.

Ties together spec generation, the generate-verify-fix loop, and WASM export.
Satisfies the GamePipeline Protocol.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from anthropic import AsyncAnthropic

from backend.pipelines.agentic.file_generator import run_file_generation
from backend.pipelines.agentic.input_map import expand_input_map
from backend.pipelines.agentic.models import AgenticGameSpec
from backend.pipelines.agentic.spec_generator import run_spec_generator
from backend.pipelines.agentic.verifier import run_verifier
from backend.pipelines.base import EmitFn, GameResult, ProgressEvent
from backend.pipelines.exporter import GAMES_DIR, run_exporter

MAX_ITERATIONS = 3
"""Maximum generate-verify-fix iterations before proceeding to export."""


def _serialize_messages(messages: list[dict]) -> list[dict]:
    """Convert a conversation message list to JSON-serializable form.

    Assistant message content blocks are Anthropic SDK objects (TextBlock,
    ToolUseBlock) which aren't plain dicts.  This recursively converts them.
    """
    serialized = []
    for msg in messages:
        content = msg["content"]
        if isinstance(content, list):
            # Could be SDK content blocks (assistant) or tool_result dicts (user)
            blocks = []
            for item in content:
                if isinstance(item, dict):
                    blocks.append(item)
                elif hasattr(item, "model_dump"):
                    blocks.append(item.model_dump())
                else:
                    blocks.append({"type": "text", "text": str(item)})
            serialized.append({"role": msg["role"], "content": blocks})
        else:
            serialized.append({"role": msg["role"], "content": content})
    return serialized


def _slugify(title: str, max_len: int = 40) -> str:
    """Convert a game title to a filesystem-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:max_len].rstrip("-")


def _build_fix_context(
    spec: AgenticGameSpec,
    flagged_files: dict[str, str],
    errors_by_file: dict[str, list[str]],
) -> str:
    """Build a fix prompt that includes flagged file content and verifier errors.

    Args:
        spec: The game specification.
        flagged_files: Dict mapping filename -> current content for files to fix.
        errors_by_file: Dict mapping filename -> list of error descriptions.

    Returns:
        A prompt string for the fix iteration.
    """
    sections = []
    for filename, content in flagged_files.items():
        error_list = errors_by_file.get(filename, [])
        error_text = (
            "\n".join(f"  - {e}" for e in error_list)
            if error_list
            else "  (no specific errors listed)"
        )
        sections.append(
            f"--- {filename} ---\n"
            f"Current content:\n{content}\n\n"
            f"Errors found:\n{error_text}\n"
            f"--- end {filename} ---"
        )

    files_block = "\n\n".join(sections)
    return (
        f"The following files have errors that need to be fixed. "
        f"Rewrite each file using write_file with the corrected content.\n\n"
        f"Game: {spec.title} ({spec.genre})\n\n"
        f"Files to fix:\n\n{files_block}\n\n"
        f"Fix all listed errors. Write each corrected file using write_file."
    )


class AgenticPipeline:
    """Agent-loop pipeline satisfying the GamePipeline Protocol.

    Stages:
      1. Spec Generator  -- raw prompt -> AgenticGameSpec
      2. Generate-Verify-Fix loop (up to MAX_ITERATIONS)
      3. Exporter         -- assembled project -> WASM
    """

    def __init__(self, *, context_strategy: str = "full_history") -> None:
        self._client = AsyncAnthropic()
        self._context_strategy = context_strategy

    async def generate(
        self,
        prompt: str,
        job_id: str,
        emit: EmitFn,
        *,
        save_intermediate: bool = True,
    ) -> GameResult:
        """Generate a game from a text prompt using the agentic loop.

        Parameters match the GamePipeline Protocol signature exactly.
        """
        try:
            await emit(
                ProgressEvent(
                    type="stage_start",
                    message="Starting agentic pipeline...",
                )
            )

            # Stage 1: Spec Generator -- prompt -> AgenticGameSpec
            spec = await run_spec_generator(self._client, prompt, emit)

            # Build a human-readable directory name
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            game_dir = f"{_slugify(spec.title)}_{timestamp}"

            # Set up intermediate output directory
            dump_dir = (
                GAMES_DIR / game_dir / "intermediate" if save_intermediate else None
            )
            if dump_dir:
                dump_dir.mkdir(parents=True, exist_ok=True)
                (dump_dir / "1_agentic_spec.json").write_text(
                    spec.model_dump_json(indent=2)
                )

            # Create project directory
            project_dir = GAMES_DIR / game_dir / "project"
            project_dir.mkdir(parents=True, exist_ok=True)

            # Stage 2: Generate-Verify-Fix loop
            all_files: dict[str, str] = {}
            fix_ctx: str | None = None

            for iteration in range(1, MAX_ITERATIONS + 1):
                await emit(
                    ProgressEvent(
                        type="stage_start",
                        message=f"Iteration {iteration}: generating files...",
                    )
                )

                # Generate files (first iteration: full generation; fix iterations: targeted)
                new_files, conversation = await run_file_generation(
                    self._client,
                    spec,
                    project_dir,
                    emit,
                    context_strategy=self._context_strategy,
                    fix_context=fix_ctx,
                )

                # Merge new/updated files into the running set
                all_files.update(new_files)

                # Save iteration artifacts
                if dump_dir:
                    iter_dir = dump_dir / f"iteration_{iteration}"
                    files_dir = iter_dir / "files"
                    files_dir.mkdir(parents=True, exist_ok=True)
                    for fname, content in all_files.items():
                        (files_dir / fname).write_text(content)
                    # Save the full agent conversation thread
                    (iter_dir / "conversation.json").write_text(
                        json.dumps(_serialize_messages(conversation), indent=2)
                    )

                # Verify
                verifier_result = await run_verifier(
                    self._client, spec, all_files, emit
                )

                if dump_dir:
                    iter_dir = dump_dir / f"iteration_{iteration}"
                    (iter_dir / "verifier.json").write_text(
                        verifier_result.model_dump_json(indent=2)
                    )

                # If no critical errors, break early
                if not verifier_result.has_critical_errors:
                    break

                # Collect flagged files for targeted fix
                flagged_filenames = {
                    e.file_path
                    for e in verifier_result.errors
                    if e.severity == "critical"
                }
                errors_by_file: dict[str, list[str]] = {}
                for err in verifier_result.errors:
                    if err.severity == "critical":
                        errors_by_file.setdefault(err.file_path, []).append(
                            err.description
                        )

                flagged_contents = {
                    f: all_files[f] for f in flagged_filenames if f in all_files
                }

                fix_ctx = _build_fix_context(spec, flagged_contents, errors_by_file)

            # Expand simplified input map to full Godot Object() format
            if "project.godot" in all_files:
                all_files["project.godot"] = expand_input_map(all_files["project.godot"])
                (project_dir / "project.godot").write_text(all_files["project.godot"])

            # Stage 3: Export
            result = await run_exporter(
                game_dir,
                all_files,
                [],  # controls=[] for agentic pipeline
                emit,
            )

            await emit(
                ProgressEvent(
                    type="done",
                    message="Your game is ready.",
                    data={
                        "job_id": result.job_id,
                        "wasm_path": result.wasm_path,
                        "controls": result.controls,
                    },
                )
            )
            await emit(None)  # type: ignore[arg-type]  # sentinel
            return result

        except Exception as e:
            await emit(ProgressEvent(type="error", message=str(e)))
            await emit(None)  # type: ignore[arg-type]
            raise
