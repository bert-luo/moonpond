# Phase 2: Backend Pipeline Foundation - Research

**Researched:** 2026-03-14
**Domain:** FastAPI async backend, SSE streaming, asyncio subprocess, pipeline Protocol, static file serving, uv project setup
**Confidence:** HIGH (all core claims verified against official FastAPI docs and Python asyncio docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `POST /api/generate` accepts a prompt body, returns `job_id` immediately (under 100ms), spawns background task
- `GET /api/stream/{job_id}` streams SSE `ProgressEvent` messages with 15-second heartbeat keepalive
- Pipeline selection via query param on generate endpoint (hidden in UI, useful for evaluation)
- `GamePipeline` Protocol with async `generate(prompt, job_id, emit)` → `GameResult` signature
- `emit` is a callback that pushes SSE events to the client
- FastAPI endpoint is pipeline-agnostic — resolves pipeline from registry and calls `generate`
- Registry is a simple dict mapping strategy names to pipeline classes (`pipelines/registry.py`)
- Subprocess wrapper in `backend/godot/runner.py`
- Executes headless export non-blocking (must not freeze FastAPI event loop)
- Captures stderr for error reporting
- Validates output file existence rather than exit code
- Uses Phase 1's base_2d template as source
- Generated games served at `/games/{job_id}/export/`
- Job directory structure: `games/{job_id}/project/` (Godot files) + `games/{job_id}/export/` (WASM output)
- `games/` directory is gitignored, runtime output only
- `ProgressEvent` and `GameResult` as Pydantic models in `backend/models/`
- SSE events are JSON-serialized ProgressEvent objects

### Claude's Discretion
- Async task management approach (asyncio.create_task vs BackgroundTasks vs task queue)
- SSE connection management and cleanup strategy
- Error handling for edge cases (duplicate job IDs, missing jobs, concurrent access)
- Test strategy for async endpoints and SSE streaming
- Heartbeat implementation mechanism (asyncio timer vs middleware)
- Job state storage (in-memory dict vs lightweight store)

### Deferred Ideas (OUT OF SCOPE)
- Single-shot agentic pipeline (future pipeline strategy)
- ROMA multi-agent pipeline (future pipeline strategy)
- Playwright visual feedback loop (future quality signal)
- GDScript self-correction pass (Phase 3 scope, STAGE-06/REL-01)
- 90-second hard timeout with partial result (v2 REL-02)
- User accounts and game persistence
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-01 | Backend exposes `POST /api/generate` that accepts a prompt and returns a `job_id` immediately | FastAPI BackgroundTasks pattern: add_task runs after response is sent; UUID for job_id; asyncio.Queue per job stored in-memory dict |
| PIPE-02 | Backend exposes `GET /api/stream/{job_id}` that streams `ProgressEvent` SSE messages for the job | FastAPI 0.135.0+ native SSE via `EventSourceResponse` + `ServerSentEvent` from `fastapi.sse`; built-in 15s ping; asyncio.Queue consumer pattern |
| PIPE-03 | Backend serves generated WASM files at `/games/{job_id}/export/` as static files | `app.mount("/games", StaticFiles(directory="games"))` using `fastapi.staticfiles.StaticFiles`; requires `aiofiles` package |
| PIPE-04 | Pipeline registry maps strategy names to `GamePipeline` Protocol implementations; active pipeline resolved from request | `typing.Protocol` for `GamePipeline`; plain dict `PIPELINES = {...}` in `pipelines/registry.py`; query param on generate endpoint |
| PIPE-05 | Godot headless runner executes export asynchronously (non-blocking), captures stderr, validates output file existence | `asyncio.create_subprocess_exec` + `communicate()` for non-blocking subprocess; `Path.exists()` for output validation (not exit code); Godot exit codes unreliable |
</phase_requirements>

---

## Summary

Phase 2 builds a FastAPI backend that establishes all the plumbing a pipeline can drive end-to-end: job creation, SSE streaming, Godot headless export, and static file serving. No LLM calls happen here — the stub pipeline copies the base_2d template, writes a dummy GDScript file, runs Godot export, and proves the whole chain works.

The two critical technical decisions left to discretion are (1) task management approach and (2) job state storage. Research points clearly toward `BackgroundTasks.add_task` for simplicity (no external dependencies, task guaranteed to start after response, appropriate for this scale), with per-job `asyncio.Queue` instances stored in an in-memory dict as the event bus between background worker and SSE consumer. For Phase 2 scope (no multi-worker, no persistence), in-memory is correct — the architecture is clean enough that adding Redis queues in future is a single-file change.

FastAPI 0.135.0 added native SSE support via `fastapi.sse.EventSourceResponse` with built-in 15-second keepalive ping, Cache-Control and X-Accel-Buffering headers set automatically — this eliminates any need for the `sse-starlette` third-party package. The asyncio subprocess API (`asyncio.create_subprocess_exec` + `communicate()`) is the correct non-blocking approach for the Godot runner; Godot's headless export exit codes are known-unreliable (GitHub issue #83042), so output file existence is the right validation strategy.

**Primary recommendation:** Use FastAPI built-in SSE (0.135.0+), BackgroundTasks for job spawning, asyncio.Queue per job as event bus, asyncio.create_subprocess_exec for Godot runner, and StaticFiles mount for game serving. Set up the project with `uv` and `pyproject.toml`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| fastapi[standard] | >=0.135.0 | Web framework, SSE, routing, static files, BackgroundTasks | 0.135.0 added native EventSourceResponse — no third-party SSE lib needed |
| uvicorn | latest (bundled with fastapi[standard]) | ASGI server for local dev | Standard runner for FastAPI; hot-reload via `--reload` |
| pydantic | v2 (bundled with fastapi) | `ProgressEvent`, `GameResult`, `GenerateRequest` models | FastAPI uses Pydantic v2 natively; model_dump_json() for SSE serialization |
| aiofiles | latest | Required by FastAPI `StaticFiles` for async file serving | Static file serving dependency; must be installed explicitly |
| python | >=3.12 | Runtime | Protocol structural subtyping works correctly; asyncio subprocess stable |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | latest | Test runner | All test files |
| pytest-anyio | latest | Async test decorator (`@pytest.mark.anyio`) | Testing async FastAPI endpoints |
| httpx | latest | Async HTTP client for tests | `AsyncClient(transport=ASGITransport(app=app))` for endpoint tests |
| anyio | latest | Async backend for pytest-anyio | Automatically pulled in by pytest-anyio |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| fastapi built-in SSE | sse-starlette | sse-starlette adds an external dep for something FastAPI 0.135.0+ provides natively; only use sse-starlette if targeting older FastAPI |
| BackgroundTasks | asyncio.create_task | create_task is leaky without explicit lifecycle management; BackgroundTasks ties task lifespan to request, simpler for this pattern |
| asyncio.Queue (in-memory) | Redis + ARQ | Redis adds infra complexity; in-memory is correct for single-process local MVP; registry pattern makes upgrading a single-file change |
| asyncio.create_subprocess_exec | subprocess.run in executor | create_subprocess_exec is native async and doesn't occupy a thread pool thread; preferred for I/O-bound subprocess |

**Installation:**
```bash
uv add "fastapi[standard]" aiofiles pydantic
uv add --dev pytest pytest-anyio httpx
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── main.py                    # FastAPI app, CORS, StaticFiles mount, route includes
├── pipelines/
│   ├── base.py                # GamePipeline Protocol, ProgressEvent, GameResult
│   ├── registry.py            # PIPELINES dict: name -> pipeline class
│   └── stub/
│       └── pipeline.py        # StubPipeline: copies template, writes dummy .gd, runs export
├── godot/
│   └── runner.py              # run_headless_export(project_path, output_path) -> RunResult
├── models/
│   ├── requests.py            # GenerateRequest Pydantic model
│   └── responses.py           # GenerateResponse (job_id), ProgressEvent, GameResult
└── state.py                   # active_jobs: dict[str, asyncio.Queue[ProgressEvent | None]]
```

### Pattern 1: Job Create + Background Task

**What:** POST endpoint creates job_id, registers queue, spawns background task, returns 200 immediately.
**When to use:** Any request where work takes >100ms and client polls/streams separately.

```python
# Source: https://fastapi.tiangolo.com/tutorial/background-tasks/
# backend/main.py
import asyncio
import uuid
from fastapi import FastAPI, BackgroundTasks
from .state import active_jobs
from .pipelines.registry import PIPELINES
from .models.requests import GenerateRequest
from .models.responses import GenerateResponse

app = FastAPI()

@app.post("/api/generate")
async def generate(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    pipeline: str = "multi_stage",
) -> GenerateResponse:
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    active_jobs[job_id] = queue

    pipeline_cls = PIPELINES.get(pipeline, PIPELINES["stub"])
    pipeline_instance = pipeline_cls()

    async def emit(event):
        await queue.put(event)

    background_tasks.add_task(pipeline_instance.generate, req.prompt, job_id, emit)
    return GenerateResponse(job_id=job_id)
```

### Pattern 2: SSE Stream Consumer

**What:** GET endpoint reads per-job queue, yields SSE events, closes stream on sentinel None.
**When to use:** Any job that needs real-time progress streaming to client.

```python
# Source: https://fastapi.tiangolo.com/tutorial/server-sent-events/
# backend/main.py
from collections.abc import AsyncIterable
from fastapi.sse import EventSourceResponse, ServerSentEvent
from .state import active_jobs
from .models.responses import ProgressEvent

@app.get("/api/stream/{job_id}")
async def stream(job_id: str) -> EventSourceResponse:
    async def event_generator() -> AsyncIterable[ServerSentEvent]:
        if job_id not in active_jobs:
            yield ServerSentEvent(data={"error": "job not found"}, event="error")
            return

        queue = active_jobs[job_id]
        while True:
            event: ProgressEvent | None = await queue.get()
            if event is None:  # sentinel: pipeline completed or errored
                del active_jobs[job_id]
                return
            yield ServerSentEvent(data=event, event=event.type)

    return EventSourceResponse(event_generator())
```

**Built-in behaviors (no code needed):**
- 15-second keepalive ping when queue is idle
- `Cache-Control: no-cache` header
- `X-Accel-Buffering: no` header (prevents Nginx buffering)

### Pattern 3: GamePipeline Protocol

**What:** Structural interface that all pipelines must implement. No inheritance required.
**When to use:** Define once in `base.py`, register concrete classes in `registry.py`.

```python
# Source: https://typing.python.org/en/latest/spec/protocol.html
# backend/pipelines/base.py
from typing import Protocol, Callable, Awaitable
from pydantic import BaseModel

class ProgressEvent(BaseModel):
    type: str        # "stage_start" | "stage_complete" | "error" | "done"
    message: str
    data: dict = {}

class GameResult(BaseModel):
    job_id: str
    wasm_path: str
    controls: list[dict] = []

EmitFn = Callable[[ProgressEvent], Awaitable[None]]

class GamePipeline(Protocol):
    async def generate(
        self,
        prompt: str,
        job_id: str,
        emit: EmitFn,
    ) -> GameResult: ...
```

### Pattern 4: Godot Headless Runner (Non-Blocking)

**What:** Async subprocess wrapper that captures stderr and validates output file existence.
**When to use:** Any time Godot export is needed without blocking the event loop.

```python
# Source: https://docs.python.org/3/library/asyncio-subprocess.html
# backend/godot/runner.py
import asyncio
from pathlib import Path
from dataclasses import dataclass

GODOT_BIN = Path("godot/Godot.app/Contents/MacOS/Godot")

@dataclass
class RunResult:
    success: bool
    stderr: str
    output_path: Path | None

async def run_headless_export(
    project_path: Path,
    output_dir: Path,
    preset_name: str = "Web",
) -> RunResult:
    output_path = output_dir / "index.html"
    output_dir.mkdir(parents=True, exist_ok=True)

    proc = await asyncio.create_subprocess_exec(
        str(GODOT_BIN),
        "--headless",
        "--path", str(project_path),
        "--export-release", preset_name, str(output_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr_bytes = await proc.communicate()
    stderr = stderr_bytes.decode(errors="replace") if stderr_bytes else ""

    # Godot exit codes are unreliable (issue #83042) — validate file existence instead
    success = output_path.exists()
    return RunResult(
        success=success,
        stderr=stderr,
        output_path=output_path if success else None,
    )
```

### Pattern 5: Static File Serving for Runtime Output

**What:** Mount the `games/` directory as a static file server after games are written.
**When to use:** After Godot export produces WASM files, frontend iframes need to load them.

```python
# Source: https://fastapi.tiangolo.com/tutorial/static-files/
# backend/main.py
from fastapi.staticfiles import StaticFiles
from pathlib import Path

GAMES_DIR = Path("games")
GAMES_DIR.mkdir(exist_ok=True)

app.mount("/games", StaticFiles(directory=GAMES_DIR), name="games")
```

Note: `StaticFiles` serves from the directory as it exists at request time — files written by background tasks are immediately available. No restart needed.

### Pattern 6: Stub Pipeline (End-to-End Proof)

**What:** Minimal GamePipeline implementation that proves the full chain works.
**When to use:** Phase 2 only — replaced by MultiStagePipeline in Phase 3.

```python
# backend/pipelines/stub/pipeline.py
import shutil
from pathlib import Path
from ..base import GamePipeline, ProgressEvent, GameResult, EmitFn
from ...godot.runner import run_headless_export

TEMPLATE_DIR = Path("godot/templates/base_2d")
GAMES_DIR = Path("games")

class StubPipeline:
    async def generate(self, prompt: str, job_id: str, emit: EmitFn) -> GameResult:
        await emit(ProgressEvent(type="stage_start", message="Setting up project..."))

        project_dir = GAMES_DIR / job_id / "project"
        export_dir = GAMES_DIR / job_id / "export"

        # Copy template
        shutil.copytree(TEMPLATE_DIR, project_dir)

        # Write dummy GDScript to prove file injection works
        (project_dir / "scripts" / "generated_main.gd").write_text(
            'extends Node\nfunc _ready(): print("stub pipeline job: %s")' % job_id
        )

        await emit(ProgressEvent(type="stage_start", message="Building for web..."))

        result = await run_headless_export(project_dir, export_dir)
        if not result.success:
            await emit(ProgressEvent(type="error", message="Export failed", data={"stderr": result.stderr}))
            raise RuntimeError(f"Godot export failed: {result.stderr[:500]}")

        await emit(ProgressEvent(type="done", message="Your game is ready."))
        # Sentinel to close SSE stream
        await emit(None)

        return GameResult(job_id=job_id, wasm_path=f"/games/{job_id}/export/index.html")
```

### Pattern 7: CORS Middleware for Frontend

**What:** Enable Cross-Origin requests from Next.js dev server.
**When to use:** Always — frontend runs on :3000, backend runs on :8000.

```python
# backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### Anti-Patterns to Avoid

- **Blocking subprocess call in async handler:** `subprocess.run(...)` inside `async def` blocks the entire event loop. Always use `asyncio.create_subprocess_exec`.
- **Validating Godot export by exit code:** Godot 4 returns 0 even on export failure (GitHub issue #83042). Always check `output_path.exists()`.
- **Storing asyncio.Queue across event loops:** Queue objects are loop-specific. Always create them inside a running event loop (inside an `async def` function, not at module level).
- **Calling `put_nowait` from background thread:** If any pipeline code ever calls a stdlib thread, use `loop.call_soon_threadsafe(queue.put_nowait, event)` instead.
- **Mounting StaticFiles before `games/` dir exists:** Call `GAMES_DIR.mkdir(exist_ok=True)` before `app.mount(...)` to avoid startup errors.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE formatting + keepalive | Custom StreamingResponse with manual `data: ...\n\n` formatting | `fastapi.sse.EventSourceResponse` | Built-in handles keepalive, cache headers, proxy buffering headers, W3C spec format |
| Async subprocess | `subprocess.run` in `asyncio.run_in_executor` | `asyncio.create_subprocess_exec` | Native async, no thread pool usage, cleaner API, communicate() prevents deadlocks |
| Static file serving | Custom route that reads files with aiofiles | `fastapi.staticfiles.StaticFiles` | Handles content-type, etag, range requests, 304 caching automatically |
| UUID generation | Custom ID scheme | `uuid.uuid4()` | Collision-proof, URL-safe string representation, zero dependencies |
| Request/response validation | Manual dict parsing | Pydantic BaseModel | Type coercion, error messages, JSON serialization via model_dump_json() |

**Key insight:** FastAPI's stdlib-integration is deep. The primitive building blocks (SSE, static files, background tasks, subprocess) are all either in the framework or Python stdlib — reaching for external packages in Phase 2 is a sign of searching in the wrong place.

---

## Common Pitfalls

### Pitfall 1: SSE Connection Closes Before Job Completes

**What goes wrong:** Client connects to `/api/stream/{job_id}` before background task has started or put anything in the queue. `queue.get()` blocks forever if the job silently fails without putting a sentinel.
**Why it happens:** Background task starts after response is sent; timing gap between job creation and first emit.
**How to avoid:** Always put a sentinel (`None`) in the queue in both success and error paths of the pipeline. Add a timeout to `queue.get()` (e.g., `asyncio.wait_for(queue.get(), timeout=120)`) and yield a timeout error event.
**Warning signs:** SSE stream hangs with no events after job is known to have completed.

### Pitfall 2: asyncio.Queue Created at Module Level

**What goes wrong:** `RuntimeError: Attached to a different event loop` or `no running event loop`.
**Why it happens:** `asyncio.Queue()` captures the running event loop at creation time. Creating at module import time (before uvicorn starts the event loop) produces a queue bound to no loop or a test loop.
**How to avoid:** Always create `asyncio.Queue()` inside an `async def` function (inside the request handler). The `active_jobs` dict is created at module level but the Queue values are created inside the async handler.
**Warning signs:** Queue operations raise RuntimeError or behave unexpectedly in tests.

### Pitfall 3: Godot Export Blocks Event Loop

**What goes wrong:** Godot export takes 10-60 seconds. Using `subprocess.run(...)` or `subprocess.Popen(...).wait()` inside `async def` freezes the entire FastAPI server — no other requests can be processed.
**Why it happens:** Synchronous blocking calls inside async functions block the event loop thread.
**How to avoid:** Always use `asyncio.create_subprocess_exec` + `await proc.communicate()`.
**Warning signs:** Other requests timeout during an export; uvicorn logs show no activity during export.

### Pitfall 4: shutil.copytree Blocks Event Loop

**What goes wrong:** Copying the base_2d template (many small files) takes measurable wall time and blocks the event loop.
**Why it happens:** `shutil.copytree` is synchronous and runs on the event loop thread.
**How to avoid:** For Phase 2, `shutil.copytree` in a BackgroundTask is acceptable (background task runs in the same event loop but after response is sent — the client won't observe the block). If this becomes a concern, wrap with `asyncio.to_thread(shutil.copytree, src, dst)`.
**Warning signs:** Server unresponsive to other requests immediately after job creation.

### Pitfall 5: StaticFiles Path Relative to Working Directory

**What goes wrong:** `StaticFiles(directory="games")` fails if uvicorn is started from a different working directory than expected.
**Why it happens:** Relative paths resolve against `os.getcwd()` at startup, not the file's location.
**How to avoid:** Use absolute paths: `StaticFiles(directory=Path(__file__).parent.parent / "games")`.
**Warning signs:** `StaticFiles` raises `RuntimeError: Directory does not exist` on startup.

### Pitfall 6: Duplicate Job ID / Race Condition

**What goes wrong:** Two concurrent requests produce the same job_id (shouldn't happen with UUID4, but the queue overwrite could cause one job's events to be dropped).
**Why it happens:** UUID4 collision is astronomically unlikely; but re-submission of same prompt doesn't deduplicate.
**How to avoid:** `uuid.uuid4()` is sufficient collision protection. No deduplication needed for Phase 2 — each request gets a fresh UUID regardless of prompt.

---

## Code Examples

Verified patterns from official sources:

### pyproject.toml for uv + FastAPI

```toml
# Source: https://docs.astral.sh/uv/guides/integration/fastapi/
[project]
name = "moonpond-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi[standard]>=0.135.0",
    "aiofiles",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-anyio",
    "httpx",
    "anyio",
]

[tool.uv.scripts]
dev = "uvicorn backend.main:app --reload --port 8000"
```

### Async Test for POST /api/generate

```python
# Source: https://fastapi.tiangolo.com/advanced/async-tests/
# tests/test_generate.py
import pytest
from httpx import ASGITransport, AsyncClient
from backend.main import app

@pytest.mark.anyio
async def test_generate_returns_job_id():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.post("/api/generate", json={"prompt": "a space shooter"})
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert len(data["job_id"]) == 36  # UUID4 string length
```

### State Module

```python
# backend/state.py
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models.responses import ProgressEvent

# Keyed by job_id; value is Queue of ProgressEvent or None (sentinel)
active_jobs: dict[str, asyncio.Queue] = {}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| sse-starlette (third-party) | fastapi.sse.EventSourceResponse (built-in) | FastAPI 0.135.0 (2024) | No external SSE dependency needed |
| `subprocess.run` in executor | `asyncio.create_subprocess_exec` | Python 3.8+ | Native async subprocess, no thread pool needed |
| Flask + gevent for SSE | FastAPI async generators | 2020+ | Proper async without greenlet hacks |
| BackgroundTasks for heavy work | ARQ/Celery for distributed | Always | BackgroundTasks is in-process; fine for single-server local MVP |

**Deprecated/outdated:**
- `sse-starlette`: Still works and is maintained (v3.3.2, Feb 2026) but is no longer needed for new FastAPI 0.135.0+ projects. sse-starlette remains useful if targeting older FastAPI or needing thread-safe multi-loop support.
- `asyncio.get_event_loop()`: Deprecated; use `asyncio.get_running_loop()` inside async context.

---

## Open Questions

1. **Godot binary path strategy**
   - What we know: Phase 1 uses `godot/Godot.app/Contents/MacOS/Godot` on macOS (from Phase 1 research)
   - What's unclear: Should the runner discover the path dynamically (env var, config file) or hard-code it?
   - Recommendation: Use a `GODOT_BIN` constant read from env var with fallback to known path; keeps CI/server override easy

2. **emit callback is async or sync?**
   - What we know: The pipeline Protocol has `emit: Callable[[ProgressEvent], Awaitable[None]]` — it's async
   - What's unclear: BackgroundTasks runs the background function; if `generate` is `async def`, does it run on the event loop?
   - Recommendation: BackgroundTasks supports `async def` tasks — they run on the same event loop. The `emit` callback putting to `asyncio.Queue` is correct and safe.

3. **SSE stream cleanup when client disconnects early**
   - What we know: FastAPI SSE generator will raise `asyncio.CancelledError` when client disconnects
   - What's unclear: The background pipeline task continues running even after client disconnects (queue fills with no consumer)
   - Recommendation: Track the background task reference; on SSE disconnect (CancelledError), cancel the task and clean up `active_jobs`. For Phase 2 stub this is a nice-to-have, not blocking.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-anyio |
| Config file | `backend/pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — see Wave 0 |
| Quick run command | `uv run pytest backend/tests/ -x -q` |
| Full suite command | `uv run pytest backend/tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | POST /api/generate returns 200 with job_id under 100ms | unit | `uv run pytest backend/tests/test_generate.py::test_generate_returns_job_id -x` | Wave 0 |
| PIPE-01 | job_id is a valid UUID4 string | unit | `uv run pytest backend/tests/test_generate.py::test_job_id_is_uuid -x` | Wave 0 |
| PIPE-02 | GET /api/stream/{job_id} returns 200 with text/event-stream content-type | unit | `uv run pytest backend/tests/test_stream.py::test_stream_content_type -x` | Wave 0 |
| PIPE-02 | SSE stream yields ProgressEvent messages emitted by pipeline | unit | `uv run pytest backend/tests/test_stream.py::test_stream_yields_events -x` | Wave 0 |
| PIPE-03 | /games/{job_id}/export/ serves index.html after export | integration | `uv run pytest backend/tests/test_static.py::test_static_file_served -x` | Wave 0 |
| PIPE-04 | Registry resolves "stub" to StubPipeline | unit | `uv run pytest backend/tests/test_registry.py::test_registry_resolves_stub -x` | Wave 0 |
| PIPE-04 | generate endpoint selects pipeline from query param | unit | `uv run pytest backend/tests/test_generate.py::test_pipeline_query_param -x` | Wave 0 |
| PIPE-05 | runner returns RunResult.success=False when output file missing | unit | `uv run pytest backend/tests/test_runner.py::test_runner_validates_file_not_exit_code -x` | Wave 0 |
| PIPE-05 | runner captures stderr from subprocess | unit | `uv run pytest backend/tests/test_runner.py::test_runner_captures_stderr -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest backend/tests/ -x -q`
- **Per wave merge:** `uv run pytest backend/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/__init__.py` — marks tests as package
- [ ] `backend/tests/test_generate.py` — covers PIPE-01
- [ ] `backend/tests/test_stream.py` — covers PIPE-02
- [ ] `backend/tests/test_static.py` — covers PIPE-03
- [ ] `backend/tests/test_registry.py` — covers PIPE-04
- [ ] `backend/tests/test_runner.py` — covers PIPE-05 (mock subprocess for unit tests)
- [ ] `backend/pytest.ini` or `pyproject.toml [tool.pytest.ini_options]` — asyncio_mode = "auto" or anyio config
- [ ] Framework install: `uv add --dev pytest pytest-anyio httpx anyio`

---

## Sources

### Primary (HIGH confidence)
- https://fastapi.tiangolo.com/tutorial/server-sent-events/ — SSE built-in EventSourceResponse, ServerSentEvent, 0.135.0 version, 15s keepalive
- https://fastapi.tiangolo.com/tutorial/background-tasks/ — BackgroundTasks.add_task pattern, async def support
- https://fastapi.tiangolo.com/tutorial/static-files/ — StaticFiles mount pattern
- https://fastapi.tiangolo.com/advanced/async-tests/ — AsyncClient + ASGITransport + pytest.mark.anyio test pattern
- https://docs.python.org/3/library/asyncio-subprocess.html — create_subprocess_exec, communicate(), PIPE constants
- https://docs.astral.sh/uv/guides/integration/fastapi/ — uv + FastAPI pyproject.toml setup

### Secondary (MEDIUM confidence)
- https://dev.to/zachary62/build-an-llm-web-app-in-python-from-scratch-part-4-fastapi-background-tasks-sse-21g4 — Complete BackgroundTasks + asyncio.Queue + SSE producer/consumer pattern; verified against official FastAPI docs
- https://github.com/godotengine/godot/issues/83042 — Godot headless export returns exit code 0 on failure; validates "check file existence not exit code" requirement from CONTEXT.md

### Tertiary (LOW confidence)
- None — all critical claims verified against official sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — fastapi[standard]>=0.135.0, aiofiles, pydantic v2 all verified from official docs
- Architecture: HIGH — SSE, BackgroundTasks, asyncio.Queue, asyncio.create_subprocess_exec all from official sources
- Pitfalls: HIGH — most pitfalls derived from official documentation caveats and confirmed GitHub issues; asyncio.Queue event loop pitfall is official Python docs behavior
- Test patterns: HIGH — pytest-anyio + AsyncClient pattern from official FastAPI async testing docs

**Research date:** 2026-03-14
**Valid until:** 2026-06-14 (stable ecosystem; FastAPI changes slowly; 90-day window)
