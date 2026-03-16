# Phase 4: Frontend Integration - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning
**Source:** Synthesized from PRD.md, planning docs, codebase exploration, and Moonlake AI research

<domain>
## Phase Boundary

This phase delivers the complete browser-facing application: a Next.js frontend that connects to the existing FastAPI backend, showing real-time pipeline progress via SSE and rendering the finished game in an iframe. The backend is fully functional (Phase 2+3 complete) — this phase is purely frontend.

**What exists:**
- Next.js 15 + React 19 project scaffold with COOP/COEP headers configured
- No components, pages, or styles exist yet — blank canvas
- Backend endpoints ready: `POST /api/generate`, `GET /api/stream/{job_id}`, static `/games/{job_id}/export/`
- SSE events: `stage_start`, `done`, `error` types with `message` and `data` fields
- GameResult includes `controls` list (key + action pairs) for legend display

**What this phase builds:**
- Two-column layout (ChatPanel + GameViewer)
- Prompt input with submit flow
- EventSource SSE client for real-time progress bubbles
- Game iframe with loading skeleton → live game transition
- Controls legend display
- Error state handling
- Prompt reset after game loads

</domain>

<decisions>
## Implementation Decisions

### Tech Stack
- Next.js 14+ app router with TypeScript and Tailwind CSS (per PRD)
- No additional UI libraries unless needed — keep dependencies minimal
- Backend proxy via Next.js API routes OR direct fetch to FastAPI on :8000 (CORS already configured)

### Layout & Visual Design
- Two-column layout: ChatPanel left, GameViewer right, both visible at 1280px
- Dark theme inspired by Moonlake AI's aesthetic — dark background, high-contrast text, subtle glow accents
- The game viewer should be the visual hero — large, prominent, with the chat panel as a supportive sidebar
- Clean, minimal chrome — the generated game should be the star, not the UI
- Loading skeleton in GameViewer should feel alive (shimmer/pulse animation, not static gray)

### Chat Panel
- Each SSE stage message renders as a chat bubble as it arrives
- Messages should feel conversational: "Understanding your idea...", "Designing game structure...", etc.
- On completion, controls legend (key → action) appears as a styled card in the chat
- Error messages appear inline in the chat with clear styling (not a modal/toast)
- No chat history between sessions — each generation is standalone

### Game Viewer
- Shows loading skeleton while pipeline runs
- On `done` event, skeleton replaced by iframe pointing to `/games/{job_id}/export/index.html`
- iframe needs COOP/COEP compatible loading (headers already configured in next.config.ts)
- Game should fill the viewer area responsively

### SSE Client
- Use native EventSource API (no library needed)
- Connect on prompt submit, parse JSON events, update chat state
- Handle connection drops gracefully — show reconnection message or error
- Clean up EventSource on component unmount or new generation

### Prompt Input
- Single text input with submit button at bottom of ChatPanel
- Disabled while generation is in progress
- Resets (clears) after game loads successfully
- Placeholder text with example prompt suggestion

### Error Handling
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

</decisions>

<specifics>
## Specific Ideas

### Moonlake AI Reference
Moonlake AI (moonlakeai.com) is a well-funded ($28M) AI game generation startup building "Reverie" — a generative game engine. Their approach:
- Prompt → playable interactive world in minutes
- Real-time diffusion model for visual reskinning
- Multi-modal reasoning for spatial layout + program synthesis for logic
- Live editing inside simulations

Their UI pattern (from public descriptions): prompt area + progress indicators + central play window. The product is in private preview so detailed UI screenshots aren't publicly available, but the general layout matches our two-column approach.

**Takeaway for Moonpond:** Our layout is aligned with industry direction. Key differentiator opportunity: make the progress feel more conversational/chat-like (vs a progress bar), and make the game viewer transition from skeleton → live game feel magical (smooth, not jarring).

### Backend API Contract (exact)
```
POST /api/generate  { "prompt": "..." }  → { "job_id": "uuid" }
GET  /api/stream/{job_id}  → SSE stream
  event types: stage_start, done, error
  data: { "type": "...", "message": "...", "data": {} }
  done event data includes: controls list, wasm_path
Static: /games/{job_id}/export/index.html (WASM game)
```

### SSE Event Sequence (typical)
1. `stage_start` — "Understanding your idea..."
2. `stage_start` — "Designing game structure and mechanics..."
3. `stage_start` — "Writing game code..."
4. `stage_start` — "Adding visual polish..."
5. `stage_start` — "Building for web..."
6. `done` — includes wasm_path + controls

</specifics>

<deferred>
## Deferred Ideas

- Iterative chat refinement (FEAT-01, v2)
- Download project as zip (FEAT-02, v2)
- Prompt hints/suggestions for new users (FEAT-03, v2)
- Mobile responsive layout (not in v1 scope)
- Game history/gallery (requires accounts, v2+)
- Dark/light theme toggle (dark only for v1)

</deferred>

---

*Phase: 04-frontend-integration*
*Context gathered: 2026-03-16 via synthesis from PRD, planning docs, and Moonlake AI research*
