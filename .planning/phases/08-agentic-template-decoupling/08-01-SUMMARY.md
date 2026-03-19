---
phase: 08-agentic-template-decoupling
plan: 01
subsystem: pipeline
tags: [godot, input-map, system-prompt, assets, agentic-pipeline]

# Dependency graph
requires:
  - phase: 07-agentic-pipeline
    provides: GENERATOR_SYSTEM_PROMPT, file_generator.py agent loop
  - phase: 01-template
    provides: project.godot format, input action keycodes
provides:
  - expand_input_map() utility converting simplified key names to Godot Object() format
  - Updated GENERATOR_SYSTEM_PROMPT with project.godot skeleton and asset paths
  - Removal of dead template files (game_manager.gd, Main.tscn)
affects: [agentic-pipeline, exporter, template]

# Tech tracking
tech-stack:
  added: []
  patterns: [regex-based INI section replacement, simplified-key-to-Object expansion]

key-files:
  created:
    - backend/backend/pipelines/agentic/input_map.py
    - backend/backend/tests/test_input_map.py
    - backend/backend/tests/test_file_generator_prompt.py
  modified:
    - backend/backend/pipelines/agentic/file_generator.py

key-decisions:
  - "Hardcoded KEY_MAP dict for Godot physical keycodes -- stable across 4.x, no runtime lookup needed"
  - "Regex section isolation for [input] parsing -- same pattern as wiring_generator.py, configparser breaks on Object() values"
  - "_build_asset_section() generates prompt text from imported constants -- no hardcoded paths in prompt string"

patterns-established:
  - "Simplified input format: LLM writes action=key_name, Python expands to full Object() serialization"
  - "Asset path surfacing: import from assets.py and embed in system prompt programmatically"

requirements-completed: [TMPL-SLIM, AGENT-PROJGODOT, AGENT-INPUTMAP, AGENT-ASSETS]

# Metrics
duration: 11min
completed: 2026-03-19
---

# Phase 08 Plan 01: Agentic Template Decoupling Summary

**expand_input_map utility for simplified key-to-Object() expansion, GENERATOR_SYSTEM_PROMPT rewritten with project.godot skeleton and asset paths, dead template files removed**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-19T22:33:10Z
- **Completed:** 2026-03-19T22:44:33Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- expand_input_map() converts simplified key names (e.g. move_left=arrow_left) to full Godot Object(InputEventKey,...) format with correct physical keycodes
- GENERATOR_SYSTEM_PROMPT now instructs LLM to generate project.godot with pre-filled [rendering] and [display] sections, [autoload] convention, and simplified [input] format
- All asset paths (shaders, palettes, particles, control snippets) surfaced in system prompt from assets.py constants
- game_manager.gd, game_manager.gd.uid, and Main.tscn removed from template (verified safe for all pipelines)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create input_map.py with expand_input_map utility + test suite** - `b256c37` (feat, TDD)
2. **Task 2: Rewrite GENERATOR_SYSTEM_PROMPT + strip template files + prompt tests** - `a15d4a0` (feat)

## Files Created/Modified
- `backend/backend/pipelines/agentic/input_map.py` - KEY_MAP, _EVENT_TEMPLATE, expand_input_map() utility
- `backend/backend/tests/test_input_map.py` - 18 tests covering expansion, passthrough, edge cases, round-trip
- `backend/backend/pipelines/agentic/file_generator.py` - Rewritten GENERATOR_SYSTEM_PROMPT with skeleton + assets
- `backend/backend/tests/test_file_generator_prompt.py` - 10 tests asserting prompt content
- `godot/templates/base_2d/game_manager.gd` - DELETED
- `godot/templates/base_2d/Main.tscn` - DELETED

## Decisions Made
- Hardcoded KEY_MAP dict for Godot physical keycodes -- stable across 4.x, no runtime lookup needed
- Regex section isolation for [input] parsing -- same pattern as wiring_generator.py
- _build_asset_section() generates prompt text from imported constants -- no hardcoded paths in prompt string

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- 5 pre-existing test failures in test_agentic_pipeline.py (pipeline.py return value unpacking issues) -- confirmed pre-existing via git stash verification, out of scope for this plan

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- expand_input_map() ready to be called in pipeline.py before export (plan 02 integration)
- GENERATOR_SYSTEM_PROMPT ready for use by the agentic pipeline agent loop
- Template stripped to essentials; all other pipelines unaffected

## Self-Check: PASSED

All created files exist, all deleted files confirmed absent, both task commits verified.

---
*Phase: 08-agentic-template-decoupling*
*Completed: 2026-03-19*
