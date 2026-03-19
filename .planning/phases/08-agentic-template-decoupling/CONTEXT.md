# Phase 08: Agentic Pipeline Template Decoupling

## Problem Statement

The agentic pipeline tells the LLM "Do NOT generate project.godot" but the template's `project.godot` has no knowledge of what the LLM generates. This creates a systematic information transfer failure:

1. **Autoload disconnect**: The LLM generates `GameManager.gd` (score/game-over logic) and every script references `GameManager` as a bare autoload singleton. But the template's `project.godot` registers `game_manager.gd` (the template's palette/state manager) as the autoload — not the LLM's version. Result: every `GameManager.xxx` call crashes at runtime.

2. **Naming collision**: Two conflicting files end up in the final project — `GameManager.gd` (generated) and `game_manager.gd` (template) — with completely different APIs.

3. **Input map blindness**: The LLM may generate code using input actions that don't exist in the template's `[input]` section, or may not use the template's pre-defined actions at all.

4. **Dead template files**: `Main.tscn` (empty Node2D) is always overwritten by the LLM's version. `game_manager.gd` is superseded by whatever the LLM generates. These template files add no value for the agentic pipeline.

5. **Asset unawareness**: The template ships shaders, palettes, particles, and control snippets (`assets/`) but the agentic pipeline never tells the LLM they exist. Unlike the contract/general/multi_stage pipelines which pass asset paths from `assets.py` into their prompts.

## Root Cause Analysis

The contract and multi_stage pipelines were designed around the template — they have structured stages that know what the template provides and fill in the gaps (e.g., `_patch_project_godot_autoloads` in `wiring_generator.py`). The agentic pipeline is fundamentally different: a single LLM agent generates all files autonomously. The template's constraints were carried over without an equivalent mechanism to bridge the gap.

The core issue is that `project.godot` is a configuration file that must be consistent with the generated code, but neither side knows about the other.

## Evidence

Inspected `games/doodle-leap_20260319-183654/`:

- **Iteration 1**: Verifier flagged 5 critical errors. Missing `Main.tscn`, `GameManager` autoload not configured, `Projectile` calls undefined method, `BreakablePlatform.on_player_landed()` never called, `SpringPlatform.on_player_landed()` never called.
- **Iteration 2**: Still 3 critical errors. `Background.gd`, `ScoreLabel.gd`, `GameOverScreen.gd` all use bare `GameManager` references that crash because `project.godot` doesn't register the LLM's `GameManager.gd` as an autoload.
- **Iteration 3**: 1 critical error remaining (`BreakablePlatform` physics override). The `GameManager` autoload issue was "fixed" by the verifier loop adding guard checks — a workaround, not a real fix.
- **Final project dir**: Contains both `GameManager.gd` and `game_manager.gd` — two conflicting singletons.

## Approach: Slim Template + LLM Generates project.godot

### Design Principles

- The template should only provide things the LLM **cannot** generate: export presets, Godot import cache, pre-built visual assets.
- The LLM should have full control over project configuration that its generated code depends on.
- Complex/verbose Godot formats (input map serialization) should be handled by Python utilities, not the LLM.

### 1. Strip template to essentials

**Remove from `godot/templates/base_2d/`:**
- `game_manager.gd` + `.uid` — LLM always generates its own game manager
- `Main.tscn` — LLM always generates its own main scene

**Keep in template:**
- `export_presets.cfg` — WASM export boilerplate, not game-specific
- `.godot/` — engine import cache
- `assets/` — pre-built shaders, palettes, particles, control snippets
- `default_bus_layout.tres` — audio bus defaults
- `project.godot` — kept as a fallback skeleton (LLM's version overwrites it)

### 2. Let the LLM generate `project.godot`

**Remove** the instruction "Do NOT generate project.godot, export_presets.cfg, or .import files" from the file generator system prompt.

**Replace with**: Inject the required `project.godot` skeleton into the system prompt. The skeleton includes `[rendering]` and `[display]` sections pre-filled (these are non-negotiable for WASM export). The LLM fills in `[application]` (main scene, project name), `[autoload]` (its singletons), and `[input]` (action declarations).

**For input actions**: The Godot `Object(InputEventKey, ...)` serialization format is extremely verbose (~5 lines per action). Rather than having the LLM produce this, provide a simplified format:
- LLM writes `[input]` with action names and human-readable key names (e.g., `move_left=arrow_left`, `shoot=z`)
- A Python post-processor (`expand_input_map()`) converts these to the full Godot `Object()` serialization before export
- Include a mapping of common key names to Godot physical keycodes

### 3. Surface available assets in the prompt

Add to the file generator system prompt:
- Available shader paths (from `assets.py`: pixel_art, glow, scanlines, etc.)
- Available palette paths
- Available particle scene paths
- Available control snippet paths

This lets the LLM optionally use pre-built visual assets rather than generating everything from scratch.

### 4. Input map expansion utility

New utility function that:
- Parses the LLM's simplified `[input]` section from the generated `project.godot`
- Maps key names to Godot physical keycodes (arrow keys, letters, space, escape, etc.)
- Expands each action into the full `Object(InputEventKey, ...)` serialization
- Rewrites the `[input]` section in-place before the exporter copies files

### 5. Update exporter integration

The exporter (`exporter.py`) already writes generated files after copying the template (`dirs_exist_ok=True`), so the LLM's `project.godot` naturally overwrites the template's. The only addition is running the input map expansion on the generated `project.godot` before export.

## What Changes

| File | Change |
|------|--------|
| `godot/templates/base_2d/game_manager.gd` | DELETE — LLM generates its own |
| `godot/templates/base_2d/game_manager.gd.uid` | DELETE |
| `godot/templates/base_2d/Main.tscn` | DELETE — LLM generates its own |
| `backend/backend/pipelines/agentic/file_generator.py` | Rewrite system prompt: remove "do not generate" rule, add project.godot skeleton, add asset paths, add simplified input format instructions |
| NEW: `backend/backend/pipelines/agentic/input_map.py` | `expand_input_map()` utility — converts simplified input actions to Godot format |
| `backend/backend/pipelines/agentic/pipeline.py` | Call input map expansion on generated `project.godot` before passing to exporter |
| `backend/backend/pipelines/assets.py` | No change — already has the constants, just needs to be imported by agentic pipeline |

## Impact on Other Pipelines

The contract, general, and multi_stage pipelines all import from `assets.py` and use `_patch_project_godot_autoloads`. Removing `game_manager.gd` and `Main.tscn` from the template affects them too:

- **Contract pipeline**: Already generates its own `game_manager.gd` via `game_manager_generator.py` and overwrites it. Already generates `Main.tscn` via `SceneAssembler`. Removing template versions is safe — they're already overwritten.
- **General pipeline**: Uses `node_generator.py` which produces `Main.tscn`. Same situation.
- **Multi_stage pipeline**: Same pattern.

All three pipelines already overwrite these template files, so removing them from the template is a no-op for existing pipelines.

## Out of Scope

- Changing the contract/general/multi_stage pipelines' prompt structure (they work fine with their existing template integration)
- Adding new asset types to the template
- Modifying the verifier to understand project.godot (it already flags autoload issues — this fix eliminates the root cause)
- Custom export presets per game

## Success Criteria

1. Generated `project.godot` has correct `[autoload]` entries matching the LLM's generated singleton scripts
2. No naming collision between template and generated files (no duplicate game manager files)
3. Input actions referenced in generated `.gd` code exist in the generated `project.godot`'s `[input]` section
4. `[rendering]` and `[display]` sections are always correct (viewport 1152x648, gl_compatibility renderer)
5. Pre-built assets (shaders, palettes, particles) are used by the LLM when appropriate
6. Existing contract/general/multi_stage pipelines are unaffected
7. Verifier no longer flags "GameManager autoload not configured" as a critical error
