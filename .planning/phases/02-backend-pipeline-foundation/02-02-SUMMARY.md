---
phase: 02-backend-pipeline-foundation
plan: 02
subsystem: api
tags: [fastapi, sse, asyncio, pipeline, stub, pydantic, httpx, pytest-anyio]

requires:
  - phase: 02-backend-pipeline-foundation
    plan: 01
    provides: GamePipeline Protocol, ProgressEvent/GameResult models, pipeline registry, Godot runner, state store
  - phase: 01-scaffold-godot-template
    provides: base_2d Godot template for stub pipeline copytree
provides:
  - FastAPI app with POST /api/generate and GET /api/stream/{job_id} endpoints
  - SSE streaming via EventSourceResponse generator pattern
  - StubPipeline exercising full chain (template copy, file injection, Godot export)
  - Complete test suite covering PIPE-01 through PIPE-05
  - Static file serving at /games/{job_id}/export/
affects: [03-llm-code-generation]

tech-stack:
  added: []
  patterns: [response_class-EventSourceResponse-generator, mock-run_headless_export-in-tests, ASGITransport-AsyncClient-test-pattern]

key-files:
  created:
    - backend/backend/main.py
    - backend/backend/pipelines/stub/__init__.py
    - backend/backend/pipelines/stub/pipeline.py
    - backend/backend/tests/__init__.py
    - backend/backend/tests/test_generate.py
    - backend/backend/tests/test_stream.py
    - backend/backend/tests/test_registry.py
    - backend/backend/tests/test_runner.py
    - backend/backend/tests/test_static.py
  modified:
    - backend/backend/pipelines/registry.py

key-decisions:
  - "SSE stream endpoint uses response_class=EventSourceResponse with async generator (not manual EventSourceResponse wrapping)"
  - "All generate endpoint tests mock run_headless_export to avoid Godot binary dependency"
  - "Repo-root-relative paths using __file__ parent traversal accounting for nested backend/backend/ layout"

patterns-established:
  - "SSE generator pattern: @app.get(path, response_class=EventSourceResponse) with yield ServerSentEvent"
  - "Test mock pattern: patch backend.pipelines.stub.pipeline.run_headless_export with AsyncMock returning RunResult"
  - "Async test pattern: httpx.AsyncClient + ASGITransport(app=app) + @pytest.mark.anyio"

requirements-completed: [PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05]

duration: 5min
completed: 2026-03-14
---

# Phase 02 Plan 02: API Endpoints and Stub Pipeline Summary

**FastAPI SSE streaming endpoints with stub pipeline exercising full template-copy-export chain, 11 tests covering all PIPE requirements**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-14T09:01:44Z
- **Completed:** 2026-03-14T09:06:47Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- POST /api/generate creates job with UUID4, spawns background pipeline task, returns job_id immediately
- GET /api/stream/{job_id} streams SSE ProgressEvent messages via async generator with 120s timeout
- StubPipeline copies base_2d template, writes dummy GDScript, calls Godot headless export
- 11 tests covering all five PIPE requirements: generate endpoint, SSE streaming, static files, registry, runner

## Task Commits

Each task was committed atomically:

1. **Task 1: FastAPI app, stub pipeline, and registry wiring** - `e59f41a` (test RED), `f532782` (feat GREEN)
2. **Task 2: Test suite for all PIPE requirements** - `295853c` (feat)
3. **Cleanup: Remove redundant scaffold tests** - `bb7e02a` (refactor)

## Files Created/Modified
- `backend/backend/main.py` - FastAPI app with generate/stream endpoints, CORS, StaticFiles mount
- `backend/backend/pipelines/stub/__init__.py` - Stub pipeline subpackage init
- `backend/backend/pipelines/stub/pipeline.py` - StubPipeline: copytree, GDScript injection, Godot export
- `backend/backend/pipelines/registry.py` - Updated with StubPipeline registration
- `backend/backend/tests/__init__.py` - Test package init
- `backend/backend/tests/test_generate.py` - PIPE-01: generate endpoint tests (job_id, UUID4, pipeline param, 400)
- `backend/backend/tests/test_stream.py` - PIPE-02: SSE content-type and event streaming tests
- `backend/backend/tests/test_registry.py` - PIPE-04: registry resolution and unknown pipeline tests
- `backend/backend/tests/test_runner.py` - PIPE-05: file-existence validation and stderr capture tests
- `backend/backend/tests/test_static.py` - PIPE-03: static file serving from /games/ mount

## Decisions Made
- Used `response_class=EventSourceResponse` with async generator pattern instead of manually wrapping `EventSourceResponse(generator())` -- the latter bypasses FastAPI's SSE encoding layer causing `ServerSentEvent.encode()` errors
- All endpoint tests mock `run_headless_export` to avoid requiring Godot binary in test environment
- Path constants in stub pipeline and main.py use `__file__` parent traversal with extra level for nested `backend/backend/` layout

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TEMPLATE_DIR/GAMES_DIR path resolution for nested layout**
- **Found during:** Task 1 (stub pipeline implementation)
- **Issue:** Plan specified `Path(__file__).parent.parent.parent.parent` for repo root, but nested `backend/backend/` layout requires one additional `.parent`
- **Fix:** Changed to `Path(__file__).parent.parent.parent.parent.parent` with `_REPO_ROOT` variable for clarity; same fix applied to `GAMES_DIR` in `main.py`
- **Files modified:** backend/backend/pipelines/stub/pipeline.py, backend/backend/main.py
- **Verification:** Template copytree succeeds, games dir created at repo root
- **Committed in:** f532782 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed SSE streaming pattern from manual wrapping to response_class generator**
- **Found during:** Task 2 (stream tests)
- **Issue:** `EventSourceResponse(event_generator())` treats `ServerSentEvent` as raw chunks and calls `.encode()` which doesn't exist on the Pydantic model. FastAPI's SSE encoding happens in the routing layer only when `response_class=EventSourceResponse` is set.
- **Fix:** Changed stream endpoint from returning `EventSourceResponse(generator())` to using `@app.get(path, response_class=EventSourceResponse)` async generator with `yield`
- **Files modified:** backend/backend/main.py
- **Verification:** test_stream_content_type and test_stream_yields_events both pass
- **Committed in:** 295853c (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correct operation with the nested package layout and FastAPI 0.135.0+ SSE API. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full backend pipeline chain proven end-to-end: job create -> SSE stream -> pipeline run -> static serve
- All PIPE requirements validated with passing tests
- Ready for Phase 3 LLM code generation pipeline to replace StubPipeline

## Self-Check: PASSED

All 9 created/modified files verified on disk. All 4 task commits (e59f41a, f532782, 295853c, bb7e02a) found in git log.

---
*Phase: 02-backend-pipeline-foundation*
*Completed: 2026-03-14*
