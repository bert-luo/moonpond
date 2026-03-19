# Phase 06: Programmatic TSCN Generation and Display Configuration - Research

**Researched:** 2026-03-18
**Domain:** Godot 4 .tscn text format, Python code generation, GDScript parsing
**Confidence:** HIGH

## Summary

This phase replaces the LLM-based wiring generator with a deterministic Python `TscnBuilder`
and `SceneAssembler`. The core insight is that Godot 4 `.tscn` files are INI-like text with a
fixed grammar — there is no reason to use an LLM to produce them when the contract and generated
`.gd` files supply all needed information. This phase also closes the display configuration gap:
the template `project.godot` has no `[display]` section, and node generator prompts do not
communicate the design resolution.

The implementation is entirely mechanical: parse `@onready var x: Type = %Name` from `.gd` files
to discover required child nodes, then generate structurally correct `.tscn` text for `Main.tscn`
and every sub-scene referenced by `scene_path` in the contract. Signal connections, `ext_resource`
declarations, `unique_name_in_owner`, and `script` bindings are all derivable from the contract
without any LLM call.

The primary risk is the `@onready` parser encountering edge cases: no-type annotations
(`@onready var x = %Name`), multi-line declarations, or non-unique-name `@onready` using
literal paths (`$Child/Node`). The scope is limited to `%Name` pattern only — literal path
`@onready` vars are out of scope because the node generator prompt already prohibits them.

**Primary recommendation:** Build `TscnBuilder` as a simple Python class with no external
dependencies, `SceneAssembler` as the orchestrator, and a regex parser for `@onready`. All
three are pure Python with no Godot runtime dependency — fully unit-testable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

All decisions documented in CONTEXT.md constitute the full specification for this phase.
Key locked decisions derived from the CONTEXT.md analysis:

- Use `TscnBuilder` as a Python utility class (`add_ext_resource`, `add_node`,
  `add_connection`, `serialize`) — no LLM involvement in .tscn generation
- Use `SceneAssembler` as the orchestrator that consumes contract + generated .gd files
- Parse `@onready var x: Type = %Name` with a regex-based parser (not a full GDScript parser)
- Replace `run_wiring_generator()` LLM call with `SceneAssembler` in `pipeline.py`
- Keep `_patch_project_godot_autoloads()` from wiring_generator — still needed
- Add `[display]` section to `godot/templates/base_2d/project.godot`:
  `viewport_width=1152`, `viewport_height=648`, `stretch/mode="canvas_items"`,
  `stretch/aspect="expand"`
- Add viewport size context to node generator system prompt
- Remove `"Also generate: {node.scene_path}"` from node generator prompt
- Keep `_strip_node_tscn()` in pipeline.py (still needed as safety net)

### Claude's Discretion

The CONTEXT.md does not define any explicit "Claude's Discretion" section. The following
implementation details are left to the implementer:

- Exact class/method naming within `TscnBuilder` and `SceneAssembler` (as long as the
  interface matches what CONTEXT.md describes)
- How `load_steps` is calculated in the `[gd_scene]` header (ext_resources + sub_resources)
- Whether `uid=` is generated for each `.tscn` (safe to omit — Godot auto-assigns UIDs)
- CollisionShape2D default size/shape for physics bodies in sub-scenes
- Where in `pipeline.py` the `SceneAssembler` is invoked (replace Stage 4)
- Whether `wiring_generator.py` is deleted or gutted (keep `_patch_project_godot_autoloads`)
- Test file naming and test organization

### Deferred Ideas (OUT OF SCOPE)

- Level design / hand-authored node positioning
- `@export` property overrides in `.tscn`
- Complex sub_resource embedding (shaders/materials)
- Signal connections from autoloads in `.tscn`
- `AnimationPlayer`, `AnimationTree` sub-resource definitions
- Non-`%Name` `@onready` patterns (literal path `$Child/Node`)
</user_constraints>

<phase_requirements>
## Phase Requirements

This phase introduces new requirements. The REQUIREMENTS.md traceability table will be updated
to include a new OPT-09 / TSCN-series requirement block after implementation. The behavioral
requirements for this phase (derived from CONTEXT.md success criteria) are:

| ID | Description | Research Support |
|----|-------------|-----------------|
| TSCN-01 | Generated games have all required .tscn files (Main.tscn + sub-scenes) | TscnBuilder + SceneAssembler pattern |
| TSCN-02 | Every `@onready %Name` reference resolves to an actual child node in the .tscn | @onready parser feeds SceneAssembler |
| TSCN-03 | Every `preload("res://X.tscn")` has a corresponding .tscn file | SceneAssembler generates all scene_path .tscn files |
| TSCN-04 | No LLM calls for .tscn generation — fully deterministic | TscnBuilder replaces run_wiring_generator LLM call |
| TSCN-05 | All scripts use consistent viewport dimensions | project.godot [display] section + prompt injection |
| TSCN-06 | Existing test suite passes; new tests cover TscnBuilder and SceneAssembler | See Validation Architecture section |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `re` | stdlib | `@onready` regex parsing | No deps; pattern is simple and fixed |
| Python stdlib `pathlib` | stdlib | File I/O for .gd reading in SceneAssembler | Already used throughout codebase |
| `pytest` + `pytest-anyio` | already installed | Unit tests for TscnBuilder and SceneAssembler | Existing test infrastructure |

### Supporting

No new libraries are needed. This phase is pure Python string generation.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Regex @onready parser | Tree-sitter GDScript grammar | Tree-sitter requires native binary + GDScript grammar not in PyPI; overkill for a single pattern |
| Hand-rolled TscnBuilder | Jinja2 template | Jinja2 adds a dep; builder gives stronger structural guarantees via method calls |

**Installation:** No new packages needed.

## Architecture Patterns

### Recommended Project Structure

```
backend/backend/pipelines/contract/
├── tscn_builder.py       # NEW: TscnBuilder utility class
├── scene_assembler.py    # NEW: SceneAssembler + @onready parser
├── pipeline.py           # MODIFIED: replace run_wiring_generator with SceneAssembler
├── node_generator.py     # MODIFIED: add viewport hint, remove "Also generate: .tscn"
├── wiring_generator.py   # MODIFIED: gut LLM call, keep _patch_project_godot_autoloads
├── models.py             # UNCHANGED
├── contract_generator.py # UNCHANGED
├── game_manager_generator.py # UNCHANGED
└── spec_expander.py      # UNCHANGED

godot/templates/base_2d/
└── project.godot         # MODIFIED: add [display] section

backend/backend/tests/
├── test_tscn_builder.py   # NEW: TscnBuilder unit tests
├── test_scene_assembler.py # NEW: SceneAssembler + @onready parser tests
├── test_wiring_generator.py # MODIFIED: update for gutted wiring_generator
└── test_contract_pipeline.py # MODIFIED: update mock side_effects (one fewer LLM call)
```

### Pattern 1: TscnBuilder — Incremental Construction

**What:** A Python class that maintains ordered lists of ext_resources, sub_resources, nodes,
and connections, then serializes to valid `.tscn` text.

**When to use:** Whenever a `.tscn` file must be created programmatically. Called by
SceneAssembler for Main.tscn and each sub-scene.

**Key .tscn format facts (verified from live generated files in this repo):**

```
[gd_scene load_steps=N format=3]          # N = total ext_resource + sub_resource count
                                            # uid= is optional, Godot assigns on first load

[ext_resource type="Script" path="res://player.gd" id="1"]
[ext_resource type="PackedScene" path="res://Bird.tscn" id="2"]
[ext_resource type="Script" path="res://hud.gd" id="3"]

[sub_resource type="RectangleShape2D" id="RectangleShape2D_1"]
size = Vector2(64, 64)

[node name="Main" type="Node2D"]
script = ExtResource("1")

[node name="Bird" parent="." instance=ExtResource("2")]
unique_name_in_owner = true

[node name="CollisionShape2D" type="CollisionShape2D" parent="Player"]
shape = SubResource("RectangleShape2D_1")

[connection signal="died" from="Bird" to="." method="_on_bird_died"]
```

**Critical format rules:**
- Root node has no `parent=` attribute
- Child nodes use `parent="."` for direct children, `parent="ParentName"` for deeper nesting
- Nodes using `instance=ExtResource("N")` have NO `type=` attribute
- Nodes using `type=` have NO `instance=` attribute — these are mutually exclusive
- `script = ExtResource("N")` is a property on the node stanza (indented by nothing, on its own line)
- `unique_name_in_owner = true` must appear on every scripted node so `%Name` lookups work
- IDs must be unique strings across ALL ext_resources in a single .tscn file
- `load_steps` = count of ext_resource + sub_resource declarations

**Example TscnBuilder interface:**

```python
# Source: Derived from live .tscn files in games/ directory (HIGH confidence)
class TscnBuilder:
    def __init__(self) -> None:
        self._ext_resources: list[tuple[str, str, str]] = []  # (type, path, id)
        self._sub_resources: list[tuple[str, str, dict]] = []  # (type, id, props)
        self._nodes: list[dict] = []
        self._connections: list[tuple[str, str, str, str]] = []  # (signal, from, to, method)
        self._next_id: int = 1

    def add_ext_resource(self, res_type: str, path: str) -> str:
        """Returns the assigned id string."""
        id_str = str(self._next_id)
        self._next_id += 1
        self._ext_resources.append((res_type, path, id_str))
        return id_str

    def add_sub_resource(self, res_type: str, props: dict) -> str:
        """Returns the assigned sub_resource id string."""
        id_str = f"{res_type}_{self._next_id}"
        self._next_id += 1
        self._sub_resources.append((res_type, id_str, props))
        return id_str

    def add_node(
        self,
        name: str,
        node_type: str | None,
        parent: str | None,
        *,
        script_id: str | None = None,
        instance_id: str | None = None,
        unique_name: bool = False,
        extra_props: dict | None = None,
    ) -> None: ...

    def add_connection(self, signal: str, from_path: str, to_path: str, method: str) -> None: ...

    def serialize(self) -> str: ...
```

### Pattern 2: SceneAssembler — Two-Pass Assembly

**What:** Orchestrates TscnBuilder to produce Main.tscn and sub-scene .tscn files.

**Two conceptually distinct passes:**

**Pass A — Main.tscn:**
- Iterate static nodes in contract (skip dynamic nodes — same rule as current wiring stage)
- For nodes with `scene_path` set: add `[ext_resource type="PackedScene" path="res://{scene_path}"]`
  and `[node name="{name}" parent="." instance=ExtResource("N")]` with `unique_name_in_owner = true`
- For nodes without `scene_path` but with a script: add Script ext_resource + inline node
- For the main node (`main_scene = "Main.tscn"`): attach it as the root with its script
- Wire signal connections from contract (filter: only connections where both `from` and `to` are
  static nodes in Main.tscn scope — skip autoload-to-node connections since those are handled in `.gd`)

**Pass B — Sub-scene .tscn for each node with `scene_path != None and scene_path != "Main.tscn"`:**
- Root node = `node_type` from contract, with the script attached
- Parse `@onready var x: Type = %Name` from the generated `.gd` to discover children
- Add each `%Name` child node to the sub-scene with `unique_name_in_owner = true`
- For physics bodies (CharacterBody2D, StaticBody2D, RigidBody2D, Area2D): add one
  `CollisionShape2D` child with a default `RectangleShape2D` sub_resource (the script
  configures it in `_ready()`, so size is irrelevant in .tscn)

### Pattern 3: @onready Parser

**What:** Regex extracts `(var_name, type_hint, unique_name)` from `@onready` declarations.

**Target pattern (verified from generated scripts in this repo):**
```
@onready var score_label: Label = %ScoreLabel
@onready var bird = %Bird           # no type hint — still valid
@onready var _tile_a: Node2D = %TileA
```

**Regex:**
```python
# Source: Verified against all @onready usages in games/flapventure-wings-of-destiny_20260317-101627/project/*.gd
ONREADY_PATTERN = re.compile(
    r"^@onready\s+var\s+(\w+)(?:\s*:\s*(\w+))?\s*=\s*%(\w+)",
    re.MULTILINE,
)

def parse_onready_unique_refs(gd_source: str) -> list[dict]:
    """Returns list of {var_name, node_type, unique_name} dicts.
    node_type is None if no type annotation present.
    """
    matches = []
    for m in ONREADY_PATTERN.finditer(gd_source):
        matches.append({
            "var_name": m.group(1),
            "node_type": m.group(2),   # may be None
            "unique_name": m.group(3),
        })
    return matches
```

**Known edge cases and how to handle them:**
- No type hint: `node_type` will be None — treat as `Node2D` when creating the child node in .tscn
- `AudioStreamPlayer` is not a visual node — create it as a plain child `type="AudioStreamPlayer"`
- `AnimationPlayer`: create as plain child `type="AnimationPlayer"` with no extra properties
- `Button`: create as `type="Button"` — configuration in `_ready()`
- `ColorRect`: create as `type="ColorRect"`
- `Panel`: create as `type="Panel"`
- `Label`: create as `type="Label"`
- The `%` prefix is what distinguishes unique-name refs from path refs — only process `%` refs

### Anti-Patterns to Avoid

- **Generating UIDs in .tscn:** Godot auto-assigns UIDs on first editor load. Do not generate
  `uid="..."` strings — they are not required for headless export to work. The template's
  `Main.tscn` has one hardcoded UID, but generated files don't need them.

- **Putting CollisionShape2D properties in .tscn:** The generated scripts configure collision
  shape dimensions in `_ready()`. Creating a default `RectangleShape2D` with `size = Vector2(64, 64)`
  is sufficient — the script will override it. Do NOT try to read shape dimensions from anywhere.

- **Node name derivation from script_path:** The contract's `scene_path` filename (without `.tscn`)
  IS the node name for the root node of each sub-scene. For example: `Bird.tscn` → root node
  name is `"Bird"`. However, this convention may not always hold — safer to look at the contract's
  node_type and derive the name from the script's `extends` statement or scene_path stem.

- **Forgetting `load_steps`:** The `[gd_scene load_steps=N]` header counts must be correct.
  `N = len(ext_resources) + len(sub_resources)`. Incorrect counts don't break Godot but are
  a correctness marker.

- **Signal connections in Main.tscn for sub-scene-internal signals:** Sub-scene signals are
  wired within the sub-scene .tscn (or in `_ready()`). Only signals that cross scene boundaries
  (from one top-level scene instance to another) go in Main.tscn `[connection]` entries.

- **Placing `scene_path` nodes inline instead of as instances:** Nodes with `scene_path` set in
  the contract MUST be instantiated via `instance=ExtResource("N")` in Main.tscn. They cannot
  be placed as inline `type=` nodes — that would not link the sub-scene.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| .tscn serialization | Custom string concatenation ad hoc | TscnBuilder class | Builder enforces ordering (ext_resources before nodes before connections), tracks IDs, and is testable independently |
| @onready parsing | Line-by-line manual parser | `re.compile` with MULTILINE | The pattern is stable and well-defined; regex is sufficient and verifiable |
| Physics body detection | Hardcoded set of type strings | `PHYSICS_NODE_TYPES` frozenset | Centralizes the "needs CollisionShape2D" logic |

**Key insight:** All the information needed to build correct `.tscn` files already exists in the
contract (`node_type`, `scene_path`, `signals`, `spawn_mode`) and the generated `.gd` files
(`@onready` declarations). No LLM reasoning is needed — only mechanical extraction and
serialization.

## Common Pitfalls

### Pitfall 1: Main.tscn vs. Sub-scene Signals

**What goes wrong:** Wiring every signal from the contract into `Main.tscn` `[connection]`
blocks, including signals that are internal to a sub-scene.

**Why it happens:** The contract's `signals` field is per-node, not per-connection. A node's
signal list says what signals IT emits — not who connects to them. The current LLM wiring stage
was told which signals to wire via the prompt and it reasoned about it. The deterministic
assembler must have its own rule.

**How to avoid:** Only wire connections from the existing contract `[connection]` data (which
the current wiring stage generates from the LLM's analysis). Since the deterministic assembler
doesn't have connection targets encoded in the contract, connections must come from the signal
entries on NodeContract — but the *targets* are not in the contract.

**Resolution for this phase:** The CONTEXT.md says "Wire signal connections between scene-local
nodes." The contract's signal information tells us WHAT signals exist. To know WHERE they connect,
the assembler must inspect the generated `.gd` files for `connect()` calls, OR the contract must
be extended to include connection targets. **This is the most significant design gap in the
phase spec.** The safest initial approach: emit zero `[connection]` entries in Main.tscn and
let scripts wire signals in `_ready()` via `connect()` — this is what the CONTEXT.md says is
already happening for autoloads and is safe for other signals too.

**Warning signs:** If generated game scripts call `emit_signal("died")` but nothing connects
to it in `_ready()` or in Main.tscn, the signal fires silently. This may be acceptable since
the node generator prompt already instructs scripts to use `connect()` in `_ready()`.

### Pitfall 2: ID Collision Between Main.tscn and Sub-scene .tscn

**What goes wrong:** If `TscnBuilder` reuses a counter across multiple `.tscn` files, IDs
may semantically appear consistent but each `.tscn` file has its own independent ID namespace.

**Why it happens:** IDs are file-scoped, not project-scoped. `id="1"` in `Bird.tscn` is
completely unrelated to `id="1"` in `Main.tscn`.

**How to avoid:** `TscnBuilder` instances are per-file. Create a fresh `TscnBuilder()` for
each `.tscn` file. Do not share instances across files.

### Pitfall 3: @onready Refs Already in Main.tscn Scope

**What goes wrong:** Some `@onready %Name` references in `main.gd` refer to top-level children
in Main.tscn (other scene instances), not to children within the main node's sub-scene. If the
assembler tries to create child nodes in a "Main sub-scene" for these refs, it creates a second
tree of redundant children.

**Why it happens:** `main.gd` is the root node script for Main.tscn. Its `@onready %Bird`
refers to the `Bird` node instance at the top level of Main.tscn — which is added by the
assembler as an `instance=ExtResource(...)` node anyway.

**How to avoid:** For nodes with `scene_path = "Main.tscn"`, do NOT run the @onready parser
to add children — those refs are to sibling scene instances, not children that need to be
created. The @onready parser is only used for sub-scene `.tscn` generation (nodes with a
non-Main `scene_path`).

### Pitfall 4: Node Name Derivation for Root Sub-scene Node

**What goes wrong:** Root node name in sub-scene doesn't match what Main.tscn expects.

**Why it happens:** Main.tscn places `[node name="Bird" parent="." instance=ExtResource("2")]`.
The `Bird.tscn` root node must be named `"Bird"` for Godot to accept the instance. If the
assembler names the root `"CharacterBody2D"` (the node_type), it breaks.

**How to avoid:** Derive the sub-scene root node name from the `scene_path` stem:
`Path(node.scene_path).stem` → `"Bird"` from `"Bird.tscn"`. This matches the convention
observed in all generated .tscn files in this repo.

### Pitfall 5: test_contract_pipeline Test Expects Wiring LLM Call

**What goes wrong:** `test_contract_pipeline_full_flow` has a `side_effect` list with 5 LLM
responses (spec, contract, node1, node2, wiring). After this phase, the wiring call is gone,
so the test will fail with "StopIteration" or wrong response on the 5th call.

**How to avoid:** Update `test_contract_pipeline.py` to have only 4 LLM responses in the
`side_effect` list. Also verify `assert len(stage_starts) >= 5` — may need adjustment since
the wiring stage start event changes.

### Pitfall 6: project.godot [display] Section Placement

**What goes wrong:** The `[display]` section is inserted into `project.godot` but breaks
the `_patch_project_godot_autoloads` regex if placed after `[autoload]` or in an unexpected
position.

**How to avoid:** Add `[display]` at the end of the template `project.godot`, after
`[rendering]`. The `_patch_project_godot_autoloads` regex only touches `[autoload]` — it
won't be affected by a new section elsewhere.

## Code Examples

Verified patterns from the codebase:

### Godot 4 .tscn File Structure (from live generated files)

```
# Source: games/flapventure-wings-of-destiny_20260317-101627/project/Main.tscn
[gd_scene load_steps=10 format=3]

[ext_resource type="Script" path="res://main.gd" id="1"]
[ext_resource type="PackedScene" path="res://Bird.tscn" id="2"]

[node name="Main" type="Node2D"]
script = ExtResource("1")

[node name="Bird" parent="." instance=ExtResource("2")]
unique_name_in_owner = true

[connection signal="died" from="Bird" to="." method="_on_bird_died"]
```

### Sub-scene with Physics Body (from live generated files)

```
# Source: games/flapventure-wings-of-destiny_20260317-101627/project/Bird.tscn
[gd_scene load_steps=2 format=3]

[sub_resource type="CapsuleShape2D" id="CapsuleShape2D_1"]
radius = 13.0
height = 10.0

[node name="Bird" type="CharacterBody2D"]
script = ExtResource("bird_script")

[node name="CollisionShape2D" type="CollisionShape2D" parent="."]
shape = SubResource("CapsuleShape2D_1")
rotation = 1.5708
```

Note: For the deterministic assembler, a default `RectangleShape2D` is sufficient since
the script configures shape in `_ready()`.

### Sub-scene with UI Hierarchy (from live generated files)

```
# Source: games/flapventure-wings-of-destiny_20260317-101627/project/HUD.tscn
[gd_scene load_steps=1 format=3]

[ext_resource type="Script" path="res://hud.gd" id="1"]

[node name="HUD" type="CanvasLayer"]
script = ExtResource("1")

[node name="ScoreLabel" type="Label" parent="."]
unique_name_in_owner = true
```

### @onready Pattern in Generated Scripts

```gdscript
# Source: games/.../project/hud.gd — single ref, with type
@onready var score_label: Label = %ScoreLabel

# Source: games/.../project/ground.gd — ref without type qualification style variations
@onready var _tile_a: Node2D = %TileA
@onready var _tile_b: Node2D = %TileB

# Source: games/.../project/main.gd — multiple refs including some without type hints
@onready var bird = %Bird
@onready var pipe_spawner = %PipeSpawner
```

### project.godot [display] Section (from CONTEXT.md)

```ini
[display]

window/size/viewport_width=1152
window/size/viewport_height=648
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"
```

### Viewport Prompt Injection

```python
# Source: CONTEXT.md — to be added to _build_node_system_prompt() in node_generator.py
"The game viewport design resolution is 1152x648 pixels.\n"
"Use get_viewport().get_visible_rect().size to read dimensions at runtime\n"
"rather than hardcoding pixel values."
```

### Physics Node Type Detection

```python
# Source: Analysis of generated .tscn files — physics bodies always need CollisionShape2D
PHYSICS_NODE_TYPES: frozenset[str] = frozenset({
    "CharacterBody2D",
    "StaticBody2D",
    "RigidBody2D",
    "RigidBody3D",  # excluded by scope but included for completeness
    "Area2D",
})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LLM generates Main.tscn (wiring_generator.py) | Deterministic TscnBuilder | Phase 06 | Eliminates hallucinated ExtResource IDs and wrong script attachments (Bugs C, F) |
| No sub-scene .tscn generation | SceneAssembler generates all scene_path .tscn files | Phase 06 | Fixes #1 cause of broken games |
| No [display] section in project.godot | [display] section with 1152x648 + canvas_items | Phase 06 | Eliminates viewport size hallucination |
| Node generator told to generate .tscn | Node generator only generates .gd | Phase 06 | Eliminates LLM .tscn waste and strip step |

**Deprecated/outdated after this phase:**
- `run_wiring_generator()` LLM call: replaced by `SceneAssembler.assemble()`
- `"Also generate: {node.scene_path}"` in node generator prompt: removed
- `_strip_node_tscn()` may become a no-op (but keep as safety net — node generator might still
  occasionally emit .tscn if it hallucinates despite prompt change)

## Open Questions

1. **Signal connection targets in Main.tscn**
   - What we know: The contract encodes what signals a node emits, but not who connects to them.
     The current LLM wiring stage reasons about connections from the full contract context.
   - What's unclear: Should the deterministic assembler produce any `[connection]` entries?
     If scripts wire all signals in `_ready()` via `connect()`, connections in .tscn are
     redundant but harmless.
   - Recommendation: For Phase 06, emit NO `[connection]` entries in Main.tscn. The node
     generator prompt instructs scripts to use `connect()` in `_ready()`. If a game breaks
     because of missing wiring, Phase 07 can add connection synthesis.

2. **Nodes with `scene_path = None` but no Main.tscn role**
   - What we know: Some nodes like `score_zone.gd` (scene_path=None) are not instanced in
     Main.tscn directly — they exist as children within sub-scenes.
   - What's unclear: How does SceneAssembler know NOT to add them to Main.tscn?
   - Recommendation: Only nodes with an explicit non-None `scene_path` (excluding Main.tscn)
     get standalone `.tscn` files. Nodes with `scene_path=None` are only added to Main.tscn
     if they appear in `@onready` refs of `main.gd`. Since `score_zone.gd` appears in
     pipe_pair.gd's @onready, it will be created as a child in PipePair.tscn. The assembler
     for Main.tscn should only place nodes whose `scene_path` is explicitly set.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-anyio (already installed) |
| Config file | `backend/pyproject.toml` → `[tool.pytest.ini_options]` `asyncio_mode = "auto"` |
| Quick run command | `cd backend && uv run python -m pytest backend/tests/test_tscn_builder.py backend/tests/test_scene_assembler.py -x -q` |
| Full suite command | `cd backend && uv run python -m pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TSCN-01 | SceneAssembler produces Main.tscn + all scene_path .tscn files | unit | `pytest tests/test_scene_assembler.py -x` | ❌ Wave 0 |
| TSCN-02 | @onready %Name refs resolve to child nodes in sub-scene .tscn | unit | `pytest tests/test_scene_assembler.py::test_onready_refs_become_children -x` | ❌ Wave 0 |
| TSCN-03 | preload("res://X.tscn") files exist when scene_path is set | unit | `pytest tests/test_scene_assembler.py::test_all_scene_paths_produced -x` | ❌ Wave 0 |
| TSCN-04 | TscnBuilder.serialize() produces valid .tscn text without LLM | unit | `pytest tests/test_tscn_builder.py -x` | ❌ Wave 0 |
| TSCN-05 | project.godot has [display] section with correct values | unit | `pytest tests/test_node_generator.py::test_viewport_hint_in_prompt -x` | ❌ Wave 0 |
| TSCN-06 | Full test suite passes (including updated pipeline test) | integration | `cd backend && uv run python -m pytest -x -q` | ✅ exists, needs updates |

### Sampling Rate

- **Per task commit:** `cd backend && uv run python -m pytest backend/tests/test_tscn_builder.py backend/tests/test_scene_assembler.py -x -q`
- **Per wave merge:** `cd backend && uv run python -m pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/backend/tests/test_tscn_builder.py` — covers TSCN-04
- [ ] `backend/backend/tests/test_scene_assembler.py` — covers TSCN-01, TSCN-02, TSCN-03
- [ ] `backend/backend/pipelines/contract/tscn_builder.py` — implementation (not a test gap but a code gap)
- [ ] `backend/backend/pipelines/contract/scene_assembler.py` — implementation

*(Existing `test_wiring_generator.py` and `test_contract_pipeline.py` need updates but files exist.)*

## Sources

### Primary (HIGH confidence)

- Live `.tscn` files in `games/flapventure-wings-of-destiny_20260317-101627/project/` — direct
  inspection of format; `Main.tscn`, `Bird.tscn`, `PipePair.tscn`, `HUD.tscn`, `Ground.tscn`
- Generated `.gd` files in same game — `@onready` usage patterns, `preload()` patterns
- `backend/backend/pipelines/contract/` source files — current wiring_generator, pipeline,
  node_generator, models
- `godot/templates/base_2d/project.godot` — current template structure (no [display] section)
- `.planning/phases/06-.../CONTEXT.md` — locked design decisions

### Secondary (MEDIUM confidence)

- CONTEXT.md analysis of the .tscn format grammar (INI-like, section-based) — consistent with
  observed files

### Tertiary (LOW confidence)

- `load_steps` exact semantics (whether it must exactly match the count or is advisory) — Godot
  parses it as a hint for progress reporting; mismatch causes no parse failure but is incorrect

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pure Python stdlib, no new dependencies, existing pytest infrastructure
- Architecture: HIGH — derived directly from live generated files in this repo; format verified
- Pitfalls: HIGH — derived from actual bugs (Bugs C, F, E) in prior phases and live .tscn inspection
- Open questions: MEDIUM — signal connection synthesis is a genuine design gap that the CONTEXT.md
  acknowledged ("skip autoload signals — those are handled in .gd `_ready()`")

**Research date:** 2026-03-18
**Valid until:** 2026-06-18 (Godot 4 text format is stable; format has not changed in 4.x lifecycle)
