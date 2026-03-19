---
phase: 06-programmatic-tscn-generation-and-display-configuration
plan: 02
subsystem: pipeline
tags: [tscn, scene-assembler, godot, viewport, deterministic]

# Dependency graph
requires:
  - phase: 06-01
    provides: TscnBuilder and SceneAssembler classes for deterministic scene generation
provides:
  - SceneAssembler integrated into ContractPipeline Stage 4 (no LLM for .tscn)
  - Node generator prompt with viewport size hint (1152x648)
  - project.godot template with [display] section for consistent viewport
  - Gutted wiring_generator.py retaining only autoload patching
affects: [contract-pipeline, node-generation, game-export]

# Tech tracking
tech-stack:
  added: []
  patterns: [deterministic-scene-assembly replaces LLM wiring]

key-files:
  created: []
  modified:
    - backend/backend/pipelines/contract/pipeline.py
    - backend/backend/pipelines/contract/wiring_generator.py
    - backend/backend/pipelines/contract/node_generator.py
    - godot/templates/base_2d/project.godot
    - backend/backend/tests/test_wiring_generator.py
    - backend/backend/tests/test_contract_pipeline.py

key-decisions:
  - "SceneAssembler runs inline in pipeline (not via LLM) -- eliminates wiring LLM call entirely"
  - "Kept _strip_node_tscn() as safety net even though prompt no longer asks for .tscn"
  - "Fixed mock content blocks to set type='text' for thinking mode compatibility"

patterns-established:
  - "Deterministic scene assembly: contract + scripts -> .tscn without LLM"
  - "Viewport hint in node prompts: tell LLM the design resolution rather than letting it hallucinate"

requirements-completed: [TSCN-04, TSCN-05, TSCN-06]

# Metrics
duration: 10min
completed: 2026-03-19
---

# Phase 06 Plan 02: Pipeline Integration Summary

**SceneAssembler replaces LLM wiring call in Stage 4, node prompts gain 1152x648 viewport hint, project.godot gets [display] section**

## Performance

- **Duration:** 10 min
- **Started:** 2026-03-19T06:20:17Z
- **Completed:** 2026-03-19T06:30:17Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Replaced LLM-based wiring generator with deterministic SceneAssembler in ContractPipeline Stage 4
- Added viewport size context (1152x648) to node generator prompts, removed "Also generate: {scene_path}" instruction
- Added [display] section to project.godot template with 1152x648 viewport and canvas_items stretch
- Gutted wiring_generator.py down to only _patch_project_godot_autoloads utility
- Updated full test suite: removed 13 deleted-function tests, fixed mock compatibility, 80 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Pipeline integration + prompt updates + display config** - `96b4f10` (feat)
2. **Task 2: Update existing test suite for removed wiring LLM call** - `b1db9eb` (test)

## Files Created/Modified
- `backend/backend/pipelines/contract/pipeline.py` - Stage 4 now uses SceneAssembler instead of run_wiring_generator
- `backend/backend/pipelines/contract/wiring_generator.py` - Gutted to only _patch_project_godot_autoloads
- `backend/backend/pipelines/contract/node_generator.py` - Viewport hint added, scene_path instruction removed
- `godot/templates/base_2d/project.godot` - [display] section with 1152x648 viewport
- `backend/backend/tests/test_wiring_generator.py` - Reduced to 3 autoload dedup tests
- `backend/backend/tests/test_contract_pipeline.py` - 4 LLM calls (no wiring), fixed mock type attr

## Decisions Made
- SceneAssembler runs inline in pipeline -- no LLM call, purely deterministic
- Kept _strip_node_tscn() as safety net even though prompt no longer asks for .tscn generation
- Fixed mock content blocks to set type="text" for contract_generator's thinking mode filtering (Rule 3 auto-fix)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed mock content blocks for thinking mode compatibility**
- **Found during:** Task 2 (test suite update)
- **Issue:** MagicMock content blocks lacked `type="text"` attribute. Contract generator now filters `block.type == "text"` for thinking mode, causing mock responses to be rejected.
- **Fix:** Set `block.type = "text"` explicitly on mock content blocks in `_mock_response()`
- **Files modified:** backend/backend/tests/test_contract_pipeline.py
- **Verification:** All 80 relevant tests pass
- **Committed in:** b1db9eb (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix for test compatibility. No scope creep.

## Issues Encountered
- Pre-existing failure in test_contract_generator.py (same mock type issue, not in scope). Logged to deferred-items.md.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Pipeline now makes one fewer LLM call (4 instead of 5 for a typical 2-node game)
- Scene assembly is fully deterministic with correct ExtResource IDs
- Viewport configuration ensures consistent 1152x648 design resolution
- All requirements (TSCN-04, TSCN-05, TSCN-06) satisfied

---
*Phase: 06-programmatic-tscn-generation-and-display-configuration*
*Completed: 2026-03-19*
