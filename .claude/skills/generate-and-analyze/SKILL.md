---
name: generate-and-analyze
description: >
  Run the full pipeline end-to-end: generate a game from a prompt, build/export
  the WASM bundle, serve it locally, capture a browser screenshot, and run
  /analyze-game to produce a report. All output lands in the game directory.
  Triggers: "/generate-and-analyze <prompt>", "generate and analyze", "run the
  full loop", "test the pipeline".
version: 1.0.0
---

# Generate and Analyze

Run the complete moonpond pipeline loop: generate a game, serve it, screenshot
it, and analyze the result — all in one shot.

## Input

The user provides a game prompt, e.g.:
`/generate-and-analyze a pong game with neon visuals`

Optional flags the user may specify:
- `--pipeline <name>` — pipeline to use (default: `contract`)
- `--port <number>` — port for the local server (default: `8080`)

## Execution Flow

### 1. Generate and Export the Game

Run the pipeline via the CLI script with `--no-serve` so it generates and
exports but returns control immediately:

```bash
cd /Users/albertluo/other/moonpond && uv run scripts/generate.py "<prompt>" --pipeline contract --no-serve
```

Parse the output to find the game directory name (printed as `Game: games/<name>/export/`).
Store the full game directory path for subsequent steps:
`/Users/albertluo/other/moonpond/games/<game-name>_<timestamp>`

If the pipeline fails (non-zero exit or error in output), stop and report the
failure to the user. Do NOT proceed to screenshot/analysis.

### 2. Serve the Game Locally

Start a local HTTP server in the background serving the export directory with
COOP/COEP headers. Use Python's built-in HTTP server with the headers Godot
WASM requires:

```bash
cd <game_dir>/export && python3 -c "
import http.server, socketserver

class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        super().end_headers()
    def log_message(self, *a): pass

with socketserver.TCPServer(('', <port>), H) as s:
    s.serve_forever()
" &
```

Run this in the background and note the PID so it can be killed later.

### 3. Take a Screenshot

Use `npx playwright` to capture a screenshot of the running game. The game
needs a few seconds to load (WASM initialization).

Write a small inline Node.js script and run it with `npx playwright`:

```bash
npx --yes playwright screenshot \
  --wait-for-timeout 8000 \
  --full-page \
  "http://localhost:<port>/index.html" \
  "<game_dir>/output.png"
```

If `npx playwright screenshot` is not available or fails, fall back to writing
a small script:

```javascript
// /tmp/moonpond_screenshot.mjs
import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto('http://localhost:<port>/index.html', { waitUntil: 'networkidle' });
await page.waitForTimeout(8000); // let WASM initialize and game render
await page.screenshot({ path: '<game_dir>/output.png', fullPage: false });
await browser.close();
```

Run with: `node /tmp/moonpond_screenshot.mjs`

Ensure `output.png` was created in the game directory. If screenshot fails,
note it but still proceed to analysis (the analysis skill handles missing
screenshots).

### 4. Kill the Server

Kill the background HTTP server process using the PID captured in step 2.

### 5. Run Analysis

Invoke the `/analyze-game` skill on the game directory:

```
/analyze-game <game_dir>
```

This will inspect the screenshot, all generated code, intermediate artifacts,
and pipeline source to produce `report.md` in the game directory.

### 6. Report to User

After analysis completes, give the user a brief summary:

- Game directory path
- Whether generation succeeded
- Whether export succeeded
- Whether screenshot was captured
- Link to the report: `<game_dir>/report.md`
- Top-line findings (P0/P1/P2 counts from the report)

## Error Handling

- **Pipeline failure**: Report the error output and stop. Do not attempt
  screenshot or analysis.
- **Export failure**: The pipeline itself reports export failures. If export
  dir is empty/missing, note it and still run analysis (it can inspect
  intermediate artifacts).
- **Server won't start**: Try an alternate port (8081, 8082). If all fail,
  skip screenshot and proceed to analysis.
- **Screenshot failure**: Log the error, proceed to analysis without
  screenshot. The analysis skill will note the missing `output.png`.
- **Always clean up**: Kill the background server process even if later steps
  fail.

## Example Session

```
User: /generate-and-analyze a side-scrolling space shooter with asteroids