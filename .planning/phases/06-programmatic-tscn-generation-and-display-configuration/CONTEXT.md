# Phase 06: Programmatic TSCN Generation and Display Configuration

## Problem Statement

The contract pipeline strips all per-node `.tscn` files (phase 05.2, Bug C/F fix) but the wiring stage only generates `Main.tscn` — nobody creates sub-scene `.tscn` files (`Bird.tscn`, `PipePair.tscn`) or child node hierarchies (collision shapes, Labels, Panels) that generated scripts depend on. This is the #1 cause of broken games.

Additionally, the template `project.godot` has no `[display]` section — no viewport size, no stretch mode. Scripts hallucinate different screen dimensions (1024, 648, etc.) because the node generator prompt doesn't mention the design resolution.

## Root Cause Analysis

### Missing sub-scene `.tscn` files

**Phase 05.2 decision**: Strip per-node `.tscn` to fix invalid ExtResource IDs (Bug C) and wrong script attachment (Bug F). The assumption was "the wiring stage owns all scene assembly." But the wiring stage only produces `Main.tscn`.

**What's missing**:
1. Sub-scenes referenced by `preload()` (e.g., `PipePair.tscn` loaded by `pipe_spawner.gd`)
2. Child nodes expected by `@onready var x: Type = %Name` (e.g., `%ScoreLabel` in HUD, `%PipeTop` in PipePair)
3. Collision shapes for physics bodies (CharacterBody2D, StaticBody2D, Area2D)

### Viewport size hallucination

**Template gap**: `project.godot` has no `[display]` section at all. Godot defaults to engine defaults.

**Prompt gap**: Node generator system prompt doesn't mention viewport dimensions. Each node is generated independently — some scripts read `ProjectSettings` correctly, others hardcode 1024, 648, or other guessed values.

## Key Insight: TSCN Files Are Deterministically Derivable

Through analysis, we established that for the class of games this pipeline generates (procedural, single-scene, no hand-authored levels):

1. **The `.tscn` format is simple** — INI-like text with `[ext_resource]` declarations, `[node]` entries forming a tree via `parent=` paths, `[connection]` signal wiring, and key-value properties.

2. **Node properties can all be set in `_ready()`** — Godot's initialization order (children before parents) means scripts always see initialized children. There are no cases where `.tscn`-level property data is needed before `_ready()` runs.

3. **The contract + generated `.gd` files contain all needed information**:
   - Contract defines: node names, types, parent relationships, script paths, signals, groups, spawn_mode
   - `.gd` scripts define: `@onready var x: Type = %Name` references (what children must exist)
   - Both together: enough to build any `.tscn` deterministically

4. **No LLM is needed for `.tscn` generation** — the structural parts (ext_resources, node tree, unique names, script bindings) are mechanical. The wiring stage LLM call for Main.tscn can be replaced by a Python builder.

## Approach

### 1. Build a `TscnBuilder` utility

A Python class that constructs valid Godot 4 `.tscn` files programmatically:
- `add_ext_resource(type, path)` → returns id
- `add_node(name, type, parent)` with optional script, unique_name_in_owner, instance
- `add_connection(signal, from_path, to_path, method)`
- `serialize()` → valid `.tscn` text string

This replaces both the wiring stage LLM call (for Main.tscn) and the missing sub-scene generation.

### 2. Build a `SceneAssembler` that uses `TscnBuilder`

Takes the contract + generated `.gd` files and produces all needed `.tscn` files:

**Main.tscn assembly**:
- For each static node in contract: add ext_resource for its script, add node to tree
- For nodes that instance sub-scenes (scene_path set): add PackedScene ext_resource, use instance=
- Set unique_name_in_owner on all scripted nodes
- Wire signal connections between scene-local nodes (skip autoload signals — those are handled in .gd `_ready()`)

**Sub-scene `.tscn` assembly** (for nodes with `scene_path` set):
- Parse the `.gd` file for `@onready var x: Type = %Name` to discover required children
- Create the root node with the contract's `node_type`
- Add child nodes with correct types and unique names
- For physics bodies: add CollisionShape2D children (shape configured in code)
- For UI containers: add Label/Panel children as referenced

### 3. Parse `@onready` references from `.gd` files

A regex-based parser that extracts `@onready var name: Type = %NodeName` from generated scripts:
- Returns list of `{var_name, type, unique_name}` for each reference
- Used by SceneAssembler to know what children each node expects

### 4. Fix display configuration

**Template `project.godot`** — add `[display]` section:
```ini
[display]
window/size/viewport_width=1152
window/size/viewport_height=648
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"
```

**Node generator prompt** — add viewport size context:
```
The game viewport design resolution is 1152x648 pixels.
Use get_viewport().get_visible_rect().size to read dimensions at runtime
rather than hardcoding pixel values.
```

### 5. Remove wiring stage LLM call

Replace `run_wiring_generator()` (which calls Claude to generate Main.tscn) with the deterministic `SceneAssembler`. The `_strip_node_tscn()` function becomes unnecessary since the node generator no longer produces `.tscn` files to strip — but the prompt instruction to generate them should also be removed.

## What Changes

| File | Change |
|------|--------|
| NEW: `backend/backend/pipelines/contract/tscn_builder.py` | TscnBuilder utility class |
| NEW: `backend/backend/pipelines/contract/scene_assembler.py` | SceneAssembler using TscnBuilder + contract + .gd parsing |
| `backend/backend/pipelines/contract/pipeline.py` | Replace wiring LLM call with SceneAssembler; remove `_strip_node_tscn` |
| `backend/backend/pipelines/contract/node_generator.py` | Add viewport size to prompt; remove "Also generate: .tscn" instruction |
| `godot/templates/base_2d/project.godot` | Add [display] section with viewport + stretch settings |
| DELETE or gut: `backend/backend/pipelines/contract/wiring_generator.py` | LLM wiring no longer needed (keep autoload patching if still useful) |

## Out of Scope

- Level design / hand-authored node positioning (not needed for procedural games)
- `@export` property overrides in `.tscn` (pipeline doesn't use this pattern)
- Complex sub_resource embedding (shaders/materials already loaded from template files)
- Signal connections from autoloads in `.tscn` (handled in `.gd` `_ready()` already)

## Success Criteria

1. Generated games have all required `.tscn` files present (Main.tscn + sub-scenes)
2. Every `@onready %Name` reference in `.gd` files resolves to an actual child node in the `.tscn`
3. Every `preload("res://X.tscn")` in `.gd` files has the corresponding `.tscn` file
4. No LLM calls for `.tscn` generation — fully deterministic
5. All scripts use consistent viewport dimensions (no hardcoded screen sizes)
6. Existing test suite passes; new tests cover TscnBuilder and SceneAssembler
