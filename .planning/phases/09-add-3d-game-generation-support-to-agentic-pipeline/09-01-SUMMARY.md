---
phase: 09-add-3d-game-generation-support-to-agentic-pipeline
plan: 01
subsystem: api
tags: [pydantic, godot, 3d, agentic-pipeline, spec-generator]

# Dependency graph
requires:
  - phase: 07-agentic-pipeline
    provides: AgenticGameSpec model, spec_generator, file_generator
  - phase: 08-agentic-template-decoupling
    provides: Decoupled template with asset prompt surface
provides:
  - "AgenticGameSpec.perspective field (Literal['2D', '3D'], default '2D')"
  - "SUBMIT_SPEC_TOOL schema with perspective as required enum"
  - "SPEC_SYSTEM_PROMPT with 2D/3D determination instruction"
  - "godot/templates/base_3d/ directory with curated 3D-compatible assets"
affects: [09-02, exporter, pipeline-routing]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Literal union default for backward-compatible schema extension"]

key-files:
  created:
    - godot/templates/base_3d/export_presets.cfg
    - godot/templates/base_3d/default_bus_layout.tres
    - godot/templates/base_3d/project.godot
    - godot/templates/base_3d/assets/shaders/glow.gdshader
    - godot/templates/base_3d/assets/shaders/chromatic_aberration.gdshader
    - godot/templates/base_3d/assets/palettes/
    - godot/templates/base_3d/assets/particles/
  modified:
    - backend/backend/pipelines/agentic/models.py
    - backend/backend/pipelines/agentic/spec_generator.py
    - backend/backend/tests/test_agentic_models.py

key-decisions:
  - "perspective field defaults to '2D' for full backward compatibility with existing specs"
  - "glow and chromatic_aberration shaders included in 3D template (canvas_item, usable on CanvasLayer/UI)"
  - "control_snippets excluded from 3D template (Node2D scripts, not applicable to 3D)"

patterns-established:
  - "Backward-compatible schema extension: new Literal field with default preserving existing behavior"

requirements-completed: [3D-SCHEMA, 3D-SPEC, 3D-TEMPLATE]

# Metrics
duration: 1min
completed: 2026-03-20
---

# Phase 09 Plan 01: Schema, Spec Generator, and 3D Template Summary

**Added perspective field (2D/3D) to AgenticGameSpec and spec generator tool schema, created base_3d Godot template with curated 3D-compatible assets**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-20T08:09:59Z
- **Completed:** 2026-03-20T08:11:16Z
- **Tasks:** 2
- **Files modified:** 45

## Accomplishments
- AgenticGameSpec now accepts perspective="2D" (default) and "3D", rejects invalid values
- SUBMIT_SPEC_TOOL schema includes perspective as required enum property
- SPEC_SYSTEM_PROMPT instructs LLM to determine 2D vs 3D and use dimension-aware entity types
- base_3d template created with export config, audio bus, glow/chromatic shaders, palettes, particles

## Task Commits

Each task was committed atomically:

1. **Task 1: Add perspective field to AgenticGameSpec and update spec generator** - `777ae39` (feat)
2. **Task 2: Create base_3d Godot template directory** - `0c28bad` (feat)

## Files Created/Modified
- `backend/backend/pipelines/agentic/models.py` - Added perspective: Literal["2D", "3D"] = "2D"
- `backend/backend/pipelines/agentic/spec_generator.py` - Added perspective to tool schema, prompt, and entity type description
- `backend/backend/tests/test_agentic_models.py` - Added 4 tests for perspective validation and tool schema
- `godot/templates/base_3d/` - Full 3D template directory (export config, shaders, palettes, particles)

## Decisions Made
- perspective field defaults to "2D" for full backward compatibility with existing specs
- glow and chromatic_aberration shaders included in 3D template (canvas_item type, usable on CanvasLayer/UI overlays)
- control_snippets excluded from 3D template (Node2D scripts, not applicable to 3D)
- pixel_art, scanlines, screen_distortion shaders excluded (2D-only effects)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failure in test_agentic_pipeline.py::test_targeted_fix (mock_file_gen missing existing_files kwarg) -- not caused by this plan's changes, confirmed by running test on clean state before changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- perspective field flows through AgenticGameSpec, ready for Plan 02 to add template routing and exporter 3D support
- base_3d template ready for use by the exporter when perspective="3D"

---
*Phase: 09-add-3d-game-generation-support-to-agentic-pipeline*
*Completed: 2026-03-20*
