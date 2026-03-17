# Phase 5: Pipeline Optimization - Research

**Researched:** 2026-03-17
**Domain:** Python async pipeline architecture, Pydantic data modeling, asyncio task scheduling, Godot file contract enforcement
**Confidence:** HIGH (primary findings based on existing codebase + established Python stdlib patterns)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Pipeline Architecture**
- New pipeline class alongside MultiStagePipeline (not replacing it yet)
- Lives in backend/backend/pipelines/ with new stages in backend/backend/stages/
- Follows the existing GamePipeline Protocol + registry pattern

**Stage 1: Spec Expander (with reasoning)**
- Takes user prompt and expands it into a full game specification
- Uses LLM reasoning to flesh out gameplay mechanics, entities, interactions
- Output: rich game spec document that downstream stages consume

**Stage 2: API Spec / Node Structure Generator**
- Generates the interface contract: method signatures, signal names, group names, enum definitions, node tree structure, scene file paths
- Defines all cross-file dependencies BEFORE any code is generated
- Output: structured contract that all parallel generators must honor

**Stage 3: Parallel Node Generation (dependency-ordered)**
- Generates individual .gd/.tscn files in parallel where the dependency graph allows
- Leaf nodes (platform.gd, enemy.gd, powerup.gd, projectile.gd, player.gd, background.gd) can all be generated concurrently
- Each generator receives the API contract from Stage 2 as context
- Follows dependency order: leaves first, then orchestrator scripts

**Stage 4: Wiring File Generation**
- Generates Main.tscn (scene tree wiring scripts to nodes)
- Generates project.godot (autoloads, main scene, input mappings)
- Ensures all ExtResource references match actual script paths
- Connects signals to handlers
- This stage runs AFTER all individual files exist

**Stage 5: Export**
- Reuse existing export logic (Godot headless WASM export)

### Claude's Discretion
- Internal data structures for the API contract format
- How to represent the dependency graph for parallel scheduling
- Error handling and self-correction within each stage
- Whether to reuse existing prompt enhancer / game designer stages or create new ones

### Deferred Ideas (OUT OF SCOPE)
- Replacing MultiStagePipeline entirely (keep both for now)
- Visual polish / shader application integration (existing visual polisher stage)
- Image generation integration (Phase 03.1)
</user_constraints>

---

## Summary

The new pipeline addresses a root-cause structural flaw: the existing MultiStagePipeline generates all files in one monolithic LLM call without defining shared contracts first. Post-hoc validation catches some errors but cannot fix cross-file inconsistencies — if `background.gd` is assigned as a script on the wrong node in `Main.tscn`, no single-file repair pass can detect that because the error spans two files. The contract-first approach solves this by separating concerns: Stage 2 produces a single authoritative contract JSON, and all subsequent generators are constrained to honor it.

The parallel node generation in Stage 3 is the performance upside. Python's `asyncio.gather()` can issue all leaf-node LLM calls simultaneously. With 6+ leaf files and ~5s per LLM call, sequential generation takes 30s+; parallel generation collapses this to ~5s. The dependency graph for Godot projects is flat (leaves → orchestrators), so `asyncio.gather()` for all leaves followed by a second gather for orchestrators covers all cases without a general DAG scheduler.

The wiring stage (Stage 4) is the most important correctness improvement. It runs after all individual scripts exist, receives all script paths + the contract, and builds `Main.tscn` and `project.godot` with knowledge of exactly which files were generated. This eliminates wrong-script-to-node assignments and missing autoloads — the two root causes identified in game analysis.

**Primary recommendation:** Implement `ContractPipeline` in `backend/backend/pipelines/contract/pipeline.py`, add it to the registry as `"contract"`, and use a `GameContract` Pydantic model as the typed handoff between Stage 2 and all downstream stages.

---

## Standard Stack

### Core (already in project, no new deps needed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | >=0.84.0 | LLM calls for all stages | Already used; AsyncAnthropic for async |
| pydantic | (via fastapi) | `GameContract` and all stage I/O models | Already used project-wide |
| asyncio | stdlib | `asyncio.gather()` for parallel node generation | stdlib, no install needed |
| pytest-anyio | dev dep | Async test support | Already configured with asyncio_mode=auto |

### No New Production Dependencies Required

All necessary tools are already installed. The new pipeline is pure Python using:
- `asyncio.gather()` for parallelism (stdlib)
- `pydantic.BaseModel` for contract data structures (already installed via fastapi)
- `anthropic.AsyncAnthropic` for LLM calls (already installed)

---

## Architecture Patterns

### Recommended Project Structure

```
backend/backend/
├── pipelines/
│   ├── base.py                     # GamePipeline Protocol (unchanged)
│   ├── registry.py                 # Add "contract" -> ContractPipeline
│   ├── multi_stage/
│   │   └── pipeline.py             # Unchanged
│   └── contract/
│       ├── __init__.py
│       └── pipeline.py             # ContractPipeline
├── stages/
│   ├── models.py                   # Add GameContract model here
│   ├── spec_expander.py            # Stage 1: prompt -> RichGameSpec
│   ├── contract_generator.py       # Stage 2: RichGameSpec -> GameContract
│   ├── node_generator.py           # Stage 3: node-level code gen (called in parallel)
│   ├── wiring_generator.py         # Stage 4: Main.tscn + project.godot
│   └── exporter.py                 # Stage 5: reused unchanged
```

### Pattern 1: GameContract Pydantic Model

**What:** Typed data structure encoding all cross-file interface contracts. This is the single source of truth that Stage 2 produces and all subsequent stages consume.

**When to use:** Passed to every node generator in Stage 3 and to the wiring generator in Stage 4.

**Recommended structure:**

```python
# Source: project design (new model, add to backend/backend/stages/models.py)
from pydantic import BaseModel

class NodeContract(BaseModel):
    """Contract for a single generated node/script."""
    script_path: str          # e.g. "player.gd"
    scene_path: str | None    # e.g. "Player.tscn", None if script-only
    node_type: str            # Godot node type: "CharacterBody2D", "Node2D", etc.
    description: str          # What this node does
    methods: list[str]        # Public method signatures: ["init()", "die()", "get_velocity() -> Vector2"]
    signals: list[str]        # Signal names this node emits: ["shoot_requested", "died"]
    groups: list[str]         # Groups this node belongs to: ["platforms", "enemies"]
    dependencies: list[str]   # script_paths this node calls methods/signals on

class GameContract(BaseModel):
    """Full interface contract produced by Stage 2."""
    title: str
    nodes: list[NodeContract]
    game_manager_enums: dict[str, list[str]]  # enum name -> values: {"GameState": ["PLAYING", "WON", "LOST"]}
    game_manager_properties: list[str]        # extra properties added to game_manager.gd
    autoloads: list[str]                      # additional autoload script paths beyond GameManager
    main_scene: str                           # entry scene: "Main.tscn"
    control_scheme: str
    controls: list[dict]                      # same ControlMapping shape as existing pipeline
    visual_style: dict                        # palette, shader, mood (same as VisualStyle)
```

### Pattern 2: asyncio.gather() for Parallel Leaf Generation

**What:** Run all leaf-node LLM calls simultaneously using `asyncio.gather()`.

**When to use:** Stage 3, for all nodes with no dependencies (or whose dependencies are all already generated).

**Example:**

```python
# Source: Python asyncio stdlib docs
import asyncio

async def run_parallel_node_generation(
    client: AsyncAnthropic,
    contract: GameContract,
    emit: EmitFn,
) -> dict[str, str]:
    """Generate all leaf nodes in parallel, then orchestrators."""
    # Separate leaves from orchestrators
    leaf_nodes = [n for n in contract.nodes if not n.dependencies]
    orchestrator_nodes = [n for n in contract.nodes if n.dependencies]

    await emit(ProgressEvent(
        type="stage_start",
        message=f"Generating {len(leaf_nodes)} game files in parallel..."
    ))

    # Generate all leaves concurrently
    leaf_results = await asyncio.gather(*[
        _generate_single_node(client, node, contract) for node in leaf_nodes
    ])
    files: dict[str, str] = {}
    for node, node_files in zip(leaf_nodes, leaf_results):
        files.update(node_files)

    # Generate orchestrators sequentially (they depend on leaf contracts)
    for node in orchestrator_nodes:
        node_files = await _generate_single_node(client, node, contract)
        files.update(node_files)

    return files
```

### Pattern 3: Per-Node Generation with Contract Context

**What:** Each LLM call for a node receives: (1) the node's NodeContract, (2) the full GameContract for cross-reference, (3) the current project-wide context (title, visual style).

**When to use:** `_generate_single_node()` called by Stage 3.

**Key prompt engineering principle:** The node generator is told "you are generating ONLY this file; all other files will be generated separately; your method signatures MUST match exactly what the contract specifies."

```python
# Source: project-specific design
async def _generate_single_node(
    client: AsyncAnthropic,
    node: NodeContract,
    contract: GameContract,
) -> dict[str, str]:
    """Generate .gd and optionally .tscn for a single node."""
    prompt = _build_node_prompt(node, contract)
    # Returns {"player.gd": "...", "Player.tscn": "..."}
    ...
```

### Pattern 4: Wiring Stage with Full File Inventory

**What:** Stage 4 receives the complete `files` dict (all generated scripts/scenes), the `GameContract`, and generates `Main.tscn` and `project.godot`.

**Key correctness invariant:** The wiring stage is the ONLY stage that writes `Main.tscn` and `project.godot`. Node generators produce only their own `.gd` and `.tscn` files, never the root wiring files.

**Why this prevents the background.gd bug:** Stage 4 explicitly assigns `ext_resource` script paths in `Main.tscn` using the contract's `script_path` per node — there is no ambiguity because the contract defines which script belongs to which node.

### Pattern 5: Registry Integration

**What:** Add `"contract"` key to the existing `PIPELINES` dict.

```python
# Source: backend/backend/pipelines/registry.py (existing pattern)
from .contract.pipeline import ContractPipeline

PIPELINES: dict[str, type] = {
    "stub": StubPipeline,
    "multi_stage": MultiStagePipeline,
    "contract": ContractPipeline,      # new
}
```

### Anti-Patterns to Avoid

- **Having node generators write Main.tscn:** Only the wiring stage writes Main.tscn. Node generators writing Main.tscn is what caused conflicting scripts in the previous analysis.
- **Putting contract generation inside Stage 1:** The spec expander produces a human-readable rich spec; the contract generator (Stage 2) converts that to the machine-readable typed contract. Keep them separate so Stage 2 can focus on interface precision.
- **Using asyncio.gather() for ALL stages:** Only Stage 3 (node generation) benefits from parallelism. Stages 1, 2, 4, 5 are sequential by design. Mixing them incorrectly would produce race conditions.
- **Sharing state between parallel node generators:** Each node generator must be pure: input = NodeContract + GameContract, output = dict[str, str]. No shared mutable state between coroutines.
- **Generating project.godot from scratch in Stage 4:** Stage 4 should start with the template's `project.godot` content as a base and patch only the `[autoload]` and `run/main_scene` sections. This preserves the pre-defined input mappings (8 actions) that the template defines.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async concurrency | Custom thread pool or subprocess workers | `asyncio.gather()` | Anthropic client is already async; gather is zero-overhead coroutine concurrency |
| Data validation of contract JSON | Custom dict parsing + type checks | `pydantic.BaseModel` | Already in project; gives free validation, serialization, and schema documentation |
| Dependency graph scheduling | Custom topological sort | Simple two-pass: leaves (empty `dependencies` list) then orchestrators | Godot project graph is always depth-2 (leaves → orchestrators); general DAG scheduler is over-engineering |
| LLM streaming for per-node generation | Custom streaming aggregator | Reuse existing `stream=True` + async iteration pattern from `run_code_generator` | Pattern already validated in codebase |
| File validation | New validator framework | Extend existing `validate_generated_files()` + `_check_scene_integrity()` in `code_generator.py` | Same checks apply; add contract-adherence check on top |

**Key insight:** The parallel node generation problem looks harder than it is. The dependency graph is flat (max depth 2), so `asyncio.gather()` on leaf scripts followed by sequential orchestrators is sufficient. No general DAG scheduler needed.

---

## Common Pitfalls

### Pitfall 1: Contract Drift Between Stage 2 and Stage 3
**What goes wrong:** Stage 2 generates a contract specifying `die()` on `enemy.gd`, but Stage 3's LLM call for `enemy.gd` generates `death()` instead. The wiring stage then references `die()`, breaking the game.
**Why it happens:** Each LLM call is independent; the model may deviate from the spec unless strongly constrained.
**How to avoid:** The node generator prompt must include the EXACT method signatures from the contract and instruct the LLM: "Implement exactly these methods with these exact names. Do not rename or add methods not in the contract."
**Warning signs:** Validation pass checking generated `.gd` files for method signatures present in the contract.

### Pitfall 2: Duplicate GameManager Definition
**What goes wrong:** The existing `game_manager.gd` in the template already defines `GameState` enum and `set_state()`. A node generator (or the spec expander) decides to regenerate `game_manager.gd`, creating a duplicate with conflicting enum values.
**Why it happens:** LLMs sometimes generate files they see referenced in context, even when not asked.
**How to avoid:** The node generator system prompt must explicitly state: "Do NOT generate game_manager.gd. GameManager is a pre-existing autoload. Reference it via `GameManager.set_state()` etc."
**Warning signs:** `game_manager.gd` appearing in the `files` dict returned by Stage 3.

### Pitfall 3: Wiring Stage Generating project.godot from Scratch
**What goes wrong:** The wiring stage generates a fresh `project.godot` without the input action mappings, breaking all 8 `Input.is_action_pressed()` calls in generated scripts.
**Why it happens:** LLM doesn't know the template's `project.godot` already has `[input]` section unless given the template content.
**How to avoid:** The wiring stage reads the template's `project.godot` at runtime (as the exporter reads the template dir) and patches only `[autoload]` and `[application]/run/main_scene`. Or: the wiring stage generates only `Main.tscn` and leaves `project.godot` to the exporter (which copies the template unchanged).
**Warning signs:** Generated `project.godot` missing `[input]` section.

### Pitfall 4: asyncio.gather() Exception Handling
**What goes wrong:** One of 6 parallel node generators raises an exception; the other 5 complete successfully but their results are discarded and the user sees an unhelpful error.
**Why it happens:** `asyncio.gather()` default behavior: re-raises the first exception and cancels remaining tasks.
**How to avoid:** Use `asyncio.gather(*coros, return_exceptions=True)`, then check results for `Exception` instances. Emit a ProgressEvent warning per failed node and either fail fast or continue with partial results.
**Warning signs:** Any exception from one coroutine silently discarding 5 successful results.

### Pitfall 5: LLM Generating Files for Other Nodes
**What goes wrong:** The node generator for `player.gd` also emits `enemy.gd` because it sees enemies referenced in the spec.
**Why it happens:** LLMs are helpful and want to complete the full game; single-file scope is counterintuitive.
**How to avoid:** The node generator system prompt: "Respond with ONLY a JSON object containing the script(s) for THIS NODE: `{node.script_path}` (and `{node.scene_path}` if applicable). Do not generate any other files."
**Warning signs:** `files` dict from a single node generator call containing more keys than expected.

### Pitfall 6: Main.tscn ext_resource ID Collisions
**What goes wrong:** The wiring stage generates `Main.tscn` with duplicate `id="1"` for multiple ext_resources.
**Why it happens:** Godot .tscn format requires unique string IDs for each `[ext_resource]` entry. Manual ID assignment can collide.
**How to avoid:** Use a counter (incrementing integer as string) for ext_resource IDs in the wiring stage. Example: id="1", id="2", id="3", etc.
**Warning signs:** Godot export stderr mentioning "duplicate resource ID".

---

## Code Examples

Verified patterns from existing codebase and stdlib:

### AsyncAnthropic Streaming Pattern (from existing code_generator.py)
```python
# Source: backend/backend/stages/code_generator.py (existing, reuse verbatim)
response = await client.messages.create(
    model=SONNET_MODEL,
    max_tokens=8192,
    system=system_prompt,
    messages=[{"role": "user", "content": user_message}],
    stream=True,
)
collected_text = []
async for event in response:
    if event.type == "content_block_delta" and hasattr(event.delta, "text"):
        collected_text.append(event.delta.text)
raw = "".join(collected_text).strip()
```

### asyncio.gather() with Exception Capture
```python
# Source: Python stdlib asyncio docs
import asyncio

results = await asyncio.gather(
    *[coro_fn(node) for node in leaf_nodes],
    return_exceptions=True,
)
files: dict[str, str] = {}
failed: list[str] = []
for node, result in zip(leaf_nodes, results):
    if isinstance(result, Exception):
        failed.append(f"{node.script_path}: {result}")
    else:
        files.update(result)
if failed:
    await emit(ProgressEvent(type="stage_start", message=f"Warning: {len(failed)} nodes failed generation"))
```

### Pydantic Model with Optional Fields (for flexible contract)
```python
# Source: existing models.py pattern
from pydantic import BaseModel

class NodeContract(BaseModel):
    script_path: str
    scene_path: str | None = None   # None for script-only nodes
    node_type: str
    description: str
    methods: list[str] = []
    signals: list[str] = []
    groups: list[str] = []
    dependencies: list[str] = []    # empty = leaf node
```

### project.godot Patch Strategy (safe approach)
```python
# Source: project-specific pattern derived from existing exporter.py template copy
# The exporter already copies the full template (including project.godot with input actions).
# The wiring stage only needs to generate Main.tscn + per-scene .tscn files.
# project.godot is handled by the template copy in run_exporter() — no override needed.
# If custom autoloads beyond GameManager are needed, the wiring stage writes project.godot
# by reading the template version first:

import re
template_project_godot = (TEMPLATE_DIR / "project.godot").read_text()

# Replace autoload section only
new_autoload = "[autoload]\n\nGameManager=\"*res://game_manager.gd\"\n"
for extra in contract.autoloads:
    name = Path(extra).stem.replace("_", "")
    new_autoload += f"{name}=\"*res://{extra}\"\n"

patched = re.sub(
    r"\[autoload\].*?(?=\n\[|\Z)",
    new_autoload,
    template_project_godot,
    flags=re.DOTALL,
)
```

### Pipeline Registration Pattern (from existing registry.py)
```python
# Source: backend/backend/pipelines/registry.py (existing pattern)
PIPELINES: dict[str, type] = {
    "stub": StubPipeline,
    "multi_stage": MultiStagePipeline,
    "contract": ContractPipeline,   # add this
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic LLM call generates all files | Per-node LLM calls with shared contract | Phase 5 | LLM context is smaller per call; each file stays within token budget |
| Sequential file generation | Parallel leaf generation via asyncio.gather | Phase 5 | 5-6x speedup for leaf node generation phase |
| Post-hoc validation catches wiring errors | Contract defined upfront; wiring stage enforces it | Phase 5 | Wiring errors prevented rather than detected after the fact |
| GameManager enum defined ad-hoc by code generator | GameManager extensions defined in GameContract | Phase 5 | Single authoritative definition; no conflicting enum values |

**Still current:**
- `asyncio_mode = "auto"` in pytest.ini_options — tests work without `@pytest.mark.anyio` decorator changes
- `client.messages.create(..., stream=True)` pattern — reuse exactly as in code_generator.py
- `pydantic v2` `model_validate()` + `model_dump_json()` — already used project-wide

---

## Open Questions

1. **Should the spec expander reuse `run_prompt_enhancer` + `run_game_designer` or replace them?**
   - What we know: The existing two stages produce `GameSpec` → `GameDesign`. The new Stage 1 (Spec Expander) needs a richer output that includes entity names, interaction types, and rough scene structure.
   - What's unclear: Whether adapting the existing `GameDesign` model with additional fields is cleaner than a new `RichGameSpec` model.
   - Recommendation: Create a new `RichGameSpec` model and new `run_spec_expander` function. The existing `GameDesign` model lacks entity-level detail (it describes scenes, not individual node types + contracts). Avoid coupling new and old pipelines' data models.

2. **How many nodes should the contract specify?**
   - What we know: The flat graph has leaf nodes + 1-2 orchestrator scripts. For a simple game, expect 4-8 leaf scripts (player, enemy, platform, projectile, powerup, background, hud, game_over) plus 1 main.gd orchestrator.
   - What's unclear: Whether to let Stage 2 decide the node list freely or constrain it to a known set.
   - Recommendation: Let Stage 2 decide. Provide a JSON schema for `NodeContract` and let the LLM produce 4-10 nodes. This is Claude's discretion per CONTEXT.md.

3. **What token budget per node generator call?**
   - What we know: Current code_generator uses `max_tokens=32768` for all files at once. Per-node calls should be much smaller.
   - Recommendation: Use `max_tokens=8192` per node for `.gd` files, `max_tokens=4096` for `.tscn` files. These match the existing repair call budget.

4. **Does Stage 4 generate project.godot?**
   - What we know: The existing exporter copies the template (which includes `project.godot` with all 8 input actions). If the contract specifies no extra autoloads, `project.godot` can be left entirely to the template copy.
   - Recommendation: Stage 4 generates `Main.tscn` always. It generates `project.godot` only if `contract.autoloads` is non-empty (i.e., custom scripts beyond GameManager need autoloading). This minimizes the risk of breaking the input action mappings.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-anyio |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]` asyncio_mode = "auto") |
| Quick run command | `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/ -x -q` |
| Full suite command | `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/ -v` |

### Phase Requirements → Test Map

This phase has no formal REQ-IDs, but the behaviors to test are:

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| `GameContract` Pydantic model validates correctly | unit | `uv run pytest backend/tests/test_contract_pipeline.py::test_game_contract_validation -x` | Wave 0 |
| `run_spec_expander` emits stage_start and returns RichGameSpec | unit | `uv run pytest backend/tests/test_contract_pipeline.py::test_spec_expander_emits_and_returns -x` | Wave 0 |
| `run_contract_generator` returns valid GameContract from RichGameSpec | unit | `uv run pytest backend/tests/test_contract_pipeline.py::test_contract_generator_returns_contract -x` | Wave 0 |
| Parallel node generation generates all leaf nodes | unit | `uv run pytest backend/tests/test_contract_pipeline.py::test_parallel_node_generation -x` | Wave 0 |
| One failed node generator doesn't kill all others | unit | `uv run pytest backend/tests/test_contract_pipeline.py::test_parallel_node_failure_handling -x` | Wave 0 |
| Wiring generator produces valid Main.tscn with correct ext_resource refs | unit | `uv run pytest backend/tests/test_contract_pipeline.py::test_wiring_generator_produces_main_tscn -x` | Wave 0 |
| ContractPipeline registered in PIPELINES dict | unit | `uv run pytest backend/tests/test_contract_pipeline.py::test_registry_has_contract_pipeline -x` | Wave 0 |
| Full ContractPipeline.generate() with mocked LLM returns GameResult | integration | `uv run pytest backend/tests/test_contract_pipeline.py::test_full_pipeline_end_to_end -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/ -x -q`
- **Per wave merge:** `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/backend/tests/test_contract_pipeline.py` — covers all new ContractPipeline behaviors
- [ ] No new framework install needed — pytest + pytest-anyio already configured

---

## Sources

### Primary (HIGH confidence)
- Existing codebase: `backend/backend/pipelines/base.py`, `multi_stage/pipeline.py`, `registry.py`
- Existing codebase: `backend/backend/stages/code_generator.py` — streaming LLM pattern, validation/repair pattern
- Existing codebase: `backend/backend/stages/models.py` — Pydantic model patterns in use
- Python stdlib asyncio documentation — `asyncio.gather()`, `return_exceptions=True` behavior
- Godot 4 text scene format: `godot/templates/base_2d/Main.tscn`, `project.godot` — ExtResource format, autoload format

### Secondary (MEDIUM confidence)
- Python asyncio `gather()` exception propagation behavior — verified against stdlib behavior (return_exceptions parameter)
- Godot ext_resource ID collision behavior — derived from Godot text format spec + existing validation code in `_check_scene_integrity()`

### Tertiary (LOW confidence, flag for validation)
- Per-node `max_tokens=8192` recommendation — derived from existing code, not formally benchmarked against actual node sizes

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all tools already in project
- Architecture: HIGH — directly derived from existing codebase patterns and known root causes
- Pitfalls: HIGH — pitfalls 1-3 derived from the game analysis findings documented in CONTEXT.md; pitfalls 4-6 derived from existing code patterns

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (stable domain; Anthropic API and asyncio stdlib are stable)
