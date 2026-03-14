# Feature Research

**Domain:** AI-powered prompt-to-playable-game generator (Godot 4 / browser WASM)
**Researched:** 2026-03-13
**Confidence:** MEDIUM — web search and WebFetch were unavailable; analysis is based on training data (through August 2025) covering Rosebud AI, Google GameNGen experiments, Ludo.ai, GDevelop AI integration, the "vibe coding" wave of 2024-2025, and first-principles UX analysis. Competitive details should be validated before launch.

---

## Competitive Landscape (Training Data)

Known AI game generation products as of August 2025:

- **Rosebud AI** — browser-based, prompt-to-Phaser.js game, iterative chat refinement, publishes to web; strong on playability, weaker on visual quality
- **Google GameNGen** — neural-diffusion-based game simulation (research paper); not a product for end users
- **Ludo.ai** — game concept ideation and asset generation; not a code-generation/playable-game tool
- **Scenario** — AI asset generation for game art; not a full game generator
- **GDevelop + AI** — GDevelop added AI event-sheet helpers; not prompt-to-complete-game
- **GPT-4 + Pygame "vibe coding"** — community demos of LLM-generated Python/Pygame games; no polished product
- **Replit + Ghostwriter** — general code generation that can produce games; not game-specific UX

**Gap Moonpond fills:** No existing product combines (a) full code generation, (b) Godot 4 specifically, (c) visual polish as first-class output, and (d) a browser-playable WASM export in one flow. Rosebud is the closest competitor; Moonpond differentiates on visual/aesthetic quality and native engine export fidelity.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Text prompt input | Core interaction primitive — all AI tools start here | LOW | Single textarea, submit button; no bells needed |
| Visible generation progress | LLM generation takes 30-90s; users abandon without feedback | MEDIUM | SSE stream with labeled stages (Designing... Coding... Polishing... Exporting...) |
| Playable game in browser | The entire value proposition — must work without install | HIGH | Godot WASM export; iframe embed; keyboard/mouse input must pass through |
| Game controls visible | Users can't discover keybindings inside a WASM canvas | LOW | Controls legend rendered alongside game; must come from pipeline metadata |
| Error surfacing | Generation fails ~20-30% of the time; silent failure destroys trust | MEDIUM | User-readable error states for: timeout, export failure, LLM failure, syntax error |
| Generation re-try | When generation fails or game is wrong, user needs a path forward | LOW | "Try again" / re-submit same prompt; not a new feature, just a clear UI affordance |
| Reasonable generation speed | Users tolerate ~2 min; beyond that, most abandon | HIGH | Hard 90s pipeline timeout; LLM model selection (Haiku for fast stages) is critical |
| Game responds to input | A "game" that can't be controlled is not a game | HIGH | Template pre-defines input actions; LLM must use them; validated in pipeline |
| Prompt history in session | User needs to remember what they asked for | LOW | In-memory, session-scoped; no persistence required for v1 |

### Differentiators (Competitive Advantage)

Features that distinguish Moonpond from Rosebud and code-gen demos. Moonpond's stated differentiator is **visual/aesthetic quality** — generated games look intentional, not like bare functional code.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Applied shader library | Games have visual character — glow, scanlines, outline shaders applied by a dedicated Visual Polisher stage | MEDIUM | Requires shader library in `base_2d` template; LLM selects and configures from known palette; not free-form shader generation |
| Curated color palettes | Games look cohesive, not random-colored rectangles | LOW | Pre-defined palette resources in template; Visual Polisher stage selects palette based on game mood; very high ROI |
| Particle effects | Juice — explosions, pickups, ambient effects that make games feel alive | MEDIUM | Pre-built particle scenes in template; pipeline attaches them; LLM doesn't write particle code from scratch |
| Streaming progress UX with stage labels | Users see "Applying visual polish..." — sets expectation that this is a multi-step creative process, not just code generation | LOW | SSE events with human-readable stage names; differentiates from Rosebud's single progress bar |
| 3D game support (base_3d template) | Competitors (Rosebud) are 2D-only; Godot 4 3D WASM is viable | HIGH | Toon shader + lighting pre-configured; LLM generates 3D scene logic; complex but high wow factor |
| GDScript self-correction loop | Games actually run vs. failing to export with syntax errors | MEDIUM | Compiler output fed back to LLM for one correction pass; Rosebud has similar but it's not marketed |
| Godot 4 native export fidelity | Games use real Godot 4 features (physics, signals, scene tree) vs. browser JS hacks | HIGH | The entire architecture choice; this is not a UI feature but the output feels qualitatively different |
| Template-enforced structure | Games are always structurally valid Godot projects; no boilerplate hallucination | MEDIUM | Template with pre-validated export presets, audio bus layout, input map; LLM only writes gameplay |

### Anti-Features (Deliberately NOT Building in v1)

Features that seem good but create disproportionate complexity or undermine v1 focus.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| In-browser code editor | "Show me the code" / "let me tweak it" | Context explosion: now need syntax highlighting, file tree, save/load, Godot-specific validation; kills the "magic box" UX; deferred in PROJECT.md | Defer to v2; in v1, provide a "Download project" zip if code access is needed |
| User accounts / game persistence | "Save my games" / "share with friends" | Auth infrastructure, storage costs, moderation surface; not core to generation quality validation | Session-scoped v1; add in v2 after validating generation quality |
| Game gallery / sharing | Social proof, discovery | CDN/storage for WASM bundles, moderation, link management; large surface; premature without user accounts | Defer post v2 auth; screenshot-based sharing is a v1.x bridge |
| Iterative chat refinement ("make the enemies faster") | Rosebud's core UX; users expect it | Requires game state diffing, partial re-generation, context management across turns; high complexity; gets it wrong more than right | v1 is one-shot generation; iteration is re-prompting from scratch |
| Mobile touch controls | Games should work on phone | Godot WASM touch input is inconsistent; requires virtual joystick injection in template; high complexity for marginal v1 value | Desktop-first; document as known limitation |
| Audio / sound effects | Makes games feel complete | LLM sound design is nascent; procedural audio requires separate pipeline stage; export size bloat | Silence is acceptable for v1 MVP; add ambient/sfx in v2 |
| Multiplayer | "Play with friends" | Requires WebSocket relay, session management, Godot MultiplayerAPI; fundamentally incompatible with single-player generation approach | Out of scope per PROJECT.md; never a v1 concern |
| "Generate from image" / sketch-to-game | Visual prompting is trending | Adds multimodal input pipeline, layout parsing stage; complicates the already-complex generation graph | Text-only v1; image prompting is a v2 differentiator after core is proven |
| Live-reload / hot-patch | Tweak game without full regeneration | Requires incremental compilation, state preservation across reloads; Godot WASM doesn't hot-patch | Full regeneration is the v1 model; under 2 min is acceptable |
| Difficulty / length sliders | "Make it harder" / "longer game" | Prompt engineering handles this naturally ("a hard platformer with 5 levels"); UI sliders add complexity without enabling new behavior | Teach users to specify in prompt; consider a prompt hint system instead |

---

## Feature Dependencies

```
[Text Prompt Input]
    └──requires──> [LLM Pipeline Backend]
                       └──requires──> [Godot Headless Binary]
                                          └──requires──> [WASM Export Preset in Template]
                                                             └──requires──> [Browser WASM Iframe Embed]

[Streaming Progress UX]
    └──requires──> [SSE Backend Endpoint]
                       └──requires──> [Pipeline ProgressEvent emission]

[Visual Polish Differentiators (shaders, palettes, particles)]
    └──requires──> [base_2d / base_3d Templates with asset libraries]
                       └──requires──> [Visual Polisher Pipeline Stage]

[GDScript Self-Correction]
    └──requires──> [Godot Headless Compile Step]
                       └──requires──> [Compiler stderr capture + LLM re-generation]

[Controls Legend]
    └──requires──> [Pipeline metadata: control scheme emitted as ProgressEvent or final event]

[Error States Surfaced to User]
    └──requires──> [Pipeline exception handling with typed error categories]
    └──requires──> [SSE error event type]

[3D Game Support]
    └──requires──> [base_3d Template] (independent path from base_2d)
    └──enhances──> [Visual Polish] (toon shader pre-configured)

[In-Browser Code Editor] (ANTI-FEATURE v1)
    └──conflicts──> [Magic Box UX] (once users see messy generated code, trust drops)

[Iterative Chat Refinement] (ANTI-FEATURE v1)
    └──conflicts──> [Generation Speed SLA] (diff + partial regen is slower than full regen)
    └──requires──> [Game State Diffing] (not built)
```

### Dependency Notes

- **WASM embed requires template export preset:** The Godot project template must ship with a pre-configured HTML5 export preset; if LLM generates this, it hallucinates wrong settings. This is why templates are non-negotiable.
- **Visual polish requires template asset library:** Shaders and particles cannot be generated reliably by LLM on demand; they must be pre-authored in the template and referenced by name.
- **Self-correction requires compile step before export:** The pipeline must run `godot --headless --check-only` (or equivalent) before full export to catch GDScript syntax errors cheaply.
- **Controls legend requires pipeline cooperation:** The Code Generator stage must emit a structured control scheme; the frontend cannot infer it from the WASM canvas.
- **3D support is an independent path:** base_3d template has different complexity profile; can be developed in parallel with or after base_2d is stable.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate "prompt to visually polished playable Godot 4 game."

- [ ] Text prompt input + submit — the core interaction
- [ ] SSE streaming progress with named stages — trust and feedback during wait
- [ ] Multi-stage pipeline: Prompt Enhancer → Game Designer → Code Generator → Visual Polisher → Exporter — the differentiated flow
- [ ] base_2d template with shader library, palette resources, particle scenes — enables visual polish without LLM hallucination
- [ ] GDScript self-correction pass — without this, export failure rate is too high to demo
- [ ] WASM iframe embed with keyboard passthrough — playable in browser
- [ ] Controls legend in chat panel — usability without code access
- [ ] Error states surfaced to user (timeout, export failure, LLM failure) — prevents silent abandonment
- [ ] 90s hard timeout with user-visible message — sets expectation, prevents zombie requests

### Add After Validation (v1.x)

Features to add once core generation quality is proven.

- [ ] base_3d template + 3D game support — trigger: base_2d pipeline is stable and generating consistently; adds wow factor
- [ ] "Download project" zip — trigger: user demand for code access; low complexity bridge before full editor
- [ ] Screenshot/GIF capture of generated game — trigger: sharing need surfaces in user feedback
- [ ] Prompt suggestions / hint system — trigger: users struggle with prompt formulation; replaces parameter sliders
- [ ] Pipeline strategy A/B toggle (for internal testing) — trigger: want to test alternative generation strategies; modular registry already supports this

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] User accounts + game persistence — defer: auth infrastructure; validate generation quality first
- [ ] In-browser code editor — defer: large scope; validate that users want to edit vs. re-generate
- [ ] Iterative refinement chat — defer: state management complexity; re-prompting from scratch covers 80% of use cases
- [ ] "Generate from image" visual prompting — defer: multimodal pipeline; text-only covers v1 hypothesis
- [ ] Audio / sound effects pipeline stage — defer: adds pipeline stage and export size; silence is acceptable
- [ ] Game gallery / sharing — defer: requires accounts + CDN; premature
- [ ] Cloud deployment / public hosting — defer: local-only v1 per PROJECT.md

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Text prompt + streaming progress | HIGH | LOW | P1 |
| WASM playable embed | HIGH | MEDIUM | P1 |
| Multi-stage pipeline (core flow) | HIGH | HIGH | P1 |
| Visual polish (shaders/palettes/particles) | HIGH | MEDIUM | P1 |
| GDScript self-correction | HIGH | MEDIUM | P1 |
| Controls legend | MEDIUM | LOW | P1 |
| Error state UX | HIGH | LOW | P1 |
| 90s timeout + messaging | MEDIUM | LOW | P1 |
| base_3d template + 3D games | HIGH | HIGH | P2 |
| Download project zip | MEDIUM | LOW | P2 |
| Prompt hint/suggestion system | MEDIUM | LOW | P2 |
| In-browser code editor | MEDIUM | HIGH | P3 |
| Iterative refinement chat | HIGH | HIGH | P3 |
| User accounts + persistence | HIGH | HIGH | P3 |
| Audio pipeline stage | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | Rosebud AI | GDevelop AI | Moonpond Approach |
|---------|--------------|-------------|-------------------|
| Target engine | Phaser.js (browser JS) | GDevelop (custom engine) | Godot 4 (industry standard) |
| Visual polish | Minimal — functional output | Asset-generation focus | First-class — dedicated pipeline stage |
| Streaming progress | Single progress bar | N/A | Named stages via SSE |
| 3D support | No | Limited | Yes (base_3d template, v1.x) |
| Iterative refinement | Yes (chat loop) | No | No (v1); full re-generation |
| Export target | Browser only | Browser + desktop | Browser WASM (v1); Godot supports more |
| Self-correction | Yes (internal) | No | Yes (explicit pipeline stage) |
| Code access | Yes (editor) | Yes (event sheets) | No v1; download zip v1.x |
| Game persistence | Yes (account-based) | Yes | No v1 |
| Generation speed | ~30-60s | N/A | Target <120s hard limit |

---

## Sources

- Training data: Rosebud AI product (observed through August 2025) — MEDIUM confidence
- Training data: GDevelop AI feature announcements (2024) — MEDIUM confidence
- Training data: Ludo.ai, Scenario product positioning (2024-2025) — MEDIUM confidence
- Training data: Google GameNGen research paper (2024) — HIGH confidence (published research)
- First-principles analysis of Godot 4 WASM constraints — HIGH confidence
- First-principles UX analysis of AI generation wait-time tolerance — MEDIUM confidence
- PROJECT.md (Moonpond project requirements) — HIGH confidence (source of truth for this project)
- WebSearch and WebFetch were unavailable during this research session; competitive details should be verified against live products before making roadmap commitments

---

*Feature research for: AI-powered prompt-to-playable-game generator (Godot 4 / browser WASM)*
*Researched: 2026-03-13*
