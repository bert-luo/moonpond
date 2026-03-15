---
phase: 03-multi-stage-pipeline
plan: 01
subsystem: api
tags: [anthropic, pydantic, llm, structured-output, claude]

# Dependency graph
requires:
  - phase: 02-backend-pipeline-foundation
    provides: FastAPI backend with ProgressEvent, GameResult, EmitFn types
provides:
  - GameSpec and GameDesign Pydantic models (stage data contracts)
  - Prompt Enhancer stage (raw prompt -> GameSpec)
  - Game Designer stage (GameSpec -> GameDesign)
  - Template asset path constants (shaders, palettes, particles, control snippets)
affects: [03-multi-stage-pipeline]

# Tech tracking
tech-stack:
  added: [anthropic SDK]
  patterns: [shared AsyncAnthropic client, JSON extraction with code-fence stripping, Pydantic model_validate for LLM output]

key-files:
  created:
    - backend/backend/stages/__init__.py
    - backend/backend/stages/models.py
    - backend/backend/stages/prompt_enhancer.py
    - backend/backend/stages/game_designer.py
  modified:
    - backend/pyproject.toml
    - backend/uv.lock

key-decisions:
  - "Used client.messages.create() + json.loads() + model_validate() over messages.parse() for safer async compatibility"
  - "Haiku for Prompt Enhancer (fast enrichment), Sonnet for Game Designer (structured reasoning)"

patterns-established:
  - "Stage function signature: async def run_X(client: AsyncAnthropic, input, emit: EmitFn) -> TypedOutput"
  - "JSON extraction strips markdown code fences before parsing (regex-based)"
  - "Each stage emits ProgressEvent(type='stage_start') before LLM call"

requirements-completed: [STAGE-01, STAGE-02, STAGE-06]

# Metrics
duration: 2min
completed: 2026-03-15
---

# Phase 3 Plan 1: SDK and First Two Stages Summary

**Anthropic SDK with Pydantic stage models (GameSpec, GameDesign) and two LLM-powered stages (Prompt Enhancer via Haiku, Game Designer via Sonnet)**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-15T07:35:59Z
- **Completed:** 2026-03-15T07:37:39Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Installed Anthropic SDK and established LLM integration pattern
- Defined all 6 Pydantic models (GameSpec, GameDesign, ControlScheme, ControlMapping, SceneSpec, VisualStyle) as typed stage contracts
- Implemented Prompt Enhancer (Haiku) and Game Designer (Sonnet) stages with structured JSON output parsing
- Added template asset path constants shared across stages (shaders, palettes, particles, control snippets)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install Anthropic SDK and create Pydantic stage models** - `5051016` (feat)
2. **Task 2: Implement Prompt Enhancer and Game Designer stages** - `19d12a9` (feat)

## Files Created/Modified
- `backend/pyproject.toml` - Added anthropic dependency
- `backend/uv.lock` - Updated lockfile
- `backend/backend/stages/__init__.py` - Package init
- `backend/backend/stages/models.py` - GameSpec, GameDesign, and supporting models + asset path constants
- `backend/backend/stages/prompt_enhancer.py` - Haiku-powered prompt enrichment to GameSpec
- `backend/backend/stages/game_designer.py` - Sonnet-powered GameSpec expansion to GameDesign

## Decisions Made
- Used `client.messages.create()` + `json.loads()` + `model_validate()` over `messages.parse()` for safer async compatibility (per research Open Question #2)
- Haiku assigned to Prompt Enhancer (fast, low-cost enrichment), Sonnet to Game Designer (structured reasoning needed)
- JSON extraction uses regex to strip markdown code fences before parsing (defensive against LLM wrapping output)

## Deviations from Plan

None - plan executed exactly as written.

## User Setup Required

External services require manual configuration:
- **ANTHROPIC_API_KEY** environment variable needed in `.env` at repo root
- Get key from: https://console.anthropic.com/settings/keys

## Issues Encountered
None

## Next Phase Readiness
- Stage models and first two stages ready for downstream consumption
- Code Generator (Plan 02) can consume GameDesign output
- Visual Polisher (Plan 03) can use asset path constants from models.py

## Self-Check: PASSED

All 4 created files verified on disk. Both task commits (5051016, 19d12a9) found in git log.

---
*Phase: 03-multi-stage-pipeline*
*Completed: 2026-03-15*
