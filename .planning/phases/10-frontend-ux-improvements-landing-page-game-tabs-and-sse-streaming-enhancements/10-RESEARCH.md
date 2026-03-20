# Phase 10: Frontend UX Improvements — Research

**Researched:** 2026-03-20
**Domain:** React/Next.js 15 frontend — layout, state management, SSE event handling
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Landing Page**
- Display a landing page when user has 0 built games this session
- Front-center prompt box with translucent prompt examples
- Awe-inspiring moon/water-reflection graphic background
- Visual reference: similar to ml-demo.png but with fewer controls (simpler system)

**Game Tabs**
- Top of chat column contains tabs with game titles (or default like game_{idx})
- Plus button to create a new game instead of continuing current game edit
- Clicking a tab switches the right game panel to that game's output

**SSE Streaming Enhancements**
- Display game title and description after spec expander stage completes in agentic pipeline
- Display file name and size when file_generator.py finishes writing a file
- Display game controls at end of chat box after generation completes

### Claude's Discretion
- Tab UI component library choice (existing project patterns vs new)
- Landing page animation/transition approach
- State management for multi-game sessions (how games are stored client-side)
- SSE event type naming and payload structure for new events
- How game controls are extracted and rendered in chat

### Deferred Ideas (OUT OF SCOPE)
- Multiturn chat for incremental edits of game (future feature)
- File text streaming to show lowest-level realtime progress of file writing (future feature)
</user_constraints>

---

## Summary

This phase adds three frontend UX improvements to the existing React/Next.js 15 app. The project uses Tailwind v4 (oklch CSS variables), vitest + React Testing Library, and a useReducer-based state management pattern. The existing codebase is lean and self-contained — no UI component libraries are installed, all components are hand-crafted with Tailwind.

The three features require: (1) a conditional full-screen landing overlay when no games have been built, (2) extending `GenerationState` from tracking one game to an array of game sessions with a selected-tab index, and (3) two new SSE event types from the backend (`spec_complete` and `file_written`) plus moving the controls legend display to render in the message stream rather than only in the `done` state.

The backend already emits a `file_generated` event (type `"file_generated"`) per write_file call in `file_generator.py` with `filename` in the data field — but no file size. The spec generator does NOT currently emit a spec-complete event with title/description. Both backend gaps must be filled as part of this phase.

**Primary recommendation:** Extend the existing reducer/hook pattern. Add a `sessions` array to `GenerationState`, a `selectedSession` index, and new SSE event types. Build the landing page as a conditional overlay in `page.tsx`. No new libraries needed.

---

## Standard Stack

### Core (all already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 15.x | App router, server + client components | Project baseline |
| React | 19.x | Component model, hooks | Project baseline |
| Tailwind CSS | 4.x | Utility CSS, oklch theme vars | Project baseline — @import syntax, @theme inline |
| TypeScript | 5.x | Type safety | Project baseline |

### Testing (already installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| vitest | 4.x | Test runner | All tests |
| @testing-library/react | 16.x | Component rendering | Component tests |
| @testing-library/jest-dom | 6.x | DOM matchers | Assertion helpers |
| jsdom | 25.x | DOM environment | CJS compat with vitest 4.x on Node 22 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-crafted tabs | Headless UI / Radix Tabs | No extra deps, project already avoids lib components — keep consistent |
| CSS transitions | Framer Motion | No animation lib in project; use CSS transitions and Tailwind animate- classes |
| Zustand/Jotai | useReducer + context | Project pattern is useReducer; extend it rather than introduce new state lib |

**Installation:** No new dependencies required.

---

## Architecture Patterns

### Existing Project Structure
```
frontend/
├── app/
│   ├── components/
│   │   ├── ChatPanel.tsx      # left column — messages, input
│   │   └── GameViewer.tsx     # right column — game iframe/skeleton
│   ├── globals.css            # Tailwind v4 @import + CSS vars
│   ├── layout.tsx             # RootLayout
│   └── page.tsx               # Home — orchestrator, useReducer
├── hooks/
│   └── useGeneration.ts       # SSE client hook
├── types/
│   └── generation.ts          # State, actions, reducer
└── __tests__/
    ├── ChatPanel.test.tsx
    ├── GameViewer.test.tsx
    ├── generation.test.ts
    └── useGeneration.test.ts
```

### Recommended Changes to Project Structure
```
frontend/
├── app/
│   ├── components/
│   │   ├── ChatPanel.tsx       # extended: tabs, spec info, file events
│   │   ├── GameViewer.tsx      # unchanged (receives session, not global state)
│   │   ├── GameTabs.tsx        # NEW: tab bar with plus button
│   │   └── LandingPage.tsx     # NEW: full-screen landing overlay
│   ├── globals.css             # may add CSS vars for landing
│   ├── layout.tsx              # unchanged
│   └── page.tsx               # conditional landing vs app layout
├── hooks/
│   └── useGeneration.ts       # extended: session-aware dispatch
├── types/
│   └── generation.ts          # extended: GameSession, multi-session state
└── __tests__/
    ├── ChatPanel.test.tsx
    ├── GameTabs.test.tsx       # NEW
    ├── LandingPage.test.tsx    # NEW
    ├── GameViewer.test.tsx
    ├── generation.test.ts      # extended for new actions/state shape
    └── useGeneration.test.ts
```

### Pattern 1: Multi-Session State via Extended Reducer

**What:** Replace the single-game `GenerationState` with a `sessions` array plus `activeSessionIdx`. Each session is its own `GameSession` object with the same fields as current `GenerationState`.

**When to use:** When the app needs to support multiple independent game generations in parallel tabs.

**Example:**
```typescript
// types/generation.ts

export interface GameSession {
  id: string;
  title: string | null;          // filled from spec_complete SSE event
  description: string | null;   // filled from spec_complete SSE event
  status: Status;
  messages: ChatMessage[];
  gameUrl: string | null;
  controls: ControlMapping[];
  errorMessage: string | null;
}

export interface AppState {
  sessions: GameSession[];
  activeSessionIdx: number;
}

// Session is "built" if status === 'done' or status === 'error' (at least one attempt)
// Landing page shows when sessions.filter(s => s.status === 'done').length === 0
```

**New actions:**
```typescript
export type GenerationAction =
  | { type: 'NEW_SESSION' }                    // creates a new session, sets activeSessionIdx
  | { type: 'SELECT_SESSION'; idx: number }    // switch active tab
  | { type: 'SUBMIT' }                         // start generation on activeSessionIdx
  | { type: 'SSE_SPEC_COMPLETE'; title: string; description: string }  // new
  | { type: 'SSE_FILE_WRITTEN'; filename: string; bytes: number }      // new
  | { type: 'SSE_STAGE'; message: string }
  | { type: 'SSE_DONE'; gameUrl: string; controls: ControlMapping[] }
  | { type: 'SSE_ERROR'; message: string }
  | { type: 'RESET' };
```

### Pattern 2: Landing Page as Conditional Overlay

**What:** In `page.tsx`, check if any session has `status === 'done'`. If none, render `<LandingPage>`. LandingPage includes the prompt input and covers the entire viewport.

**When to use:** Session count with done status === 0.

**Example:**
```typescript
// page.tsx
const hasBuiltGame = state.sessions.some(s => s.status === 'done');

return (
  <main className="flex h-screen relative">
    {!hasBuiltGame && (
      <LandingPage onSubmit={handleSubmit} isGenerating={activeSession.status === 'generating'} />
    )}
    {/* Main app layout — always mounted but hidden behind landing */}
    <div className={!hasBuiltGame ? 'hidden' : 'flex w-full h-full'}>
      ...chat panel + game viewer...
    </div>
  </main>
);
```

Alternative: unmount main layout entirely when no games built. Simpler but loses any ongoing generation state if user navigates away. The `hidden` approach keeps EventSource alive.

### Pattern 3: Moon/Water Landing Page Background

**What:** CSS-only moon/water reflection using radial gradients + CSS animation. No canvas, no WebGL, no external libraries.

**When to use:** Awe-inspiring visual background that matches the dark color scheme (`oklch(0.09 0.01 260)` background).

**Example:**
```css
/* In globals.css */
@keyframes water-shimmer {
  0%, 100% { transform: scaleX(1) translateY(0); opacity: 0.6; }
  50%       { transform: scaleX(1.02) translateY(-4px); opacity: 0.8; }
}

.landing-bg {
  background:
    radial-gradient(ellipse 200px 200px at 50% 25%, oklch(0.85 0.05 265 / 0.9) 0%, transparent 70%),
    radial-gradient(ellipse 300px 80px at 50% 60%, oklch(0.72 0.18 265 / 0.3) 0%, transparent 70%),
    oklch(0.09 0.01 260);
}
```

The moon is a radial gradient at ~25% vertical. The water reflection is a blurred, animated ellipse below center. The existing `--color-accent` (oklch 0.72 0.18 265) and `--color-glow` work naturally for the moonlit water look.

### Pattern 4: Game Tabs Component

**What:** Horizontal tab strip above the chat messages area in `ChatPanel`. Tabs = sessions. Each tab shows `session.title ?? 'Game ${idx + 1}'`. Active tab highlighted with accent border. Plus button appends a new empty session.

**Example:**
```tsx
// app/components/GameTabs.tsx
interface GameTabsProps {
  sessions: GameSession[];
  activeIdx: number;
  onSelect: (idx: number) => void;
  onNew: () => void;
}

export function GameTabs({ sessions, activeIdx, onSelect, onNew }: GameTabsProps) {
  return (
    <div className="flex items-center gap-1 px-2 pt-2 border-b border-[var(--color-border)] overflow-x-auto">
      {sessions.map((session, idx) => (
        <button
          key={session.id}
          onClick={() => onSelect(idx)}
          className={`px-3 py-1.5 text-xs rounded-t-md whitespace-nowrap transition-colors ${
            idx === activeIdx
              ? 'bg-[var(--color-surface)] border border-[var(--color-accent)] text-[var(--color-text)]'
              : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
          }`}
        >
          {session.title ?? `Game ${idx + 1}`}
        </button>
      ))}
      <button
        onClick={onNew}
        className="ml-1 px-2 py-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] text-sm rounded transition-colors"
        title="New game"
      >
        +
      </button>
    </div>
  );
}
```

### Pattern 5: Controls Display in Chat Stream

**Context:** Currently the controls legend renders after `status === 'done'` outside the message list. The CONTEXT.md says to display controls "at end of chat box after generation completes." This means rendering controls as a special message type in the messages array OR as a fixed element at the bottom of the scrollable area.

**Recommendation:** Add a `'controls'` message type to `ChatMessage`. When the `done` SSE event arrives with controls, dispatch both `SSE_DONE` (which appends a complete message) and insert a controls message into the session. This keeps the chat history linear and scrollable. Remove the separate `state.controls` conditional render from outside the message loop.

```typescript
export interface ChatMessage {
  id: string;
  type: 'stage' | 'complete' | 'error' | 'spec_info' | 'file_written' | 'controls';
  text: string;
  data?: Record<string, unknown>;  // for spec_info: {title, description}; for controls: {controls: ControlMapping[]}
}
```

### Anti-Patterns to Avoid

- **Don't persist sessions to localStorage yet:** This phase is about in-session multi-game support only. Persistence is a v2 feature.
- **Don't use a React key that changes on session switch:** Keep the `<GameViewer>` mounted and pass the active session's gameUrl — switching sessions should not remount the iframe if the same URL is showing.
- **Don't introduce a global context for session state:** The current pattern is `useReducer` in `page.tsx`, prop-drilled down. Keep it that way — the tree is shallow (2 levels).
- **Don't add animation libraries:** The project has no animation library. Use `transition-*` Tailwind utilities and CSS `@keyframes` in `globals.css`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tab overflow scrolling | Custom JS scroll tracking | `overflow-x-auto` on the tab bar div | CSS handles scroll; no JS needed |
| Unique session IDs | Custom ID generator | `crypto.randomUUID()` | Already used for message IDs; same pattern |
| CSS variables in JS | Inline style strings | Access via `var(--color-*)` classes | Tailwind v4 already exposes them as CSS vars |
| SSE event buffering | Custom re-connect logic | Existing `EventSource` + error handler | `useGeneration.ts` already handles reconnect/error |

**Key insight:** The project deliberately avoids component libraries. Tabs, modals, and overlays are all achievable with 30-50 lines of Tailwind — introducing Radix or Headless UI would be inconsistent with the project's lightweight approach.

---

## Common Pitfalls

### Pitfall 1: Session Dispatch Targeting the Wrong Session

**What goes wrong:** When a new session is created and generation starts, if SSE events use closure-captured `activeSessionIdx` at submission time but the user switches tabs during generation, events may target the wrong session in the reducer.

**Why it happens:** The `useGeneration` hook captures `dispatch` but not the session index. Reducer actions without a `sessionId` don't know which session to update.

**How to avoid:** All SSE-dispatched actions (`SSE_STAGE`, `SSE_DONE`, `SSE_ERROR`, `SSE_SPEC_COMPLETE`, `SSE_FILE_WRITTEN`) should carry a `sessionId: string` field. The reducer matches by ID, not by current `activeSessionIdx`.

```typescript
// Action includes session identity
{ type: 'SSE_STAGE'; sessionId: string; message: string }
```

The hook captures the `sessionId` at submission time (from the new session created by `NEW_SESSION`).

**Warning signs:** Messages appearing in the wrong tab when rapidly creating new games.

### Pitfall 2: `file_generated` vs `file_written` Event Naming

**What goes wrong:** The backend already emits `type: "file_generated"` events from `file_generator.py`. The CONTEXT.md calls the desired frontend message "display file name and size when file_generator.py finishes writing a file." There is a naming mismatch between the existing backend event name (`file_generated`) and what the CONTEXT describes.

**Why it happens:** The backend event was added in a previous phase but the frontend never displayed it. Now the frontend needs to consume it, and the payload needs to include file size (currently missing — the current payload only has `{"filename": filename}`).

**How to avoid:**
1. Backend: add `"size_bytes": len(content)` to the `data` dict in `file_generator.py`'s `ProgressEvent` emission.
2. Frontend: add a `file_generated` listener in `useGeneration.ts` that dispatches `SSE_FILE_WRITTEN` with `{filename, bytes}`.

The frontend action name (`SSE_FILE_WRITTEN`) and the backend event type (`file_generated`) can differ — the hook maps one to the other.

**Warning signs:** Displaying file events but size always shows 0 or undefined.

### Pitfall 3: Spec-Complete Event Does Not Exist in Backend Yet

**What goes wrong:** The spec generator (`spec_generator.py`) currently does NOT emit a dedicated event after the spec is complete with title and description. It emits one `stage_start` event at the beginning ("Generating game specification...") and then returns the spec silently.

**Why it happens:** No prior phase needed to send spec metadata to the frontend.

**How to avoid:** Add a `spec_complete` emission at the end of `run_spec_generator()`, AFTER the LLM response is parsed and validated:

```python
# spec_generator.py — after AgenticGameSpec.model_validate(tool_block.input)
await emit(ProgressEvent(
    type="spec_complete",
    message=f"Game spec: {result.title}",
    data={"title": result.title, "description": result.scene_description},
))
```

Frontend registers a `spec_complete` listener and dispatches `SSE_SPEC_COMPLETE`.

**Warning signs:** Title/description never appear in chat.

### Pitfall 4: Controls Still Rendered Outside Message Loop After Refactor

**What goes wrong:** `ChatPanel.tsx` currently renders the controls legend conditionally based on `state.status === 'done'` OUTSIDE the message map loop. After adding controls as a `ChatMessage` type, if both render paths remain, controls appear twice.

**How to avoid:** Remove the existing controls conditional block from `ChatPanel` and rely entirely on the `controls` message type in the message list. The reducer's `SSE_DONE` case should add a controls-type message.

### Pitfall 5: Landing Page Hides In-Progress Generation on First Game

**What goes wrong:** If the condition is `sessions.filter(s => s.status === 'done').length === 0`, the landing page stays visible during the first game's generation (status is `'generating'`, not `'done'`). Users submitting from the landing page would see no feedback.

**How to avoid:** The condition for hiding the landing page should be: any session has status `'generating'`, `'done'`, or `'error'`. Landing page only shows when ALL sessions are `'idle'` (i.e., no game has ever been started this session).

```typescript
const showLanding = state.sessions.every(s => s.status === 'idle');
```

---

## Code Examples

### Backend: Adding spec_complete event

```python
# backend/backend/pipelines/agentic/spec_generator.py
# After model_validate() call:
result = AgenticGameSpec.model_validate(tool_block.input)

await emit(ProgressEvent(
    type="spec_complete",
    message=f"Spec: {result.title}",
    data={
        "title": result.title,
        "description": result.scene_description,
        "genre": result.genre,
    },
))
return result
```

### Backend: Adding size_bytes to file_generated event

```python
# backend/backend/pipelines/agentic/file_generator.py
# In the write_file branch of _dispatch_tool:
(game_dir / filename).write_text(content)
generated_files[filename] = content
# size for SSE event
return f"OK: wrote {filename} ({len(content)} chars)"

# In the emit call for write_file in run_file_generation:
if block.name == "write_file":
    filename = block.input.get("filename", "unknown")
    content = block.input.get("content", "")
    await emit(
        ProgressEvent(
            type="file_generated",
            message=f"Wrote {filename}",
            data={"filename": filename, "size_bytes": len(content.encode("utf-8"))},
        )
    )
```

Note: `len(content)` counts characters, `len(content.encode("utf-8"))` counts bytes. Use bytes for display accuracy.

### Frontend: New SSE event listeners in useGeneration.ts

```typescript
// spec_complete event
es.addEventListener('spec_complete', (e: Event) => {
  const me = e as MessageEvent;
  try {
    const event = JSON.parse(me.data);
    const d = event.data ?? {};
    dispatch({
      type: 'SSE_SPEC_COMPLETE',
      sessionId,
      title: d.title ?? '',
      description: d.description ?? '',
    });
  } catch { /* ignore */ }
});

// file_generated event
es.addEventListener('file_generated', (e: Event) => {
  const me = e as MessageEvent;
  try {
    const event = JSON.parse(me.data);
    const d = event.data ?? {};
    dispatch({
      type: 'SSE_FILE_WRITTEN',
      sessionId,
      filename: d.filename ?? 'unknown',
      bytes: d.size_bytes ?? 0,
    });
  } catch { /* ignore */ }
});
```

### Frontend: Multi-session state shape

```typescript
// types/generation.ts

export interface GameSession {
  id: string;
  title: string | null;
  description: string | null;
  status: Status;
  messages: ChatMessage[];
  gameUrl: string | null;
  controls: ControlMapping[];
  errorMessage: string | null;
}

export interface AppState {
  sessions: GameSession[];
  activeSessionIdx: number;
}

export const initialSession = (): GameSession => ({
  id: crypto.randomUUID(),
  title: null,
  description: null,
  status: 'idle',
  messages: [],
  gameUrl: null,
  controls: [],
  errorMessage: null,
});

export const initialState: AppState = {
  sessions: [initialSession()],
  activeSessionIdx: 0,
};
```

### Frontend: Reducer helper for updating active session

```typescript
// Helper to update a session by ID
function updateSession(
  sessions: GameSession[],
  id: string,
  update: Partial<GameSession>
): GameSession[] {
  return sessions.map(s => s.id === id ? { ...s, ...update } : s);
}
```

### Frontend: ChatMessage with new types

```typescript
export interface ChatMessage {
  id: string;
  type: 'stage' | 'complete' | 'error' | 'spec_info' | 'file_written' | 'controls';
  text: string;
  data?: Record<string, unknown>;
}
```

### Frontend: Controls message rendering in ChatPanel

```tsx
// In the messages.map():
{msg.type === 'controls' && msg.data?.controls && (
  <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg p-3 mt-2">
    <h3 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">
      Controls
    </h3>
    <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
      {(msg.data.controls as ControlMapping[]).map((ctrl, i) => (
        <div key={i} className="contents text-sm">
          <kbd className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded px-1.5 py-0.5 text-xs font-mono text-[var(--color-text)]">
            {ctrl.key}
          </kbd>
          <span className="text-[var(--color-text-muted)]">{ctrl.action}</span>
        </div>
      ))}
    </div>
  </div>
)}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single game state | Multi-session state array | Phase 10 | All state reads need `sessions[activeSessionIdx]` instead of root-level fields |
| Controls rendered as separate block | Controls as `ChatMessage` type | Phase 10 | Linear chat history, scrollable, no separate DOM section |
| Landing page = empty idle state text | Full-screen landing overlay | Phase 10 | `page.tsx` conditionally renders LandingPage before showing main layout |

**Deprecated/outdated:**
- `initialState: GenerationState` flat object: replaced by `AppState` with sessions array
- `state.controls` top-level field: controls now stored per-session and rendered in message stream
- Separate controls legend render block in `ChatPanel.tsx`: removed in favor of `controls` message type

---

## Open Questions

1. **Tab title source for in-progress generation**
   - What we know: `session.title` comes from `spec_complete` SSE event, which fires after spec generation (~3-5s into a generation)
   - What's unclear: Should the tab show "Game 1" until title arrives, then animate/update to the real title?
   - Recommendation: Start with `'Game ${idx + 1}'` fallback. When `SSE_SPEC_COMPLETE` updates `session.title`, React re-renders the tab automatically — no special handling needed.

2. **Plus button behavior when a generation is in progress**
   - What we know: Creating a new session while the current one is generating is allowed by the state model
   - What's unclear: Should the plus button be disabled during generation, or is creating a new session while one is in progress acceptable?
   - Recommendation: Allow it. The SSE hook uses `sessionId` to target events to the correct session. Multiple concurrent EventSources are supported by browsers.

3. **Landing page prompt box positioning on mobile**
   - What we know: The current app is desktop-only (fixed 420px sidebar)
   - What's unclear: Does the landing page need mobile responsiveness?
   - Recommendation: Keep desktop-only. The app layout has no mobile breakpoints today; don't introduce them here.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | vitest 4.x + React Testing Library 16.x |
| Config file | `frontend/vitest.config.mts` |
| Quick run command | `cd /Users/albertluo/other/moonpond/frontend && npm test` |
| Full suite command | `cd /Users/albertluo/other/moonpond/frontend && npm test` |

### Phase Requirements → Test Map

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| AppState initializes with one idle session | unit | `npm test -- generation.test.ts` | ✅ (extend generation.test.ts) |
| NEW_SESSION action adds session and sets activeSessionIdx | unit | `npm test -- generation.test.ts` | ✅ (extend) |
| SELECT_SESSION action updates activeSessionIdx | unit | `npm test -- generation.test.ts` | ✅ (extend) |
| SSE_SPEC_COMPLETE targets correct session by ID | unit | `npm test -- generation.test.ts` | ✅ (extend) |
| SSE_FILE_WRITTEN appends file_written message to correct session | unit | `npm test -- generation.test.ts` | ✅ (extend) |
| SSE_DONE appends controls message and sets status=done | unit | `npm test -- generation.test.ts` | ✅ (extend) |
| GameTabs renders session titles with fallback | unit | `npm test -- GameTabs.test.tsx` | ❌ Wave 0 |
| GameTabs calls onNew when plus button clicked | unit | `npm test -- GameTabs.test.tsx` | ❌ Wave 0 |
| GameTabs calls onSelect with correct index | unit | `npm test -- GameTabs.test.tsx` | ❌ Wave 0 |
| LandingPage renders when no games built | unit | `npm test -- LandingPage.test.tsx` | ❌ Wave 0 |
| LandingPage hides when status transitions to generating | unit | `npm test -- LandingPage.test.tsx` | ❌ Wave 0 |
| ChatPanel renders spec_info message with title | unit | `npm test -- ChatPanel.test.tsx` | ✅ (extend) |
| ChatPanel renders file_written message with filename and size | unit | `npm test -- ChatPanel.test.tsx` | ✅ (extend) |
| ChatPanel renders controls message inline | unit | `npm test -- ChatPanel.test.tsx` | ✅ (extend) |

### Sampling Rate

- **Per task commit:** `cd /Users/albertluo/other/moonpond/frontend && npm test`
- **Per wave merge:** `cd /Users/albertluo/other/moonpond/frontend && npm test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `frontend/__tests__/GameTabs.test.tsx` — covers GameTabs rendering and interaction
- [ ] `frontend/__tests__/LandingPage.test.tsx` — covers landing page show/hide conditions
- [ ] `frontend/app/components/GameTabs.tsx` — new component file
- [ ] `frontend/app/components/LandingPage.tsx` — new component file

---

## Backend Changes Summary

This phase requires two backend additions alongside the frontend work:

1. **`spec_generator.py`**: Add `spec_complete` event emission after `AgenticGameSpec.model_validate()` with `title`, `description`, and `genre` in `data`.

2. **`file_generator.py`**: Add `size_bytes: len(content.encode("utf-8"))` to the existing `file_generated` event `data` dict (currently only has `filename`).

Both are small, localized additions to existing emit calls. No new backend routes, models, or pipeline stages needed.

---

## Sources

### Primary (HIGH confidence)
- Direct source read: `frontend/app/components/ChatPanel.tsx` — current component structure
- Direct source read: `frontend/app/page.tsx` — current layout pattern
- Direct source read: `frontend/types/generation.ts` — current state/action types
- Direct source read: `frontend/hooks/useGeneration.ts` — SSE client hook pattern
- Direct source read: `frontend/app/globals.css` — Tailwind v4 CSS variables
- Direct source read: `frontend/package.json` — installed dependencies and versions
- Direct source read: `backend/backend/pipelines/agentic/pipeline.py` — orchestration and emit calls
- Direct source read: `backend/backend/pipelines/agentic/spec_generator.py` — spec emit gap identified
- Direct source read: `backend/backend/pipelines/agentic/file_generator.py` — existing file_generated event, missing size_bytes
- Direct source read: `backend/backend/pipelines/base.py` — ProgressEvent model
- Direct source read: `backend/backend/main.py` — SSE stream pattern

### Secondary (MEDIUM confidence)
- `fe.md` (user's raw feature notes) — original intent for all three features
- `.planning/phases/10-*/10-CONTEXT.md` — formalized decisions from PRD Express Path

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in package.json, exact versions confirmed
- Architecture: HIGH — existing codebase read directly; patterns extrapolated from actual code
- Pitfalls: HIGH — identified by reading actual backend emit paths and frontend reducer logic
- Backend gaps: HIGH — confirmed by reading spec_generator.py and file_generator.py directly

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable stack; React/Next/Tailwind versions unlikely to shift)
