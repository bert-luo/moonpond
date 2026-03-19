"""Verifier Agent — independent LLM verification of generated game files.

Makes a fresh LLM call (not connected to the generator conversation) to audit
all generated files for a Godot 4 project and produces a structured error list.
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
You are a Godot 4 game project reviewer. Your job is to review all generated \
game files and identify errors that would prevent the game from running correctly.

Check for:
1. **GDScript syntax errors** — invalid syntax, missing colons, wrong indentation, \
Godot 3 syntax used instead of Godot 4 (e.g. .connect() string form instead of callable form).
2. **Missing references** — preload() paths pointing to files that don't exist, \
@onready var referencing node paths that don't exist in the scene tree, \
get_node() calls for missing nodes.
3. **Logic errors** — signals connected but never emitted, methods called but not \
defined, variables used before assignment, infinite loops.
4. **Missing files** — files referenced in code or scenes but not provided.

IMPORTANT: Only report errors you are confident about. A file that appears \
syntactically complete should not be flagged unless a specific reference is \
provably missing or a specific syntax rule is violated.

Severity levels:
- "critical" — will cause a crash, blank screen, or completely broken gameplay
- "warning" — may cause issues but the game could still partially function

Call the submit_verification tool with your findings. \
If no errors are found, call it with an empty errors list.\
"""

SUBMIT_VERIFICATION_TOOL = {
    "name": "submit_verification",
    "description": "Submit the verification results with any errors found.",
    "input_schema": {
        "type": "object",
        "properties": {
            "errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Filename that has the error.",
                        },
                        "error_type": {
                            "type": "string",
                            "enum": ["syntax", "reference", "logic", "missing"],
                            "description": "Category of error.",
                        },
                        "description": {
                            "type": "string",
                            "description": "Clear description of the error.",
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["critical", "warning"],
                            "description": "How severe the error is.",
                        },
                    },
                    "required": ["file_path", "error_type", "description", "severity"],
                },
            },
            "summary": {
                "type": "string",
                "description": "Brief human-readable summary of findings.",
            },
        },
        "required": ["errors", "summary"],
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
        f"Analyze all files and call submit_verification with any errors found."
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
    await emit(ProgressEvent(type="stage_start", message="Verifying generated files..."))

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

    error_count = len(result.errors)
    critical_count = sum(1 for e in result.errors if e.severity == "critical")
    await emit(ProgressEvent(
        type="stage_complete",
        message=f"Verification complete: {error_count} errors ({critical_count} critical)",
        data={"error_count": error_count, "critical_count": critical_count},
    ))

    return result
