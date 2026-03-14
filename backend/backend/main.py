"""FastAPI application with generate/stream endpoints and static file serving."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles

from .models.requests import GenerateRequest
from .models.responses import GenerateResponse
from .pipelines.registry import PIPELINES
from .state import active_jobs

app = FastAPI(title="Moonpond")

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Games output directory (runtime only, gitignored)
GAMES_DIR = Path(__file__).parent.parent.parent / "games"
GAMES_DIR.mkdir(exist_ok=True)


@app.post("/api/generate")
async def generate(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    pipeline: str = "stub",
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

    background_tasks.add_task(pipeline_cls().generate, req.prompt, job_id, emit)
    return GenerateResponse(job_id=job_id)


@app.get("/api/stream/{job_id}", response_class=EventSourceResponse)
async def stream(job_id: str):
    """Stream SSE ProgressEvent messages for a running job."""
    if job_id not in active_jobs:
        yield ServerSentEvent(data={"error": "job not found"}, event="error")
        return

    queue = active_jobs[job_id]
    try:
        while True:
            event = await asyncio.wait_for(queue.get(), timeout=120)
            if event is None:
                del active_jobs[job_id]
                return
            yield ServerSentEvent(data=event.model_dump_json(), event=event.type)
    except asyncio.TimeoutError:
        yield ServerSentEvent(data={"error": "stream timeout"}, event="error")
        if job_id in active_jobs:
            del active_jobs[job_id]


# Mount static files AFTER route definitions (defensive ordering)
app.mount("/games", StaticFiles(directory=GAMES_DIR), name="games")
