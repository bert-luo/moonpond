# Phase 4: Frontend Integration - Research

**Researched:** 2026-03-16
**Domain:** Next.js 15 App Router, React 19, Tailwind CSS v4, EventSource SSE, COOP/COEP iframe
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tech Stack:**
- Next.js 14+ app router with TypeScript and Tailwind CSS (per PRD)
- No additional UI libraries unless needed — keep dependencies minimal
- Backend proxy via Next.js API routes OR direct fetch to FastAPI on :8000 (CORS already configured)

**Layout & Visual Design:**
- Two-column layout: ChatPanel left, GameViewer right, both visible at 1280px
- Dark theme inspired by Moonlake AI's aesthetic — dark background, high-contrast text, subtle glow accents
- The game viewer should be the visual hero — large, prominent, with the chat panel as a supportive sidebar
- Clean, minimal chrome — the generated game should be the star, not the UI
- Loading skeleton in GameViewer should feel alive (shimmer/pulse animation, not static gray)

**Chat Panel:**
- Each SSE stage message renders as a chat bubble as it arrives
- Messages should feel conversational: "Understanding your idea...", "Designing game structure...", etc.
- On completion, controls legend (key → action) appears as a styled card in the chat
- Error messages appear inline in the chat with clear styling (not a modal/toast)
- No chat history between sessions — each generation is standalone

**Game Viewer:**
- Shows loading skeleton while pipeline runs
- On `done` event, skeleton replaced by iframe pointing to `/games/{job_id}/export/index.html`
- iframe needs COOP/COEP compatible loading (headers already configured in next.config.ts)
- Game should fill the viewer area responsively

**SSE Client:**
- Use native EventSource API (no library needed)
- Connect on prompt submit, parse JSON events, update chat state
- Handle connection drops gracefully — show reconnection message or error
- Clean up EventSource on component unmount or new generation

**Prompt Input:**
- Single text input with submit button at bottom of ChatPanel
- Disabled while generation is in progress
- Resets (clears) after game loads successfully
- Placeholder text with example prompt suggestion

**Error Handling:**
- LLM errors, export failures, timeouts → error message in ChatPanel
- Prompt input stays available for retry on error
- No automatic retry from frontend — user decides to retry

### Claude's Discretion
- Component file organization within `frontend/app/`
- Specific Tailwind color values and spacing
- Animation details for loading skeleton
- Whether to use Next.js API routes as proxy or direct fetch
- State management approach (useState vs useReducer vs context)
- Responsive behavior below 1280px (reasonable degradation is fine)

### Deferred Ideas (OUT OF SCOPE)
- Iterative chat refinement (FEAT-01, v2)
- Download project as zip (FEAT-02, v2)
- Prompt hints/suggestions for new users (FEAT-03, v2)
- Mobile responsive layout (not in v1 scope)
- Game history/gallery (requires accounts, v2+)
- Dark/light theme toggle (dark only for v1)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FE-01 | Frontend renders a two-column layout: ChatPanel on the left, GameViewer on the right | Two-column CSS grid/flex with `min-h-screen`, 1280px minimum visible per Tailwind breakpoints |
| FE-02 | User can type a prompt and submit it; frontend sends `POST /api/generate` and subscribes to `GET /api/stream/{job_id}` | POST with `fetch`, then `new EventSource(url)` — CORS configured for localhost:3000 |
| FE-03 | ChatPanel displays each incoming SSE stage message as a chat bubble as it arrives | `stage_start` events with `message` field; append to messages array on each SSE event |
| FE-04 | GameViewer shows a loading skeleton while generation is in progress | `animate-pulse` or custom shimmer keyframe on placeholder div; driven by `status === 'generating'` |
| FE-05 | On completion SSE event, GameViewer loads the game iframe automatically; skeleton replaced by live game | `done` event → set `gameUrl` state → conditionally render `<iframe>` with COOP/COEP `allow` attribute |
| FE-06 | ChatPanel renders a controls legend (key + action pairs) when the completion event includes a `controls` list | `done` event `data` field contains `controls: [{key, action}]` from `GameResult.controls` |
| FE-07 | User sees an error message in ChatPanel if generation fails (LLM error, export failure, or timeout) | `error` event type from SSE stream; backend also emits `{error: "stream timeout"}` on 120s deadline |
| FE-08 | Prompt input resets after game loads; user can submit a new prompt | Clear input and reset `status` to `idle` after `done` event is processed |
</phase_requirements>

---

## Summary

This phase builds a complete browser application on top of a fully functional backend. The existing Next.js 15 + React 19 scaffold has no components, pages, or styles — everything is built from scratch. The locked decisions in CONTEXT.md are clear and reasonable, leaving implementation details (component organization, state shape, Tailwind values) to discretion.

The primary technical challenge is the iframe/COOP/COEP interaction. The frontend serves with `Cross-Origin-Opener-Policy: same-origin` and `Cross-Origin-Embedder-Policy: require-corp` (already in `next.config.ts`). The backend's static game files at `/games/{job_id}/export/` are served by FastAPI (different origin at `:8000`). The iframe must receive the game content cross-origin, which requires the backend to serve those files with appropriate CORS/CORP headers OR the frontend must proxy game assets. This is the single highest-risk item to verify before implementation.

The SSE client pattern is straightforward: native `EventSource`, custom hook, `useReducer` for predictable state transitions. The backend emits named events (`stage_start`, `done`, `error`) with JSON `data`, all confirmed from reading the actual `main.py` source. Tailwind v4 is the current standard for Next.js 15 projects and replaces `tailwind.config.js` with a CSS-first `@import "tailwindcss"` approach.

**Primary recommendation:** Build the page as a single `"use client"` root component (`page.tsx`) with `useReducer` for generation state, two child display components (`ChatPanel`, `GameViewer`), and a single `useGeneration` hook that orchestrates fetch + EventSource lifecycle.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 15.x (already installed) | App router, dev server, CORS header config | Already scaffolded; COOP/COEP headers already set |
| React | ^19.0.0 (already installed) | UI rendering | Already installed |
| TypeScript | ^5 (already installed) | Type safety | Already installed |
| Tailwind CSS | v4 (needs install) | Utility-first CSS, dark theme | v4 is current standard for Next.js 15 new projects; no config file needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@tailwindcss/postcss` | v4 | PostCSS plugin for Tailwind v4 | Required with Tailwind v4 |
| `postcss` | latest | PostCSS pipeline | Required with Tailwind v4 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native `EventSource` | `use-next-sse` library | Library adds 0 real benefit for this use case; native is 10 lines |
| `useReducer` | multiple `useState` calls | `useReducer` is cleaner when state has 4+ interdependent fields (status, messages, gameUrl, error) |
| Direct fetch to `:8000` | Next.js API route proxy | Direct fetch is simpler (CORS already configured); proxy adds latency for no v1 benefit |
| Tailwind v4 | Tailwind v3 | v4 is standard for new Next.js 15 projects; v3 requires `tailwind.config.js` and old `@tailwind` directives |

**Installation:**
```bash
cd frontend
npm install tailwindcss @tailwindcss/postcss postcss
```

---

## Architecture Patterns

### Recommended Project Structure
```
frontend/
├── app/
│   ├── layout.tsx          # root layout with dark bg, metadata
│   ├── page.tsx            # "use client" — two-column shell + state orchestration
│   ├── globals.css         # @import "tailwindcss"; CSS variables for dark theme
│   └── components/
│       ├── ChatPanel.tsx   # message bubbles, controls legend, prompt input
│       ├── GameViewer.tsx  # loading skeleton → iframe transition
│       └── ChatMessage.tsx # single message bubble (stage, error, controls types)
├── hooks/
│   └── useGeneration.ts    # fetch + EventSource lifecycle, dispatches to reducer
├── types/
│   └── generation.ts       # GenerationState, GenerationAction, ChatMessage, SSEEvent
├── next.config.ts          # already exists — COOP/COEP headers
├── postcss.config.mjs      # Tailwind v4 PostCSS config (new file)
└── package.json            # already exists
```

### Pattern 1: useReducer for Generation State

**What:** A single reducer manages all generation state — prevents impossible states (e.g. `status: 'done'` with no `gameUrl`).

**When to use:** When 4+ state fields must update together atomically (submit clears messages AND sets status AND disables input simultaneously).

```typescript
// types/generation.ts
type Status = 'idle' | 'generating' | 'done' | 'error';

interface GenerationState {
  status: Status;
  messages: ChatMessage[];
  gameUrl: string | null;
  controls: ControlMapping[];
  errorMessage: string | null;
}

type GenerationAction =
  | { type: 'SUBMIT' }
  | { type: 'SSE_STAGE'; message: string }
  | { type: 'SSE_DONE'; gameUrl: string; controls: ControlMapping[] }
  | { type: 'SSE_ERROR'; message: string }
  | { type: 'RESET' };  // prompt reset after done

function generationReducer(state: GenerationState, action: GenerationAction): GenerationState {
  switch (action.type) {
    case 'SUBMIT':
      return { status: 'generating', messages: [], gameUrl: null, controls: [], errorMessage: null };
    case 'SSE_STAGE':
      return { ...state, messages: [...state.messages, { type: 'stage', text: action.message }] };
    case 'SSE_DONE':
      return { ...state, status: 'done', gameUrl: action.gameUrl, controls: action.controls,
               messages: [...state.messages, { type: 'complete', text: 'Your game is ready.' }] };
    case 'SSE_ERROR':
      return { ...state, status: 'error', errorMessage: action.message,
               messages: [...state.messages, { type: 'error', text: action.message }] };
    case 'RESET':
      return { ...state, status: 'idle' };  // keep gameUrl — game stays visible
    default:
      return state;
  }
}
```

### Pattern 2: useGeneration Hook (SSE Client)

**What:** Encapsulates fetch → EventSource lifecycle. Returns dispatch so page.tsx stays declarative.

**When to use:** Any time you need to decouple SSE plumbing from rendering logic.

```typescript
// hooks/useGeneration.ts
// Source: native EventSource API + backend event schema from main.py
export function useGeneration(dispatch: React.Dispatch<GenerationAction>) {
  const esRef = useRef<EventSource | null>(null);

  const submit = useCallback(async (prompt: string) => {
    // Clean up previous connection
    esRef.current?.close();
    dispatch({ type: 'SUBMIT' });

    // POST to FastAPI directly (CORS configured for localhost:3000)
    const res = await fetch('http://localhost:8000/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });
    const { job_id } = await res.json();

    // Open SSE stream
    const es = new EventSource(`http://localhost:8000/api/stream/${job_id}`);
    esRef.current = es;

    // Backend emits named events: stage_start, done, error
    // data field is JSON string: { type, message, data }
    es.addEventListener('stage_start', (e) => {
      const event = JSON.parse(e.data);
      dispatch({ type: 'SSE_STAGE', message: event.message });
    });

    es.addEventListener('done', (e) => {
      const event = JSON.parse(e.data);
      dispatch({ type: 'SSE_DONE',
        gameUrl: `http://localhost:8000/games/${event.data?.job_id ?? ''}/export/index.html`,
        controls: event.data?.controls ?? [],
      });
      es.close();
    });

    es.addEventListener('error', (e) => {
      // Backend emits named 'error' event with data
      const event = JSON.parse((e as MessageEvent).data ?? '{"message":"Unknown error"}');
      dispatch({ type: 'SSE_ERROR', message: event.message ?? event.error ?? 'Generation failed' });
      es.close();
    });

    // Network error (onerror fires on connection failure, NOT on named 'error' events)
    es.onerror = () => {
      dispatch({ type: 'SSE_ERROR', message: 'Connection lost' });
      es.close();
    };
  }, [dispatch]);

  // Cleanup on unmount
  useEffect(() => () => { esRef.current?.close(); }, []);

  return { submit };
}
```

### Pattern 3: Tailwind v4 CSS Setup

**What:** Tailwind v4 uses `@import "tailwindcss"` instead of `@tailwind` directives. Theme defined with CSS variables.

```css
/* app/globals.css */
@import "tailwindcss";

/* Dark theme CSS variables */
:root {
  --color-bg: oklch(0.09 0.01 260);       /* near-black, cool tint */
  --color-surface: oklch(0.13 0.01 260);  /* card/panel backgrounds */
  --color-border: oklch(0.22 0.02 260);   /* subtle borders */
  --color-text: oklch(0.93 0.01 260);     /* primary text */
  --color-text-muted: oklch(0.55 0.02 260); /* secondary text */
  --color-accent: oklch(0.72 0.18 260);   /* indigo/blue accent */
  --color-glow: oklch(0.72 0.18 260 / 0.3); /* glow effect */
}

@theme inline {
  --color-background: var(--color-bg);
  --color-surface: var(--color-surface);
  --color-accent: var(--color-accent);
}
```

```mjs
// postcss.config.mjs
export default {
  plugins: {
    "@tailwindcss/postcss": {},
  },
};
```

### Pattern 4: GameViewer iframe with COOP/COEP

**What:** The iframe embeds the Godot WASM game. The parent page has COOP/COEP headers; the iframe content must also be cross-origin isolated for SharedArrayBuffer.

**Critical constraint:** The game files are served by FastAPI on `:8000`. FastAPI's `StaticFiles` does NOT automatically add COOP/COEP or CORS headers. The Godot WASM runtime requires `SharedArrayBuffer`, which needs cross-origin isolation.

**Two valid approaches:**

**Approach A — Add headers to FastAPI static mount (RECOMMENDED):**
```python
# In backend main.py — add middleware or custom StaticFiles subclass
# that adds COOP/COEP headers to /games/* responses
```
This keeps the frontend clean but requires a backend change.

**Approach B — Next.js API route proxy:**
```typescript
// app/api/games/[...path]/route.ts
// Proxies /games/* from FastAPI and adds COOP/COEP headers
```
Adds latency (proxying large WASM files) but keeps backend unchanged.

**iframe attributes needed regardless:**
```tsx
<iframe
  src={gameUrl}
  allow="cross-origin-isolated"  // permissions policy
  sandbox="allow-scripts allow-same-origin"  // restrict iframe capabilities
  className="w-full h-full border-0"
  title="Generated game"
/>
```

**Note:** `allow="cross-origin-isolated"` delegates the permission down to the embedded frame. The embedded page must ALSO serve with its own COOP/COEP headers to use SharedArrayBuffer. This is a known WASM/Godot web export requirement.

### Anti-Patterns to Avoid

- **Putting EventSource in component body (not a hook):** EventSource leaks on re-renders; always use `useRef` + cleanup in `useEffect`
- **Multiple `useState` calls for generation state:** Leads to impossible intermediate states; use `useReducer`
- **Importing server components into `"use client"` components:** Don't try to use RSC features inside the interactive components — everything interactive needs `"use client"`
- **Assuming `es.onerror` fires for SSE `error` events:** The backend emits a *named* `error` event; `es.onerror` fires only on network/connection failures. Register both `es.addEventListener('error', ...)` and `es.onerror`
- **Using `EventSource` for POST:** EventSource only supports GET; the two-step pattern (POST → job_id → GET EventSource) is correct and matches the existing backend design

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSS utility classes | Custom CSS for dark theme | Tailwind CSS v4 | Tailwind provides all needed utilities; custom CSS creates maintenance burden |
| SSE reconnection | Manual retry loop | EventSource built-in reconnect (with `onerror` + manual on terminal events) | Native EventSource auto-reconnects on network drops; only manual close needs handling |
| Shimmer animation | Custom JS animation | Tailwind `animate-pulse` + CSS `@keyframes shimmer` | Standard pattern, zero JS needed |
| Loading state | Spinners library | Tailwind pulse/shimmer classes | No dependency needed for a pulsing skeleton |
| Type-safe SSE events | Runtime validation library | TypeScript discriminated union + JSON.parse | Zod is overkill for 3 event types with known shapes |

**Key insight:** This phase is almost entirely UI composition. The only non-trivial problem is the COOP/COEP iframe chain — everything else is standard React + Tailwind patterns.

---

## Common Pitfalls

### Pitfall 1: COOP/COEP iframe Chain Break

**What goes wrong:** Game iframe loads but Godot WASM fails with "SharedArrayBuffer is not defined" or similar; game appears blank.

**Why it happens:** Cross-origin isolation requires the FULL chain — parent page AND the iframe content — to be served with COOP/COEP headers. FastAPI's `StaticFiles` does not add these headers by default. The iframe content at `localhost:8000/games/.../index.html` lacks the headers.

**How to avoid:** Either (A) add a custom middleware to FastAPI that injects COOP/COEP headers for `/games/*` responses, or (B) proxy game static files through Next.js which already adds the headers.

**Warning signs:** `self.crossOriginIsolated` returns `false` in browser console when the game iframe is focused.

### Pitfall 2: Named SSE Events vs. `onerror`

**What goes wrong:** Backend emits `event: error` named events, but the frontend's `es.onerror` handler never fires. Error messages never appear in chat.

**Why it happens:** `EventSource.onerror` is NOT triggered by SSE events with `event: error`. It fires only on connection-level failures. Named events require `addEventListener('error', handler)`.

**How to avoid:** Register BOTH: `es.addEventListener('error', ...)` for backend-emitted error events, AND `es.onerror = ...` for network failures.

**Warning signs:** Generation fails silently; no error bubble appears in ChatPanel.

### Pitfall 3: EventSource URL (Absolute vs. Relative)

**What goes wrong:** `new EventSource('/api/stream/...')` hits Next.js (port 3000), which has no `/api/stream` route. The SSE stream gets a 404.

**Why it happens:** The backend is on port 8000. Relative URLs resolve to the Next.js dev server.

**How to avoid:** Use absolute URL `http://localhost:8000/api/stream/{job_id}` for direct fetch approach (CORS is configured). OR add a Next.js API proxy route at `/api/stream/[job_id]` that pipes the FastAPI SSE response.

**Warning signs:** EventSource connects and immediately fires `onerror`.

### Pitfall 4: EventSource Leak on New Generation

**What goes wrong:** User submits a new prompt while a previous generation is still streaming. Two EventSource connections are open; both dispatch to the same state — messages interleave.

**Why it happens:** The first EventSource was not closed before opening the second.

**How to avoid:** In `useGeneration.submit`, call `esRef.current?.close()` before creating a new EventSource. The reducer's `SUBMIT` action also clears the messages array.

**Warning signs:** Chat shows messages from multiple concurrent generations mixed together.

### Pitfall 5: `"use client"` Boundary Placement

**What goes wrong:** The whole `page.tsx` subtree loses RSC benefits; or conversely, interactive components fail with "hooks can only be used in client components."

**Why it happens:** The entire interactive feature (prompt input → SSE → iframe) requires client state. There are no meaningful RSC benefits in this phase.

**How to avoid:** Mark `page.tsx` with `"use client"` — it's the right call. Don't fight the boundary for this phase. The page is 100% interactive.

### Pitfall 6: `done` Event Data Shape

**What goes wrong:** `event.data.controls` is undefined; controls legend never renders.

**Why it happens:** The `done` event from the backend carries `GameResult` data. The controls list is in `data.controls` (array of `{key, action}` dicts), not at top level.

**Backend actual shape (from `main.py` and `base.py`):**
```
event: done
data: {"type": "done", "message": "Your game is ready.", "data": {}}
```
Wait — confirmed from reading `pipeline.py`: the `done` event is emitted as `ProgressEvent(type="done", message="Your game is ready.")` with empty `data: {}`. The `GameResult` (which contains `controls` and `wasm_path`) is the pipeline return value but is NOT emitted to the SSE stream directly.

**Resolution needed:** Verify whether the `done` SSE event carries controls or if the GameResult controls need to be added to the `done` event data. From `pipeline.py` the `done` event has `data={}`. The planner must add a task to verify/update the backend to include controls + wasm_path in the `done` event `data` field, OR have the frontend fetch a separate `/api/result/{job_id}` endpoint after the `done` event.

**Warning signs:** Controls legend never appears even after successful generation.

---

## Code Examples

### Two-Column Layout (Tailwind v4)

```tsx
// app/page.tsx — verified Tailwind v4 grid pattern
"use client";

export default function Page() {
  const [state, dispatch] = useReducer(generationReducer, initialState);
  const { submit } = useGeneration(dispatch);

  return (
    <main className="flex h-screen bg-[var(--color-bg)] text-[var(--color-text)]">
      {/* ChatPanel: fixed width sidebar */}
      <div className="w-[420px] min-w-[320px] flex flex-col border-r border-[var(--color-border)]">
        <ChatPanel state={state} onSubmit={submit} dispatch={dispatch} />
      </div>
      {/* GameViewer: fills remaining space */}
      <div className="flex-1 flex items-center justify-center bg-black/20">
        <GameViewer status={state.status} gameUrl={state.gameUrl} />
      </div>
    </main>
  );
}
```

### Loading Skeleton (Shimmer)

```tsx
// components/GameViewer.tsx
// Custom shimmer keyframe via Tailwind v4 @theme or inline style
function LoadingSkeleton() {
  return (
    <div className="w-full h-full relative overflow-hidden rounded-lg bg-[var(--color-surface)]">
      {/* Shimmer sweep using animate-pulse for simplicity, or custom keyframe for sweep effect */}
      <div className="absolute inset-0 animate-pulse bg-gradient-to-br from-[var(--color-surface)] via-[var(--color-border)] to-[var(--color-surface)]" />
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-[var(--color-text-muted)]">
        <div className="text-sm">Building your game...</div>
      </div>
    </div>
  );
}
```

### SSE Event Types (from Backend Source)

```typescript
// types/generation.ts — exact event shapes from reading main.py + base.py
interface SSEProgressEvent {
  type: 'stage_start' | 'done' | 'error';
  message: string;
  data: Record<string, unknown>;
}

// Backend emits via: ServerSentEvent(data=event.model_dump_json(), event=event.type)
// So event.data is the JSON-stringified ProgressEvent, event.type is the named event type
// EventSource parses: e.data = '{"type":"stage_start","message":"...","data":{}}'
//                     named event = 'stage_start'
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind v3 `@tailwind base/components/utilities` | Tailwind v4 `@import "tailwindcss"` | Tailwind v4 released 2025 | No config file needed; 70% smaller CSS output |
| `tailwind.config.js` | CSS variables in `globals.css` via `@theme` | v4 | Theming is native CSS, not JS config |
| Next.js Pages Router | App Router (default since Next 13) | 2023, stable | Server Components default; `"use client"` opt-in |
| Next.js default caching (`cache: 'force-cache'`) | No-cache by default in Next.js 15 | Next.js 15, 2024 | `fetch()` calls are not cached unless explicit |

**Deprecated/outdated:**
- `tailwind.config.js` with `content` array: No longer required in v4; auto-scans
- `@tailwind base; @tailwind components; @tailwind utilities`: Replaced by `@import "tailwindcss"` in v4
- `postcss-autoprefixer` as separate install: Included in `@tailwindcss/postcss` v4

---

## Open Questions

1. **Does the `done` SSE event carry controls + wasm_path in its `data` field?**
   - What we know: `pipeline.py` emits `ProgressEvent(type="done", message="Your game is ready.")` — `data={}` (default empty dict). `GameResult` (with `controls`, `wasm_path`) is the pipeline return value but is not explicitly passed to `emit`.
   - What's unclear: Is there code that enriches the `done` event with GameResult fields before emission, or does the frontend need to hit a separate endpoint after `done`?
   - Recommendation: **Wave 0 task** — add `data=result.model_dump()` to the `done` ProgressEvent in `pipeline.py`, OR add a `GET /api/result/{job_id}` endpoint. Frontend needs controls + wasm_path from somewhere.

2. **COOP/COEP for FastAPI static game files**
   - What we know: `next.config.ts` applies COOP/COEP to all Next.js routes. FastAPI `StaticFiles` at `/games/*` has no such headers.
   - What's unclear: Whether Godot's exported WASM truly requires SharedArrayBuffer (depends on export settings — `--threads` flag in Godot export).
   - Recommendation: **Wave 0 task** — add a custom FastAPI middleware that adds COOP/COEP headers to `/games/*` responses. Verify with `self.crossOriginIsolated` after first integration.

3. **Direct fetch vs. Next.js proxy for backend calls**
   - What we know: CORS is configured for `localhost:3000`; direct fetch to `:8000` works.
   - What's unclear: Whether hardcoding `localhost:8000` is acceptable or environment variable injection is needed.
   - Recommendation: Use `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000` env var; direct fetch (no proxy). Simpler for v1.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None detected — no jest.config, no vitest.config, no test files in frontend/ |
| Config file | Wave 0 — create `jest.config.ts` or `vitest.config.ts` |
| Quick run command | `cd frontend && npx vitest run --reporter=verbose` (after Wave 0 setup) |
| Full suite command | `cd frontend && npx vitest run` |

**Recommended: Vitest** — integrates cleanly with Vite-based tooling; React Testing Library for component tests; no Babel config needed.

**Alternative: Jest** — established, more docs, but requires more config for Next.js 15 + ESM.

**Note:** Per project pattern, tests are added as needed. Given the frontend is pure UI + SSE client logic, the highest value tests are:
1. `useGeneration` hook — SSE event dispatch logic
2. `generationReducer` — state transition correctness

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FE-01 | Two-column layout renders | Smoke (visual) | Manual verify at 1280px | ❌ Wave 0 |
| FE-02 | Submit sends POST + opens EventSource | Unit (hook) | `vitest run hooks/useGeneration.test.ts` | ❌ Wave 0 |
| FE-03 | stage_start events append chat bubbles | Unit (reducer) | `vitest run types/generation.test.ts` | ❌ Wave 0 |
| FE-04 | Loading skeleton renders during `generating` | Unit (component) | `vitest run components/GameViewer.test.tsx` | ❌ Wave 0 |
| FE-05 | done event loads iframe | Unit (component) | `vitest run components/GameViewer.test.tsx` | ❌ Wave 0 |
| FE-06 | Controls legend renders from done event | Unit (component) | `vitest run components/ChatPanel.test.tsx` | ❌ Wave 0 |
| FE-07 | Error event shows error bubble | Unit (reducer+component) | `vitest run types/generation.test.ts` | ❌ Wave 0 |
| FE-08 | Input resets after done | Unit (reducer) | `vitest run types/generation.test.ts` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd frontend && npx vitest run --reporter=dot` (reducer + hook unit tests, < 5s)
- **Per wave merge:** `cd frontend && npx vitest run` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `frontend/vitest.config.ts` — Vitest config with jsdom environment
- [ ] `frontend/package.json` — add `vitest`, `@vitejs/plugin-react`, `@testing-library/react`, `@testing-library/user-event`, `jsdom` as devDependencies
- [ ] `frontend/app/types/generation.test.ts` — covers FE-03, FE-07, FE-08 (reducer unit tests)
- [ ] `frontend/hooks/useGeneration.test.ts` — covers FE-02 (mock fetch + EventSource)
- [ ] `frontend/app/components/GameViewer.test.tsx` — covers FE-04, FE-05
- [ ] `frontend/app/components/ChatPanel.test.tsx` — covers FE-06

---

## Sources

### Primary (HIGH confidence)

- Backend source (`backend/backend/main.py`) — exact SSE event format, CORS config, endpoint shapes
- Backend source (`backend/backend/pipelines/base.py`) — `ProgressEvent`, `GameResult` model definitions
- Backend source (`backend/backend/pipelines/multi_stage/pipeline.py`) — `done` event emission pattern
- Frontend source (`frontend/next.config.ts`) — COOP/COEP header configuration, confirmed `require-corp`
- Frontend source (`frontend/package.json`) — Next.js 15.x, React 19, TypeScript 5 — already installed
- [MDN COEP](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cross-Origin-Embedder-Policy) — cross-origin isolation requirements for SharedArrayBuffer
- [Tailwind CSS animation docs](https://tailwindcss.com/docs/animation) — `animate-pulse` utility

### Secondary (MEDIUM confidence)

- WebSearch (verified with Tailwind official docs): Tailwind v4 uses `@import "tailwindcss"` and `@tailwindcss/postcss`, no config file required
- WebSearch (verified with MDN): `EventSource` named events require `addEventListener`, not `onerror`
- [web.dev COOP/COEP guide](https://web.dev/articles/coop-coep) — iframe chain requirement for cross-origin isolation

### Tertiary (LOW confidence)

- WebSearch only: Vitest recommended over Jest for new Next.js 15 projects — matches ecosystem trend but not verified against official Next.js testing docs

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — confirmed from existing package.json; Tailwind v4 verified from official docs
- Architecture: HIGH — SSE event shapes confirmed from reading actual backend source code
- Pitfall (COOP/COEP iframe): HIGH — confirmed from MDN official docs; directly observable in existing next.config.ts
- Pitfall (done event data): HIGH — confirmed gap from reading pipeline.py source directly
- Pitfall (EventSource onerror): HIGH — verified from MDN EventSource specification
- Validation architecture: MEDIUM — Vitest recommendation is from ecosystem patterns, not official Next.js docs

**Research date:** 2026-03-16
**Valid until:** 2026-04-16 (30 days — Next.js and Tailwind are stable; SSE API is browser standard)
