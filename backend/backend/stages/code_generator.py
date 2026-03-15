"""Code Generator stage — produces GDScript files from a GameDesign."""

from __future__ import annotations

import json
import re
from pathlib import Path

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.stages.models import (
    CONTROL_SNIPPET_PATHS,
    INPUT_ACTIONS,
    ControlScheme,
    GameDesign,
)

SONNET_MODEL = "claude-sonnet-4-6"

_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # stages -> backend -> backend -> repo root

_CODEGEN_SYSTEM_PROMPT = """\
You are a Godot 4 game programmer. Given a GameDesign JSON specification, generate \
the complete set of GDScript files needed to implement the game.

CRITICAL — You MUST use Godot 4 GDScript syntax. FORBIDDEN patterns:
- `True` / `False` → use `true` / `false`
- `None` → use `null`
- `self.variable` for member variables → just use `variable` (no self prefix)
- `Input.is_key_pressed(KEY_X)` → use `Input.is_action_pressed("action_name")`

The ONLY valid input action names are:
  move_left, move_right, move_up, move_down, jump, shoot, interact, pause

Each script MUST extend an appropriate Godot node type (Node2D, CharacterBody2D, \
Area2D, RigidBody2D, Control, etc.).

Respond ONLY with a JSON object where keys are filenames (e.g. "main.gd", \
"player.gd") and values are the full GDScript source code for that file.

Do NOT include markdown code fences. Respond with raw JSON only.\
"""


def _build_codegen_prompt(
    game_design: GameDesign, previous_error: str | None = None
) -> str:
    """Build the user-facing prompt for the Code Generator LLM call."""
    parts: list[str] = []

    if previous_error is not None:
        parts.append(
            f"PREVIOUS ATTEMPT FAILED. Fix these errors:\n{previous_error}\n\n"
            "Generate corrected code:"
        )

    parts.append(f"GameDesign:\n{game_design.model_dump_json(indent=2)}")

    parts.append(f"\nValid input actions: {', '.join(INPUT_ACTIONS)}")

    # Inject control snippet source for non-WASD schemes
    if game_design.control_scheme != ControlScheme.WASD:
        scheme_name = game_design.control_scheme.value
        snippet_res_path = CONTROL_SNIPPET_PATHS.get(scheme_name)
        if snippet_res_path:
            # Read the actual GDScript file from the template directory on disk
            snippet_disk_path = (
                _REPO_ROOT
                / "godot"
                / "templates"
                / "base_2d"
                / "assets"
                / "control_snippets"
                / f"{scheme_name}.gd"
            )
            try:
                snippet_source = snippet_disk_path.read_text()
                parts.append(
                    f"\nControl scheme: {scheme_name}\n"
                    f"The following control snippet is available at {snippet_res_path}. "
                    "You MUST attach or integrate this script into the player node. "
                    "Here is the full source for reference:\n\n"
                    f"```gdscript\n{snippet_source}\n```"
                )
            except FileNotFoundError:
                parts.append(
                    f"\nControl scheme: {scheme_name} — "
                    f"snippet path {snippet_res_path} (integrate manually)"
                )

    return "\n\n".join(parts)


def _check_gdscript_syntax_patterns(files: dict[str, str]) -> str | None:
    """Check generated GDScript for common Python contamination patterns.

    Returns a human-readable error string if issues found, None if clean.
    """
    issues: list[str] = []

    # Patterns to detect — match standalone tokens, not inside strings
    checks = [
        (r"\bTrue\b", "Use `true` instead of `True` (Python syntax)"),
        (r"\bFalse\b", "Use `false` instead of `False` (Python syntax)"),
        (r"\bNone\b", "Use `null` instead of `None` (Python syntax)"),
        (
            r"Input\.is_key_pressed",
            'Use `Input.is_action_pressed("action_name")` instead of `Input.is_key_pressed`',
        ),
    ]

    for filename, content in files.items():
        for line_num, line in enumerate(content.splitlines(), start=1):
            # Skip lines that are inside string literals (rough heuristic:
            # ignore lines where the match is within quotes)
            for pattern, message in checks:
                match = re.search(pattern, line)
                if match:
                    # Basic check: if the match is inside a string literal, skip
                    col = match.start()
                    before = line[:col]
                    # Count unescaped quotes before match position
                    single_q = before.count("'") - before.count("\\'")
                    double_q = before.count('"') - before.count('\\"')
                    if single_q % 2 == 0 and double_q % 2 == 0:
                        issues.append(f"  {filename}:{line_num}: {message}")

    if issues:
        return "GDScript syntax issues found:\n" + "\n".join(issues)
    return None


async def run_code_generator(
    client: AsyncAnthropic,
    game_design: GameDesign,
    emit: EmitFn,
    previous_error: str | None = None,
) -> dict[str, str]:
    """Generate GDScript files from a GameDesign via LLM.

    Args:
        client: Anthropic async client.
        game_design: The game design specification.
        emit: Async callback for progress events.
        previous_error: If set, included in prompt for retry (suppresses
            duplicate stage_start event).

    Returns:
        Dict mapping filename to GDScript source code.
    """
    # Only emit stage_start on the first attempt (not retries)
    if previous_error is None:
        await emit(
            ProgressEvent(type="stage_start", message="Writing game code...")
        )

    user_message = _build_codegen_prompt(game_design, previous_error)

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=8192,
        system=_CODEGEN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:json)?\s*", "", raw)
    cleaned = cleaned.strip().rstrip("`")

    files: dict[str, str] = json.loads(cleaned)
    return files
