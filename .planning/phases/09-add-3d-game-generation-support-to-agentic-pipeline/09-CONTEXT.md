# Phase 9: Add 3D Game Generation Support to Agentic Pipeline - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning
**Source:** PRD Express Path (3d-plan.md)

<domain>
## Phase Boundary

Add 3D game generation capability to the agentic pipeline. The core approach: add a `perspective` field to the game spec schema, then make all prompts dynamic based on whether the game is 2D or 3D. No changes to the verifier prompt — it already receives the spec and can infer 3D-specific checks.

Files in scope:
- `backend/backend/pipelines/agentic/models.py` — schema
- `backend/backend/pipelines/agentic/spec_generator.py` — spec generation
- `backend/backend/pipelines/agentic/file_generator.py` — file generation (biggest change)
- `backend/backend/pipelines/exporter.py` — template selection
- `backend/backend/pipelines/agentic/pipeline.py` — orchestrator plumbing
- `godot/templates/base_3d/` — new template directory

</domain>

<decisions>
## Implementation Decisions

### Schema
- Add `perspective: Literal["2D", "3D"]` to `AgenticGameSpec` with default `"2D"` for backward compatibility
- Field flows through entire pipeline — spec generator sets it, file generator and verifier read it from spec

### Spec Generator
- Add `perspective` property (enum: 2D/3D) to `SUBMIT_SPEC_TOOL` input schema, mark required
- Add "Determine whether the game is 2D or 3D based on the concept" to system prompt
- Make entity type description dimension-aware: show both 2D types (CharacterBody2D, Area2D, StaticBody2D) and 3D types (CharacterBody3D, Area3D, Node3D, Camera3D, MeshInstance3D)

### File Generator (biggest change)
- Convert `GENERATOR_SYSTEM_PROMPT` from static string to `build_generator_system_prompt(perspective: str) -> str` function
- Dynamic sections based on perspective:
  - Mission statement: "2D game project" vs "3D game project"
  - Control snippets: show for 2D, mark as "2D only, not applicable" for 3D
  - Entity node types: 2D types vs 3D types
  - Main scene root: Node2D vs Node3D
  - Display config: `canvas_items` stretch mode for 2D, `disabled` for 3D
- Add 3D-only essentials section: Camera3D required, lighting required, Vector3 not Vector2, built-in meshes (BoxMesh, SphereMesh, etc.), WorldEnvironment guidance
- Pass spec.perspective through `run_file_generation()` to builder at generation time

### Exporter
- Add `_get_template_dir(perspective: str)` to select base_2d vs base_3d
- Pass perspective from pipeline orchestrator into `run_exporter()`

### Template
- Create `godot/templates/base_3d/` by copying base_2d and adapting
- Keep: export_presets.cfg, default_bus_layout.tres, .godot/ cache
- Remove: 2D-only control snippets from assets/
- Keep: screen-space shaders that work in 3D (chromatic_aberration, glow)
- Remove: 2D-only shaders (pixel_art is 2D-specific)

### Verifier
- No prompt changes — verifier receives full AgenticGameSpec with perspective field in spec summary, existing dimension-agnostic checks suffice, LLM infers 3D-specific issues from context

### Claude's Discretion
- Exact shader curation for base_3d (which shaders are truly 3D-compatible)
- Whether to add 3D-specific assets (toon shader, default environment .tres) to the template
- Internal code structure of `build_generator_system_prompt()` (string building approach)
- Test coverage for new perspective-dependent paths

</decisions>

<specifics>
## Specific Ideas

- 3D essentials prompt section must include: Camera3D, DirectionalLight3D/OmniLight3D, Vector3, move_and_slide() on CharacterBody3D, MeshInstance3D with built-in meshes (BoxMesh, SphereMesh, CapsuleMesh, CylinderMesh, PlaneMesh, QuadMesh), WorldEnvironment
- Display config for 3D: `window/stretch/mode="disabled"` (not `canvas_items`)
- Rendering stays `gl_compatibility` for both (WASM target)

</specifics>

<deferred>
## Deferred Ideas

- 3D-specific asset library (toon shaders, environment presets) — add if quality proves insufficient
- Verifier prompt 3D-specific checks — only if verification quality is insufficient in practice
- Isometric/2.5D as a third perspective option

</deferred>

---

*Phase: 09-add-3d-game-generation-support-to-agentic-pipeline*
*Context gathered: 2026-03-20 via PRD Express Path*
