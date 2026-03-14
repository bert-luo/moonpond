# Phase 3: Multi-Stage Pipeline - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning
**Source:** Synthesized from PRD.md, REQUIREMENTS.md, ROADMAP.md, and existing codebase

<domain>
## Phase Boundary

This phase implements the five sequential LLM-powered stages that turn a user prompt into a playable WASM game. It builds on the Phase 2 backend foundation (FastAPI, SSE streaming, pipeline registry, Godot runner) and the Phase 1 template (base_2d with shaders, palettes, particles, control snippets).

Deliverable: a `multi_stage` pipeline registered in the registry that runs end-to-end from the command line — prompt in, WASM out — within 90 seconds.

</domain>

<decisions>
## Implementation Decisions

### Stage Architecture
- Five stages execute sequentially: Prompt Enhancer → Game Designer → Code Generator → Visual Polisher → Exporter
- Each stage takes a typed Pydantic input and produces a typed Pydantic output (stage contracts from PRD)
- Each stage emits a `ProgressEvent` (type=`stage_start`) with a human-readable SSE message at its start
- Stages live in `backend/backend/stages/` as individual modules
- The `MultiStagePipeline` class in `backend/backend/pipelines/multi_stage/` wires them together and registers as `"multi_stage"` in the pipeline registry

### LLM Model Assignments (from PRD)
- Prompt Enhancer: Haiku (fast, low-cost enrichment)
- Game Designer: Sonnet (structured output, design reasoning)
- Code Generator: Sonnet (code generation quality)
- Visual Polisher: Sonnet (code review + asset selection)
- Exporter: No LLM — Godot headless subprocess only

### Pydantic Models (from PRD)
- `GameSpec` — output of Prompt Enhancer (title, genre, mechanics, visual hints)
- `GameDesign` — output of Game Designer (scenes, visual_style, control_scheme, controls, win/fail conditions)
  - Includes `ControlScheme` enum: WASD, MOUSE_FOLLOW, CLICK_TO_MOVE, DRAG, POINT_AND_SHOOT
  - Includes `ControlMapping` model (key + action)
  - Includes `SceneSpec`, `VisualStyle` sub-models
- Code Generator output: dict of filename → GDScript content
- Visual Polisher output: dict of filename → patched GDScript content (with shader/palette/particle references)

### Code Generation Constraints
- Generated GDScript MUST use Godot 4 syntax exclusively
- MUST use named input actions from the template (move_left, move_right, etc.) — never hardcode keys
- For non-WASD schemes, import from `control_snippets/` rather than generating input handling from scratch

### Visual Polisher Requirements
- Must apply at least one shader reference from the template asset library
- Must apply at least one palette selection from the template asset library
- May add particle scene references (explosion, dust, sparkle, trail) where appropriate

### Self-Correction (GDScript Syntax Errors)
- If Code Generator output has a GDScript syntax error, feed compiler output back to Code Generator
- Up to 2 retry attempts with the original GameDesign in context
- After 2 failures, the pipeline fails with an error event

### Exporter Stage
- Copies the base_2d template to `games/{job_id}/project/`
- Writes generated GDScript files into the project
- Runs Godot headless export using the existing `runner.py` (from Phase 2)
- Returns the WASM output path in `GameResult`

### Existing Infrastructure (from Phase 2)
- `GamePipeline` Protocol, `ProgressEvent`, `GameResult`, `EmitFn` in `pipelines/base.py`
- `PIPELINES` registry in `pipelines/registry.py` — add `"multi_stage"` entry
- `run_headless_export()` in `godot/runner.py` — async, non-blocking, validates output file existence
- `POST /api/generate` and `GET /api/stream/{job_id}` endpoints already working
- Job state management in `state.py`

### Claude's Discretion
- Exact LLM prompt templates for each stage (system prompts, few-shot examples)
- How to handle the Anthropic client initialization (shared client vs per-stage)
- Structured output parsing strategy (tool_use vs JSON mode vs text parsing)
- Whether to use a syntax check step before the full Godot export for self-correction
- Internal error handling within individual stages (beyond the self-correction requirement)
- Test strategy for stages (unit tests with mocked LLM responses vs integration tests)

</decisions>

<specifics>
## Specific Ideas

### SSE Messages per Stage (from PRD)
| Stage | Message |
|---|---|
| Prompt Enhancer | "Understanding your idea..." |
| Game Designer | "Designing game structure..." |
| Code Generator | "Writing game code..." |
| Visual Polisher | "Adding visual polish..." |
| Exporter | "Building for web..." |

### GameDesign Model Reference (from PRD)
```python
class ControlScheme(str, Enum):
    WASD = "wasd"
    MOUSE_FOLLOW = "mouse_follow"
    CLICK_TO_MOVE = "click_to_move"
    DRAG = "drag"
    POINT_AND_SHOOT = "point_and_shoot"

class ControlMapping(BaseModel):
    key: str      # human-readable, e.g. "Drag mouse"
    action: str   # e.g. "Ship follows cursor"

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

### Template Assets Available to Visual Polisher
- Shaders: pixel_art, glow, scanlines, chromatic_aberration, screen_distortion
- Palettes: neon, retro, pastel, monochrome (Gradient .tres files)
- Particles: explosion, dust, sparkle, trail (.tscn scenes)
- Control snippets: mouse_follow, click_to_move, drag, point_and_shoot

### 90-Second Budget
The entire pipeline must complete within 90 seconds. Budget should be weighted toward Code Generator and Visual Polisher stages. Exporter (Godot headless) typically takes 5-15 seconds.

</specifics>

<deferred>
## Deferred Ideas

- Single-shot agentic pipeline (future pipeline strategy)
- ROMA multi-agent pipeline (future pipeline strategy)
- Playwright visual feedback loop (future quality signal)
- base_3d template support (TMPL-07, v2)
- Audio/sound effects pipeline stage (out of scope)

</deferred>

---

*Phase: 03-multi-stage-pipeline*
*Context gathered: 2026-03-14 via synthesis from PRD.md and project docs*
