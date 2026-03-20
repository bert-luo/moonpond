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
from backend.pipelines.agentic.image_gen_client import ImageGenClient, ImageGenError
from backend.pipelines.agentic.input_map import expand_input_map
from backend.pipelines.agentic.models import AgenticGameSpec, VerifierTask
from backend.pipelines.agentic.spec_generator import run_spec_generator
from backend.pipelines.agentic.tripo_client import TripoAssetGenerator, TripoError
from backend.pipelines.agentic.verifier import run_verifier
from backend.pipelines.base import EmitFn, GameResult, ProgressEvent, SoftTimeout
from backend.pipelines.exporter import GAMES_DIR, run_exporter

logger = __import__("logging").getLogger(__name__)

MAX_ITERATIONS = 4
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
    tasks: list[VerifierTask],
    all_files: dict[str, str],
) -> str:
    """Build a fix prompt from verifier tasks (edits and creates).

    Args:
        spec: The game specification.
        tasks: Filtered list of verifier tasks to address.
        all_files: All currently generated files (for edit context).

    Returns:
        A prompt string for the fix iteration.
    """
    edit_tasks = [t for t in tasks if t.action == "edit"]
    create_tasks = [t for t in tasks if t.action == "create"]

    sections = []

    # Edit section — show current file content + what to fix
    if edit_tasks:
        sections.append("## FILES TO EDIT\n")
        tasks_by_file: dict[str, list[str]] = {}
        for t in edit_tasks:
            tasks_by_file.setdefault(t.file, []).append(t.description)

        for filename, descs in tasks_by_file.items():
            content = all_files.get(filename, "(file not found)")
            task_text = "\n".join(f"  - {d}" for d in descs)
            sections.append(
                f"--- {filename} ---\n"
                f"Current content:\n{content}\n\n"
                f"Tasks:\n{task_text}\n"
                f"--- end {filename} ---"
            )

    # Create section — describe what new files are needed
    if create_tasks:
        sections.append("## FILES TO CREATE\n")
        for t in create_tasks:
            sections.append(
                f"- **{t.file}**: {t.description}"
            )

    body = "\n\n".join(sections)
    return (
        f"The verifier identified remaining work for this game. "
        f"Use write_file to fix existing files and create any new files.\n\n"
        f"Game: {spec.title} ({spec.genre})\n"
        f"Spec summary: {spec.scene_description}\n"
        f"Mechanics: {', '.join(spec.mechanics)}\n"
        f"Win: {spec.win_condition} | Fail: {spec.fail_condition}\n\n"
        f"{body}\n\n"
        f"Address all tasks above. Use write_file for each file (edited or new)."
    )


class AgenticPipeline:
    """Agent-loop pipeline satisfying the GamePipeline Protocol.

    Stages:
      1. Spec Generator  -- raw prompt -> AgenticGameSpec
      2. Generate-Verify-Fix loop (up to MAX_ITERATIONS)
      3. Exporter         -- assembled project -> WASM
    """

    def __init__(
        self,
        *,
        context_strategy: str = "full_history",
        thinking: bool = False,
    ) -> None:
        self._client = AsyncAnthropic()
        self._context_strategy = context_strategy
        self._thinking = thinking

    async def generate(
        self,
        prompt: str,
        job_id: str,
        emit: EmitFn,
        *,
        save_intermediate: bool = True,
        soft_timeout: SoftTimeout | None = None,
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

            # Initialize asset generators if API keys are available
            tripo: TripoAssetGenerator | None = None
            if spec.perspective == "3D":
                try:
                    tripo = TripoAssetGenerator()
                    logger.info("Tripo 3D asset generator initialized")
                except TripoError:
                    logger.info("TRIPO_API_KEY not set — 3D asset generation disabled")

            image_gen: ImageGenClient | None = None
            if spec.perspective == "2D":
                try:
                    image_gen = ImageGenClient()
                    logger.info("2D image generator initialized")
                except ImageGenError:
                    logger.info("OPENAI_API_KEY not set — 2D asset generation disabled")

            # Asset counter shared across iterations (mutable list)
            asset_counter: list[int] = [0]

            # Stage 2: Generate-Verify-Fix loop
            all_files: dict[str, str] = {}
            fix_ctx: str | None = None

            for iteration in range(1, MAX_ITERATIONS + 1):
                # Soft timeout: skip further fix iterations, go straight to export
                if iteration > 1 and soft_timeout and soft_timeout.is_expired:
                    await emit(
                        ProgressEvent(
                            type="stage_start",
                            message="Soft timeout reached — skipping fix iteration, proceeding to build...",
                        )
                    )
                    break

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
                    existing_files=all_files if fix_ctx else None,
                    tripo=tripo,
                    image_gen=image_gen,
                    asset_counter=asset_counter,
                    soft_timeout=soft_timeout,
                    thinking=self._thinking,
                )

                # Merge new/updated files into the running set
                all_files.update(new_files)

                # NOTE: No soft timeout check here — always run verification
                # after a generation iteration completes. Verification is a
                # single fast LLM call and ensures we know the final state.

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

                # Collect generated asset paths (2D sprites + 3D models)
                generated_assets: list[str] = []
                sprites_dir = project_dir / "assets" / "sprites"
                if sprites_dir.is_dir():
                    for p in sorted(sprites_dir.iterdir()):
                        if p.suffix in (".png", ".jpg", ".svg"):
                            generated_assets.append(f"res://assets/sprites/{p.name}")
                models_dir = project_dir / "assets" / "models"
                if models_dir.is_dir():
                    for p in sorted(models_dir.iterdir()):
                        if p.suffix in (".glb", ".gltf"):
                            generated_assets.append(f"res://assets/models/{p.name}")

                # Verify
                verifier_result = await run_verifier(
                    self._client, spec, all_files, emit,
                    generated_assets=generated_assets,
                )

                if dump_dir:
                    iter_dir = dump_dir / f"iteration_{iteration}"
                    (iter_dir / "verifier.json").write_text(
                        verifier_result.model_dump_json(indent=2)
                    )

                # If no critical tasks, break early
                if not verifier_result.has_critical_tasks:
                    break

                # Filter tasks to address — all criticals plus gameplay warnings
                _GAMEPLAY_KEYWORDS = {
                    "non-functional", "broken", "will not work",
                    "never called", "wrong position", "default position",
                    "patrol", "spawn", "missing",
                }

                def _should_fix(task):  # noqa: ANN001, ANN202
                    if task.severity == "critical":
                        return True
                    if task.severity == "warning":
                        desc_lower = task.description.lower()
                        return any(kw in desc_lower for kw in _GAMEPLAY_KEYWORDS)
                    return False

                tasks_to_fix = [t for t in verifier_result.tasks if _should_fix(t)]

                fix_ctx = _build_fix_context(spec, tasks_to_fix, all_files)

            # Expand simplified input map to full Godot Object() format
            if "project.godot" in all_files:
                all_files["project.godot"] = expand_input_map(
                    all_files["project.godot"]
                )
                (project_dir / "project.godot").write_text(all_files["project.godot"])

            # Stage 3: Export
            result = await run_exporter(
                game_dir,
                all_files,
                [c.model_dump() for c in spec.controls],
                emit,
                perspective=spec.perspective,
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
