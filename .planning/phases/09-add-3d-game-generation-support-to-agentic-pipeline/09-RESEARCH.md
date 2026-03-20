# Phase 09: Add 3D Game Generation Support to Agentic Pipeline - Research

**Researched:** 2026-03-20
**Domain:** Godot 4 3D pipeline integration, agentic prompt engineering
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Schema:**
- Add `perspective: Literal["2D", "3D"]` to `AgenticGameSpec` with default `"2D"` for backward compatibility
- Field flows through entire pipeline — spec generator sets it, file generator and verifier read it from spec

**Spec Generator:**
- Add `perspective` property (enum: 2D/3D) to `SUBMIT_SPEC_TOOL` input schema, mark required
- Add "Determine whether the game is 2D or 3D based on the concept" to system prompt
- Make entity type description dimension-aware: show both 2D types (CharacterBody2D, Area2D, StaticBody2D) and 3D types (CharacterBody3D, Area3D, Node3D, Camera3D, MeshInstance3D)

**File Generator (biggest change):**
- Convert `GENERATOR_SYSTEM_PROMPT` from static string to `build_generator_system_prompt(perspective: str) -> str` function
- Dynamic sections based on perspective:
  - Mission statement: "2D game project" vs "3D game project"
  - Control snippets: show for 2D, mark as "2D only, not applicable" for 3D
  - Entity node types: 2D types vs 3D types
  - Main scene root: Node2D vs Node3D
  - Display config: `canvas_items` stretch mode for 2D, `disabled` for 3D
- Add 3D-only essentials section: Camera3D required, lighting required, Vector3 not Vector2, built-in meshes (BoxMesh, SphereMesh, etc.), WorldEnvironment guidance
- Pass spec.perspective through `run_file_generation()` to builder at generation time

**Exporter:**
- Add `_get_template_dir(perspective: str)` to select base_2d vs base_3d
- Pass perspective from pipeline orchestrator into `run_exporter()`

**Template:**
- Create `godot/templates/base_3d/` by copying base_2d and adapting
- Keep: export_presets.cfg, default_bus_layout.tres, .godot/ cache
- Remove: 2D-only control snippets from assets/
- Keep: screen-space shaders that work in 3D (chromatic_aberration, glow)
- Remove: 2D-only shaders (pixel_art is 2D-specific)

**Verifier:**
- No prompt changes — verifier receives full AgenticGameSpec with perspective field in spec summary, existing dimension-agnostic checks suffice, LLM infers 3D-specific issues from context

**3D essentials prompt section must include:**
- Camera3D, DirectionalLight3D/OmniLight3D, Vector3, move_and_slide() on CharacterBody3D
- MeshInstance3D with built-in meshes (BoxMesh, SphereMesh, CapsuleMesh, CylinderMesh, PlaneMesh, QuadMesh)
- WorldEnvironment
- Display config: `window/stretch/mode="disabled"` (not `canvas_items`)
- Rendering stays `gl_compatibility` for both (WASM target)

### Claude's Discretion

- Exact shader curation for base_3d (which shaders are truly 3D-compatible)
- Whether to add 3D-specific assets (toon shader, default environment .tres) to the template
- Internal code structure of `build_generator_system_prompt()` (string building approach)
- Test coverage for new perspective-dependent paths

### Deferred Ideas (OUT OF SCOPE)

- 3D-specific asset library (toon shaders, environment presets) — add if quality proves insufficient
- Verifier prompt 3D-specific checks — only if verification quality is insufficient in practice
- Isometric/2.5D as a third perspective option
</user_constraints>

---

## Summary

Phase 9 adds a `perspective` field to the agentic pipeline, routing 2D and 3D game generation through divergent prompt paths while sharing the same generate-verify-fix orchestration loop. The changes are additive: the schema grows by one field, the spec generator gains a decision, the file generator's system prompt becomes a function, the exporter gains template selection, and a new `base_3d/` template is created.

The technical core is prompt engineering: what does the LLM need to know to generate correct Godot 4 3D GDScript? The 3D node hierarchy differs significantly from 2D — CharacterBody3D, CollisionShape3D, MeshInstance3D, Camera3D, DirectionalLight3D, and WorldEnvironment are all required for a functional 3D game. Shaders in base_2d use `shader_type canvas_item`, which is 2D-only; only `shader_type spatial` (3D surface) or `shader_type sky`/`shader_type particles` work in 3D scenes. The two existing shaders to keep (glow, chromatic_aberration) are canvas_item typed — they work only on CanvasLayer or UI elements in 3D contexts, not on 3D meshes directly. This is a nuance the template curation decision must address.

**Primary recommendation:** Implement `build_generator_system_prompt(perspective: str)` as a function that shares boilerplate (Variant typing rules, dynamic spawning rules, tool instructions, asset paths) and branches only on the 2D vs 3D-specific sections. The base_3d template should be a minimal copy of base_2d with control snippets removed, pixel_art/scanlines/screen_distortion shaders removed, and project.godot stretch mode set to `disabled`.

---

## Standard Stack

### Core (unchanged — agentic pipeline already uses these)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic (AsyncAnthropic) | current | LLM calls | Already in use |
| pydantic (BaseModel) | current | Schema validation | Already in use |
| Python Literal type | stdlib | Enum-style field | Already used in models.py |

### No new dependencies required
This phase adds no new Python packages. All changes are to existing files or new template assets.

---

## Architecture Patterns

### Recommended Structure After Phase 9

```
backend/backend/pipelines/agentic/
├── models.py          # AgenticGameSpec gains perspective field
├── spec_generator.py  # SUBMIT_SPEC_TOOL gains perspective property
├── file_generator.py  # GENERATOR_SYSTEM_PROMPT -> build_generator_system_prompt()
├── verifier.py        # UNCHANGED
├── pipeline.py        # pass spec.perspective to run_file_generation, run_exporter
├── input_map.py       # UNCHANGED
└── ...

backend/backend/pipelines/
├── exporter.py        # _get_template_dir(), run_exporter gains perspective param
└── assets.py          # UNCHANGED (paths are same in base_3d)

godot/templates/
├── base_2d/           # UNCHANGED
└── base_3d/           # NEW: copy of base_2d minus 2D-only files, different project.godot
    ├── export_presets.cfg      # identical copy
    ├── default_bus_layout.tres # identical copy
    ├── .godot/                 # identical copy
    ├── assets/
    │   ├── shaders/
    │   │   ├── glow.gdshader              # keep (canvas_item — usable on UI in 3D)
    │   │   └── chromatic_aberration.gdshader  # keep (canvas_item — usable on UI in 3D)
    │   │   # REMOVE: pixel_art, scanlines, screen_distortion (canvas_item 2D-only)
    │   ├── palettes/           # keep all (Gradient .tres files work in 3D)
    │   └── particles/          # keep all (GPUParticles3D works in 3D)
    │   # REMOVE: control_snippets/ (2D Node2D scripts)
    └── project.godot           # adapted: stretch mode=disabled, no canvas_items
```

### Pattern 1: Schema Field with Default for Backward Compatibility

The `perspective` field uses a Pydantic `Literal` with a default of `"2D"` so existing callers that don't provide perspective still get valid specs. This is the same pattern already used in the contract pipeline (`spawn_mode: Literal['static', 'dynamic'] = 'static'` from Phase 5.2 decision log).

```python
# models.py — add to AgenticGameSpec
from typing import Literal

class AgenticGameSpec(BaseModel):
    title: str
    genre: str
    mechanics: list[str]
    entities: list[dict]
    scene_description: str
    win_condition: str
    fail_condition: str
    perspective: Literal["2D", "3D"] = "2D"  # NEW — default preserves backward compat
```

### Pattern 2: Dynamic Prompt Builder Function

Convert the module-level constant to a function. The function shares all dimension-agnostic content (Variant rules, spawning rules, project.godot skeleton, asset paths) and branches only on dimension-specific sections.

```python
# file_generator.py — rename from GENERATOR_SYSTEM_PROMPT constant
def build_generator_system_prompt(perspective: str) -> str:
    """Build the file generator system prompt based on game perspective."""
    is_3d = (perspective == "3D")

    mission = (
        "Your job is to generate all files for a complete, playable 3D game project one at a time by calling write_file."
        if is_3d else
        "Your job is to generate all files for a complete, playable 2D game project one at a time by calling write_file."
    )

    # ... dimension-specific entity types, root node, display config, 3D essentials ...
    return "\n".join([header, mission, critical_rules, important_rules, project_godot_skeleton, asset_section])
```

Pass perspective at call time in `run_file_generation`:

```python
async def run_file_generation(
    client: AsyncAnthropic,
    spec: AgenticGameSpec,
    game_dir: Path,
    emit: EmitFn,
    *,
    context_strategy: str = "full_history",
    fix_context: str | None = None,
    existing_files: dict[str, str] | None = None,
) -> tuple[dict[str, str], list[dict]]:
    system_prompt = build_generator_system_prompt(spec.perspective)
    # ... rest of loop uses system_prompt instead of GENERATOR_SYSTEM_PROMPT
```

### Pattern 3: Template Dir Selection in Exporter

```python
# exporter.py
_REPO_ROOT = Path(__file__).parent.parent.parent.parent
TEMPLATE_DIR_2D = _REPO_ROOT / "godot" / "templates" / "base_2d"
TEMPLATE_DIR_3D = _REPO_ROOT / "godot" / "templates" / "base_3d"


def _get_template_dir(perspective: str) -> Path:
    """Return the template directory for the given perspective."""
    if perspective == "3D":
        return TEMPLATE_DIR_3D
    return TEMPLATE_DIR_2D


async def run_exporter(
    game_dir: str,
    files: dict[str, str],
    controls: list[dict],
    emit: EmitFn,
    *,
    perspective: str = "2D",   # NEW param with default for backward compat
) -> GameResult:
    template_dir = _get_template_dir(perspective)
    shutil.copytree(template_dir, project_dir, dirs_exist_ok=True)
    # ... rest unchanged
```

Pipeline orchestrator (pipeline.py) passes `perspective=spec.perspective` to `run_exporter`.

### Anti-Patterns to Avoid

- **Branching in the static constant:** Do not gate prompt sections with runtime `if` in a module-level string. Always use the builder function pattern.
- **Shadowing GENERATOR_SYSTEM_PROMPT entirely:** Keep the constant name available as `GENERATOR_SYSTEM_PROMPT = build_generator_system_prompt("2D")` for backward compat if any tests import it by name. (See `test_file_generator_prompt.py` which imports `GENERATOR_SYSTEM_PROMPT` directly.)
- **Using canvas_item shaders in 3D meshes:** `shader_type canvas_item` only applies to 2D nodes and UI — do not put these on MeshInstance3D. The base_3d template keeps them because they still apply to CanvasLayer-based HUD overlays in 3D games.
- **Omitting Camera3D or lighting:** A 3D Godot scene with no Camera3D renders nothing (black screen). A scene with no light source shows only unlit, solid-black meshes unless using WorldEnvironment with ambient light. Both are critical.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 3D mesh shapes | Custom mesh generation code | Built-in Godot mesh classes (BoxMesh, SphereMesh, CapsuleMesh, etc.) | These are instantiated as resources in GDScript with zero boilerplate |
| 3D lighting | Custom shader-based light sim | DirectionalLight3D / OmniLight3D / SpotLight3D nodes | Standard Godot scene nodes — just add and configure |
| 3D camera | Custom projection math | Camera3D with default perspective projection | Godot default is perspective 70° FOV — correct for most 3D games |
| World ambient | Manual ambient color setup | WorldEnvironment + Environment resource | Standard Godot pattern for sky/ambient/fog/glow in 3D |
| Perspective detection | Keyword matching on user prompt | LLM determination in spec generator | The spec generator LLM has full context and should decide |

**Key insight:** The LLM already knows Godot 4 3D API. The prompt only needs to make the right concepts salient — Camera3D requirement, lighting requirement, Vector3 instead of Vector2, CharacterBody3D/move_and_slide() for physics-based characters.

---

## Common Pitfalls

### Pitfall 1: Black Screen — Missing Camera3D

**What goes wrong:** LLM generates a 3D scene with Node3D root but no Camera3D. Godot exports fine, but the game shows a black screen.
**Why it happens:** LLM trained on 2D games defaults to Node2D root with no camera (2D has no camera requirement for basic scenes). Camera3D is opt-in in 3D and not inferrable from the game spec alone.
**How to avoid:** The 3D-only essentials section of the prompt MUST list Camera3D as a hard requirement with explicit language: "REQUIRED: Every 3D game MUST include a Camera3D node."
**Warning signs:** Verifier can detect this — it's a "missing" error type. But the prompt should prevent it.

### Pitfall 2: Black Meshes — Missing Lighting

**What goes wrong:** LLM generates MeshInstance3D nodes but no light source. Meshes render black/dark in gl_compatibility renderer.
**Why it happens:** gl_compatibility (OpenGL ES 3) does not have automatic ambient light — all shading is zero without a light source or WorldEnvironment with ambient settings.
**How to avoid:** Prompt must state: "REQUIRED: Every 3D game MUST include at least one DirectionalLight3D or OmniLight3D node. Without a light source, all meshes will appear black."
**Warning signs:** Verifier can flag this as "missing" with critical severity.

### Pitfall 3: Wrong stretch mode — canvas_items in 3D project.godot

**What goes wrong:** LLM copies 2D project.godot verbatim with `window/stretch/mode="canvas_items"`. This works but causes minor rendering glitches in 3D (viewport doesn't behave as expected for 3D aspect ratio).
**Why it happens:** The 2D project.godot skeleton is the example the LLM has seen most. The 3D prompt must explicitly override this.
**How to avoid:** 3D prompt skeleton for project.godot MUST show `window/stretch/mode="disabled"` not `canvas_items`.
**Warning signs:** Game runs but UI scaling and viewport behavior may be off.

### Pitfall 4: Vector2 used in 3D scripts

**What goes wrong:** LLM writes `velocity = Vector2(...)` or `position = Vector2(...)` in a CharacterBody3D script.
**Why it happens:** Vector2 is the default for 2D scripts. The LLM needs explicit reminding.
**How to avoid:** Prompt must include "Use Vector3 not Vector2 for all 3D positions, velocities, and directions."

### Pitfall 5: canvas_item shader applied to MeshInstance3D

**What goes wrong:** LLM writes code applying a `canvas_item` shader (e.g., glow.gdshader) to a MeshInstance3D via `mesh_instance.material_override = shader_material`. Godot silently ignores it or logs a warning.
**Why it happens:** The asset list in the prompt includes glow.gdshader without noting its shader type.
**How to avoid:** In the 3D asset section, note shaders as "HUD/overlay only — not applicable to 3D mesh materials." Do not remove them from the template (they're valid for CanvasLayer-based HUDs), but annotate them clearly in the prompt.

### Pitfall 6: Test suite importing GENERATOR_SYSTEM_PROMPT as constant

**What goes wrong:** `test_file_generator_prompt.py` imports `GENERATOR_SYSTEM_PROMPT` by name. If the constant is removed and replaced purely with `build_generator_system_prompt()`, the existing test will break with `ImportError`.
**Why it happens:** Phase 8 tests were written against the constant.
**How to avoid:** After converting to the builder function, expose a module-level constant for the default case: `GENERATOR_SYSTEM_PROMPT = build_generator_system_prompt("2D")`. This maintains import compatibility. The existing tests will still pass (they test the 2D prompt). New tests cover 3D prompt content.

### Pitfall 7: Exporter signature change breaks callers

**What goes wrong:** Adding `perspective` param to `run_exporter()` without a default breaks any existing callers that don't pass it.
**Why it happens:** `run_exporter` is called from multiple pipeline orchestrators (AgenticPipeline and potentially others).
**How to avoid:** Use keyword-only arg with default: `*, perspective: str = "2D"`. Only AgenticPipeline needs to pass `perspective=spec.perspective`; all other callers get backward-compatible 2D behavior.

---

## Code Examples

### 3D project.godot stretch mode (verified from CONTEXT.md specifics section)

```ini
[display]
window/size/viewport_width=1152
window/size/viewport_height=648
window/stretch/mode="disabled"
window/stretch/aspect="expand"
```

### Minimal 3D scene structure (Main.tscn pattern for LLM)

```
Node3D (Main.tscn root, script=main.gd)
├── Camera3D
├── DirectionalLight3D
├── WorldEnvironment
└── [game-specific nodes: CharacterBody3D, MeshInstance3D, etc.]
```

### CharacterBody3D movement (core 3D physics pattern)

```gdscript
extends CharacterBody3D

const SPEED = 5.0
const JUMP_VELOCITY = 4.5
var gravity = ProjectSettings.get_setting("physics/3d/default_gravity")

func _physics_process(delta):
    if not is_on_floor():
        velocity.y -= gravity * delta

    var direction = Vector3.ZERO
    if Input.is_action_pressed("move_right"):
        direction.x += 1
    if Input.is_action_pressed("move_left"):
        direction.x -= 1

    if direction:
        velocity.x = direction.x * SPEED
        velocity.z = direction.z * SPEED
    else:
        velocity.x = move_toward(velocity.x, 0, SPEED)
        velocity.z = move_toward(velocity.z, 0, SPEED)

    move_and_slide()
```

### MeshInstance3D with built-in mesh (no external asset needed)

```gdscript
var mesh_instance = MeshInstance3D.new()
var box_mesh = BoxMesh.new()
box_mesh.size = Vector3(1, 1, 1)
mesh_instance.mesh = box_mesh
add_child(mesh_instance)
```

### Pydantic Literal field with default (backward compat pattern from Phase 5.2)

```python
# Source: existing codebase pattern (pipeline.py spawn_mode)
perspective: Literal["2D", "3D"] = "2D"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Static `GENERATOR_SYSTEM_PROMPT` constant | `build_generator_system_prompt(perspective)` function | Phase 9 | Enables dimension-specific prompt routing |
| Single `TEMPLATE_DIR` constant in exporter | `_get_template_dir(perspective)` function | Phase 9 | Enables template selection at export time |
| `AgenticGameSpec` without perspective | `perspective: Literal["2D", "3D"] = "2D"` | Phase 9 | Spec carries dimension through entire pipeline |

---

## Shader Curation Decision (Claude's Discretion)

The base_2d template has 5 shaders, all `shader_type canvas_item`:

| Shader | Keep in base_3d? | Rationale |
|--------|-----------------|-----------|
| glow.gdshader | YES | Applicable to CanvasLayer/UI overlays in 3D games |
| chromatic_aberration.gdshader | YES | Same — UI/HUD usage in 3D |
| pixel_art.gdshader | NO | Floor/pixelate UV operation is purely 2D sprite concept |
| scanlines.gdshader | NO | Pure 2D screen-space effect; rarely useful in 3D |
| screen_distortion.gdshader | NO | Uses TEXTURE_PIXEL_SIZE which is 2D-only in canvas_item |

**Recommendation:** Keep glow and chromatic_aberration in base_3d. They work as post-processing effects on CanvasLayer nodes (health bars, HUDs, screens-within-screens). Remove the other three — pixel_art and scanlines are 2D-specific aesthetics, screen_distortion uses TEXTURE_PIXEL_SIZE which doesn't work as expected in 3D.

The 3D prompt's asset section should annotate these shaders: "Shaders (apply to CanvasLayer or UI elements — NOT to 3D mesh materials):".

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with anyio plugin |
| Config file | `backend/pyproject.toml` |
| Quick run command | `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/test_agentic_models.py backend/tests/test_agentic_pipeline.py backend/tests/test_file_generator_prompt.py -x -q` |
| Full suite command | `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/ -x -q` |

### Phase Requirements → Test Map

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| `AgenticGameSpec` validates with `perspective="2D"` default | unit | `pytest tests/test_agentic_models.py -x -k perspective` | ❌ Wave 0 |
| `AgenticGameSpec` validates with `perspective="3D"` | unit | `pytest tests/test_agentic_models.py -x -k perspective` | ❌ Wave 0 |
| `AgenticGameSpec` rejects invalid perspective value | unit | `pytest tests/test_agentic_models.py -x -k perspective` | ❌ Wave 0 |
| Existing spec dict without `perspective` still validates (backward compat) | unit | `pytest tests/test_agentic_models.py -x -k "no_perspective or backward"` | ❌ Wave 0 |
| `build_generator_system_prompt("2D")` contains 2D node types | unit | `pytest tests/test_file_generator_prompt.py -x` | ✅ (adapt) |
| `build_generator_system_prompt("3D")` contains 3D node types (CharacterBody3D, Camera3D) | unit | `pytest tests/test_file_generator_prompt.py -x -k "3d"` | ❌ Wave 0 |
| `build_generator_system_prompt("3D")` contains `mode="disabled"` display config | unit | `pytest tests/test_file_generator_prompt.py -x -k "3d"` | ❌ Wave 0 |
| `build_generator_system_prompt("3D")` does NOT contain `canvas_items` stretch mode | unit | `pytest tests/test_file_generator_prompt.py -x -k "3d"` | ❌ Wave 0 |
| `GENERATOR_SYSTEM_PROMPT` constant still importable (backward compat) | unit | `pytest tests/test_file_generator_prompt.py::test_rendering_section -x` | ✅ (unchanged if constant preserved) |
| `run_file_generation` uses perspective from spec when building prompt | unit | `pytest tests/test_agentic_pipeline.py -x -k perspective` | ❌ Wave 0 |
| `_get_template_dir("2D")` returns base_2d path | unit | `pytest tests/test_exporter.py -x -k template_dir` | ❌ Wave 0 |
| `_get_template_dir("3D")` returns base_3d path | unit | `pytest tests/test_exporter.py -x -k template_dir` | ❌ Wave 0 |
| `run_exporter` with no perspective arg defaults to 2D (backward compat) | unit | `pytest tests/test_exporter.py -x -k backward_compat` | ❌ Wave 0 |
| `run_spec_generator` returns spec with `perspective` field set | unit | `pytest tests/test_agentic_models.py -x -k spec_generator` | ❌ Wave 0 |
| `SUBMIT_SPEC_TOOL` schema includes `perspective` property | unit | `pytest tests/test_agentic_models.py -x -k submit_spec_tool` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/test_agentic_models.py backend/tests/test_file_generator_prompt.py -x -q`
- **Per wave merge:** `cd /Users/albertluo/other/moonpond/backend && uv run pytest backend/tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_agentic_models.py` — add `perspective` field tests (file exists, needs new test methods)
- [ ] `backend/tests/test_file_generator_prompt.py` — add 3D prompt content tests; adapt existing tests if `GENERATOR_SYSTEM_PROMPT` constant is preserved
- [ ] `backend/tests/test_exporter.py` — add `_get_template_dir()` tests; file may not exist, check first
- [ ] `backend/tests/test_agentic_pipeline.py` — add test that `run_file_generation` is called with correct perspective; add test that `run_exporter` is called with `perspective=spec.perspective`

---

## Open Questions

1. **Does `test_exporter.py` already exist?**
   - What we know: It's not in the test file list from current scan
   - What's unclear: Whether exporter has any tests
   - Recommendation: Wave 0 should create `test_exporter.py` with `_get_template_dir()` tests and backward compat test for `run_exporter` default param

2. **Should `GENERATOR_SYSTEM_PROMPT` remain as a module-level constant?**
   - What we know: `test_file_generator_prompt.py` imports it by name; removing it breaks existing tests
   - What's unclear: Whether the plan prefers updating the test or preserving the constant
   - Recommendation: Preserve `GENERATOR_SYSTEM_PROMPT = build_generator_system_prompt("2D")` for backward compat; do not update the existing test

3. **Will the base_3d template's `.godot/` cache cause export issues?**
   - What we know: base_2d has a .godot/ cache with pre-exported assets; this cache was generated with the 2D template's assets
   - What's unclear: Whether copying the 2D `.godot/` cache into base_3d with different assets causes Godot to error
   - Recommendation: The `.godot/` cache is a build artifact — Godot regenerates it on first import/export. Copying it from base_2d into base_3d is safe because the headless export process will regenerate it. However, the base_3d template needs to be validated with an actual headless export after creation (manual task).

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `backend/backend/pipelines/agentic/` (all files read)
- Direct codebase inspection — `backend/backend/pipelines/exporter.py`
- Direct codebase inspection — `backend/backend/pipelines/assets.py`
- Direct codebase inspection — `backend/backend/tests/test_file_generator_prompt.py`
- Direct codebase inspection — `godot/templates/base_2d/` (all shader files read)
- `.planning/phases/09-add-3d-game-generation-support-to-agentic-pipeline/09-CONTEXT.md`
- `.planning/STATE.md` (decision log for Phases 1-8)

### Secondary (MEDIUM confidence)
- Godot 4 3D fundamentals: Camera3D, lighting, CharacterBody3D, MeshInstance3D, WorldEnvironment — assessed from training data knowledge of Godot 4 documentation (knowledge cutoff Aug 2025, stable API)
- Shader type scoping (canvas_item vs spatial): Verified by reading all 5 shader files in base_2d — all are `shader_type canvas_item`

### Tertiary (LOW confidence — needs validation)
- gl_compatibility renderer ambient light behavior in 3D — training data knowledge, not verified against Godot 4.5.1 docs directly
- `.godot/` cache reusability across templates — inferred from Godot's cache-as-build-artifact model

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all changes are to existing files
- Architecture: HIGH — patterns directly derived from CONTEXT.md decisions and existing codebase patterns
- Pitfalls: HIGH for code-level issues (verified by reading files); MEDIUM for runtime behavior (canvas_item in 3D, gl_compatibility lighting)
- Shader curation: MEDIUM — canvas_item type confirmed by file inspection; 3D usability of glow/chromatic_aberration in CanvasLayer context is sound but not 100% verified against headless export

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable API domain — Godot 4.5 is released, Anthropic SDK is stable)
