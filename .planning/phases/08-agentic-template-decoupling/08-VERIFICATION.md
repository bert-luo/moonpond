---
phase: 08-agentic-template-decoupling
verified: 2026-03-19T23:30:00Z
status: passed
score: 11/11 must-haves verified
re_verification: false
---

# Phase 08: Agentic Template Decoupling Verification Report

**Phase Goal:** Decouple the agentic pipeline from hardcoded template files so the LLM generates project.godot (with input maps), game_manager.gd, and Main.tscn itself, guided by an asset-aware system prompt.
**Verified:** 2026-03-19T23:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | expand_input_map converts simplified key names to full Godot Object(InputEventKey,...) format | VERIFIED | input_map.py lines 66-133: regex-based expansion with KEY_MAP lookup; test_input_map.py test_expand_simple_action confirms Object(InputEventKey with physical_keycode:4194319 |
| 2 | expand_input_map passes through lines already in Object() format unchanged | VERIFIED | input_map.py lines 97-109: detects Object( or { and passes through entire block; test_passthrough_already_expanded and test_passthrough_brace_line confirm |
| 3 | expand_input_map preserves [rendering] and [display] sections untouched | VERIFIED | Regex _INPUT_SECTION_RE only modifies [input] section body; test_full_round_trip_preserves_rendering and test_full_round_trip_preserves_display confirm with full project.godot |
| 4 | GENERATOR_SYSTEM_PROMPT no longer contains 'Do NOT generate project.godot' | VERIFIED | file_generator.py GENERATOR_SYSTEM_PROMPT (lines 160-205) does not contain that phrase; test_no_prohibition asserts this |
| 5 | GENERATOR_SYSTEM_PROMPT contains project.godot skeleton with [rendering] and [display] sections | VERIFIED | file_generator.py lines 180-203: [rendering] with gl_compatibility, [display] with 1152x648, [autoload] example, [input] simplified format |
| 6 | GENERATOR_SYSTEM_PROMPT lists available asset paths (shaders, palettes, particles, control snippets) | VERIFIED | file_generator.py lines 134-157: _build_asset_section() programmatically builds from assets.py imports; lines 205: appended to prompt. Tests test_contains_shader_path through test_contains_control_snippet_path confirm |
| 7 | game_manager.gd, game_manager.gd.uid, and Main.tscn no longer exist in godot/templates/base_2d/ | VERIFIED | All three files confirmed absent from filesystem; git status shows clean working tree |
| 8 | AgenticPipeline calls expand_input_map on generated project.godot before exporting | VERIFIED | pipeline.py lines 226-229: conditional call after generate-verify-fix loop, before Stage 3 export; test_expand_input_map_called_when_project_godot_present confirms expanded Object() format reaches exporter |
| 9 | Expanded project.godot is written to disk and passed to the exporter | VERIFIED | pipeline.py line 229: writes to project_dir / "project.godot"; line 228: updates all_files dict which is passed to run_exporter on line 232 |
| 10 | If LLM does not generate project.godot, the pipeline still completes (template fallback) | VERIFIED | pipeline.py line 227: conditional `if "project.godot" in all_files`; test_pipeline_completes_without_project_godot confirms expand_input_map not called and pipeline succeeds |
| 11 | Existing agentic pipeline tests continue to pass | VERIFIED | 42 tests pass (18 input_map + 10 prompt + 14 pipeline) including all pre-existing tests |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/backend/pipelines/agentic/input_map.py` | expand_input_map utility with KEY_MAP and _EVENT_TEMPLATE | VERIFIED | 134 lines, exports expand_input_map, KEY_MAP has 62 keys (arrows, common, a-z, 0-9, f1-f12) |
| `backend/backend/pipelines/agentic/file_generator.py` | Updated GENERATOR_SYSTEM_PROMPT with skeleton and asset paths | VERIFIED | Contains "You MUST generate project.godot", imports from assets.py, _build_asset_section() |
| `backend/backend/tests/test_input_map.py` | Unit tests for expand_input_map (min 40 lines) | VERIFIED | 220 lines, 18 tests covering expansion, passthrough, edge cases, round-trip |
| `backend/backend/tests/test_file_generator_prompt.py` | Unit tests for GENERATOR_SYSTEM_PROMPT content (min 20 lines) | VERIFIED | 76 lines, 10 tests asserting prompt content |
| `backend/backend/pipelines/agentic/pipeline.py` | Pipeline integration calling expand_input_map before export | VERIFIED | Lines 226-229: conditional expand_input_map call with disk write |
| `backend/backend/tests/test_agentic_pipeline.py` | Integration test verifying input map expansion call | VERIFIED | 2 new tests: test_expand_input_map_called_when_project_godot_present, test_pipeline_completes_without_project_godot |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| file_generator.py | assets.py | `from backend.pipelines.assets import SHADER_PATHS, PALETTE_PATHS, PARTICLE_PATHS, CONTROL_SNIPPET_PATHS` | WIRED | Lines 17-22: all four constants imported and used in _build_asset_section() |
| pipeline.py | input_map.py | `from backend.pipelines.agentic.input_map import expand_input_map` | WIRED | Line 17: import; line 228: called conditionally on project.godot content |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TMPL-SLIM | 08-01 | Remove game_manager.gd and Main.tscn from base_2d template | SATISFIED | All three files confirmed absent from godot/templates/base_2d/ |
| AGENT-PROJGODOT | 08-01 | LLM generates project.godot with correct autoloads/input | SATISFIED | GENERATOR_SYSTEM_PROMPT contains "You MUST generate project.godot" with skeleton |
| AGENT-INPUTMAP | 08-01 | Python expand_input_map() converts simplified key names to Godot format | SATISFIED | input_map.py with 18 unit tests all passing |
| AGENT-ASSETS | 08-01 | Surface asset paths in file generator system prompt | SATISFIED | _build_asset_section() programmatically includes all asset categories |
| PIPE-INPUTMAP | 08-02 | pipeline.py calls expand_input_map when project.godot in all_files | SATISFIED | pipeline.py lines 226-229 with 2 integration tests |

**Note:** These five requirement IDs (TMPL-SLIM, AGENT-PROJGODOT, AGENT-INPUTMAP, AGENT-ASSETS, PIPE-INPUTMAP) are defined in ROADMAP.md phase 08 and 08-RESEARCH.md but are NOT present in REQUIREMENTS.md's traceability table. This is a documentation gap only -- the requirements themselves are fully implemented. REQUIREMENTS.md should be updated to include phase 08 requirement IDs in the traceability table.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| file_generator.py | 136 | "placeholders" in prompt text | Info | Not a code placeholder -- instructs LLM to use assets instead of generating placeholders. No issue. |

No blockers, no warnings.

### Human Verification Required

### 1. End-to-End Game Generation with project.godot

**Test:** Run the full agentic pipeline with a game prompt (e.g. "make a platformer") and verify the generated project.godot contains correct autoloads, expanded input maps, and [rendering]/[display] sections.
**Expected:** Generated game exports to WASM successfully with working input controls.
**Why human:** Requires live LLM calls and Godot export runtime.

### 2. Asset Path Usage in Generated Games

**Test:** Generate a game and check whether the LLM actually references shader/palette/particle paths from the system prompt.
**Expected:** At least some asset paths appear in generated GDScript or .tscn files.
**Why human:** Depends on LLM behavior with the new system prompt -- cannot verify programmatically without running generation.

### Gaps Summary

No gaps found. All 11 observable truths verified. All 6 artifacts exist, are substantive, and are properly wired. All 5 requirement IDs are satisfied. All 42 tests pass. Template files confirmed deleted.

The only documentation note is that REQUIREMENTS.md traceability table does not yet include phase 08 requirement IDs -- this is cosmetic and does not affect code functionality.

---

_Verified: 2026-03-19T23:30:00Z_
_Verifier: Claude (gsd-verifier)_
