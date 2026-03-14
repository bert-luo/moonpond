# Architecture Research

**Domain:** AI-powered multi-stage code/game generation pipeline
**Researched:** 2026-03-13
**Confidence:** HIGH (primary source: project PRD.md + training knowledge on FastAPI SSE, multi-stage AI pipelines, Godot headless)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Browser (Next.js 14)                        │
│  ┌──────────────────────┐        ┌──────────────────────────────┐   │
│  │      ChatPanel        │        │         GameViewer           │   │
│  │  - prompt input       │        │  - iframe (WASM game)        │   │
│  │  - SSE event stream   │        │  - loading skeleton          │   │
│  │  - progress messages  │        │  - controls legend           │   │
│  │  - error states       │        │                              │   │
│  └─────────┬────────────┘        └──────────────────────────────┘   │
│            │ POST /api/generate                                      │
│            │ GET  /api/stream/{job_id} (EventSource / SSE)           │
└────────────┼────────────────────────────────────────────────────────┘
             │  (Next.js API routes proxy to FastAPI)
             │
┌────────────▼────────────────────────────────────────────────────────┐
│                     FastAPI Backend (Python async)                  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                        API Layer                               │  │
│  │   POST /generate  →  job_id, enqueue pipeline run             │  │
│  │   GET  /stream/{job_id}  →  StreamingResponse (SSE)           │  │
│  │   GET  /games/{job_id}/export/{file}  →  static WASM files    │  │
│  └───────────────────────────┬───────────────────────────────────┘  │
│                              │                                      │
│  ┌───────────────────────────▼───────────────────────────────────┐  │
│  │                    Pipeline Registry                           │  │
│  │   "multi_stage" → MultiStagePipeline                         │  │
│  │   "single_shot" → SingleShotPipeline  (future)               │  │
│  │   "roma"        → RomaPipeline        (future)               │  │
│  └───────────────────────────┬───────────────────────────────────┘  │
│                              │  emit: Callable[[ProgressEvent], None]│
│  ┌───────────────────────────▼───────────────────────────────────┐  │
│  │              Active Pipeline (GamePipeline Protocol)           │  │
│  │                                                               │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐              │  │
│  │  │  Prompt    │  │   Game     │  │   Code     │              │  │
│  │  │  Enhancer  │→ │  Designer  │→ │ Generator  │→ ...         │  │
│  │  │  (Haiku)   │  │  (Sonnet)  │  │  (Sonnet)  │              │  │
│  │  └────────────┘  └────────────┘  └────────────┘              │  │
│  │                                                               │  │
│  │  ┌────────────┐  ┌──────────────────────────────────────┐    │  │
│  │  │  Visual    │  │             Exporter                  │    │  │
│  │  │  Polisher  │→ │  (Godot 4.5.1 headless subprocess)   │    │  │
│  │  │  (Sonnet)  │  │                                      │    │  │
│  │  └────────────┘  └──────────────────────────────────────┘    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   Godot Templates (static)                     │  │
│  │   base_2d/  base_3d/  — copied per job, never mutated         │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                   games/ (runtime output)                      │  │
│  │   {job_id}/project/   — GDScript files written here           │  │
│  │   {job_id}/export/    — WASM bundle served to iframe           │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| ChatPanel (frontend) | Display streaming progress, prompt input, controls legend on completion | EventSource (SSE), POST /api/generate |
| GameViewer (frontend) | iframe hosting the exported WASM game; loading skeleton while pending | Receives game URL from SSE completion event |
| Next.js API routes | Thin proxy; forward POST /generate and SSE stream to FastAPI; avoids CORS complexity | Frontend, FastAPI |
| FastAPI API layer | HTTP routing, job_id generation, SSE StreamingResponse wiring | Pipeline registry, static file server |
| Pipeline Registry | Maps pipeline name → class; resolves which pipeline to instantiate per request | API layer, concrete pipeline implementations |
| GamePipeline (Protocol) | Defines the interface every pipeline must implement; API is pipeline-agnostic | Consumed by API layer, implemented by pipelines |
| Stage modules (stages/) | Each stage owns a bounded LLM call with typed input/output; independently testable | Called sequentially by MultiStagePipeline; use LLM client + models/ types |
| Godot headless runner | Subprocess wrapper around `godot --headless --export-release`; captures stdout/stderr; enforces timeout | Called by Exporter stage; reads/writes games/{job_id}/ |
| Godot templates | Pre-built valid Godot projects (base_2d, base_3d); copied per job as scaffolding | Copied by Exporter (or pipeline init) before stages write GDScript |
| LLM client(s) | Thin wrappers around Anthropic/OpenAI SDKs | Stage modules |
| games/ directory | Runtime-only; gitignored; stores per-job project files and WASM export output | Godot runner (write), FastAPI static server (read) |

## Recommended Project Structure

```
moonpond/
  frontend/
    app/
      page.tsx                     # Root layout: two-column shell
      api/
        generate/route.ts          # Proxy: POST → FastAPI /generate
        stream/[job_id]/route.ts   # Proxy: GET  → FastAPI /stream/{job_id}
      components/
        ChatPanel/
          index.tsx                # SSE consumer, message list, prompt form
          ProgressMessage.tsx      # Individual progress bubble
          ControlsLegend.tsx       # Rendered on completion event
        GameViewer/
          index.tsx                # iframe + loading skeleton state machine
    public/
  backend/
    main.py                        # FastAPI app, route registration
    pipelines/
      base.py                      # GamePipeline Protocol, ProgressEvent, GameResult
      registry.py                  # PIPELINES dict: name → class
      multi_stage/
        __init__.py                # MultiStagePipeline.generate() — sequential stage runner
      single_shot/                 # (future)
      roma/                        # (future)
    stages/
      prompt_enhancer.py           # Haiku: vague prompt → EnhancedPrompt model
      game_designer.py             # Sonnet: EnhancedPrompt → GameDesign model
      code_generator.py            # Sonnet: GameDesign → {filename: gdscript} dict
      visual_polisher.py           # Sonnet: code + GameDesign → patched code + asset refs
      exporter.py                  # Godot runner invocation → GameResult
    godot/
      templates/
        base_2d/                   # Committed valid Godot project (never modified in place)
        base_3d/
      runner.py                    # headless subprocess wrapper
    models/
      game_design.py               # GameDesign, ControlScheme, VisualStyle, SceneSpec
      pipeline_io.py               # EnhancedPrompt, GeneratedCode, GameResult, ProgressEvent
    llm/
      anthropic_client.py          # Thin wrapper; structured output helpers
      openai_client.py             # Optional secondary (image gen, embeddings)
  games/                           # gitignored; runtime per-job output
    {job_id}/
      project/                     # Godot project (template copy + generated GDScript)
      export/                      # index.html + .wasm + .js served as static files
```

### Structure Rationale

- **stages/ vs pipelines/:** Stages are reusable building blocks (independently testable, individually swappable to different models). Pipelines are orchestration strategies that compose stages differently. This separation is what enables future `single_shot` and `roma` pipelines to reuse the same stage modules.
- **models/:** All Pydantic types live here, not in stage files. Stages import types; types don't import stages. Prevents circular imports and makes the data contracts inspectable at a glance.
- **godot/runner.py:** Isolates all subprocess complexity behind one boundary. Stages never call `subprocess` directly — only the runner does. This makes mocking trivial for unit tests.
- **llm/:** LLM client wrappers separated from stage logic. Stages describe *what* to ask; clients handle *how* to call the API (retry, structured output extraction, token counting). Swapping Sonnet → Opus affects only the client call, not stage logic.
- **games/ (gitignored):** Runtime output never committed. Each job is ephemeral. The static server reads from here; the Godot runner writes here.

## Architectural Patterns

### Pattern 1: Protocol-Based Pipeline Registry

**What:** A Python `Protocol` defines the pipeline interface. A registry dict maps string names to concrete classes. The API resolves the pipeline at request time; it never imports concrete pipeline classes directly.

**When to use:** Any time you need swappable strategy implementations without touching the API surface. Enables A/B testing generation strategies via a query param with no frontend changes.

**Trade-offs:** Adds one indirection layer. Worth it because it decouples the API from pipeline implementations entirely, which is core to the project's architectural goal.

**Example:**
```python
# pipelines/base.py
class GamePipeline(Protocol):
    async def generate(
        self,
        prompt: str,
        job_id: str,
        emit: Callable[[ProgressEvent], None]
    ) -> GameResult: ...

# pipelines/registry.py
PIPELINES: dict[str, type[GamePipeline]] = {
    "multi_stage": MultiStagePipeline,
}

# main.py (API layer — never mentions MultiStagePipeline)
pipeline_name = request.pipeline or "multi_stage"
pipeline_cls = PIPELINES[pipeline_name]
pipeline = pipeline_cls()
result = await pipeline.generate(prompt, job_id, emit=queue.put_nowait)
```

### Pattern 2: Emit Callback → SSE Queue

**What:** The pipeline receives an `emit` callable that pushes `ProgressEvent` objects into an asyncio queue. The SSE endpoint independently drains that queue and formats events as `data: ...\n\n` strings. The pipeline never knows it's talking to HTTP.

**When to use:** Any long-running async operation that needs to stream intermediate results to a client. The queue decouples generation speed from HTTP write speed.

**Trade-offs:** Requires per-job queue management (create on POST /generate, look up on GET /stream). A simple dict keyed by job_id works at MVP scale. At scale, replace with Redis pub/sub.

**Example:**
```python
# main.py
job_queues: dict[str, asyncio.Queue] = {}

@app.post("/generate")
async def generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    q: asyncio.Queue[ProgressEvent | None] = asyncio.Queue()
    job_queues[job_id] = q
    background_tasks.add_task(run_pipeline, request.prompt, job_id, q)
    return {"job_id": job_id}

@app.get("/stream/{job_id}")
async def stream(job_id: str):
    q = job_queues[job_id]
    async def event_generator():
        while True:
            event = await q.get()
            if event is None:  # sentinel: pipeline done
                yield "data: [DONE]\n\n"
                break
            yield f"data: {event.model_dump_json()}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Pattern 3: Template Copy-on-Job — Never Mutate Originals

**What:** At the start of each generation job, the pipeline copies the appropriate template (`base_2d` or `base_3d`) into `games/{job_id}/project/`. Subsequent stages write generated GDScript files into this copy. The template source is never touched.

**When to use:** Any time you have a scaffold that multiple concurrent jobs must build on top of. Avoids race conditions and ensures each job starts from a known-good state.

**Trade-offs:** Disk I/O per job (a full Godot project copy is ~50-200KB of text files). Acceptable at MVP scale. At high concurrency, consider symlinks for read-only assets (shaders, palettes) rather than copying binaries.

**Example:**
```python
import shutil, pathlib

TEMPLATES_DIR = pathlib.Path("backend/godot/templates")
GAMES_DIR = pathlib.Path("games")

def init_job_project(job_id: str, template: str) -> pathlib.Path:
    src = TEMPLATES_DIR / template        # "base_2d" or "base_3d"
    dst = GAMES_DIR / job_id / "project"
    shutil.copytree(src, dst)
    return dst
```

### Pattern 4: Typed Stage Contracts (Pydantic I/O)

**What:** Every stage has an explicit input type and output type as Pydantic models. The pipeline passes the output of stage N directly as the input to stage N+1. No untyped dict passing between stages.

**When to use:** Any multi-step LLM pipeline where debugging intermediate outputs matters. Typed contracts make the data flow inspectable (log or serialize any stage output trivially), testable (mock any stage input), and refactorable (changing a stage's output type surfaces all downstream consumers immediately via type checker).

**Trade-offs:** Slightly more upfront model definition work. Pays back immediately when debugging LLM output quality.

**Example:**
```python
# Stage N output becomes Stage N+1 input
enhanced: EnhancedPrompt = await prompt_enhancer.run(raw_prompt, emit)
design: GameDesign       = await game_designer.run(enhanced, emit)
code: GeneratedCode      = await code_generator.run(design, emit)
polished: GeneratedCode  = await visual_polisher.run(code, design, emit)
result: GameResult       = await exporter.run(polished, job_id, emit)
```

### Pattern 5: Godot Headless Subprocess with Stderr Capture

**What:** The Godot headless runner wraps `asyncio.create_subprocess_exec` (not `subprocess.run` — which would block the event loop). It streams both stdout and stderr, enforces the 90s hard timeout, and returns structured output including the exit code and any compiler error lines.

**When to use:** Any time you need to run an external long-running process from an async Python server without blocking. Critical for Godot export which can take 20-60 seconds.

**Trade-offs:** Async subprocess handling is more complex than synchronous. The complexity is localized entirely to `godot/runner.py` — callers see a simple async function.

**Example:**
```python
# godot/runner.py
async def export_project(project_path: Path, job_id: str) -> ExportResult:
    proc = await asyncio.create_subprocess_exec(
        GODOT_BINARY, "--headless", "--export-release", "Web",
        cwd=project_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=EXPORT_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        proc.kill()
        return ExportResult(success=False, error="Export timed out")

    return ExportResult(
        success=(proc.returncode == 0),
        stdout=stdout.decode(),
        stderr=stderr.decode(),   # GDScript compiler errors are here
        export_path=project_path / "export",
    )
```

### Pattern 6: GDScript Self-Correction Loop

**What:** After the Code Generator stage, if Godot headless reports GDScript parser/compiler errors in stderr, the error output is fed back to the LLM with the original code for a single correction pass. Not a loop — one retry maximum to stay within the 90s budget.

**When to use:** Syntax errors are predictable and fixable. Semantic errors (wrong game logic) are not worth retrying programmatically — surface to user instead.

**Trade-offs:** Adds one more LLM round-trip on error (typically 3-8 seconds for Sonnet). Worth it because GDScript syntax errors are common and the compiler output is highly actionable context for the LLM.

**Example:**
```python
# stages/code_generator.py (simplified)
async def run_with_correction(design: GameDesign, job_id: str, emit) -> GeneratedCode:
    code = await self._generate(design, emit)
    syntax_errors = await validate_gdscript(code, job_id)  # headless --check pass
    if syntax_errors:
        emit(ProgressEvent(message="Fixing syntax errors..."))
        code = await self._correct(code, syntax_errors, emit)
    return code
```

## Data Flow

### Primary Request Flow (Happy Path)

```
User types prompt → POST /api/generate
    ↓
Next.js proxy → POST /generate (FastAPI)
    ↓
API layer: generate job_id, create asyncio.Queue, launch background task
    ↓
Return {"job_id": "abc123"} synchronously
    ↓
Frontend: open EventSource("GET /api/stream/abc123")
    ↓
Background task: resolve pipeline from registry, call pipeline.generate(prompt, job_id, emit)
    ↓
Pipeline copies template → games/abc123/project/
    ↓
Stage 1: Prompt Enhancer (Haiku) → EnhancedPrompt
    emit(ProgressEvent("Understanding your idea...")) → queue
    ↓
Stage 2: Game Designer (Sonnet) → GameDesign
    emit(ProgressEvent("Designing game structure...")) → queue
    ↓
Stage 3: Code Generator (Sonnet) → GeneratedCode (GDScript files written to disk)
    emit(ProgressEvent("Writing game code...")) → queue
    → optional: GDScript self-correction pass if syntax errors detected
    ↓
Stage 4: Visual Polisher (Sonnet) → GeneratedCode (shader/particle/palette refs patched)
    emit(ProgressEvent("Adding visual polish...")) → queue
    ↓
Stage 5: Exporter (Godot headless subprocess)
    emit(ProgressEvent("Building for web...")) → queue
    → games/abc123/export/index.html + .wasm written
    ↓
emit(ProgressEvent(type="complete", game_url="/games/abc123/export/index.html",
                   controls=design.controls)) → queue
emit(None)  # sentinel: SSE stream ends
    ↓
SSE endpoint drains queue → "data: {...}\n\n" events → EventSource
    ↓
Frontend: on "complete" event → set iframe src → game loads
           render controls legend in ChatPanel
```

### SSE Event Types

```
ProgressEvent:
  type: "progress" | "complete" | "error" | "warning"
  message: str              # Human-readable chat bubble text
  stage: str | None         # "prompt_enhancer" | "game_designer" | ...
  game_url: str | None      # Only on type="complete"
  controls: list[ControlMapping] | None  # Only on type="complete"
  error_detail: str | None  # Only on type="error"
```

### Template Data Flow

```
base_2d/ (committed, immutable)
    ↓ shutil.copytree (per job)
games/{job_id}/project/
    + scripts/gameplay.gd          ← Code Generator writes
    + scripts/player.gd            ← Code Generator writes
    + scenes/Gameplay.tscn         ← Code Generator writes
    + scenes/Player.tscn           ← Code Generator writes
    (existing files: Main.tscn, game_manager.gd, shaders/, particles/, palettes/)
    ↓ Visual Polisher patches shader references and palette usage in generated scripts
    ↓ Godot headless --export-release
games/{job_id}/export/
    index.html
    moonpond.wasm
    moonpond.js
    (+ audio bus, icon.png from template)
```

### Error State Flow

```
Stage failure
    ↓
emit(ProgressEvent(type="error", message="Generation failed. Try again.", error_detail=...))
emit(None)  # close stream
    ↓
Frontend: SSE "error" event → show error message in ChatPanel, re-enable prompt input

Timeout (90s hard cap via asyncio.wait_for on pipeline.generate)
    ↓
emit(ProgressEvent(type="error", message="Took too long. Try a simpler idea."))
    ↓
Background task cancelled, queue sentinel emitted
```

## Build Order (Phase Dependencies)

The dependency graph drives build order. Each phase's components depend on the previous:

```
Phase 1: Project Scaffold
  ├── Next.js app shell (no logic, just file structure)
  ├── FastAPI app with placeholder routes
  └── Godot 4.5.1 binary verified present
        ↓ (template must exist before pipeline can copy it)

Phase 2: Godot Templates
  ├── base_2d project (project.godot, export_presets.cfg, Main.tscn)
  ├── Shader library (pixel_art, glow, scanlines, etc.)
  ├── Particle scene library
  ├── Palette .tres files
  └── base_3d project
  → GATE: Template must export to WASM cleanly before pipeline work begins
        ↓ (pipeline needs types, registry, runner, SSE endpoint)

Phase 3: Backend Pipeline Foundation
  ├── GamePipeline Protocol, ProgressEvent, GameResult types (models/)
  ├── Pipeline registry skeleton
  ├── Godot headless runner (runner.py)
  ├── Static file serving (/games/{job_id}/export/)
  ├── SSE endpoint (GET /stream/{job_id})
  └── Generate endpoint (POST /generate) with background task wiring
        ↓ (stages need foundation types; pipeline needs stages)

Phase 4: Multi-Stage MVP Pipeline
  ├── All 5 stage modules (prompt_enhancer, game_designer, code_generator,
  │    visual_polisher, exporter) with typed Pydantic I/O
  ├── MultiStagePipeline wiring stages in sequence
  ├── GDScript self-correction pass
  └── End-to-end test: prompt in → WASM out (no frontend yet)
        ↓ (frontend needs working backend SSE)

Phase 5: Frontend
  ├── Two-column layout
  ├── SSE EventSource client → streaming ChatPanel messages
  ├── GameViewer iframe with loading skeleton
  └── Prompt input form wired to POST /api/generate
        ↓ (integration requires both working)

Phase 6: Integration & Polish
  ├── End-to-end frontend↔backend wiring
  ├── Prompt engineering per stage
  ├── Error state UX
  └── Evaluation against test prompt set
```

**Critical dependency:** Phase 2 (working Godot template that exports cleanly) is the hardest gating dependency. If `export_presets.cfg` is wrong or the template has a GDScript error, the entire Exporter stage is broken regardless of how good the LLM output is. This must be verified before Phase 3 begins.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Anthropic Claude API | Async SDK (`anthropic` Python package); structured output via tool_use or JSON mode | Primary LLM; Haiku for Prompt Enhancer (speed), Sonnet for Designer/Generator/Polisher (quality) |
| OpenAI API | Async SDK; optional secondary for image generation or fallback | Not used in MVP pipeline; reserved for ROMA multi-agent future |
| Godot 4.5.1 headless binary | `asyncio.create_subprocess_exec`; stdout/stderr piped; 90s timeout | Binary must be exactly 4.5.1 — export_presets.cfg is version-locked |
| Browser EventSource API | Frontend native; no library needed; reconnects automatically | One-directional only; sufficient for progress streaming |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Frontend ↔ FastAPI | HTTP (POST /generate, SSE GET /stream, GET /games static) via Next.js proxy | Proxy avoids CORS; all traffic goes through Next.js API routes in dev |
| API layer ↔ Pipeline | Python function call (`pipeline.generate(prompt, job_id, emit)`) + asyncio.Queue for events | API never imports concrete pipeline classes; only registry and Protocol |
| Pipeline ↔ Stages | Direct async function calls; typed Pydantic models as arguments | Stage modules are not classes — simple async functions is sufficient for MVP |
| Stages ↔ LLM clients | Function calls in `llm/` wrappers | Clients handle retry, model selection, structured output parsing |
| Exporter stage ↔ Godot runner | Function call to `runner.export_project(path, job_id)` | Runner owns all subprocess complexity; Exporter only calls this one function |
| Godot runner ↔ filesystem | Reads from `games/{job_id}/project/`, writes to `games/{job_id}/export/` | Template copy must happen before runner is called |
| FastAPI static server ↔ frontend iframe | HTTP GET `/games/{job_id}/export/index.html` + `.wasm` | FastAPI's `StaticFiles` mount; game_url in completion SSE event |

## Anti-Patterns

### Anti-Pattern 1: Stage Modules Calling subprocess Directly

**What people do:** Each stage that needs Godot validation calls `subprocess.run(["godot", ...])` inline.

**Why it's wrong:** Blocks the async event loop (subprocess.run is synchronous). Multiple stages calling Godot create competing processes. Impossible to mock in tests. Timeout logic duplicated.

**Do this instead:** All Godot subprocess calls go through `godot/runner.py`. It uses `asyncio.create_subprocess_exec`, owns the timeout, and is the single place to mock in tests.

### Anti-Pattern 2: Mutating Templates In Place

**What people do:** The pipeline writes generated GDScript directly into the template directory rather than copying it first.

**Why it's wrong:** The first job corrupts the template for all subsequent jobs. Concurrent jobs overwrite each other's files. Templates become non-reproducible.

**Do this instead:** Always `shutil.copytree(template_src, games/{job_id}/project/)` at job start. Templates are read-only.

### Anti-Pattern 3: Untyped Dict Passing Between Stages

**What people do:** Stages return `dict` and the next stage does `data["game_design"]["scenes"]`.

**Why it's wrong:** No type checking, no IDE completion, silent key errors at runtime, impossible to know what fields exist without reading the full chain. Breaks the independently-testable property of stages.

**Do this instead:** Every stage input and output is a Pydantic model defined in `backend/models/`. Pass model instances, not dicts.

### Anti-Pattern 4: Blocking the FastAPI Event Loop During Pipeline Execution

**What people do:** Run `pipeline.generate()` directly in the request handler (not as a background task).

**Why it's wrong:** Holds the request open for 60-90 seconds. Only one generation can run at a time. The SSE endpoint for that job can never be opened because the event loop is busy.

**Do this instead:** `POST /generate` returns immediately with `job_id` after launching the pipeline as a `BackgroundTask`. The SSE endpoint `GET /stream/{job_id}` drains the asyncio.Queue that the background task populates.

### Anti-Pattern 5: LLM-Generated export_presets.cfg

**What people do:** Ask the LLM to generate the Godot export configuration along with the game scripts.

**Why it's wrong:** `export_presets.cfg` is highly version-sensitive and contains paths to the export template binary (`.tpz` file). Even a minor deviation causes silent export failure with cryptic errors. The LLM has no reliable knowledge of the exact 4.5.1 export template path on the host system.

**Do this instead:** Commit a known-working `export_presets.cfg` in the template. The LLM never touches it. The runner always uses the template's preset.

### Anti-Pattern 6: Polling Instead of SSE for Progress

**What people do:** Frontend polls `GET /status/{job_id}` every second to check for updates.

**Why it's wrong:** Introduces up to 1s latency on each stage transition. Creates unnecessary HTTP load. Makes progress messages feel choppy rather than live.

**Do this instead:** SSE (`EventSource`) is push-based. The server emits events the instant a stage completes. The browser receives them in real time with no polling overhead.

## Scaling Considerations

This is an MVP targeting local single-user usage. Scaling considerations are noted for future awareness, not immediate action.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 user (MVP) | In-process asyncio.Queue per job; local filesystem for games/; in-memory job registry dict |
| 10-50 concurrent users | asyncio.Queue approach still works; filesystem I/O is the first bottleneck (Godot template copy + export); consider tmpfs mount for games/ |
| 100+ concurrent users | Replace in-process job queue with Redis pub/sub; move games/ to object storage (S3); run Godot exports in isolated subprocesses with a worker pool |

**First bottleneck at scale:** Godot headless export is the most resource-intensive operation (single-threaded, CPU-bound, 20-60s per job). A worker pool with a queue depth limit is the first scaling intervention needed.

**Second bottleneck:** The in-memory `job_queues` dict doesn't survive server restart. At multi-instance scale, replace with Redis.

## Sources

- Moonpond PRD.md (primary specification — HIGH confidence, authoritative for this project)
- FastAPI `BackgroundTasks` + `StreamingResponse` for SSE: training knowledge, confirmed patterns align with FastAPI official documentation approach (MEDIUM confidence)
- asyncio `create_subprocess_exec` for non-blocking subprocess: Python stdlib — HIGH confidence
- Godot 4 headless export CLI flags (`--headless --export-release`): training knowledge from Godot 4.x documentation (MEDIUM confidence — verify exact flag against 4.5.1 release notes)
- Protocol-based registry pattern: standard Python structural subtyping — HIGH confidence
- Server-Sent Events / `EventSource` browser API: web standard, no library needed — HIGH confidence
- Pydantic v2 structured output from LLMs: well-established pattern with Anthropic tool_use — HIGH confidence

---
*Architecture research for: AI-powered multi-stage Godot 4 game generation pipeline (Moonpond)*
*Researched: 2026-03-13*
