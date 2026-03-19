# Phase 08: Agentic Template Decoupling - Research

**Researched:** 2026-03-19
**Domain:** Godot 4 project.godot format, agentic pipeline prompt engineering, Python string processing
**Confidence:** HIGH

## Summary

The agentic pipeline has a systematic configuration mismatch: the LLM generates code that references `GameManager` as a global autoload singleton, but the template's `project.godot` registers a _different_ `game_manager.gd` (the template's palette/state manager, not the LLM's version). The fix is surgical: strip two template files that the agentic pipeline always overwrites anyway, let the LLM generate `project.godot` itself (with guarded skeleton for the WASM-required sections), and add a Python post-processor for the verbose `Object(InputEventKey, ...)` serialization format.

The three other pipelines (contract, general, multi_stage) all overwrite `game_manager.gd` and `Main.tscn` from the template already — removing them from the template is a verified no-op for those pipelines.

**Primary recommendation:** Remove `game_manager.gd` and `Main.tscn` from `godot/templates/base_2d/`, update `GENERATOR_SYSTEM_PROMPT` to remove the "do not generate project.godot" prohibition and inject a partial skeleton, add `input_map.py` for key expansion, and call `expand_input_map()` in the pipeline before export.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Strip from template:**
- `game_manager.gd` + `.uid` — LLM always generates its own game manager
- `Main.tscn` — LLM always generates its own main scene

**Keep in template:**
- `export_presets.cfg` — WASM export boilerplate, not game-specific
- `.godot/` — engine import cache
- `assets/` — pre-built shaders, palettes, particles, control snippets
- `default_bus_layout.tres` — audio bus defaults
- `project.godot` — kept as a fallback skeleton (LLM's version overwrites it)

**project.godot approach:**
- Remove "Do NOT generate project.godot" rule from file generator system prompt
- Inject `project.godot` skeleton with pre-filled `[rendering]` and `[display]` sections
- LLM fills in `[application]`, `[autoload]`, and `[input]` sections
- Simplified input format: LLM writes `move_left=arrow_left`, Python post-processor expands to full `Object(InputEventKey, ...)` format
- Python utility `expand_input_map()` in new `backend/backend/pipelines/agentic/input_map.py`

**Asset surfacing:**
- Add shader paths, palette paths, particle paths, and control snippet paths to file generator system prompt
- Import from existing `backend/backend/pipelines/assets.py` (no changes to assets.py required)

**Exporter integration:**
- Run `expand_input_map()` on the generated `project.godot` in `pipeline.py` before passing to exporter
- Exporter's `dirs_exist_ok=True` `shutil.copytree` already means LLM's `project.godot` overwrites the template's

**Out of scope:**
- Changing the contract/general/multi_stage pipelines' prompt structure
- Adding new asset types to the template
- Modifying the verifier to understand project.godot
- Custom export presets per game

### Claude's Discretion

No explicit discretion areas defined — CONTEXT.md is prescriptive throughout.

### Deferred Ideas (OUT OF SCOPE)

- Changing contract/general/multi_stage pipeline prompt structure
- New asset types in the template
- Verifier changes for project.godot awareness
- Custom export presets per game
</user_constraints>

<phase_requirements>
## Phase Requirements

Phase 08 does not have formally assigned requirement IDs in REQUIREMENTS.md (the phase was added to the roadmap after the initial requirements definition). The work addresses the agentic pipeline quality gap described in CONTEXT.md.

| ID | Description | Research Support |
|----|-------------|-----------------|
| TMPL-SLIM | Remove game_manager.gd and Main.tscn from base_2d template | Verified: contract/multi_stage/general all overwrite these; agentic never uses them |
| AGENT-PROJGODOT | LLM generates project.godot with correct autoloads/input | Verified: current prohibition is the root cause of the runtime crash loop |
| AGENT-INPUTMAP | Python expand_input_map() converts simplified key names to Godot format | Verified: full Object() serialization is ~5 lines per action, LLM-hostile |
| AGENT-ASSETS | Surface asset paths in file generator system prompt | Verified: assets.py already has all constants, just needs import |
</phase_requirements>

## Standard Stack

### Core

| Library / File | Version | Purpose | Why Standard |
|----------------|---------|---------|--------------|
| Python `re` module | stdlib | Regex-based section parsing of project.godot INI format | Already used in wiring_generator.py for same pattern |
| `pathlib.Path` | stdlib | File I/O for project.godot read/write | Project-standard pattern across all pipeline files |
| `pydantic` | ~2.x | Already used — no new models needed for this phase | Project-wide model validation pattern |
| Anthropic SDK (`AsyncAnthropic`) | already installed | LLM calls — file_generator.py already wired | No changes to client setup |

### Supporting

| Library / File | Version | Purpose | When to Use |
|----------------|---------|---------|-------------|
| `backend.pipelines.assets` | local | Shader/palette/particle/control paths | Import in file_generator.py to build asset list for prompt |
| `godot/templates/base_2d/project.godot` | — | Physical keycode values for the input map | Source of truth for Godot 4.5 key constants |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python regex for project.godot parsing | Full INI parser (`configparser`) | configparser fails on Godot's `Object(...)` values and multi-line event dicts — regex is the established project pattern (wiring_generator.py uses it already) |
| Simplified key names in prompt | Full Object() serialization by LLM | LLM produces ~5 lines per action with 15+ fields each; error rate is high; the project explicitly decided against this in CONTEXT.md |

**Installation:** No new packages required. All dependencies already in the project.

## Architecture Patterns

### Files Changed or Created

```
backend/backend/pipelines/agentic/
├── file_generator.py     # MODIFY: update GENERATOR_SYSTEM_PROMPT
├── input_map.py          # NEW: expand_input_map() utility
└── pipeline.py           # MODIFY: call expand_input_map() before export

godot/templates/base_2d/
├── game_manager.gd       # DELETE
├── game_manager.gd.uid   # DELETE
└── Main.tscn             # DELETE
```

### Pattern 1: project.godot Skeleton Injection

**What:** The file generator system prompt includes a partial `project.godot` skeleton with the `[rendering]` and `[display]` sections pre-filled. The LLM must include these verbatim and fill in the game-specific sections.

**When to use:** Always — these sections are required for WASM export correctness.

**Skeleton to inject in GENERATOR_SYSTEM_PROMPT:**

```
When generating project.godot, ALWAYS include these sections verbatim:

[rendering]
renderer/rendering_method="gl_compatibility"
renderer/rendering_method.mobile="gl_compatibility"

[display]
window/size/viewport_width=1152
window/size/viewport_height=648
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"

For [autoload], list every singleton script you generate, e.g.:
[autoload]
GameManager="*res://game_manager.gd"

For [input], use simplified format — one action per line:
[input]
move_left=arrow_left
move_right=arrow_right
jump=space
shoot=z
(Supported keys: arrow_left, arrow_right, arrow_up, arrow_down,
 space, enter, escape, shift, ctrl, a-z, 0-9, f1-f12)
```

**Why pre-filled:** The `gl_compatibility` renderer and 1152x648 viewport are required for the WASM export preset. If the LLM uses `forward_plus` or wrong dimensions, export will produce a broken game. Locking these in the prompt prevents silent misconfiguration.

### Pattern 2: Input Map Expansion — expand_input_map()

**What:** Post-processor that reads a generated `project.godot`, finds the `[input]` section, and expands simplified key notation to full Godot `Object(InputEventKey, ...)` format.

**When to use:** Called in `pipeline.py` immediately after the file generation loop, before `run_exporter()`. Only applied if `project.godot` is in the generated files.

**Physical keycode mapping** (from existing template project.godot):

```python
KEY_MAP: dict[str, int] = {
    # Arrow keys
    "arrow_left":  4194319,
    "arrow_right": 4194321,
    "arrow_up":    4194320,
    "arrow_down":  4194322,
    # Common keys
    "space":       32,
    "enter":       4194309,
    "escape":      4194305,
    "shift":       4194325,
    "ctrl":        4194326,
    "tab":         4194308,
    "backspace":   4194310,
    # Letters (lowercase ASCII values)
    "a": 65, "b": 66, "c": 67, "d": 68, "e": 69,
    "f": 70, "g": 71, "h": 72, "i": 73, "j": 74,
    "k": 75, "l": 76, "m": 77, "n": 78, "o": 79,
    "p": 80, "q": 81, "r": 82, "s": 83, "t": 84,
    "u": 85, "v": 86, "w": 87, "x": 88, "y": 89,
    "z": 90,
    # Digits
    "0": 48, "1": 49, "2": 50, "3": 51, "4": 52,
    "5": 53, "6": 54, "7": 55, "8": 56, "9": 57,
    # F-keys
    "f1": 4194332, "f2": 4194333, "f3": 4194334,
    "f4": 4194335, "f5": 4194336, "f6": 4194337,
    "f7": 4194338, "f8": 4194339, "f9": 4194340,
    "f10": 4194341, "f11": 4194342, "f12": 4194343,
}
```

**Physical keycode values confirmed** from `/godot/templates/base_2d/project.godot`:
- `arrow_left` = 4194319, `arrow_right` = 4194321, `arrow_up` = 4194320, `arrow_down` = 4194322
- `space` = 32, `escape` = 4194305, `z` = 90, `e` = 69

**Object() serialization template** (from existing project.godot — verified format):

```
{key_name}={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":{keycode},"key_label":0,"unicode":0,"echo":false,"script":null)]
}
```

**Parsing strategy:** Use regex to find the `[input]` section boundary, then for each line matching `key_name=key_label` (no braces), replace with the full Object() block. Lines that already contain `Object(` or `{` are left untouched (graceful passthrough if LLM already used full format).

### Pattern 3: Asset Path Surfacing

**What:** Import `SHADER_PATHS`, `PALETTE_PATHS`, `PARTICLE_PATHS`, `CONTROL_SNIPPET_PATHS` from `backend.pipelines.assets` in `file_generator.py` and embed them in `GENERATOR_SYSTEM_PROMPT`.

**Format for prompt injection:**

```
AVAILABLE ASSETS (use these instead of generating placeholders):
Shaders (apply via ShaderMaterial):
  pixel_art: res://assets/shaders/pixel_art.gdshader
  glow: res://assets/shaders/glow.gdshader
  scanlines: res://assets/shaders/scanlines.gdshader
  chromatic_aberration: res://assets/shaders/chromatic_aberration.gdshader
  screen_distortion: res://assets/shaders/screen_distortion.gdshader

Palettes (Gradient resources, sample via GameManager.get_palette_color(t)):
  neon: res://assets/palettes/neon.tres
  retro: res://assets/palettes/retro.tres
  pastel: res://assets/palettes/pastel.tres
  monochrome: res://assets/palettes/monochrome.tres

Particles (preload and instance):
  explosion: res://assets/particles/explosion.tscn
  dust: res://assets/particles/dust.tscn
  sparkle: res://assets/particles/sparkle.tscn
  trail: res://assets/particles/trail.tscn

Control snippets (attach as script to any Node2D):
  mouse_follow: res://assets/control_snippets/mouse_follow.gd
  click_to_move: res://assets/control_snippets/click_to_move.gd
  drag: res://assets/control_snippets/drag.gd
  point_and_shoot: res://assets/control_snippets/point_and_shoot.gd
```

### Pattern 4: pipeline.py Integration Point

**What:** In `AgenticPipeline.generate()`, after the generate-verify-fix loop completes and `all_files` is finalized, check if `project.godot` is in `all_files` and run `expand_input_map()` on it before calling `run_exporter()`.

**Exact insertion point** — after line 222 (the `fix_ctx = _build_fix_context(...)` block) and before the "Stage 3: Export" comment:

```python
# Expand simplified input map to full Godot Object() format
if "project.godot" in all_files:
    from backend.pipelines.agentic.input_map import expand_input_map
    all_files["project.godot"] = expand_input_map(all_files["project.godot"])
    # Write expanded version back to disk
    (project_dir / "project.godot").write_text(all_files["project.godot"])
```

**Why write to disk:** The exporter calls `shutil.copytree(..., dirs_exist_ok=True)` then overwrites from `files` dict. If the expanded content is only in `all_files` (not on disk), the exporter's `for filename, content in files.items()` will write it correctly. Writing to disk here is a belt-and-suspenders measure for save_intermediate consistency.

### Anti-Patterns to Avoid

- **Parsing project.godot with configparser:** Godot's INI format uses `Object(...)` multi-line values that configparser cannot handle. Use regex section replacement (same pattern as `wiring_generator.py`).
- **Expecting LLM to generate complete Object() blocks:** The 15-field Object() format is LLM-hostile and produces silent mistakes. Always use the simplified key name format with Python expansion.
- **Removing export_presets.cfg from template:** The WASM export preset must exist before `godot --export-release` runs. This file is not game-specific and should stay in the template.
- **Stripping the fallback project.godot from template:** If the LLM forgets to generate project.godot, the template's version serves as a valid (if incorrect) fallback that still allows export to complete. This is better than no project.godot at all.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| project.godot section replacement | Custom INI parser | Regex (same pattern as `wiring_generator.py`) | Already proven in the codebase; configparser breaks on Godot's Object() values |
| Key name → physical keycode lookup | Dynamic lookup from Godot headers | Hardcoded dict in `input_map.py` | Godot physical keycodes are stable across 4.x versions; the template already shows the exact values |
| Asset path constants | Re-reading template directory at runtime | Import from `assets.py` | All constants already defined there, used by three other pipelines |

**Key insight:** The project.godot format is Godot-specific enough that general-purpose parsers fail. The regex replacement approach that already works in `wiring_generator.py` is the correct pattern to replicate.

## Common Pitfalls

### Pitfall 1: LLM Omits project.godot Entirely
**What goes wrong:** The LLM may not generate `project.godot` at all, especially if it sees the old "Do NOT generate project.godot" message cached in its patterns from this codebase.
**Why it happens:** The system prompt change only affects new calls; the LLM may pattern-match against the existing prohibition rule in its memory.
**How to avoid:** Make the instruction affirmative and explicit: "You MUST generate project.godot" (not just removing the prohibition). The pipeline's fallback (template's project.godot) means export still works, but with the old autoload collision.
**Warning signs:** `project.godot` absent from `all_files` after generation loop.

### Pitfall 2: LLM Uses Full Object() Format Already
**What goes wrong:** The LLM may generate the full `Object(InputEventKey, ...)` format rather than the simplified format — especially since it can read_file existing template files.
**Why it happens:** The LLM may `read_file` the template's project.godot (which has the full format) and copy it.
**How to avoid:** `expand_input_map()` must detect and passthrough already-expanded actions (lines containing `Object(`). This is the "graceful passthrough" requirement in Pattern 2.
**Warning signs:** Double-expanded `Object(Object(...))` in the final project.godot.

### Pitfall 3: Autoload Name Mismatch
**What goes wrong:** LLM generates `GameManager.gd` but registers it as `game_manager` in `[autoload]` (or vice versa), causing scripts using `GameManager.xxx` to fail.
**Why it happens:** The LLM may not consistently map autoload names to their registered singleton names.
**How to avoid:** The system prompt skeleton must explicitly show the convention: `AutoloadName="*res://script_file.gd"` where `AutoloadName` is the bare class name (PascalCase) used in GDScript.
**Warning signs:** Verifier flags "undefined identifier: GameManager" errors in iteration 1.

### Pitfall 4: [rendering] Section Missing or Wrong Renderer
**What goes wrong:** LLM generates project.godot without `[rendering]` or uses `forward_plus` renderer, producing a black screen on WASM export.
**Why it happens:** `gl_compatibility` is a WASM-specific requirement; LLMs default to `forward_plus` as the "standard" Godot renderer.
**How to avoid:** Instruct the LLM to include the rendering section verbatim — do not allow it to choose the renderer.
**Warning signs:** Export succeeds but WASM loads to a black screen.

### Pitfall 5: Template Removal Affects Other Pipelines
**What goes wrong:** Removing `game_manager.gd` and `Main.tscn` from the template breaks contract/multi_stage/general pipelines.
**Why it happens (won't happen):** Verified by reading all three pipelines — they all generate and overwrite these files before export. The exporter's `dirs_exist_ok=True` pattern means template files are the baseline, and generated files always overwrite.
**Confirmed safe** (HIGH confidence): contract pipeline generates `game_manager.gd` via `game_manager_generator.py` and `Main.tscn` via `SceneAssembler`; multi_stage pipeline generates `Main.tscn` via `node_generator.py`; general pipeline does the same.

## Code Examples

Verified patterns from existing codebase:

### Existing project.godot [input] Section Format (from project.godot)
```
; Source: godot/templates/base_2d/project.godot
move_left={
"deadzone": 0.5,
"events": [Object(InputEventKey,"resource_local_to_scene":false,"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,"pressed":false,"keycode":0,"physical_keycode":4194319,"key_label":0,"unicode":0,"echo":false,"script":null)]
}
```

### Existing Regex Section Replacement Pattern (from wiring_generator.py)
```python
# Source: backend/backend/pipelines/contract/wiring_generator.py
pattern = r"\[autoload\]\s*\n(?:.*\n)*?(?=\[|\Z)"
result = re.sub(pattern, new_autoload + "\n", template_content)
```

Use the same lookahead pattern `(?=\[|\Z)` for the `[input]` section replacement in `expand_input_map()`.

### expand_input_map() Skeleton
```python
# backend/backend/pipelines/agentic/input_map.py
import re

# Maps human-readable key names to Godot 4 physical_keycode values.
# Values confirmed from godot/templates/base_2d/project.godot.
KEY_MAP: dict[str, int] = {
    "arrow_left": 4194319,
    "arrow_right": 4194321,
    "arrow_up": 4194320,
    "arrow_down": 4194322,
    "space": 32,
    "enter": 4194309,
    "escape": 4194305,
    # ... (full mapping in implementation)
}

_EVENT_TEMPLATE = (
    '{action}={{\n'
    '"deadzone": 0.5,\n'
    '"events": [Object(InputEventKey,"resource_local_to_scene":false,'
    '"resource_name":"","device":-1,"window_id":0,"alt_pressed":false,'
    '"shift_pressed":false,"ctrl_pressed":false,"meta_pressed":false,'
    '"pressed":false,"keycode":0,"physical_keycode":{keycode},'
    '"key_label":0,"unicode":0,"echo":false,"script":null)]\n'
    '}}'
)

def expand_input_map(project_godot_content: str) -> str:
    """Expand simplified [input] actions to full Godot Object() format.

    Lines like `move_left=arrow_left` become the full Object(InputEventKey, ...)
    block. Lines already in full format (containing `Object(`) are passed through.
    Lines with unknown key names are left unchanged with a comment.
    """
    # Use same pattern as wiring_generator.py for section isolation
    ...
```

### Exporter Call Chain (from exporter.py — verified)
```python
# Source: backend/backend/pipelines/exporter.py
# Template copy then generated file overwrite — LLM's project.godot wins naturally
shutil.copytree(TEMPLATE_DIR, project_dir, dirs_exist_ok=True)
for filename, content in files.items():
    (project_dir / filename).write_text(content)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM forbidden from generating project.godot | LLM generates project.godot with skeleton guidance | Phase 08 | Eliminates autoload collision root cause |
| Template's game_manager.gd always present | game_manager.gd removed from template | Phase 08 | No more naming collision; clean slate for LLM |
| Agentic pipeline unaware of template assets | Asset paths injected into system prompt | Phase 08 | LLM can optionally use pre-built shaders/particles |
| LLM writes full Object() input serialization | Simplified key names + Python expansion | Phase 08 | Removes ~5-line-per-key error surface |

**Deprecated/outdated:**
- "Do NOT generate project.godot" instruction: replaced by explicit generation requirement with skeleton
- Template's `game_manager.gd` API (palette/state manager): LLM generates its own game manager per game

## Open Questions

1. **Should [input] section in project.godot skeleton always include the 8 standard template actions?**
   - What we know: The 8 standard actions (move_left, move_right, etc.) are the "contract" defined in Phase 01. Including them by default in the skeleton means games that use standard controls work without the LLM having to declare them.
   - What's unclear: If the LLM generates a game that needs different actions (e.g., a mouse-only game), having the standard 8 in the skeleton is harmless but slightly wasteful.
   - Recommendation: Include the 8 standard actions in the skeleton with simplified notation. The LLM can add its own custom actions. This matches Phase 01's "8 input actions as contract" decision.

2. **What happens when the LLM generates project.godot with both [autoload] AND references game_manager.gd (the deleted template file)?**
   - What we know: If the template's `game_manager.gd` is deleted and the LLM doesn't generate its own, any reference to `GameManager` autoload will fail at runtime.
   - What's unclear: Whether the verifier will catch "GameManager autoload registered but script file missing."
   - Recommendation: The system prompt should explicitly instruct the LLM that it MUST generate every script it registers as an autoload. The verifier already checks for "missing references" (error_type="missing") — it will likely catch this.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with anyio |
| Config file | `backend/pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/test_agentic_pipeline.py -x -q` |
| Full suite command | `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TMPL-SLIM | game_manager.gd and Main.tscn absent from template dir | unit | `pytest backend/tests/test_template_slim.py -x` | Wave 0 |
| AGENT-PROJGODOT | System prompt no longer contains "Do NOT generate project.godot" | unit | `pytest backend/tests/test_file_generator.py -x` | Wave 0 |
| AGENT-PROJGODOT | System prompt contains project.godot skeleton with [rendering] and [display] | unit | `pytest backend/tests/test_file_generator.py -x` | Wave 0 |
| AGENT-INPUTMAP | expand_input_map("move_left=arrow_left\n") produces Object(InputEventKey,...,physical_keycode:4194319,...) | unit | `pytest backend/tests/test_input_map.py -x` | Wave 0 |
| AGENT-INPUTMAP | Lines already containing Object( pass through unchanged | unit | `pytest backend/tests/test_input_map.py -x` | Wave 0 |
| AGENT-INPUTMAP | Unknown key names are left unchanged (no crash) | unit | `pytest backend/tests/test_input_map.py -x` | Wave 0 |
| AGENT-INPUTMAP | Full project.godot round-trip: [rendering] and [display] sections preserved after expansion | unit | `pytest backend/tests/test_input_map.py -x` | Wave 0 |
| AGENT-ASSETS | GENERATOR_SYSTEM_PROMPT contains SHADER_PATHS keys | unit | `pytest backend/tests/test_file_generator.py -x` | Wave 0 |
| PIPE-INPUTMAP | pipeline.py calls expand_input_map when project.godot in all_files | unit | `pytest backend/tests/test_agentic_pipeline.py -x` | ❌ add test |

### Sampling Rate
- **Per task commit:** `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/test_input_map.py backend/tests/test_file_generator.py -x -q`
- **Per wave merge:** `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/backend/tests/test_input_map.py` — covers AGENT-INPUTMAP (unit tests for expand_input_map)
- [ ] `backend/backend/tests/test_file_generator.py` — covers AGENT-PROJGODOT and AGENT-ASSETS (assert on GENERATOR_SYSTEM_PROMPT content)
- [ ] `backend/backend/tests/test_template_slim.py` — covers TMPL-SLIM (assert deleted files absent from template dir)

Note: `test_agentic_pipeline.py` already exists and should get one additional test for the input map expansion call in pipeline.py.

## Sources

### Primary (HIGH confidence)
- Direct file inspection: `backend/backend/pipelines/agentic/file_generator.py` — current GENERATOR_SYSTEM_PROMPT with "Do NOT generate project.godot" rule
- Direct file inspection: `backend/backend/pipelines/agentic/pipeline.py` — AgenticPipeline.generate() structure and insertion point
- Direct file inspection: `godot/templates/base_2d/project.godot` — exact Object(InputEventKey,...) format and physical_keycode values
- Direct file inspection: `backend/backend/pipelines/assets.py` — SHADER_PATHS, PALETTE_PATHS, PARTICLE_PATHS, CONTROL_SNIPPET_PATHS
- Direct file inspection: `backend/backend/pipelines/exporter.py` — `dirs_exist_ok=True` pattern confirming LLM overwrites template
- Direct file inspection: `backend/backend/pipelines/contract/wiring_generator.py` — `re.sub` section replacement pattern
- Direct file inspection: `.planning/phases/08-agentic-template-decoupling/CONTEXT.md` — all locked decisions

### Secondary (MEDIUM confidence)
- Direct file inspection: `backend/backend/tests/test_agentic_pipeline.py` — existing test structure and mock patterns to follow for new tests

### Tertiary (LOW confidence)
- None — all claims verified against project source files

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already in project, no new libraries
- Architecture: HIGH — based on direct code inspection of all affected files
- Pitfalls: HIGH — pitfall 5 (pipeline regression) verified by reading contract/multi_stage/general pipelines
- Input map keycode values: HIGH — extracted directly from template project.godot, not inferred

**Research date:** 2026-03-19
**Valid until:** Stable (template format and keycode values don't change within Godot 4.x)
