"""Code Generator stage — produces GDScript files from a GameDesign."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.pipelines.assets import CONTROL_SNIPPET_PATHS, INPUT_ACTIONS
from backend.pipelines.multi_stage.models import ControlScheme, GameDesign

SONNET_MODEL = "claude-sonnet-4-6"
OPUS_MODEL = "claude-opus-4-6"

_REPO_ROOT = Path(
    __file__
).parent.parent.parent.parent.parent  # multi_stage -> pipelines -> backend -> backend -> repo root

_CODEGEN_SYSTEM_PROMPT = """\
You are a Godot 4 game programmer. Given a GameDesign JSON specification, generate \
the complete set of GDScript and .tscn files needed to implement the game.

CRITICAL — You MUST use Godot 4 GDScript syntax. FORBIDDEN patterns:
- `True` / `False` → use `true` / `false`
- `None` → use `null`
- `self.variable` for member variables → just use `variable` (no self prefix)
- `Input.is_key_pressed(KEY_X)` → use `Input.is_action_pressed("action_name")`

The ONLY valid input action names are:
  move_left, move_right, move_up, move_down, jump, shoot, interact, pause

Each script MUST extend an appropriate Godot node type (Node2D, CharacterBody2D, \
Area2D, RigidBody2D, Control, etc.).

VISUALS — There are NO image/texture assets available. You MUST draw all visuals \
programmatically using _draw() overrides. Examples:
- Rectangles: draw_rect(Rect2(-w/2, -h/2, w, h), Color.WHITE)
- Circles: draw_circle(Vector2.ZERO, radius, Color.WHITE)
- Lines: draw_line(from, to, Color.WHITE, width)
For CollisionShape2D nodes, assign shapes in _ready() programmatically:
  var shape = RectangleShape2D.new()
  shape.size = Vector2(w, h)
  $CollisionShape2D.shape = shape
Do NOT reference any texture files or image resources. Use Color constants for all visuals.

SCENE FILES — You MUST generate .tscn scene files alongside .gd scripts:
- You MUST generate a "Main.tscn" that replaces the template's empty scene. It must \
attach "res://main.gd" as the root node's script and wire all child nodes that \
main.gd references via @onready vars (e.g. $Player, $HUD/ScoreLabel, $Timer).
- For every preload("res://foo.tscn") in any script, you MUST generate "foo.tscn".
- .tscn files use Godot text scene format. Example:
  [gd_scene load_steps=2 format=3]
  [ext_resource type="Script" path="res://main.gd" id="1"]
  [node name="Main" type="Node2D"]
  script = ExtResource("1")
  [node name="Player" type="CharacterBody2D" parent="."]
- All ext_resource paths use res:// (project root). Files are placed at project root.
- Every node referenced by $NodePath in a script MUST exist in the corresponding .tscn.
- Node names MUST be unique among siblings in a .tscn file. Duplicate names cause \
$NodePath resolution to be ambiguous and break @onready references.

SCENE NAVIGATION — The template sets Main.tscn as the entry scene. Follow these rules:
- Use `get_tree().change_scene_to_file("res://SceneName.tscn")` for ALL scene transitions. \
NEVER use `load().instantiate()` + `add_child()` / `remove_child()` for scene switching — \
mixing these patterns causes crashes.
- `_ready()` fires EVERY TIME a node enters the scene tree, including when navigating \
back to a scene via change_scene_to_file. If main.gd._ready() redirects to a menu, \
the game will enter an infinite loop when the menu navigates back to Main.tscn.
- For multi-scene games (menu → gameplay → game over), use the GameManager autoload \
(already available globally) to track state. Set `GameManager.state` before transitioning \
and check it in `_ready()` to decide behavior. Example pattern:
  # main.gd
  func _ready():
      if GameManager.state == GameManager.GameState.PLAYING:
          _start_gameplay()
      else:
          get_tree().change_scene_to_file("res://Menu.tscn")
  # menu.gd
  func _start_game():
      GameManager.set_state(GameManager.GameState.PLAYING)
      get_tree().change_scene_to_file("res://Main.tscn")

Respond ONLY with a JSON object where keys are filenames (e.g. "main.gd", \
"Main.tscn", "player.gd", "player.tscn") and values are the full source for that file.

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
        if not filename.endswith(".gd"):
            continue
        for line_num, line in enumerate(content.splitlines(), start=1):
            for pattern, message in checks:
                match = re.search(pattern, line)
                if match:
                    col = match.start()
                    before = line[:col]
                    single_q = before.count("'") - before.count("\\'")
                    double_q = before.count('"') - before.count('\\"')
                    if single_q % 2 == 0 and double_q % 2 == 0:
                        issues.append(f"  {filename}:{line_num}: {message}")

    if issues:
        return "GDScript syntax issues found:\n" + "\n".join(issues)
    return None


def _check_gdscript_structure(files: dict[str, str]) -> str | None:
    """Check GDScript files for structural errors (bad indentation, nested funcs).

    Returns error string if issues found, None if clean.
    """
    issues: list[str] = []

    for filename, content in files.items():
        if not filename.endswith(".gd"):
            continue
        lines = content.splitlines()
        in_func = False
        for line_num, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            indent = len(line) - len(stripped)

            # func/class declarations must be at column 0
            if stripped.startswith("func ") or stripped.startswith("static func "):
                if indent > 0 and in_func:
                    issues.append(
                        f"  {filename}:{line_num}: `{stripped.split('(')[0]}` is indented "
                        f"inside another function — nested functions are not valid GDScript"
                    )

            if line.startswith("func "):
                in_func = True
            elif line and not line[0].isspace() and not stripped.startswith("#"):
                # Top-level non-func line resets context
                if (
                    stripped.startswith("var ")
                    or stripped.startswith("const ")
                    or stripped.startswith("@")
                    or stripped.startswith("class ")
                    or stripped.startswith("enum ")
                    or stripped.startswith("signal ")
                ):
                    in_func = False

    if issues:
        return "GDScript structure errors:\n" + "\n".join(issues)
    return None


def _check_scene_integrity(files: dict[str, str]) -> str | None:
    """Check .tscn files for broken references and structural issues.

    Validates:
    - Exactly one Main.tscn exists
    - All ext_resource script paths reference generated files
    - All preload("res://X.tscn") in scripts have a matching .tscn file
    """
    issues: list[str] = []
    generated_names = set(files.keys())

    # Check: exactly one Main.tscn
    main_tscns = [f for f in generated_names if f.lower() == "main.tscn"]
    if len(main_tscns) == 0:
        issues.append("  Missing Main.tscn — the entry scene must be generated")
    elif len(main_tscns) > 1:
        issues.append(
            f"  Multiple Main.tscn variants: {main_tscns} — generate exactly one"
        )

    for filename, content in files.items():
        if filename.endswith(".tscn"):
            # Check ext_resource paths point to generated files
            for match in re.finditer(r'path="res://([^"]+)"', content):
                ref_path = match.group(1)
                if ref_path.startswith("assets/"):
                    continue  # template assets are fine
                if ref_path not in generated_names:
                    issues.append(
                        f"  {filename}: ext_resource references res://{ref_path} "
                        f"but that file was not generated"
                    )

            # Check for duplicate sibling node names
            # Build map of parent -> list of child names
            children_by_parent: dict[str, list[str]] = {}
            for node_match in re.finditer(
                r'\[node\s+name="([^"]+)"(?:\s+type="[^"]+")?\s*(?:parent="([^"]*)")?\s*\]',
                content,
            ):
                node_name = node_match.group(1)
                parent = (
                    node_match.group(2)
                    if node_match.group(2) is not None
                    else "__root__"
                )
                children_by_parent.setdefault(parent, []).append(node_name)
            for parent, names in children_by_parent.items():
                seen: set[str] = set()
                for name in names:
                    if name in seen:
                        issues.append(
                            f'  {filename}: duplicate node name "{name}" under '
                            f'parent "{parent}" — $NodePath will be ambiguous'
                        )
                    seen.add(name)

        elif filename.endswith(".gd"):
            # Check preload("res://X.tscn") references
            for match in re.finditer(r'preload\("res://([^"]+\.tscn)"\)', content):
                ref_tscn = match.group(1)
                if ref_tscn not in generated_names:
                    issues.append(
                        f'  {filename}: preload("res://{ref_tscn}") '
                        f"but {ref_tscn} was not generated"
                    )

    if issues:
        return "Scene integrity errors:\n" + "\n".join(issues)
    return None


def validate_generated_files(files: dict[str, str]) -> dict[str, list[str]]:
    """Run all validators on generated files.

    Returns a dict mapping filename to list of errors. Empty dict = all clean.
    """
    per_file_errors: dict[str, list[str]] = {}

    # Collect all errors, then attribute to files
    syntax_err = _check_gdscript_syntax_patterns(files)
    structure_err = _check_gdscript_structure(files)
    scene_err = _check_scene_integrity(files)

    for err_str in [syntax_err, structure_err, scene_err]:
        if err_str is None:
            continue
        for line in err_str.splitlines()[1:]:  # skip header
            line = line.strip()
            if ":" in line:
                # Parse "filename:line: message" or "filename: message"
                fname = line.split(":")[0].strip()
                if fname in files:
                    per_file_errors.setdefault(fname, []).append(line)
                else:
                    # Global error (e.g. "Missing Main.tscn")
                    per_file_errors.setdefault("__global__", []).append(line)
            else:
                per_file_errors.setdefault("__global__", []).append(line)

    return per_file_errors


_REPAIR_SYSTEM_PROMPT = """\
You are a Godot 4 code repair tool. You will be given a file with errors and must \
return ONLY the corrected file content. Do not include any explanation, markdown, \
or code fences — return the raw file content only.

Rules:
- Fix ONLY the reported errors. Do not change anything else.
- `func` declarations must be at column 0 (top-level), never indented inside another func.
- Use Godot 4 syntax: true/false/null, not True/False/None.
- ext_resource paths in .tscn files must match files that exist in the project.
- All preload("res://X.tscn") must reference .tscn files that exist.
- Do NOT add markdown code fences to your response.\
"""


async def _repair_file(
    client: AsyncAnthropic,
    filename: str,
    content: str,
    errors: list[str],
    all_filenames: list[str],
) -> str:
    """Ask the LLM to fix a single file given specific errors."""
    error_text = "\n".join(errors)
    user_msg = (
        f"File: {filename}\n"
        f"All files in project: {', '.join(sorted(all_filenames))}\n\n"
        f"Errors:\n{error_text}\n\n"
        f"Current content:\n{content}"
    )

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=8192,
        system=_REPAIR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
        stream=True,
    )

    collected_text = []
    async for event in response:
        if event.type == "content_block_delta" and hasattr(event.delta, "text"):
            collected_text.append(event.delta.text)
    raw = "".join(collected_text).strip()
    # Strip code fences if LLM wraps anyway
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return raw


MAX_REPAIR_ROUNDS = 2


async def run_code_generator(
    client: AsyncAnthropic,
    game_design: GameDesign,
    emit: EmitFn,
    previous_error: str | None = None,
) -> dict[str, str]:
    """Generate GDScript files from a GameDesign via LLM.

    After initial generation, runs validators and repairs individual files
    up to MAX_REPAIR_ROUNDS times.
    """
    # Only emit stage_start on the first attempt (not retries)
    if previous_error is None:
        await emit(ProgressEvent(type="stage_start", message="Writing game code..."))

    user_message = _build_codegen_prompt(game_design, previous_error)

    # Attempt generation with retry on JSON parse failure
    files: dict[str, str] | None = None
    for attempt in range(3):
        response = await client.messages.create(
            model=SONNET_MODEL,
            max_tokens=32768,
            system=_CODEGEN_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            stream=True,
        )

        # Collect streamed response
        collected_text = []
        stop_reason = None
        async for event in response:
            if event.type == "content_block_delta" and hasattr(event.delta, "text"):
                collected_text.append(event.delta.text)
            elif event.type == "message_delta" and hasattr(event.delta, "stop_reason"):
                stop_reason = event.delta.stop_reason
        raw = "".join(collected_text).strip()

        # Extract JSON from markdown fences or preamble text.
        # The LLM sometimes adds explanatory text before/after the JSON block.
        fence_match = re.search(r"```(?:json)?\s*\n(\{.*)\n\s*```", raw, re.DOTALL)
        if fence_match:
            raw = fence_match.group(1).strip()
        elif raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```\s*$", "", raw)

        # Find the first '{' and extract the top-level JSON object via brace matching.
        # Handles preamble text before and trailing text after the JSON.
        json_start = raw.find("{")
        if json_start >= 0:
            depth = 0
            for i, ch in enumerate(raw[json_start:], start=json_start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        raw = raw[json_start : i + 1]
                        break

        try:
            files = json.loads(raw)
            break
        except json.JSONDecodeError as exc:
            logger.error(
                "Code generator JSON parse failed (attempt %d/3): %s\n"
                "stop_reason=%s, raw length=%d, first 500 chars:\n%s",
                attempt + 1,
                exc,
                stop_reason,
                len(raw),
                raw[:500],
            )
            if attempt < 2:
                await emit(
                    ProgressEvent(
                        type="stage_start",
                        message=f"Retrying code generation (parse error, attempt {attempt + 2}/3)...",
                    )
                )
            else:
                raise

    assert files is not None

    # Validate and repair loop
    for round_num in range(MAX_REPAIR_ROUNDS):
        file_errors = validate_generated_files(files)
        if not file_errors:
            break

        error_summary = []
        for fname, errs in file_errors.items():
            error_summary.extend(errs)

        await emit(
            ProgressEvent(
                type="stage_start",
                message=f"Fixing {len(file_errors)} file(s) (round {round_num + 1})...",
            )
        )

        all_filenames = list(files.keys())
        for fname, errs in file_errors.items():
            if fname == "__global__":
                # Global errors (e.g. missing Main.tscn) can't be repaired per-file.
                # They require a full regeneration — handled by the pipeline's
                # outer retry loop.
                continue
            if fname not in files:
                continue
            files[fname] = await _repair_file(
                client, fname, files[fname], errs, all_filenames
            )

    return files
