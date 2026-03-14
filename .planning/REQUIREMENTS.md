# Requirements: Moonpond

**Defined:** 2026-03-13
**Core Value:** The generated game must look and feel intentional — shaders, particles, and curated color palettes applied by design, not bare functional code that happens to run.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Setup

- [x] **SETUP-01**: Godot 4.5.1 headless binary and export templates are installed via a setup script and verified at server startup
- [x] **SETUP-02**: Frontend dev server serves WASM game files with correct COOP/COEP headers (`Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Embedder-Policy: require-corp`)

### Godot Templates

- [x] **TMPL-01**: base_2d Godot 4 project template exports a clean blank WASM game with no errors via headless export
- [x] **TMPL-02**: base_2d template includes a shader library (pixel_art, glow, scanlines, chromatic_aberration, screen_distortion)
- [x] **TMPL-03**: base_2d template includes a particle scene library (explosion, dust, sparkle, trail)
- [x] **TMPL-04**: base_2d template includes curated color palette resources (neon, retro, pastel, monochrome as Gradient .tres files)
- [x] **TMPL-05**: base_2d template pre-defines a standard input action map (move_left, move_right, move_up, move_down, jump, shoot, interact, pause)
- [x] **TMPL-06**: base_2d template includes control snippet scripts (mouse_follow, click_to_move, drag, point_and_shoot)

### Backend Pipeline Foundation

- [ ] **PIPE-01**: Backend exposes `POST /api/generate` that accepts a prompt and returns a `job_id` immediately
- [ ] **PIPE-02**: Backend exposes `GET /api/stream/{job_id}` that streams `ProgressEvent` SSE messages for the job
- [ ] **PIPE-03**: Backend serves generated WASM files at `/games/{job_id}/export/` as static files
- [ ] **PIPE-04**: Pipeline registry maps strategy names to `GamePipeline` Protocol implementations; active pipeline is resolved from request
- [ ] **PIPE-05**: Godot headless runner executes export asynchronously (non-blocking), captures stderr, and validates output file existence (not exit code)

### Multi-Stage MVP Pipeline

- [ ] **STAGE-01**: Prompt Enhancer stage takes raw user prompt and outputs a structured game spec (title, genre, mechanics, visual hints)
- [ ] **STAGE-02**: Game Designer stage produces a full `GameDesign` model (scenes, visual_style, control_scheme, controls list, win/fail conditions)
- [ ] **STAGE-03**: Code Generator stage produces GDScript files per scene using Godot 4 syntax exclusively; uses named input actions from the template
- [ ] **STAGE-04**: Visual Polisher stage reviews generated code and applies shader references, palette selections, and particle scenes from the template asset library
- [ ] **STAGE-05**: Exporter stage copies the base_2d template, writes generated GDScript files, runs Godot headless export, and returns the WASM output path
- [ ] **STAGE-06**: Each stage emits a `ProgressEvent` SSE message at start with a human-readable label

### Frontend

- [ ] **FE-01**: Frontend renders a two-column layout: ChatPanel on the left, GameViewer on the right
- [ ] **FE-02**: User can type a prompt and submit it; frontend sends `POST /api/generate` and subscribes to `GET /api/stream/{job_id}`
- [ ] **FE-03**: ChatPanel displays each incoming SSE stage message as a chat bubble as it arrives
- [ ] **FE-04**: GameViewer shows a loading skeleton while generation is in progress
- [ ] **FE-05**: On completion SSE event, GameViewer loads the game iframe automatically; skeleton is replaced by the live game
- [ ] **FE-06**: ChatPanel renders a controls legend (key + action pairs) when the completion event includes a `controls` list
- [ ] **FE-07**: User sees an error message in ChatPanel if generation fails (LLM error, export failure, or timeout)
- [ ] **FE-08**: Prompt input resets after game loads; user can submit a new prompt

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Reliability

- **REL-01**: GDScript self-correction pass — compiler error output fed back to Code Generator for up to 2 retry attempts (with original GameDesign in context)
- **REL-02**: 90-second hard timeout with user-visible message and partial result if available

### Templates

- **TMPL-07**: base_3d template with toon shader and DirectionalLight + WorldEnvironment pre-configured

### Features

- **FEAT-01**: Iterative chat refinement — user can describe changes to an existing generated game
- **FEAT-02**: Download generated project as a zip file
- **FEAT-03**: Prompt hints / suggestions shown to new users

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multiplayer / networking | High complexity, not core value — deferred indefinitely |
| User accounts and game persistence | Auth infrastructure complexity; validate generation quality first |
| Mobile-native export | Web WASM only; mobile adds export config surface area without v1 value |
| In-browser code editor | Large scope; validate that users prefer re-generation over editing first |
| Deployment infra (Docker, fly.io, etc.) | Local-only MVP; focus on generation quality before ops |
| Audio / sound effects pipeline stage | Silence is acceptable for v1; adds LLM/asset complexity |
| Game gallery and sharing | Requires accounts + CDN; deferred to v2+ |
| Image-to-game prompting | Text-only covers the v1 hypothesis; multimodal adds pipeline complexity |
| Single-shot agentic pipeline | Future pipeline strategy; registry makes it easy to add later |
| ROMA multi-agent pipeline | Future pipeline strategy; complex coordination, high implementation cost |
| Playwright visual feedback loop | Future quality signal; good idea but adds significant infra |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 1 | Complete |
| SETUP-02 | Phase 1 | Complete |
| TMPL-01 | Phase 1 | Complete |
| TMPL-02 | Phase 1 | Complete |
| TMPL-03 | Phase 1 | Complete |
| TMPL-04 | Phase 1 | Complete |
| TMPL-05 | Phase 1 | Complete |
| TMPL-06 | Phase 1 | Complete |
| PIPE-01 | Phase 2 | Pending |
| PIPE-02 | Phase 2 | Pending |
| PIPE-03 | Phase 2 | Pending |
| PIPE-04 | Phase 2 | Pending |
| PIPE-05 | Phase 2 | Pending |
| STAGE-01 | Phase 3 | Pending |
| STAGE-02 | Phase 3 | Pending |
| STAGE-03 | Phase 3 | Pending |
| STAGE-04 | Phase 3 | Pending |
| STAGE-05 | Phase 3 | Pending |
| STAGE-06 | Phase 3 | Pending |
| FE-01 | Phase 4 | Pending |
| FE-02 | Phase 4 | Pending |
| FE-03 | Phase 4 | Pending |
| FE-04 | Phase 4 | Pending |
| FE-05 | Phase 4 | Pending |
| FE-06 | Phase 4 | Pending |
| FE-07 | Phase 4 | Pending |
| FE-08 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-13 after roadmap creation*
