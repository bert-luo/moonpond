# Phase 5: Pipeline Optimization - Context

**Gathered:** 2026-03-17
**Status:** Ready for planning
**Source:** User discussion context (inline)

<domain>
## Phase Boundary

Build a new pipeline (parallel to the existing MultiStagePipeline) that addresses structural flaws discovered in generated game analysis. The current pipeline generates files sequentially without enforcing interface contracts, leading to wiring bugs (wrong autoloads, orphaned scripts, unconnected signals, mismatched enums). The new pipeline introduces a contract-first, dependency-aware generation strategy with parallel file generation.

</domain>

<decisions>
## Implementation Decisions

### Pipeline Architecture
- New pipeline class alongside MultiStagePipeline (not replacing it yet)
- Lives in backend/backend/pipelines/ with new stages in backend/backend/stages/
- Follows the existing GamePipeline Protocol + registry pattern

### Stage 1: Spec Expander (with reasoning)
- Takes user prompt and expands it into a full game specification
- Uses LLM reasoning to flesh out gameplay mechanics, entities, interactions
- Output: rich game spec document that downstream stages consume

### Stage 2: API Spec / Node Structure Generator
- Generates the interface contract: method signatures, signal names, group names, enum definitions, node tree structure, scene file paths
- Defines all cross-file dependencies BEFORE any code is generated
- Output: structured contract that all parallel generators must honor

### Stage 3: Parallel Node Generation (dependency-ordered)
- Generates individual .gd/.tscn files in parallel where the dependency graph allows
- Leaf nodes (platform.gd, enemy.gd, powerup.gd, projectile.gd, player.gd, background.gd) can all be generated concurrently
- Each generator receives the API contract from Stage 2 as context
- Follows dependency order: leaves first, then orchestrator scripts

### Stage 4: Wiring File Generation
- Generates Main.tscn (scene tree wiring scripts to nodes)
- Generates project.godot (autoloads, main scene, input mappings)
- Ensures all ExtResource references match actual script paths
- Connects signals to handlers
- This stage runs AFTER all individual files exist

### Stage 5: Export
- Reuse existing export logic (Godot headless WASM export)

### Claude's Discretion
- Internal data structures for the API contract format
- How to represent the dependency graph for parallel scheduling
- Error handling and self-correction within each stage
- Whether to reuse existing prompt enhancer / game designer stages or create new ones

</decisions>

<specifics>
## Specific Ideas

- The dependency graph of Godot project files is quite flat — many leaf scripts/scenes can be generated in parallel
- The key insight: files are loosely coupled by path but tightly coupled by interface contracts (method signatures, signal names, group names, enum values)
- Bugs found in analyzed game were all wiring/contract failures, not logic failures in individual files
- Contract must specify: group names ("platforms"), method signatures (init(), on_landed(), get_bounce_velocity(), die()), signal names (shoot_requested), GameManager enum + properties, scene file paths, node paths
- Background node had wrong script attached (main.gd instead of background.gd) — wiring stage must validate ExtResource assignments
- Two conflicting GameManager scripts existed — contract stage must define single authoritative version

</specifics>

<deferred>
## Deferred Ideas

- Replacing MultiStagePipeline entirely (keep both for now)
- Visual polish / shader application integration (existing visual polisher stage)
- Image generation integration (Phase 03.1)

</deferred>

---

*Phase: 05-pipeline-optimization*
*Context gathered: 2026-03-17 via user discussion*
