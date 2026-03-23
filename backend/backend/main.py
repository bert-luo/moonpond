"""FastAPI application with generate/stream endpoints and static file serving."""

from __future__ import annotations

import asyncio
import io
import uuid
import zipfile
from pathlib import Path

from dotenv import load_dotenv

# Load .env from repo root (one level above backend/)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .models.requests import GenerateRequest
from .models.responses import GenerateResponse
from .pipelines.base import ProgressEvent, SoftTimeout
from .pipelines.registry import PIPELINES
from .state import active_jobs

SOFT_TIMEOUT_S: float = 900
"""Seconds before the pipeline receives a soft-stop signal."""

HEARTBEAT_INTERVAL_S: int = 15
"""Seconds between SSE heartbeat comments when the pipeline queue is idle."""

app = FastAPI(title="Moonpond")

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class COOPCOEPMiddleware(BaseHTTPMiddleware):
    """Inject cross-origin isolation headers on /games/* responses.

    Required for Godot WASM SharedArrayBuffer support in iframes.
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/games/"):
            response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
            response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
            response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
            response.headers["Access-Control-Allow-Origin"] = "*"
        return response


app.add_middleware(COOPCOEPMiddleware)

# Games output directory (runtime only, gitignored)
GAMES_DIR = Path(__file__).parent.parent.parent / "games"
GAMES_DIR.mkdir(exist_ok=True)


@app.post("/api/generate")
async def generate(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    pipeline: str = "agentic",
) -> GenerateResponse:
    """Create a new game generation job and return job_id immediately."""
    job_id = str(uuid.uuid4())

    # Create queue inside async handler (Pitfall 2: avoid module-level Queue)
    queue: asyncio.Queue = asyncio.Queue()
    active_jobs[job_id] = queue

    pipeline_cls = PIPELINES.get(pipeline)
    if pipeline_cls is None:
        del active_jobs[job_id]
        raise HTTPException(
            status_code=400,
            detail=f"Unknown pipeline '{pipeline}'. Available: {', '.join(sorted(PIPELINES))}",
        )

    async def emit(event):
        await queue.put(event)

    soft_timeout = SoftTimeout(SOFT_TIMEOUT_S)

    # Build pipeline instance — pass thinking flag for AgenticPipeline
    init_kwargs: dict = {}
    if pipeline == "agentic" and req.thinking:
        init_kwargs["thinking"] = True
    pipeline_instance = pipeline_cls(**init_kwargs)

    async def run_pipeline():
        soft_timeout.start()
        try:
            await pipeline_instance.generate(
                req.prompt,
                job_id,
                emit,
                save_intermediate=req.save_intermediate,
                soft_timeout=soft_timeout,
            )
        except Exception as exc:
            # Pipeline should emit its own error, but catch anything that slips through
            try:
                await emit(ProgressEvent(type="error", message=str(exc)))
            except Exception:
                pass  # queue may already be dead
        finally:
            soft_timeout.cancel()
            # Always send sentinel so the SSE stream terminates
            try:
                await queue.put(None)
            except Exception:
                pass

    background_tasks.add_task(run_pipeline)
    return GenerateResponse(job_id=job_id)


@app.get("/api/stream/{job_id}", response_class=EventSourceResponse)
async def stream(job_id: str):
    """Stream SSE ProgressEvent messages for a running job."""
    if job_id not in active_jobs:
        from .pipelines.base import ProgressEvent

        not_found = ProgressEvent(type="error", message="Job not found")
        yield ServerSentEvent(raw_data=not_found.model_dump_json(), event="error")
        return

    queue = active_jobs[job_id]
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_S)
        except asyncio.TimeoutError:
            yield ServerSentEvent(comment="ping")
            continue
        if event is None:
            active_jobs.pop(job_id, None)
            return
        yield ServerSentEvent(raw_data=event.model_dump_json(), event=event.type)


@app.get("/api/export/{game_dir_name}")
async def export_game(game_dir_name: str):
    """Zip the export directory for a completed game and return it as a download."""
    game_dir = GAMES_DIR / game_dir_name
    if not game_dir.is_dir():
        raise HTTPException(status_code=404, detail="Game not found")
    export_dir = game_dir / "export"
    if not export_dir.is_dir():
        raise HTTPException(status_code=404, detail="Export not ready")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in export_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(export_dir))
    buf.seek(0)

    filename = game_dir.name + ".zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Mount static files AFTER route definitions (defensive ordering)
app.mount("/games", StaticFiles(directory=GAMES_DIR), name="games")
