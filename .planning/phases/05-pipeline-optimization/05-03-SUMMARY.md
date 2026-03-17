---
phase: 05-pipeline-optimization
plan: 03
subsystem: api
tags: [asyncio, parallel-generation, topological-sort, godot, tscn, wiring]

# Dependency graph
requires:
  - phase: 05-pipeline-optimization
    provides: GameContract, NodeContract, ContractPipeline skeleton
  - phase: 02-backend-api
    provides: GamePipeline Protocol, ProgressEvent, EmitFn
  - phase: 03-llm-pipeline
    provides: LLM streaming pattern, code_generator.py reference
provides:
  - run_parallel_node_generation() with topological wave scheduling
  - run_wiring_generator() producing Main.tscn and project.godot
  - Fault-tolerant parallel generation (failed nodes don't kill wave)
affects: [05-04, 05-05]

# Tech tracking
tech-stack:
  added: []
  patterns: [topological wave scheduling via dependency depth, asyncio.gather with return_exceptions for fault tolerance, template-patching for project.godot autoloads]

key-files:
  created:
    - backend/backend/stages/node_generator.py
    - backend/backend/stages/wiring_generator.py
    - backend/backend/tests/test_node_generator.py
    - backend/backend/tests/test_wiring_generator.py
  modified: []

key-decisions:
  - "Topological depth map with cycle detection for wave scheduling"
  - "System prompt scoped per-node with ONLY constraint to prevent cross-node bleed"
  - "project.godot patched via regex replacement of [autoload] section preserving [input]"

patterns-established:
  - "Wave-based parallel generation: depth map -> group by depth -> asyncio.gather per wave"
  - "Template patching over LLM generation for configuration files (project.godot)"

requirements-completed: [OPT-04, OPT-05, OPT-06]

# Metrics
duration: 4min
completed: 2026-03-16
---

# Phase 5 Plan 3: Parallel Node Generation and Wiring Generator Summary

**Topological wave-scheduled parallel node generation with asyncio.gather and deterministic Main.tscn/project.godot assembly**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-17T05:36:11Z
- **Completed:** 2026-03-17T05:39:47Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Parallel node generation with topological sorting into dependency waves (flat, 2-level, 3-level, diamond topologies)
- Fault-tolerant generation via asyncio.gather(return_exceptions=True) -- failed nodes don't kill other parallel generators
- Wiring generator produces Main.tscn with unique ExtResource IDs and patches project.godot only when autoloads present
- 18 passing tests covering all topologies, failure handling, prompt correctness, and wiring integrity

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement parallel node generator** - `079c1cb` (feat)
2. **Task 2: Implement wiring generator** - `822d643` (feat)

_Note: TDD tasks each had RED (import failure) -> GREEN (implementation) phases._

## Files Created/Modified
- `backend/backend/stages/node_generator.py` - Parallel node generation with topological wave scheduling
- `backend/backend/stages/wiring_generator.py` - Main.tscn generation and project.godot autoload patching
- `backend/backend/tests/test_node_generator.py` - 10 tests: topology variants, failure handling, prompt validation
- `backend/backend/tests/test_wiring_generator.py` - 8 tests: tscn output, ext_resource uniqueness, autoload patching

## Decisions Made
- Topological depth map with cycle detection for wave scheduling (nodes with empty deps = depth 0, others = max(dep depths) + 1)
- Per-node system prompt scoped with "ONLY files for: {script_path}" to prevent cross-node generation bleed
- project.godot patched via regex replacement of [autoload] section rather than LLM generation (preserves [input] actions)
- Mock matching uses system prompt pattern "ONLY files for: {path}" for precise node identification in tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test mock matching logic**
- **Found during:** Task 1 (parallel node generator tests)
- **Issue:** Mock client matched script_path in user message but the contract JSON contains all script_paths, causing false matches for orchestrator nodes
- **Fix:** Changed mock to match on system prompt pattern "ONLY files for: {script_path}" which is unique per node
- **Files modified:** backend/backend/tests/test_node_generator.py
- **Verification:** All 10 tests pass
- **Committed in:** 079c1cb (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test fixture fix. No scope creep.

## Issues Encountered
- pytest --timeout flag not available (pytest-timeout not installed). Used pytest without timeout for verification. Out of scope to add the dependency.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- node_generator.py and wiring_generator.py ready for import by ContractPipeline (Plan 05-04/05-05)
- All exports match plan interfaces: run_parallel_node_generation(), run_wiring_generator()
- Both stages accept GameContract from contract_models.py and emit ProgressEvents

## Self-Check: PASSED

All 4 created files verified on disk. Both task commits (079c1cb, 822d643) verified in git log.

---
*Phase: 05-pipeline-optimization*
*Completed: 2026-03-16*
