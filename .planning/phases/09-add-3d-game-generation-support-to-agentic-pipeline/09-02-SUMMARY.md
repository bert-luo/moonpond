---
phase: 09-add-3d-game-generation-support-to-agentic-pipeline
plan: 02
subsystem: pipeline
tags: [godot, 3d, prompt-engineering, template-selection, agentic-pipeline]

requires:
  - phase: 09-01
    provides: "AgenticGameSpec.perspective field, base_3d template directory"
provides:
  - "Dynamic build_generator_system_prompt() with 2D/3D branching"
  - "Perspective-aware exporter template selection via get_template_dir()"
  - "Pipeline wiring passing spec.perspective to file generator and exporter"
  - "Comprehensive test coverage for 3D prompt content and template routing"
affects: [09-03, 09-04]

tech-stack:
  added: []
  patterns:
    - "Dynamic prompt builder function with backward-compatible module constant"
    - "Perspective-parameterized asset section with conditional control snippet inclusion"

key-files:
  created: []
  modified:
    - "backend/backend/pipelines/agentic/file_generator.py"
    - "backend/backend/pipelines/exporter.py"
    - "backend/backend/pipelines/agentic/pipeline.py"
    - "backend/backend/tests/test_file_generator_prompt.py"
    - "backend/backend/tests/test_agentic_pipeline.py"

key-decisions:
  - "build_generator_system_prompt() shares all dimension-agnostic content and branches only on perspective-specific sections"
  - "3D prompt omits control snippet paths entirely (marked as 2D only) since they are Node2D scripts"
  - "3D prompt annotates shaders as CanvasLayer/UI only, not for 3D mesh materials"
  - "GENERATOR_SYSTEM_PROMPT backward-compat constant assigned as build_generator_system_prompt('2D')"

patterns-established:
  - "Dynamic prompt builder: function returns prompt string, module constant for backward compat"
  - "Perspective parameter threading: keyword-only with '2D' default for backward compat"

requirements-completed: [3D-PROMPT, 3D-EXPORT, 3D-WIRE]

duration: 4min
completed: 2026-03-20
---

# Phase 9 Plan 02: Prompt Builder, Exporter, and Pipeline Wiring Summary

**Dynamic build_generator_system_prompt() with 3D essentials (Camera3D, lighting, Vector3, built-in meshes), perspective-aware exporter template selection, and full pipeline wiring**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-20T08:13:12Z
- **Completed:** 2026-03-20T08:17:12Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Converted static GENERATOR_SYSTEM_PROMPT to dynamic build_generator_system_prompt() that branches on 2D/3D for mission, node types, root node, display config, 3D essentials, asset annotations
- Added get_template_dir() to exporter routing 2D to base_2d and 3D to base_3d template directories
- Wired spec.perspective through pipeline to both file generator and exporter
- Added 13 new tests: 10 for 3D prompt content verification, 3 for exporter template selection

## Task Commits

Each task was committed atomically:

1. **Task 1: Convert file generator to dynamic prompt builder and update exporter with template selection** - `28128c8` (feat)
2. **Task 2: Add 3D prompt content tests and exporter template selection tests** - `3f27a54` (test)

## Files Created/Modified
- `backend/backend/pipelines/agentic/file_generator.py` - Dynamic prompt builder with perspective branching, _build_asset_section accepts perspective
- `backend/backend/pipelines/exporter.py` - get_template_dir(), TEMPLATE_DIR_2D/3D constants, run_exporter perspective param
- `backend/backend/pipelines/agentic/pipeline.py` - Passes spec.perspective to run_exporter
- `backend/backend/tests/test_file_generator_prompt.py` - 10 new 3D prompt content tests + backward compat test
- `backend/backend/tests/test_agentic_pipeline.py` - 3 exporter template selection tests + mock signature fixes

## Decisions Made
- build_generator_system_prompt() shares all dimension-agnostic content (Variant warnings, spawn ordering, GDScript syntax rules) and branches only on perspective-specific sections
- 3D prompt omits control snippet paths entirely (marked as "2D only, not applicable to 3D games") since they are Node2D scripts
- 3D prompt annotates shaders as "apply to CanvasLayer or UI elements -- NOT to 3D mesh materials"
- GENERATOR_SYSTEM_PROMPT backward-compat constant assigned as build_generator_system_prompt("2D") so existing imports continue working

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing test_targeted_fix mock missing existing_files parameter**
- **Found during:** Task 1 (mid-task sanity check)
- **Issue:** mock_file_gen in test_targeted_fix lacked existing_files keyword param, causing TypeError when pipeline passes it
- **Fix:** Added existing_files=None to mock function signature
- **Files modified:** backend/backend/tests/test_agentic_pipeline.py
- **Verification:** Test passes (was failing before this plan too)
- **Committed in:** 28128c8 (Task 1 commit)

**2. [Rule 1 - Bug] Fixed capture_exporter mock missing perspective parameter**
- **Found during:** Task 1 (pipeline wiring)
- **Issue:** capture_exporter mock in test_expand_input_map test lacked perspective keyword param
- **Fix:** Added perspective="2D" keyword param to mock
- **Files modified:** backend/backend/tests/test_agentic_pipeline.py
- **Verification:** Test passes with pipeline now passing perspective kwarg
- **Committed in:** 28128c8 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep.

## Issues Encountered
- Pre-existing test failure in test_contract_generator.py (unrelated contract pipeline module) -- out of scope, not addressed

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 3D prompt builder and exporter wiring complete, ready for end-to-end 3D game generation
- Plans 09-03/09-04 can build on this foundation for integration testing and any remaining 3D features

---
*Phase: 09-add-3d-game-generation-support-to-agentic-pipeline*
*Completed: 2026-03-20*
