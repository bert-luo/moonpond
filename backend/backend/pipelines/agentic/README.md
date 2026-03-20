# Agentic Pipeline

The primary production pipeline for Moonpond. An agent-loop pipeline that generates complete Godot 4 games (2D and 3D) through iterative LLM-driven file generation with automated verification, self-correction, and optional AI-generated assets.

## Architecture

```
User Prompt
    |
    v
┌──────────────────────┐
│  1. Spec Generator   │  Single-turn LLM call
│     (structured)     │  Output: AgenticGameSpec JSON
└──────────┬───────────┘
           v
┌──────────────────────────────────────────┐
│  2. Generate-Verify-Fix Loop (max 4x)    │
│                                          │
│   ┌─────────────────────┐                │
│   │  File Generator     │  Multi-turn    │
│   │  (tool-use agent)   │  LLM agent     │
│   │  + Image Gen (2D)   │  w/ write_file │
│   │  + Tripo 3D (3D)    │  read_file     │
│   └─────────┬───────────┘                │
│             v                            │
│   ┌─────────────────────┐                │
│   │  Verifier           │  Single-turn   │
│   │  (fresh context)    │  LLM call      │
│   │  (asset-aware)      │                │
│   └─────────┬───────────┘                │
│             v                            │
│   Critical tasks? ──yes──> Fix loop      │
│        │ no                              │
└────────┼─────────────────────────────────┘
         v
┌──────────────────────┐
│  3. Input Map        │  Expand simplified
│     Expansion        │  key names → Godot
│                      │  Object() format
├──────────────────────┤
│  4. Exporter         │  Godot headless
│     (WASM build)     │  export (2D or 3D)
└──────────────────────┘
```

## Stages

### Stage 1: Spec Generator (`spec_generator.py`) — Single-Turn

Converts the raw user prompt into a structured game specification via one forced tool call.

**Input:** User prompt string (e.g. `"a space shooter with asteroids"`)

**Output:** `AgenticGameSpec` — saved to `intermediate/1_agentic_spec.json`

```json
{
  "title": "Asteroid Blaster",
  "genre": "shooter",
  "mechanics": ["shooting", "dodging", "score_tracking"],
  "entities": [
    {"name": "Player", "type": "CharacterBody2D", "behavior": "WASD movement, fires bullets on click"},
    {"name": "Asteroid", "type": "RigidBody2D", "behavior": "Spawns at top, drifts downward, splits on hit"}
  ],
  "scene_description": "Space background with player ship at bottom, asteroids spawning from top",
  "win_condition": "Survive 60 seconds",
  "fail_condition": "Player collides with asteroid",
  "controls": [
    {"key": "WASD", "action": "Move ship"},
    {"key": "Left Click", "action": "Fire"}
  ],
  "perspective": "2D"
}
```

**LLM details:** `claude-sonnet-4-6`, `tool_choice` forced to `submit_spec` tool.

**SSE events emitted:** `stage_start` ("Generating game specification..."), `spec_complete` (title, description, genre).

---

### Stage 2: File Generator (`file_generator.py`) — Multi-Turn

An LLM agent loop that generates game files one at a time by calling `write_file` and `read_file` tools. Supports optional AI asset generation for sprites (2D) and 3D models.

**Input:** `AgenticGameSpec` + existing files on disk (if fix iteration) + optional `fix_context`

**Output:** `dict[filename, content]` — each file also saved to `intermediate/iteration_N/files/`

**Tools available to the LLM:**

| Tool | Purpose |
|------|---------|
| `write_file(filename, content)` | Write a complete file to the project directory |
| `read_file(filename)` | Read an already-written file (for checking dependencies) |
| `generate_sprite(description, filename, ...)` | Generate a 2D sprite via OpenAI gpt-image-1 (when `ImageGenClient` available) |
| `generate_spritesheet(description, filename, frames, ...)` | Generate a multi-frame spritesheet (when `ImageGenClient` available) |
| `generate_3d_model(description, filename)` | Generate a GLB model via Tripo API (when `TripoAssetGenerator` available) |

**Loop mechanics:**
- Multi-turn tool-call conversation until the agent signals completion (text response with no tool call)
- The agent decides file order based on the system prompt guidance
- System prompt is dynamically generated based on perspective (2D vs 3D) via `build_generator_system_prompt()`
- Available template assets (shaders, palettes, particles, control snippets) surfaced in the prompt
- Viewport target: 1152x648 pixels

**Context strategies:**
- `"full_history"` (default) — accumulates all messages across turns; better coherence
- `"stateless"` — resets messages each turn with fresh prompt + filenames list; agent uses `read_file` to inspect dependencies

**Thinking mode:** Optional extended thinking support (`thinking=True`) for more complex game generation.

**Asset generation:**
- 2D games: `ImageGenClient` (OpenAI gpt-image-1-mini) generates sprites and spritesheets with optional post-processing (trim, resize, palette quantization, outline). Budget: 8 assets per game.
- 3D games: `TripoAssetGenerator` (Tripo API) generates GLB models from text descriptions. Uses async polling with exponential backoff.
- Asset clients are initialized based on the spec's `perspective` field and available API keys.

**On fix iterations**, the agent receives `fix_context` containing:
- The current content of each flagged file
- The specific tasks identified by the verifier (edit or create)
- Instructions to rewrite only the broken files or create missing ones

---

### Stage 3: Verifier (`verifier.py`) — Single-Turn

An independent LLM reviewer with fresh context (no shared history with the generator) that audits all generated files. Asset-aware: receives a list of generated binary assets (sprites, 3D models) so it doesn't flag valid `load()` calls as missing references.

**Input:** `AgenticGameSpec` + all generated files + list of generated asset paths

**Output:** `VerifierResult` — saved to `intermediate/iteration_N/verifier.json`

```json
{
  "tasks": [
    {
      "action": "edit",
      "file": "player.gd",
      "description": "Using `:=` with randf_range() — Godot 4.5 parse error. Use `var x = randf_range(...)` instead.",
      "severity": "critical"
    },
    {
      "action": "create",
      "file": "enemy.gd",
      "description": "Referenced in Main.tscn but not generated. Needs patrol + shoot AI behavior.",
      "severity": "critical"
    }
  ],
  "summary": "2 critical tasks: syntax error in player.gd, missing enemy.gd file"
}
```

**Task types:**
- `edit` — an existing file needs modification
- `create` — a new file is missing and must be generated

**Severity levels:**
- `critical` — will crash, produce blank screen, or break gameplay. Triggers fix loop.
- `warning` — may cause issues but won't prevent the game from running. Gameplay-affecting warnings are also fixed.

**LLM details:** `claude-sonnet-4-6`, `tool_choice` forced to `submit_verification` tool. Uses extended thinking when enabled.

---

### Generate-Verify-Fix Loop (`pipeline.py`)

```python
for iteration in range(1, MAX_ITERATIONS + 1):  # up to 4
    # Skip fix iterations on soft timeout
    if iteration > 1 and soft_timeout and soft_timeout.is_expired:
        break

    new_files = await run_file_generation(spec, fix_context=fix_ctx, ...)
    all_files.update(new_files)

    verifier_result = await run_verifier(spec, all_files, generated_assets=assets)

    if not verifier_result.has_critical_tasks:
        break

    # Filter: all criticals + gameplay-affecting warnings
    tasks_to_fix = [t for t in verifier_result.tasks if _should_fix(t)]
    fix_ctx = _build_fix_context(spec, tasks_to_fix, all_files)
```

The fix loop addresses **critical** tasks plus **warnings** containing gameplay keywords (e.g. "non-functional", "broken", "missing", "never called"). The fix context includes the current file content and specific task descriptions so the agent can make targeted corrections.

**Soft timeout:** The pipeline accepts a `SoftTimeout` (default 750s) that causes fix iterations to be skipped when expired, proceeding directly to export. Verification always runs after each generation iteration regardless of timeout.

---

### Stage 4: Input Map Expansion (`input_map.py`)

After the generate-verify-fix loop, if the LLM generated a `project.godot` file with a simplified `[input]` section (e.g. `move_left=arrow_left`), this stage expands it to the full Godot `Object(InputEventKey, ...)` serialization format. Uses a hardcoded `KEY_MAP` dict of Godot 4 physical keycodes.

---

### Stage 5: Exporter

Copies the appropriate Godot template (`base_2d` or `base_3d` based on `spec.perspective`), writes all generated files into the project directory, and runs Godot's headless export to produce a WASM bundle.

**Output:** `GameResult` with `job_id`, `wasm_path`, and `controls`

---

## Output Directory Structure

```
games/{game-slug}_{timestamp}/
├── project/                    # Working Godot project
│   ├── project.godot           # LLM-generated with input map
│   ├── Main.tscn
│   ├── player.gd
│   ├── enemy.gd
│   ├── assets/
│   │   ├── sprites/            # AI-generated (2D games)
│   │   │   ├── player.png
│   │   │   └── enemy.png
│   │   ├── models/             # AI-generated (3D games)
│   │   │   └── spaceship.glb
│   │   ├── shaders/            # From template
│   │   ├── palettes/           # From template
│   │   └── particles/          # From template
│   └── ...
├── intermediate/               # Debugging/audit trail
│   ├── 1_agentic_spec.json
│   ├── iteration_1/
│   │   ├── files/
│   │   │   ├── Main.tscn
│   │   │   └── player.gd
│   │   ├── verifier.json
│   │   └── conversation.json   # Full LLM conversation thread
│   └── iteration_2/           # Only if fix loop triggered
│       ├── files/
│       ├── verifier.json
│       └── conversation.json
└── export/                     # Final WASM build
    ├── index.html
    ├── moonpond.wasm
    ├── moonpond.js
    └── moonpond.worker.js
```

## Data Models (`models.py`)

| Model | Fields | Purpose |
|-------|--------|---------|
| `AgenticGameSpec` | `title`, `genre`, `mechanics`, `entities`, `scene_description`, `win_condition`, `fail_condition`, `controls`, `perspective` | Structured game design spec with 2D/3D support |
| `ControlMapping` | `key`, `action` | Single input → action mapping |
| `VerifierTask` | `action` (edit\|create), `file`, `description`, `severity` (critical\|warning) | Single task from verification |
| `VerifierResult` | `tasks`, `summary` | Aggregated verification output; `.has_critical_tasks` property drives loop |

## Configuration

| Constant | Value | File | Purpose |
|----------|-------|------|---------|
| `MAX_ITERATIONS` | 4 | `pipeline.py` | Max generate-verify-fix cycles |
| `SOFT_TIMEOUT_S` | 750 | `main.py` | Seconds before soft-stop signal |
| `ASSET_BUDGET` | 8 | `image_gen_client.py` | Max AI-generated assets per game |
| `MAX_SPRITESHEET_FRAMES` | 8 | `image_gen_client.py` | Max frames per spritesheet |
| All LLM calls | `claude-sonnet-4-6` | Various | LLM model for all stages |
| Image gen model | `gpt-image-1-mini` | `image_gen_client.py` | OpenAI image generation |
| 3D model version | `P1-20260311` | `tripo_client.py` | Tripo API model version |

## Progress Events (SSE)

The pipeline streams `ProgressEvent` objects to the client:

| Type | When |
|------|------|
| `stage_start` | Pipeline begins, spec gen starts, each iteration starts, verification starts, export starts |
| `spec_complete` | After spec generation (includes `title`, `description`, `genre`) |
| `file_generated` | Each file written by the agent (includes `filename`, `lines`) |
| `stage_complete` | After verification (includes task/severity counts) |
| `controls_complete` | After export (includes control mappings) |
| `done` | Pipeline complete (includes `job_id`, `wasm_path`, `controls`) |
| `error` | On exception |

## Module Overview

| File | Purpose |
|------|---------|
| `pipeline.py` | Top-level orchestrator, generate-verify-fix loop |
| `spec_generator.py` | Prompt → AgenticGameSpec via forced tool call |
| `file_generator.py` | Multi-turn LLM agent with write_file/read_file tools |
| `verifier.py` | Independent LLM reviewer, produces task list |
| `models.py` | Pydantic data models (spec, tasks, results) |
| `image_gen_client.py` | OpenAI sprite/spritesheet generation with post-processing |
| `tripo_client.py` | Tripo API client for text-to-3D GLB asset generation |
| `input_map.py` | Expand simplified input key names to Godot Object() format |
