---
phase: 06-programmatic-tscn-generation-and-display-configuration
plan: 01
subsystem: pipeline
tags: [godot, tscn, scene-assembly, deterministic-generation, tdd]

requires:
  - phase: 05.2-fix-pipeline-generation-failure-modes
    provides: "Contract models (GameContract, NodeContract) with spawn_mode and scene_path"
provides:
  - "TscnBuilder utility class for programmatic .tscn generation"
  - "SceneAssembler orchestrator producing Main.tscn + sub-scene .tscn files"
  - "parse_onready_unique_refs parser for @onready %Name extraction"
affects: [06-02, pipeline-integration, wiring-generator-replacement]

tech-stack:
  added: []
  patterns: [TDD red-green, deterministic scene generation, regex-based GDScript parsing]

key-files:
  created:
    - backend/backend/pipelines/contract/tscn_builder.py
    - backend/backend/pipelines/contract/scene_assembler.py
    - backend/backend/tests/test_tscn_builder.py
    - backend/backend/tests/test_scene_assembler.py
  modified: []

key-decisions:
  - "TscnBuilder uses monotonic counter for ext_resource/sub_resource IDs"
  - "Sub-resource IDs use Type_N format for readability"
  - "SceneAssembler derives PascalCase node names from script_path stems"
  - "Physics bodies auto-get CollisionShape2D with default 64x64 RectangleShape2D"
  - "No [connection] entries in Main.tscn — signals wired in _ready() per design"

patterns-established:
  - "TscnBuilder pattern: builder.add_ext_resource/add_node/serialize() for any .tscn"
  - "SceneAssembler.assemble() static method returning dict[str, str] filename -> content"

requirements-completed: [TSCN-01, TSCN-02, TSCN-03, TSCN-04, TSCN-06]

duration: 3min
completed: 2026-03-19
---

# Phase 06 Plan 01: TscnBuilder and SceneAssembler Summary

**Deterministic .tscn builder and scene assembler replacing LLM-based wiring with programmatic Godot 4 scene generation from contract + .gd files**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-19T06:02:55Z
- **Completed:** 2026-03-19T06:06:01Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- TscnBuilder utility class producing valid Godot 4 .tscn text for all node configurations
- SceneAssembler generating Main.tscn with correct ext_resource references plus sub-scene .tscn files
- @onready %Name parser extracting unique node references from generated .gd files
- Physics body auto-detection adding CollisionShape2D children with default shapes
- Full TDD coverage: 36 tests (14 TscnBuilder + 22 SceneAssembler)

## Task Commits

Each task was committed atomically:

1. **Task 1: TscnBuilder utility class with tests**
   - `b0f82cd` (test) - RED: failing tests for TscnBuilder
   - `00730da` (feat) - GREEN: TscnBuilder implementation, 14 tests pass
2. **Task 2: SceneAssembler + @onready parser with tests**
   - `74a4946` (test) - RED: failing tests for SceneAssembler
   - `f8491bf` (feat) - GREEN: SceneAssembler implementation, 22 tests pass

## Files Created/Modified
- `backend/backend/pipelines/contract/tscn_builder.py` - TscnBuilder class for programmatic .tscn generation
- `backend/backend/pipelines/contract/scene_assembler.py` - SceneAssembler + parse_onready_unique_refs
- `backend/backend/tests/test_tscn_builder.py` - 14 unit tests for TscnBuilder
- `backend/backend/tests/test_scene_assembler.py` - 22 unit tests for SceneAssembler and parser

## Decisions Made
- TscnBuilder uses monotonic counter for resource IDs (simple, deterministic)
- Sub-resource IDs use Type_N format (e.g., RectangleShape2D_3) for readability in generated files
- Node names derived from script_path stems via PascalCase conversion
- Physics bodies (CharacterBody2D, StaticBody2D, RigidBody2D, Area2D) auto-get CollisionShape2D
- No [connection] entries in Main.tscn — signals wired in _ready() per existing design decision

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- TscnBuilder and SceneAssembler ready for integration into ContractPipeline (Plan 06-02)
- wiring_generator.py LLM call can be replaced with SceneAssembler.assemble()
- Display configuration (viewport size, stretch mode) to be addressed in Plan 06-02

---
*Phase: 06-programmatic-tscn-generation-and-display-configuration*
*Completed: 2026-03-19*
