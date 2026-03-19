# Phase 7: Agentic Pipeline - Context

**Gathered:** 2026-03-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build a new pipeline strategy ("agentic") that uses a single multi-turn LLM conversation to generate a complete game through a spec → todo-driven file generation → LLM verification → targeted fix loop. This is a new pipeline alongside `contract` and `multi_stage` — new agentic-native stages, not reusing existing contract pipeline components.

</domain>

<decisions>
## Implementation Decisions

### Agent Loop Design
- Loop runs: generate files → LLM verifier → fix flagged files → repeat until verifier passes or max iterations hit
- Exit condition: verifier reports zero errors (structured error list)
- Targeted fixes only — only regenerate files the verifier flagged, passing original file content + error context
- All intermediate state saved per iteration (numbered subdirs: iteration_1/, iteration_2/, etc.)
- Configurable context strategy: can run with full conversation history OR statelessly where each step only sees todo list / state tracker and reads files as needed

### Spec & Todo Generation
- Dedicated first conversation turn produces a rich game spec from the user prompt (similar richness to RichGameSpec but agentic-native, not reusing existing models)
- Todo list is emergent — agent decides what files to create based on the spec, not a pre-computed contract
- System prompt hints at best-practice ordering: visual assets first (skippable for now) → main .gd scripts → scene files (.tscn) and auxiliary scripts → the rest
- Ordering is hinted but autonomous — agent can deviate if it has reason to
- Filesystem-based state tracking — files are written to the game directory as they complete; the agent reads the directory to see what exists and what's remaining

### Conversation & File Generation
- Single pipeline-level conversation — one multi-turn LLM conversation for the whole game
- One file per turn — each conversation turn produces exactly one file
- File extraction via Anthropic tool_use API — define a `write_file` tool the LLM calls with filename + content
- Agent also has a `read_file` tool to inspect already-generated files (essential for stateless context mode)
- In stateless mode, agent uses read_file to inspect existing files instead of relying on conversation history

### Verifier Agent
- Separate LLM call (fresh context) — not part of the generator conversation
- LLM-only review — no static analysis; the verifier reads all generated files and the spec, produces a structured error list
- Structured output: Pydantic model with file path, error type (syntax/reference/logic/missing), description, severity
- Verifier errors fed back to generator as structured data for targeted fixes

### Scene & File Generation
- LLM generates ALL files including .tscn scenes — no deterministic scene assembly step
- System prompt includes .tscn format reference/examples so the LLM produces valid structure
- The verify/fix loop is what ensures .tscn correctness instead of programmatic assembly
- project.godot patches also LLM-generated

### Claude's Discretion
- Max iteration cap (suggested ~3 but Claude picks)
- Which Claude model(s) for generator vs verifier
- Pipeline registry name and API selection mechanism
- SSE progress event design (per-file, per-iteration, verifier results)
- Error handling when max iterations reached without passing
- Exact tool definitions for write_file and read_file
- How the filesystem-based state tracker is structured (TODO.md format, directory conventions)

</decisions>

<specifics>
## Specific Ideas

- The key difference from ContractPipeline: instead of pre-computing a full contract and generating in parallel waves, the agent builds up the game iteratively through conversation, deciding what to generate next based on what exists
- Context strategy is configurable: full conversation history (coherent but long context) vs stateless with file reading (shorter context, agent reads what it needs). This allows experimenting with which approach produces better games
- The verifier being a separate LLM call (not the same conversation) provides an independent "second opinion" — the verifier isn't biased by the generation decisions
- Best-practice file ordering hint (assets → main scripts → scenes → auxiliary) comes from observed patterns in what makes games work, but the agent can deviate

</specifics>

<deferred>
## Deferred Ideas

- Visual asset generation integration (Phase 3.1 scope — the "assets first" ordering hint anticipates this)
- Static analysis pre-check before LLM verification (could speed up the loop)
- Playwright visual feedback loop (mentioned in PROJECT.md as future pipeline strategy)
- A/B comparison tooling between agentic and contract pipeline outputs

</deferred>

---

*Phase: 07-agentic-pipeline*
*Context gathered: 2026-03-19*
