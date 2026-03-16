# Roadmap: Moonpond

## Overview

Moonpond is built in four phases, each gated by the previous. Phase 1 establishes the Godot template foundation — the single highest-leverage artifact in the system — and must produce a verified clean WASM export before pipeline code is written. Phase 2 builds the backend infrastructure (SSE streaming, pipeline registry, Godot runner) that all stage modules depend on. Phase 3 implements all five pipeline stages plus self-correction, ending with a command-line end-to-end proof. Phase 4 connects the frontend to the working pipeline, delivering the complete user-facing application.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Scaffold and Godot Template** - Monorepo structure, Godot 4.5.1 setup, base_2d template that exports clean WASM with shader/palette/particle assets
- [x] **Phase 2: Backend Pipeline Foundation** - FastAPI app, SSE streaming endpoints, pipeline registry, Godot headless runner (completed 2026-03-14)
- [ ] **Phase 3: Multi-Stage Pipeline** - All five pipeline stages, self-correction pass, end-to-end CLI proof
- [ ] **Phase 4: Frontend Integration** - Two-column Next.js UI wired to working pipeline, full user flow end-to-end
- [ ] **Phase 5: E2E Optimization** - Await further instructions based on results of previous phases

## Phase Details

### Phase 1: Scaffold and Godot Template
**Goal**: A verified Godot 4.5.1 development environment with a base_2d template that exports a clean blank WASM game and contains all visual assets the pipeline will reference
**Depends on**: Nothing (first phase)
**Requirements**: SETUP-01, SETUP-02, TMPL-01, TMPL-02, TMPL-03, TMPL-04, TMPL-05, TMPL-06
**Success Criteria** (what must be TRUE):
  1. Running the setup script installs Godot 4.5.1 headless and export templates; server startup prints a confirmed version string and no errors
  2. `godot --headless --export-release "Web"` on the base_2d template produces a `.wasm` and `.html` with no errors
  3. The base_2d template project contains shader library files (pixel_art, glow, scanlines, chromatic_aberration, screen_distortion), particle scenes (explosion, dust, sparkle, trail), and palette resources (neon, retro, pastel, monochrome) committed to the repo
  4. The base_2d template's input map defines all eight standard named actions (move_left, move_right, move_up, move_down, jump, shoot, interact, pause)
  5. Opening the game WASM file in a browser (served with COOP/COEP headers) shows a blank running game with no console errors
**Plans**: 4 plans
Plans:
- [ ] 01-01-PLAN.md — Monorepo scaffold, setup/verify scripts, Next.js COOP/COEP config
- [ ] 01-02-PLAN.md — base_2d core project files (project.godot, export_presets.cfg, Main.tscn, game_manager.gd)
- [ ] 01-03-PLAN.md — Shader library (5 shaders) and control snippet scripts (4 GDScript files)
- [ ] 01-04-PLAN.md — Particle scenes (4 GPUParticles2D .tscn) and palette resources (4 Gradient .tres)

### Phase 2: Backend Pipeline Foundation
**Goal**: A FastAPI backend with working SSE streaming, a pipeline registry, and a Godot headless runner — ready to receive stage module implementations
**Depends on**: Phase 1
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05
**Success Criteria** (what must be TRUE):
  1. `POST /api/generate` with any prompt body returns a `job_id` immediately (under 100ms) while a background task begins
  2. `GET /api/stream/{job_id}` streams SSE `ProgressEvent` messages and sends a heartbeat every 15 seconds without dropping the connection
  3. A stub pipeline registered in the registry runs, copies the base_2d template, writes a dummy GDScript file, and the resulting WASM is accessible at `/games/{job_id}/export/`
  4. The Godot runner executes headless export non-blocking (does not freeze the FastAPI event loop), captures stderr, and validates output file existence rather than exit code
**Plans**: 3 plans
Plans:
- [ ] 02-01-PLAN.md — Python project setup, type contracts (models, Protocol, registry), Godot headless runner
- [ ] 02-02-PLAN.md — FastAPI app with SSE endpoints, stub pipeline, test suite for all PIPE requirements
- [ ] 02-03-PLAN.md — Gap closure: Add 15-second SSE heartbeat to stream endpoint

### Phase 3: Multi-Stage Pipeline
**Goal**: A complete working pipeline that takes a text prompt and produces a playable WASM game via five sequential LLM-powered stages with self-correction
**Depends on**: Phase 2
**Requirements**: STAGE-01, STAGE-02, STAGE-03, STAGE-04, STAGE-05, STAGE-06
**Success Criteria** (what must be TRUE):
  1. Running the pipeline from the command line with a test prompt produces a `.wasm` file that loads in a browser within 90 seconds
  2. Each of the five stages emits a human-readable SSE `ProgressEvent` message at its start (visible in the SSE stream)
  3. The generated game's GDScript files use Godot 4 syntax exclusively and reference only the named input actions defined in the base_2d template
  4. The Visual Polisher stage's output includes at least one shader reference and one palette selection from the template asset library in the generated code
  5. If the Code Generator produces a GDScript syntax error, the pipeline automatically retries with compiler output in context (up to 2 attempts) before failing
**Plans**: 3 plans
Plans:
- [ ] 03-01-PLAN.md — Anthropic SDK, Pydantic stage models, Prompt Enhancer and Game Designer stages
- [ ] 03-02-PLAN.md — Code Generator, Visual Polisher, and Exporter stages
- [ ] 03-03-PLAN.md — MultiStagePipeline wiring with self-correction, registry, and test suite

### Phase 03.1: Asset Generation Pipeline (INSERTED)
**Goal**: A configurable image generation system with swappable providers (OpenAI/Google) that produces sprites, backgrounds, and textures for generated games, integrated into the multi-stage pipeline
**Depends on**: Phase 3
**Requirements**: ASSET-01, ASSET-02, ASSET-03, ASSET-04, ASSET-05, ASSET-06
**Success Criteria** (what must be TRUE):
  1. Switching `IMAGE_PROVIDER=openai` to `IMAGE_PROVIDER=google` (or vice versa) in `.env` changes which API is called without any code changes
  2. The Asset Generator stage produces at least one `.png` file in `assets/generated/` for a test prompt, and the generated GDScript references it
  3. The Asset Generator emits a `ProgressEvent` SSE message visible in the stream
  4. All API keys are loaded from `.env` via python-dotenv; no hardcoded keys in source
  5. The pipeline still completes end-to-end (prompt → WASM) with asset generation enabled
**Plans**: 2 plans
Plans:
- [ ] 03.1-01-PLAN.md — ImageProvider Protocol, OpenAI + Google providers, provider registry, python-dotenv integration
- [ ] 03.1-02-PLAN.md — Asset Generator stage, AssetManifest type, MultiStagePipeline integration

### Phase 03.2: Containerization (INSERTED)
**Goal**: A Docker container that packages the Godot headless binary, export templates, and Python backend into a reproducible build environment — enabling consistent pipeline execution across machines without manual Godot installation
**Depends on**: Phase 3
**Requirements**: TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd:plan-phase 03.2 to break down)

### Phase 4: Frontend Integration
**Goal**: A browser application where a user types a prompt, watches real-time stage progress, and receives a playable game in an iframe — with error states handled
**Depends on**: Phase 3
**Requirements**: FE-01, FE-02, FE-03, FE-04, FE-05, FE-06, FE-07, FE-08
**Success Criteria** (what must be TRUE):
  1. The app renders a two-column layout: ChatPanel on the left, GameViewer on the right; both visible on a standard 1280px-wide viewport
  2. A user submits a prompt and sees each pipeline stage appear as a chat bubble in the ChatPanel as it begins, without refreshing the page
  3. The GameViewer shows a loading skeleton while the pipeline runs; when generation completes the skeleton is replaced by the live game iframe automatically
  4. The controls legend (key + action pairs) appears in the ChatPanel when the completion SSE event includes a `controls` list
  5. If generation fails (LLM error, export failure, or timeout), a clear error message appears in the ChatPanel and the prompt input remains available for retry
  6. After a game loads, the prompt input resets and a new prompt can be submitted immediately
**Plans**: 3 plans
Plans:
- [ ] 04-01-PLAN.md — Backend patches (done event data, COOP/COEP middleware) + Tailwind v4 setup + types/reducer/layout foundation
- [ ] 04-02-PLAN.md — useGeneration SSE hook, ChatPanel, GameViewer components, page.tsx two-column wiring
- [ ] 04-03-PLAN.md — Human verification checkpoint: full visual and functional review in browser

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scaffold and Godot Template | 2/4 | In Progress|  |
| 2. Backend Pipeline Foundation | 3/3 | Complete   | 2026-03-14 |
| 3. Multi-Stage Pipeline | 3/3 | Complete   | 2026-03-15 |
| 3.1 Asset Generation Pipeline | 0/2 | Not started | - |
| 3.2 Containerization? | 0/TBD | Not started | - |
| 4. Frontend Integration | 0/3 | Not started | - |
