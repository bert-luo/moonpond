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
- [ ] **Phase 5: Pipeline Optimization** - Contract-first parallel pipeline with dependency-aware generation and centralized wiring

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
- [x] 04-01-PLAN.md — Backend patches (done event data, COOP/COEP middleware) + Tailwind v4 setup + types/reducer/layout foundation
- [ ] 04-02-PLAN.md — useGeneration SSE hook, ChatPanel, GameViewer components, page.tsx two-column wiring
- [ ] 04-03-PLAN.md — Human verification checkpoint: full visual and functional review in browser

### Phase 5: Pipeline Optimization
**Goal**: A contract-first parallel pipeline (ContractPipeline) that defines interface contracts before code generation, generates independent files in parallel, and centralizes scene wiring — eliminating cross-file bugs while improving generation speed
**Depends on**: Phase 4
**Requirements**: OPT-01, OPT-02, OPT-03, OPT-04, OPT-05, OPT-06, OPT-07, OPT-08
**Success Criteria** (what must be TRUE):
  1. GameContract Pydantic model validates a structured contract with nodes, method signatures, signals, groups, and dependencies
  2. Spec Expander stage converts a raw prompt into a RichGameSpec with entity-level detail
  3. Contract Generator stage produces a typed GameContract that all downstream stages consume
  4. Parallel Node Generation runs all leaf nodes concurrently via asyncio.gather(); one failure does not kill others
  5. Wiring Generator produces Main.tscn with correct ExtResource references matching contract; patches project.godot only when needed
  6. ContractPipeline is selectable via `get_pipeline("contract")` from the registry
  7. Full pipeline with mocked LLM produces a GameResult and emits progress events for each stage
**Plans**: 4 plans
Plans:
- [ ] 05-01-PLAN.md — Data models (RichGameSpec, NodeContract, GameContract) + ContractPipeline skeleton + test scaffolds
- [ ] 05-02-PLAN.md — Spec Expander + Contract Generator stages with mocked LLM tests
- [ ] 05-03-PLAN.md — Parallel Node Generator + Wiring Generator stages with mocked LLM tests
- [ ] 05-04-PLAN.md — ContractPipeline full wiring + registry integration + end-to-end test

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scaffold and Godot Template | 2/4 | In Progress|  |
| 2. Backend Pipeline Foundation | 3/3 | Complete   | 2026-03-14 |
| 3. Multi-Stage Pipeline | 3/3 | Complete   | 2026-03-15 |
| 3.1 Asset Generation Pipeline | 0/2 | Not started | - |
| 3.2 Containerization? | 0/TBD | Not started | - |
| 4. Frontend Integration | 2/3 | In Progress|  |
| 5. Pipeline Optimization | 1/4 | In Progress|  |

### Phase 05.1: Contract Pipeline Context Enrichment (INSERTED)

**Goal:** Enrich the contract pipeline's node generation with three context improvements: (1) generate a game-specific game_manager.gd from the contract's enums/properties instead of using the static template, (2) inject the GameManager API surface into every node generation prompt so nodes code against a known interface, (3) inject focused sibling node API blocks for each node's declared dependencies
**Requirements**: CTXE-01, CTXE-02, CTXE-03
**Depends on:** Phase 5
**Success Criteria** (what must be TRUE):
  1. ContractPipeline generates a game-specific game_manager.gd with properties, methods, signals, and enums derived from GameContract — replacing the static template copy
  2. Node generation system prompts include an explicit GameManager API block listing all available properties, methods, signals, and enums from the contract
  3. Node generation system prompts include a focused dependency API block for each declared dependency, showing that node's methods, signals, and groups
**Plans:** 2/2 plans complete

Plans:
- [ ] 05.1-01-PLAN.md — GameContract model extensions + game_manager.gd generator + pipeline wiring
- [ ] 05.1-02-PLAN.md — GameManager API + sibling dependency API injection into node generation prompts

### Phase 05.2: Fix Pipeline Generation Failure Modes (INSERTED)

**Goal:** Systematically fix the remaining pipeline generation failure modes identified from inspecting game outputs — duplicate method definitions, invalid .tscn ExtResource IDs, signal argument mismatches, duplicate autoloads, and other issues that cause blank screens or runtime crashes
**Requirements**: BUG-A, BUG-B, BUG-C, BUG-D, BUG-E, BUG-F
**Depends on:** Phase 5.1
**Success Criteria** (what must be TRUE):
  1. game_manager.gd generation never duplicates base template methods (set_state, set_palette, get_palette_color, _ready) even when the contract includes methods with those names
  2. project.godot autoload section never contains duplicate GameManager entries
  3. Per-node .tscn files from the LLM are stripped before reaching the wiring stage — Main.tscn is assembled solely by the wiring generator from the contract
  4. Signal signatures in the contract include argument types so node generators emit signals with correct arguments
  5. Nodes marked as dynamically spawned (spawn_mode="dynamic") are excluded from the Main.tscn scene tree
**Plans:** 3/3 plans complete

Plans:
- [ ] 05.2-01-PLAN.md — Deterministic fixes: filter duplicate base methods (Bug A) + deduplicate autoloads (Bug B)
- [ ] 05.2-02-PLAN.md — Strip per-node .tscn files from pipeline output (Bugs C + F)
- [ ] 05.2-03-PLAN.md — Signal signature enrichment (Bug D) + spawn_mode contract field + dynamic node filtering (Bug E)

### Phase 6: Programmatic TSCN generation and display configuration

**Goal:** Replace the LLM-based wiring generator with a deterministic TscnBuilder and SceneAssembler that produces all .tscn files programmatically from the contract and generated .gd files, and fix viewport size hallucination by adding display configuration to the template and node generator prompt
**Requirements**: TSCN-01, TSCN-02, TSCN-03, TSCN-04, TSCN-05, TSCN-06
**Depends on:** Phase 5.2
**Success Criteria** (what must be TRUE):
  1. Generated games have all required .tscn files present (Main.tscn + sub-scenes)
  2. Every @onready %Name reference in .gd files resolves to an actual child node in the .tscn
  3. Every preload("res://X.tscn") in .gd files has the corresponding .tscn file
  4. No LLM calls for .tscn generation -- fully deterministic
  5. All scripts use consistent viewport dimensions (no hardcoded screen sizes)
  6. Existing test suite passes; new tests cover TscnBuilder and SceneAssembler
**Plans:** 2/2 plans complete

Plans:
- [ ] 06-01-PLAN.md — TscnBuilder utility + SceneAssembler + @onready parser with full test suites
- [ ] 06-02-PLAN.md — Pipeline integration, prompt updates, display config, existing test fixes

### Phase 7: Agentic Pipeline — lightweight agent-loop pipeline with spec generation, todo-driven iterative file generation, and verifier agent

**Goal:** A new pipeline strategy ("agentic") that uses a single multi-turn LLM conversation to generate a complete game through a spec -> todo-driven file generation -> LLM verification -> targeted fix loop, registered alongside the existing contract and multi_stage pipelines
**Requirements**: AGNT-01, AGNT-02, AGNT-03, AGNT-04, AGNT-05, AGNT-06, AGNT-07, AGNT-08, AGNT-09
**Depends on:** Phase 6
**Success Criteria** (what must be TRUE):
  1. AgenticPipeline is registered as "agentic" in the pipeline registry and selectable via get_pipeline("agentic")
  2. The pipeline uses Anthropic tool_use API (write_file, read_file tools) for multi-turn file generation with correct message role alternation
  3. A separate verifier LLM call audits all generated files and produces a structured VerifierResult with typed errors
  4. The generate-verify-fix loop runs up to MAX_ITERATIONS, with targeted fixes only for files the verifier flagged
  5. All intermediate state (spec, per-iteration files, verifier results) is persisted in numbered subdirectories
  6. AgenticPipeline.generate() satisfies the GamePipeline Protocol and produces a GameResult via the shared exporter
  7. Configurable context strategy: full_history (default) or stateless mode
**Plans:** 2/3 plans executed

Plans:
- [ ] 07-01-PLAN.md — Data models (AgenticGameSpec, VerifierResult), spec generator, tool definitions and dispatch
- [ ] 07-02-PLAN.md — Multi-turn file generation loop + verifier agent
- [ ] 07-03-PLAN.md — AgenticPipeline orchestrator with generate-verify-fix loop + registry integration

### Phase 8: Agentic template decoupling

**Goal:** Slim the base_2d template to essentials (export presets, assets, engine cache), let the LLM generate project.godot with autoloads and input maps, surface asset paths in the file generator prompt, and add a Python input map expansion utility — eliminating the GameManager autoload mismatch and input action disconnect in the agentic pipeline
**Requirements**: TMPL-SLIM, AGENT-PROJGODOT, AGENT-INPUTMAP, AGENT-ASSETS, PIPE-INPUTMAP
**Depends on:** Phase 7
**Success Criteria** (what must be TRUE):
  1. Generated project.godot has correct [autoload] entries matching the LLM's generated singleton scripts
  2. No naming collision between template and generated files (no duplicate game manager files)
  3. Input actions referenced in generated .gd code exist in the generated project.godot's [input] section
  4. [rendering] and [display] sections are always correct (viewport 1152x648, gl_compatibility renderer)
  5. Pre-built assets (shaders, palettes, particles) are used by the LLM when appropriate
  6. Existing contract/general/multi_stage pipelines are unaffected
  7. Verifier no longer flags "GameManager autoload not configured" as a critical error
**Plans:** 2 plans

Plans:
- [ ] 08-01-PLAN.md — Input map expansion utility, system prompt rewrite with project.godot skeleton and asset paths, template file stripping
- [ ] 08-02-PLAN.md — Pipeline integration: wire expand_input_map into AgenticPipeline before export

### Phase 9: Add 3D game generation support to agentic pipeline

**Goal:** Add a `perspective` field to the agentic pipeline that routes 2D and 3D game generation through divergent prompt paths while sharing the same generate-verify-fix orchestration loop, with a new base_3d template for 3D WASM export
**Requirements**: 3D-SCHEMA, 3D-SPEC, 3D-TEMPLATE, 3D-PROMPT, 3D-EXPORT, 3D-WIRE
**Depends on:** Phase 8
**Success Criteria** (what must be TRUE):
  1. AgenticGameSpec has a `perspective` field (Literal["2D", "3D"]) with "2D" default for backward compatibility
  2. Spec generator determines whether a game is 2D or 3D and sets the perspective field
  3. File generator system prompt dynamically branches on perspective — 3D prompt includes Camera3D, lighting, Vector3, MeshInstance3D requirements
  4. Exporter selects base_2d or base_3d template based on perspective
  5. base_3d template exists with 3D-compatible assets (no 2D-only control snippets or shaders)
  6. All existing 2D pipelines and tests are unaffected (backward compatible)
**Plans:** 2 plans

Plans:
- [ ] 09-01-PLAN.md — Schema perspective field, spec generator updates, base_3d template creation
- [ ] 09-02-PLAN.md — Dynamic prompt builder, exporter template selection, pipeline wiring, tests
