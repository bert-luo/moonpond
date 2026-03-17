---
phase: 05-pipeline-optimization
plan: 02
subsystem: api
tags: [anthropic, llm, pydantic, async, game-spec, contract]

# Dependency graph
requires:
  - phase: 05-pipeline-optimization/01
    provides: RichGameSpec, NodeContract, GameContract contract models
provides:
  - run_spec_expander() async function converting raw prompt to RichGameSpec
  - run_contract_generator() async function converting RichGameSpec to GameContract
  - Unit tests with mocked LLM for both stages
affects: [05-pipeline-optimization/03, 05-pipeline-optimization/04]

# Tech tracking
tech-stack:
  added: []
  patterns: [stage function signature (client, input, emit) -> output, json.loads + model_validate for LLM response parsing]

key-files:
  created:
    - backend/backend/stages/spec_expander.py
    - backend/backend/stages/contract_generator.py
    - backend/backend/tests/test_spec_expander.py
    - backend/backend/tests/test_contract_generator.py
  modified: []

key-decisions:
  - "Spec Expander uses max_tokens=4096 (sufficient for structured spec, less than code gen's 8192)"
  - "Contract Generator system prompt explicitly excludes game_manager.gd from node list"
  - "Both stages use pytest.mark.anyio (not asyncio) matching project convention"

patterns-established:
  - "Stage function signature: async def run_X(client: AsyncAnthropic, input, emit: EmitFn) -> OutputModel"
  - "System prompt includes full JSON schema for expected output format"

requirements-completed: [OPT-02, OPT-03]

# Metrics
duration: 4min
completed: 2026-03-17
---

# Phase 5 Plan 2: Spec Expander and Contract Generator Summary

**LLM-powered spec expansion and interface contract generation stages with mocked async tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-17T05:36:04Z
- **Completed:** 2026-03-17T05:40:10Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Spec Expander stage converts raw user prompts into detailed RichGameSpec with entity-level decomposition
- Contract Generator stage converts RichGameSpec into typed GameContract with node interfaces, control scheme, and visual style
- Both stages emit stage_start ProgressEvents for SSE tracking
- 9 unit tests with mocked Anthropic responses covering emission, parsing, return types, and prompt content

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement Spec Expander stage** - `30b1c69` (test: RED), `9e84e11` (feat: GREEN)
2. **Task 2: Implement Contract Generator stage** - `25ab160` (test: RED), `a89fb4c` (feat: GREEN)

_TDD tasks have two commits each (test -> feat)_

## Files Created/Modified
- `backend/backend/stages/spec_expander.py` - Stage 1: expands raw prompt into RichGameSpec via LLM
- `backend/backend/stages/contract_generator.py` - Stage 2: converts RichGameSpec into GameContract via LLM
- `backend/backend/tests/test_spec_expander.py` - 4 tests for spec expander with mocked Anthropic client
- `backend/backend/tests/test_contract_generator.py` - 5 tests for contract generator with mocked Anthropic client

## Decisions Made
- Used max_tokens=4096 for Spec Expander (structured spec output is smaller than code gen)
- Used max_tokens=8192 for Contract Generator (needs room for detailed node contracts)
- Contract Generator system prompt explicitly warns not to include game_manager.gd as a node
- Used pytest.mark.anyio (not pytest.mark.asyncio) matching project test convention with pytest-anyio

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed async test marker from pytest.mark.asyncio to pytest.mark.anyio**
- **Found during:** Task 1 (Spec Expander tests)
- **Issue:** Tests used @pytest.mark.asyncio but project uses pytest-anyio, not pytest-asyncio
- **Fix:** Changed all test markers to @pytest.mark.anyio matching existing test_node_generator.py convention
- **Files modified:** backend/backend/tests/test_spec_expander.py, backend/backend/tests/test_contract_generator.py
- **Verification:** All tests pass with anyio marker
- **Committed in:** 9e84e11 (part of Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for test execution. No scope creep.

## Issues Encountered
- Pre-existing test failure in test_generate.py (MultiStagePipeline.generate() signature mismatch) unrelated to this plan's changes. Logged as out-of-scope.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Spec Expander and Contract Generator are ready for integration into ContractPipeline (Plan 04)
- run_spec_expander and run_contract_generator follow the established stage function pattern
- GameContract output feeds directly into parallel node generation (Plan 03)

---
*Phase: 05-pipeline-optimization*
*Completed: 2026-03-17*
