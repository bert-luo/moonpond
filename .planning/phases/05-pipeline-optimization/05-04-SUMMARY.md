---
phase: 05-pipeline-optimization
plan: 04
subsystem: api
tags: [pipeline, contract-first, integration, godot, wasm]

requires:
  - phase: 05-pipeline-optimization/02
    provides: "Spec Expander and Contract Generator stages"
  - phase: 05-pipeline-optimization/03
    provides: "Node Generator and Wiring Generator stages"
provides:
  - "Fully wired ContractPipeline connecting all 5 stages end-to-end"
  - "'contract' strategy registered in PIPELINES registry"
  - "End-to-end integration tests with mocked LLM"
affects: [api, frontend, deployment]

tech-stack:
  added: []
  patterns: ["contract-first pipeline wiring with intermediate artifact saving", "fake_copytree pattern for exporter test isolation"]

key-files:
  created: []
  modified:
    - backend/backend/pipelines/contract/pipeline.py
    - backend/backend/pipelines/registry.py
    - backend/backend/tests/test_contract_pipeline.py
    - backend/backend/tests/test_registry.py

key-decisions:
  - "Reused _slugify helper locally (same as MultiStagePipeline) rather than extracting shared util"
  - "fake_copytree pattern creates destination dir in tests so exporter file writes succeed"

patterns-established:
  - "Contract pipeline intermediate artifacts: 1_rich_game_spec.json, 2_game_contract.json, 3_node_files/, 4_wiring_files/, 5_result.json"

requirements-completed: [OPT-07, OPT-08]

duration: 4min
completed: 2026-03-17
---

# Phase 5 Plan 4: Wire ContractPipeline Summary

**Full ContractPipeline wiring all 5 stages (spec_expander, contract_generator, parallel_node_generation, wiring_generator, exporter) with registry registration and e2e tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-17T05:41:55Z
- **Completed:** 2026-03-17T05:46:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- ContractPipeline.generate() executes all 5 stages in sequence with intermediate artifact saving
- "contract" registered in PIPELINES, accessible via get_pipeline("contract")
- 4 integration tests covering full flow, intermediate saving, error handling, and instantiation
- Registry test confirms contract pipeline is discoverable

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire ContractPipeline with all 5 stages** - `a23ba21` (feat)
2. **Task 2: Register pipeline and add end-to-end integration test** - `0c32c88` (feat)

## Files Created/Modified
- `backend/backend/pipelines/contract/pipeline.py` - Full ContractPipeline implementation with 5-stage generate() method
- `backend/backend/pipelines/registry.py` - Added "contract": ContractPipeline to PIPELINES dict
- `backend/backend/tests/test_contract_pipeline.py` - 4 tests: instantiation, full flow, intermediates, error handling
- `backend/backend/tests/test_registry.py` - Added test_contract_pipeline_in_registry

## Decisions Made
- Reused _slugify helper locally rather than extracting to shared module (matches MultiStagePipeline pattern, avoids cross-module refactor)
- Used fake_copytree side_effect pattern to create destination dirs in tests, since mocking copytree prevents the exporter from creating the project directory

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed test mocking to patch GAMES_DIR in both exporter and pipeline modules**
- **Found during:** Task 1 (test verification)
- **Issue:** Pipeline imports GAMES_DIR from exporter at module load time; patching only backend.stages.exporter.GAMES_DIR leaves pipeline's local reference pointing to real path
- **Fix:** Added second patch for backend.pipelines.contract.pipeline.GAMES_DIR in all tests using tmp_path
- **Files modified:** backend/backend/tests/test_contract_pipeline.py
- **Verification:** All 4 tests pass with correct tmp_path usage
- **Committed in:** a23ba21 (Task 1 commit)

**2. [Rule 1 - Bug] Replaced skeleton test assertions with proper LLM mock setup**
- **Found during:** Task 1 (test verification)
- **Issue:** Existing skeleton tests from Plan 01 only patched AsyncAnthropic class but not client.messages.create, causing TypeError on await
- **Fix:** Rewrote tests with full mock chain: AsyncAnthropic -> mock_client -> messages.create as AsyncMock with side_effect
- **Files modified:** backend/backend/tests/test_contract_pipeline.py
- **Verification:** All tests pass
- **Committed in:** a23ba21 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep.

## Issues Encountered
- Pre-existing test failures in test_multi_stage_pipeline.py, test_generate.py, test_stages.py, test_stream.py due to MultiStagePipeline signature mismatch (missing job_id parameter). These are unrelated to this plan's changes and were not addressed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ContractPipeline is fully wired and registered, ready for use via the API with pipeline="contract" query parameter
- All 5 stages execute in sequence with proper error handling and progress events
- Pre-existing MultiStagePipeline signature mismatch should be addressed separately

---
*Phase: 05-pipeline-optimization*
*Completed: 2026-03-17*
