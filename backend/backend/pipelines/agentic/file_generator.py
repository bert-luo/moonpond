"""File Generator — tool definitions and dispatch for the agentic pipeline.

Defines the write_file and read_file tools that the LLM agent calls via
the Anthropic tool_use API, plus the dispatch function that executes them.

The multi-turn file generation loop (run_file_generation) will be implemented
in a later plan once the pipeline orchestrator is in place.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions (Anthropic tool_use API format)
# ---------------------------------------------------------------------------

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": (
        "Write a complete file to the game project. "
        "Call this exactly once per turn with one complete file. "
        "filename must be a bare filename (e.g. 'player.gd', 'Main.tscn') "
        "with no directory prefix."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Filename only, no path. E.g. 'player.gd' or 'Main.tscn'.",
            },
            "content": {
                "type": "string",
                "description": "Complete file content as a string.",
            },
        },
        "required": ["filename", "content"],
    },
}

READ_FILE_TOOL = {
    "name": "read_file",
    "description": (
        "Read the current content of a file already written to the game project. "
        "Use this to inspect previously written files before "
        "generating a file that depends on them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Filename to read (bare filename, no path).",
            },
        },
        "required": ["filename"],
    },
}

AGENT_TOOLS = [WRITE_FILE_TOOL, READ_FILE_TOOL]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GENERATOR_MODEL = "claude-sonnet-4-6"
MAX_TURNS_PER_ITERATION = 30

# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


async def _dispatch_tool(
    tool_name: str,
    tool_input: dict,
    game_dir: Path,
    generated_files: dict[str, str],
) -> str:
    """Execute a tool call and return the result string for tool_result.

    Args:
        tool_name: Name of the tool to execute.
        tool_input: Input dict from the LLM tool call.
        game_dir: Path to the game project directory.
        generated_files: Mutable dict tracking filename -> content for all
            files written during this generation iteration.

    Returns:
        A string result to send back as tool_result content.
    """
    if tool_name == "write_file":
        filename = tool_input["filename"]
        content = tool_input["content"]
        try:
            (game_dir / filename).write_text(content)
            generated_files[filename] = content
            return f"OK: wrote {filename} ({len(content)} chars)"
        except Exception as e:
            logger.error("write_file failed for %s: %s", filename, e)
            return f"ERROR: {e}"

    elif tool_name == "read_file":
        filename = tool_input["filename"]
        if filename in generated_files:
            return generated_files[filename]
        path = game_dir / filename
        if path.exists():
            return path.read_text()
        return f"ERROR: file not found: {filename}"

    else:
        return f"ERROR: unknown tool {tool_name}"
