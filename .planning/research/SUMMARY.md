# Project Research Summary

**Project:** Moonpond
**Domain:** AI-powered prompt-to-playable-game pipeline (Godot 4 + LLM + WASM)
**Researched:** 2026-03-13
**Confidence:** MEDIUM (Godot 4.5.1 exact release details and Claude model IDs need live validation; core patterns are HIGH confidence)

## Executive Summary

Moonpond is an AI-powered game generator: a user submits a text prompt and receives a browser-playable Godot 4 game exported as WASM. The system is built on a multi-stage LLM pipeline (Next.js frontend + FastAPI backend + Godot 4.5.1 headless) where each pipeline stage has a typed Pydantic input/output contract, progress events are streamed to the browser via SSE, and the entire visual quality differentiator depends on a pre-authored Godot project template (shader library, color palettes, particle scenes) that the LLM references but never generates from scratch. The closest competitor is Rosebud AI (Phaser.js, 2D only); Moonpond's differentiation is Godot 4 fidelity, visual polish as a first-class pipeline stage, and browser WASM export from a real game engine.

The recommended architecture is a clean separation between protocol-defined pipeline strategies (swappable via a registry), independently-testable stage modules with typed contracts, and a Godot template that provides infrastructure but no gameplay nodes. The SSE streaming pattern uses a POST-to-generate / GET-to-stream job model (not a single streaming endpoint) so the pipeline runs as a background task decoupled from the HTTP connection. The most critical non-code decision is the Godot template design: it must be minimal enough to not over-constrain the LLM across diverse game genres, but complete enough to provide pre-validated export presets, input action maps, shader resources, and palette assets.

The key risks are: (1) Godot headless export is a black box with unreliable exit codes — output validation is mandatory; (2) LLMs default to Godot 3 GDScript syntax, which must be actively suppressed in system prompts; (3) the WASM embed requires COOP/COEP HTTP headers that are easy to miss until browser testing; and (4) the self-correction loop for GDScript syntax errors can diverge if it lacks the original game design spec as context. All four risks have clear mitigations that must be built from day one, not added after the pipeline works.

## Key Findings

### Recommended Stack

The backend is FastAPI 0.135.1+ (native SSE via `fastapi.sse.EventSourceResponse` — no third-party `sse-starlette`), Python 3.11+, `anthropic` SDK 0.84.0, and `anyio` for non-blocking Godot subprocess execution. The frontend is Next.js 15.3 with TypeScript and Tailwind 4, consuming SSE via `fetch()` + `ReadableStream` (not the browser `EventSource` API — which only supports GET). Godot 4.5.1 exact version is locked by the export preset format; the headless binary and export templates must match to the patch version.

**Core technologies:**
- **Next.js 15.3:** Frontend framework — app router stable, native streaming, Turbopack dev; upgrade from PRD-specified 14 is painless and recommended
- **FastAPI 0.135.1:** Backend + SSE — native `EventSourceResponse` eliminates third-party dependency; async-first; auto-sets CORS/cache headers
- **anthropic 0.84.0:** Claude API client — `AsyncAnthropic` for non-blocking calls inside async handlers; use Haiku for fast stages, Sonnet for quality stages
- **Godot 4.5.1-stable:** Headless WASM exporter — exact version lock required; `--headless --export-release "Web"` CLI; binary + export templates must match
- **anyio / asyncio.create_subprocess_exec:** Non-blocking Godot subprocess — `subprocess.run()` would block the SSE event loop for 20-60s during export
- **uv:** Python package manager — faster than pip/poetry, lockfile semantics, already in use across this codebase

### Expected Features

**Must have (table stakes):**
- Text prompt input — core interaction; single textarea
- Streaming progress with named stages — users abandon without feedback during 30-90s generation
- Playable WASM game in browser iframe — the entire value proposition
- GDScript self-correction pass — without it, export failure rate is too high to demo
- Error states surfaced to user (timeout, LLM failure, export failure) — silent failure destroys trust
- 90s hard timeout with user-visible message — prevents zombie requests
- Controls legend rendered in chat panel — players cannot discover keybindings from inside a WASM canvas
- Game responds to input — a game that cannot be controlled is not a game

**Should have (competitive differentiators):**
- Applied shader library (glow, scanlines, pixel art, outline) — visual character without LLM shader generation
- Curated color palettes — cohesive look; extremely high ROI relative to implementation cost
- Particle effects (pickups, explosions, ambient) — "juice" that makes games feel alive
- Streaming progress UX with human-readable stage labels — sets expectation of multi-step creative process; differentiates from Rosebud's single bar
- GDScript self-correction loop — Rosebud has similar internally; making it explicit is a trust signal
- 3D game support via base_3d template (v1.x) — Godot 4's 3D WASM is viable; no 2D-only competitor offers this

**Defer to v2+:**
- In-browser code editor — large scope; validate that users prefer re-generation over editing first
- Iterative chat refinement — state management complexity; re-prompting from scratch covers 80% of cases
- User accounts and game persistence — auth infrastructure; validate generation quality first
- Audio / sound effects pipeline stage — silence is acceptable for v1
- Game gallery and sharing — requires accounts + CDN
- Image-to-game prompting — multimodal pipeline; text-only covers the v1 hypothesis

### Architecture Approach

The system is structured as a two-tier async application: a Next.js frontend proxies all requests to a FastAPI backend that owns pipeline execution, SSE streaming, and static file serving of WASM exports. The pipeline is strategy-pattern: a `GamePipeline` Protocol defines the interface, a registry dict maps names to concrete classes, and the API layer never imports pipeline implementations directly. Stage modules are simple async functions with Pydantic-typed inputs and outputs — they are independently testable and swappable. All Godot subprocess complexity is isolated behind `godot/runner.py`; no stage calls subprocess directly.

**Major components:**
1. **ChatPanel (frontend)** — SSE consumer, prompt form, progress message stream, controls legend on completion
2. **GameViewer (frontend)** — iframe + loading skeleton state machine; replaces src only on successful completion event
3. **FastAPI API layer** — job_id generation, asyncio.Queue per job, background task wiring, SSE drain endpoint, static WASM file serving
4. **Pipeline Registry + GamePipeline Protocol** — decouples API from concrete pipeline implementations; enables A/B testing via query param
5. **Stage modules (prompt_enhancer, game_designer, code_generator, visual_polisher, exporter)** — each owns a bounded LLM call with typed Pydantic I/O; sequentially composed by MultiStagePipeline
6. **Godot headless runner (runner.py)** — `asyncio.create_subprocess_exec`, stderr capture, 90s timeout, output validation
7. **Godot templates (base_2d, base_3d)** — pre-authored valid projects with shader library, palettes, particles, export presets; copied per job, never mutated

### Critical Pitfalls

1. **Godot export template version mismatch** — Lock binary and templates to the same release in one setup script; assert `godot --headless --version` at server startup; a mismatch produces broken WASM silently with exit code 0
2. **LLM generates Godot 3 GDScript** — Explicitly forbid Godot 3 patterns by name in the Code Generator system prompt (`yield()`, string-form `connect()`, `KinematicBody2D`); run `--check-only` lint before full export
3. **WASM requires COOP/COEP headers** — `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` must be set on all routes serving game files; without them `SharedArrayBuffer` is disabled and the game shows a blank screen
4. **Self-correction loop diverges** — Always include the original game design spec in the correction context, not just the error and the broken code; cap at 2 correction attempts; treat >30% code rewrite as a failure requiring reset
5. **Template over-constrains LLM** — Templates must provide infrastructure (export presets, input map, shader resources) but NO gameplay nodes; test against 5 diverse genres before locking the template structure
6. **Input action name mismatch** — Include the exact list of pre-defined input action names in the Code Generator system prompt; add post-generation validation that checks all `is_action_pressed` calls against the allowed set; failure is silent (controls appear unresponsive with no runtime error)

## Implications for Roadmap

Based on the dependency graph in ARCHITECTURE.md and the pitfall-to-phase mapping in PITFALLS.md, the natural build order has a hard gating constraint: the Godot template must export cleanly to WASM before any pipeline work can be validated end-to-end.

### Phase 1: Project Scaffold and Godot Template Foundation

**Rationale:** The Godot template is the single highest-leverage design decision in the project. If the template structure is wrong (over-constrained, wrong input actions, broken export preset), every subsequent phase is built on a broken foundation. This phase gates all pipeline work. Template correctness must be verified with a real headless export before writing pipeline code.

**Delivers:** Monorepo structure (frontend/, backend/, games/), Godot 4.5.1 binary setup script, base_2d template that exports a clean blank WASM, shader library committed to template, palette resources, particle scene library, confirmed COOP/COEP headers on dev server, placeholder FastAPI and Next.js app shells.

**Addresses:** Table stakes "game responds to input" (input map pre-defined), differentiator "visual polish" (shader/palette/particle assets).

**Avoids:** Export template version mismatch (Pitfall 1), template over-constrains LLM (Pitfall 5), input action name mismatch (Pitfall 10), LLM-generated `export_presets.cfg` (Architecture anti-pattern 5).

**Research flag:** Needs validation — Godot 4.5.1 exact headless CLI flags and export template installation path must be confirmed against the live release. The headless command pattern is MEDIUM confidence in STACK.md.

### Phase 2: Backend Pipeline Foundation (Types, Registry, SSE, Runner)

**Rationale:** All stage modules depend on shared Pydantic types (ProgressEvent, GameResult, GameDesign, etc.) and the pipeline infrastructure (registry, Protocol, background task wiring, SSE endpoint, Godot runner). Building this foundation before stages means stages can be developed and tested in isolation with proper typed contracts from the start.

**Delivers:** `GamePipeline` Protocol and `ProgressEvent`/`GameResult` types in models/, pipeline registry skeleton, `godot/runner.py` with asyncio subprocess + timeout + output validation, POST /generate endpoint with background task and asyncio.Queue wiring, GET /stream/{job_id} SSE endpoint with heartbeat, static file serving for WASM exports.

**Addresses:** Table stakes "streaming progress UX" (SSE endpoint), "error states surfaced" (typed error event), "90s timeout" (asyncio.wait_for on pipeline).

**Avoids:** Blocking FastAPI event loop (Architecture anti-pattern 4), SSE connection drops silently (Pitfall 6 — heartbeat from day one), headless export silent failure (Pitfall 7 — output validation in runner), synchronous Godot subprocess (Performance trap 1).

**Research flag:** Standard patterns — FastAPI SSE, asyncio.Queue, Protocol registry are well-documented. No additional research needed.

### Phase 3: Multi-Stage Pipeline (All 5 Stages, Self-Correction, End-to-End)

**Rationale:** With typed foundation and runner in place, the five stage modules can be built in dependency order (prompt_enhancer → game_designer → code_generator → visual_polisher → exporter) and wired into MultiStagePipeline. The self-correction loop belongs here, not as a later add-on, because it directly affects whether end-to-end testing produces playable games. This phase ends with a command-line end-to-end test (prompt → WASM) before any frontend work.

**Delivers:** All 5 stage modules with typed Pydantic I/O, MultiStagePipeline wiring, GDScript self-correction pass (2 retries max, includes game design spec in context), prompt engineering per stage (with Godot 4 syntax cheat sheet and explicit Godot 3 prohibition), end-to-end test: CLI prompt-in → WASM-out.

**Addresses:** Table stakes "multi-stage pipeline", "GDScript self-correction", differentiator "visual polish stages", differentiator "template-enforced structure".

**Avoids:** LLM generates Godot 3 GDScript (Pitfall 2 — system prompt), self-correction loop diverges (Pitfall 4 — game design spec in context + retry cap), context budget exhaustion (Pitfall 8 — instrument token usage from first LLM call, set max_tokens per stage), input action name mismatch (Pitfall 10 — post-generation validator), prompt injection (Pitfall 9 — Prompt Enhancer as sanitization barrier).

**Research flag:** Needs phase research — optimal system prompt structure for Godot 4 code generation, Anthropic structured output via tool_use for GameDesign model, and Claude model selection (verify exact model IDs against live Anthropic docs — MEDIUM confidence in STACK.md). This phase is the highest implementation uncertainty.

### Phase 4: Frontend and Full Integration

**Rationale:** The frontend depends on a working SSE backend (Phase 2) and a working pipeline (Phase 3). Building it last means the SSE event contract is stable and the frontend can be tested against real pipeline output rather than mocks. This phase also resolves the COOP/COEP headers in the Next.js config for the real iframe embed.

**Delivers:** Two-column Next.js layout, ChatPanel with SSE `fetch()`+ReadableStream consumer, progressive message stream UI, GameViewer iframe with loading skeleton state machine, prompt input form wired to POST /api/generate, controls legend rendered on completion event, error state UX (typed error categories shown to user), prompt history in session.

**Addresses:** All table stakes UX features, "streaming progress with stage labels" differentiator.

**Avoids:** WASM COOP/COEP headers (Pitfall 3 — Next.js headers() config), iframe sandbox over-restriction (Integration gotcha), Next.js SSE route caching (Pitfall — `export const dynamic = 'force-dynamic'`), WASM MIME type (Integration gotcha — `application/wasm` in next.config.js), keeping previous game visible until new one succeeds (UX pitfall).

**Research flag:** Standard patterns — Next.js App Router, Tailwind, React state management are well-documented. COOP/COEP header configuration in Next.js may need verification.

### Phase 5: Polish, Prompt Engineering Tuning, and Evaluation

**Rationale:** The first end-to-end working system will have rough prompt engineering. This phase is dedicated to evaluating generation quality across a diverse prompt set, tuning stage system prompts, and verifying all the "looks done but isn't" checklist items from PITFALLS.md.

**Delivers:** Evaluation against a test prompt set (5+ genres), tuned system prompts per stage, verified "looks done but isn't" checklist, generation speed profiling (is 90s budget realistic?), cleanup script for generated files (TTL-based disk management).

**Addresses:** Generation quality, error rate reduction, visual consistency of output.

**Research flag:** No additional research needed — this is empirical tuning against real output.

### Phase 6 (v1.x): 3D Support and Quality-of-Life

**Rationale:** Once base_2d pipeline is stable and consistently producing quality output, add the high-wow-factor features that have clear implementation paths but were deferred to not block the core loop.

**Delivers:** base_3d template (toon shader, lighting pre-configured), 3D game support in pipeline, "Download project" zip endpoint, prompt hint/suggestion system.

**Addresses:** Differentiator "3D game support", anti-feature "download project zip" promoted to v1.x.

**Research flag:** 3D Godot WASM export constraints may need research — Godot 4 3D in WASM is viable per FEATURES.md but complexity is rated HIGH.

### Phase Ordering Rationale

- **Template before pipeline:** The architecture research explicitly identifies Phase 2 (Godot template, in their phase numbering) as the "hardest gating dependency." A broken template cannot be fixed after the pipeline is built around it.
- **Foundation before stages:** Pydantic types and the runner are imported by every stage module. Building them first means stages are never blocked on missing types.
- **Pipeline before frontend:** The SSE event contract (ProgressEvent schema, completion event shape, game_url field) must be stable before the frontend can be built against it. An unstable contract causes frontend rewrites.
- **Visual polish in the pipeline, not the frontend:** The shader/palette differentiators are implemented as a Visual Polisher pipeline stage, not as post-processing in the browser. This means they must be built in Phase 3 with the other stages.
- **Self-correction in Phase 3, not "later":** The pitfalls research shows that adding self-correction after the fact requires redesigning the correction prompt to include the game design spec — much harder once the stage interface is frozen.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Godot 4.5.1 exact release URL, headless CLI flags, and export template installation path — verify before writing the setup script (MEDIUM confidence in STACK.md)
- **Phase 3:** Anthropic tool_use / structured output for GameDesign Pydantic model extraction, exact Claude model IDs (Haiku/Sonnet current generation), optimal GDScript 4.x system prompt structure — verify against live Anthropic docs before implementing Code Generator stage

Phases with standard patterns (skip research-phase):
- **Phase 2:** FastAPI SSE, asyncio.Queue, Protocol registry — established Python async patterns, HIGH confidence
- **Phase 4:** Next.js App Router, React SSE consumption — well-documented official patterns
- **Phase 5:** Empirical tuning — no research needed, only execution

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Core framework choices (FastAPI SSE, Next.js, anthropic SDK) are HIGH confidence from official docs. Godot 4.5.1 exact CLI flags and export URLs are MEDIUM — verify against live release. Claude model IDs are MEDIUM — verify against Anthropic docs before first use. |
| Features | MEDIUM | Competitive analysis (Rosebud, GDevelop) is from training data through August 2025; competitive details should be validated before launch. Feature priorities are first-principles analysis of Godot WASM constraints — HIGH confidence for technical constraints. |
| Architecture | HIGH | Architecture is primarily derived from the project PRD + established FastAPI/asyncio/Godot patterns. Protocol registry, SSE queue pattern, template copy-on-job, typed stage contracts are all proven patterns with HIGH confidence. |
| Pitfalls | MEDIUM-HIGH | Godot headless exit code reliability issues (Pitfall 7) and GDScript 3-vs-4 syntax (Pitfall 2) are well-documented in the Godot community. COOP/COEP requirements are a web standard (HIGH confidence). SSE and FastAPI async patterns are HIGH confidence. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Godot 4.5.1 release validation:** STACK.md notes this version "not yet confirmed released as of research date" — confirm the exact download URL and export template path before writing the setup script in Phase 1. If 4.5.1 is not yet released, use the latest stable 4.x release and update the version lock.
- **Claude model IDs:** STACK.md lists `claude-sonnet-4-6` and `claude-3-5-haiku-20241022` as best guesses. Verify the exact model string identifiers from `https://docs.anthropic.com/en/docs/about-claude/models/overview` before the first LLM call in Phase 3.
- **Godot 4 headless `--check-only` flag:** PITFALLS.md recommends `godot --headless --check-only --script <file.gd>` for GDScript lint before full export. Confirm this flag exists in Godot 4.5.x (it is a known flag in 4.x but should be verified against the exact version).
- **Next.js 15 COOP/COEP header config:** The `headers()` function in `next.config.js` is documented but the exact configuration for serving `.wasm` files with correct MIME type alongside COOP/COEP should be verified in Phase 4.
- **Anthropic structured output / tool_use:** The GameDesign Pydantic model is complex (nested scenes, control schemes, visual style). Whether tool_use JSON extraction is reliable for this schema at Sonnet quality should be validated with a quick prompt experiment at the start of Phase 3.

## Sources

### Primary (HIGH confidence)
- FastAPI 0.135 SSE docs — `https://fastapi.tiangolo.com/tutorial/server-sent-events/` — native SSE via `EventSourceResponse`
- FastAPI 0.135 release notes — `https://fastapi.tiangolo.com/release-notes/` — version confirmation
- Next.js 15.3 blog — `https://nextjs.org/blog/next-15-3` — version confirmation
- Next.js Route Handlers docs — `https://nextjs.org/docs/app/building-your-application/routing/route-handlers` — SSE consumption patterns
- Moonpond PRD.md — project requirements, template structure, pipeline stage definitions
- SharedArrayBuffer COOP/COEP requirement — web standard, documented across MDN and Godot web export docs
- Python asyncio.create_subprocess_exec — Python stdlib, HIGH confidence for non-blocking subprocess pattern
- Anthropic API stop_reason and max_tokens behavior — documented in Anthropic API reference

### Secondary (MEDIUM confidence)
- anthropic Python SDK releases — GitHub releases page v0.84.0 — version confirmation
- Godot 4 headless export flags — training knowledge; verify against Godot 4.5.x release notes
- Godot WASM export requirements — training knowledge + standard WASM threading requirements
- LLM GDScript 3-vs-4 generation patterns — derived from known API divergences and LLM code generation behavior
- Rosebud AI, GDevelop AI product features — training data through August 2025; verify before competitive claims

### Tertiary (LOW confidence / validate before use)
- Godot 4.5.1 exact download URLs — projected from release pattern; confirm from `https://github.com/godotengine/godot/releases`
- Claude model IDs (`claude-sonnet-4-6`, etc.) — inferred from SDK release notes; confirm from Anthropic docs
- Godot headless `--check-only` flag availability in 4.5.x — known in 4.x but not confirmed for this patch

---
*Research completed: 2026-03-13*
*Ready for roadmap: yes*
