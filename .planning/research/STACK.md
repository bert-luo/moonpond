# Stack Research

**Domain:** AI-powered game generation (LLM pipeline + Godot 4 WASM export)
**Researched:** 2026-03-13
**Confidence:** MEDIUM-HIGH (core stack verified; Godot headless flags and Claude model IDs from training data — flag for validation)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Next.js | 15.3 | Frontend framework | Current stable (released Apr 2025, docs updated Feb 2026). PRD says "14" but 15.3 is the right target — app router is stable, streaming via `ReadableStream` works natively, no breaking changes from 14 to 15 for this use case. Use 15 for the keepalive improvements and stable Turbopack dev. |
| TypeScript | 5.x (bundled with Next.js) | Type safety | Next.js ships its own TS version; no separate decision needed. |
| Tailwind CSS | 4.x | Styling | Two-column layout + chat panel styling. Tailwind 4 ships as a PostCSS plugin, zero config. |
| FastAPI | 0.135.1 | Backend API + SSE | Native SSE support landed in 0.135.0 via `fastapi.sse.EventSourceResponse` — no third-party sse-starlette needed. Auto-sets correct headers (Cache-Control: no-cache, X-Accel-Buffering: no, 15s keepalive). Async-first, Python 3.10+. |
| Python | 3.11+ | Backend runtime | 3.10 is minimum for FastAPI 0.135; use 3.11 for better async performance and `tomllib` stdlib. |
| uvicorn | 0.34+ | ASGI server | Standard FastAPI server. Use `uvicorn[standard]` for uvloop + httptools on Linux. |
| anthropic | 0.84.0 | Claude API client | Official SDK; supports streaming via `stream()` context manager, async variants, and `with_streaming_response`. |
| Godot 4.5.1 | 4.5.1-stable | Headless WASM export | Exact version locked by PRD — export presets are version-specific; switching versions breaks them. Linux headless binary + web export templates required. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | 2.x (bundled with FastAPI) | Request/response models, ProgressEvent schema | Use for `ProgressEvent` Pydantic model that gets JSON-serialized into SSE `data:` field automatically by `EventSourceResponse`. |
| anyio | 4.x (FastAPI dep) | Async subprocess, cancellation | Use `anyio.to_thread.run_sync()` to run Godot headless export subprocess without blocking the event loop. Also use `await anyio.sleep(0)` in SSE generators for proper cancellation. |
| aiofiles | 23.x | Async file I/O | Reading generated game files, serving WASM assets. Only if needed — Python's `asyncio` open is sufficient for simple cases. |
| python-multipart | 0.0.12+ | FastAPI form data | Required if accepting any form uploads (probably not needed for this project). |
| react | 19.x (peer of Next.js 15) | UI library | Bundled with Next.js 15; no separate choice. |
| tailwind-merge | 2.x | Conditional class merging | Essential for conditional Tailwind classes in chat panel / game iframe toggle states. |
| clsx | 2.x | Conditional classnames | Pairs with tailwind-merge. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Python package manager + venv | Faster than pip/poetry; lockfile support; already in use across this codebase. Use `uv sync` for reproducible installs. |
| ruff | Python linter + formatter | Replaces black + flake8 + isort in one tool. Already in use in taster project. |
| pytest + pytest-asyncio | Backend testing | `pytest-asyncio` for testing async FastAPI routes and pipeline stages. Set `asyncio_mode = "auto"` in pytest.ini. |
| httpx | HTTP client + async test client | FastAPI's `TestClient` uses it; also use `AsyncClient` for async tests. Required as FastAPI dev dependency. |
| eslint | Frontend linting | Bundled with Next.js `create-next-app`. |
| prettier | Frontend formatting | Standard for TypeScript/JSX. |

## Installation

```bash
# Backend (Python — use uv)
uv init backend
cd backend
uv add fastapi==0.135.1 uvicorn[standard] anthropic pydantic anyio

# Dev dependencies
uv add --dev ruff pytest pytest-asyncio httpx

# Frontend (Node — use npm)
npx create-next-app@15 frontend --typescript --tailwind --app --src-dir
npm install --save-dev tailwind-merge clsx
```

## Godot 4.5.1 Headless Setup

The headless binary and export templates must be installed as part of project setup. These are separate downloads.

```bash
# Download headless binary (Linux x86_64)
# URL pattern: https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_linux.x86_64.zip
wget https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_linux.x86_64.zip
unzip Godot_v4.5.1-stable_linux.x86_64.zip
chmod +x Godot_v4.5.1-stable_linux.x86_64
mv Godot_v4.5.1-stable_linux.x86_64 /usr/local/bin/godot

# Download export templates (required for any export)
# URL pattern: https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_export_templates.tpz
wget https://github.com/godotengine/godot/releases/download/4.5.1-stable/Godot_v4.5.1-stable_export_templates.tpz

# Install export templates to Godot's expected path
mkdir -p ~/.local/share/godot/export_templates/4.5.1.stable
unzip Godot_v4.5.1-stable_export_templates.tpz -d /tmp/godot_templates
mv /tmp/godot_templates/templates/* ~/.local/share/godot/export_templates/4.5.1.stable/
```

**Headless export command** (MEDIUM confidence — flags verified against Godot 4 docs pattern; 4.5.1 not yet released as of research date so exact URL is projected):

```bash
godot --headless --export-release "Web" /path/to/output/index.html --path /path/to/project
```

Key flags:
- `--headless` — no display required; mandatory for server/subprocess use
- `--export-release "Web"` — uses the export preset named "Web" in `export_presets.cfg`; use `--export-debug` for debug builds
- `--path /path/to/project` — absolute path to the Godot project directory (contains `project.godot`)
- Output path must be `.html` — Godot generates `.html`, `.wasm`, `.js`, `.pck` alongside it

**Exit code behavior:** Godot exits 0 on success, non-zero on failure. Capture stderr for error messages — GDScript syntax errors and export failures appear in stderr.

**WASM export prerequisites:**
- The project must have an export preset named "Web" in `export_presets.cfg`
- Export templates for the exact version must be installed (see above)
- The output directory must exist before running the export
- `SharedArrayBuffer` (COOP/COEP headers) is required at serve time for WASM threads — Next.js must set `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` on the page serving the iframe

## SSE Streaming Pattern (FastAPI 0.135+)

FastAPI 0.135 introduced native SSE via `fastapi.sse`. Do NOT use `sse-starlette` (third-party, now superseded).

```python
from collections.abc import AsyncIterable
from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

class ProgressEvent(BaseModel):
    stage: str
    message: str
    progress: float  # 0.0–1.0
    done: bool = False

@app.post("/generate", response_class=EventSourceResponse)
async def generate_game(request: GenerateRequest) -> AsyncIterable[ProgressEvent]:
    pipeline = registry.get(request.pipeline or "default")
    async for event in pipeline.run(request.prompt):
        yield event  # ProgressEvent auto-serialized as JSON in SSE data: field
        await anyio.sleep(0)  # yield to event loop; enables stream cancellation
```

Auto-handled by `EventSourceResponse`:
- `Content-Type: text/event-stream`
- `Cache-Control: no-cache`
- `X-Accel-Buffering: no` (prevents nginx buffering)
- Keep-alive comment every 15 seconds

## Next.js SSE Consumption Pattern

Direct `fetch()` with `ReadableStream` reader is the correct approach for consuming the FastAPI SSE stream from a React client component. Do NOT use the browser's `EventSource` API — it only supports GET with no request body.

```typescript
// app/components/GameGenerator.tsx
'use client'

async function startGeneration(prompt: string, onEvent: (e: ProgressEvent) => void) {
  const response = await fetch('http://localhost:8000/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  })

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const text = decoder.decode(value)
    // SSE format: "data: {...}\n\n"
    for (const line of text.split('\n')) {
      if (line.startsWith('data: ')) {
        const event: ProgressEvent = JSON.parse(line.slice(6))
        onEvent(event)
      }
    }
  }
}
```

Use `useState` + `useCallback` to accumulate events; use `useRef` for the AbortController to cancel in-flight generations.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| FastAPI native SSE (0.135+) | sse-starlette | Never for new projects — native SSE is now built in and officially maintained |
| FastAPI native SSE (0.135+) | WebSockets | If you needed bidirectional communication (not the case here — progress is one-way server→client) |
| fetch() + ReadableStream | Browser EventSource API | If all your SSE endpoints are GET-only with no body — not viable here since we POST the prompt |
| fetch() + ReadableStream | Vercel AI SDK (`useChat`) | If using OpenAI-compatible streaming format throughout — overkill and wrong abstraction for a pipeline progress stream |
| anyio.to_thread.run_sync | asyncio.subprocess directly | asyncio.create_subprocess_exec works fine for Godot if you don't need thread-based cancellation |
| uv | poetry / pip | Use only if the team already has poetry investment — uv is faster and has better lockfile semantics |
| Next.js 15 | Next.js 14 (PRD-specified) | PRD says "14" but 15 is the current release with no migration pain; use 15 unless a specific 14-only package dependency exists |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| sse-starlette | Third-party library now superseded by FastAPI's native `fastapi.sse` in 0.135; adds unnecessary dependency | `from fastapi.sse import EventSourceResponse, ServerSentEvent` |
| EventSource browser API | Only supports GET, no request body — cannot POST the prompt | `fetch()` + `response.body.getReader()` |
| Godot 4 versions other than 4.5.1 | Export presets in `export_presets.cfg` are version-specific — using a different version silently breaks the export pipeline | Godot 4.5.1-stable exactly |
| Godot export without `--headless` | Without `--headless`, Godot tries to open a display; fails on headless servers and blocks in subprocess | Always pass `--headless` flag |
| Python 3.9 | Dropped by FastAPI 0.129.0 — incompatible with current FastAPI | Python 3.11+ |
| Synchronous Godot subprocess call | `subprocess.run()` blocks the entire event loop during ~30-60s export; kills SSE keep-alive and timeouts | `anyio.to_thread.run_sync(subprocess.run, ...)` or `asyncio.create_subprocess_exec` |
| Streaming Godot output line-by-line to SSE | Godot export produces no useful incremental stdout; "progress" events should come from pipeline stage transitions, not Godot I/O | Emit pipeline-level `ProgressEvent`s; wrap Godot export as a single atomic stage |
| next/dynamic with no SSR for the game iframe | The Godot WASM iframe is served from a static file URL, not a React component — no dynamic import needed | Plain `<iframe src={gameUrl} />` in a client component |

## Stack Patterns by Variant

**If the Godot export fails with "Export template not found":**
- The templates are not installed, or are installed under the wrong version string
- Godot looks for templates at `~/.local/share/godot/export_templates/{VERSION}.stable/`
- The VERSION must match exactly: for 4.5.1, the directory must be `4.5.1.stable`

**If WASM game shows blank/black screen in iframe:**
- Missing `Cross-Origin-Opener-Policy` and `Cross-Origin-Embedder-Policy` headers on the serving page
- Add to `next.config.js` `headers()` for the route serving the game files
- Both headers required for `SharedArrayBuffer` which Godot WASM uses for threading

**If SSE stream is buffered (events arrive in bulk, not incrementally):**
- A proxy (nginx, Caddy) is buffering the response
- FastAPI's `EventSourceResponse` sets `X-Accel-Buffering: no` automatically for nginx
- For other proxies, configure response buffering off explicitly

**If pipeline uses Claude for multiple stages:**
- Use `claude-3-5-haiku-20241022` for cheap/fast stages (Prompt Enhancer)
- Use `claude-3-5-sonnet-20241022` (or newer `claude-sonnet-4-6` if available) for quality stages (Code Generator, Visual Polisher)
- Use `anthropic.AsyncAnthropic()` client — not `anthropic.Anthropic()` — for non-blocking calls inside async FastAPI handlers

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| FastAPI 0.135.1 | Starlette >=0.46.0, Python >=3.10 | FastAPI bundles Starlette; no separate install needed |
| FastAPI 0.135.1 | Pydantic >=2.0 | Pydantic v1 support dropped in FastAPI 0.100+ |
| Next.js 15.3 | React 19, Node.js >=18.18 | React 19 is the peer dep — breaking change from React 18 only in Server Components API |
| anthropic 0.84.0 | Python >=3.8, httpx >=0.23 | Async client requires `asyncio` — no extra install |
| Godot 4.5.1 export templates | Godot 4.5.1 binary exactly | Templates from 4.5.0 or 4.4.x will NOT work; Godot validates version match |
| Godot WASM output | Modern browsers with SharedArrayBuffer | Safari 15.2+, Chrome 92+, Firefox 79+; requires COOP/COEP headers to enable |

## Claude Model Names (MEDIUM confidence)

The anthropic SDK release notes referenced `claude-sonnet-4-6` and `claude-opus-4-6` in late 2025 releases, suggesting a new model generation beyond 3.x. Verify exact model IDs from `https://docs.anthropic.com/en/docs/about-claude/models/overview` before first use.

Current best-guess mapping (verify before use):
- **Speed stage (Prompt Enhancer):** `claude-3-5-haiku-20241022` or newer Haiku
- **Quality stage (Code Generator, Visual Polisher):** `claude-3-5-sonnet-20241022` or `claude-sonnet-4-6`

## Sources

- FastAPI 0.135 SSE tutorial — `https://fastapi.tiangolo.com/tutorial/server-sent-events/` — HIGH confidence (official docs, verified)
- FastAPI 0.135 release notes — `https://fastapi.tiangolo.com/release-notes/` — HIGH confidence (official, lists v0.135.1 as latest)
- FastAPI stream-data docs — `https://fastapi.tiangolo.com/advanced/stream-data/` — HIGH confidence (official)
- Next.js 15.3 blog post — `https://nextjs.org/blog/next-15-3` — HIGH confidence (official, April 2025)
- Next.js Route Handlers docs — `https://nextjs.org/docs/app/building-your-application/routing/route-handlers` — HIGH confidence (official, version 16.1.6, Feb 2026)
- anthropic Python SDK releases — GitHub releases page v0.84.0 (Feb 25, 2026) — MEDIUM confidence (from fetched release list)
- Godot 4 headless export flags — MEDIUM confidence (training data; Godot 4.5.1 not yet confirmed released as of research)
- Godot WASM COOP/COEP requirements — MEDIUM confidence (training data, standard WebAssembly threading requirement)
- Claude model names — MEDIUM confidence (training data + SDK release inference; verify against official docs)

---
*Stack research for: AI-powered game generation (Godot 4 + LLM pipeline)*
*Researched: 2026-03-13*
