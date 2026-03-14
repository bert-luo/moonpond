# Moonpond

## What This Is

Moonpond is an AI-powered web application that generates playable Godot 4 browser games from a single natural language prompt. The user describes a game idea; a multi-stage agent pipeline designs, codes, applies visual polish, and exports a fully playable WASM game in real time — with streaming progress visible throughout.

## Core Value

The generated game must look and feel intentional: shaders, particle effects, and curated color palettes applied by design — not bare functional code that happens to run.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] User can submit a text prompt and receive a playable browser game
- [ ] Generation streams real-time progress events to the UI
- [ ] Generated games have applied visual polish (shaders, palettes, particles)
- [ ] Two-column UI: chat panel on left, game iframe on right
- [ ] Godot 4.5.1 headless binary is installed and used for WASM export
- [ ] Backend pipeline is modular — new strategies swappable without touching API or frontend
- [ ] Multi-stage MVP pipeline: Prompt Enhancer → Game Designer → Code Generator → Visual Polisher → Exporter
- [ ] GDScript self-correction pass on syntax error (compiler output fed back to LLM)
- [ ] base_2d Godot template with shader library, particle scenes, palette resources
- [ ] base_3d Godot template with toon shader and lighting setup
- [ ] Controls legend rendered in chat panel when game loads
- [ ] Error states surfaced to user (timeout, export failure, LLM failure)

### Out of Scope

- Multiplayer / networking — high complexity, not core value
- User accounts or game persistence beyond the session — deferred to v2
- Mobile-native export — web WASM only for v1
- In-browser code editing — deferred to v2
- Deployment infra — local-only MVP

## Context

- **Tech stack**: Next.js 14 (app router) + TypeScript + Tailwind for frontend; FastAPI (Python, async) + SSE for backend; Anthropic Claude as primary LLM (Haiku for speed, Sonnet for quality stages)
- **Game engine**: Godot 4.5.1 headless — exact version locked; binary installed as part of project setup
- **Pipeline architecture**: `GamePipeline` Protocol with `emit: Callable[[ProgressEvent], None]` callback; pipeline registry maps names to classes; API is pipeline-agnostic
- **Templates**: Pre-built valid Godot projects (`base_2d`, `base_3d`) as scaffolding — LLM generates gameplay logic on top, never writes boilerplate (engine config, export presets, audio bus layout)
- **Input system**: Template pre-defines named input actions (move_left, jump, shoot, etc.); LLM always uses named actions; non-traditional schemes import from `control_snippets/`
- **Future pipelines scoped out of v1**: single-shot agentic, ROMA multi-agent, Playwright visual feedback loop

## Constraints

- **Tech stack**: Godot 4.5.1 headless (exactly) — other versions break export presets
- **Runtime**: Local persistent server for MVP — no cloud deployment in v1
- **Performance**: Hard timeout of 90s total per generation; target under 2 minutes end-to-end
- **LLM**: Anthropic Claude primary; OpenAI/Gemini optional secondary

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Template-based generation | LLM generates gameplay on top of pre-built scaffold — improves export reliability, frees context budget for gameplay/visuals | — Pending |
| SSE for streaming | Simple, browser-native, no WebSocket complexity needed for one-way progress stream | — Pending |
| Modular pipeline registry | Enables A/B testing generation strategies without touching API or frontend | — Pending |
| Local-only v1 | Avoids deployment complexity; focus on generation quality first | — Pending |
| Phase 1 installs Godot binary | Ensures reproducible setup; binary version is critical dependency | — Pending |

---
*Last updated: 2026-03-13 after initialization*
