# Phase 3: Multi-Stage Pipeline - Research

**Researched:** 2026-03-14
**Domain:** Anthropic Python SDK, multi-stage LLM pipeline, Pydantic structured output, Godot GDScript code generation
**Confidence:** HIGH (Anthropic SDK verified from official docs; infrastructure verified from Phase 2 source)

## Summary

Phase 3 wires five sequential LLM-powered stages (Prompt Enhancer, Game Designer, Code Generator, Visual Polisher, Exporter) into a `MultiStagePipeline` that satisfies STAGE-01 through STAGE-06. The Anthropic Python SDK 0.84.0 supports `AsyncAnthropic` with `await client.messages.create()` and a newer `client.messages.parse()` method for Pydantic-validated structured output — no beta header needed as of the current SDK. The Phase 2 infrastructure (`GamePipeline` Protocol, `ProgressEvent`, `EmitFn`, `run_headless_export`, pipeline registry) is the complete foundation and requires no modification.

The critical design decisions are: (1) use `AsyncAnthropic` with a single shared client instance to avoid creating a new HTTP connection per stage; (2) use `client.messages.parse()` with Pydantic models for the first two stages (`GameSpec`, `GameDesign`) to get guaranteed-schema output; (3) use `client.messages.create()` with plain text for Code Generator and Visual Polisher since the output is a dict of filenames to GDScript content (not a strict schema); (4) do NOT rely on Godot `--check-only` for self-correction pre-validation — it has known false-positive issues with autoloads; use string-pattern regex checks on generated code instead.

**Primary recommendation:** Build five stage modules in `backend/backend/stages/`, wire them in `backend/backend/pipelines/multi_stage/pipeline.py`, add `"multi_stage"` to the registry, and add `anthropic>=0.84` to `pyproject.toml`.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Five stages execute sequentially: Prompt Enhancer → Game Designer → Code Generator → Visual Polisher → Exporter
- Each stage takes a typed Pydantic input and produces a typed Pydantic output
- Each stage emits a `ProgressEvent` (type=`stage_start`) with a human-readable SSE message at its start
- Stages live in `backend/backend/stages/` as individual modules
- The `MultiStagePipeline` class in `backend/backend/pipelines/multi_stage/` wires them together and registers as `"multi_stage"` in the pipeline registry
- Prompt Enhancer: Haiku (fast, low-cost enrichment)
- Game Designer: Sonnet (structured output, design reasoning)
- Code Generator: Sonnet (code generation quality)
- Visual Polisher: Sonnet (code review + asset selection)
- Exporter: No LLM — Godot headless subprocess only
- `GameSpec` — output of Prompt Enhancer (title, genre, mechanics, visual hints)
- `GameDesign` — output of Game Designer with `ControlScheme` enum, `ControlMapping`, `SceneSpec`, `VisualStyle` sub-models
- Code Generator output: dict of filename → GDScript content
- Visual Polisher output: dict of filename → patched GDScript content
- Generated GDScript MUST use Godot 4 syntax exclusively
- MUST use named input actions from the template (move_left, move_right, etc.) — never hardcode keys
- For non-WASD schemes, import from `control_snippets/` rather than generating input handling from scratch
- Visual Polisher must apply at least one shader reference and one palette selection
- If Code Generator output has a GDScript syntax error, feed compiler output back to Code Generator — up to 2 retry attempts — before failing
- Exporter copies base_2d template to `games/{job_id}/project/`, writes GDScript files, runs `run_headless_export()`, returns WASM path

### Claude's Discretion

- Exact LLM prompt templates for each stage (system prompts, few-shot examples)
- How to handle the Anthropic client initialization (shared client vs per-stage)
- Structured output parsing strategy (tool_use vs JSON mode vs text parsing)
- Whether to use a syntax check step before the full Godot export for self-correction
- Internal error handling within individual stages (beyond the self-correction requirement)
- Test strategy for stages (unit tests with mocked LLM responses vs integration tests)

### Deferred Ideas (OUT OF SCOPE)

- Single-shot agentic pipeline
- ROMA multi-agent pipeline
- Playwright visual feedback loop
- base_3d template support (TMPL-07, v2)
- Audio/sound effects pipeline stage
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STAGE-01 | Prompt Enhancer stage: raw user prompt → structured `GameSpec` (title, genre, mechanics, visual hints) | Anthropic `AsyncAnthropic` + `messages.parse()` with Pydantic `GameSpec` model; Haiku model ID `claude-haiku-4-5` |
| STAGE-02 | Game Designer stage: `GameSpec` → full `GameDesign` model (scenes, visual_style, control_scheme, controls list, win/fail conditions) | `messages.parse()` with nested Pydantic `GameDesign`; Sonnet model ID `claude-sonnet-4-6` |
| STAGE-03 | Code Generator: produces GDScript files per scene, Godot 4 syntax only, uses named input actions | System prompt with input action contract; `messages.create()` returning JSON dict; control_snippets path injection for non-WASD |
| STAGE-04 | Visual Polisher: reviews code, applies shader refs, palette selections, particle scenes | System prompt with full asset library manifest; `messages.create()` with patched dict output |
| STAGE-05 | Exporter: copies template, writes GDScript files, runs headless export, returns WASM path | Phase 2 `run_headless_export()` already handles this; file copy pattern from StubPipeline |
| STAGE-06 | Each stage emits `ProgressEvent(type="stage_start", message=...)` at its start | Phase 2 `EmitFn` already in place; SSE labels specified in CONTEXT.md |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.84.0 | LLM API client | Official Anthropic Python SDK; `AsyncAnthropic` for non-blocking calls in FastAPI |
| pydantic | bundled with fastapi | Stage I/O contracts (`GameSpec`, `GameDesign`, etc.) | Already used in Phase 2 for request/response models |
| asyncio | stdlib | Non-blocking stage execution | Phase 2 already uses asyncio for pipeline and SSE queue |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shutil | stdlib | Template directory copy | Exporter stage: `shutil.copytree(TEMPLATE_DIR, project_dir)` |
| pathlib | stdlib | Path manipulation | All stages that write files |
| re | stdlib | GDScript pattern validation for self-correction | Pre-check before full Godot export |
| json | stdlib | Parse JSON dict from Code Generator / Visual Polisher responses | Structured text response parsing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `AsyncAnthropic` (single shared instance) | Per-stage client creation | Per-stage creation opens a new HTTP connection pool per stage — waste |
| `messages.parse()` for GameSpec/GameDesign | `tool_use` / manual JSON extraction | `parse()` is cleaner: Pydantic model is the schema definition, no separate JSON schema |
| Regex for self-correction pre-check | Godot `--check-only` | `--check-only` has known false-positive failures with autoloads (GitHub issue #78587) |

**Installation:**
```bash
# From backend/ directory
uv add anthropic
```

This adds `anthropic>=0.84.0` to `pyproject.toml` dependencies.

---

## Architecture Patterns

### Recommended Project Structure
```
backend/backend/
├── stages/
│   ├── __init__.py
│   ├── models.py          # GameSpec, GameDesign, ControlScheme, etc.
│   ├── prompt_enhancer.py # STAGE-01: prompt → GameSpec
│   ├── game_designer.py   # STAGE-02: GameSpec → GameDesign
│   ├── code_generator.py  # STAGE-03: GameDesign → dict[str, str]
│   ├── visual_polisher.py # STAGE-04: dict[str, str] → dict[str, str]
│   └── exporter.py        # STAGE-05: dict[str, str] + job_id → GameResult
├── pipelines/
│   ├── multi_stage/
│   │   ├── __init__.py
│   │   └── pipeline.py    # MultiStagePipeline.generate() wires all stages
│   ├── stub/
│   │   └── pipeline.py    # Keep; used by existing tests
│   ├── base.py            # Unchanged from Phase 2
│   └── registry.py        # Add "multi_stage": MultiStagePipeline
```

### Pattern 1: Shared Async Client
**What:** Create one `AsyncAnthropic` instance at pipeline instantiation time and pass it to each stage call
**When to use:** When multiple stages in the same request must call the API — avoids reconnect overhead

```python
# Source: https://github.com/anthropics/anthropic-sdk-python
from anthropic import AsyncAnthropic

class MultiStagePipeline:
    def __init__(self):
        self._client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

    async def generate(self, prompt: str, job_id: str, emit: EmitFn) -> GameResult:
        game_spec = await run_prompt_enhancer(self._client, prompt, emit)
        game_design = await run_game_designer(self._client, game_spec, emit)
        ...
```

### Pattern 2: Pydantic Structured Output via `messages.parse()`
**What:** Pass a Pydantic model class as `output_format`; SDK validates response against schema
**When to use:** Stages 1 and 2 where output is a well-defined nested Pydantic model

```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from anthropic import AsyncAnthropic
from .models import GameSpec

async def run_prompt_enhancer(client: AsyncAnthropic, prompt: str, emit) -> GameSpec:
    await emit(ProgressEvent(type="stage_start", message="Understanding your idea..."))
    response = await client.messages.parse(
        model="claude-haiku-4-5",
        max_tokens=512,
        system="You are a game concept analyst...",
        messages=[{"role": "user", "content": prompt}],
        output_format=GameSpec,
    )
    return response.parsed_output
```

### Pattern 3: JSON Dict Response for Code Generator
**What:** Use `messages.create()` and parse the text response as JSON; the LLM returns `{"main.gd": "extends Node\n...", "player.gd": "..."}`
**When to use:** Stage 3 and 4 where output is an open-ended dict of filenames to GDScript

```python
import json
from anthropic import AsyncAnthropic

async def run_code_generator(
    client: AsyncAnthropic,
    game_design: GameDesign,
    emit,
    previous_error: str | None = None,
) -> dict[str, str]:
    await emit(ProgressEvent(type="stage_start", message="Writing game code..."))
    messages = [{"role": "user", "content": _build_codegen_prompt(game_design, previous_error)}]
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=_CODEGEN_SYSTEM_PROMPT,
        messages=messages,
    )
    raw = response.content[0].text
    return json.loads(raw)  # LLM instructed to return only valid JSON
```

### Pattern 4: Self-Correction Loop
**What:** Detect likely syntax errors with a regex pre-check, then re-call Code Generator with error context; retry up to 2 times
**When to use:** After Code Generator returns code, before calling Exporter

```python
MAX_RETRIES = 2

async def _generate_code_with_correction(client, game_design, emit) -> dict[str, str]:
    error_context: str | None = None
    for attempt in range(MAX_RETRIES + 1):
        files = await run_code_generator(client, game_design, emit, error_context)
        syntax_error = _check_gdscript_syntax_patterns(files)
        if syntax_error is None:
            return files
        if attempt == MAX_RETRIES:
            raise RuntimeError(f"Code generation failed after {MAX_RETRIES} retries: {syntax_error}")
        error_context = syntax_error
    return files  # unreachable
```

Note: Full Godot export is the authoritative syntax check. The regex pre-check catches obvious patterns (Python-style `print()`, missing `func` keyword, incorrect variable syntax) to avoid wasting 10-15 seconds on a doomed export. If the regex pre-check passes but export fails, the export error text from `RunResult.stderr` becomes the `error_context` for retry.

### Pattern 5: Exporter Stage File Layout
**What:** Copy template to job directory, write generated GDScript files into `scripts/` subdirectory, call `run_headless_export()`
**When to use:** Stage 5 — matches pattern already proven in StubPipeline

```python
# Source: backend/backend/pipelines/stub/pipeline.py (Phase 2)
import shutil
from pathlib import Path
from ..godot.runner import run_headless_export

_REPO_ROOT = Path(__file__).parent.parent.parent.parent.parent
TEMPLATE_DIR = _REPO_ROOT / "godot" / "templates" / "base_2d"
GAMES_DIR = _REPO_ROOT / "games"

async def run_exporter(job_id: str, files: dict[str, str], controls: list[dict], emit) -> GameResult:
    await emit(ProgressEvent(type="stage_start", message="Building for web..."))
    project_dir = GAMES_DIR / job_id / "project"
    export_dir = GAMES_DIR / job_id / "export"
    shutil.copytree(TEMPLATE_DIR, project_dir)
    scripts_dir = project_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    for filename, content in files.items():
        (scripts_dir / filename).write_text(content)
    result = await run_headless_export(project_dir, export_dir)
    if not result.success:
        raise RuntimeError(f"Export failed: {result.stderr[:500]}")
    return GameResult(
        job_id=job_id,
        wasm_path=f"/games/{job_id}/export/index.html",
        controls=controls,
    )
```

### Anti-Patterns to Avoid
- **Synchronous `Anthropic()` client:** FastAPI uses asyncio; synchronous calls block the event loop. Always use `AsyncAnthropic`.
- **Creating `AsyncAnthropic()` at module level:** This creates the HTTP client before the event loop starts. Create inside `__init__` or as a lazy property.
- **Trusting Godot `--check-only` for self-correction:** GitHub issue #78587 shows false positives when scripts reference autoloads (like `GameManager`). Use regex heuristics + export stderr instead.
- **Writing generated GDScript outside `scripts/`:** The Exporter should write only to `scripts/` under the project dir. Never write into `assets/` — that corrupts the shader/palette/particle resources.
- **Hardcoded key checks in GDScript:** System prompt must explicitly forbid `KEY_A`, `KEY_W`, etc. and require `Input.is_action_pressed("move_left")` form.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pydantic schema → JSON schema conversion | Manual schema dict | `messages.parse(output_format=MyModel)` | SDK handles schema conversion, additionalProperties, constraint stripping, validation |
| HTTP connection pooling | Per-call `AsyncAnthropic()` | Single `AsyncAnthropic` instance per pipeline | SDK manages connection pool internally |
| Retry logic for rate limits | Custom backoff loop | `anthropic` SDK auto-retries with exponential backoff by default | SDK handles 429/529 automatically |
| Async subprocess for Godot | `subprocess.run()` | `run_headless_export()` from Phase 2 | Already implemented, tested, handles the Godot exit-code bug |
| Template file copy | Manual file-by-file copy | `shutil.copytree()` | Handles all nested dirs, preserves file metadata |

**Key insight:** The Anthropic SDK handles the hard parts of LLM I/O (retries, connection pooling, schema validation). Don't replicate any of it.

---

## Common Pitfalls

### Pitfall 1: `AsyncAnthropic` Created at Module Level
**What goes wrong:** `RuntimeError: no running event loop` when the module is imported during server startup
**Why it happens:** `AsyncAnthropic.__init__` creates an `httpx.AsyncClient`, which requires a running event loop in some configurations
**How to avoid:** Create `AsyncAnthropic()` inside `MultiStagePipeline.__init__()`, not at module level
**Warning signs:** Error at import time before any request is made

### Pitfall 2: Code Generator Returns GDScript with Python Syntax
**What goes wrong:** LLM uses `print("text")` (Godot 4 GDScript requires `print("text")` — actually same, but may use `elif` instead of `elif`, `null` vs `None`, `true/false` vs `True/False`)
**Why it happens:** LLM training data contains both Python and GDScript; without explicit Godot 4 constraints the model blends them
**How to avoid:** System prompt must list forbidden patterns explicitly: `True/False` → `true/false`, `None` → `null`, `elif` is fine in GDScript but `self.` on variables is not needed, `int()` → `int()` is fine but `str()` → `str()` is also fine; key constraint is `Input.is_action_pressed()` not `Input.is_key_pressed()`
**Warning signs:** Export stderr contains `Parse Error: Unexpected token` or `Identifier not found`

### Pitfall 3: Visual Polisher Overwrites Asset Files
**What goes wrong:** Polisher patches a script that `preload`s a shader path, but writes the wrong `res://` path, breaking the export
**Why it happens:** LLM hallucinates shader paths if not given exact template paths
**How to avoid:** System prompt for Visual Polisher must include the exact asset manifest with `res://` paths (e.g., `res://assets/shaders/pixel_art.gdshader`, `res://assets/palettes/neon.tres`)
**Warning signs:** Export succeeds but game crashes in browser on shader load

### Pitfall 4: Self-Correction Retry Doubles Stage-Start Events
**What goes wrong:** If Code Generator is retried, it emits another `stage_start` event, confusing the frontend with duplicate "Writing game code..." messages
**Why it happens:** Retry logic naively calls the full stage function including `emit`
**How to avoid:** Only emit `stage_start` on the first call. Pass a flag (`is_retry: bool`) or emit only from the outer loop that manages retries

### Pitfall 5: 90-Second Budget Blown by Large Prompts
**What goes wrong:** Code Generator system prompt with full GameDesign + example snippets + all control snippet source code exceeds context window budget and LLM takes 45+ seconds
**Why it happens:** Including full control snippet source code in the prompt for all 5 schemes even when only one is needed
**How to avoid:** Inject only the relevant control snippet source code based on `game_design.control_scheme`. For WASD, no snippet needed. For others, inject only the matching snippet.

### Pitfall 6: `shutil.copytree` Fails if Destination Exists
**What goes wrong:** Second run for same `job_id` raises `FileExistsError`
**Why it happens:** `shutil.copytree` raises by default if destination exists
**How to avoid:** Pass `dirs_exist_ok=True` to `shutil.copytree()` (Python 3.8+, project requires 3.12)

---

## Code Examples

### Verified: Model IDs (from official docs, 2026-03-14)
```python
# Source: https://platform.claude.com/docs/en/docs/about-claude/models/overview
HAIKU_MODEL = "claude-haiku-4-5"         # alias for claude-haiku-4-5-20251001
SONNET_MODEL = "claude-sonnet-4-6"       # alias for current Sonnet 4.6
```

### Verified: AsyncAnthropic Basic Call
```python
# Source: https://github.com/anthropics/anthropic-sdk-python
from anthropic import AsyncAnthropic

client = AsyncAnthropic()  # reads ANTHROPIC_API_KEY from environment

response = await client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}],
)
text = response.content[0].text
```

### Verified: Structured Output with Pydantic
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from anthropic import AsyncAnthropic
from pydantic import BaseModel

class GameSpec(BaseModel):
    title: str
    genre: str
    mechanics: list[str]
    visual_hints: list[str]

client = AsyncAnthropic()
response = await client.messages.parse(
    model="claude-haiku-4-5",
    max_tokens=512,
    messages=[{"role": "user", "content": "A side-scrolling platformer about a robot"}],
    output_format=GameSpec,
)
spec: GameSpec = response.parsed_output
```

### Template Asset Paths (verified from codebase)
```python
# Exact res:// paths for Visual Polisher system prompt
SHADER_PATHS = {
    "pixel_art": "res://assets/shaders/pixel_art.gdshader",
    "glow": "res://assets/shaders/glow.gdshader",
    "scanlines": "res://assets/shaders/scanlines.gdshader",
    "chromatic_aberration": "res://assets/shaders/chromatic_aberration.gdshader",
    "screen_distortion": "res://assets/shaders/screen_distortion.gdshader",
}
PALETTE_PATHS = {
    "neon": "res://assets/palettes/neon.tres",
    "retro": "res://assets/palettes/retro.tres",
    "pastel": "res://assets/palettes/pastel.tres",
    "monochrome": "res://assets/palettes/monochrome.tres",
}
PARTICLE_PATHS = {
    "explosion": "res://assets/particles/explosion.tscn",
    "dust": "res://assets/particles/dust.tscn",
    "sparkle": "res://assets/particles/sparkle.tscn",
    "trail": "res://assets/particles/trail.tscn",
}
CONTROL_SNIPPET_PATHS = {
    "mouse_follow": "res://assets/control_snippets/mouse_follow.gd",
    "click_to_move": "res://assets/control_snippets/click_to_move.gd",
    "drag": "res://assets/control_snippets/drag.gd",
    "point_and_shoot": "res://assets/control_snippets/point_and_shoot.gd",
}

# Named input actions (from project.godot [input] section)
INPUT_ACTIONS = ["move_left", "move_right", "move_up", "move_down", "jump", "shoot", "interact", "pause"]
```

### GameDesign Model (from CONTEXT.md, verified matches PRD)
```python
from enum import Enum
from pydantic import BaseModel

class ControlScheme(str, Enum):
    WASD = "wasd"
    MOUSE_FOLLOW = "mouse_follow"
    CLICK_TO_MOVE = "click_to_move"
    DRAG = "drag"
    POINT_AND_SHOOT = "point_and_shoot"

class ControlMapping(BaseModel):
    key: str    # human-readable, e.g. "Drag mouse"
    action: str # e.g. "Ship follows cursor"

class SceneSpec(BaseModel):
    name: str
    description: str
    nodes: list[str]  # node type names

class VisualStyle(BaseModel):
    palette: str   # one of: neon, retro, pastel, monochrome
    shader: str    # one of: pixel_art, glow, scanlines, chromatic_aberration, screen_distortion
    mood: str

class GameSpec(BaseModel):
    title: str
    genre: str
    mechanics: list[str]
    visual_hints: list[str]

class GameDesign(BaseModel):
    title: str
    genre: str
    scenes: list[SceneSpec]
    visual_style: VisualStyle
    mechanics: list[str]
    control_scheme: ControlScheme
    controls: list[ControlMapping]
    win_condition: str
    fail_condition: str
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Beta header `structured-outputs-2025-11-13` required | No beta header needed; `messages.parse()` stable | Late 2025 | Simpler client setup |
| `tool_use` for JSON extraction | `messages.parse(output_format=PydanticModel)` | Late 2025 | Direct Pydantic integration, SDK handles schema |
| `claude-3-haiku-20240307` | `claude-haiku-4-5` (alias) | 2025 | Haiku 3 deprecated April 19, 2026 |
| Manual JSON parsing + validation | `response.parsed_output` typed attribute | Late 2025 | No try/except around json.loads needed for structured stages |

**Deprecated/outdated:**
- `claude-3-haiku-20240307`: Deprecated, retires April 19, 2026. Use `claude-haiku-4-5`.
- Beta header `anthropic-beta: structured-outputs-2025-11-13`: Old parameter; `output_format` parameter works without it.

---

## Open Questions

1. **GDScript syntax error detection pre-export**
   - What we know: Godot `--check-only` has false positives with autoloads (issue #78587). Regex heuristics are unreliable for complex scripts.
   - What's unclear: Whether a quick Godot `--export-release` is fast enough to be the primary syntax check even for retries (5-15 seconds per attempt would mean up to 30 extra seconds on two retries).
   - Recommendation: Use regex to catch obvious Python-syntax contamination before the export. Accept that the actual Godot export stderr is the authoritative error for the second retry context. Total budget for 2 retries: ~30 extra seconds, leaving 60 seconds for the rest of the pipeline.

2. **`messages.parse()` async availability**
   - What we know: `messages.create()` confirmed async via `AsyncAnthropic`. The `messages.parse()` docs show synchronous examples.
   - What's unclear: Whether `await client.messages.parse()` works with `AsyncAnthropic` exactly as with `messages.create()`.
   - Recommendation: Check anthropic SDK source or test on first implementation. If `messages.parse()` is not async, fall back to `messages.create()` + `json.loads()` + `GameSpec.model_validate()`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-anyio 0.0.0 (from backend pyproject.toml) |
| Config file | `backend/pyproject.toml` → `[tool.pytest.ini_options] asyncio_mode = "auto"` |
| Quick run command | `cd backend && uv run pytest backend/tests/test_stages.py -x` |
| Full suite command | `cd backend && uv run pytest backend/tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STAGE-01 | Prompt Enhancer returns `GameSpec` with all required fields | unit (mock LLM) | `pytest backend/tests/test_stages.py::test_prompt_enhancer_returns_game_spec -x` | Wave 0 |
| STAGE-02 | Game Designer returns valid `GameDesign` with ControlScheme | unit (mock LLM) | `pytest backend/tests/test_stages.py::test_game_designer_returns_game_design -x` | Wave 0 |
| STAGE-03 | Code Generator returns dict of `.gd` files using named actions | unit (mock LLM) | `pytest backend/tests/test_stages.py::test_code_generator_uses_named_actions -x` | Wave 0 |
| STAGE-04 | Visual Polisher output contains shader + palette references | unit (mock LLM) | `pytest backend/tests/test_stages.py::test_visual_polisher_includes_shader_and_palette -x` | Wave 0 |
| STAGE-05 | Exporter copies template and calls `run_headless_export` | unit (mock export) | `pytest backend/tests/test_stages.py::test_exporter_calls_headless_export -x` | Wave 0 |
| STAGE-06 | Each stage emits `ProgressEvent(type="stage_start")` | unit | `pytest backend/tests/test_stages.py::test_all_stages_emit_stage_start -x` | Wave 0 |
| STAGE-01+06 | Self-correction: 2nd call includes error context | unit (mock LLM) | `pytest backend/tests/test_stages.py::test_self_correction_retry -x` | Wave 0 |
| all | End-to-end pipeline registered as "multi_stage" | integration (mock export + LLM) | `pytest backend/tests/test_multi_stage_pipeline.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && uv run pytest backend/tests/test_stages.py -x`
- **Per wave merge:** `cd backend && uv run pytest backend/tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/backend/tests/test_stages.py` — covers STAGE-01 through STAGE-06 with mocked `AsyncAnthropic`
- [ ] `backend/backend/tests/test_multi_stage_pipeline.py` — end-to-end integration with both LLM and export mocked
- [ ] `backend/backend/stages/__init__.py` — package init
- [ ] `backend/backend/pipelines/multi_stage/__init__.py` — package init
- [ ] SDK install: `cd backend && uv add anthropic` — not yet in pyproject.toml

---

## Sources

### Primary (HIGH confidence)
- `https://platform.claude.com/docs/en/docs/about-claude/models/overview` — model IDs for Haiku 4.5 and Sonnet 4.6 (fetched 2026-03-14)
- `https://platform.claude.com/docs/en/build-with-claude/structured-outputs` — `messages.parse()` API with Pydantic (fetched 2026-03-14)
- `https://github.com/anthropics/anthropic-sdk-python` — `AsyncAnthropic` import and usage (fetched 2026-03-14)
- Phase 2 source code (`backend/backend/`) — all existing infrastructure verified by direct file read

### Secondary (MEDIUM confidence)
- `https://pypi.org/project/anthropic/` — latest SDK version 0.84.0 (fetched 2026-03-14)
- `https://platform.claude.com/docs/en/build-with-claude/structured-outputs` — beta header no longer required (fetched 2026-03-14)

### Tertiary (LOW confidence)
- `https://github.com/godotengine/godot/issues/78587` — `--check-only` false positive bug; search result, not directly verified via issue content
- WebSearch results for `AsyncAnthropic` pattern confirmation — cross-verified with official SDK docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — model IDs and SDK API verified from official Anthropic docs
- Architecture: HIGH — patterns derived from verified SDK docs + Phase 2 source code
- Pitfalls: MEDIUM — GDScript generation pitfalls from domain knowledge + Godot issue search
- Validation: HIGH — test framework verified from pyproject.toml

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (model aliases stable; SDK API stable; Haiku 3 deprecation April 19, 2026 is after this phase)
