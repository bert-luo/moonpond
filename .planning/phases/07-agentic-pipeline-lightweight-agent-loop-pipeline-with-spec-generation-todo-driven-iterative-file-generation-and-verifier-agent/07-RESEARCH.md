# Phase 7: Agentic Pipeline — Research

**Researched:** 2026-03-19
**Domain:** Anthropic tool_use API, multi-turn conversation state, agentic agent loops, Pydantic structured output, async Python pipeline patterns
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Agent Loop Design**
- Loop runs: generate files → LLM verifier → fix flagged files → repeat until verifier passes or max iterations hit
- Exit condition: verifier reports zero errors (structured error list)
- Targeted fixes only — only regenerate files the verifier flagged, passing original file content + error context
- All intermediate state saved per iteration (numbered subdirs: iteration_1/, iteration_2/, etc.)
- Configurable context strategy: can run with full conversation history OR statelessly where each step only sees todo list / state tracker and reads files as needed

**Spec & Todo Generation**
- Dedicated first conversation turn produces a rich game spec from the user prompt (similar richness to RichGameSpec but agentic-native, not reusing existing models)
- Todo list is emergent — agent decides what files to create based on the spec, not a pre-computed contract
- System prompt hints at best-practice ordering: visual assets first (skippable for now) → main .gd scripts → scene files (.tscn) and auxiliary scripts → the rest
- Ordering is hinted but autonomous — agent can deviate if it has reason to
- Filesystem-based state tracking — files are written to the game directory as they complete; the agent reads the directory to see what exists and what's remaining

**Conversation & File Generation**
- Single pipeline-level conversation — one multi-turn LLM conversation for the whole game
- One file per turn — each conversation turn produces exactly one file
- File extraction via Anthropic tool_use API — define a `write_file` tool the LLM calls with filename + content
- Agent also has a `read_file` tool to inspect already-generated files (essential for stateless context mode)
- In stateless mode, agent uses read_file to inspect existing files instead of relying on conversation history

**Verifier Agent**
- Separate LLM call (fresh context) — not part of the generator conversation
- LLM-only review — no static analysis; the verifier reads all generated files and the spec, produces a structured error list
- Structured output: Pydantic model with file path, error type (syntax/reference/logic/missing), description, severity
- Verifier errors fed back to generator as structured data for targeted fixes

**Scene & File Generation**
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

### Deferred Ideas (OUT OF SCOPE)
- Visual asset generation integration (Phase 3.1 scope — the "assets first" ordering hint anticipates this)
- Static analysis pre-check before LLM verification (could speed up the loop)
- Playwright visual feedback loop (mentioned in PROJECT.md as future pipeline strategy)
- A/B comparison tooling between agentic and contract pipeline outputs
</user_constraints>

---

## Summary

Phase 7 introduces a new pipeline strategy — `AgenticPipeline` — that lives at `pipelines/agentic/` alongside the existing `contract/` and `multi_stage/` pipelines. It replaces the pre-computed contract + parallel wave pattern with a single multi-turn LLM conversation that iteratively builds a complete game. The agent calls `write_file` and `read_file` tools per turn; files are materialized to disk in real time. A separate verifier LLM then audits all files and produces a structured error list; flagged files are passed back to the generator for targeted fixes. The loop repeats up to a configurable cap.

The key design challenge is correctly managing the Anthropic Messages API multi-turn conversation state. Every tool call from the assistant and every tool result you send back must accumulate in the `messages` list in the correct alternating role sequence (`assistant` → `user`). Getting this wrong produces API errors. The codebase already uses `AsyncAnthropic` and `client.messages.create()` exclusively, so the agentic pipeline will follow exactly the same pattern — only now the message list grows over many turns instead of being single-shot.

The verifier uses a fresh `client.messages.create()` call (not connected to the generator conversation) and returns structured JSON. The project already uses the `model_validate()` / `model_dump_json()` Pydantic pattern for all structured LLM output, and that pattern works here too.

**Primary recommendation:** Implement the agentic pipeline as `pipelines/agentic/pipeline.py` following the `GamePipeline` Protocol. Use `tool_use` / `tool_result` message accumulation for the generator conversation. Use a separate `_run_verifier()` function with plain `client.messages.create()` + Pydantic parsing for the verifier.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic (AsyncAnthropic) | 0.84.0 (installed) | Multi-turn conversation + tool_use API | Already the project LLM client; supports async tool_use natively |
| pydantic (BaseModel) | installed with fastapi | Verifier structured output, AgenticSpec model | Already used for all structured LLM output across every pipeline |
| asyncio | stdlib | Async pipeline execution | Project uses asyncio throughout; pytest-anyio for tests |
| pathlib | stdlib | Intermediate iteration directories, file writes | Used in exporter and every pipeline |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| json | stdlib | Parse/serialize tool call inputs | tool_use `input` dict is plain Python dict; no extra parsing needed |
| logging | stdlib | Debug per-turn logging | Existing pipelines use `logger = logging.getLogger(__name__)` |
| re | stdlib | _slugify for game_dir name | Already present in contract/pipeline.py — reuse pattern |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual message accumulation | LangChain / OpenAI Agents SDK | Manual is what the project already does; avoids adding framework dependency |
| Pydantic for verifier output | tool_use structured output | Pydantic + JSON parse is the project convention; tool_use strict mode could work but adds complexity |

**Installation:** No new dependencies required. Everything needed is already in `backend/pyproject.toml`.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/backend/pipelines/agentic/
├── __init__.py
├── pipeline.py          # AgenticPipeline class — GamePipeline Protocol
├── spec_generator.py    # Turn 1: prompt -> AgenticGameSpec (tool_use)
├── file_generator.py    # Agent loop: multi-turn write_file / read_file calls
├── verifier.py          # Separate LLM call -> VerifierResult (Pydantic)
└── models.py            # AgenticGameSpec, VerifierError, VerifierResult
```

### Pattern 1: Multi-Turn Tool Use Message Accumulation

**What:** The Anthropic API requires that assistant tool calls and user tool results alternate correctly. Every response from the assistant with `stop_reason="tool_use"` must be appended to the messages list as an assistant turn, and the tool result must be sent back in the next user turn.

**When to use:** Every iteration of the file-generation loop.

**Message flow:**
```python
# Source: Anthropic tool_use docs (official, HIGH confidence)

messages: list[dict] = [
    {"role": "user", "content": initial_user_message}
]

while True:
    response = await client.messages.create(
        model=GENERATOR_MODEL,
        max_tokens=8192,
        system=system_prompt,
        tools=AGENT_TOOLS,
        messages=messages,
    )

    # Append assistant turn (MUST include full content list, not just text)
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason == "end_turn":
        break  # Agent decided it's done

    # Process tool calls from the response
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result_content = await _dispatch_tool(block.name, block.input, game_dir)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_content,
            })

    if not tool_results:
        break  # No tool calls — agent finished

    # Append user turn with tool results
    messages.append({"role": "user", "content": tool_results})
```

**Critical:** `response.content` is a list of blocks (TextBlock and/or ToolUseBlock). Append the entire list, not just `.content[0].text`. The API will error if an assistant turn has a `tool_use` block without a matching `tool_result` in the following user turn.

### Pattern 2: Stateless Context Mode

**What:** Instead of accumulating full conversation history, each turn is a fresh call that includes only the current todo state + a `read_file` tool. The agent reads previously written files explicitly.

**When to use:** When `context_strategy == "stateless"` (configurable).

```python
# Stateless turn: messages reset each call
messages = [
    {"role": "user", "content": _build_stateless_prompt(spec, existing_files, todo_remaining)}
]
response = await client.messages.create(
    model=GENERATOR_MODEL,
    max_tokens=8192,
    system=stateless_system_prompt,
    tools=AGENT_TOOLS,
    messages=messages,
)
```

In stateless mode, the `read_file` tool is essential — the LLM will call it to inspect already-written files before generating a dependent file.

### Pattern 3: Verifier as Independent LLM Call

**What:** The verifier gets a fresh context with all generated file contents embedded. It returns structured JSON (no tool calls needed).

**When to use:** After each generation iteration, before deciding whether to continue or exit.

```python
# Source: project convention (client.messages.create + model_validate)
verifier_prompt = _build_verifier_prompt(spec, generated_files)

response = await client.messages.create(
    model=VERIFIER_MODEL,
    max_tokens=4096,
    system=VERIFIER_SYSTEM_PROMPT,
    messages=[{"role": "user", "content": verifier_prompt}],
)

raw = response.content[0].text.strip()
result = VerifierResult.model_validate(json.loads(raw))
```

### Pattern 4: Iteration Directory Layout

```
games/<game-slug>_<timestamp>/
├── intermediate/
│   ├── 1_agentic_spec.json
│   ├── iteration_1/
│   │   ├── files/          # All files written in this iteration
│   │   └── verifier.json   # VerifierResult from this iteration
│   ├── iteration_2/
│   │   ├── files/          # Only the files regenerated in this iteration
│   │   └── verifier.json
│   └── final_result.json
└── project/                # Final assembled project (merged from all iterations)
└── export/                 # WASM output
```

### Anti-Patterns to Avoid

- **Sending only `response.content[0].text` as the assistant message:** The message must be the full `response.content` list to include ToolUseBlock entries alongside any TextBlock. Missing ToolUseBlocks break the conversation contract.
- **Forgetting `tool_use_id` in tool_result:** Every `tool_result` block must include the `tool_use_id` matching the corresponding `tool_use` block. Mismatch produces a 400 error from the API.
- **Verifying before files are on disk:** The verifier reads file contents you pass in the prompt; the generator writes files to disk. Ensure the iteration's file dict is complete before calling the verifier.
- **Unbounded file generation loop:** The agent might call `write_file` indefinitely. Enforce an iteration-level max turn count (e.g., 30 turns per generation iteration) in addition to the outer verify/fix iteration cap.
- **Mixing stateful and stateless context in the same conversation:** Pick one strategy per pipeline run; mixing them produces incoherent message history.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured verifier output | Custom regex extraction | Pydantic `model_validate(json.loads(...))` | Project convention; already proven in all pipelines |
| Async LLM calls | Thread pool / requests | `AsyncAnthropic.messages.create()` | Already in the project; proper async event loop integration |
| File export / template copy | Custom copy logic | `run_exporter()` from `pipelines/exporter.py` | Shared exporter already handles copytree + headless export |
| Game directory naming | New slugify | `_slugify()` from contract/pipeline.py | Copy the same local helper pattern |
| SSE progress events | Custom event format | `ProgressEvent` from `pipelines/base.py` | The protocol requires `EmitFn`; existing event types cover all cases |

**Key insight:** The exporter, SSE events, and pipeline registration are fully reusable. The agentic pipeline only needs to implement the generation conversation loop and verifier — it hands off to `run_exporter()` exactly like `ContractPipeline` does.

---

## Common Pitfalls

### Pitfall 1: Tool Result Role Confusion

**What goes wrong:** Developer sends `tool_result` as a top-level `assistant` message instead of inside a `user` message, or sends it without wrapping it in a content array.

**Why it happens:** The Messages API has an unusual requirement: `tool_result` content blocks go inside a **user** message, not an assistant message. This is counterintuitive.

**How to avoid:** Always structure tool results as:
```python
messages.append({
    "role": "user",
    "content": [
        {"type": "tool_result", "tool_use_id": block.id, "content": result_string}
    ]
})
```

**Warning signs:** `400 Bad Request` from the Anthropic API mentioning "tool_result" or "alternating roles."

### Pitfall 2: Context Window Exhaustion in Full History Mode

**What goes wrong:** With one file per turn and full conversation history, a game with 10 files accumulates 20+ turns of messages. Each file may be 100-300 lines. After 8-10 files the context fills, causing truncation or refusal.

**Why it happens:** Full history mode preserves every generated file as message content. Files compound quickly.

**How to avoid:** Set a per-turn `max_tokens` budget, monitor `response.usage.input_tokens` and warn/switch to stateless mode if approaching limit. `claude-sonnet-4-6` has a 200K token context window (HIGH confidence from project usage), so for typical games (5-10 files) this is not likely to be a problem, but it should be tracked.

**Warning signs:** `stop_reason == "max_tokens"` before the agent calls `write_file`.

### Pitfall 3: Verifier Hallucinating Non-Errors

**What goes wrong:** The verifier reports errors on correctly written files, causing the fix loop to re-generate working files and introduce new bugs.

**Why it happens:** LLM verifiers err toward false positives, especially for GDScript syntax they haven't seen much training data for.

**How to avoid:** Include explicit instructions in the verifier system prompt: "Only report errors you are confident about. A file that appears syntactically complete should not be flagged unless a specific reference is provably missing." Use severity levels (`critical` / `warning`) and only trigger regeneration for `critical` severity items by default.

**Warning signs:** Iteration count reaches max without progress; the same files are re-generated every iteration.

### Pitfall 4: Partial Write on Tool Call Failure

**What goes wrong:** A `write_file` tool call is dispatched but the Python file write fails (permissions, bad path). The agent believes the file was written and moves on. The missing file causes export failure or verifier panic.

**Why it happens:** Tool dispatch errors are returned as `is_error: true` in the tool_result, but if the error is swallowed or mishandled, the agent gets an empty result and assumes success.

**How to avoid:** On `write_file` failure, return a `tool_result` with `is_error=True` and the error message. The agent will see the error and retry. Log all write failures.

### Pitfall 5: Max Iterations Reached Without Full Game

**What goes wrong:** The loop exits at max iterations but only 3 of 8 expected files exist. The exporter runs on a partial project and either fails or exports a broken game.

**Why it happens:** The verifier is strict, or the generator keeps rewriting the same files on each fix iteration.

**How to avoid:** At max iterations, log a warning and proceed to export with whatever files exist (same graceful-degradation approach as `ContractPipeline` exceptions). Emit a `ProgressEvent` indicating partial completion. Raise a non-fatal error that surfaces in the SSE stream rather than a hard crash.

---

## Code Examples

Verified patterns from official sources and project conventions:

### write_file Tool Definition

```python
# Source: Anthropic tool_use API spec (verified against ToolParam TypedDict in SDK 0.84.0)
WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": (
        "Write a complete file to the game project. "
        "Call this exactly once per turn with one complete file. "
        "filename must be a bare filename (e.g. 'player.gd', 'Main.tscn') "
        "with no directory prefix."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Filename only, no path. E.g. 'player.gd' or 'Main.tscn'.",
            },
            "content": {
                "type": "string",
                "description": "Complete file content as a string.",
            },
        },
        "required": ["filename", "content"],
    },
}
```

### read_file Tool Definition

```python
# Source: project design decision in 07-CONTEXT.md
READ_FILE_TOOL = {
    "name": "read_file",
    "description": (
        "Read the current content of a file already written to the game project. "
        "Use this in stateless mode to inspect previously written files before "
        "generating a file that depends on them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Filename to read (bare filename, no path).",
            },
        },
        "required": ["filename"],
    },
}
```

### Tool Dispatch Function

```python
# Source: project convention + Anthropic tool_use docs
async def _dispatch_tool(
    tool_name: str,
    tool_input: dict,
    game_dir: Path,
    generated_files: dict[str, str],
) -> str:
    """Execute a tool call and return the result string for tool_result."""
    if tool_name == "write_file":
        filename = tool_input["filename"]
        content = tool_input["content"]
        try:
            (game_dir / filename).write_text(content)
            generated_files[filename] = content
            return f"OK: wrote {filename} ({len(content)} chars)"
        except Exception as e:
            return f"ERROR: {e}"  # Return as is_error=False so LLM sees the message

    elif tool_name == "read_file":
        filename = tool_input["filename"]
        if filename in generated_files:
            return generated_files[filename]
        path = game_dir / filename
        if path.exists():
            return path.read_text()
        return f"ERROR: file not found: {filename}"

    else:
        return f"ERROR: unknown tool {tool_name}"
```

### VerifierError and VerifierResult Models

```python
# Source: project CONTEXT.md decisions + Pydantic project convention
from typing import Literal
from pydantic import BaseModel


class VerifierError(BaseModel):
    file_path: str
    error_type: Literal["syntax", "reference", "logic", "missing"]
    description: str
    severity: Literal["critical", "warning"]


class VerifierResult(BaseModel):
    errors: list[VerifierError]
    summary: str

    @property
    def has_critical_errors(self) -> bool:
        return any(e.severity == "critical" for e in self.errors)
```

### AgenticPipeline Skeleton

```python
# Source: project GamePipeline Protocol (pipelines/base.py)
class AgenticPipeline:
    """Agentic pipeline — single multi-turn conversation with verify/fix loop."""

    MAX_ITERATIONS = 3         # Claude's discretion pick
    MAX_TURNS_PER_ITERATION = 30  # guard against unbounded tool calls

    def __init__(self) -> None:
        self._client = AsyncAnthropic()

    async def generate(
        self,
        prompt: str,
        job_id: str,
        emit: EmitFn,
        *,
        save_intermediate: bool = True,
    ) -> GameResult:
        ...
```

### Multi-Turn Loop with Tool Accumulation

```python
# Source: Anthropic tool_use docs (official)
messages: list[dict] = [{"role": "user", "content": initial_prompt}]
turn_count = 0

while turn_count < self.MAX_TURNS_PER_ITERATION:
    response = await self._client.messages.create(
        model=GENERATOR_MODEL,
        max_tokens=8192,
        system=system_prompt,
        tools=[WRITE_FILE_TOOL, READ_FILE_TOOL],
        messages=messages,
    )
    turn_count += 1

    # Accumulate assistant turn — full content list, not just text
    messages.append({"role": "assistant", "content": response.content})

    if response.stop_reason == "end_turn":
        break  # Agent signalled completion

    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result = await _dispatch_tool(block.name, block.input, game_dir, generated_files)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

    if not tool_results:
        break  # No tool calls despite tool_use stop_reason — defensive exit

    messages.append({"role": "user", "content": tool_results})
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential single-shot file generation | Multi-turn tool_use conversation | Anthropic tool_use stable since ~2024 | Agent can reference prior output and self-correct during generation |
| Pre-computed contract + parallel waves | Emergent todo list from spec | Phase 7 (this phase) | Simpler planning step; more flexible file set |
| Programmatic scene assembly (SceneAssembler) | LLM generates all .tscn directly | Phase 7 (this phase) | Verify/fix loop replaces deterministic assembly |
| Separate wiring generator | Embedded in single conversation | Phase 7 (this phase) | Fewer LLM calls for wiring |

**Deprecated/outdated for this pipeline:**
- `SceneAssembler`: not used in agentic pipeline. LLM generates .tscn directly.
- Contract/NodeContract models: not reused. AgenticGameSpec is agentic-native.
- Parallel wave scheduling: replaced by sequential per-turn file generation.

---

## Open Questions

1. **Context strategy default**
   - What we know: Full history is coherent but grows with every file; stateless is cheaper but requires the LLM to read files explicitly.
   - What's unclear: Which produces better game quality in practice.
   - Recommendation: Default to `"full_history"` for the initial implementation; add `context_strategy` parameter to the pipeline with `"stateless"` as an option. Can be toggled via the registry or request body.

2. **Spec generation turn: text response or tool_use?**
   - What we know: The spec is the first conversation turn, producing a rich game spec.
   - What's unclear: Whether to define a `produce_spec` tool or just ask for plain JSON text response (like the existing spec_expander stage).
   - Recommendation: Use plain text JSON response for spec generation (follow existing `spec_expander.py` pattern with `json.loads` + `model_validate`). Keep tool_use exclusively for file generation turns. This avoids an extra tool call round-trip.

3. **How does the agent know when to call `end_turn` (stop_reason) vs keep writing?**
   - What we know: `end_turn` happens when the LLM produces a text response without calling a tool. In the agentic loop, the LLM should call `write_file` repeatedly until all files are done, then produce a text turn to signal completion.
   - What's unclear: Whether explicit "I am done writing files" instruction in the system prompt is sufficient, or whether a `declare_done` tool is clearer.
   - Recommendation: Use a `declare_done` tool that takes a `summary` string. This gives the LLM a clear mechanism to signal completion and provides a natural summary to emit as an SSE event. Alternatively, monitor when `stop_reason == "end_turn"` without any tool call — the LLM naturally does this when it has nothing left to call.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest with pytest-anyio 0.x |
| Config file | `backend/pyproject.toml` (`asyncio_mode = "auto"`) |
| Quick run command | `cd backend && uv run pytest backend/tests/test_agentic_pipeline.py -x` |
| Full suite command | `cd backend && uv run pytest backend/tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGNT-01 | AgenticPipeline registered as "agentic" in registry | unit | `pytest backend/tests/test_registry.py -x` | ✅ (extend existing) |
| AGNT-02 | write_file tool materializes files to disk | unit | `pytest backend/tests/test_agentic_pipeline.py::test_write_file_dispatch -x` | ❌ Wave 0 |
| AGNT-03 | read_file tool returns existing file content | unit | `pytest backend/tests/test_agentic_pipeline.py::test_read_file_dispatch -x` | ❌ Wave 0 |
| AGNT-04 | Multi-turn message accumulation preserves correct role alternation | unit | `pytest backend/tests/test_agentic_pipeline.py::test_message_accumulation -x` | ❌ Wave 0 |
| AGNT-05 | VerifierResult Pydantic model validates correct JSON | unit | `pytest backend/tests/test_agentic_models.py::test_verifier_result -x` | ❌ Wave 0 |
| AGNT-06 | VerifierResult.has_critical_errors correct | unit | `pytest backend/tests/test_agentic_models.py::test_has_critical_errors -x` | ❌ Wave 0 |
| AGNT-07 | Max iterations exits loop even without verifier pass | unit | `pytest backend/tests/test_agentic_pipeline.py::test_max_iterations_exit -x` | ❌ Wave 0 |
| AGNT-08 | AgenticPipeline.generate() satisfies GamePipeline Protocol | unit | `pytest backend/tests/test_registry.py -x` | ❌ Wave 0 |
| AGNT-09 | Intermediate directories created per iteration | unit | `pytest backend/tests/test_agentic_pipeline.py::test_iteration_dirs -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && uv run pytest backend/tests/test_agentic_models.py backend/tests/test_agentic_pipeline.py -x`
- **Per wave merge:** `cd backend && uv run pytest backend/tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_agentic_pipeline.py` — covers AGNT-02, AGNT-03, AGNT-04, AGNT-07, AGNT-08, AGNT-09
- [ ] `backend/tests/test_agentic_models.py` — covers AGNT-05, AGNT-06
- [ ] Extend `backend/tests/test_registry.py` with `test_agentic_pipeline_in_registry` — covers AGNT-01

All tests must mock `AsyncAnthropic.messages.create` using `AsyncMock` (following the project pattern from `test_contract_generator.py` and `test_multi_stage_pipeline.py`). Do not make real LLM calls in tests.

---

## Sources

### Primary (HIGH confidence)
- Anthropic Python SDK 0.84.0 installed at `backend/.venv/lib/python3.12/site-packages/anthropic/` — `ToolParam`, `ToolUseBlock`, `ToolResultBlockParam` TypedDicts verified from source
- `backend/backend/pipelines/base.py` — `GamePipeline` Protocol, `ProgressEvent`, `GameResult`, `EmitFn`
- `backend/backend/pipelines/contract/pipeline.py` — reference implementation pattern for pipeline structure
- `backend/backend/pipelines/exporter.py` — `run_exporter()` reuse confirmed
- `backend/backend/pipelines/registry.py` — registration pattern
- `backend/backend/tests/test_contract_generator.py` — `AsyncMock` test pattern for LLM calls

### Secondary (MEDIUM confidence)
- Anthropic official tool_use docs (https://platform.claude.com/docs/en/docs/build-with-claude/tool-use/overview) — multi-turn message accumulation pattern, tool_result structure, stop_reason values confirmed
- `07-CONTEXT.md` — all locked decisions, discretion areas, and deferred items

### Tertiary (LOW confidence)
- Context window size for `claude-sonnet-4-6` (200K tokens) — stated from Claude's knowledge, not verified against a live API spec. Unlikely to matter for typical 5-10 file games but should be monitored.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in the project, versions confirmed from installed SDK
- Architecture: HIGH — Anthropic tool_use pattern verified from SDK source + official docs; message accumulation pattern is a fixed API contract
- Pitfalls: HIGH for tool_result role confusion (verified against API contract); MEDIUM for context window exhaustion (size estimate LOW confidence but failure mode is well understood)

**Research date:** 2026-03-19
**Valid until:** 2026-04-19 (Anthropic SDK stable; tool_use API is stable)
