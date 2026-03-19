---
phase: 06-programmatic-tscn-generation-and-display-configuration
verified: 2026-03-19T07:00:00Z
status: passed
score: 10/10 must-haves verified
re_verification: false
---

# Phase 06: Programmatic TSCN Generation and Display Configuration Verification Report

**Phase Goal:** Replace the LLM-based wiring generator with a deterministic TscnBuilder and SceneAssembler that produces all .tscn files programmatically from the contract and generated .gd files, and fix viewport size hallucination by adding display configuration to the template and node generator prompt
**Verified:** 2026-03-19T07:00:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | TscnBuilder.serialize() produces syntactically valid Godot 4 .tscn text | VERIFIED | tscn_builder.py L84-128: serialize() outputs [gd_scene], [ext_resource], [sub_resource], [node], [connection] sections in correct Godot 4 format. 14 passing tests confirm. |
| 2 | SceneAssembler generates Main.tscn with correct ext_resource references for all static nodes | VERIFIED | scene_assembler.py L87-140: _build_main_tscn adds Script and PackedScene ext_resources, skips dynamic nodes. Tests verify ext_resource paths and instance references. |
| 3 | SceneAssembler generates sub-scene .tscn files for every node with a non-Main scene_path | VERIFIED | scene_assembler.py L75-83: Pass B iterates contract.nodes for scene_path != main_scene, calls _build_sub_scene. Tests confirm HUD.tscn is created, Enemy.tscn is skipped (dynamic). |
| 4 | Every @onready %Name reference in .gd files becomes a child node in the corresponding sub-scene .tscn | VERIFIED | scene_assembler.py L163-173: parse_onready_unique_refs extracts refs, _build_sub_scene adds child nodes. Tests confirm ScoreLabel and HealthBar appear in HUD.tscn. |
| 5 | Physics body nodes get a CollisionShape2D child with a default RectangleShape2D | VERIFIED | scene_assembler.py L176-185: PHYSICS_NODE_TYPES check adds CollisionShape2D with RectangleShape2D sub_resource. Test test_physics_body_gets_collision_shape confirms. |
| 6 | ContractPipeline Stage 4 uses SceneAssembler instead of an LLM call | VERIFIED | pipeline.py L20,143-144: imports SceneAssembler, calls assembler.assemble(). No import of run_wiring_generator anywhere in codebase. |
| 7 | Node generator prompt no longer says "Also generate: {scene_path}" | VERIFIED | node_generator.py: grep for "Also generate" returns zero matches. The scene_path instruction block is completely removed. |
| 8 | Node generator prompt includes viewport size context (1152x648) | VERIFIED | node_generator.py L155-158: "The game viewport design resolution is 1152x648 pixels" with runtime getter recommendation. |
| 9 | project.godot template has [display] section with 1152x648 viewport and canvas_items stretch | VERIFIED | godot/templates/base_2d/project.godot L63-69: [display] section with viewport_width=1152, viewport_height=648, stretch/mode="canvas_items", stretch/aspect="expand". |
| 10 | Full test suite passes with the wiring LLM call removed | VERIFIED | 121 tests collected; 120 pass. 1 failure in test_contract_generator.py is pre-existing (mock missing type="text"), not introduced by Phase 06, documented in deferred-items.md. Phase-06 specific tests: 36/36 pass. |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/backend/pipelines/contract/tscn_builder.py` | TscnBuilder utility class, min 60 lines | VERIFIED | 141 lines, exports TscnBuilder with add_ext_resource, add_sub_resource, add_node, add_connection, serialize |
| `backend/backend/pipelines/contract/scene_assembler.py` | SceneAssembler + parse_onready_unique_refs, min 80 lines | VERIFIED | 197 lines, exports SceneAssembler and parse_onready_unique_refs |
| `backend/backend/tests/test_tscn_builder.py` | Unit tests for TscnBuilder, min 40 lines | VERIFIED | 138 lines, 14 tests covering all TscnBuilder features |
| `backend/backend/tests/test_scene_assembler.py` | Unit tests for SceneAssembler and @onready parser, min 60 lines | VERIFIED | 294 lines, 22 tests covering parser and assembler |
| `backend/backend/pipelines/contract/pipeline.py` | ContractPipeline using SceneAssembler for stage 4 | VERIFIED | L20: imports SceneAssembler; L143-144: uses it for Stage 4 |
| `backend/backend/pipelines/contract/node_generator.py` | Node generator with viewport hint, no .tscn instruction | VERIFIED | L155-158: viewport hint present; "Also generate" removed |
| `godot/templates/base_2d/project.godot` | Template with [display] section | VERIFIED | L63-69: [display] section with correct values |
| `backend/backend/pipelines/contract/wiring_generator.py` | Gutted, keeping only _patch_project_godot_autoloads | VERIFIED | 46 lines, only _patch_project_godot_autoloads and constants remain. No LLM imports or functions. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| scene_assembler.py | tscn_builder.py | import TscnBuilder | WIRED | L19: `from backend.pipelines.contract.tscn_builder import TscnBuilder` |
| scene_assembler.py | models.py | import GameContract, NodeContract | WIRED | L18: `from backend.pipelines.contract.models import GameContract, NodeContract` |
| pipeline.py | scene_assembler.py | import SceneAssembler | WIRED | L20: `from backend.pipelines.contract.scene_assembler import SceneAssembler`; L143-144: instantiated and called |
| pipeline.py | wiring_generator.py | import _patch_project_godot_autoloads only | WIRED | L21-24: imports only `_patch_project_godot_autoloads` and `TEMPLATE_DIR`; no run_wiring_generator |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TSCN-01 | 06-01 | Generated games have all required .tscn files (Main.tscn + sub-scenes) | SATISFIED | SceneAssembler.assemble() returns Main.tscn + all sub-scene .tscn files. Tests verify HUD.tscn and Bird.tscn are generated. |
| TSCN-02 | 06-01 | Every @onready %Name reference resolves to a child node in the .tscn | SATISFIED | parse_onready_unique_refs extracts refs; _build_sub_scene creates child nodes for each. Tests verify ScoreLabel, HealthBar in HUD.tscn. |
| TSCN-03 | 06-01 | Every preload("res://X.tscn") has the corresponding .tscn file | SATISFIED | SceneAssembler generates .tscn for every node with scene_path != None. Main.tscn uses instance=ExtResource for these scene_paths. |
| TSCN-04 | 06-01, 06-02 | No LLM calls for .tscn generation -- fully deterministic | SATISFIED | TscnBuilder and SceneAssembler are pure Python, no client/LLM imports. run_wiring_generator completely removed. Pipeline Stage 4 calls assembler.assemble(). |
| TSCN-05 | 06-02 | All scripts use consistent viewport dimensions | SATISFIED | project.godot has [display] with 1152x648. Node generator prompt includes "1152x648 pixels" with runtime getter recommendation. |
| TSCN-06 | 06-01, 06-02 | Existing test suite passes; new tests cover TscnBuilder and SceneAssembler | SATISFIED | 36 new tests (14 TscnBuilder + 22 SceneAssembler) all pass. Existing pipeline tests updated and passing. 1 pre-existing failure in test_contract_generator.py (not introduced by Phase 06). |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | - | - | - | No anti-patterns found in any Phase 06 artifacts |

### Human Verification Required

### 1. End-to-end game generation with SceneAssembler

**Test:** Run a full pipeline generation with a real prompt and verify the exported WASM loads in browser
**Expected:** Game loads without errors, all scene nodes visible, no "missing node" or "invalid resource" errors in Godot console
**Why human:** Requires running the full pipeline with a real LLM, exporting via Godot headless, and loading in browser

### 2. Viewport dimensions consistency

**Test:** Generate a game and check that generated GDScript uses runtime viewport queries instead of hardcoded pixel values
**Expected:** Generated .gd files reference get_viewport().get_visible_rect().size instead of hardcoded numbers like 1920, 1080, etc.
**Why human:** Depends on LLM behavior in response to the prompt hint -- cannot verify programmatically

### Gaps Summary

No gaps found. All 10 observable truths verified. All 6 requirements (TSCN-01 through TSCN-06) satisfied. All artifacts exist, are substantive, and are properly wired. The single test failure (`test_contract_generator.py`) is pre-existing and documented in `deferred-items.md` -- it was not introduced by Phase 06 and does not affect any Phase 06 functionality.

---

_Verified: 2026-03-19T07:00:00Z_
_Verifier: Claude (gsd-verifier)_
