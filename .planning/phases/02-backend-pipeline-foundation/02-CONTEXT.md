# Phase 2: Backend Pipeline Foundation - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning
**Source:** PRD Express Path (PRD.md)

<domain>
## Phase Boundary

This phase delivers the FastAPI backend skeleton with:
- API endpoints (`POST /api/generate`, `GET /api/stream/{job_id}`)
- SSE streaming infrastructure for real-time progress events
- Pipeline registry mapping strategy names to `GamePipeline` Protocol implementations
- Godot headless runner for async WASM export
- Static file serving for generated games at `/games/{job_id}/export/`

The phase produces a working backend that a stub pipeline can exercise end-to-end. Actual LLM-powered stages come in Phase 3.

</domain>

<decisions>
## Implementation Decisions

### API Design
- `POST /api/generate` accepts a prompt body, returns `job_id` immediately (under 100ms), spawns background task
- `GET /api/stream/{job_id}` streams SSE `ProgressEvent` messages with 15-second heartbeat keepalive
- Pipeline selection via query param on generate endpoint (hidden in UI, useful for evaluation)

### Pipeline Protocol
- `GamePipeline` Protocol with async `generate(prompt, job_id, emit)` → `GameResult` signature
- `emit` is a callback that pushes SSE events to the client
- FastAPI endpoint is pipeline-agnostic — resolves pipeline from registry and calls `generate`
- Registry is a simple dict mapping strategy names to pipeline classes (`pipelines/registry.py`)

### Godot Runner
- Subprocess wrapper in `backend/godot/runner.py`
- Executes headless export non-blocking (must not freeze FastAPI event loop)
- Captures stderr for error reporting
- Validates output file existence rather than exit code
- Uses Phase 1's base_2d template as source

### Static File Serving
- Generated games served at `/games/{job_id}/export/`
- Job directory structure: `games/{job_id}/project/` (Godot files) + `games/{job_id}/export/` (WASM output)
- `games/` directory is gitignored, runtime output only

### Type System
- `ProgressEvent` and `GameResult` as Pydantic models in `backend/models/`
- SSE events are JSON-serialized ProgressEvent objects

### Claude's Discretion
- Async task management approach (asyncio.create_task vs BackgroundTasks vs task queue)
- SSE connection management and cleanup strategy
- Error handling for edge cases (duplicate job IDs, missing jobs, concurrent access)
- Test strategy for async endpoints and SSE streaming
- Heartbeat implementation mechanism (asyncio timer vs middleware)
- Job state storage (in-memory dict vs lightweight store)

</decisions>

<specifics>
## Specific Ideas

- File structure from PRD: `backend/main.py` (FastAPI app, routes), `backend/pipelines/base.py` (Protocol, ProgressEvent, GameResult), `backend/pipelines/registry.py` (name → class mapping), `backend/godot/runner.py` (headless export wrapper), `backend/models/` (Pydantic types)
- The stub pipeline should: copy base_2d template, write a dummy GDScript file, run Godot export, return WASM path
- SSE progress event examples from PRD: "Understanding your idea...", "Designing game structure...", etc.
- `GameDesign` model includes `control_scheme` field and `controls` list that flow through to SSE completion event
- Hard timeout of 90s total mentioned in PRD (though REL-02 is deferred to v2, the architecture should not preclude it)

</specifics>

<deferred>
## Deferred Ideas

- Single-shot agentic pipeline (future pipeline strategy)
- ROMA multi-agent pipeline (future pipeline strategy)
- Playwright visual feedback loop (future quality signal)
- GDScript self-correction pass (Phase 3 scope, STAGE-06/REL-01)
- 90-second hard timeout with partial result (v2 REL-02)
- User accounts and game persistence

</deferred>

---

*Phase: 02-backend-pipeline-foundation*
*Context gathered: 2026-03-14 via PRD Express Path*
