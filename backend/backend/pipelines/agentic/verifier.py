"""Verifier Agent — independent LLM verification of generated game files.

Makes a fresh LLM call (not connected to the generator conversation) to audit
all generated files for a Godot 4 project and produces a structured task list.
Uses tool_choice to force structured JSON output.
"""

from __future__ import annotations

import json
import logging

from anthropic import AsyncAnthropic

from backend.pipelines.agentic.models import AgenticGameSpec, VerifierResult
from backend.pipelines.base import EmitFn, ProgressEvent

logger = logging.getLogger(__name__)

VERIFIER_MODEL = "claude-sonnet-4-6"

VERIFIER_SYSTEM_PROMPT = """\
You are a Godot 4.5 game project reviewer. The target engine is Godot 4.5.1. \
Your job is to review all generated game files and produce a task list of \
remaining work needed to make the game correct and complete.

Each task is either:
- **edit** — an existing file needs to be modified to fix an error
- **create** — a new file needs to be added to implement missing functionality

CHECK FOR ERRORS IN EXISTING FILES (action: "edit"):
1. **GDScript syntax errors** — invalid syntax, missing colons, wrong indentation, \
Godot 3 syntax used instead of Godot 4 (e.g. .connect() string form instead of callable form). \
CRITICAL Godot 4.5 rule: using `:=` with any function that returns Variant is a PARSE ERROR. \
This includes load(), preload(), lerp(), ceil(), floor(), clamp(), randf(), randf_range(), \
randi_range(), abs(), min(), max(), snapped(), get_node(), and any custom method without \
an explicit return type annotation. Flag every `:=` used with these functions as a \
"critical" task. The fix is to use explicit typing (`var x: Type = ...`) or \
untyped (`var x = ...`).
2. **Missing references** — preload() paths pointing to files that don't exist, \
@onready var referencing node paths that don't exist in the scene tree, \
get_node() calls for missing nodes.
3. **Logic errors** — signals connected but never emitted, methods called but not \
defined, variables used before assignment, infinite loops.

CHECK FOR MISSING FUNCTIONALITY (action: "create"):
4. **Missing files** — files referenced in code or scenes but not provided.
5. **Missing gameplay features** — compare the file manifest against the game spec. \
If core gameplay functionality described in the spec (enemies, scoring, win/lose \
conditions, key mechanics) has no implementation in any existing file, emit a \
"create" task with a suggested filename and description of what the file should do.

IMPORTANT: Only report issues you are confident about. A file that appears \
syntactically complete should not be flagged unless a specific reference is \
provably missing or a specific syntax rule is violated. For "create" tasks, \
only flag functionality that is clearly described in the spec but entirely absent \
from the generated files.

Severity levels:
- "critical" — will cause a crash, blank screen, or completely broken gameplay
- "warning" — may cause issues but the game could still partially function

Call the submit_verification tool with your findings. \
If no issues are found, call it with an empty tasks list.\
"""

SUBMIT_VERIFICATION_TOOL = {
    "name": "submit_verification",
    "description": "Submit verification results as a task list of remaining work.",
    "input_schema": {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["edit", "create"],
                            "description": (
                                "'edit' if an existing file needs fixing, "
                                "'create' if a new file should be added."
                            ),
                        },
                        "file": {
                            "type": "string",
                            "description": (
                                "Filename to edit (must exist) or suggested "
                                "filename to create (e.g. 'enemy.gd')."
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": "What needs to be done — the fix or the new file's purpose.",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "warning"],
                            "description": "How severe the issue is.",
                        },
                    },
                    "required": ["action", "file", "description", "severity"],
                },
            },
            "summary": {
                "type": "string",
                "description": "Brief human-readable summary of findings.",
            },
        },
        "required": ["tasks", "summary"],
    },
}


def _build_verifier_prompt(spec: AgenticGameSpec, files: dict[str, str]) -> str:
    """Build the verifier prompt with spec summary and all file contents.

    Args:
        spec: The game specification that was implemented.
        files: Dict mapping filename -> content for all generated files.

    Returns:
        A prompt string with spec and all file contents embedded.
    """
    spec_summary = (
        f"Game: {spec.title} ({spec.genre})\n"
        f"Mechanics: {', '.join(spec.mechanics)}\n"
        f"Win: {spec.win_condition}\n"
        f"Fail: {spec.fail_condition}\n"
        f"Scene: {spec.scene_description}"
    )

    file_sections = []
    for filename, content in files.items():
        file_sections.append(f"--- {filename} ---\n{content}\n--- end {filename} ---")

    files_block = "\n\n".join(file_sections)

    return (
        f"Review the following Godot 4 game project files for errors.\n\n"
        f"Game Specification:\n{spec_summary}\n\n"
        f"Generated Files ({len(files)} total):\n\n{files_block}\n\n"
        f"Analyze all files against the spec. Call submit_verification with "
        f"tasks for any files that need editing or new files that should be created."
    )


async def run_verifier(
    client: AsyncAnthropic,
    spec: AgenticGameSpec,
    files: dict[str, str],
    emit: EmitFn,
) -> VerifierResult:
    """Run the verifier agent to audit generated game files.

    Makes an independent LLM call (fresh context) using tool_choice to force
    structured output via the submit_verification tool.

    Args:
        client: Anthropic async client.
        spec: The game specification that was implemented.
        files: Dict mapping filename -> content for all generated files.
        emit: Async callback for progress events.

    Returns:
        A validated VerifierResult with errors and summary.
    """
    await emit(
        ProgressEvent(type="stage_start", message="Verifying generated files...")
    )

    response = await client.messages.create(
        model=VERIFIER_MODEL,
        max_tokens=4096,
        system=VERIFIER_SYSTEM_PROMPT,
        tools=[SUBMIT_VERIFICATION_TOOL],
        tool_choice={"type": "tool", "name": "submit_verification"},
        messages=[{"role": "user", "content": _build_verifier_prompt(spec, files)}],
    )

    # Extract the tool call input — guaranteed by tool_choice
    tool_block = next(b for b in response.content if b.type == "tool_use")
    result = VerifierResult.model_validate(tool_block.input)

    task_count = len(result.tasks)
    critical_count = sum(1 for t in result.tasks if t.severity == "critical")
    edit_count = sum(1 for t in result.tasks if t.action == "edit")
    create_count = sum(1 for t in result.tasks if t.action == "create")
    await emit(
        ProgressEvent(
            type="stage_complete",
            message=(
                f"Verification complete: {task_count} tasks "
                f"({edit_count} edits, {create_count} creates, "
                f"{critical_count} critical)"
            ),
            data={
                "task_count": task_count,
                "critical_count": critical_count,
                "edit_count": edit_count,
                "create_count": create_count,
            },
        )
    )

    return result
