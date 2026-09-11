# Phase 4: UI shell, Fleet and Instance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `http://127.0.0.1:8765` into a real control panel: a shell with a rail, a top bar and an alerts drawer; a Fleet home page with one card per instance led by its live thumbnail; and an Instance page with the live screen, a plain-language feed, the farm plan, the schedule timeline and the session panel.

**Architecture:** A Vite + React 19 single-page app in `brawlfarm/web/`, built to `brawlfarm/web/dist` and served by the FastAPI app that already mounts that directory when it exists. Server state is `@tanstack/react-query` over a thin typed `fetch` wrapper; live state is one module-level `EventSource` on `/api/events` that invalidates or appends to the query cache, so nothing polls except the screenshot thumbnails. Three small Python additions close the gaps the screens need (alert dismiss-all, a feed line number for de-duplication, the owned-brawler roster on the plan route); nothing else under `brawlfarm/` changes except `core/farmplan.py`, which gains one new pure function.

**Tech Stack:** Vite 7, React 19, TypeScript 5.9 (strict; `tsc --noEmit` is the lint, there is no ESLint), Tailwind v4 through `@tailwindcss/vite`, `react-router` 7 (declarative mode), `@tanstack/react-query` 5, `lucide-react`. Tests: vitest 3 + `@testing-library/react` 16 + `@testing-library/user-event` 14 + jsdom 26. Package manager pnpm 10.17.1 through corepack; Node 22 in CI. Python side unchanged: 3.13, uv, pytest, ruff.

**Spec:** docs/superpowers/specs/2026-09-10-brawlfarm-design.md

**Design brief:** docs/superpowers/plans/2026-09-11-phase-4-design-brief.md

## Global Constraints

- The UI never sends a tap, never exposes shop or purchase actions, never bypasses the API. Only these files under `brawlfarm/core` may change: `farmplan.py` (adding `plan_queue` only). `controller.py`, `states.py`, `vision.py` and the calibration block of `config.py` are not touched. The never-tap rail tests must pass unchanged.
- Loopback only, no auth, no CORS middleware (the Vite proxy handles dev).
- Instance names in URLs are used as given; the API validates them (`^[A-Za-z0-9_-]{1,32}$`).
- Scrub: `uv run python tools/scrub_check.py` prints `0 hit(s)` before every commit; no player tag, nickname, user path or token appears in code, tests, fixtures, screenshots or PR text. Web test fixtures use names Pie64 / Pie64_1 / Pie64_3, ports 5555 / 5565 / 5585, tag `#2P0YLQ9` (a made-up tag the scrub list does not match). The existing Python suite keeps its `alpha` / `bravo` names.
- The client must never log, store or display `connection.brawl_api_token`; only `app.theme` is read from `GET /api/settings`.
- Copy: no em-dashes, no emoji, no exclamation marks; state is a word plus a colour, never colour alone. Icons are `lucide-react` only, 16 px, `strokeWidth={1.6}`.
- Tokens live in `brawlfarm/web/src/styles/theme.css` and nowhere else. Radius 6 px on controls, 10 px on panels. No gradients, no glows, no shadows beyond a 1 px line. Motion: hover and press 120 ms; `@media (prefers-reduced-motion: reduce)` removes transitions. Focus: `outline: 2px solid var(--accent); outline-offset: 2px` on every interactive element via `:focus-visible`.
- Type scale (Tailwind arbitrary sizes): 11 (ids, captions), 12 (labels), 13 (body in panels), 15 (card titles, item text), 20 (page headers), 28 (h1). Numbers, ports, tags, times and log lines use `font-mono` with `tabular-nums`.
- TypeScript is strict and `any` is banned. Function components only; no default exports. `verbatimModuleSyntax` is on, so type-only imports are written `import type { ... }`.
- Every new `.ts` or `.tsx` module opens with a short block comment saying what it is for, matching the module-docstring density of the Python side. Every new Python file keeps its module docstring; every new test file says what behaviour it pins.
- Tests: vitest for every lib function and component behaviour named in the design brief; pytest for every API change. `pnpm typecheck`, `pnpm test`, `pnpm build`, `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest -q` are green before each commit. Every commit is self-contained: the tree builds and both suites pass at every one.
- Python line length 100, ruff lint select `E`, `F`, `W`, `I`. Run `uv run ruff format <changed files>` and `uv run ruff check --fix <changed files>` before the repo-wide check.
- Every commit: a conventional message plus the two trailers
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV`; `git config user.name` is `as9pa`.
- The branch is `phase-4/ui-shell-fleet-instance` from `main`; one PR. The PR carries screenshots of the real panel with the player tag and thumbnails blurred (playwright-cli `eval` sets `filter: blur(14px)` on `[data-private]` elements before the shot; the Instance header tag and every `Thumb` image carry `data-private`).
- Live evidence before done: the real instance (Pie64 on 5555) driven from the panel: Start from the card, the chip walks Starting to Farming, the feed streams a match, Stop shows "Stopping after this match" then Stopped; a plan change is visible in `farmplan.json` within a minute; the connection pill turns Reconnecting when the server is stopped and Live when it returns.
- Shell commands are written for Git Bash on Windows, with forward slashes. Web commands run from `brawlfarm/web`; Python commands run from the repo root.

## File map

Everything phase 4 creates or modifies, across all twelve tasks.

Web scaffold and configuration:

```
brawlfarm/web/package.json                  # scripts, caret-pinned deps, packageManager pnpm@10.17.1          (task 1)
brawlfarm/web/pnpm-lock.yaml                # generated by pnpm install, committed; CI installs --frozen        (task 1)
brawlfarm/web/tsconfig.json                 # one strict config covering src and vite.config.ts                 (task 1)
brawlfarm/web/vite.config.ts                # react + tailwind plugins, the /api dev proxy, the vitest block    (task 1)
brawlfarm/web/index.html                    # title "brawlfarm", the inline-SVG gold-square favicon             (task 1)
brawlfarm/web/public/fonts/*.woff2, *.txt   # Archivo latin, JetBrains Mono 400 and 500, both OFL texts         (task 1)
brawlfarm/web/src/main.tsx                  # createRoot, StrictMode, the theme.css import                      (task 1)
brawlfarm/web/src/vite-env.d.ts             # the vite/client type reference                                    (task 1)
brawlfarm/web/src/styles/theme.css          # @font-face, the tokens, @theme inline, base and motion rules      (task 1)
brawlfarm/web/src/test/setup.ts             # jest-dom matchers plus cleanup after each test                     (task 1)
```

Data layer and helpers:

```
brawlfarm/web/src/api/client.ts             # ApiError, api<T>(), errorFrom(), validationLines()                (task 2)
brawlfarm/web/src/api/types.ts              # every payload the API serves, mirroring the contracts file        (task 2)
brawlfarm/web/src/api/queries.ts            # queryKeys and createQueryClient (staleTime 5 s, retry 1)          (task 2)
brawlfarm/web/src/api/instances.ts          # listInstances, startInstance, stop, restart, retry                (task 2)
brawlfarm/web/src/api/plans.ts              # getPlan, putPlan                                                  (task 2)
brawlfarm/web/src/api/schedule.ts           # getSchedule, patchSchedule                                        (task 2)
brawlfarm/web/src/api/feed.ts               # getFeed                                                           (task 2)
brawlfarm/web/src/api/alerts.ts             # listAlerts, dismissAlert, dismissAllAlerts                        (task 2)
brawlfarm/web/src/api/stats.ts              # getStatsToday                                                     (task 2)
brawlfarm/web/src/api/settings.ts           # getSettings                                                       (task 2)
brawlfarm/web/src/api/screens.ts            # screenshotUrl, fetchScreenshot                                    (task 2)
brawlfarm/web/src/api/useInstances.ts       # useInstances(): the instances query and its 15 s visible poll     (task 2)
brawlfarm/web/src/lib/time.ts               # since, age, hhmm, hhmmss, duration, hoursText                     (task 2)
brawlfarm/web/src/lib/format.ts             # signed, plural                                                    (task 2)
brawlfarm/web/src/lib/toast.ts              # the toast queue store, toast(), useToasts()                       (task 2)
brawlfarm/web/src/live/useEvents.ts         # the shared EventSource, the backoff, subscribe, useConnection     (task 2)
brawlfarm/web/src/live/useVisiblePolling.ts # the refetch interval that stops while the tab is hidden           (task 2)
brawlfarm/web/src/test/http.ts              # stubFetch, jsonResponse, pngResponse                              (task 2)
brawlfarm/web/src/test/fixtures.ts          # makeInstance, makeAlert, makeFeedRecord (extended in task 8)      (task 2)
brawlfarm/web/src/lib/states.ts             # state labels and tones, phaseLabel, alert-kind chips, feed tones  (task 3)
brawlfarm/web/src/lib/feedText.ts           # feedText(record) -> { text, tone }, the whole event table         (task 9)
brawlfarm/web/src/lib/schedule.ts           # timeline(payload, nowIso) -> blocks, nowPct, ticks                (task 11)
```

Components and pages:

```
brawlfarm/web/src/components/ui/Button.tsx       # primary / quiet / text, disabledReason as a title           (task 3)
brawlfarm/web/src/components/ui/StateChip.tsx    # the seven instance states as word plus dot                  (task 3)
brawlfarm/web/src/components/ui/Chip.tsx         # the generic toned word chip                                 (task 3)
brawlfarm/web/src/components/ui/Switch.tsx       # a real button[role=switch][aria-checked]                    (task 3)
brawlfarm/web/src/components/ui/Segmented.tsx    # radiogroup semantics for the filter chips                   (task 3)
brawlfarm/web/src/components/ui/Field.tsx        # labelled text or number input with a suffix and a datalist  (task 3)
brawlfarm/web/src/components/ui/Toast.tsx        # Toast and Toaster over lib/toast.ts                          (task 3)
brawlfarm/web/src/components/ui/Drawer.tsx       # right-side 360 px dialog, focus trapped, Escape closes      (task 3)
brawlfarm/web/src/components/ui/ErrorBlock.tsx   # the API detail verbatim, 422 lines, the network sentence    (task 3)
brawlfarm/web/src/components/ui/Thumb.tsx        # the screenshot box: refresh, age, error state, data-private (task 3)
brawlfarm/web/src/test/renderWithProviders.tsx   # render inside a QueryClientProvider and a MemoryRouter      (task 3)
brawlfarm/web/src/App.tsx                        # providers, routes, theme bootstrap, SSE handlers, Toaster   (tasks 1, 4, 6, 8)
brawlfarm/web/src/app/Shell.tsx                  # the rail / top bar / content grid and the drawer            (task 4)
brawlfarm/web/src/app/Rail.tsx                   # wordmark, nav with soon tags, the instances group           (task 4)
brawlfarm/web/src/app/TopBar.tsx                 # page title, connection pill, the Alerts button and badge    (task 4)
brawlfarm/web/src/app/AlertsDrawer.tsx           # the alert rows, per-row Dismiss, Dismiss all, empty copy    (task 4)
brawlfarm/web/src/app/Placeholder.tsx            # h1 plus one paragraph                                       (task 4)
brawlfarm/web/src/app/alertsDrawer.ts            # the open/closed store the top bar and the alert strip share (task 4)
brawlfarm/web/src/fleet/Fleet.tsx                # header, Start all / Stop all, the grid, totals, empty state (task 6)
brawlfarm/web/src/fleet/InstanceCard.tsx         # thumbnail, name row, the 2 x 2 metrics, the footer controls (task 6)
brawlfarm/web/src/fleet/AlertStrip.tsx           # the newest alert above the grid, with Retry now and Dismiss (task 6)
brawlfarm/web/src/instance/Instance.tsx          # the /instances/:name frame, header and two-column layout    (task 8)
brawlfarm/web/src/instance/LiveScreen.tsx        # the 16:9 box, Refresh and Full size                         (task 8)
brawlfarm/web/src/instance/Feed.tsx              # the filter chips, Follow, SSE appends, the empty copy       (task 9)
brawlfarm/web/src/instance/FarmPlan.tsx          # mode, goal, fallback, current brawler, queue, roster        (task 10)
brawlfarm/web/src/instance/Schedule.tsx          # the timeline bar, override chip, Run for, Redraw today      (task 11)
brawlfarm/web/src/instance/SessionPanel.tsx      # the six session figures and the frozen "Session ended"      (task 11)
```

Vitest files sit next to the module they pin, named `<module>.test.ts` or `<module>.test.tsx`:

```
src/App.test.tsx (tasks 1, 4)                    src/api/client.test.ts (task 2)
src/api/endpoints.test.ts (task 2)               src/api/useInstances.test.tsx (task 2)
src/lib/time.test.ts (task 2)                    src/lib/format.test.ts (task 2)
src/lib/toast.test.ts (task 2)                   src/live/useEvents.test.ts (task 2)
src/live/useVisiblePolling.test.ts (task 2)      src/lib/states.test.ts (task 3)
src/components/ui/Button.test.tsx (task 3)       src/components/ui/StateChip.test.tsx (task 3)
src/components/ui/Switch.test.tsx (task 3)       src/components/ui/Segmented.test.tsx (task 3)
src/components/ui/Field.test.tsx (task 3)        src/components/ui/Toast.test.tsx (task 3)
src/components/ui/Drawer.test.tsx (task 3)       src/components/ui/ErrorBlock.test.tsx (task 3)
src/components/ui/Thumb.test.tsx (task 3)        src/app/Rail.test.tsx (task 4)
src/app/TopBar.test.tsx (task 4)                 src/app/AlertsDrawer.test.tsx (task 4)
src/fleet/Fleet.test.tsx (task 6)                src/fleet/InstanceCard.test.tsx (task 6)
src/fleet/AlertStrip.test.tsx (task 6)           src/instance/Instance.test.tsx (task 8)
src/instance/LiveScreen.test.tsx (task 8)        src/lib/feedText.test.ts (task 9)
src/instance/Feed.test.tsx (task 9)              src/instance/FarmPlan.test.tsx (task 10)
src/lib/schedule.test.ts (task 11)               src/instance/Schedule.test.tsx (task 11)
src/instance/SessionPanel.test.tsx (task 11)
```

Python and repository files:

```
brawlfarm/api/alerts.py                # AlertStore.dismiss_all and POST /api/alerts/dismiss-all               (task 5)
brawlfarm/api/feed.py                  # the feed record's seq, count_lines, the SSE payload's session key     (task 5)
brawlfarm/api/roster.py                # RosterCache: the supervisor process's first Brawl Stars API call      (task 7)
brawlfarm/api/plans.py                 # current / roster / queue / roster_status on GET and PUT               (task 7)
brawlfarm/api/app.py                   # app.state.roster                                                      (task 7)
brawlfarm/core/farmplan.py             # plan_queue, a new pure function; nothing existing changes             (task 7)
tests/test_api_alerts.py               # dismiss_all and its route                                             (task 5)
tests/test_api_feed.py                 # seq on both paths, the SSE session key, updated shape assertions      (task 5)
tests/test_api_roster.py               # RosterCache: ok, no_token, no_tag, stale, TTL expiry                  (task 7)
tests/test_api_plan.py                 # the enriched GET and PUT payloads                                     (task 7)
tests/test_farmplan_queue.py           # plan_queue for ladder and prestige                                    (task 7)
.github/workflows/ci.yml               # the node 22 web steps and the wheel check                             (task 1)
pyproject.toml                         # [tool.hatch.build.targets.wheel] artifacts and exclude                (task 1)
README.md                              # "Developing the panel"; the Running section's panel paragraph         (tasks 1, 12)
docs/superpowers/plans/2026-09-11-phase-4-design-brief.md   # the brief this plan implements                   (task 1)
```

`.gitignore` already carries `node_modules/` and `brawlfarm/web/dist/`, and `tools/scrub_check.py` already skips `node_modules` and `dist` (its `SKIP_DIRS`), so neither file needs a change. Safety-rail files (`brawlfarm/core/controller.py`, `core/states.py`, `core/vision.py`, the calibration block of `core/config.py`) are not touched by any task.

---
### Task 1: The web scaffold, the design tokens, CI and the wheel

Everything the other eleven tasks stand on: a pnpm workspace under `brawlfarm/web`, Vite building React 19 with Tailwind v4, the token stylesheet, two self-hosted fonts, vitest running in jsdom with one real test, the CI steps that typecheck, test and build the panel before pytest, and the packaging change that puts the built `dist` inside the wheel. It ends with `brawlfarm --no-browser` serving a real page instead of the phase 3 placeholder.

**Files:**
- Create: `brawlfarm/web/package.json`
- Create: `brawlfarm/web/pnpm-lock.yaml` (generated by `pnpm install`)
- Create: `brawlfarm/web/tsconfig.json`
- Create: `brawlfarm/web/vite.config.ts`
- Create: `brawlfarm/web/index.html`
- Create: `brawlfarm/web/public/fonts/Archivo-latin.woff2`
- Create: `brawlfarm/web/public/fonts/JetBrainsMono-Regular.woff2`
- Create: `brawlfarm/web/public/fonts/JetBrainsMono-Medium.woff2`
- Create: `brawlfarm/web/public/fonts/OFL-Archivo.txt`
- Create: `brawlfarm/web/public/fonts/OFL-JetBrainsMono.txt`
- Create: `brawlfarm/web/src/vite-env.d.ts`
- Create: `brawlfarm/web/src/styles/theme.css`
- Create: `brawlfarm/web/src/main.tsx`
- Create: `brawlfarm/web/src/App.tsx`
- Create: `brawlfarm/web/src/test/setup.ts`
- Test: `brawlfarm/web/src/App.test.tsx`
- Create: `docs/superpowers/plans/2026-09-11-phase-4-design-brief.md` (the brief, copied in unchanged)
- Modify: `.github/workflows/ci.yml` (insert the node block before `- run: uv sync --group dev`; append the wheel check after `- run: uv run pytest -q`)
- Modify: `pyproject.toml` (the two lines under the `[tool.hatch.build.targets.wheel]` header, found by that header text, not by line number)
- Modify: `README.md` (a `### Developing the panel` subsection at the end of `## Development`)

**Interfaces:**
- Consumes: nothing from earlier phase 4 tasks. From the existing repo: `brawlfarm/api/app.py::dist_dir()` returns `<brawlfarm package>/web/dist` and `create_app` mounts `SpaFiles` when `dist/index.html` exists (no change needed); `brawlfarm --no-browser` serves it.
- Produces:
  - `brawlfarm/web` as a pnpm package named `brawlfarm-web` with scripts `dev`, `build` (`tsc --noEmit && vite build`), `test` (`vitest run`) and `typecheck` (`tsc --noEmit`)
  - `src/styles/theme.css` exporting the Tailwind theme names every later task uses: colours `ground`, `panel`, `panel-2`, `line`, `text`, `muted`, `accent`, `accent-ink`, `ok`, `warn`, `bad`, `idle`; fonts `sans` and `mono`; radii `control` (6 px) and `panel` (10 px)
  - `src/App.tsx` exporting `export function App(): ReactElement` (task 4 replaces the body, keeps the name)
  - `src/test/setup.ts` as the vitest `setupFiles` entry: jest-dom matchers plus `cleanup()` after each test
- Consumed by: every later web task.

- [ ] **Step 1: Branch, and put the design brief in the repo**

```bash
cd <repo>
git switch -c phase-4/ui-shell-fleet-instance
git config user.name   # must print as9pa
```

Copy the brief this plan implements to `docs/superpowers/plans/2026-09-11-phase-4-design-brief.md` byte for byte. It is the reference every later task quotes; the plan is unreadable without it.

- [ ] **Step 2: Create the package and install the toolchain**

```bash
mkdir -p brawlfarm/web/src/styles brawlfarm/web/src/test brawlfarm/web/public/fonts
corepack enable
```

`brawlfarm/web/package.json`:

```json
{
  "name": "brawlfarm-web",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "packageManager": "pnpm@10.17.1",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "test": "vitest run",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.62.0",
    "lucide-react": "^0.544.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router": "^7.1.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@testing-library/jest-dom": "^6.6.0",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^5.0.0",
    "jsdom": "^26.0.0",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.9.0",
    "vite": "^7.0.0",
    "vitest": "^3.0.0"
  }
}
```

Then install. The caret ranges are floors, not pins: `pnpm install` resolves the current patch releases and writes them into `pnpm-lock.yaml`, which is what CI installs from.

```bash
cd brawlfarm/web
pnpm install
pnpm exec vite --version && pnpm exec tsc --version && pnpm exec vitest --version
```

Expected: vite 7.x, tsc 5.9.x, vitest 3.x, and a new `pnpm-lock.yaml`. If `corepack enable` reports a permissions problem, rerun the terminal as administrator once; corepack only has to shim `pnpm` on PATH.

- [ ] **Step 3: Fetch the two fonts and their licences**

Both fonts are served from `brawlfarm/web/public/fonts/`, so the panel makes no third-party request at runtime. Google Fonts only serves woff2 to a browser-shaped User-Agent, hence the header.

```bash
cd <repo>/brawlfarm/web
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# Archivo: the variable latin subset, weights 400 to 600.
curl -sS -A "$UA" "https://fonts.googleapis.com/css2?family=Archivo:wght@400..600&display=swap" -o /tmp/archivo.css
ARCHIVO_URL=$(awk '/\/\* latin \*\//{seen=1} seen && /src: url\(/{print; exit}' /tmp/archivo.css | sed -E 's/.*url\(([^)]+)\).*/\1/')
echo "$ARCHIVO_URL"    # must be an https://fonts.gstatic.com/... .woff2 URL
curl -sS -A "$UA" "$ARCHIVO_URL" -o public/fonts/Archivo-latin.woff2
curl -sSL "https://raw.githubusercontent.com/google/fonts/main/ofl/archivo/OFL.txt" -o public/fonts/OFL-Archivo.txt

# JetBrains Mono 2.304: the two weights the panel uses, plus the licence from the same zip.
curl -sSL "https://github.com/JetBrains/JetBrainsMono/releases/download/v2.304/JetBrainsMono-2.304.zip" -o /tmp/jbmono.zip
unzip -o -j /tmp/jbmono.zip "fonts/webfonts/JetBrainsMono-Regular.woff2" "fonts/webfonts/JetBrainsMono-Medium.woff2" -d public/fonts
unzip -p /tmp/jbmono.zip "OFL.txt" > public/fonts/OFL-JetBrainsMono.txt

ls -l public/fonts
file public/fonts/Archivo-latin.woff2
```

Expected: five files; each `.woff2` is tens of kilobytes and `file` reports "Web Open Font Format (Version 2)"; both `.txt` files start with "Copyright".

**If any fetch fails, stop and report it.** Do not substitute a different font, do not fall back to a Google Fonts `<link>`, do not commit a placeholder file. The two families are fixed by the design brief and self-hosting is a requirement, so a blocked download is a blocked task, not a design decision.

- [ ] **Step 4: Write the build configuration**

`brawlfarm/web/tsconfig.json` (one config, so `tsc --noEmit` needs no project references):

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "moduleDetection": "force",
    "jsx": "react-jsx",
    "types": ["vite/client"],
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "noEmit": true
  },
  "include": ["src", "vite.config.ts"]
}
```

`brawlfarm/web/vite.config.ts`:

```ts
/**
 * How the panel is built and tested.
 *
 * The dev server proxies /api to the running brawlfarm process instead of talking to it
 * across origins: the API has no CORS middleware on purpose, and a proxied request still
 * reaches it from 127.0.0.1, so the loopback-only guard is satisfied. The proxy carries
 * the SSE stream too, which is why changeOrigin stays off.
 */
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8765", changeOrigin: false },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    globals: false,
  },
});
```

`brawlfarm/web/index.html` (the favicon is an inline SVG data URI, so the panel ships no extra image file):

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="color-scheme" content="dark light" />
    <title>brawlfarm</title>
    <link
      rel="icon"
      href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='3' fill='%23E0B84B'/%3E%3C/svg%3E"
    />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`brawlfarm/web/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

- [ ] **Step 5: Write the token stylesheet**

`brawlfarm/web/src/styles/theme.css`. The `:root` and `@theme inline` blocks are the design brief's section 3 verbatim; the `@font-face` blocks and the base layer are the only additions. `@import` has to come first, which is why the font faces follow it rather than lead.

```css
@import "tailwindcss";

@font-face {
  font-family: "Archivo";
  font-style: normal;
  font-weight: 400 600;
  font-display: swap;
  src: url("/fonts/Archivo-latin.woff2") format("woff2");
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC,
    U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215,
    U+FEFF, U+FFFD;
}
@font-face {
  font-family: "JetBrains Mono";
  font-style: normal;
  font-weight: 400;
  font-display: swap;
  src: url("/fonts/JetBrainsMono-Regular.woff2") format("woff2");
}
@font-face {
  font-family: "JetBrains Mono";
  font-style: normal;
  font-weight: 500;
  font-display: swap;
  src: url("/fonts/JetBrainsMono-Medium.woff2") format("woff2");
}

:root {
  --ground: #0C0F14; --panel: #12161D; --panel-2: #181D26; --line: #252C38;
  --text: #E7EAF0; --muted: #8A94A6; --accent: #E0B84B; --accent-ink: #0C0F14;
  --ok: #58B77E; --warn: #E08A3C; --bad: #E06565; --idle: #6B7484;
  --series-1: #3987E5; --series-2: #D95926; --series-3: #199E70;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    --ground: #F3F4F6; --panel: #FFFFFF; --panel-2: #EEF0F3; --line: #D9DDE4;
    --text: #161A21; --muted: #5F6876; --accent: #9A7418; --accent-ink: #FFFFFF;
    --ok: #2B8A57; --warn: #B8631E; --bad: #B94A4A; --idle: #7B838F;
    --series-1: #2A78D6; --series-2: #EB6834; --series-3: #1BAF7A;
  }
}
:root[data-theme="light"] {
  --ground: #F3F4F6; --panel: #FFFFFF; --panel-2: #EEF0F3; --line: #D9DDE4;
  --text: #161A21; --muted: #5F6876; --accent: #9A7418; --accent-ink: #FFFFFF;
  --ok: #2B8A57; --warn: #B8631E; --bad: #B94A4A; --idle: #7B838F;
  --series-1: #2A78D6; --series-2: #EB6834; --series-3: #1BAF7A;
}
@theme inline {
  --color-ground: var(--ground); --color-panel: var(--panel); --color-panel-2: var(--panel-2);
  --color-line: var(--line); --color-text: var(--text); --color-muted: var(--muted);
  --color-accent: var(--accent); --color-accent-ink: var(--accent-ink);
  --color-ok: var(--ok); --color-warn: var(--warn); --color-bad: var(--bad); --color-idle: var(--idle);
  --font-sans: "Archivo", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
  --radius-control: 6px; --radius-panel: 10px;
}

@layer base {
  html {
    color-scheme: dark light;
  }
  :root[data-theme="dark"] {
    color-scheme: dark;
  }
  :root[data-theme="light"] {
    color-scheme: light;
  }
  body {
    margin: 0;
    background: var(--ground);
    color: var(--text);
    font-family: var(--font-sans);
    font-size: 13px;
    -webkit-font-smoothing: antialiased;
  }
  :focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    transition-duration: 0ms !important;
    animation-duration: 0ms !important;
  }
}
```

- [ ] **Step 6: Write the failing smoke test**

`brawlfarm/web/src/test/setup.ts` first, because vitest loads it before any test file:

```ts
/**
 * Runs before every test file: the jest-dom matchers (toBeInTheDocument, toHaveAttribute)
 * and an unmount after each test, so one test's DOM never leaks into the next.
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
```

`brawlfarm/web/src/App.test.tsx`:

```tsx
/** The scaffold end to end: React renders, the JSX transform runs, jsdom and the jest-dom
 * matchers are wired up. Task 4 replaces this with the routed shell's tests. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("App", () => {
  it("renders the wordmark", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "brawlfarm" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Run the test to confirm it fails**

```bash
cd <repo>/brawlfarm/web
pnpm test
```

Expected: FAIL, `Failed to resolve import "./App" from "src/App.test.tsx"`.

- [ ] **Step 8: Write the entry point and the placeholder App**

`brawlfarm/web/src/App.tsx`:

```tsx
/**
 * The panel's root component.
 *
 * Task 4 replaces this body with the providers, the routes and the live wiring. Until
 * then it proves the whole toolchain in one render: React 19, the Tailwind v4 token
 * utilities from styles/theme.css, and the self-hosted Archivo face.
 */
export function App() {
  return (
    <div className="min-h-screen bg-ground p-6 font-sans text-text">
      <h1 className="text-[28px] font-semibold tracking-tight">brawlfarm</h1>
      <p className="mt-2 text-[13px] text-muted">The panel is being built.</p>
    </div>
  );
}
```

`brawlfarm/web/src/main.tsx`:

```tsx
/** The browser entry point: mount App into index.html's #root with the tokens loaded. */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import "./styles/theme.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("index.html is missing its #root element");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 9: Run the test and the typecheck to confirm they pass**

```bash
cd <repo>/brawlfarm/web
pnpm test
pnpm typecheck
```

Expected: PASS, `1 passed (1)` from vitest; `tsc --noEmit` prints nothing and exits 0.

- [ ] **Step 10: Build, and check the FastAPI app serves the result**

```bash
cd <repo>/brawlfarm/web
pnpm build
ls dist/index.html dist/assets
cd <repo>
uv run pytest -q tests/test_api_app.py
```

Expected: `dist/index.html` plus a hashed `dist/assets/index-*.js` and `index-*.css`; the five app tests still pass. Both index tests monkeypatch `dist_dir`, so a real `dist/` on disk cannot change their result.

Then serve it for real, once, by hand:

```bash
uv run brawlfarm --no-browser
```

Open `http://127.0.0.1:8765/` in a browser: the page reads "brawlfarm" in Archivo on the dark ground colour, not the phase 3 placeholder sentence. Stop the process with Ctrl+C.

- [ ] **Step 11: Put the built panel in the wheel**

`dist/` is gitignored, and hatchling's file selection follows git, so the built panel would be silently missing from a wheel. Find the `[tool.hatch.build.targets.wheel]` header in `pyproject.toml` and work from the header text, never from a line number: `[tool.ruff]` sits a couple of lines below it and is easy to hit by counting. The block reads:

```toml
[tool.hatch.build.targets.wheel]
packages = ["brawlfarm"]
```

Replace exactly those two lines with:

```toml
[tool.hatch.build.targets.wheel]
packages = ["brawlfarm"]
# The panel is built by pnpm and git ignores brawlfarm/web/dist, so hatchling's VCS-aware
# file selection drops it: artifacts force it back in. The sources that produced it are
# excluded in turn -- a wheel carries the built page, never the TypeScript behind it.
artifacts = ["brawlfarm/web/dist/**"]
exclude = [
  "brawlfarm/web/src",
  "brawlfarm/web/public",
  "brawlfarm/web/node_modules",
  "brawlfarm/web/*.json",
  "brawlfarm/web/*.ts",
  "brawlfarm/web/*.html",
  "brawlfarm/web/*.yaml",
]
```

Check it:

```bash
cd <repo>
uv build --wheel
uv run python -c "import glob, zipfile; names = zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]).namelist(); assert 'brawlfarm/web/dist/index.html' in names, 'dist/index.html missing from the wheel'; assert not any(n.startswith('brawlfarm/web/src/') for n in names), 'the wheel carries web sources'; print('wheel ok')"
```

Expected: `wheel ok`. If `index.html` is missing, the `artifacts` line did not take; if a `src/` entry is listed, the `exclude` list did not.

- [ ] **Step 12: Add the web steps to CI**

`.github/workflows/ci.yml`. Insert the node block between the `astral-sh/setup-uv@v5` step and `- run: uv sync --group dev`, and append the wheel check after `- run: uv run pytest -q`. The whole file afterwards:

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.13"
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: corepack enable
      - run: pnpm install --frozen-lockfile
        working-directory: brawlfarm/web
      - run: pnpm typecheck
        working-directory: brawlfarm/web
      - run: pnpm test
        working-directory: brawlfarm/web
      - run: pnpm build
        working-directory: brawlfarm/web
      - run: uv sync --group dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run python tools/scrub_check.py
      - run: uv run pytest -q
      - run: uv build --wheel
      - name: the wheel carries the built panel
        run: |
          uv run python -c "import glob, zipfile; names = zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]).namelist(); assert 'brawlfarm/web/dist/index.html' in names, 'dist/index.html missing from the wheel'; assert not any(n.startswith('brawlfarm/web/src/') for n in names), 'the wheel carries web sources'; print('wheel ok')"
```

The web steps come before `uv sync` so a broken panel fails the job in about a minute instead of after the whole Python suite, and so `pnpm build` has already produced `dist/` by the time `uv build --wheel` runs.

- [ ] **Step 13: Document the workflow in the README**

Append this subsection to the end of `## Development` in `README.md`, directly before `## Running`:

````markdown
### Developing the panel

The panel lives in `brawlfarm/web`. pnpm runs it, pinned by `packageManager` in
`brawlfarm/web/package.json` and installed through corepack.

```
corepack enable                  # once per machine
cd brawlfarm/web
pnpm install
pnpm dev                         # http://127.0.0.1:5173, proxying /api to port 8765
```

Run `uv run brawlfarm --no-browser` in a second terminal so the dev server has an API to
proxy to; the proxy carries the live event stream as well as the plain requests.

`pnpm typecheck`, `pnpm test` and `pnpm build` are the three checks CI runs. `pnpm build`
writes `brawlfarm/web/dist`; restart `uv run brawlfarm` afterwards and it serves the built
panel from `http://127.0.0.1:8765/` instead of the placeholder page.
````

- [ ] **Step 14: Run every check, then commit**

```bash
cd <repo>/brawlfarm/web
pnpm typecheck && pnpm test && pnpm build
cd <repo>
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
uv run pytest -q
```

Expected: 1 vitest test passing, a clean `tsc`, a successful build, ruff silent, `0 hit(s)` from the scrub check, and the Python suite at its current 486 tests with no warnings.

```bash
git add brawlfarm/web/package.json brawlfarm/web/pnpm-lock.yaml brawlfarm/web/tsconfig.json brawlfarm/web/vite.config.ts brawlfarm/web/index.html brawlfarm/web/public brawlfarm/web/src .github/workflows/ci.yml pyproject.toml README.md docs/superpowers/plans/2026-09-11-phase-4-design-brief.md
git commit -m "feat(web): vite, react 19 and tailwind v4 scaffold for the panel

brawlfarm/web is the panel's source tree. Vite 7 builds it into brawlfarm/web/dist,
which the FastAPI app has mounted since phase 3, so uv run brawlfarm now serves a
real page instead of the placeholder. Tailwind v4 reads the design tokens from
src/styles/theme.css, which is the only file that names a colour.

Archivo and JetBrains Mono are self-hosted under public/fonts with both OFL texts
beside them: the panel is a loopback app and must not fetch anything from the
internet to render.

CI grows a node 22 half that typechecks, tests and builds the panel before the
Python steps, and a wheel check after pytest. hatchling follows git for file
selection and git ignores dist, so pyproject now force-includes the built panel as
an artifact and excludes the TypeScript that produced it.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 2: The data layer

Everything between the API and a component: one typed `fetch` wrapper whose failures are always a sentence, one module per route group, the time and number helpers the screens format with, the toast queue, and the single shared `EventSource` that drives every live update. No component imports `fetch` or `EventSource` after this task.

**Files:**
- Create: `brawlfarm/web/src/api/client.ts`
- Create: `brawlfarm/web/src/api/types.ts`
- Create: `brawlfarm/web/src/api/queries.ts`
- Create: `brawlfarm/web/src/api/instances.ts`
- Create: `brawlfarm/web/src/api/plans.ts`
- Create: `brawlfarm/web/src/api/schedule.ts`
- Create: `brawlfarm/web/src/api/feed.ts`
- Create: `brawlfarm/web/src/api/alerts.ts`
- Create: `brawlfarm/web/src/api/stats.ts`
- Create: `brawlfarm/web/src/api/settings.ts`
- Create: `brawlfarm/web/src/api/screens.ts`
- Create: `brawlfarm/web/src/api/useInstances.ts`
- Create: `brawlfarm/web/src/lib/time.ts`
- Create: `brawlfarm/web/src/lib/format.ts`
- Create: `brawlfarm/web/src/lib/toast.ts`
- Create: `brawlfarm/web/src/live/useEvents.ts`
- Create: `brawlfarm/web/src/live/useVisiblePolling.ts`
- Create: `brawlfarm/web/src/test/http.ts`
- Create: `brawlfarm/web/src/test/fixtures.ts`
- Test: `brawlfarm/web/src/api/client.test.ts`
- Test: `brawlfarm/web/src/api/endpoints.test.ts`
- Test: `brawlfarm/web/src/api/useInstances.test.tsx`
- Test: `brawlfarm/web/src/lib/time.test.ts`
- Test: `brawlfarm/web/src/lib/format.test.ts`
- Test: `brawlfarm/web/src/lib/toast.test.ts`
- Test: `brawlfarm/web/src/live/useEvents.test.ts`
- Test: `brawlfarm/web/src/live/useVisiblePolling.test.ts`

**Interfaces:**
- Consumes: task 1's `tsconfig.json`, `vite.config.ts` and `src/test/setup.ts`.
- Produces:
  - `api/client.ts`: `class ApiError extends Error { constructor(status: number, detail: string, lines?: string[]) }` with readonly `status: number`, `detail: string`, `lines: string[]`; `api<T>(path: string, init?: RequestInit): Promise<T>`; `errorFrom(response: Response): Promise<ApiError>`; `validationLines(detail: unknown): string[]`; `const NETWORK_DETAIL: string`
  - `api/types.ts`: `InstanceState`, `Health`, `Phase`, `InstanceSession`, `Today`, `InstancePayload`, `InstancesResponse`, `FarmPlan`, `RosterBrawler`, `RosterStatus`, `PlanCurrent`, `PlanResponse`, `ScheduleSession`, `ScheduleOverride`, `SchedulePayload`, `SchedulePatch`, `FeedCategory`, `FeedKind`, `FeedRecord`, `FeedResponse`, `FeedEvent`, `Alert`, `AlertsResponse`, `StatsSummary`, `StatsResponse`, `AppSettings`
  - `api/queries.ts`: `queryKeys.instances()`, `.alerts()`, `.plan(name)`, `.schedule(name)`, `.feed(name, kind)`, `.statsToday(instance?)`, `.settings()`; `createQueryClient(): QueryClient`
  - `api/instances.ts`: `listInstances(): Promise<InstancePayload[]>`, `startInstance(name: string, hours?: number): Promise<OkResponse>`, `stopInstance(name: string): Promise<OkResponse>`, `restartInstance(name: string): Promise<OkResponse>`, `retryInstance(name: string): Promise<OkResponse>` where `OkResponse = { ok: boolean }`
  - `api/plans.ts`: `getPlan(name: string): Promise<PlanResponse>`, `putPlan(name: string, plan: FarmPlan): Promise<PlanResponse>`
  - `api/schedule.ts`: `getSchedule(name: string): Promise<SchedulePayload>`, `patchSchedule(name: string, patch: SchedulePatch): Promise<SchedulePayload>`
  - `api/feed.ts`: `getFeed(name: string, kind: FeedKind, limit: number): Promise<FeedResponse>`
  - `api/alerts.ts`: `listAlerts(): Promise<AlertsResponse>`, `dismissAlert(id: number): Promise<void>`, `dismissAllAlerts(): Promise<void>`
  - `api/stats.ts`: `getStatsToday(instance?: string): Promise<StatsResponse>`
  - `api/settings.ts`: `getSettings(): Promise<AppSettings>`
  - `api/screens.ts`: `screenshotUrl(name: string): string`, `fetchScreenshot(name: string): Promise<Blob>`
  - `api/useInstances.ts`: `useInstances(): UseQueryResult<InstancePayload[], Error>` and `INSTANCES_POLL_MS = 15000` -- the `["instances"]` query with the 15 s poll that stops while the tab is hidden
  - `lib/time.ts`: `since(fromMs: number, nowMs: number): string`, `age(fromMs: number, nowMs: number): string`, `hhmm(iso: string): string`, `hhmmss(iso: string): string`, `duration(minutes: number): string`, `hoursText(h: number): string`
  - `lib/format.ts`: `signed(n: number): string`, `plural(n: number, word: string): string`
  - `lib/toast.ts`: `toast(message: string, opts?: { undo?: () => void | Promise<void>; durationMs?: number }): number`, `dismissToast(id: number): void`, `resetToasts(): void`, `useToasts(): readonly ToastItem[]`, `interface ToastItem { id: number; message: string; durationMs: number; undo?: () => void | Promise<void> }`, `TOAST_MS = 4000`, `TOAST_UNDO_MS = 6000`
  - `live/useEvents.ts`: `type Connection = "connecting" | "live" | "reconnecting"`, `type EventKind = "instance" | "feed" | "alert" | "log"`, `subscribe(kind: EventKind, handler: (data: unknown) => void): () => void`, `onReconnect(handler: () => void): () => void`, `useConnection(): Connection`, `setEventSourceFactory(factory: ((url: string) => EventSource) | null): void`, `closeEvents(): void`, `lastEventId(): number`, `BACKOFF_MS`, `EVENTS_URL`
  - `live/useVisiblePolling.ts`: `useVisiblePolling(intervalMs: number): number | false`
  - `test/http.ts`: `stubFetch(route): { calls, mock }`, `jsonResponse(body: unknown, status?: number): Response`, `pngResponse(): Response`
  - `test/fixtures.ts`: `makeInstance(overrides?: Partial<InstancePayload>): InstancePayload`, `makeAlert(overrides?: Partial<Alert>): Alert`, `makeFeedRecord(overrides?: Partial<FeedRecord>): FeedRecord`
- Consumed by: every later web task. Task 3's `Thumb` uses `fetchScreenshot` and `age`; task 4's `App` uses `subscribe`, `onReconnect`, `createQueryClient` and `queryKeys` and its `Rail` uses `useInstances`; task 6's `Fleet` and task 8's `Instance` read the fleet through `useInstances`, which is why the 15 s poll lives in one place; task 6 uses `makeInstance` in its fixtures.

- [ ] **Step 1: Write the payload types**

`brawlfarm/web/src/api/types.ts`. Every shape here is the phase 3 API's, field for field. `seq` on `FeedRecord`, `session` on `FeedEvent` and the four roster keys on `PlanResponse` are what tasks 5 and 7 add on the Python side; the types land now so the components compile against the finished contract.

```ts
/**
 * The API's payloads as TypeScript.
 *
 * Mirrors brawlfarm/api/*.py exactly: optional in Python means `| null` here, never
 * `?`, because the API always sends the key. Anything the panel does not use (the stats
 * series, the settings sections other than app.theme) is left out on purpose -- the
 * client must not carry connection.brawl_api_token anywhere near a component.
 */

export type InstanceState =
  | "farming"
  | "stopped"
  | "scheduled_break"
  | "reconnecting"
  | "offline"
  | "starting"
  | "stopping";

export type Health = "healthy" | "stale" | "dead";

export type Phase = "at_menu" | "queuing" | "playing" | "returning";

export interface InstanceSession {
  minutes_elapsed: number | null;
  start_trophies: number | null;
  last_trophies: number | null;
  disconnect_count: number | null;
  recovery_attempts: number | null;
  session: string | null;
}

export interface Today {
  games: number;
  trophies: number;
}

export interface InstancePayload {
  name: string;
  adb_port: number;
  state: InstanceState;
  health: Health;
  pid: number | null;
  heartbeat_age_s: number | null;
  /** The worker's own phase string; unknown values are shown as they arrive. */
  phase: Phase | string | null;
  desired: "run" | "stop";
  desired_reason: string | null;
  until: string | null;
  games_played: number | null;
  farm_brawler: string | null;
  note: string;
  player_tag: string;
  session: InstanceSession | null;
  today: Today;
}

export interface InstancesResponse {
  instances: InstancePayload[];
}

export interface FarmPlan {
  mode: "ladder" | "prestige";
  prestige_start: "highest" | "lowest";
  goal_trophies: number;
  maxed_fallback: string | null;
}

export interface RosterBrawler {
  id: number;
  name: string;
  trophies: number;
  highest: number;
  rank: number;
  power: number;
}

export type RosterStatus = "ok" | "no_token" | "no_tag" | "unavailable";

export interface PlanCurrent {
  brawler: string | null;
  trophies: number | null;
  goal: number;
}

export interface PlanResponse extends FarmPlan {
  current: PlanCurrent;
  roster: RosterBrawler[] | null;
  queue: string[];
  roster_status: RosterStatus;
}

export interface ScheduleSession {
  start: string;
  end: string;
}

export interface ScheduleOverride {
  mode: "run" | "stop";
  until: string;
  set_at: string | null;
}

export interface SchedulePayload {
  enabled: boolean;
  override: ScheduleOverride | null;
  plan_date: string | null;
  sessions: ScheduleSession[];
  day_end: string | null;
  desired: Record<string, unknown> | null;
  games_played_today: number;
  now: string;
}

export interface SchedulePatch {
  enabled?: boolean;
  redraw?: boolean;
  clear_override?: boolean;
}

export type FeedCategory = "matches" | "interrupts" | "errors" | "other";

export type FeedKind = "all" | "matches" | "interrupts" | "errors";

export interface FeedRecord {
  ts: string;
  /** The line's 1-based position in the session file; unique within one session. */
  seq: number;
  event: string;
  category: FeedCategory;
  fields: Record<string, unknown>;
}

export interface FeedResponse {
  session: string | null;
  records: FeedRecord[];
}

/** The SSE "feed" payload. */
export interface FeedEvent {
  instance: string;
  session: string | null;
  record: FeedRecord;
}

export interface Alert {
  id: number;
  ts: string;
  instance: string;
  kind: string;
  title: string;
  detail: string;
  dismissed: boolean;
}

export interface AlertsResponse {
  alerts: Alert[];
  unread: number;
}

export interface StatsSummary {
  games: number;
  trophies: number;
  trophies_per_hour: number | null;
  avg_rank: number | null;
  top4_rate: number | null;
  hours_farmed: number;
}

export interface StatsResponse {
  range: string;
  instances: string[];
  summary: StatsSummary;
}

/** Only app.theme is read. The rest of GET /api/settings, including the plaintext Brawl
 * Stars token, is deliberately not modelled so no component can reach it. */
export interface AppSettings {
  app: {
    port: number;
    theme: "system" | "dark" | "light";
  };
}
```

- [ ] **Step 2: Write the test helpers**

`brawlfarm/web/src/test/http.ts`:

```ts
/**
 * A fetch stub for the tests. Every test that touches the API installs one route
 * function and gets back the calls it received, so assertions can pin the URL, the
 * method and the body the client actually sent.
 */
import { vi } from "vitest";

export type Route = (url: string, init: RequestInit | undefined) => Response | Promise<Response>;

export interface FetchCall {
  url: string;
  init: RequestInit | undefined;
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** A four-byte PNG header: enough for Response.blob(), nothing decodes it. */
export function pngResponse(): Response {
  return new Response(new Uint8Array([137, 80, 78, 71]), {
    status: 200,
    headers: { "content-type": "image/png" },
  });
}

export function stubFetch(route: Route): { calls: FetchCall[]; mock: ReturnType<typeof vi.fn> } {
  const calls: FetchCall[] = [];
  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : String(input);
    calls.push({ url, init });
    return route(url, init);
  });
  vi.stubGlobal("fetch", mock);
  return { calls, mock };
}
```

`brawlfarm/web/src/test/fixtures.ts`:

```ts
/**
 * Payload builders for the tests. Shapes match the API exactly, so a component test
 * fails the same way the real payload would. The names, ports and tag are invented:
 * Pie64 / Pie64_1 / Pie64_3 on 5555 / 5565 / 5585 with the made-up tag #2P0YLQ9, which
 * tools/scrub_check.py does not match.
 */
import type { Alert, FeedRecord, InstancePayload } from "../api/types";

export function makeInstance(overrides: Partial<InstancePayload> = {}): InstancePayload {
  return {
    name: "Pie64",
    adb_port: 5555,
    state: "farming",
    health: "healthy",
    pid: 4242,
    heartbeat_age_s: 3.5,
    phase: "playing",
    desired: "run",
    desired_reason: "session",
    until: "2026-09-11T20:18:00",
    games_played: 12,
    farm_brawler: "NORI",
    note: "",
    player_tag: "#2P0YLQ9",
    session: {
      minutes_elapsed: 72,
      start_trophies: 41200,
      last_trophies: 41286,
      disconnect_count: 1,
      recovery_attempts: 0,
      session: "session-20260911-190540.jsonl",
    },
    today: { games: 12, trophies: 86 },
    ...overrides,
  };
}

export function makeAlert(overrides: Partial<Alert> = {}): Alert {
  return {
    id: 1,
    ts: "2026-09-11T19:42:00",
    instance: "Pie64",
    kind: "crash",
    title: "Bot crashed",
    detail: "err=adb did not answer",
    dismissed: false,
    ...overrides,
  };
}

export function makeFeedRecord(overrides: Partial<FeedRecord> = {}): FeedRecord {
  return {
    ts: "2026-09-11T19:05:40",
    seq: 1,
    event: "phase",
    category: "matches",
    fields: { to: "playing", frm: "queuing", games: 3 },
    ...overrides,
  };
}
```

- [ ] **Step 3: Write the failing tests for the client and the helpers**

`brawlfarm/web/src/api/client.test.ts`:

```ts
/** The one HTTP door: what it parses, and the sentence every failure mode turns into. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, validationLines } from "./client";
import { jsonResponse, stubFetch } from "../test/http";

afterEach(() => {
  // stubFetch installs a global; leaving it behind would leak into the next file.
  vi.unstubAllGlobals();
});

describe("api", () => {
  it("returns the parsed body", async () => {
    stubFetch(() => jsonResponse({ instances: [] }));
    await expect(api<{ instances: unknown[] }>("/api/instances")).resolves.toEqual({
      instances: [],
    });
  });

  it("sends a JSON content type only when there is a body", async () => {
    const { calls } = stubFetch(() => jsonResponse({ ok: true }));
    await api("/api/instances/Pie64/stop", { method: "POST" });
    await api("/api/instances/Pie64/start", { method: "POST", body: '{"hours":2}' });
    expect(calls[0].init).toEqual({ method: "POST" });
    expect(calls[1].init).toEqual({
      method: "POST",
      body: '{"hours":2}',
      headers: { "content-type": "application/json" },
    });
  });

  it("resolves a 204 as undefined", async () => {
    stubFetch(() => new Response(null, { status: 204 }));
    await expect(api<void>("/api/alerts/1/dismiss", { method: "POST" })).resolves.toBeUndefined();
  });

  it("turns a string detail into the error detail", async () => {
    stubFetch(() => jsonResponse({ detail: "unknown instance" }, 404));
    const error = await api("/api/instances/ghost/plan").catch((failure: unknown) => failure);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, detail: "unknown instance", lines: [] });
  });

  it("turns FastAPI's validation list into lines", async () => {
    stubFetch(() =>
      jsonResponse(
        {
          detail: [
            { loc: ["body", "goal_trophies"], msg: "Input should be greater than or equal to 0" },
            { loc: ["query", "limit"], msg: "Input should be less than or equal to 1000" },
          ],
        },
        422,
      ),
    );
    const error = await api("/api/instances/Pie64/plan", { method: "PUT", body: "{}" }).catch(
      (failure: unknown) => failure,
    );
    expect(error).toMatchObject({
      status: 422,
      detail: "Validation failed",
      lines: [
        "body.goal_trophies: Input should be greater than or equal to 0",
        "query.limit: Input should be less than or equal to 1000",
      ],
    });
  });

  it("falls back to the status when the body carries no detail", async () => {
    stubFetch(() => jsonResponse({ oops: true }, 500));
    const error = await api("/api/stats").catch((failure: unknown) => failure);
    expect(error).toMatchObject({ status: 500, detail: "Request failed (HTTP 500)" });
  });

  it("turns an unreachable server into the panel's own sentence", async () => {
    stubFetch(() => {
      throw new TypeError("Failed to fetch");
    });
    const error = await api("/api/instances").catch((failure: unknown) => failure);
    expect(error).toMatchObject({
      status: 0,
      detail: "The panel cannot reach brawlfarm. Is it still running?",
    });
  });
});

describe("validationLines", () => {
  it("joins loc with dots and ignores anything that is not an item", () => {
    expect(validationLines([{ loc: ["body", 0, "name"], msg: "required" }, "junk"])).toEqual([
      "body.0.name: required",
    ]);
    expect(validationLines("unknown instance")).toEqual([]);
  });
});
```

Every test file in this plan that calls `stubFetch` carries that same `afterEach(() => { vi.unstubAllGlobals(); })`.

`brawlfarm/web/src/lib/time.test.ts`:

```ts
/** The clock strings the screens print: ages, wall-clock times and durations. */
import { describe, expect, it } from "vitest";

import { age, duration, hhmm, hhmmss, hoursText, since } from "./time";

const NOW = Date.parse("2026-09-11T20:00:00");

describe("since and age", () => {
  it("counts seconds, then minutes, then hours", () => {
    expect(since(NOW - 8_000, NOW)).toBe("8 s");
    expect(since(NOW - 59_000, NOW)).toBe("59 s");
    expect(since(NOW - 60_000, NOW)).toBe("1 min");
    expect(since(NOW - 3 * 60_000, NOW)).toBe("3 min");
    expect(since(NOW - 3_600_000, NOW)).toBe("1 h");
    expect(since(NOW - 2 * 3_600_000, NOW)).toBe("2 h");
  });

  it("never counts backwards from a clock that ran ahead", () => {
    expect(since(NOW + 5_000, NOW)).toBe("0 s");
  });

  it("adds ago", () => {
    expect(age(NOW - 8_000, NOW)).toBe("8 s ago");
    expect(age(NOW - 3 * 60_000, NOW)).toBe("3 min ago");
    expect(age(NOW - 2 * 3_600_000, NOW)).toBe("2 h ago");
  });
});

describe("hhmm and hhmmss", () => {
  it("prints local wall-clock time", () => {
    expect(hhmm("2026-09-11T20:18:00")).toBe("20:18");
    expect(hhmm("2026-09-11T09:05:00")).toBe("09:05");
    expect(hhmmss("2026-09-11T19:05:40")).toBe("19:05:40");
  });

  it("prints nothing for a stamp it cannot parse", () => {
    expect(hhmm("not a time")).toBe("");
    expect(hhmmss("")).toBe("");
  });
});

describe("duration and hoursText", () => {
  it("prints minutes under an hour and h plus min above", () => {
    expect(duration(0)).toBe("0 min");
    expect(duration(0.4)).toBe("0 min");
    expect(duration(4)).toBe("4 min");
    expect(duration(59)).toBe("59 min");
    expect(duration(60)).toBe("1 h 0 min");
    expect(duration(72)).toBe("1 h 12 min");
    expect(duration(-5)).toBe("0 min");
  });

  it("turns a fractional hour count into the same shape", () => {
    expect(hoursText(3.6667)).toBe("3 h 40 min");
    expect(hoursText(0.5)).toBe("30 min");
    expect(hoursText(0)).toBe("0 min");
  });
});
```

`brawlfarm/web/src/lib/format.test.ts`:

```ts
/** Signed trophy deltas and the singular nouns the feed sentences need. */
import { describe, expect, it } from "vitest";

import { plural, signed } from "./format";

describe("signed", () => {
  it("puts a plus on a gain and leaves a plain zero alone", () => {
    expect(signed(86)).toBe("+86");
    expect(signed(-12)).toBe("-12");
    expect(signed(0)).toBe("0");
    expect(signed(-0)).toBe("0");
  });
});

describe("plural", () => {
  it("drops the s at one", () => {
    expect(plural(1, "game")).toBe("1 game");
    expect(plural(3, "game")).toBe("3 games");
    expect(plural(0, "skin")).toBe("0 skins");
  });
});
```

`brawlfarm/web/src/lib/toast.test.ts`:

```ts
/** The toast queue: one at a time, a longer life when an Undo is offered, and a store
 * that a component can subscribe to. */
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TOAST_MS, TOAST_UNDO_MS, dismissToast, resetToasts, toast, useToasts } from "./toast";

afterEach(() => {
  resetToasts();
});

describe("toast", () => {
  it("queues messages in order and reports them to a subscriber", () => {
    const { result } = renderHook(() => useToasts());
    act(() => {
      toast("Started Pie64");
      toast("Restarting Pie64");
    });
    expect(result.current.map((item) => item.message)).toEqual([
      "Started Pie64",
      "Restarting Pie64",
    ]);
  });

  it("lives 4 s normally and 6 s when it offers an undo", () => {
    const { result } = renderHook(() => useToasts());
    act(() => {
      toast("Plan saved");
      toast("Stopping Pie64 after this match", { undo: vi.fn() });
      toast("Redrawing today; new sessions appear after the next tick", { durationMs: 9000 });
    });
    expect(result.current.map((item) => item.durationMs)).toEqual([TOAST_MS, TOAST_UNDO_MS, 9000]);
  });

  it("dismisses by id and ignores an id it has already dropped", () => {
    const { result } = renderHook(() => useToasts());
    let id = 0;
    act(() => {
      id = toast("Alerts dismissed");
    });
    expect(result.current).toHaveLength(1);
    act(() => {
      dismissToast(id);
      dismissToast(id);
    });
    expect(result.current).toEqual([]);
  });
});
```

- [ ] **Step 4: Run the four test files to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test
```

Expected: FAIL, four `Failed to resolve import` errors for `./client`, `./time`, `./format` and `./toast`, plus the passing `App` test from task 1.

- [ ] **Step 5: Write the client and the helpers**

`brawlfarm/web/src/api/client.ts`:

```ts
/**
 * The panel's one HTTP door.
 *
 * Every call goes through api<T>() so a failure always arrives as an ApiError carrying a
 * sentence ErrorBlock can print: the API's own `detail` string when it sent one, the
 * lines of FastAPI's validation list when it sent that instead, the status otherwise,
 * and the panel's own wording when fetch itself could not reach the server.
 */

export const NETWORK_DETAIL = "The panel cannot reach brawlfarm. Is it still running?";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly lines: string[] = [],
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

interface ValidationItem {
  loc: (string | number)[];
  msg: string;
}

function isValidationItem(value: unknown): value is ValidationItem {
  if (typeof value !== "object" || value === null) return false;
  const item = value as { loc?: unknown; msg?: unknown };
  return Array.isArray(item.loc) && typeof item.msg === "string";
}

/** FastAPI's 422 body is a list of {loc, msg}; anything else has no lines. */
export function validationLines(detail: unknown): string[] {
  if (!Array.isArray(detail)) return [];
  return detail.filter(isValidationItem).map((item) => `${item.loc.join(".")}: ${item.msg}`);
}

export async function errorFrom(response: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  const detail = (body as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") return new ApiError(response.status, detail);
  const lines = validationLines(detail);
  if (lines.length > 0) return new ApiError(response.status, "Validation failed", lines);
  return new ApiError(response.status, `Request failed (HTTP ${response.status})`);
}

function withJsonHeaders(init: RequestInit | undefined): RequestInit {
  if (init?.body === undefined) return { ...init };
  return { ...init, headers: { "content-type": "application/json", ...init.headers } };
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, withJsonHeaders(init));
  } catch {
    // fetch only rejects when the request never got an answer: the server is down, or
    // the browser refused to send it. Either way the panel says the same thing.
    throw new ApiError(0, NETWORK_DETAIL);
  }
  if (!response.ok) throw await errorFrom(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
```

`brawlfarm/web/src/lib/time.ts`:

```ts
/**
 * Clock strings. Pure functions over a millisecond stamp or an ISO string, so the tests
 * pin them without a fake clock and the components pass Date.now() in.
 */

const MINUTE_S = 60;
const HOUR_S = 3600;

/** "8 s", "3 min", "2 h": how long ago something happened, without the word "ago". */
export function since(fromMs: number, nowMs: number): string {
  const seconds = Math.max(0, Math.round((nowMs - fromMs) / 1000));
  if (seconds < MINUTE_S) return `${seconds} s`;
  if (seconds < HOUR_S) return `${Math.floor(seconds / MINUTE_S)} min`;
  return `${Math.floor(seconds / HOUR_S)} h`;
}

export function age(fromMs: number, nowMs: number): string {
  return `${since(fromMs, nowMs)} ago`;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Local wall-clock time; the API's stamps have no timezone and mean local already. */
export function hhmm(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return `${pad(at.getHours())}:${pad(at.getMinutes())}`;
}

export function hhmmss(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return `${pad(at.getHours())}:${pad(at.getMinutes())}:${pad(at.getSeconds())}`;
}

export function duration(minutes: number): string {
  const total = Math.max(0, Math.floor(minutes));
  if (total < 60) return `${total} min`;
  return `${Math.floor(total / 60)} h ${total % 60} min`;
}

export function hoursText(h: number): string {
  return duration(Math.round(h * 60));
}
```

`brawlfarm/web/src/lib/format.ts`:

```ts
/** Number and word formatting: signed deltas, and nouns that agree with their count. */

export function signed(n: number): string {
  if (n === 0) return "0";
  return n > 0 ? `+${n}` : String(n);
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}
```

`brawlfarm/web/src/lib/toast.ts`:

```ts
/**
 * The toast queue.
 *
 * A module store rather than context: toasts are fired from event handlers deep in the
 * tree (a card's Stop button, the alerts drawer) and read by one Toaster mounted in App.
 * The queue holds every pending message; Toaster shows the head, so only one is visible.
 */
import { useSyncExternalStore } from "react";

export interface ToastOptions {
  undo?: () => void | Promise<void>;
  durationMs?: number;
}

export interface ToastItem {
  id: number;
  message: string;
  durationMs: number;
  undo?: () => void | Promise<void>;
}

export const TOAST_MS = 4000;
export const TOAST_UNDO_MS = 6000;

let queue: readonly ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of [...listeners]) listener();
}

export function toast(message: string, opts: ToastOptions = {}): number {
  const item: ToastItem = {
    id: nextId,
    message,
    durationMs: opts.durationMs ?? (opts.undo === undefined ? TOAST_MS : TOAST_UNDO_MS),
    ...(opts.undo === undefined ? {} : { undo: opts.undo }),
  };
  nextId += 1;
  queue = [...queue, item];
  emit();
  return item.id;
}

export function dismissToast(id: number): void {
  const next = queue.filter((item) => item.id !== id);
  if (next.length === queue.length) return;
  queue = next;
  emit();
}

/** Tests only: empty the queue and restart the ids. */
export function resetToasts(): void {
  queue = [];
  nextId = 1;
  emit();
}

function subscribeToasts(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function snapshot(): readonly ToastItem[] {
  return queue;
}

export function useToasts(): readonly ToastItem[] {
  return useSyncExternalStore(subscribeToasts, snapshot, snapshot);
}
```

- [ ] **Step 6: Run those tests to confirm they pass**

```bash
cd <repo>/brawlfarm/web
pnpm test
```

Expected: PASS, 5 files and 18 tests.

- [ ] **Step 7: Write the failing tests for the live layer**

`brawlfarm/web/src/live/useEvents.test.ts`. The fake stands in for the browser's `EventSource` so the test can decide when the stream opens, what it delivers and when it drops.

```ts
/** The shared event stream: one connection for the whole panel, per-kind handlers, a
 * backoff we control rather than the browser's, and a reconnect signal the query cache
 * refetches on. */
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  closeEvents,
  lastEventId,
  onReconnect,
  setEventSourceFactory,
  subscribe,
  useConnection,
} from "./useEvents";

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  private readonly listeners = new Map<string, Set<(event: Event) => void>>();

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(kind: string, listener: (event: Event) => void): void {
    const set = this.listeners.get(kind) ?? new Set<(event: Event) => void>();
    set.add(listener);
    this.listeners.set(kind, set);
  }

  removeEventListener(kind: string, listener: (event: Event) => void): void {
    this.listeners.get(kind)?.delete(listener);
  }

  close(): void {
    this.closed = true;
  }

  /** The server accepted the connection. */
  connect(): void {
    this.onopen?.();
  }

  /** One SSE frame: an id, an event name and a JSON data payload. */
  emit(kind: string, data: unknown, id: number): void {
    const event = new MessageEvent(kind, {
      data: JSON.stringify(data),
      lastEventId: String(id),
    });
    for (const listener of [...(this.listeners.get(kind) ?? [])]) listener(event);
  }

  /** The stream dropped. */
  fail(): void {
    this.onerror?.();
  }
}

function latest(): FakeEventSource {
  const source = FakeEventSource.instances.at(-1);
  if (source === undefined) throw new Error("no EventSource has been created");
  return source;
}

beforeEach(() => {
  FakeEventSource.instances = [];
  setEventSourceFactory((url) => new FakeEventSource(url) as unknown as EventSource);
});

afterEach(() => {
  closeEvents();
  setEventSourceFactory(null);
  vi.useRealTimers();
});

describe("subscribe", () => {
  it("opens one stream on /api/events and shares it between subscribers", () => {
    subscribe("instance", () => {});
    subscribe("alert", () => {});
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(latest().url).toBe("/api/events");
  });

  it("delivers each kind's payload to its own handlers", () => {
    const instances: unknown[] = [];
    const alerts: unknown[] = [];
    const feeds: unknown[] = [];
    subscribe("instance", (data) => instances.push(data));
    subscribe("alert", (data) => alerts.push(data));
    subscribe("feed", (data) => feeds.push(data));
    latest().connect();
    latest().emit("instance", { name: "Pie64", state: "farming" }, 1);
    latest().emit("alert", { id: 4, kind: "crash" }, 2);
    latest().emit("feed", { instance: "Pie64", session: "s.jsonl", record: { seq: 9 } }, 3);
    latest().emit("log", { message: "ignored" }, 4);
    expect(instances).toEqual([{ name: "Pie64", state: "farming" }]);
    expect(alerts).toEqual([{ id: 4, kind: "crash" }]);
    expect(feeds).toEqual([{ instance: "Pie64", session: "s.jsonl", record: { seq: 9 } }]);
  });

  it("ignores a frame whose id it has already delivered", () => {
    const seen: unknown[] = [];
    subscribe("alert", (data) => seen.push(data));
    latest().connect();
    latest().emit("alert", { id: 1 }, 7);
    latest().emit("alert", { id: 1 }, 7);
    latest().emit("alert", { id: 2 }, 8);
    expect(seen).toEqual([{ id: 1 }, { id: 2 }]);
    expect(lastEventId()).toBe(8);
  });

  it("stops delivering after the returned unsubscribe runs", () => {
    const seen: unknown[] = [];
    const off = subscribe("alert", (data) => seen.push(data));
    latest().connect();
    latest().emit("alert", { id: 1 }, 1);
    off();
    latest().emit("alert", { id: 2 }, 2);
    expect(seen).toEqual([{ id: 1 }]);
  });
});

describe("useConnection", () => {
  it("reports connecting, then live, then reconnecting", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useConnection());
    act(() => {
      subscribe("instance", () => {});
    });
    expect(result.current).toBe("connecting");
    act(() => latest().connect());
    expect(result.current).toBe("live");
    act(() => latest().fail());
    expect(result.current).toBe("reconnecting");
    act(() => {
      vi.advanceTimersByTime(1000);
      latest().connect();
    });
    expect(result.current).toBe("live");
  });
});

describe("the backoff", () => {
  it("reopens after 1, 2, 4, 8, 16 then 30 seconds and stays at 30", () => {
    vi.useFakeTimers();
    subscribe("instance", () => {});
    latest().connect();
    for (const delay of [1000, 2000, 4000, 8000, 16000, 30000, 30000]) {
      const before = FakeEventSource.instances.length;
      latest().fail();
      expect(latest().closed).toBe(true);
      expect(FakeEventSource.instances).toHaveLength(before);
      vi.advanceTimersByTime(delay - 1);
      expect(FakeEventSource.instances).toHaveLength(before);
      vi.advanceTimersByTime(1);
      expect(FakeEventSource.instances).toHaveLength(before + 1);
      expect(latest().url).toBe("/api/events");
    }
  });

  it("restarts the backoff once the stream comes back", () => {
    vi.useFakeTimers();
    subscribe("instance", () => {});
    latest().connect();
    latest().fail();
    vi.advanceTimersByTime(1000);
    latest().connect();
    const before = FakeEventSource.instances.length;
    latest().fail();
    vi.advanceTimersByTime(1000);
    expect(FakeEventSource.instances).toHaveLength(before + 1);
  });
});

describe("onReconnect", () => {
  it("runs only after a stream that had already dropped comes back", () => {
    vi.useFakeTimers();
    const refetch = vi.fn();
    onReconnect(refetch);
    subscribe("instance", () => {});
    latest().connect();
    expect(refetch).not.toHaveBeenCalled();
    latest().fail();
    vi.advanceTimersByTime(1000);
    latest().connect();
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});
```

`brawlfarm/web/src/live/useVisiblePolling.test.ts`:

```ts
/** Refetch intervals stop while the tab is hidden: a backgrounded panel must not keep
 * screenshotting a BlueStacks window. */
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useVisiblePolling } from "./useVisiblePolling";

function setVisibility(state: "visible" | "hidden"): void {
  Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
}

afterEach(() => {
  Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
});

describe("useVisiblePolling", () => {
  it("returns the interval while visible and false while hidden", () => {
    const { result } = renderHook(() => useVisiblePolling(15000));
    expect(result.current).toBe(15000);
    act(() => setVisibility("hidden"));
    expect(result.current).toBe(false);
    act(() => setVisibility("visible"));
    expect(result.current).toBe(15000);
  });
});
```

- [ ] **Step 8: Run them to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test
```

Expected: FAIL, `Failed to resolve import "./useEvents"` and `"./useVisiblePolling"`.

- [ ] **Step 9: Write the live layer**

`brawlfarm/web/src/live/useEvents.ts`:

```ts
/**
 * One EventSource for the whole panel.
 *
 * The browser's own auto-reconnect is not used: on an error the stream is closed and a
 * timer reopens it on a 1, 2, 4, 8, 16, 30 s backoff, so the connection pill and the
 * refetch-after-reconnect hook have something deterministic to report. The API replays
 * history only from the browser's own Last-Event-ID header, which a manual reopen never
 * sends, so a reconnect invalidates the queries instead of replaying frames.
 *
 * Module state rather than a provider: the stream must survive a route change, and every
 * screen that wants live data wants the same one connection.
 */
import { useSyncExternalStore } from "react";

export type Connection = "connecting" | "live" | "reconnecting";
export type EventKind = "instance" | "feed" | "alert" | "log";
export type EventHandler = (data: unknown) => void;
export type EventSourceFactory = (url: string) => EventSource;

export const EVENTS_URL = "/api/events";
export const BACKOFF_MS: readonly number[] = [1000, 2000, 4000, 8000, 16000, 30000];

const KINDS: readonly EventKind[] = ["instance", "feed", "alert", "log"];

const browserFactory: EventSourceFactory = (url) => new EventSource(url);

let makeSource: EventSourceFactory = browserFactory;
let source: EventSource | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let attempt = 0;
let lastId = 0;
let connection: Connection = "connecting";

const handlers = new Map<EventKind, Set<EventHandler>>();
const reconnectHandlers = new Set<() => void>();
const connectionListeners = new Set<() => void>();

/** Tests inject a fake here; null puts the browser's EventSource back. */
export function setEventSourceFactory(factory: EventSourceFactory | null): void {
  makeSource = factory ?? browserFactory;
}

/** Drop the connection and every handler. Tests call it between cases; nothing in the
 * app does, because the stream lives as long as the tab. */
export function closeEvents(): void {
  if (retryTimer !== null) {
    clearTimeout(retryTimer);
    retryTimer = null;
  }
  source?.close();
  source = null;
  attempt = 0;
  lastId = 0;
  handlers.clear();
  reconnectHandlers.clear();
  setConnection("connecting");
}

/** The id of the newest frame delivered on this connection; resets on every open. */
export function lastEventId(): number {
  return lastId;
}

export function subscribe(kind: EventKind, handler: EventHandler): () => void {
  const set = handlers.get(kind) ?? new Set<EventHandler>();
  set.add(handler);
  handlers.set(kind, set);
  openIfNeeded();
  return () => {
    set.delete(handler);
  };
}

export function onReconnect(handler: () => void): () => void {
  reconnectHandlers.add(handler);
  openIfNeeded();
  return () => {
    reconnectHandlers.delete(handler);
  };
}

export function useConnection(): Connection {
  return useSyncExternalStore(
    subscribeConnection,
    () => connection,
    () => connection,
  );
}

function subscribeConnection(listener: () => void): () => void {
  connectionListeners.add(listener);
  return () => {
    connectionListeners.delete(listener);
  };
}

function setConnection(next: Connection): void {
  if (connection === next) return;
  connection = next;
  for (const listener of [...connectionListeners]) listener();
}

function openIfNeeded(): void {
  if (source !== null || retryTimer !== null) return;
  open();
}

function open(): void {
  setConnection(attempt === 0 ? "connecting" : "reconnecting");
  const opened = makeSource(EVENTS_URL);
  source = opened;

  opened.onopen = () => {
    const reconnected = attempt > 0;
    attempt = 0;
    // A fresh connection starts the server's replay window over, so the id we compare
    // against has to start over too.
    lastId = 0;
    setConnection("live");
    if (reconnected) {
      for (const handler of [...reconnectHandlers]) handler();
    }
  };

  opened.onerror = () => {
    if (source !== opened) return; // a stale source we already replaced
    opened.close();
    source = null;
    setConnection("reconnecting");
    const delay = BACKOFF_MS[Math.min(attempt, BACKOFF_MS.length - 1)] ?? 30000;
    attempt += 1;
    retryTimer = setTimeout(() => {
      retryTimer = null;
      open();
    }, delay);
  };

  for (const kind of KINDS) {
    opened.addEventListener(kind, (event) => {
      dispatch(kind, event as MessageEvent<string>);
    });
  }
}

function dispatch(kind: EventKind, event: MessageEvent<string>): void {
  const id = Number(event.lastEventId);
  if (Number.isFinite(id) && id > 0) {
    if (id <= lastId) return;
    lastId = id;
  }
  let data: unknown;
  try {
    data = JSON.parse(event.data);
  } catch {
    return; // a frame we cannot parse is one frame lost, never a dead stream
  }
  for (const handler of [...(handlers.get(kind) ?? [])]) handler(data);
}
```

`brawlfarm/web/src/live/useVisiblePolling.ts`:

```ts
/**
 * The refetch interval a query should use, or false while the tab is hidden.
 *
 * Feeds react-query's refetchInterval. A backgrounded panel must not keep asking for
 * screenshots: every one of those is an adb screencap against a live BlueStacks window.
 */
import { useEffect, useState } from "react";

export function useVisiblePolling(intervalMs: number): number | false {
  const [visible, setVisible] = useState(() => document.visibilityState === "visible");

  useEffect(() => {
    const onChange = () => {
      setVisible(document.visibilityState === "visible");
    };
    document.addEventListener("visibilitychange", onChange);
    return () => {
      document.removeEventListener("visibilitychange", onChange);
    };
  }, []);

  return visible ? intervalMs : false;
}
```

- [ ] **Step 10: Run them to confirm they pass**

```bash
cd <repo>/brawlfarm/web
pnpm test src/live
```

Expected: PASS, 2 files and 8 tests.

- [ ] **Step 11: Write the failing tests for the endpoint modules**

`brawlfarm/web/src/api/endpoints.test.ts`:

```ts
/** Every route module: the URL it builds, the method and body it sends, and the shape it
 * hands back. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { dismissAlert, dismissAllAlerts, listAlerts } from "./alerts";
import { ApiError } from "./client";
import { getFeed } from "./feed";
import { listInstances, restartInstance, retryInstance, startInstance, stopInstance } from "./instances";
import { getPlan, putPlan } from "./plans";
import { fetchScreenshot, screenshotUrl } from "./screens";
import { getSchedule, patchSchedule } from "./schedule";
import { getSettings } from "./settings";
import { getStatsToday } from "./stats";
import { jsonResponse, pngResponse, stubFetch } from "../test/http";
import { makeAlert, makeInstance } from "../test/fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("instances", () => {
  it("unwraps the instances envelope", async () => {
    const { calls } = stubFetch(() => jsonResponse({ instances: [makeInstance()] }));
    const instances = await listInstances();
    expect(instances.map((inst) => inst.name)).toEqual(["Pie64"]);
    expect(calls[0].url).toBe("/api/instances");
  });

  it("posts start with hours, and with an empty body to clear a stop override", async () => {
    const { calls } = stubFetch(() => jsonResponse({ ok: true }));
    await startInstance("Pie64", 2);
    await startInstance("Pie64");
    expect(calls[0]).toEqual({
      url: "/api/instances/Pie64/start",
      init: {
        method: "POST",
        body: '{"hours":2}',
        headers: { "content-type": "application/json" },
      },
    });
    expect(calls[1].init?.body).toBe("{}");
  });

  it("posts the other three controls with no body", async () => {
    const { calls } = stubFetch(() => jsonResponse({ ok: true }));
    await stopInstance("Pie64");
    await restartInstance("Pie64");
    await retryInstance("Pie64");
    expect(calls.map((call) => call.url)).toEqual([
      "/api/instances/Pie64/stop",
      "/api/instances/Pie64/restart",
      "/api/instances/Pie64/retry",
    ]);
    expect(calls.every((call) => call.init?.body === undefined)).toBe(true);
  });
});

describe("plans and schedule", () => {
  it("reads and writes the plan", async () => {
    const { calls } = stubFetch(() =>
      jsonResponse({
        mode: "ladder",
        prestige_start: "highest",
        goal_trophies: 1000,
        maxed_fallback: null,
        current: { brawler: "NORI", trophies: 812, goal: 1000 },
        roster: null,
        queue: [],
        roster_status: "no_token",
      }),
    );
    const plan = await getPlan("Pie64");
    expect(plan.roster_status).toBe("no_token");
    await putPlan("Pie64", {
      mode: "prestige",
      prestige_start: "lowest",
      goal_trophies: 1000,
      maxed_fallback: null,
    });
    expect(calls[1]).toEqual({
      url: "/api/instances/Pie64/plan",
      init: {
        method: "PUT",
        body: '{"mode":"prestige","prestige_start":"lowest","goal_trophies":1000,"maxed_fallback":null}',
        headers: { "content-type": "application/json" },
      },
    });
  });

  it("patches the schedule with only the keys it was given", async () => {
    const { calls } = stubFetch(() => jsonResponse({ enabled: true, sessions: [] }));
    await getSchedule("Pie64");
    await patchSchedule("Pie64", { redraw: true });
    expect(calls[0].url).toBe("/api/instances/Pie64/schedule");
    expect(calls[1].init).toEqual({
      method: "PUT",
      body: '{"redraw":true}',
      headers: { "content-type": "application/json" },
    });
  });
});

describe("feed, alerts, stats and settings", () => {
  it("asks the feed for one kind and a limit", async () => {
    const { calls } = stubFetch(() => jsonResponse({ session: null, records: [] }));
    await getFeed("Pie64", "errors", 200);
    expect(calls[0].url).toBe("/api/instances/Pie64/feed?kind=errors&limit=200");
  });

  it("lists, dismisses one and dismisses all alerts", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: [makeAlert()], unread: 1 })
        : new Response(null, { status: 204 }),
    );
    const body = await listAlerts();
    expect(body.unread).toBe(1);
    await expect(dismissAlert(1)).resolves.toBeUndefined();
    await expect(dismissAllAlerts()).resolves.toBeUndefined();
    expect(calls.map((call) => call.url)).toEqual([
      "/api/alerts",
      "/api/alerts/1/dismiss",
      "/api/alerts/dismiss-all",
    ]);
  });

  it("scopes today's stats to one instance when asked", async () => {
    const { calls } = stubFetch(() =>
      jsonResponse({ range: "today", instances: ["Pie64"], summary: { avg_rank: 3.4 } }),
    );
    await getStatsToday();
    await getStatsToday("Pie64");
    expect(calls.map((call) => call.url)).toEqual([
      "/api/stats?range=today",
      "/api/stats?range=today&instances=Pie64",
    ]);
  });

  it("reads only the theme out of the settings document", async () => {
    stubFetch(() =>
      jsonResponse({
        app: { port: 8765, theme: "dark" },
        connection: { adb_path: "adb.exe", brawl_api_token: "must-not-be-used" },
      }),
    );
    const settings = await getSettings();
    expect(settings.app.theme).toBe("dark");
  });
});

describe("screenshots", () => {
  it("builds the url the Full size link opens", () => {
    expect(screenshotUrl("Pie64")).toBe("/api/instances/Pie64/screenshot.png");
  });

  it("fetches the png uncached and turns a 503 into its detail", async () => {
    const { calls } = stubFetch(() => pngResponse());
    const blob = await fetchScreenshot("Pie64");
    expect(blob.size).toBe(4);
    expect(calls[0].init).toEqual({ cache: "no-store" });

    stubFetch(() => jsonResponse({ detail: "adb did not answer" }, 503));
    const error = await fetchScreenshot("Pie64").catch((failure: unknown) => failure);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 503, detail: "adb did not answer" });
  });
});
```

`brawlfarm/web/src/api/useInstances.test.tsx`. The hook is three lines of composition,
but it is the one place the fleet's poll interval is decided, so the interval itself is
pinned here rather than in each screen's test.

```tsx
/** The instances query every screen shares: one key, one fetcher, and a 15 s poll that
 * stops while the tab is hidden. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { INSTANCES_POLL_MS, useInstances } from "./useInstances";
import { makeInstance } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

/** One client per test, so a cached list never leaks into the next case. */
function withClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useInstances", () => {
  it("reads the fleet through the shared instances key", async () => {
    const { calls } = stubFetch(() => jsonResponse({ instances: [makeInstance()] }));
    const { result } = renderHook(() => useInstances(), { wrapper: withClient() });
    await waitFor(() => {
      expect(result.current.data?.map((inst) => inst.name)).toEqual(["Pie64"]);
    });
    expect(calls[0].url).toBe("/api/instances");
  });

  it("asks again every 15 s while the tab is visible", async () => {
    vi.useFakeTimers();
    const { calls } = stubFetch(() => jsonResponse({ instances: [] }));
    renderHook(() => useInstances(), { wrapper: withClient() });
    await vi.waitFor(() => {
      expect(calls).toHaveLength(1);
    });
    expect(INSTANCES_POLL_MS).toBe(15000);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(INSTANCES_POLL_MS);
    });
    expect(calls).toHaveLength(2);
  });
});
```

- [ ] **Step 12: Run them to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test src/api/endpoints.test.ts src/api/useInstances.test.tsx
```

Expected: FAIL, unresolved imports for `./alerts`, `./feed`, `./instances`, `./plans`, `./schedule`, `./screens`, `./settings`, `./stats` and `./useInstances`.

- [ ] **Step 13: Write the endpoint modules and the query keys**

Instance names are already validated by the API against `^[A-Za-z0-9_-]{1,32}$`, and every name the panel puts in a URL came from the API, so the templates below interpolate them as given.

`brawlfarm/web/src/api/instances.ts`:

```ts
/** GET /api/instances and the five per-instance controls. Each control is 202 Accepted:
 * the supervisor has been poked, not finished. */
import { api } from "./client";
import type { InstancePayload, InstancesResponse } from "./types";

export interface OkResponse {
  ok: boolean;
}

export async function listInstances(): Promise<InstancePayload[]> {
  const body = await api<InstancesResponse>("/api/instances");
  return body.instances;
}

/** No hours clears the stop override; with hours the instance runs that long and stops. */
export function startInstance(name: string, hours?: number): Promise<OkResponse> {
  return api<OkResponse>(`/api/instances/${name}/start`, {
    method: "POST",
    body: JSON.stringify(hours === undefined ? {} : { hours }),
  });
}

export function stopInstance(name: string): Promise<OkResponse> {
  return api<OkResponse>(`/api/instances/${name}/stop`, { method: "POST" });
}

export function restartInstance(name: string): Promise<OkResponse> {
  return api<OkResponse>(`/api/instances/${name}/restart`, { method: "POST" });
}

export function retryInstance(name: string): Promise<OkResponse> {
  return api<OkResponse>(`/api/instances/${name}/retry`, { method: "POST" });
}
```

`brawlfarm/web/src/api/plans.ts`:

```ts
/** The farm plan, with the roster, the queue and the current brawler the API adds. */
import { api } from "./client";
import type { FarmPlan, PlanResponse } from "./types";

export function getPlan(name: string): Promise<PlanResponse> {
  return api<PlanResponse>(`/api/instances/${name}/plan`);
}

export function putPlan(name: string, plan: FarmPlan): Promise<PlanResponse> {
  return api<PlanResponse>(`/api/instances/${name}/plan`, {
    method: "PUT",
    body: JSON.stringify(plan),
  });
}
```

`brawlfarm/web/src/api/schedule.ts`:

```ts
/** Today's drawn sessions, the manual override and the schedule switch. PUT is a patch:
 * only the keys present act, so { redraw: true } leaves `enabled` alone. */
import { api } from "./client";
import type { SchedulePatch, SchedulePayload } from "./types";

export function getSchedule(name: string): Promise<SchedulePayload> {
  return api<SchedulePayload>(`/api/instances/${name}/schedule`);
}

export function patchSchedule(name: string, patch: SchedulePatch): Promise<SchedulePayload> {
  return api<SchedulePayload>(`/api/instances/${name}/schedule`, {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}
```

`brawlfarm/web/src/api/feed.ts`:

```ts
/** The newest session's narration. Only the newest session file is served; older ones
 * belong to the stats page. */
import { api } from "./client";
import type { FeedKind, FeedResponse } from "./types";

export function getFeed(name: string, kind: FeedKind, limit: number): Promise<FeedResponse> {
  return api<FeedResponse>(`/api/instances/${name}/feed?kind=${kind}&limit=${limit}`);
}
```

`brawlfarm/web/src/api/alerts.ts`:

```ts
/** The Fleet drawer's alerts. Both dismiss calls answer 204 with no body. */
import { api } from "./client";
import type { AlertsResponse } from "./types";

export function listAlerts(): Promise<AlertsResponse> {
  return api<AlertsResponse>("/api/alerts");
}

export function dismissAlert(id: number): Promise<void> {
  return api<void>(`/api/alerts/${id}/dismiss`, { method: "POST" });
}

export function dismissAllAlerts(): Promise<void> {
  return api<void>("/api/alerts/dismiss-all", { method: "POST" });
}
```

`brawlfarm/web/src/api/stats.ts`:

```ts
/** Today's aggregates. Phase 4 reads only `summary`; the Stats page is phase 6. */
import { api } from "./client";
import type { StatsResponse } from "./types";

export function getStatsToday(instance?: string): Promise<StatsResponse> {
  const scope = instance === undefined ? "" : `&instances=${instance}`;
  return api<StatsResponse>(`/api/stats?range=today${scope}`);
}
```

`brawlfarm/web/src/api/settings.ts`:

```ts
/** The settings document. The response also carries connection.brawl_api_token in
 * plaintext; AppSettings does not model it, and nothing in the panel may read it. */
import { api } from "./client";
import type { AppSettings } from "./types";

export function getSettings(): Promise<AppSettings> {
  return api<AppSettings>("/api/settings");
}
```

`brawlfarm/web/src/api/screens.ts`:

```ts
/** The live screenshot. Not JSON, so it bypasses api<T>() and builds its own ApiError
 * from the same helper; the API sends Cache-Control: no-store and we ask for no-store
 * again, because a cached frame is a stale screen. */
import { ApiError, NETWORK_DETAIL, errorFrom } from "./client";

export function screenshotUrl(name: string): string {
  return `/api/instances/${name}/screenshot.png`;
}

export async function fetchScreenshot(name: string): Promise<Blob> {
  let response: Response;
  try {
    response = await fetch(screenshotUrl(name), { cache: "no-store" });
  } catch {
    throw new ApiError(0, NETWORK_DETAIL);
  }
  if (!response.ok) throw await errorFrom(response);
  return response.blob();
}
```

`brawlfarm/web/src/api/queries.ts`:

```ts
/**
 * The query cache's keys and its defaults.
 *
 * Keys are built here rather than inline so an invalidation and a read can never drift
 * apart. staleTime 5 s keeps a route change from refetching everything; the live stream
 * is what makes data fresh, and retry 1 means a single blip does not paint an error.
 */
import { QueryClient } from "@tanstack/react-query";

import type { FeedKind } from "./types";

export const queryKeys = {
  instances: () => ["instances"] as const,
  alerts: () => ["alerts"] as const,
  plan: (name: string) => ["plan", name] as const,
  schedule: (name: string) => ["schedule", name] as const,
  feed: (name: string, kind: FeedKind) => ["feed", name, kind] as const,
  /** Fleet-wide with no argument, scoped to one instance for the session panel. Both
   * start with ["stats", "today"], so one invalidation covers them. */
  statsToday: (instance?: string) =>
    instance === undefined ? (["stats", "today"] as const) : (["stats", "today", instance] as const),
  settings: () => ["settings"] as const,
};

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 5000, retry: 1, refetchOnWindowFocus: true },
    },
  });
}
```

`brawlfarm/web/src/api/useInstances.ts`:

```ts
/**
 * The instances query, in one place.
 *
 * The rail, the Fleet page and the Instance page all want the same list, and all three
 * want it fresh: `session` and `today` exist only on GET /api/instances, so the instance
 * events (which carry the supervisor's view alone) cannot keep those numbers moving. One
 * hook owns the key, the fetcher and the 15 s poll, and the poll stops while the tab is
 * hidden, so a backgrounded panel costs the supervisor nothing.
 */
import { type UseQueryResult, useQuery } from "@tanstack/react-query";

import { listInstances } from "./instances";
import { queryKeys } from "./queries";
import type { InstancePayload } from "./types";
import { useVisiblePolling } from "../live/useVisiblePolling";

export const INSTANCES_POLL_MS = 15000;

export function useInstances(): UseQueryResult<InstancePayload[], Error> {
  const refetchInterval = useVisiblePolling(INSTANCES_POLL_MS);
  return useQuery({
    queryKey: queryKeys.instances(),
    queryFn: listInstances,
    refetchInterval,
  });
}
```

- [ ] **Step 14: Run everything, typecheck, build**

```bash
cd <repo>/brawlfarm/web
pnpm test
pnpm typecheck
pnpm build
```

Expected: PASS, 9 files and 35 tests; `tsc` silent; the build succeeds.

- [ ] **Step 15: Commit**

```bash
cd <repo>
uv run python tools/scrub_check.py
git add brawlfarm/web/src/api brawlfarm/web/src/lib brawlfarm/web/src/live brawlfarm/web/src/test
git commit -m "feat(web): typed api client, clock helpers and the shared event stream

One door to the API: api<T>() turns every failure into an ApiError carrying a
sentence the UI can print -- the API's own detail string, the lines of FastAPI's
validation list, the status, or the panel's own wording when the server cannot be
reached at all. api/types.ts mirrors the payloads field for field, including the
seq and roster keys the Python tasks add later.

api/useInstances.ts is the fleet list as one hook: the same key, the same
fetcher and one 15 s poll that stops with the tab, so the rail, the Fleet page
and the Instance page cannot drift into three different refresh rates.

live/useEvents.ts owns the single EventSource. The browser's auto-reconnect is
replaced with an explicit 1, 2, 4, 8, 16, 30 s backoff so the connection pill has
something honest to show and a reconnect can trigger the refetches that replace
the replay the API cannot give us. A module-level factory seam lets the tests
drive a fake stream frame by frame.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 3: The UI primitives

The ten components every screen is assembled from, plus the vocabulary module that maps a state or an alert kind to its word and its colour. Nothing here fetches its own data except `Thumb`, which owns the screenshot loop because no two callers want the same refresh rate.

Every toned dot and chip carries `data-tone="ok" | "warn" | "bad" | "idle"`. That attribute is the testable half of "word plus colour": a test asserts the tone without asserting a Tailwind class name, and the CSS reads the same attribute nowhere, so it costs nothing at runtime.

**Files:**
- Create: `brawlfarm/web/src/lib/states.ts`
- Create: `brawlfarm/web/src/components/ui/Button.tsx`
- Create: `brawlfarm/web/src/components/ui/StateChip.tsx`
- Create: `brawlfarm/web/src/components/ui/Chip.tsx`
- Create: `brawlfarm/web/src/components/ui/Switch.tsx`
- Create: `brawlfarm/web/src/components/ui/Segmented.tsx`
- Create: `brawlfarm/web/src/components/ui/Field.tsx`
- Create: `brawlfarm/web/src/components/ui/Toast.tsx`
- Create: `brawlfarm/web/src/components/ui/Drawer.tsx`
- Create: `brawlfarm/web/src/components/ui/ErrorBlock.tsx`
- Create: `brawlfarm/web/src/components/ui/Thumb.tsx`
- Create: `brawlfarm/web/src/test/renderWithProviders.tsx`
- Test: `brawlfarm/web/src/lib/states.test.ts`
- Test: `brawlfarm/web/src/components/ui/Button.test.tsx`
- Test: `brawlfarm/web/src/components/ui/StateChip.test.tsx`
- Test: `brawlfarm/web/src/components/ui/Switch.test.tsx`
- Test: `brawlfarm/web/src/components/ui/Segmented.test.tsx`
- Test: `brawlfarm/web/src/components/ui/Field.test.tsx`
- Test: `brawlfarm/web/src/components/ui/Toast.test.tsx`
- Test: `brawlfarm/web/src/components/ui/Drawer.test.tsx`
- Test: `brawlfarm/web/src/components/ui/ErrorBlock.test.tsx`
- Test: `brawlfarm/web/src/components/ui/Thumb.test.tsx`

**Interfaces:**
- Consumes: task 2's `ApiError`, `fetchScreenshot`, `age`, `lib/toast.ts` (`useToasts`, `dismissToast`, `ToastItem`), `api/types.ts`.
- Produces:
  - `lib/states.ts`: `type Tone = "ok" | "warn" | "bad" | "idle"`; `stateLabel(state: InstanceState): string`; `stateTone(state: InstanceState): Tone`; `phaseLabel(phase: string | null): string`; `alertKindLabel(kind: string): string`; `alertKindTone(kind: string): Tone`; `feedTone(category: FeedCategory): Tone`; `TONE_DOT: Record<Tone, string>`; `TONE_TEXT: Record<Tone, string>`
  - `Button({ variant?: "primary" | "quiet" | "text"; size?: "sm" | "md"; disabled?: boolean; disabledReason?: string; onClick?: (event: MouseEvent<HTMLButtonElement>) => void; children: ReactNode; type?: "button" | "submit" })`
  - `StateChip({ state: InstanceState })`
  - `Chip({ tone: Tone; children: ReactNode })`
  - `Switch({ checked: boolean; onChange: (next: boolean) => void; label: string; disabled?: boolean })`
  - `Segmented({ value: string; options: { value: string; label: string }[]; onChange: (next: string) => void; label: string })`
  - `Field({ label: string; id: string; value: string; onChange: (v: string) => void; type?: "text" | "number"; suffix?: string; min?: number; step?: number; disabled?: boolean; placeholder?: string; list?: string })`
  - `Toast({ item: ToastItem })` and `Toaster()`
  - `Drawer({ open: boolean; onClose: () => void; title: string; children: ReactNode; actions?: ReactNode })`
  - `ErrorBlock({ error: unknown; onRetry?: () => void })`
  - `Thumb({ name: string; refreshMs: number | false; dimmed?: boolean; caption?: string; overlay?: ReactNode; refreshKey?: number })` -- a change of `refreshKey` forces an immediate fetch; the `<img>` carries `data-private`
  - `test/renderWithProviders.tsx`: `renderWithProviders(ui: ReactElement, options?: { route?: string; client?: QueryClient }): RenderResult & { client: QueryClient }`; `testQueryClient(): QueryClient`
- Consumed by: tasks 4, 6, 8, 9, 10, 11.

- [ ] **Step 1: Write the failing tests for the vocabulary and the simple controls**

`brawlfarm/web/src/lib/states.test.ts`:

```ts
/** The panel's word-and-colour vocabulary: every instance state, every phase caption and
 * every alert kind the API can send. */
import { describe, expect, it } from "vitest";

import type { InstanceState } from "../api/types";
import { alertKindLabel, alertKindTone, feedTone, phaseLabel, stateLabel, stateTone } from "./states";

const STATES: [InstanceState, string, string][] = [
  ["farming", "Farming", "ok"],
  ["starting", "Starting", "idle"],
  ["stopping", "Stopping after this match", "warn"],
  ["stopped", "Stopped", "idle"],
  ["scheduled_break", "Scheduled break", "idle"],
  ["reconnecting", "Reconnecting", "warn"],
  ["offline", "Offline", "bad"],
];

describe("stateLabel and stateTone", () => {
  it.each(STATES)("maps %s to its word and tone", (state, label, tone) => {
    expect(stateLabel(state)).toBe(label);
    expect(stateTone(state)).toBe(tone);
  });
});

describe("phaseLabel", () => {
  it("captions the four worker phases and says so when there is no status", () => {
    expect(phaseLabel("at_menu")).toBe("at menu");
    expect(phaseLabel("queuing")).toBe("queuing");
    expect(phaseLabel("playing")).toBe("playing");
    expect(phaseLabel("returning")).toBe("returning");
    expect(phaseLabel(null)).toBe("no status yet");
    expect(phaseLabel("")).toBe("no status yet");
  });

  it("shows a phase it does not know rather than pretending there is none", () => {
    expect(phaseLabel("shopping")).toBe("shopping");
  });
});

describe("alertKindLabel and alertKindTone", () => {
  it("names the six panel alert kinds", () => {
    expect([
      alertKindLabel("offline"),
      alertKindLabel("crash"),
      alertKindLabel("bad_resolution"),
      alertKindLabel("recover"),
      alertKindLabel("wrong_mode"),
      alertKindLabel("recalibrate"),
    ]).toEqual(["Offline", "Crash", "Wrong resolution", "Recover", "Wrong mode", "Recalibrate"]);
    expect([
      alertKindTone("offline"),
      alertKindTone("crash"),
      alertKindTone("bad_resolution"),
      alertKindTone("recover"),
      alertKindTone("wrong_mode"),
      alertKindTone("recalibrate"),
    ]).toEqual(["bad", "bad", "bad", "warn", "warn", "warn"]);
  });

  it("falls back to the kind text for anything the API adds later", () => {
    expect(alertKindLabel("brand_new")).toBe("brand_new");
    expect(alertKindTone("brand_new")).toBe("idle");
  });
});

describe("feedTone", () => {
  it("colours the four feed categories", () => {
    expect([feedTone("matches"), feedTone("interrupts"), feedTone("errors"), feedTone("other")]).toEqual([
      "ok",
      "warn",
      "bad",
      "idle",
    ]);
  });
});
```

`brawlfarm/web/src/components/ui/StateChip.test.tsx`:

```tsx
/** The chip is the state: a word and a coloured dot, never colour alone. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StateChip } from "./StateChip";
import type { InstanceState } from "../../api/types";

const CASES: [InstanceState, string, string][] = [
  ["farming", "Farming", "ok"],
  ["starting", "Starting", "idle"],
  ["stopping", "Stopping after this match", "warn"],
  ["stopped", "Stopped", "idle"],
  ["scheduled_break", "Scheduled break", "idle"],
  ["reconnecting", "Reconnecting", "warn"],
  ["offline", "Offline", "bad"],
];

describe("StateChip", () => {
  it.each(CASES)("renders %s as a word with a %s dot", (state, label, tone) => {
    const { container } = render(<StateChip state={state} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(container.querySelector("[data-tone]")).toHaveAttribute("data-tone", tone);
  });
});
```

`brawlfarm/web/src/components/ui/Button.test.tsx`:

```tsx
/** The one button: three looks, a disabled reason that reaches the user as a tooltip. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";

describe("Button", () => {
  it("calls onClick and defaults to type button so it never submits a form", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Stop</Button>);
    const button = screen.getByRole("button", { name: "Stop" });
    expect(button).toHaveAttribute("type", "button");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("explains why it is disabled and does not fire", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled disabledReason="Not running" onClick={onClick}>
        Stop
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Stop" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Not running");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});
```

`brawlfarm/web/src/components/ui/Switch.test.tsx`:

```tsx
/** A real switch: screen readers get role and state, the keyboard gets it for free. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Switch } from "./Switch";

describe("Switch", () => {
  it("reports its state and toggles the other way round", async () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="Follow" />);
    const control = screen.getByRole("switch", { name: "Follow" });
    expect(control).toHaveAttribute("aria-checked", "false");
    await userEvent.click(control);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("does not toggle while disabled", async () => {
    const onChange = vi.fn();
    render(<Switch checked onChange={onChange} label="Schedule on" disabled />);
    await userEvent.click(screen.getByRole("switch", { name: "Schedule on" }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
```

`brawlfarm/web/src/components/ui/Segmented.test.tsx`:

```tsx
/** The filter chips are a radio group, so arrow keys and screen readers both work. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Segmented } from "./Segmented";

const OPTIONS = [
  { value: "all", label: "All" },
  { value: "matches", label: "Matches" },
  { value: "errors", label: "Errors" },
];

describe("Segmented", () => {
  it("marks the pressed option and reports the one that was clicked", async () => {
    const onChange = vi.fn();
    render(<Segmented value="all" options={OPTIONS} onChange={onChange} label="Feed filter" />);
    expect(screen.getByRole("radiogroup", { name: "Feed filter" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "All" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Errors" })).toHaveAttribute("aria-checked", "false");
    await userEvent.click(screen.getByRole("radio", { name: "Errors" }));
    expect(onChange).toHaveBeenCalledWith("errors");
  });
});
```

`brawlfarm/web/src/components/ui/Field.test.tsx`:

```tsx
/** A labelled input with a suffix, so "Goal 1000 trophies" is one control, not three. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Field } from "./Field";

describe("Field", () => {
  it("ties the label to the input and reports what was typed", async () => {
    const onChange = vi.fn();
    render(
      <Field
        label="Goal"
        id="goal"
        value="1000"
        onChange={onChange}
        type="number"
        suffix="trophies"
        min={0}
      />,
    );
    const input = screen.getByLabelText("Goal");
    expect(input).toHaveValue(1000);
    expect(input).toHaveAttribute("min", "0");
    expect(screen.getByText("trophies")).toBeInTheDocument();
    await userEvent.type(input, "1");
    expect(onChange).toHaveBeenLastCalledWith("10001");
  });

  it("passes a datalist id through so the roster can suggest brawlers", () => {
    render(
      <Field label="Fallback brawler" id="fallback" value="" onChange={vi.fn()} list="roster" disabled />,
    );
    const input = screen.getByLabelText("Fallback brawler");
    expect(input).toHaveAttribute("list", "roster");
    expect(input).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test src/lib/states.test.ts src/components
```

Expected: FAIL, unresolved imports for `./states`, `./StateChip`, `./Button`, `./Switch`, `./Segmented`, `./Field`.

- [ ] **Step 3: Write the vocabulary and the simple controls**

`brawlfarm/web/src/lib/states.ts`:

```ts
/**
 * The panel's word-and-colour vocabulary.
 *
 * Colour alone never carries meaning, so every mapping here comes in pairs: a word for
 * the reader and a tone for the dot beside it. The tone names match the theme's colour
 * tokens, and TONE_DOT / TONE_TEXT are the only place a tone becomes a class.
 */
import type { FeedCategory, InstanceState } from "../api/types";

export type Tone = "ok" | "warn" | "bad" | "idle";

const STATE_LABELS: Record<InstanceState, string> = {
  farming: "Farming",
  starting: "Starting",
  stopping: "Stopping after this match",
  stopped: "Stopped",
  scheduled_break: "Scheduled break",
  reconnecting: "Reconnecting",
  offline: "Offline",
};

const STATE_TONES: Record<InstanceState, Tone> = {
  farming: "ok",
  starting: "idle",
  stopping: "warn",
  stopped: "idle",
  scheduled_break: "idle",
  reconnecting: "warn",
  offline: "bad",
};

const PHASE_LABELS: Record<string, string> = {
  at_menu: "at menu",
  queuing: "queuing",
  playing: "playing",
  returning: "returning",
};

const ALERT_KIND_LABELS: Record<string, string> = {
  offline: "Offline",
  crash: "Crash",
  bad_resolution: "Wrong resolution",
  recover: "Recover",
  wrong_mode: "Wrong mode",
  recalibrate: "Recalibrate",
};

const ALERT_KIND_TONES: Record<string, Tone> = {
  offline: "bad",
  crash: "bad",
  bad_resolution: "bad",
  recover: "warn",
  wrong_mode: "warn",
  recalibrate: "warn",
};

const FEED_TONES: Record<FeedCategory, Tone> = {
  matches: "ok",
  interrupts: "warn",
  errors: "bad",
  other: "idle",
};

export const TONE_DOT: Record<Tone, string> = {
  ok: "bg-ok",
  warn: "bg-warn",
  bad: "bg-bad",
  idle: "bg-idle",
};

export const TONE_TEXT: Record<Tone, string> = {
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  idle: "text-idle",
};

export function stateLabel(state: InstanceState): string {
  return STATE_LABELS[state];
}

export function stateTone(state: InstanceState): Tone {
  return STATE_TONES[state];
}

/** The worker writes its own phase strings; one it has not taught us is shown as it
 * arrived, because "no status yet" would be a lie. */
export function phaseLabel(phase: string | null): string {
  if (phase === null || phase === "") return "no status yet";
  return PHASE_LABELS[phase] ?? phase;
}

export function alertKindLabel(kind: string): string {
  return ALERT_KIND_LABELS[kind] ?? kind;
}

export function alertKindTone(kind: string): Tone {
  return ALERT_KIND_TONES[kind] ?? "idle";
}

export function feedTone(category: FeedCategory): Tone {
  return FEED_TONES[category];
}
```

`brawlfarm/web/src/components/ui/Button.tsx`:

```tsx
/** The panel's only button. A disabled control still says why: disabledReason becomes
 * the title, so "Stop" on a stopped instance explains itself instead of just greying. */
import type { MouseEvent, ReactNode } from "react";

export interface ButtonProps {
  variant?: "primary" | "quiet" | "text";
  size?: "sm" | "md";
  disabled?: boolean;
  disabledReason?: string;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  children: ReactNode;
  type?: "button" | "submit";
}

const VARIANTS: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "bg-accent text-accent-ink hover:brightness-110",
  quiet: "border border-line bg-panel-2 text-text hover:border-accent",
  text: "text-accent hover:underline",
};

const SIZES: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "h-7 px-2 text-[12px]",
  md: "h-8 px-3 text-[13px]",
};

export function Button({
  variant = "quiet",
  size = "md",
  disabled = false,
  disabledReason,
  onClick,
  children,
  type = "button",
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      title={disabled ? disabledReason : undefined}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-[6px] font-medium transition-[background-color,border-color,color] duration-[120ms] disabled:cursor-not-allowed disabled:opacity-50 ${SIZES[size]} ${VARIANTS[variant]}`}
    >
      {children}
    </button>
  );
}
```

`brawlfarm/web/src/components/ui/StateChip.tsx`:

```tsx
/** An instance's state as a word plus a dot. */
import type { InstanceState } from "../../api/types";
import { TONE_DOT, stateLabel, stateTone } from "../../lib/states";

export interface StateChipProps {
  state: InstanceState;
}

export function StateChip({ state }: StateChipProps) {
  const tone = stateTone(state);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-[6px] border border-line bg-panel px-2 py-0.5 text-[11px] text-text">
      <span
        data-tone={tone}
        aria-hidden="true"
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`}
      />
      {stateLabel(state)}
    </span>
  );
}
```

`brawlfarm/web/src/components/ui/Chip.tsx`:

```tsx
/** A toned word chip: alert kinds, the schedule override, anything that is one label. */
import type { ReactNode } from "react";

import type { Tone } from "../../lib/states";
import { TONE_DOT } from "../../lib/states";

export interface ChipProps {
  tone: Tone;
  children: ReactNode;
}

export function Chip({ tone, children }: ChipProps) {
  return (
    <span
      data-tone={tone}
      className="inline-flex items-center gap-1.5 rounded-[6px] border border-line bg-panel px-2 py-0.5 text-[11px] text-text"
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`} />
      {children}
    </span>
  );
}
```

`brawlfarm/web/src/components/ui/Switch.tsx`:

```tsx
/** A real button[role=switch]: the keyboard, the screen reader and the pointer all get
 * the same control, and the visible label is its accessible name. */
export interface SwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
}

export function Switch({ checked, onChange, label, disabled = false }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-2 rounded-[6px] text-[12px] text-muted disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span
        aria-hidden="true"
        className={`relative h-4 w-7 shrink-0 rounded-full border border-line transition-colors duration-[120ms] ${checked ? "bg-accent" : "bg-panel-2"}`}
      >
        <span
          className={`absolute top-0.5 h-2.5 w-2.5 rounded-full transition-[left] duration-[120ms] ${checked ? "left-3.5 bg-accent-ink" : "left-0.5 bg-muted"}`}
        />
      </span>
      {label}
    </button>
  );
}
```

`brawlfarm/web/src/components/ui/Segmented.tsx`:

```tsx
/** A radio group that looks like chips. Radio semantics rather than buttons, so the
 * "one of these is selected" relationship survives in a screen reader. */
export interface SegmentedOption {
  value: string;
  label: string;
}

export interface SegmentedProps {
  value: string;
  options: SegmentedOption[];
  onChange: (next: string) => void;
  label: string;
}

export function Segmented({ value, options, onChange, label }: SegmentedProps) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex gap-0.5 rounded-[6px] border border-line bg-panel p-0.5"
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={`h-6 rounded-[4px] px-2 text-[12px] transition-colors duration-[120ms] ${selected ? "bg-accent text-accent-ink" : "text-muted hover:text-text"}`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
```

`brawlfarm/web/src/components/ui/Field.tsx`:

```tsx
/** A labelled input with an optional unit suffix. `step` is here because the schedule's
 * "Run for" field counts in half hours; everything else leaves it alone. */
export interface FieldProps {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "number";
  suffix?: string;
  min?: number;
  step?: number;
  disabled?: boolean;
  placeholder?: string;
  list?: string;
}

export function Field({
  label,
  id,
  value,
  onChange,
  type = "text",
  suffix,
  min,
  step,
  disabled = false,
  placeholder,
  list,
}: FieldProps) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-[12px] text-muted">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        min={min}
        step={step}
        list={list}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 w-24 rounded-[6px] border border-line bg-panel-2 px-2 font-mono text-[13px] tabular-nums text-text disabled:cursor-not-allowed disabled:opacity-50"
      />
      {suffix !== undefined && <span className="text-[12px] text-muted">{suffix}</span>}
    </div>
  );
}
```

- [ ] **Step 4: Run them to confirm they pass**

```bash
cd <repo>/brawlfarm/web
pnpm test src/lib/states.test.ts src/components
```

Expected: PASS, 6 files and 20 tests.

- [ ] **Step 5: Write the failing tests for Toast, Drawer, ErrorBlock and Thumb**

`brawlfarm/web/src/test/renderWithProviders.tsx` first, because the component tests use it:

```tsx
/**
 * render() with the two providers every screen needs: a fresh query client per test (no
 * retries, no cache carried between cases) and a MemoryRouter so Link and useParams work
 * without a browser history.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type RenderResult, render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router";

export function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: ReactElement,
  options: { route?: string; client?: QueryClient } = {},
): RenderResult & { client: QueryClient } {
  const client = options.client ?? testQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[options.route ?? "/"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return { ...render(ui, { wrapper }), client };
}
```

`brawlfarm/web/src/components/ui/Toast.test.tsx`:

```tsx
/** One toast visible at a time, a life the caller can lengthen, and an Undo that both
 * runs the callback and closes the toast. */
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "./Toast";
import { resetToasts, toast } from "../../lib/toast";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  resetToasts();
  vi.useRealTimers();
});

describe("Toaster", () => {
  it("shows one message at a time and moves on when the first expires", () => {
    render(<Toaster />);
    act(() => {
      toast("Started Pie64");
      toast("Restarting Pie64");
    });
    expect(screen.getByText("Started Pie64")).toBeInTheDocument();
    expect(screen.queryByText("Restarting Pie64")).not.toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText("Started Pie64")).not.toBeInTheDocument();
    expect(screen.getByText("Restarting Pie64")).toBeInTheDocument();
  });

  it("keeps an undoable toast up for 6 s and runs the undo when clicked", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const undo = vi.fn();
    render(<Toaster />);
    act(() => {
      toast("Stopping Pie64 after this match", { undo });
    });
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.getByText("Stopping Pie64 after this match")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(undo).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Stopping Pie64 after this match")).not.toBeInTheDocument();
  });

  it("announces politely and offers no Undo when there is nothing to undo", () => {
    render(<Toaster />);
    act(() => {
      toast("Plan saved");
    });
    expect(screen.getByText("Plan saved").closest("[aria-live]")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });

  it("renders nothing at all when the queue is empty", () => {
    const { container } = render(<Toaster />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

`brawlfarm/web/src/components/ui/Drawer.test.tsx`:

```tsx
/** The alerts drawer's frame: a modal dialog that traps focus, closes on Escape and
 * closes when the scrim is clicked. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { Drawer } from "./Drawer";

describe("Drawer", () => {
  it("renders nothing while closed", () => {
    const { container } = render(
      <Drawer open={false} onClose={vi.fn()} title="Alerts">
        <p>rows</p>
      </Drawer>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("is a modal dialog named by its title, with its actions in the header", () => {
    render(
      <Drawer open onClose={vi.fn()} title="Alerts" actions={<Button variant="text">Dismiss all</Button>}>
        <p>rows</p>
      </Drawer>,
    );
    const dialog = screen.getByRole("dialog", { name: "Alerts" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "Dismiss all" })).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(
      <Drawer open onClose={onClose} title="Alerts">
        <p>rows</p>
      </Drawer>,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps Tab inside the panel", async () => {
    render(
      <Drawer open onClose={vi.fn()} title="Alerts">
        <Button variant="text">Dismiss</Button>
      </Drawer>,
    );
    const close = screen.getByRole("button", { name: "Close" });
    const dismiss = screen.getByRole("button", { name: "Dismiss" });
    // The header, Close included, comes before the children in the DOM, so Tab reaches
    // Close first and wraps from Dismiss back to it.
    await userEvent.tab();
    expect(close).toHaveFocus();
    await userEvent.tab();
    expect(dismiss).toHaveFocus();
    await userEvent.tab();
    expect(close).toHaveFocus();
  });
});
```

`brawlfarm/web/src/components/ui/ErrorBlock.test.tsx`:

```tsx
/** Failures the user can act on: the API's own sentence, the validation lines, or the
 * panel's wording when the server is gone. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ErrorBlock } from "./ErrorBlock";
import { ApiError } from "../../api/client";

describe("ErrorBlock", () => {
  it("prints the API's detail verbatim", () => {
    render(<ErrorBlock error={new ApiError(409, "Stop Pie64 before removing it")} />);
    expect(screen.getByText("Stop Pie64 before removing it")).toBeInTheDocument();
  });

  it("prints one line per validation error", () => {
    render(
      <ErrorBlock
        error={
          new ApiError(422, "Validation failed", [
            "body.goal_trophies: Input should be greater than or equal to 0",
          ])
        }
      />,
    );
    expect(screen.getByText("Validation failed")).toBeInTheDocument();
    expect(
      screen.getByText("body.goal_trophies: Input should be greater than or equal to 0"),
    ).toBeInTheDocument();
  });

  it("says the panel cannot reach the server when fetch itself failed", () => {
    render(
      <ErrorBlock error={new ApiError(0, "The panel cannot reach brawlfarm. Is it still running?")} />,
    );
    expect(
      screen.getByText("The panel cannot reach brawlfarm. Is it still running?"),
    ).toBeInTheDocument();
  });

  it("offers Retry only when it was given something to retry", async () => {
    const onRetry = vi.fn();
    const { rerender } = render(<ErrorBlock error={new ApiError(503, "adb did not answer")} />);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    rerender(<ErrorBlock error={new ApiError(503, "adb did not answer")} onRetry={onRetry} />);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("copes with something that is not an ApiError at all", () => {
    render(<ErrorBlock error={new Error("boom")} />);
    expect(screen.getByText("boom")).toBeInTheDocument();
    render(<ErrorBlock error={{ weird: true }} />);
    expect(screen.getByText("Request failed")).toBeInTheDocument();
  });
});
```

`brawlfarm/web/src/components/ui/Thumb.test.tsx`:

```tsx
/** The screenshot box: it fetches, it ages, it retries, it never leaks an object URL,
 * and its image is marked private so the pull request's screenshots can blur it. */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Thumb } from "./Thumb";
import { jsonResponse, pngResponse, stubFetch } from "../../test/http";

const created: string[] = [];
const revoked: string[] = [];

beforeEach(() => {
  created.length = 0;
  revoked.length = 0;
  let counter = 0;
  URL.createObjectURL = (() => {
    counter += 1;
    const url = `blob:fake/${counter}`;
    created.push(url);
    return url;
  }) as typeof URL.createObjectURL;
  URL.revokeObjectURL = ((url: string) => {
    revoked.push(url);
  }) as typeof URL.revokeObjectURL;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("Thumb", () => {
  it("fetches the screen, shows its age and marks the image private", async () => {
    const { calls } = stubFetch(() => pngResponse());
    render(<Thumb name="Pie64" refreshMs={false} />);
    const image = await screen.findByRole("img", { name: "Pie64 screen" });
    expect(image).toHaveAttribute("src", "blob:fake/1");
    expect(image).toHaveAttribute("data-private");
    expect(screen.getByText("0 s ago")).toBeInTheDocument();
    expect(calls[0].url).toBe("/api/instances/Pie64/screenshot.png");
  });

  it("refreshes on the interval and revokes the url it replaced", async () => {
    vi.useFakeTimers();
    const { calls } = stubFetch(() => pngResponse());
    render(<Thumb name="Pie64" refreshMs={15000} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(calls).toHaveLength(1);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(calls).toHaveLength(2);
    expect(revoked).toEqual(["blob:fake/1"]);
    expect(created).toEqual(["blob:fake/1", "blob:fake/2"]);
  });

  it("fetches again as soon as refreshKey changes", async () => {
    const { calls } = stubFetch(() => pngResponse());
    const { rerender } = render(<Thumb name="Pie64" refreshMs={false} refreshKey={0} />);
    await screen.findByRole("img", { name: "Pie64 screen" });
    expect(calls).toHaveLength(1);
    rerender(<Thumb name="Pie64" refreshMs={false} refreshKey={1} />);
    await vi.waitFor(() => {
      expect(calls).toHaveLength(2);
    });
  });

  it("shows the failure detail in the box and retries 15 s later", async () => {
    vi.useFakeTimers();
    const { calls } = stubFetch(() => jsonResponse({ detail: "adb did not answer" }, 503));
    render(<Thumb name="Pie64" refreshMs={false} />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByText("Screenshot failed: adb did not answer")).toBeInTheDocument();
    expect(screen.getByText("Retrying in 15 s.")).toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(15000);
    });
    expect(calls).toHaveLength(2);
  });

  it("dims the image and captions it while the instance is on a break", async () => {
    stubFetch(() => pngResponse());
    render(<Thumb name="Pie64" refreshMs={false} dimmed caption="Break until 21:30" />);
    const image = await screen.findByRole("img", { name: "Pie64 screen" });
    expect(image.className).toContain("opacity-40");
    expect(screen.getByText("Break until 21:30")).toBeInTheDocument();
  });

  it("revokes its object url when it unmounts", async () => {
    stubFetch(() => pngResponse());
    const { unmount } = render(<Thumb name="Pie64" refreshMs={false} />);
    await screen.findByRole("img", { name: "Pie64 screen" });
    unmount();
    expect(revoked).toEqual(["blob:fake/1"]);
  });
});
```

- [ ] **Step 6: Run them to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test src/components/ui/Toast.test.tsx src/components/ui/Drawer.test.tsx src/components/ui/ErrorBlock.test.tsx src/components/ui/Thumb.test.tsx
```

Expected: FAIL, unresolved imports for `./Toast`, `./Drawer`, `./ErrorBlock`, `./Thumb`.

- [ ] **Step 7: Write Toast, Drawer, ErrorBlock and Thumb**

`brawlfarm/web/src/components/ui/Toast.tsx`:

```tsx
/**
 * The transient confirmation strip.
 *
 * Toaster shows the head of the queue in lib/toast.ts, so exactly one is visible and the
 * rest wait their turn. The hairline bar drains over the toast's own duration, which is
 * longer when an Undo is on offer because the user has a decision to make.
 */
import { useEffect, useState } from "react";

import { Button } from "./Button";
import { type ToastItem, dismissToast, useToasts } from "../../lib/toast";

const TICK_MS = 100;

export interface ToastProps {
  item: ToastItem;
}

export function Toast({ item }: ToastProps) {
  const [remaining, setRemaining] = useState(item.durationMs);

  useEffect(() => {
    const startedAt = Date.now();
    setRemaining(item.durationMs);
    const drain = setInterval(() => {
      setRemaining(Math.max(0, item.durationMs - (Date.now() - startedAt)));
    }, TICK_MS);
    const expire = setTimeout(() => {
      dismissToast(item.id);
    }, item.durationMs);
    return () => {
      clearInterval(drain);
      clearTimeout(expire);
    };
  }, [item.id, item.durationMs]);

  const onUndo = () => {
    dismissToast(item.id);
    void item.undo?.();
  };

  return (
    <div
      aria-live="polite"
      className="pointer-events-auto w-[320px] overflow-hidden rounded-[10px] border border-line bg-panel"
    >
      <div className="flex items-center gap-3 px-3 py-2">
        <span className="flex-1 text-[13px] text-text">{item.message}</span>
        {item.undo !== undefined && (
          <Button variant="text" size="sm" onClick={onUndo}>
            Undo
          </Button>
        )}
      </div>
      <div
        aria-hidden="true"
        className="h-px bg-accent"
        style={{ width: `${(remaining / item.durationMs) * 100}%` }}
      />
    </div>
  );
}

export function Toaster() {
  const toasts = useToasts();
  const current = toasts[0];
  if (current === undefined) return null;
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-50 flex justify-center">
      <Toast key={current.id} item={current} />
    </div>
  );
}
```

`brawlfarm/web/src/components/ui/Drawer.tsx`:

```tsx
/**
 * A right-side modal panel.
 *
 * Focus moves into the panel on open, Tab cycles inside it, Escape closes it, and focus
 * returns to whatever opened it. Written by hand rather than pulled from a library: this
 * is the only modal in the panel and it owes nothing to a dependency.
 */
import { type ReactNode, useEffect, useRef } from "react";

import { Button } from "./Button";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function Drawer({ open, onClose, title, children, actions }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    if (panel === null) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panel.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      opener?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40">
      <div aria-hidden="true" className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className="absolute right-0 top-0 flex h-full w-[360px] flex-col border-l border-line bg-panel outline-none"
      >
        <header className="flex h-[52px] shrink-0 items-center justify-between border-b border-line px-4">
          <h2 className="text-[15px] font-semibold">{title}</h2>
          <div className="flex items-center gap-2">
            {actions}
            <Button variant="text" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}
```

`brawlfarm/web/src/components/ui/ErrorBlock.tsx`:

```tsx
/**
 * A failure the user can read.
 *
 * The API's `detail` is printed verbatim, because it was written for a person: "adb did
 * not answer", "Stop Pie64 before removing it". A 422 adds one line per field. Anything
 * that is not an ApiError still gets a sentence rather than a stack trace.
 */
import { Button } from "./Button";
import { ApiError } from "../../api/client";

export interface ErrorBlockProps {
  error: unknown;
  onRetry?: () => void;
}

function describe(error: unknown): { detail: string; lines: string[] } {
  if (error instanceof ApiError) return { detail: error.detail, lines: error.lines };
  if (error instanceof Error) return { detail: error.message, lines: [] };
  return { detail: "Request failed", lines: [] };
}

export function ErrorBlock({ error, onRetry }: ErrorBlockProps) {
  const { detail, lines } = describe(error);
  return (
    <div className="rounded-[10px] border border-line bg-panel p-3">
      <p className="text-[13px] text-bad">{detail}</p>
      {lines.length > 0 && (
        <ul className="mt-1 space-y-0.5">
          {lines.map((line) => (
            <li key={line} className="font-mono text-[11px] text-muted">
              {line}
            </li>
          ))}
        </ul>
      )}
      {onRetry !== undefined && (
        <div className="mt-2">
          <Button variant="quiet" size="sm" onClick={onRetry}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}
```

`brawlfarm/web/src/components/ui/Thumb.tsx`:

```tsx
/**
 * The live screenshot box.
 *
 * Owns its own fetch loop instead of going through react-query: the body is a Blob, not
 * JSON, and every caller wants a different cadence (a Fleet card idles, the Instance page
 * refreshes every 15 s, both stop when the tab is hidden). Each frame becomes an object
 * URL, and the previous one is revoked the moment it is replaced -- an unrevoked blob is
 * a megabyte of retained memory per frame.
 *
 * A change of `refreshKey` fetches immediately: that is the Instance page's Refresh
 * button. The `<img>` carries data-private so the pull request's screenshots can blur it.
 */
import { type ReactNode, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import { fetchScreenshot } from "../../api/screens";
import { age } from "../../lib/time";

const ERROR_RETRY_MS = 15000;
const AGE_TICK_MS = 1000;

export interface ThumbProps {
  name: string;
  refreshMs: number | false;
  dimmed?: boolean;
  caption?: string;
  overlay?: ReactNode;
  refreshKey?: number;
}

export function Thumb({
  name,
  refreshMs,
  dimmed = false,
  caption,
  overlay,
  refreshKey = 0,
}: ThumbProps) {
  const [url, setUrl] = useState<string | null>(null);
  const [takenAt, setTakenAt] = useState<number | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const schedule = (delay: number | false) => {
      if (delay === false || cancelled) return;
      timer = setTimeout(() => {
        void load();
      }, delay);
    };

    const load = async (): Promise<void> => {
      try {
        const blob = await fetchScreenshot(name);
        if (cancelled) return;
        if (urlRef.current !== null) URL.revokeObjectURL(urlRef.current);
        urlRef.current = URL.createObjectURL(blob);
        setUrl(urlRef.current);
        setTakenAt(Date.now());
        setNow(Date.now());
        setError(null);
        schedule(refreshMs);
      } catch (failure) {
        if (cancelled) return;
        setError(failure instanceof ApiError ? failure : new ApiError(0, String(failure)));
        schedule(ERROR_RETRY_MS);
      }
    };

    void load();
    return () => {
      cancelled = true;
      if (timer !== null) clearTimeout(timer);
    };
  }, [name, refreshMs, refreshKey]);

  // Revoking belongs to unmount alone: the effect above re-runs on every prop change and
  // must not throw away the frame it is about to keep showing.
  useEffect(
    () => () => {
      if (urlRef.current !== null) {
        URL.revokeObjectURL(urlRef.current);
        urlRef.current = null;
      }
    },
    [],
  );

  useEffect(() => {
    if (takenAt === null) return;
    const tick = setInterval(() => setNow(Date.now()), AGE_TICK_MS);
    return () => clearInterval(tick);
  }, [takenAt]);

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-[6px] border border-line bg-panel-2">
      {url !== null && (
        <img
          src={url}
          alt={`${name} screen`}
          data-private=""
          className={`h-full w-full object-cover transition-opacity duration-[120ms] ${dimmed ? "opacity-40" : ""}`}
        />
      )}
      {error !== null && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 p-3 text-center">
          <span className="text-[13px] text-bad">{`Screenshot failed: ${error.detail}`}</span>
          <span className="text-[12px] text-muted">Retrying in 15 s.</span>
        </div>
      )}
      {caption !== undefined && (
        <div className="absolute inset-0 flex items-center justify-center text-[13px] text-text">
          {caption}
        </div>
      )}
      {overlay !== undefined && <div className="absolute left-2 top-2">{overlay}</div>}
      {takenAt !== null && error === null && (
        <span className="absolute right-2 top-2 font-mono text-[11px] tabular-nums text-muted">
          {age(takenAt, now)}
        </span>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Run the whole suite, typecheck, build**

```bash
cd <repo>/brawlfarm/web
pnpm test
pnpm typecheck
pnpm build
```

Expected: PASS, 16 files and 55 tests; `tsc` silent; the build succeeds.

- [ ] **Step 9: Commit**

```bash
cd <repo>
uv run python tools/scrub_check.py
git add brawlfarm/web/src/components brawlfarm/web/src/lib/states.ts brawlfarm/web/src/lib/states.test.ts brawlfarm/web/src/test/renderWithProviders.tsx
git commit -m "feat(web): the ten ui primitives and the state vocabulary

lib/states.ts is the single place a state, a phase, an alert kind or a feed
category becomes a word and a tone, so no screen invents its own wording. Every
toned dot also carries data-tone, which is how a test asserts \"word plus colour\"
without asserting a class name.

Thumb owns its own fetch loop rather than going through react-query: the body is
a Blob and every caller wants a different cadence. It revokes the object URL it
replaces and the one it holds at unmount, retries a failed screencap every 15 s
showing the API's own detail, and marks its image data-private so the pull
request's screenshots can blur it.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 4: The shell, the routes and the live wiring

The frame every page sits in, and the one place the event stream is turned into cache updates. After this task the panel is navigable: the rail lists the instances, the top bar reports the connection and the unread alert count, the drawer lists and dismisses alerts, and the theme follows `app.theme`. The Fleet and Instance routes mount placeholders that tasks 6 and 8 replace.

**Files:**
- Create: `brawlfarm/web/src/app/Shell.tsx`
- Create: `brawlfarm/web/src/app/Rail.tsx`
- Create: `brawlfarm/web/src/app/TopBar.tsx`
- Create: `brawlfarm/web/src/app/AlertsDrawer.tsx`
- Create: `brawlfarm/web/src/app/Placeholder.tsx`
- Create: `brawlfarm/web/src/app/alertsDrawer.ts`
- Modify: `brawlfarm/web/src/App.tsx` (replace the task 1 body entirely)
- Modify: `brawlfarm/web/src/App.test.tsx` (replace the task 1 smoke test entirely)
- Test: `brawlfarm/web/src/app/Rail.test.tsx`
- Test: `brawlfarm/web/src/app/TopBar.test.tsx`
- Test: `brawlfarm/web/src/app/AlertsDrawer.test.tsx`

**Interfaces:**
- Consumes: task 2's `createQueryClient`, `queryKeys`, `useInstances`, `listAlerts`, `dismissAlert`, `dismissAllAlerts`, `getSettings`, `subscribe`, `onReconnect`, `useConnection`, `toast`, `hhmm`; task 3's `Button`, `Chip`, `Drawer`, `Toaster`, `TONE_DOT`, `stateTone`, `alertKindLabel`, `alertKindTone`, `renderWithProviders`.
- Produces:
  - `App()` -- the whole tree: `QueryClientProvider`, `BrowserRouter`, the theme bootstrap, the SSE handlers, `Shell`, the four routes, `Toaster`
  - `Shell({ children: ReactNode })`
  - `Rail()`
  - `TopBar()`, plus `pageTitle(pathname: string): string`
  - `AlertsDrawer()`
  - `Placeholder({ title: string; body: string })`
  - `app/alertsDrawer.ts`: `openAlertsDrawer(): void`, `closeAlertsDrawer(): void`, `useAlertsDrawerOpen(): boolean`
- Consumed by: task 6 (`Placeholder` is swapped for `Fleet`; `AlertStrip` calls `openAlertsDrawer`), task 8 (the `/instances/:name` placeholder is swapped for `Instance`). The `feed` event kind is deliberately not subscribed to here: the `Feed` component (task 9) installs its own handler, because only it knows which chip a record belongs in and it is the only screen that can show one.

- [ ] **Step 1: Write the failing tests for the rail, the top bar and the drawer**

`brawlfarm/web/src/app/Rail.test.tsx`:

```tsx
/** The rail: the wordmark, three sections with soon tags on the two that are not built,
 * and every instance with a dot in its state's colour. */
import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Rail } from "./Rail";
import { jsonResponse, stubFetch } from "../test/http";
import { makeInstance } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubInstances(): void {
  stubFetch(() =>
    jsonResponse({
      instances: [
        makeInstance({ name: "Pie64", state: "farming" }),
        makeInstance({ name: "Pie64_1", adb_port: 5565, state: "offline" }),
        makeInstance({ name: "Pie64_3", adb_port: 5585, state: "scheduled_break" }),
      ],
    }),
  );
}

describe("Rail", () => {
  it("shows the wordmark and tags the sections that are not built yet", async () => {
    stubInstances();
    renderWithProviders(<Rail />);
    expect(screen.getByText("brawlfarm")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fleet" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: /Stats/ })).toHaveTextContent("Stats soon");
    expect(screen.getByRole("link", { name: /Settings/ })).toHaveTextContent("Settings soon");
    expect(await screen.findByText("Instances")).toBeInTheDocument();
  });

  it("gives every instance a dot in its state's tone", async () => {
    stubInstances();
    renderWithProviders(<Rail />);
    const pie64 = await screen.findByRole("link", { name: /Pie64$/ });
    expect(pie64).toHaveAttribute("href", "/instances/Pie64");
    expect(pie64.querySelector("[data-tone]")).toHaveAttribute("data-tone", "ok");
    expect(
      screen.getByRole("link", { name: /Pie64_1/ }).querySelector("[data-tone]"),
    ).toHaveAttribute("data-tone", "bad");
    expect(
      screen.getByRole("link", { name: /Pie64_3/ }).querySelector("[data-tone]"),
    ).toHaveAttribute("data-tone", "idle");
  });

  it("marks the page you are on", async () => {
    stubInstances();
    renderWithProviders(<Rail />, { route: "/instances/Pie64_1" });
    expect(await screen.findByRole("link", { name: /Pie64_1/ })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "Fleet" })).not.toHaveAttribute("aria-current");
  });
});
```

`brawlfarm/web/src/app/TopBar.test.tsx`:

The connection states themselves are already pinned by task 2's `useEvents` tests, so `TopBar` only has to prove it renders whatever `useConnection` reports and that the badge tracks `unread`. The store has no non-hook getter, so a one-line `renderHook` reader stands in for one.

```tsx
/** The top bar: which page you are on, whether the stream is live, and how many alerts
 * are waiting. */
import { renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TopBar, pageTitle } from "./TopBar";
import { closeAlertsDrawer, useAlertsDrawerOpen } from "./alertsDrawer";
import { jsonResponse, stubFetch } from "../test/http";
import { makeAlert } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

function alertsDrawerIsOpen(): boolean {
  return renderHook(() => useAlertsDrawerOpen()).result.current;
}

afterEach(() => {
  closeAlertsDrawer();
  vi.unstubAllGlobals();
});

describe("pageTitle", () => {
  it("names the three sections and uses the instance name on its own page", () => {
    expect(pageTitle("/")).toBe("Fleet");
    expect(pageTitle("/stats")).toBe("Stats");
    expect(pageTitle("/settings")).toBe("Settings");
    expect(pageTitle("/instances/Pie64_1")).toBe("Pie64_1");
  });
});

describe("TopBar", () => {
  it("shows the page title and the connection pill", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<TopBar />, { route: "/instances/Pie64" });
    expect(screen.getByRole("heading", { name: "Pie64" })).toBeInTheDocument();
    // Nothing has subscribed to the stream in this test, so it is still connecting.
    expect(screen.getByText("Connecting")).toBeInTheDocument();
    expect(screen.getByText("Connecting").closest("[data-tone]")).toHaveAttribute(
      "data-tone",
      "idle",
    );
  });

  it("badges the Alerts button with the unread count and hides it at zero", async () => {
    stubFetch(() => jsonResponse({ alerts: [makeAlert(), makeAlert({ id: 2 })], unread: 2 }));
    const { client } = renderWithProviders(<TopBar />);
    expect(await screen.findByText("2")).toBeInTheDocument();
    client.setQueryData(["alerts"], { alerts: [], unread: 0 });
    await vi.waitFor(() => {
      expect(screen.queryByText("2")).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Alerts/ })).toBeInTheDocument();
  });

  it("opens the drawer store when Alerts is clicked", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<TopBar />);
    expect(alertsDrawerIsOpen()).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: /Alerts/ }));
    expect(alertsDrawerIsOpen()).toBe(true);
  });
});
```

`brawlfarm/web/src/app/AlertsDrawer.test.tsx`. Two readers sit beside the imports, for the same reason: the toast queue and the drawer store are read through hooks.

```tsx
/** The drawer: newest first, one Dismiss per row, one Dismiss all in the header, and a
 * sentence when there is nothing to show. */
import { renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AlertsDrawer } from "./AlertsDrawer";
import { closeAlertsDrawer, openAlertsDrawer } from "./alertsDrawer";
import { resetToasts, useToasts } from "../lib/toast";
import { jsonResponse, stubFetch } from "../test/http";
import { makeAlert } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

beforeEach(() => {
  openAlertsDrawer();
});

afterEach(() => {
  closeAlertsDrawer();
  resetToasts();
  vi.unstubAllGlobals();
});

const ALERTS = [
  makeAlert({
    id: 9,
    ts: "2026-09-11T19:42:00",
    instance: "Pie64_1",
    kind: "offline",
    title: "Instance offline",
    detail: "misses=3",
  }),
  makeAlert({
    id: 8,
    ts: "2026-09-11T18:10:00",
    instance: "Pie64",
    kind: "crash",
    title: "Bot crashed",
    detail: "err=adb did not answer",
  }),
];

describe("AlertsDrawer", () => {
  it("lists the alerts newest first with kind, instance, time and detail", async () => {
    stubFetch(() => jsonResponse({ alerts: ALERTS, unread: 2 }));
    renderWithProviders(<AlertsDrawer />);
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Offline");
    expect(rows[0]).toHaveTextContent("Pie64_1");
    expect(rows[0]).toHaveTextContent("19:42");
    expect(rows[0]).toHaveTextContent("misses=3");
    expect(rows[0].querySelector("[data-tone]")).toHaveAttribute("data-tone", "bad");
    expect(rows[1]).toHaveTextContent("Crash");
  });

  it("dismisses one row", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : new Response(null, { status: 204 }),
    );
    renderWithProviders(<AlertsDrawer />);
    const rows = await screen.findAllByRole("listitem");
    await userEvent.click(within(rows[0]).getByRole("button", { name: "Dismiss" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/alerts/9/dismiss");
    });
  });

  it("dismisses all of them and says so", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : new Response(null, { status: 204 }),
    );
    renderWithProviders(<AlertsDrawer />);
    await userEvent.click(await screen.findByRole("button", { name: "Dismiss all" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/alerts/dismiss-all");
    });
    expect(toastMessages()).toContain("Alerts dismissed");
  });

  it("says what the drawer is for when it is empty", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<AlertsDrawer />);
    expect(
      await screen.findByText(
        "No alerts. Offline instances, crashes and wrong-mode recoveries show up here.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dismiss all" })).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the three files to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test src/app
```

Expected: FAIL, unresolved imports for `./Rail`, `./TopBar`, `./AlertsDrawer` and `./alertsDrawer`.

- [ ] **Step 3: Write the drawer store, the rail, the top bar and the drawer**

The rail puts a literal space between a section's label and its `soon` tag. That space is
deliberate: the flex gap is visual only, so without it the link's text content, and a screen
reader reading the link, run the two words together as "Statssoon". `Rail.test.tsx` asserts
the spaced form with `toHaveTextContent("Stats soon")`.

`brawlfarm/web/src/app/alertsDrawer.ts`:

```ts
/**
 * Whether the alerts drawer is open.
 *
 * A module store rather than context: the Fleet page's alert strip opens the same drawer
 * the top bar's button does, and the two have no common parent below Shell. Same shape as
 * lib/toast.ts, for the same reason.
 */
import { useSyncExternalStore } from "react";

let open = false;
const listeners = new Set<() => void>();

function set(next: boolean): void {
  if (open === next) return;
  open = next;
  for (const listener of [...listeners]) listener();
}

export function openAlertsDrawer(): void {
  set(true);
}

export function closeAlertsDrawer(): void {
  set(false);
}

function subscribeOpen(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useAlertsDrawerOpen(): boolean {
  return useSyncExternalStore(
    subscribeOpen,
    () => open,
    () => open,
  );
}
```

`brawlfarm/web/src/app/Placeholder.tsx`:

```tsx
/** A page that is not built yet: its name, and one sentence saying when it arrives. */
export interface PlaceholderProps {
  title: string;
  body: string;
}

export function Placeholder({ title, body }: PlaceholderProps) {
  return (
    <section className="max-w-[560px]">
      <h1 className="text-[28px] font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-[13px] text-muted">{body}</p>
    </section>
  );
}
```

`brawlfarm/web/src/app/Rail.tsx`:

```tsx
/**
 * The left rail: wordmark, sections, instances.
 *
 * Under 820 px it becomes a top row of section links and the instance list hides -- on a
 * phone the fleet grid is the navigation. NavLink is used rather than Link so the current
 * page gets aria-current="page" without the component tracking the route itself.
 */
import { NavLink } from "react-router";

import { useInstances } from "../api/useInstances";
import { TONE_DOT, stateTone } from "../lib/states";

const SECTIONS: { to: string; label: string; soon: boolean }[] = [
  { to: "/", label: "Fleet", soon: false },
  { to: "/stats", label: "Stats", soon: true },
  { to: "/settings", label: "Settings", soon: true },
];

function linkClass(isActive: boolean): string {
  return `flex items-center gap-2 rounded-[6px] border-l-2 px-2 py-1.5 text-[13px] transition-colors duration-[120ms] ${
    isActive ? "border-accent bg-panel-2 text-text" : "border-transparent text-muted hover:text-text"
  }`;
}

export function Rail() {
  const { data: instances } = useInstances();

  return (
    <nav
      aria-label="Sections"
      className="border-b border-line bg-panel min-[820px]:border-b-0 min-[820px]:border-r"
    >
      <div className="flex h-[52px] items-center gap-2 px-4">
        <span aria-hidden="true" className="h-2.5 w-2.5 rounded-[2px] bg-accent" />
        <span className="text-[15px] font-semibold tracking-tight">brawlfarm</span>
      </div>

      <ul className="flex gap-1 px-2 pb-2 min-[820px]:block min-[820px]:space-y-0.5">
        {SECTIONS.map((section) => (
          <li key={section.to}>
            <NavLink
              to={section.to}
              end={section.to === "/"}
              className={({ isActive }) => linkClass(isActive)}
            >
              <span className="flex-1">{section.label}</span>
              {section.soon && <> <span className="text-[11px] text-muted">soon</span></>}
            </NavLink>
          </li>
        ))}
      </ul>

      <div className="hidden min-[820px]:block">
        <p className="px-3 pb-1 pt-3 text-[11px] uppercase tracking-wide text-muted">Instances</p>
        <ul className="space-y-0.5 px-2 pb-2">
          {(instances ?? []).map((inst) => {
            const tone = stateTone(inst.state);
            return (
              <li key={inst.name}>
                <NavLink
                  to={`/instances/${inst.name}`}
                  className={({ isActive }) => linkClass(isActive)}
                >
                  <span
                    data-tone={tone}
                    aria-hidden="true"
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[tone]}`}
                  />
                  <span className="truncate font-mono text-[12px]">{inst.name}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
```

`brawlfarm/web/src/app/TopBar.tsx`:

```tsx
/**
 * The top bar: where you are, whether the panel is hearing from the server, and how many
 * alerts are waiting. The connection pill is the only place the SSE state surfaces, so
 * "Reconnecting" there is the panel admitting it may be showing stale data.
 */
import { useQuery } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useLocation } from "react-router";

import { openAlertsDrawer } from "./alertsDrawer";
import { listAlerts } from "../api/alerts";
import { queryKeys } from "../api/queries";
import { Button } from "../components/ui/Button";
import { type Connection, useConnection } from "../live/useEvents";
import { TONE_DOT, type Tone } from "../lib/states";

const SECTION_TITLES: Record<string, string> = {
  "/": "Fleet",
  "/stats": "Stats",
  "/settings": "Settings",
};

const INSTANCE_PREFIX = "/instances/";

const CONNECTION_PILL: Record<Connection, { label: string; tone: Tone }> = {
  live: { label: "Live", tone: "ok" },
  reconnecting: { label: "Reconnecting", tone: "warn" },
  connecting: { label: "Connecting", tone: "idle" },
};

export function pageTitle(pathname: string): string {
  if (pathname.startsWith(INSTANCE_PREFIX)) return pathname.slice(INSTANCE_PREFIX.length);
  return SECTION_TITLES[pathname] ?? "brawlfarm";
}

export function TopBar() {
  const { pathname } = useLocation();
  const connection = useConnection();
  const { data: alerts } = useQuery({ queryKey: queryKeys.alerts(), queryFn: listAlerts });
  const unread = alerts?.unread ?? 0;
  const pill = CONNECTION_PILL[connection];

  return (
    <header className="flex h-[52px] shrink-0 items-center gap-3 border-b border-line bg-panel px-4">
      <h1 className="flex-1 truncate text-[20px] font-semibold tracking-tight">
        {pageTitle(pathname)}
      </h1>

      <span
        data-tone={pill.tone}
        className="inline-flex items-center gap-1.5 rounded-[6px] border border-line bg-panel-2 px-2 py-0.5 text-[11px] text-muted"
      >
        <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${TONE_DOT[pill.tone]}`} />
        {pill.label}
      </span>

      <Button variant="quiet" size="sm" onClick={openAlertsDrawer}>
        <Bell size={16} strokeWidth={1.6} aria-hidden="true" />
        Alerts
        {unread > 0 && (
          <span className="ml-1 rounded-[6px] bg-accent px-1.5 font-mono text-[11px] tabular-nums text-accent-ink">
            {unread}
          </span>
        )}
      </Button>
    </header>
  );
}
```

`brawlfarm/web/src/app/AlertsDrawer.tsx`:

```tsx
/**
 * The alerts drawer.
 *
 * Reads the same ["alerts"] query the top bar's badge does, so dismissing a row updates
 * both. Dismissing is a plain call plus an invalidation rather than an optimistic write:
 * the list is short, the call is local, and a wrong guess here would hide an alert that
 * is still live.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { closeAlertsDrawer, useAlertsDrawerOpen } from "./alertsDrawer";
import { dismissAlert, dismissAllAlerts, listAlerts } from "../api/alerts";
import { queryKeys } from "../api/queries";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { Drawer } from "../components/ui/Drawer";
import { alertKindLabel, alertKindTone } from "../lib/states";
import { hhmm } from "../lib/time";
import { toast } from "../lib/toast";

export function AlertsDrawer() {
  const open = useAlertsDrawerOpen();
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: queryKeys.alerts(), queryFn: listAlerts });
  const alerts = data?.alerts ?? [];

  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.alerts() });
  };

  const onDismiss = (id: number) => {
    void dismissAlert(id).then(refresh);
  };

  const onDismissAll = () => {
    void dismissAllAlerts().then(() => {
      refresh();
      toast("Alerts dismissed");
    });
  };

  return (
    <Drawer
      open={open}
      onClose={closeAlertsDrawer}
      title="Alerts"
      actions={
        alerts.length > 0 ? (
          <Button variant="text" size="sm" onClick={onDismissAll}>
            Dismiss all
          </Button>
        ) : undefined
      }
    >
      {alerts.length === 0 ? (
        <p className="p-4 text-[13px] text-muted">
          No alerts. Offline instances, crashes and wrong-mode recoveries show up here.
        </p>
      ) : (
        <ul className="divide-y divide-line">
          {alerts.map((alert) => (
            <li key={alert.id} className="flex flex-col gap-1 p-3">
              <div className="flex items-center gap-2">
                <Chip tone={alertKindTone(alert.kind)}>{alertKindLabel(alert.kind)}</Chip>
                <span className="font-mono text-[12px] text-text">{alert.instance}</span>
                <span className="flex-1 text-right font-mono text-[11px] tabular-nums text-muted">
                  {hhmm(alert.ts)}
                </span>
              </div>
              <p className="text-[13px] text-muted">{alert.detail}</p>
              <div>
                <Button variant="text" size="sm" onClick={() => onDismiss(alert.id)}>
                  Dismiss
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
```

- [ ] **Step 4: Run the three files to confirm they pass**

```bash
cd <repo>/brawlfarm/web
pnpm test src/app
```

Expected: PASS, 3 files and 10 tests.

- [ ] **Step 5: Write the failing test for App**

Replace `brawlfarm/web/src/App.test.tsx` entirely:

```tsx
/** The whole tree: the four routes, the theme bootstrap, and the live handlers that turn
 * server-sent events into cache updates. */
import { act, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { closeAlertsDrawer } from "./app/alertsDrawer";
import { closeEvents, setEventSourceFactory } from "./live/useEvents";
import { resetToasts } from "./lib/toast";
import { jsonResponse, pngResponse, stubFetch } from "./test/http";
import { makeInstance } from "./test/fixtures";
import { render } from "@testing-library/react";

class FakeEventSource {
  static last: FakeEventSource | null = null;

  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private readonly listeners = new Map<string, Set<(event: Event) => void>>();

  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }

  addEventListener(kind: string, listener: (event: Event) => void): void {
    const set = this.listeners.get(kind) ?? new Set<(event: Event) => void>();
    set.add(listener);
    this.listeners.set(kind, set);
  }

  removeEventListener(kind: string, listener: (event: Event) => void): void {
    this.listeners.get(kind)?.delete(listener);
  }

  close(): void {}

  connect(): void {
    this.onopen?.();
  }

  emit(kind: string, data: unknown, id: number): void {
    const event = new MessageEvent(kind, { data: JSON.stringify(data), lastEventId: String(id) });
    for (const listener of [...(this.listeners.get(kind) ?? [])]) listener(event);
  }
}

function stubApi(theme: "system" | "dark" | "light" = "system"): { calls: { url: string }[] } {
  return stubFetch((url) => {
    if (url === "/api/settings") {
      return jsonResponse({
        app: { port: 8765, theme },
        connection: { adb_path: "adb.exe", brawl_api_token: "never-render-me" },
      });
    }
    if (url === "/api/instances") return jsonResponse({ instances: [makeInstance()] });
    if (url === "/api/alerts") return jsonResponse({ alerts: [], unread: 0 });
    if (url.endsWith("screenshot.png")) return pngResponse();
    throw new Error(`unstubbed request: ${url}`);
  });
}

beforeEach(() => {
  FakeEventSource.last = null;
  setEventSourceFactory((url) => new FakeEventSource(url) as unknown as EventSource);
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  closeEvents();
  setEventSourceFactory(null);
  closeAlertsDrawer();
  resetToasts();
  resetTheme();
  vi.unstubAllGlobals();
});

function resetTheme(): void {
  delete document.documentElement.dataset.theme;
}

describe("App", () => {
  it("mounts the shell and the Fleet route", async () => {
    stubApi();
    render(<App />);
    expect(screen.getByText("brawlfarm")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Pie64/ })).toBeInTheDocument();
  });

  it("renders the two placeholder pages with their copy", async () => {
    stubApi();
    window.history.pushState({}, "", "/stats");
    render(<App />);
    expect(await screen.findByText("Stats arrive in phase 6.")).toBeInTheDocument();
  });

  it("applies the stored theme and never renders the API token", async () => {
    stubApi("light");
    render(<App />);
    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe("light");
    });
    expect(document.body.innerHTML).not.toContain("never-render-me");
  });

  it("leaves the theme to the operating system when the setting says system", async () => {
    stubApi("system");
    render(<App />);
    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBeUndefined();
    });
  });

  it("refetches the instances when an instance event arrives", async () => {
    vi.useFakeTimers();
    const { calls } = stubApi();
    render(<App />);
    await vi.waitFor(() => {
      expect(calls.filter((call) => call.url === "/api/instances")).toHaveLength(1);
    });
    act(() => {
      FakeEventSource.last?.connect();
      FakeEventSource.last?.emit("instance", { name: "Pie64", state: "stopping" }, 1);
      FakeEventSource.last?.emit("instance", { name: "Pie64", state: "stopped" }, 2);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    expect(calls.filter((call) => call.url === "/api/instances")).toHaveLength(2);
    vi.useRealTimers();
  });

  it("refetches the alerts when an alert event arrives", async () => {
    const { calls } = stubApi();
    render(<App />);
    await vi.waitFor(() => {
      expect(calls.filter((call) => call.url === "/api/alerts")).toHaveLength(1);
    });
    act(() => {
      FakeEventSource.last?.connect();
      FakeEventSource.last?.emit("alert", { id: 1, kind: "crash" }, 1);
    });
    await vi.waitFor(() => {
      expect(calls.filter((call) => call.url === "/api/alerts").length).toBeGreaterThan(1);
    });
  });
});
```

- [ ] **Step 6: Run it to confirm it fails**

```bash
cd <repo>/brawlfarm/web
pnpm test src/App.test.tsx
```

Expected: FAIL, the task 1 `App` renders no rail, so `findByRole("link", { name: /Pie64/ })` times out and the theme assertions fail.

- [ ] **Step 7: Write the shell and the new App**

`brawlfarm/web/src/app/Shell.tsx`:

```tsx
/**
 * The page frame: a 220 px rail, a 52 px top bar, and the content between them.
 *
 * Under 820 px the grid collapses to one column, which turns the rail into a top row of
 * section links (Rail hides its instance list at the same width).
 */
import type { ReactNode } from "react";

import { AlertsDrawer } from "./AlertsDrawer";
import { Rail } from "./Rail";
import { TopBar } from "./TopBar";

export interface ShellProps {
  children: ReactNode;
}

export function Shell({ children }: ShellProps) {
  return (
    <div className="min-h-screen bg-ground text-text">
      <div className="grid min-h-screen grid-cols-1 min-[820px]:grid-cols-[220px_1fr]">
        <Rail />
        <div className="flex min-w-0 flex-col">
          <TopBar />
          <main className="min-w-0 flex-1 p-4">{children}</main>
        </div>
      </div>
      <AlertsDrawer />
    </div>
  );
}
```

`brawlfarm/web/src/App.tsx` (replaces the task 1 file):

```tsx
/**
 * The panel's root.
 *
 * Providers, routes, and the two effects that make the whole thing live: the theme
 * bootstrap (one read of GET /api/settings, from which only app.theme is used) and the
 * event-stream handlers. `instance` and `alert` live here rather than in the screens so
 * a page that is not mounted still keeps its cache warm, and so there is exactly one
 * subscriber for each. `feed` is not one of them: a feed record only matters to the
 * screen that is showing that instance's feed, so the Feed component subscribes itself
 * (task 9) and this file stays out of it.
 *
 * The Fleet and Instance routes are placeholders until tasks 6 and 8 land.
 */
import { QueryClientProvider, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router";

import { Placeholder } from "./app/Placeholder";
import { Shell } from "./app/Shell";
import { createQueryClient, queryKeys } from "./api/queries";
import { getSettings } from "./api/settings";
import { Toaster } from "./components/ui/Toast";
import { onReconnect, subscribe } from "./live/useEvents";

/** A burst of state changes (a tick touching five instances) is one refetch, not five. */
const INSTANCE_DEBOUNCE_MS = 250;

function useThemeBootstrap(): void {
  const { data } = useQuery({ queryKey: queryKeys.settings(), queryFn: getSettings });
  const theme = data?.app.theme;

  useEffect(() => {
    if (theme === undefined) return;
    if (theme === "system") {
      delete document.documentElement.dataset.theme;
    } else {
      document.documentElement.dataset.theme = theme;
    }
  }, [theme]);
}

function useLiveHandlers(): void {
  const client = useQueryClient();

  useEffect(() => {
    let pending: ReturnType<typeof setTimeout> | null = null;

    const offInstance = subscribe("instance", () => {
      if (pending !== null) return;
      pending = setTimeout(() => {
        pending = null;
        void client.invalidateQueries({ queryKey: queryKeys.instances() });
      }, INSTANCE_DEBOUNCE_MS);
    });

    const offAlert = subscribe("alert", () => {
      void client.invalidateQueries({ queryKey: queryKeys.alerts() });
    });

    // The API only replays from the browser's own Last-Event-ID header, which our manual
    // reopen never sends, so a reconnect refetches instead of catching up.
    const offReconnect = onReconnect(() => {
      void client.invalidateQueries({ queryKey: queryKeys.instances() });
      void client.invalidateQueries({ queryKey: queryKeys.alerts() });
      void client.invalidateQueries({ queryKey: ["feed"] });
    });

    return () => {
      if (pending !== null) clearTimeout(pending);
      offInstance();
      offAlert();
      offReconnect();
    };
  }, [client]);
}

function Panel() {
  useThemeBootstrap();
  useLiveHandlers();

  return (
    <Shell>
      <Routes>
        <Route
          path="/"
          element={<Placeholder title="Fleet" body="The fleet grid arrives in the next commit." />}
        />
        <Route
          path="/instances/:name"
          element={
            <Placeholder title="Instance" body="The instance screen arrives in a later commit." />
          }
        />
        <Route path="/stats" element={<Placeholder title="Stats" body="Stats arrive in phase 6." />} />
        <Route
          path="/settings"
          element={
            <Placeholder
              title="Settings"
              body="Settings arrive in phase 5. Until then edit config.toml and restart brawlfarm."
            />
          }
        />
      </Routes>
    </Shell>
  );
}

export function App() {
  const [client] = useState(createQueryClient);

  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <Panel />
        <Toaster />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
```

- [ ] **Step 8: Run everything, typecheck, build**

```bash
cd <repo>/brawlfarm/web
pnpm test
pnpm typecheck
pnpm build
```

Expected: PASS, 19 files and 71 tests; `tsc` silent; the build succeeds.

- [ ] **Step 9: Commit**

```bash
cd <repo>
uv run python tools/scrub_check.py
git add brawlfarm/web/src/app brawlfarm/web/src/App.tsx brawlfarm/web/src/App.test.tsx
git commit -m "feat(web): the shell, the four routes and the live wiring

App subscribes to the two event kinds no single screen owns: instance events
invalidate the instance list on a 250 ms debounce so one tick touching five
instances is one refetch, and alert events invalidate the alert list. A
reconnect invalidates both plus every feed, because the API replays only from
the browser's own Last-Event-ID header and our manual reopen never sends one.
Feed records are left to the Feed component, which is the only thing that knows
which chip a record belongs in.

The theme bootstrap reads GET /api/settings once and uses app.theme alone. That
response also carries the Brawl Stars token in plaintext; AppSettings does not
model it and a test asserts it never reaches the DOM.

Fleet and the instance page are placeholders that the next two web tasks replace.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 5: Python -- dismiss-all, and a line number on every feed record

Two gaps the shell just ran into. The drawer's "Dismiss all" is N HTTP calls without a route for it. And a feed record carries only a second-resolution `ts`, so a line that arrives over SSE cannot be matched against the same line fetched by `GET .../feed`: the panel either drops real lines or shows duplicates. A 1-based line number within the session file fixes it, and the SSE envelope starts carrying the session name so the client knows which file the number belongs to.

`classify()` is not touched. No kind moves between chips, and `DROP`, `MATCHES`, `INTERRUPTS` and `ERRORS` keep exactly the membership they have today.

**Files:**
- Modify: `brawlfarm/api/alerts.py` (add `AlertStore.dismiss_all` after `dismiss`, and the route between `get_alerts` and `dismiss_alert`)
- Modify: `brawlfarm/api/feed.py` (`to_record` signature and body, `read_session` loop, a new `count_lines`, `FeedTailer._positions` / `poll_once` / `_read_new`)
- Modify: `tests/test_api_alerts.py` (two new tests)
- Modify: `tests/test_api_feed.py` (one new unit test, one new integration test, and the four existing assertions that pin the record shape)

**Interfaces:**
- Consumes: nothing from the web tasks; `EventBus.publish`, `AlertStore`, `S.instance_dir` as they are.
- Produces:
  - `AlertStore.dismiss_all() -> int` (how many were still unread) and `POST /api/alerts/dismiss-all -> 204`
  - `feed.count_lines(path: Path) -> int`
  - `feed.to_record(line: dict, seq: int) -> dict | None`, now returning `{"ts", "seq", "event", "category", "fields"}`
  - `feed.read_session(path, *, kind="all", limit=100)` and `feed.read_feed(inst_dir, kind="all", limit=100)` unchanged in signature, with `seq` on every record
  - `FeedTailer._read_new(name) -> tuple[str | None, list[tuple[int, dict]]]`
  - the SSE `"feed"` payload is now `{"instance": str, "session": str | None, "record": <record>}`
- Consumed by: task 2's `FeedRecord` and `FeedEvent` types (already written against this shape), task 4's `dismissAllAlerts`, and task 9's `Feed`, which de-duplicates a streamed record against a fetched one on `(session, seq)`.

- [ ] **Step 1: Write the failing alert tests**

Append to `tests/test_api_alerts.py`, after `test_list_is_newest_first_and_hides_dismissed`:

```python
def test_dismiss_all_clears_every_unread_alert() -> None:
    store = AlertStore()
    first = store.add("alpha", "crash", {"err": "adb gone"})
    store.add("bravo", "offline", {"misses": 3})
    assert store.dismiss(first.id) is True
    assert store.dismiss_all() == 1  # only the one that was still unread
    assert store.list() == []
    assert store.unread_count() == 0
    assert len(store.list(include_dismissed=True)) == 2
    assert store.dismiss_all() == 0  # a second call is a no-op, not an error
```

and after `test_alert_routes_list_and_dismiss`:

```python
def test_the_dismiss_all_route_empties_the_drawer(api) -> None:
    client, _sup, _home = api
    store: AlertStore = client.app.state.alerts
    store.add("alpha", "crash", {"err": "adb gone"})
    store.add("alpha", "offline", {"misses": 3})

    assert client.post("/api/alerts/dismiss-all").status_code == 204
    assert client.get("/api/alerts").json() == {"alerts": [], "unread": 0}
    # Dismissed is read, not deleted: the drawer can still show them on request.
    assert len(client.get("/api/alerts?include_dismissed=true").json()["alerts"]) == 2
    # Clearing an already-clear drawer is still a 204, so the button never shows an error.
    assert client.post("/api/alerts/dismiss-all").status_code == 204
```

- [ ] **Step 2: Write the failing feed tests**

Two new tests in `tests/test_api_feed.py`. Put `test_count_lines_ignores_a_half_written_tail` after `test_read_feed_is_empty_without_a_session`, and `test_get_and_the_stream_agree_on_a_line_number` at the end of the file. Add `count_lines` and `read_session` to the module's import from `brawlfarm.api.feed`.

```python
def test_count_lines_ignores_a_half_written_tail(tmp_path: Path) -> None:
    session = tmp_path / "session-20260911-100000.jsonl"
    _append(session, "start", max_minutes=90)
    _append(session, "phase", to="queuing", frm="menu", games=0)
    assert count_lines(session) == 2
    with session.open("a", encoding="utf-8") as f:
        f.write('{"ts": "2026-09-11T18:05:00", "kind": "rec')
    # The torn line is not a line yet; it becomes line 3 once the worker finishes it.
    assert count_lines(session) == 2
    assert count_lines(tmp_path / "nothing.jsonl") == 0
```

```python
@pytest.mark.asyncio
async def test_get_and_the_stream_agree_on_a_line_number(tmp_path: Path) -> None:
    """The panel de-duplicates a streamed record against a polled one by (session, seq),
    so the two paths have to number the same physical line identically -- including the
    lines neither path shows."""
    inst_dir = S.instance_dir(tmp_path, "alpha")
    session = inst_dir / "session-20260911-100000.jsonl"
    _append(session, "start", max_minutes=90)  # line 1
    _append(session, "tap", button="play", x=1, y=2)  # line 2, dropped by both paths
    bus = EventBus()
    tailer = FeedTailer(tmp_path, StubSup(build_settings(("alpha",))), bus)
    assert await tailer.poll_once() == 0  # joins the session already in progress at its end

    _append(session, "crash", err="adb gone")  # line 3
    assert await tailer.poll_once() == 1
    streamed = bus.recent()[-1].data
    assert streamed["instance"] == "alpha"
    assert streamed["session"] == "session-20260911-100000.jsonl"
    assert streamed["record"]["seq"] == 3

    polled = read_feed(inst_dir)
    assert [(r["event"], r["seq"]) for r in polled] == [("start", 1), ("crash", 3)]
    assert polled[-1] == streamed["record"]
```

- [ ] **Step 3: Update the four existing feed assertions that pin the old shape**

In `test_read_feed_reads_the_newest_session_newest_last`, the new session file is five lines: `start`, `tap`, the torn line, `crash`, `phase`. Replace the full-record assertion with:

```python
    assert records[-1] == {
        "ts": "2026-09-10T18:00:00",
        "seq": 5,
        "event": "phase",
        "category": "matches",
        "fields": {"to": "queuing", "frm": "menu", "games": 0},
    }
    # The dropped tap and the torn line still consume their own line numbers.
    assert [r["seq"] for r in records] == [1, 4, 5]
```

In `test_tailer_skips_history_then_publishes_new_lines`, the file is `start`, `phase`, then `crash`, `tap`, `recover`. Replace the two `bus.recent()` assertions with:

```python
    published = [(e.kind, e.data["record"]["event"], e.data["record"]["seq"]) for e in bus.recent()]
    assert published == [("feed", "crash", 3), ("feed", "recover", 5)]
    assert bus.recent()[0].data["instance"] == "alpha"
    assert bus.recent()[0].data["session"] == "session-20260910-100000.jsonl"
```

In `test_tailer_follows_a_session_roll_from_the_top`, replace the last assertion with:

```python
    assert bus.recent()[-1].data["record"]["event"] == "start"
    # A new file starts its own numbering at 1, not where the old one left off.
    assert bus.recent()[-1].data["record"]["seq"] == 1
    assert bus.recent()[-1].data["session"] == "session-20260910-120000.jsonl"
```

In `test_tailer_waits_for_a_half_written_line`, replace the last assertion with:

```python
    record = bus.recent()[-1].data["record"]
    assert record["event"] == "recap" and record["fields"]["trophies"] == 120
    assert record["seq"] == 1  # the file was empty when the tailer first looked
```

- [ ] **Step 4: Run both modules to confirm they fail**

```bash
cd <repo>
uv run pytest tests/test_api_alerts.py tests/test_api_feed.py -q
```

Expected: FAIL. The alert tests fail with `AttributeError: 'AlertStore' object has no attribute 'dismiss_all'` and a 405 on `POST /api/alerts/dismiss-all`; the feed tests fail with `ImportError: cannot import name 'count_lines'` and, once that import is stubbed out, `KeyError: 'seq'`.

- [ ] **Step 5: Add dismiss-all to the alert store and the router**

In `brawlfarm/api/alerts.py`, add the method immediately after `dismiss`:

```python
    def dismiss_all(self) -> int:
        """Mark everything read; returns how many were still unread. The drawer's
        "Dismiss all" is one call rather than one per row, so a screen full of alerts
        does not become a burst of writes against the same lock."""
        dismissed = 0
        with self._lock:
            for alert in self._alerts:
                if not alert.dismissed:
                    alert.dismissed = True
                    dismissed += 1
        return dismissed
```

and the route between `get_alerts` and `dismiss_alert`:

```python
@router.post("/api/alerts/dismiss-all", status_code=204)
async def dismiss_all_alerts(request: Request) -> Response:
    """Clear the drawer in one call. Always 204, even when nothing was unread: the button
    is idempotent, and a second click must not paint an error."""
    store: AlertStore = request.app.state.alerts
    store.dismiss_all()
    return Response(status_code=204)
```

The two paths do not collide (`/api/alerts/dismiss-all` has one segment after `alerts`, `/api/alerts/{alert_id}/dismiss` has two), so no ordering trick is needed; it sits above `dismiss_alert` because that is the order the drawer uses them in.

- [ ] **Step 6: Number every feed line**

In `brawlfarm/api/feed.py`, replace `to_record` with:

```python
def to_record(line: dict, seq: int) -> dict | None:
    """One session line as a feed record, or None when the kind is dropped. `kind` is
    renamed to `event` because the screen's filter is also called kind. `seq` is the
    line's 1-based position in its session file: `ts` is only second-resolution, so
    without it the panel cannot tell a record streamed over SSE from the same record it
    already fetched."""
    kind = str(line.get("kind") or "")
    if not kind:
        return None
    category = classify(kind)
    if category is None:
        return None
    fields = {k: v for k, v in line.items() if k not in ("ts", "kind")}
    return {
        "ts": str(line.get("ts") or ""),
        "seq": seq,
        "event": kind,
        "category": category,
        "fields": fields,
    }
```

Add `count_lines` immediately after `latest_session`:

```python
def count_lines(path: Path) -> int:
    """How many complete lines the file already holds. The tailer needs it the first time
    it meets a session that is already in progress: it seeks to the end, so its numbering
    has to continue from the file's real length rather than restarting at 1. A half-written
    tail is not counted -- it becomes the next line once the worker finishes writing it."""
    total = 0
    try:
        with path.open("rb") as f:
            for raw in f:
                if raw.endswith(b"\n"):
                    total += 1
    except OSError:
        return 0
    return total
```

In `read_session`, number the lines as the file yields them, so a dropped kind or a torn line still consumes its own number:

```python
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for seq, raw in enumerate(f, start=1):
                try:
                    line = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(line, dict):
                    continue
                record = to_record(line, seq)
                if record is None or (kind != "all" and record["category"] != kind):
                    continue
                records.append(record)
```

- [ ] **Step 7: Carry the number and the session name through the tailer**

Still in `brawlfarm/api/feed.py`. Change the position table's type in `FeedTailer.__init__`:

```python
        # name -> (session file, byte offset, last line number handed out)
        self._positions: dict[str, tuple[Path, int, int]] = {}
```

Replace `poll_once`'s body between the `for inst in ...` line and `return published`:

```python
        for inst in self._sup.settings.instances:
            name = inst.name
            try:
                session, lines = await asyncio.to_thread(self._read_new, name)
            except Exception:  # one unreadable folder must never kill the tailer
                log.exception("%s: feed tail failed", name)
                continue
            for seq, line in lines:
                if self._alerts is not None:
                    self._alerts.ingest(name, line)
                record = to_record(line, seq)
                if record is None:
                    continue
                self._bus.publish("feed", {"instance": name, "session": session, "record": record})
                published += 1
```

Replace `_read_new` with:

```python
    def _read_new(self, name: str) -> tuple[str | None, list[tuple[int, dict]]]:
        """Blocking: the current session's file name, and the lines written since the last
        poll with their 1-based line numbers. Offsets are counted in bytes on a binary
        handle because text-mode tell() is not allowed while iterating."""
        inst_dir = S.instance_dir(self.home, name)
        path = latest_session(inst_dir)
        first_look = name not in self._seen
        self._seen.add(name)
        if path is None:
            self._positions.pop(name, None)
            return None, []
        known, offset, seq = self._positions.get(name, (None, 0, 0))
        if known != path:
            # A session already in progress is joined at its end (ruling 4), so the
            # numbering continues from the lines already on disk. A file that rolled
            # under us is a new session and starts again at 1.
            offset = path.stat().st_size if first_look else 0
            seq = count_lines(path) if first_look else 0
        lines: list[tuple[int, dict]] = []
        try:
            with path.open("rb") as f:
                f.seek(0, 2)
                if f.tell() < offset:  # replaced or truncated under us
                    offset = 0
                    seq = 0
                f.seek(offset)
                for raw in f:
                    if not raw.endswith(b"\n"):
                        break  # a half-written line; the next poll picks it up whole
                    offset += len(raw)
                    seq += 1
                    try:
                        line = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(line, dict):
                        lines.append((seq, line))
        except OSError as exc:
            log.debug("%s: cannot read %s: %s", name, path.name, exc)
            return path.name, []
        self._positions[name] = (path, offset, seq)
        return path.name, lines
```

Finally, update the class docstring's description of the published payload:

```python
    """Follows every instance's newest session file and publishes new lines onto the bus as
    kind "feed" (`{"instance": name, "session": <file name>, "record": <feed record>}`).
```

- [ ] **Step 8: Run both modules, then the whole suite**

```bash
cd <repo>
uv run pytest tests/test_api_alerts.py tests/test_api_feed.py -v
uv run pytest -q
```

Expected: the alert module at 9 tests and the feed module at 12, all passing; the full suite at 490 (486 + 4) with no warnings. If any other module fails, it was asserting the old record shape; `grep -rn '"record"\|read_feed\|to_record' tests/` finds every caller, and today only `tests/test_api_feed.py` has any.

- [ ] **Step 9: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api/alerts.py brawlfarm/api/feed.py tests/test_api_alerts.py tests/test_api_feed.py
uv run ruff check --fix brawlfarm/api tests
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/api/alerts.py brawlfarm/api/feed.py tests/test_api_alerts.py tests/test_api_feed.py
git commit -m "feat(api): dismiss every alert at once, and number every feed line

The drawer's Dismiss all was N requests without a route for it; it is one now,
and it answers 204 whether or not anything was unread so a second click cannot
paint an error.

Feed records gain seq, their 1-based position in the session file, and the SSE
envelope gains the session name. ts is only second-resolution, so a record that
arrived over the stream could not be matched against the same record fetched by
GET .../feed -- the panel had to choose between dropping real lines and showing
duplicates. Dropped kinds and torn lines still consume their own number, so the
two paths number the same physical line identically; a tailer joining a session
already in progress counts the lines on disk first rather than restarting at 1.

classify() is untouched: no kind moves between chips.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 6: The Fleet page

The home screen: one card per instance, led by its live thumbnail, with the four numbers that answer "is this one working" and the three controls that change it. Above the grid, the newest unread alert. This replaces the Fleet placeholder task 4 mounted.

Two things the design brief leaves to the implementation, settled here so every card behaves the same: a card's thumbnail refreshes every 15 s while the tab is visible, in every state that shows a thumbnail at all (offline replaces it with the message block, and a scheduled break keeps the dimmed frame refreshing like any other), which is the same cadence the Instance page's live screen uses; and the header count is written with `plural`, so one instance reads "1 instance".

**Files:**
- Create: `brawlfarm/web/src/fleet/Fleet.tsx`
- Create: `brawlfarm/web/src/fleet/InstanceCard.tsx`
- Create: `brawlfarm/web/src/fleet/AlertStrip.tsx`
- Modify: `brawlfarm/web/src/App.tsx` (the `path="/"` route only)
- Test: `brawlfarm/web/src/fleet/InstanceCard.test.tsx`
- Test: `brawlfarm/web/src/fleet/AlertStrip.test.tsx`
- Test: `brawlfarm/web/src/fleet/Fleet.test.tsx`

**Interfaces:**
- Consumes: task 2's `useInstances`, `startInstance`, `stopInstance`, `restartInstance`, `retryInstance`, `listAlerts`, `dismissAlert`, `getStatsToday`, `queryKeys`, `useVisiblePolling`, `toast`, `since`, `hhmm`, `duration`, `hoursText`, `signed`, `plural`, `makeInstance`, `makeAlert`; task 3's `Button`, `Chip`, `StateChip`, `Thumb`, `ErrorBlock`, `phaseLabel`, `alertKindLabel`, `alertKindTone`, `renderWithProviders`; task 4's `openAlertsDrawer`.
- Produces:
  - `Fleet()`
  - `InstanceCard({ inst: InstancePayload })`, plus the three pure helpers it is tested through: `retryMinutes(note: string): number | null`, `breakCaption(until: string | null): string`, `nextValue(inst: InstancePayload): string`, and `NEXT_LABELS: Record<InstanceState, string>`
  - `AlertStrip({ alert: Alert; unread: number; onOpen: () => void })`
- Consumed by: task 12 (the keyboard, reduced-motion and phone-width pass), and the live evidence run.

- [ ] **Step 1: Write the failing tests for the card**

`brawlfarm/web/src/fleet/InstanceCard.test.tsx`:

```tsx
/** One card per instance, in all seven states: what it shows, what it disables, and what
 * it calls. The seven cases are the whole point -- a card that looks the same when the
 * instance is farming and when it is offline is a card nobody can trust. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { InstanceCard, breakCaption, nextValue, retryMinutes } from "./InstanceCard";
import type { InstanceState } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeInstance } from "../test/fixtures";
import { jsonResponse, pngResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

function stubScreens() {
  return stubFetch((url) => {
    if (url.endsWith("screenshot.png")) return pngResponse();
    if (url === "/api/instances") return jsonResponse({ instances: [] });
    return jsonResponse({ ok: true });
  });
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

const CHIPS: [InstanceState, string][] = [
  ["farming", "Farming"],
  ["starting", "Starting"],
  ["stopping", "Stopping after this match"],
  ["stopped", "Stopped"],
  ["scheduled_break", "Scheduled break"],
  ["reconnecting", "Reconnecting"],
  ["offline", "Offline"],
];

describe("retryMinutes, breakCaption and nextValue", () => {
  it("reads the minutes out of the supervisor's offline note", () => {
    expect(retryMinutes("BlueStacks window not found. Retrying in 4 min.")).toBe(4);
    expect(retryMinutes("BlueStacks window not found. Retrying in 15 min.")).toBe(15);
    expect(retryMinutes("Starting; waiting for the first heartbeat")).toBeNull();
    expect(retryMinutes("")).toBeNull();
  });

  it("captions a break with its end time, or without one when there is none", () => {
    expect(breakCaption("2026-09-11T21:30:00")).toBe("Break until 21:30");
    expect(breakCaption(null)).toBe("On a scheduled break");
  });

  it("shows the next moment as a time, a countdown, or none", () => {
    expect(nextValue(makeInstance({ state: "farming", until: "2026-09-11T21:30:00" }))).toBe("21:30");
    expect(nextValue(makeInstance({ state: "stopped", until: null }))).toBe("none");
    expect(
      nextValue(
        makeInstance({ state: "offline", until: null, note: "BlueStacks window not found. Retrying in 4 min." }),
      ),
    ).toBe("4 min");
    expect(nextValue(makeInstance({ state: "offline", until: null, note: "" }))).toBe("soon");
  });
});

describe("InstanceCard", () => {
  it.each(CHIPS)("shows the %s state as a chip", async (state, label) => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state })} />);
    expect(await screen.findByText(label)).toBeInTheDocument();
  });

  it("links the whole card to the instance page and names the port and phase", () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ phase: "queuing" })} />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/instances/Pie64");
    expect(screen.getByText("Pie64")).toBeInTheDocument();
    expect(screen.getByText("5555")).toBeInTheDocument();
    expect(screen.getByText("queuing")).toBeInTheDocument();
  });

  it("shows the four metrics", () => {
    stubScreens();
    renderWithProviders(
      <InstanceCard
        inst={makeInstance({
          today: { games: 12, trophies: 86 },
          session: {
            minutes_elapsed: 72,
            start_trophies: 41200,
            last_trophies: 41286,
            disconnect_count: 0,
            recovery_attempts: 0,
            session: "session-20260911-190540.jsonl",
          },
          until: "2026-09-11T21:30:00",
        })}
      />,
    );
    expect(screen.getByText("Games today").nextSibling).toHaveTextContent("12");
    expect(screen.getByText("Trophies today").nextSibling).toHaveTextContent("+86");
    expect(screen.getByText("Session").nextSibling).toHaveTextContent("1 h 12 min");
    expect(screen.getByText("Next break").nextSibling).toHaveTextContent("21:30");
  });

  it("says none for a session that has not started", () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "stopped", session: null, until: null })} />);
    expect(screen.getByText("Session").nextSibling).toHaveTextContent("none");
    expect(screen.getByText("Next session")).toBeInTheDocument();
  });

  it("replaces the thumbnail with the offline block and retries from it", async () => {
    const { calls } = stubScreens();
    renderWithProviders(
      <InstanceCard
        inst={makeInstance({
          state: "offline",
          until: null,
          note: "BlueStacks window not found. Retrying in 4 min.",
        })}
      />,
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(
      screen.getByText("BlueStacks window not found. Retrying in 4 min."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry now" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/retry");
    });
    expect(toastMessages()).toContain("Retrying Pie64 now");
  });

  it("says retrying soon when the note has no minute count", () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "offline", note: "", until: null })} />);
    expect(screen.getByText("BlueStacks window not found. Retrying soon.")).toBeInTheDocument();
  });

  it("dims the thumbnail and captions it on a scheduled break", async () => {
    stubScreens();
    renderWithProviders(
      <InstanceCard inst={makeInstance({ state: "scheduled_break", until: "2026-09-11T21:30:00" })} />,
    );
    const image = await screen.findByRole("img", { name: "Pie64 screen" });
    expect(image.className).toContain("opacity-40");
    expect(screen.getByText("Break until 21:30")).toBeInTheDocument();
  });

  it("disables Stop with a reason on the three states that are not running", () => {
    for (const state of ["stopped", "scheduled_break", "offline"] as const) {
      stubScreens();
      const { unmount } = renderWithProviders(<InstanceCard inst={makeInstance({ state })} />);
      const stop = screen.getByRole("button", { name: "Stop" });
      expect(stop).toBeDisabled();
      expect(stop).toHaveAttribute("title", "Not running");
      unmount();
    }
  });

  it("stops with an undo that starts it again, without following the card link", async () => {
    const { calls } = stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    await userEvent.click(screen.getByRole("button", { name: "Stop" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/stop");
    });
    expect(toastMessages()).toContain("Stopping Pie64 after this match");

    const undo = renderHook(() => useToasts()).result.current[0]?.undo;
    expect(undo).toBeTypeOf("function");
    await undo?.();
    expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/start");
  });

  it("restarts from the footer", async () => {
    const { calls } = stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    await userEvent.click(screen.getByRole("button", { name: "Restart" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/restart");
    });
    expect(toastMessages()).toContain("Restarting Pie64");
  });

  it("has an Open control beside the two that act", () => {
    stubScreens();
    renderWithProviders(<InstanceCard inst={makeInstance({ state: "farming" })} />);
    expect(within(screen.getByRole("link")).getByRole("button", { name: /Open/ })).toBeInTheDocument();
  });
});
```

`brawlfarm/web/src/fleet/AlertStrip.test.tsx`:

```tsx
/** The strip above the grid: the newest alert in one sentence, with the one action that
 * kind deserves. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertStrip } from "./AlertStrip";
import { resetToasts } from "../lib/toast";
import { makeAlert } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

const OFFLINE = makeAlert({
  id: 9,
  instance: "Pie64_1",
  kind: "offline",
  title: "Instance offline",
  detail: "misses=3",
  ts: new Date(Date.now() - 8 * 60_000).toISOString(),
});

const CRASH = makeAlert({
  id: 8,
  instance: "Pie64",
  kind: "crash",
  title: "Bot crashed",
  detail: "err=adb did not answer",
});

describe("AlertStrip", () => {
  it("writes an offline alert as a sentence with its age", () => {
    stubFetch(() => jsonResponse({ ok: true }));
    renderWithProviders(<AlertStrip alert={OFFLINE} unread={1} onOpen={vi.fn()} />);
    expect(
      screen.getByText("Pie64_1 has been offline for 8 min. BlueStacks window not found."),
    ).toBeInTheDocument();
    expect(screen.getByText("Offline")).toBeInTheDocument();
  });

  it("writes every other kind as instance, title and detail", () => {
    stubFetch(() => jsonResponse({ ok: true }));
    renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={vi.fn()} />);
    expect(screen.getByText("Pie64 bot crashed: err=adb did not answer")).toBeInTheDocument();
  });

  it("offers Retry now only for an offline alert", () => {
    stubFetch(() => jsonResponse({ ok: true }));
    const { unmount } = renderWithProviders(<AlertStrip alert={OFFLINE} unread={1} onOpen={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Retry now" })).toBeInTheDocument();
    unmount();
    renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Retry now" })).not.toBeInTheDocument();
  });

  it("dismisses the alert it is showing", async () => {
    const { calls } = stubFetch(() => new Response(null, { status: 204 }));
    renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/alerts/8/dismiss");
    });
  });

  it("offers the rest only when there is more than one", async () => {
    stubFetch(() => jsonResponse({ ok: true }));
    const onOpen = vi.fn();
    const { unmount } = renderWithProviders(<AlertStrip alert={CRASH} unread={1} onOpen={onOpen} />);
    expect(screen.queryByRole("button", { name: /more/ })).not.toBeInTheDocument();
    unmount();
    renderWithProviders(<AlertStrip alert={CRASH} unread={4} onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: "3 more" }));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });
});
```

`brawlfarm/web/src/fleet/Fleet.test.tsx`:

```tsx
/** The page around the cards: the count, the two fleet-wide controls, the totals line and
 * the sentence that tells a new user what to do next. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { Fleet } from "./Fleet";
import { resetToasts, useToasts } from "../lib/toast";
import { makeAlert, makeInstance } from "../test/fixtures";
import { jsonResponse, pngResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

const FLEET = [
  makeInstance({ name: "Pie64", adb_port: 5555, state: "farming", today: { games: 12, trophies: 86 } }),
  makeInstance({ name: "Pie64_1", adb_port: 5565, state: "stopped", today: { games: 4, trophies: -12 } }),
  makeInstance({ name: "Pie64_3", adb_port: 5585, state: "offline", today: { games: 0, trophies: 0 } }),
];

function stubFleet(instances = FLEET, alerts: ReturnType<typeof makeAlert>[] = []) {
  return stubFetch((url) => {
    if (url === "/api/instances") return jsonResponse({ instances });
    if (url === "/api/alerts") return jsonResponse({ alerts, unread: alerts.length });
    if (url.startsWith("/api/stats")) {
      return jsonResponse({
        range: "today",
        instances: instances.map((inst) => inst.name),
        summary: {
          games: 16,
          trophies: 74,
          trophies_per_hour: null,
          avg_rank: 3.4,
          top4_rate: null,
          hours_farmed: 3.6667,
        },
      });
    }
    if (url.endsWith("screenshot.png")) return pngResponse();
    return jsonResponse({ ok: true });
  });
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Fleet", () => {
  it("heads the page with the instance count and totals today", async () => {
    stubFleet();
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("3 instances")).toBeInTheDocument();
    // One farming, one stopped, one offline; 12 + 4 + 0 games and 86 - 12 + 0 trophies
    // from the cards, and 3.6667 hours from the stats route.
    expect(
      await screen.findByText(
        "1 farming · 16 games today · +74 trophies today · 3 h 40 min farmed",
      ),
    ).toBeInTheDocument();
  });

  it("counts one instance in the singular", async () => {
    stubFleet([FLEET[0]]);
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("1 instance")).toBeInTheDocument();
  });

  it("starts and stops the whole fleet", async () => {
    const { calls } = stubFleet();
    renderWithProviders(<Fleet />);
    await userEvent.click(await screen.findByRole("button", { name: "Start all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Starting 3 instances");
    });
    expect(calls.filter((call) => call.url.endsWith("/start"))).toHaveLength(3);

    await userEvent.click(screen.getByRole("button", { name: "Stop all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Stopping 3 instances after their matches");
    });
    expect(calls.filter((call) => call.url.endsWith("/stop"))).toHaveLength(3);
  });

  it("shows the newest alert above the grid", async () => {
    stubFleet(FLEET, [
      makeAlert({ id: 9, instance: "Pie64", kind: "crash", title: "Bot crashed", detail: "err=adb did not answer" }),
    ]);
    renderWithProviders(<Fleet />);
    expect(
      await screen.findByText("Pie64 bot crashed: err=adb did not answer"),
    ).toBeInTheDocument();
  });

  it("tells a new user what to do when there are no instances", async () => {
    stubFleet([]);
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("No instances yet.")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Setup arrives in the next phase; until then add an [[instances]] table to config.toml and restart brawlfarm.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start all" })).not.toBeInTheDocument();
  });

  it("shows the API's own sentence when the list cannot be fetched", async () => {
    stubFetch((url) =>
      url === "/api/instances"
        ? jsonResponse({ detail: "adb did not answer" }, 503)
        : jsonResponse({ alerts: [], unread: 0, summary: { hours_farmed: 0 } }),
    );
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the three files to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test src/fleet
```

Expected: FAIL, unresolved imports for `./InstanceCard`, `./AlertStrip` and `./Fleet`.

- [ ] **Step 3: Write the card**

`brawlfarm/web/src/fleet/InstanceCard.tsx`:

```tsx
/**
 * One instance, at a glance.
 *
 * The whole card is a link to the instance page, so the largest target does the most
 * likely thing. The three controls in the footer are buttons inside that link, so each
 * one stops the click from reaching it; that is the price of making the card itself
 * clickable, and it is paid in one helper rather than in every handler.
 *
 * The thumbnail is the headline: a screen is the fastest way to see that a bot is in a
 * match and not stuck on a popup. It refreshes every 15 s while the tab is visible and
 * stops entirely while it is hidden, because every frame is an adb screencap against a
 * live BlueStacks window. An offline instance has no window to capture, so its card shows
 * the supervisor's own retry note instead.
 */
import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight } from "lucide-react";
import type { MouseEvent, ReactNode } from "react";
import { Link, useNavigate } from "react-router";

import {
  restartInstance,
  retryInstance,
  startInstance,
  stopInstance,
} from "../api/instances";
import { queryKeys } from "../api/queries";
import type { InstancePayload, InstanceState } from "../api/types";
import { Button } from "../components/ui/Button";
import { StateChip } from "../components/ui/StateChip";
import { Thumb } from "../components/ui/Thumb";
import { useVisiblePolling } from "../live/useVisiblePolling";
import { signed } from "../lib/format";
import { phaseLabel } from "../lib/states";
import { duration, hhmm } from "../lib/time";
import { toast } from "../lib/toast";

const THUMB_MS = 15000;
const RETRY_MINUTES_RE = /Retrying in (\d+) min/;

const STOPPABLE_STATES: ReadonlySet<InstanceState> = new Set<InstanceState>([
  "farming",
  "starting",
  "stopping",
  "reconnecting",
]);

export const NEXT_LABELS: Record<InstanceState, string> = {
  farming: "Next break",
  starting: "Next break",
  stopping: "Next break",
  reconnecting: "Next break",
  scheduled_break: "Next session",
  stopped: "Next session",
  offline: "Next retry",
};

/** The supervisor writes "BlueStacks window not found. Retrying in 4 min."; the card
 * shows the number on its own as well, so read it back out rather than duplicating the
 * backoff schedule here. */
export function retryMinutes(note: string): number | null {
  const match = RETRY_MINUTES_RE.exec(note);
  if (match === null) return null;
  const minutes = Number(match[1]);
  return Number.isFinite(minutes) ? minutes : null;
}

export function breakCaption(until: string | null): string {
  return until === null ? "On a scheduled break" : `Break until ${hhmm(until)}`;
}

export function nextValue(inst: InstancePayload): string {
  if (inst.state === "offline") {
    const minutes = retryMinutes(inst.note);
    return minutes === null ? "soon" : `${minutes} min`;
  }
  return inst.until === null ? "none" : hhmm(inst.until);
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[11px] text-muted">{label}</div>
      <div className="font-mono text-[15px] tabular-nums text-text">{value}</div>
    </div>
  );
}

function OfflineBlock({ note, onRetry }: { note: string; onRetry: ReactNode }) {
  const minutes = retryMinutes(note);
  return (
    <div className="flex aspect-video w-full flex-col items-center justify-center gap-1.5 rounded-[6px] border border-line bg-panel-2 p-3 text-center">
      <StateChip state="offline" />
      <p className="text-[13px] text-text">
        {minutes === null
          ? "BlueStacks window not found. Retrying soon."
          : `BlueStacks window not found. Retrying in ${minutes} min.`}
      </p>
      <p className="text-[12px] text-muted">Open the instance, or {onRetry}.</p>
    </div>
  );
}

export interface InstanceCardProps {
  inst: InstancePayload;
}

export function InstanceCard({ inst }: InstanceCardProps) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const refreshMs = useVisiblePolling(THUMB_MS);

  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.instances() });
  };

  /** Every footer control lives inside the card's own link. */
  const act = (event: MouseEvent<HTMLButtonElement>, run: () => Promise<void>) => {
    event.preventDefault();
    event.stopPropagation();
    void run();
  };

  const onStop = (event: MouseEvent<HTMLButtonElement>) =>
    act(event, async () => {
      await stopInstance(inst.name);
      refresh();
      toast(`Stopping ${inst.name} after this match`, {
        undo: async () => {
          await startInstance(inst.name);
          refresh();
        },
      });
    });

  const onRestart = (event: MouseEvent<HTMLButtonElement>) =>
    act(event, async () => {
      await restartInstance(inst.name);
      refresh();
      toast(`Restarting ${inst.name}`);
    });

  const onRetry = (event: MouseEvent<HTMLButtonElement>) =>
    act(event, async () => {
      await retryInstance(inst.name);
      refresh();
      toast(`Retrying ${inst.name} now`);
    });

  const stoppable = STOPPABLE_STATES.has(inst.state);
  const sessionMinutes = inst.session?.minutes_elapsed ?? null;

  return (
    <Link
      to={`/instances/${inst.name}`}
      className="block rounded-[10px] border border-line bg-panel p-3 transition-colors duration-[120ms] hover:border-accent"
    >
      {inst.state === "offline" ? (
        <OfflineBlock
          note={inst.note}
          onRetry={
            <Button variant="text" size="sm" onClick={onRetry}>
              Retry now
            </Button>
          }
        />
      ) : (
        <Thumb
          name={inst.name}
          refreshMs={refreshMs}
          dimmed={inst.state === "scheduled_break"}
          caption={inst.state === "scheduled_break" ? breakCaption(inst.until) : undefined}
          overlay={<StateChip state={inst.state} />}
        />
      )}

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-[15px] font-semibold">{inst.name}</span>
        <span className="font-mono text-[12px] tabular-nums text-muted">{inst.adb_port}</span>
        <span className="flex-1 truncate text-right text-[12px] text-muted">
          {phaseLabel(inst.phase)}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <Metric label="Games today" value={String(inst.today.games)} />
        <Metric label="Trophies today" value={signed(inst.today.trophies)} />
        <Metric
          label="Session"
          value={sessionMinutes === null ? "none" : duration(sessionMinutes)}
        />
        <Metric label={NEXT_LABELS[inst.state]} value={nextValue(inst)} />
      </div>

      <div className="mt-3 flex items-center gap-2 border-t border-line pt-2">
        <Button
          variant="quiet"
          size="sm"
          disabled={!stoppable}
          disabledReason="Not running"
          onClick={onStop}
        >
          Stop
        </Button>
        <Button variant="quiet" size="sm" onClick={onRestart}>
          Restart
        </Button>
        <span className="flex-1" />
        <Button
          variant="text"
          size="sm"
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            void navigate(`/instances/${inst.name}`);
          }}
        >
          Open
          <ChevronRight size={16} strokeWidth={1.6} aria-hidden="true" />
        </Button>
      </div>
    </Link>
  );
}
```

- [ ] **Step 4: Write the alert strip**

`brawlfarm/web/src/fleet/AlertStrip.tsx`:

```tsx
/**
 * The newest unread alert, above the grid.
 *
 * One line, one action. An offline alert is rewritten into a sentence with its age,
 * because "misses=3" means nothing to the person reading it; every other kind is the
 * instance, the alert's own title and its detail, which the API already writes for
 * people.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { dismissAlert } from "../api/alerts";
import { retryInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import type { Alert } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { alertKindLabel, alertKindTone } from "../lib/states";
import { since } from "../lib/time";
import { toast } from "../lib/toast";

export interface AlertStripProps {
  alert: Alert;
  unread: number;
  onOpen: () => void;
}

export function alertSentence(alert: Alert, nowMs: number): string {
  if (alert.kind === "offline") {
    const age = since(Date.parse(alert.ts), nowMs);
    return `${alert.instance} has been offline for ${age}. BlueStacks window not found.`;
  }
  return `${alert.instance} ${alert.title.toLowerCase()}: ${alert.detail}`;
}

export function AlertStrip({ alert, unread, onOpen }: AlertStripProps) {
  const client = useQueryClient();
  // Frozen at mount: the strip is replaced whenever the alert list changes, and a ticking
  // age here would rerender the whole Fleet page every second for no benefit.
  const [nowMs] = useState(() => Date.now());

  const onDismiss = () => {
    void dismissAlert(alert.id).then(() => {
      void client.invalidateQueries({ queryKey: queryKeys.alerts() });
    });
  };

  const onRetry = () => {
    void retryInstance(alert.instance).then(() => {
      void client.invalidateQueries({ queryKey: queryKeys.instances() });
      toast(`Retrying ${alert.instance} now`);
    });
  };

  return (
    <div className="flex items-center gap-3 rounded-[10px] border border-line bg-panel px-3 py-2">
      <Chip tone={alertKindTone(alert.kind)}>{alertKindLabel(alert.kind)}</Chip>
      <p className="min-w-0 flex-1 truncate text-[13px] text-text">
        {alertSentence(alert, nowMs)}
      </p>
      {alert.kind === "offline" && (
        <Button variant="text" size="sm" onClick={onRetry}>
          Retry now
        </Button>
      )}
      <Button variant="text" size="sm" onClick={onDismiss}>
        Dismiss
      </Button>
      {unread > 1 && (
        <Button variant="text" size="sm" onClick={onOpen}>
          {`${unread - 1} more`}
        </Button>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Write the page and mount it**

`brawlfarm/web/src/fleet/Fleet.tsx`:

```tsx
/**
 * The home screen.
 *
 * The list comes from useInstances, which carries the 15 s visible poll: `session` and
 * `today` only exist on GET /api/instances, and the instance events carry the
 * supervisor's view alone, so without the poll a card's numbers would freeze between
 * route changes. The totals line's "farmed" figure is the only thing here that needs
 * GET /api/stats.
 *
 * Start all and Stop all fire one request per instance in parallel; there is no
 * fleet-wide route, and inventing one in the client would hide a partial failure.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { AlertStrip } from "./AlertStrip";
import { InstanceCard } from "./InstanceCard";
import { openAlertsDrawer } from "../app/alertsDrawer";
import { listAlerts } from "../api/alerts";
import { startInstance, stopInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import { getStatsToday } from "../api/stats";
import { useInstances } from "../api/useInstances";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { plural, signed } from "../lib/format";
import { hoursText } from "../lib/time";
import { toast } from "../lib/toast";

const GRID_COLUMNS = "repeat(auto-fill, minmax(340px, 1fr))";

export function Fleet() {
  const client = useQueryClient();

  const { data: instances, error, refetch } = useInstances();
  const { data: alerts } = useQuery({ queryKey: queryKeys.alerts(), queryFn: listAlerts });
  // Only summary.hours_farmed is read here; games and trophies come from the cards' own
  // payload, so the totals line always agrees with the grid above it.
  const { data: stats } = useQuery({
    queryKey: queryKeys.statsToday(),
    queryFn: () => getStatsToday(),
  });

  const fleet = instances ?? [];
  const newest = alerts?.alerts[0];
  const farming = fleet.filter((inst) => inst.state === "farming").length;
  const games = fleet.reduce((total, inst) => total + inst.today.games, 0);
  const trophies = fleet.reduce((total, inst) => total + inst.today.trophies, 0);
  const hours = stats?.summary.hours_farmed ?? 0;

  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.instances() });
  };

  const onStartAll = () => {
    void Promise.all(fleet.map((inst) => startInstance(inst.name))).then(() => {
      refresh();
      toast(`Starting ${fleet.length} instances`);
    });
  };

  const onStopAll = () => {
    void Promise.all(fleet.map((inst) => stopInstance(inst.name))).then(() => {
      refresh();
      toast(`Stopping ${fleet.length} instances after their matches`);
    });
  };

  if (error !== null) {
    return (
      <ErrorBlock
        error={error}
        onRetry={() => {
          void refetch();
        }}
      />
    );
  }

  if (instances !== undefined && fleet.length === 0) {
    return (
      <section className="max-w-[560px]">
        <h1 className="text-[28px] font-semibold tracking-tight">No instances yet.</h1>
        <p className="mt-2 text-[13px] text-muted">
          Setup arrives in the next phase; until then add an [[instances]] table to
          config.toml and restart brawlfarm.
        </p>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <header className="flex items-center gap-3">
        <h1 className="text-[28px] font-semibold tracking-tight">Fleet</h1>
        <span className="flex-1 text-[13px] text-muted">{plural(fleet.length, "instance")}</span>
        <Button variant="quiet" size="sm" onClick={onStartAll}>
          Start all
        </Button>
        <Button variant="quiet" size="sm" onClick={onStopAll}>
          Stop all
        </Button>
      </header>

      {newest !== undefined && (
        <AlertStrip alert={newest} unread={alerts?.unread ?? 0} onOpen={openAlertsDrawer} />
      )}

      <div className="grid gap-4" style={{ gridTemplateColumns: GRID_COLUMNS }}>
        {fleet.map((inst) => (
          <InstanceCard key={inst.name} inst={inst} />
        ))}
      </div>

      <p className="font-mono text-[12px] tabular-nums text-muted">
        {`${farming} farming · ${games} games today · ${signed(trophies)} trophies today · ${hoursText(hours)} farmed`}
      </p>
    </section>
  );
}
```

In `brawlfarm/web/src/App.tsx`, add the import and swap the `/` route:

```tsx
import { Fleet } from "./fleet/Fleet";
```

```tsx
        <Route path="/" element={<Fleet />} />
```

- [ ] **Step 6: Run the three files to confirm they pass**

```bash
cd <repo>/brawlfarm/web
pnpm test src/fleet src/App.test.tsx
```

Expected: PASS. `src/fleet` is 3 files and 22 tests; `App.test.tsx` still passes, but its first case now finds the Fleet page rather than the placeholder -- if `mounts the shell and the Fleet route` fails on the missing `Pie64` link, the route swap did not land.

- [ ] **Step 7: Run everything, typecheck, build**

```bash
cd <repo>/brawlfarm/web
pnpm test
pnpm typecheck
pnpm build
```

Expected: PASS, 22 files and 93 tests; `tsc` silent; the build succeeds.

- [ ] **Step 8: Look at it**

```bash
cd <repo>
uv run brawlfarm --no-browser
```

Open `http://127.0.0.1:8765/`. The Fleet page shows one card per configured instance with a live thumbnail, the chip on the thumbnail matches what the instance is actually doing, and Stop offers an Undo for six seconds. Stop the process with Ctrl+C. This is a look, not the phase's evidence run; task 12 records that properly.

- [ ] **Step 9: Commit**

```bash
uv run python tools/scrub_check.py
git add brawlfarm/web/src/fleet brawlfarm/web/src/App.tsx
git commit -m "feat(web): the Fleet page, one card per instance

The thumbnail leads the card because a screen is the fastest way to see that a
bot is in a match rather than stuck behind a popup. It refreshes every 15 s
while the tab is visible and not at all while it is hidden, because every frame
is an adb screencap against a live BlueStacks window.

Each of the seven states changes the card, not just its colour: offline replaces
the thumbnail with the supervisor's own retry note and a Retry now button, a
scheduled break dims the frame and captions it with the end time, and the fourth
metric relabels itself between next break, next session and next retry. Stop
carries a six-second Undo that starts the instance again, because stopping the
wrong card is the easy mistake to make on this page.

Start all and Stop all fan out one request per instance rather than pretending
there is a fleet-wide route; a partial failure stays visible.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 7: The owned-brawler roster on the plan routes (Python)

The gap the contracts file records: the supervisor process holds
`settings.connection.brawl_api_token` and each instance's `player_tag` but has never called
the Brawl Stars API, so `GET /api/instances/{name}/plan` cannot show the editor a roster.
This task opens that path once, behind a cache, and adds the one pure function the queue
preview needs. Nothing in `core/farmplan.py` changes: `plan_queue` is appended beside
`choose_target`, which keeps its behaviour bit for bit.

**Files:**
- Modify: `brawlfarm/core/farmplan.py` (append `plan_queue` after `choose_target`, at line 500, before `resolve_target`)
- Create: `brawlfarm/api/roster.py`
- Modify: `brawlfarm/api/plans.py` (the module docstring's last paragraph at lines 9 to 11; the import block at lines 16 to 22; a new `enrich_plan`; both route bodies at lines 58 to 70)
- Modify: `brawlfarm/api/app.py` (the `from brawlfarm.api import (...)` block at lines 28 to 39, and the `app.state` block at lines 126 to 132)
- Create: `tests/test_farmplan_queue.py`
- Create: `tests/test_api_roster.py`
- Modify: `tests/test_api_plan.py` (the two whole-body equality assertions, lines 29 to 34 and 50 to 56, and the key-set assertion at line 89)

**Interfaces:**
- Consumes: `farmplan.PRESTIGE_GOAL`, `farmplan._prestige_pool`, `farmplan.DEFAULT_PLAN`, `farmplan.load_plan`, `farmplan.save_plan`; `brawlfarm.core.api.ApiClient.get_player(tag)`; `api.deps.resolve_instance(request, name) -> (InstanceSettings, Path)` and `api.deps.get_sup(request) -> Supervisor`; `Supervisor.views() -> list[InstanceView]` (`view.farm_brawler`); `settings.InstanceSettings.player_tag`; `settings.ConnectionSection.brawl_api_token`; `tests.apihelpers.make_client`.
- Produces:
  - `farmplan.plan_queue(plan: dict, brawlers: list[dict], *, current: str | None, n: int = 3) -> list[str]`
  - `brawlfarm.api.roster.RosterCache(*, ttl_s: float = TTL_S, now: Callable[[], float] = time.monotonic, fetch: Callable[[str, str], dict] = fetch_player)` with `async get(name: str, tag: str, token: str) -> tuple[list[dict] | None, str]`
  - `brawlfarm.api.roster.TTL_S = 300.0`, `roster.Entry`, `roster.fetch_player(tag, token) -> dict`
  - `plans.enrich_plan(request: Request, name: str, plan: dict) -> dict`
  - `app.state.roster: RosterCache`
  - `GET|PUT /api/instances/{name}/plan` bodies gain `current`, `roster`, `queue`, `roster_status`
- Consumed by: task 10 (`FarmPlan`), which reads every one of the four new keys.
- Ordering: task 5 is the phase's other Python task and it touches `api/alerts.py` and `api/feed.py` only, so this is the first and only edit to `api/app.py` and the two cannot collide. Run it after task 5 all the same, so `uv run pytest -q` here is run against a tree that already carries the feed's `seq`.

- [ ] **Step 1: Write the failing tests**

`tests/test_farmplan_queue.py`:

```python
"""farmplan.plan_queue: the three brawlers the Instance screen lists under "Next in
queue". A preview of the plan's own order and never a decision -- it reads no games.csv,
so choose_target's win-rate bias and rotation set cannot be moved by anything here."""

from __future__ import annotations

from brawlfarm.core import farmplan

ROSTER = [
    {"name": "NORI", "trophies": 812},
    {"name": "TARA", "trophies": 540},
    {"name": "SHELLY", "trophies": 615},
    {"name": "DYNAMIKE", "trophies": 705},
    {"name": "EDGAR", "trophies": 1000},
    {"name": "SPIKE", "trophies": 1140},
]


def _plan(**over) -> dict:
    return {**farmplan.DEFAULT_PLAN, **over}


def test_ladder_lists_the_lowest_brawlers_still_under_the_goal() -> None:
    assert farmplan.plan_queue(_plan(), ROSTER, current="NORI") == ["TARA", "SHELLY", "DYNAMIKE"]


def test_the_current_brawler_is_dropped_case_insensitively() -> None:
    assert farmplan.plan_queue(_plan(), ROSTER, current="tara") == ["SHELLY", "DYNAMIKE", "NORI"]


def test_the_goal_is_the_ceiling_and_n_is_the_length() -> None:
    assert farmplan.plan_queue(_plan(goal_trophies=700), ROSTER, current=None) == [
        "TARA",
        "SHELLY",
    ]
    assert farmplan.plan_queue(_plan(), ROSTER, current=None, n=1) == ["TARA"]


def test_a_trophy_tie_breaks_on_the_name() -> None:
    tied = [{"name": "PIPER", "trophies": 600}, {"name": "BULL", "trophies": 600}]
    assert farmplan.plan_queue(_plan(), tied, current=None) == ["BULL", "PIPER"]


def test_prestige_starts_from_the_end_the_plan_names() -> None:
    high = _plan(mode="prestige", prestige_start="highest")
    low = _plan(mode="prestige", prestige_start="lowest")
    assert farmplan.plan_queue(high, ROSTER, current="NORI") == ["DYNAMIKE", "SHELLY", "TARA"]
    assert farmplan.plan_queue(low, ROSTER, current="NORI") == ["TARA", "SHELLY", "DYNAMIKE"]


def test_prestige_never_lists_a_brawler_at_or_past_the_prestige_goal() -> None:
    low = _plan(mode="prestige", prestige_start="lowest")
    # EDGAR at exactly 1000 and SPIKE at 1140 are done; the pool is strictly under 1000.
    assert farmplan.plan_queue(low, ROSTER, current=None, n=6) == [
        "TARA",
        "SHELLY",
        "DYNAMIKE",
        "NORI",
    ]


def test_an_empty_or_nameless_roster_is_an_empty_queue() -> None:
    assert farmplan.plan_queue(_plan(), [], current="NORI") == []
    assert farmplan.plan_queue(_plan(), [{"trophies": 10}], current=None) == []


def test_the_preview_never_moves_choose_target() -> None:
    plan = _plan()
    before = farmplan.choose_target(plan, ROSTER)
    farmplan.plan_queue(plan, ROSTER, current="NORI")
    assert farmplan.choose_target(plan, ROSTER) == before
    assert ROSTER[0] == {"name": "NORI", "trophies": 812}  # the caller's list is not sorted
```

`tests/test_api_roster.py`:

```python
"""The roster block on GET and PUT /api/instances/{name}/plan, and the cache behind it:
one upstream call per instance per TTL, the last good list kept when a call fails, and the
three reasons the list can be missing. No network anywhere -- the clock and the fetcher
are injected."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.api.roster import RosterCache
from tests.apihelpers import make_client

PLAN_URL = "/api/instances/alpha/plan"
TAG = "#2P0YLQ9"  # invented from the game's alphabet; not an account that exists
TOKEN = "not-a-real-token"

PLAYER = {
    "tag": TAG,
    "brawlers": [
        {
            "id": 16000000,
            "name": "SHELLY",
            "trophies": 615,
            "highestTrophies": 700,
            "rank": 20,
            "power": 9,
            "gadgets": [{"id": 1, "name": "CLAY PIGEONS"}],
        },
        {
            "id": 16000101,
            "name": "NORI",
            "trophies": 812,
            "highestTrophies": 830,
            "rank": 25,
            "power": 11,
            "gadgets": [],
        },
        {
            "id": 16000002,
            "name": "TARA",
            "trophies": 540,
            "highestTrophies": 615,
            "rank": 19,
            "power": 11,
            "gadgets": [],
        },
    ],
}

NORI = {"id": 16000101, "name": "NORI", "trophies": 812, "highest": 830, "rank": 25, "power": 11}


class FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class FakeFetch:
    """One GET /players/{tag}: counts its calls and can be made to raise."""

    def __init__(self, player: dict) -> None:
        self.player = player
        self.calls: list[tuple[str, str]] = []
        self.boom: Exception | None = None

    def __call__(self, tag: str, token: str) -> dict:
        self.calls.append((tag, token))
        if self.boom is not None:
            raise self.boom
        return self.player


@pytest.mark.asyncio
async def test_the_cache_fetches_once_per_ttl_and_sorts_by_trophies() -> None:
    clock, fetch = FakeClock(), FakeFetch(PLAYER)
    cache = RosterCache(now=clock, fetch=fetch)
    first, status = await cache.get("alpha", TAG, TOKEN)
    assert status == "ok"
    assert [b["name"] for b in first] == ["NORI", "SHELLY", "TARA"]
    assert first[0] == NORI  # six fields, highestTrophies renamed, no gadgets
    clock.t += 299.0
    again, status = await cache.get("alpha", TAG, TOKEN)
    assert status == "ok" and again == first and len(fetch.calls) == 1
    clock.t += 2.0  # now past the 300 s TTL
    await cache.get("alpha", TAG, TOKEN)
    assert len(fetch.calls) == 2


@pytest.mark.asyncio
async def test_every_instance_has_its_own_entry() -> None:
    fetch = FakeFetch(PLAYER)
    cache = RosterCache(now=FakeClock(), fetch=fetch)
    await cache.get("alpha", TAG, TOKEN)
    await cache.get("bravo", TAG, TOKEN)
    assert len(fetch.calls) == 2


@pytest.mark.asyncio
async def test_a_failed_refresh_keeps_the_last_good_roster() -> None:
    clock, fetch = FakeClock(), FakeFetch(PLAYER)
    cache = RosterCache(now=clock, fetch=fetch)
    good, _ = await cache.get("alpha", TAG, TOKEN)
    fetch.boom = RuntimeError("upstream said no")
    clock.t += 400.0
    stale, status = await cache.get("alpha", TAG, TOKEN)
    assert status == "unavailable" and stale == good


@pytest.mark.asyncio
async def test_a_first_fetch_that_fails_has_nothing_to_show() -> None:
    fetch = FakeFetch(PLAYER)
    fetch.boom = RuntimeError("upstream said no")
    cache = RosterCache(now=FakeClock(), fetch=fetch)
    assert await cache.get("alpha", TAG, TOKEN) == (None, "unavailable")


@pytest.mark.asyncio
async def test_the_failure_log_carries_neither_the_tag_nor_the_token(caplog) -> None:
    fetch = FakeFetch(PLAYER)
    fetch.boom = RuntimeError(f"/players/{TAG} -> HTTP 403: bad token {TOKEN}")
    cache = RosterCache(now=FakeClock(), fetch=fetch)
    with caplog.at_level("WARNING", logger="brawlfarm.api"):
        await cache.get("alpha", TAG, TOKEN)
    assert "roster fetch failed" in caplog.text
    assert TAG not in caplog.text and TOKEN not in caplog.text


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def _credentials(client, sup) -> tuple[FakeFetch, FakeClock]:
    """Give the app a token, a tag and an upstream that never leaves the process."""
    fetch, clock = FakeFetch(PLAYER), FakeClock()
    sup.settings.connection.brawl_api_token = TOKEN
    sup.settings.instance("alpha").player_tag = TAG
    client.app.state.roster = RosterCache(now=clock, fetch=fetch)
    return fetch, clock


def _farming(home: Path, sup, name: str, brawler: str) -> None:
    """What the worker writes when it picks a brawler. The view reads farm_brawler from
    status.json, so the tick after this one carries it."""
    d = S.instance_dir(home, name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(
        json.dumps({"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "farm_brawler": brawler}),
        encoding="utf-8",
    )
    sup.tick()


def test_get_carries_the_current_brawler_the_roster_and_the_queue(api) -> None:
    client, sup, home = api
    fetch, _clock = _credentials(client, sup)
    _farming(home, sup, "alpha", "NORI")
    body = client.get(PLAN_URL).json()
    assert set(body) == {
        "mode",
        "prestige_start",
        "goal_trophies",
        "maxed_fallback",
        "current",
        "roster",
        "queue",
        "roster_status",
    }
    assert body["current"] == {"brawler": "NORI", "trophies": 812, "goal": 1000}
    assert body["queue"] == ["TARA", "SHELLY"]
    assert body["roster"][0] == NORI
    assert body["roster_status"] == "ok"
    client.get(PLAN_URL)
    assert len(fetch.calls) == 1  # the second GET is served from the cache


def test_prestige_reports_the_prestige_threshold_as_the_goal(api) -> None:
    client, sup, home = api
    _credentials(client, sup)
    _farming(home, sup, "alpha", "NORI")
    body = client.put(PLAN_URL, json={"mode": "prestige", "goal_trophies": 1400}).json()
    assert body["goal_trophies"] == 1400  # the stored plan is untouched
    assert body["current"]["goal"] == 1000  # prestige always finishes a brawler at 1000
    assert body["queue"] == ["SHELLY", "TARA"]  # highest first, NORI excluded


def test_put_returns_the_same_enriched_shape_as_get(api) -> None:
    client, sup, _home = api
    _credentials(client, sup)
    put = client.put(PLAN_URL, json={"mode": "ladder", "goal_trophies": 700})
    assert put.status_code == 200
    assert set(put.json()) == set(client.get(PLAN_URL).json())
    assert put.json()["queue"] == ["TARA", "SHELLY"]  # 540 and 615 are the two under 700


def test_no_token_is_reported_not_guessed(api) -> None:
    client, sup, _home = api
    sup.settings.instance("alpha").player_tag = TAG
    body = client.get(PLAN_URL).json()
    assert body["roster_status"] == "no_token"
    assert body["roster"] is None and body["queue"] == []
    assert body["current"] == {"brawler": None, "trophies": None, "goal": 1000}


def test_no_tag_is_reported_not_guessed(api) -> None:
    client, sup, _home = api
    sup.settings.connection.brawl_api_token = TOKEN
    body = client.get(PLAN_URL).json()
    assert body["roster_status"] == "no_tag" and body["roster"] is None


def test_an_unavailable_upstream_still_serves_the_last_known_roster(api) -> None:
    client, sup, home = api
    fetch, clock = _credentials(client, sup)
    _farming(home, sup, "alpha", "NORI")
    assert client.get(PLAN_URL).json()["roster_status"] == "ok"
    fetch.boom = RuntimeError("upstream said no")
    clock.t += 400.0  # the TTL has expired, so the next GET tries the upstream again
    body = client.get(PLAN_URL).json()
    assert body["roster_status"] == "unavailable"
    assert body["roster"][0] == NORI  # the stale list is still worth showing
    assert body["current"]["trophies"] == 812


def test_a_brawler_the_roster_does_not_know_has_no_trophies(api) -> None:
    client, sup, home = api
    _credentials(client, sup)
    _farming(home, sup, "alpha", "SURGE")  # owned in game, absent from this fake payload
    body = client.get(PLAN_URL).json()
    assert body["current"] == {"brawler": "SURGE", "trophies": None, "goal": 1000}


def test_an_unknown_instance_is_still_a_404(api) -> None:
    client, _sup, _home = api
    assert client.get("/api/instances/ghost/plan").status_code == 404
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
uv run pytest tests/test_farmplan_queue.py tests/test_api_roster.py -q
```

Expected: every test in `tests/test_farmplan_queue.py` fails with
`AttributeError: module 'brawlfarm.core.farmplan' has no attribute 'plan_queue'`;
`tests/test_api_roster.py` fails collection with
`ModuleNotFoundError: No module named 'brawlfarm.api.roster'`.

- [ ] **Step 3: Append `plan_queue` to `brawlfarm/core/farmplan.py`**

Insert after `choose_target` ends (`return None, goal` at line 500) and before
`def resolve_target`. Nothing above it changes.

```python
def plan_queue(
    plan: dict,
    brawlers: list[dict],
    *,
    current: str | None,
    n: int = 3,
) -> list[str]:
    """The next ``n`` brawler names this plan would reach for after ``current``.

    A READ-ONLY preview for the panel's "Next in queue" rows (spec section 8), kept
    deliberately apart from :func:`choose_target`: it never reads games.csv, so the
    win-rate bias and the controller's session rotation set cannot move it, and nothing
    the panel does can change what the worker picks. Ladder lists the owned brawlers
    still under ``goal_trophies``, lowest first, which is the order the ladder walks;
    prestige lists the pool still under :data:`PRESTIGE_GOAL` from the end
    ``prestige_start`` names. ``current`` is dropped from both and matched
    case-insensitively, like every other name comparison in this module. An empty roster
    gives an empty list: the panel shows the roster-status line instead.
    """
    skip = (current or "").strip().upper()
    pool = [b for b in brawlers if (b.get("name") or "").upper() != skip]
    if plan.get("mode") == "prestige":
        pool = _prestige_pool(pool)
        descending = plan.get("prestige_start", "highest") == "highest"
    else:
        goal = int(plan.get("goal_trophies") or PRESTIGE_GOAL)
        pool = [b for b in pool if (b.get("trophies") or 0) < goal]
        descending = False
    # Two stable sorts: the name is the tie-break, so equal trophies read alphabetically
    # whichever end the plan starts from.
    pool.sort(key=lambda b: (b.get("name") or "").upper())
    pool.sort(key=lambda b: b.get("trophies") or 0, reverse=descending)
    return [b["name"] for b in pool[: max(0, int(n))] if b.get("name")]
```

- [ ] **Step 4: Write `brawlfarm/api/roster.py`**

```python
"""The owned-brawler roster behind GET and PUT /api/instances/{name}/plan.

The plan editor needs the account's brawlers: the current brawler's trophies for its
progress bar, the next few the plan would farm, and the names its maxed-fallback box
offers. Until now only the worker subprocess called the Brawl Stars API; the supervisor
process had the token and the tag but no code path that used them. This module is that
path, and it is a cache first and a client second.

The official API is rate limited and its token is locked to one IP, so the budget is one
fetch per instance per TTL_S no matter how many panels are open, and two callers racing
share one call through that instance's lock. A fetch that fails keeps the last good list
and reports "unavailable" beside it, because a five-minute-old roster is far more useful
to the editor than an empty one. Neither the token nor the tag is ever logged: the
upstream client puts the requested path in its error message, so only the exception TYPE
reaches the log.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from brawlfarm.core.api import ApiClient

log = logging.getLogger("brawlfarm.api")

TTL_S = 300.0  # five minutes: a roster moves a few trophies per match, not per second


def fetch_player(tag: str, token: str) -> dict:
    """One blocking GET /players/{tag}. The default fetcher; tests inject their own."""
    return ApiClient(token=token).get_player(tag)


def _brawler(raw: dict) -> dict:
    """One upstream brawler entry as the six fields the editor draws. The rest of the
    payload (gadgets, star powers, gears) is dropped here rather than in the browser."""
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "trophies": raw.get("trophies"),
        "highest": raw.get("highestTrophies"),
        "rank": raw.get("rank"),
        "power": raw.get("power"),
    }


@dataclass
class Entry:
    """One instance's cached roster: the last good value, when it was fetched, and the
    lock that stops two requests fetching it twice."""

    brawlers: list[dict] | None = None
    fetched_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RosterCache:
    """Per-instance owned-brawler lists with a TTL and stale-on-failure.

    `now` and `fetch` are injected so the tests need neither a clock nor a network; the
    app builds the cache with the defaults. One instance lives on app.state.roster for
    the process's lifetime.
    """

    def __init__(
        self,
        *,
        ttl_s: float = TTL_S,
        now: Callable[[], float] = time.monotonic,
        fetch: Callable[[str, str], dict] = fetch_player,
    ) -> None:
        self._ttl_s = ttl_s
        self._now = now
        self._fetch = fetch
        self._entries: dict[str, Entry] = {}

    def _entry(self, name: str) -> Entry:
        """One lock per instance name, created on first use so it binds to this loop."""
        entry = self._entries.get(name)
        if entry is None:
            entry = self._entries[name] = Entry()
        return entry

    async def get(self, name: str, tag: str, token: str) -> tuple[list[dict] | None, str]:
        """This instance's owned brawlers sorted by trophies descending, and a status.

        The status is "ok" when the list is fresh or was just refreshed, "unavailable"
        when the fetch raised -- with the previous list, if there is one, still returned
        beside it. A blank token or tag is the route's business, not this call's.
        """
        entry = self._entry(name)
        async with entry.lock:
            if entry.brawlers is not None and self._now() - entry.fetched_at < self._ttl_s:
                return entry.brawlers, "ok"
            try:
                player = await asyncio.to_thread(self._fetch, tag, token)
            except Exception as exc:  # network, auth, rate limit, a shape we did not expect
                # str(exc) can carry the tag and the token, so only the type is logged.
                log.warning("%s: roster fetch failed (%s)", name, type(exc).__name__)
                return entry.brawlers, "unavailable"
            raw = player.get("brawlers") or []
            brawlers = [_brawler(b) for b in raw if isinstance(b, dict)]
            brawlers.sort(key=lambda b: b.get("name") or "")
            brawlers.sort(key=lambda b: b.get("trophies") or 0, reverse=True)
            entry.brawlers = brawlers
            entry.fetched_at = self._now()
            return brawlers, "ok"
```

- [ ] **Step 5: Enrich both plan routes**

In `brawlfarm/api/plans.py`, replace the docstring's last paragraph, the one opening "The worker re-reads the plan live" (lines 9 to 11):

```python
The worker re-reads the plan live (at startup and on every trophy snapshot, roughly once
a minute), so a PUT takes effect without restarting anything. Both routes return the same
enriched shape: the four stored keys plus the brawler being farmed, the owned roster from
api/roster.py, the next three names plan_queue would reach for, and a roster_status
saying why the roster is missing when it is. PUT returns it too, so the editor never has
to re-read the plan to refresh its rows after a save.
```

Replace the import block, `from typing import Literal` down to `from brawlfarm.core import farmplan` (lines 16 to 22), with:

```python
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from brawlfarm.api.deps import get_sup, resolve_instance
from brawlfarm.core import farmplan
```

Insert `enrich_plan` after `_as_plan` and before the routes:

```python
async def enrich_plan(request: Request, name: str, plan: dict) -> dict:
    """The stored plan plus everything the editor draws around it.

    `current.goal` is the goal for the MODE, not the stored number: prestige always
    finishes a brawler at PRESTIGE_GOAL, whatever goal_trophies happens to say. The
    roster is None (and the queue empty) whenever roster_status is not "ok", except for
    "unavailable", which may still carry the last good list. resolve_instance runs again
    here rather than being threaded through from the route: it is a dict lookup, and the
    helper stays callable from both routes with nothing but a name.
    """
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    token = sup.settings.connection.brawl_api_token.strip()
    tag = inst.player_tag.strip()
    view = next((v for v in sup.views() if v.name == inst.name), None)
    brawler = view.farm_brawler if view is not None else None

    roster: list[dict] | None = None
    if not token:
        status = "no_token"
    elif not tag:
        status = "no_tag"
    else:
        roster, status = await request.app.state.roster.get(inst.name, tag, token)

    trophies = None
    if roster is not None and brawler:
        want = brawler.upper()
        match = next((b for b in roster if (b.get("name") or "").upper() == want), None)
        trophies = None if match is None else match.get("trophies")
    goal = farmplan.PRESTIGE_GOAL if plan["mode"] == "prestige" else plan["goal_trophies"]
    queue = [] if roster is None else farmplan.plan_queue(plan, roster, current=brawler)
    return {
        **plan,
        "current": {"brawler": brawler, "trophies": trophies, "goal": goal},
        "roster": roster,
        "queue": queue,
        "roster_status": status,
    }
```

Replace both route bodies, `@router.get("/api/instances/{name}/plan")` to the end of `write_plan` (lines 58 to 70):

```python
@router.get("/api/instances/{name}/plan")
async def read_plan(request: Request, name: str) -> dict:
    """The stored plan merged over the defaults (a missing file reads as ladder), plus
    the roster block the editor draws its rows from."""
    _inst, inst_dir = resolve_instance(request, name)
    plan = _as_plan(farmplan.load_plan(data_dir=inst_dir)).model_dump()
    return await enrich_plan(request, name, plan)


@router.put("/api/instances/{name}/plan")
async def write_plan(request: Request, name: str, body: FarmPlan) -> dict:
    """Replace the plan. A running worker picks it up within a minute; no restart."""
    _inst, inst_dir = resolve_instance(request, name)
    inst_dir.mkdir(parents=True, exist_ok=True)
    saved = _as_plan(farmplan.save_plan(body.model_dump(), data_dir=inst_dir)).model_dump()
    return await enrich_plan(request, name, saved)
```

- [ ] **Step 6: Put the cache on app.state**

In `brawlfarm/api/app.py`, add `roster` to the `from brawlfarm.api import (...)` list (it is
alphabetical, so between `plans` and `schedule`), then add one line to the `app.state` block
after `app.state.screenshot_locks = {}` (line 132, the last line of that block):

```python
    # One roster cache for the process: per instance, five-minute TTL, stale on failure.
    # Not built in the lifespan because it holds nothing loop-bound until its first use.
    app.state.roster = roster.RosterCache()
```

- [ ] **Step 7: Update the three assertions in `tests/test_api_plan.py`**

That file asserts the whole GET body, so the four new keys break it. What it pins is the
plan's own keys, so it checks those and leaves the roster block to
`tests/test_api_roster.py`. Replace `test_get_returns_the_defaults_for_a_fresh_instance`:

```python
def test_get_returns_the_defaults_for_a_fresh_instance(api) -> None:
    client, _sup, _home = api
    body = client.get(PLAN_URL).json()
    assert {k: body[k] for k in ("mode", "prestige_start", "goal_trophies", "maxed_fallback")} == {
        "mode": "ladder",
        "prestige_start": "highest",
        "goal_trophies": 1000,
        "maxed_fallback": None,
    }
    # No token is configured here, so there is nothing to show beside the plan.
    assert body["roster"] is None and body["roster_status"] == "no_token"
    assert client.get("/api/instances/ghost/plan").status_code == 404
```

In `test_put_writes_the_plan_the_worker_reads`, replace the two assertions that follow
`assert r.status_code == 200`:

```python
    keys = ("mode", "prestige_start", "goal_trophies", "maxed_fallback")
    stored = {k: r.json()[k] for k in keys}
    assert stored == {
        "mode": "prestige",
        "prestige_start": "lowest",
        "goal_trophies": 1200,
        "maxed_fallback": "Shelly",
    }
    assert farmplan.load_plan(data_dir=S.instance_dir(home, "alpha")) == stored
```

In `test_a_legacy_plan_file_still_reads`, replace the `assert set(body) == ...` line (line 89):

```python
    assert set(body) == {
        "mode",
        "prestige_start",
        "goal_trophies",
        "maxed_fallback",
        "current",
        "roster",
        "queue",
        "roster_status",
    }
    # The legacy file's own "queue" key is dropped; this one is the roster preview, and
    # with no token there is no roster to preview.
    assert body["queue"] == []
```

- [ ] **Step 8: Run the tests and the rest of the suite**

```bash
uv run pytest tests/test_farmplan_queue.py tests/test_api_roster.py tests/test_api_plan.py -q
uv run pytest -q
uv run ruff format brawlfarm/core/farmplan.py brawlfarm/api/roster.py brawlfarm/api/plans.py brawlfarm/api/app.py tests/test_farmplan_queue.py tests/test_api_roster.py tests/test_api_plan.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
```

Expected: 8 passed in `test_farmplan_queue.py`, 14 in `test_api_roster.py`, 6 in
`test_api_plan.py`; the full suite green with no warnings; `All checks passed!`; every file
already formatted; `0 hit(s)`. If `test_farmplan.py` or any `test_farmplan_winrate*.py` moves
at all, `plan_queue` has touched something it must not: revert and re-read step 3.

- [ ] **Step 9: Commit**

```bash
git add brawlfarm/core/farmplan.py brawlfarm/api/roster.py brawlfarm/api/plans.py \
        brawlfarm/api/app.py tests/test_farmplan_queue.py tests/test_api_roster.py \
        tests/test_api_plan.py
git commit -m "feat(api): the owned-brawler roster on the plan routes

The plan editor needs the roster to draw a progress bar, a queue and a
fallback picker, and the supervisor process held the token and the tag
but had never called the Brawl Stars API. api/roster.py opens that path
behind a five-minute per-instance cache that keeps the last good list
when the upstream call fails, and farmplan.plan_queue previews the
plan's own order without reading games.csv, so choose_target is
untouched. Neither the token nor the tag reaches the log.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 8: The Instance page frame and the live screen

The route the Fleet card links to. It owns the header, the two-column layout the next three
tasks drop panels into, and the live screen. It also appends the three payload fixtures
tasks 10 and 11 build their tests from; the test helpers themselves are already there, from
tasks 2 and 3.

**Files:**
- Modify: `brawlfarm/web/src/test/fixtures.ts` (append `makeRosterBrawler`, `makePlan` and `makeSchedule`; the file exists from task 2 with `makeInstance`, `makeAlert` and `makeFeedRecord`, none of which change)
- Create: `brawlfarm/web/src/instance/LiveScreen.tsx`
- Create: `brawlfarm/web/src/instance/Instance.tsx`
- Modify: `brawlfarm/web/src/App.tsx` (the `<Route path="/instances/:name" ... />` line, which task 4 pointed at `Placeholder`)
- Test: `brawlfarm/web/src/instance/LiveScreen.test.tsx`
- Test: `brawlfarm/web/src/instance/Instance.test.tsx`

**Interfaces:**
- Consumes: `ApiError` (`../api/client`); `InstancePayload`, `PlanResponse`, `SchedulePayload` (`../api/types`); `useInstances` (`../api/useInstances`); `startInstance`, `stopInstance`, `restartInstance`, `retryInstance` (`../api/instances`); `queryKeys` (`../api/queries`); `screenshotUrl` (`../api/screens`); `Thumb` (`../components/ui/Thumb`, props `{ name, refreshMs, dimmed?, caption?, overlay?, refreshKey? }`); `Button`, `StateChip`, `ErrorBlock` (`../components/ui/`); `phaseLabel` (`../lib/states`); `toast`, `useToasts`, `resetToasts` (`../lib/toast`); `useVisiblePolling` (`../live/useVisiblePolling`); `makeInstance` (`../test/fixtures`); `stubFetch`, `jsonResponse`, `pngResponse`, `FetchCall` (`../test/http`, task 2); `renderWithProviders` (`../test/renderWithProviders`, task 3).
- Produces:
  - `brawlfarm/web/src/instance/Instance.tsx`: `export function Instance(): ReactElement` (route `/instances/:name`; a named export, like every other component in this plan)
  - `brawlfarm/web/src/instance/LiveScreen.tsx`: `export function LiveScreen({ name }: { name: string }): ReactElement`
  - `src/test/fixtures.ts`: `makeRosterBrawler(overrides?)`, `makePlan(overrides?)`, `makeSchedule(overrides?)`, appended beside task 2's `makeInstance`, `makeAlert` and `makeFeedRecord`
- Consumed by: tasks 9, 10 and 11, which mount `Feed`, `FarmPlan`, `Schedule` and `SessionPanel` into `Instance.tsx`'s two columns and build their payloads from the three new fixtures.
- The page reads the fleet through task 2's `useInstances()`, which already carries the 15 s visible poll. That is why the header's chip, the session figures and today's numbers keep moving without this page holding any state of its own: there is no per-instance GET on the API, and the `instance` events App subscribes to invalidate the same `["instances"]` key.

- [ ] **Step 1: Write the failing tests**

`brawlfarm/web/src/instance/LiveScreen.test.tsx`:

```tsx
/** The instance's own screen: the frame it draws, the link to the raw PNG, and the
 * Refresh button that asks for a new frame now rather than in 15 s. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { LiveScreen } from "./LiveScreen";
import { type FetchCall, pngResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const SHOT = "/api/instances/Pie64/screenshot.png";

beforeAll(() => {
  // jsdom has no object URLs, and Thumb turns every screenshot blob into one.
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:shot"), writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
});

describe("LiveScreen", () => {
  let calls: FetchCall[];

  beforeEach(() => {
    calls = stubFetch(() => pngResponse()).calls;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function shots(): number {
    return calls.filter((call) => call.url === SHOT).length;
  }

  it("shows the live frame and a full size link", async () => {
    renderWithProviders(<LiveScreen name="Pie64" />);
    const image = await screen.findByRole("img");
    expect(image).toHaveAttribute("data-private");
    const link = screen.getByRole("link", { name: "Full size" });
    expect(link).toHaveAttribute("href", SHOT);
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
  });

  it("Refresh forces one extra fetch", async () => {
    renderWithProviders(<LiveScreen name="Pie64" />);
    await waitFor(() => {
      expect(shots()).toBe(1);
    });
    await userEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => {
      expect(shots()).toBe(2);
    });
  });
});
```

`brawlfarm/web/src/instance/Instance.test.tsx`. The page is mounted inside a `Routes` so
`useParams` sees a real name; `renderWithProviders` (task 3) supplies the query client and
the `MemoryRouter` around it.

```tsx
/** The /instances/:name frame: which row of the fleet it picks, what its header says
 * about that instance, and what each of its controls calls. */
import { renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { Instance } from "./Instance";
import { resetToasts, useToasts } from "../lib/toast";
import { makeInstance } from "../test/fixtures";
import { type FetchCall, jsonResponse, pngResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

beforeAll(() => {
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:shot"), writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
});

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

function toasts() {
  return renderHook(() => useToasts()).result.current;
}

/** Every request the page makes: the fleet list, the screenshot, and the three controls,
 * each of which the API answers 202 Accepted. */
function stubPage(instances: ReturnType<typeof makeInstance>[]): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") return jsonResponse({ instances });
    if (url.endsWith("screenshot.png")) return pngResponse();
    return jsonResponse({ ok: true }, 202);
  }).calls;
}

function mountPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/instances/:name" element={<Instance />} />
    </Routes>,
    { route: "/instances/Pie64" },
  );
}

describe("Instance", () => {
  it("renders nothing but the shell while the fleet is loading", () => {
    stubFetch(() => new Promise<Response>(() => {}));
    const { container } = mountPage();
    expect(container.textContent).toBe("");
  });

  it("reports an unknown instance with the API's own words", async () => {
    stubPage([makeInstance({ name: "Pie64_1" })]);
    mountPage();
    expect(await screen.findByText("unknown instance")).toBeInTheDocument();
  });

  it("heads the page with the name, state, port, tag, phase and a screenshot link", async () => {
    stubPage([
      makeInstance({
        name: "Pie64",
        adb_port: 5555,
        state: "farming",
        phase: "playing",
        player_tag: "#2P0YLQ9",
      }),
    ]);
    mountPage();
    expect(await screen.findByRole("heading", { level: 1, name: "Pie64" })).toBeInTheDocument();
    expect(screen.getByText("Farming")).toBeInTheDocument();
    expect(screen.getByText("5555")).toBeInTheDocument();
    expect(screen.getByText("playing")).toBeInTheDocument();
    expect(screen.getByText("#2P0YLQ9")).toHaveAttribute("data-private");
    const shot = screen.getByRole("link", { name: "Screenshot" });
    expect(shot).toHaveAttribute("href", "/api/instances/Pie64/screenshot.png");
    expect(shot).toHaveAttribute("target", "_blank");
    expect(shot).toHaveAttribute("rel", "noreferrer");
  });

  it("stops after this match and offers an undo that starts again", async () => {
    const calls = stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/stop");
    });
    expect(toasts()[0].message).toBe("Stopping Pie64 after this match");
    await toasts()[0].undo?.();
    await waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/start");
    });
  });

  it("disables Stop on a stopped instance and says why", async () => {
    stubPage([makeInstance({ name: "Pie64", state: "stopped" })]);
    mountPage();
    const stop = await screen.findByRole("button", { name: "Stop" });
    expect(stop).toBeDisabled();
    expect(stop).toHaveAttribute("title", "Not running");
    expect(screen.queryByRole("button", { name: "Retry now" })).not.toBeInTheDocument();
  });

  it("offers Retry now only while the instance is offline", async () => {
    const calls = stubPage([makeInstance({ name: "Pie64", state: "offline" })]);
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Retry now" }));
    await waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/retry");
    });
    expect(toasts()[0].message).toBe("Retrying Pie64 now");
  });

  it("speaks the API's own sentence when a control fails, and says nothing else", async () => {
    stubFetch((url) => {
      if (url === "/api/instances") {
        return jsonResponse({ instances: [makeInstance({ name: "Pie64", state: "farming" })] });
      }
      if (url.endsWith("screenshot.png")) return pngResponse();
      return jsonResponse({ detail: "adb did not answer" }, 503);
    });
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await waitFor(() => {
      expect(toasts()[0]?.message).toBe("adb did not answer");
    });
    // The success toast never fires, so the failure is the only line on screen.
    expect(toasts()).toHaveLength(1);
  });
});
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test src/instance
```

Expected: both files fail to collect with
`Failed to resolve import "./LiveScreen"` and `"./Instance"`.

- [ ] **Step 3: Append the payload fixtures**

Append to `brawlfarm/web/src/test/fixtures.ts`. Task 2 created it with `makeInstance`,
`makeAlert` and `makeFeedRecord`; those three are not touched, and the three new payload
types join its existing `import type` line, which becomes:

```ts
import type {
  Alert,
  FeedRecord,
  InstancePayload,
  PlanResponse,
  RosterBrawler,
  SchedulePayload,
} from "../api/types";
```

Then, below `makeFeedRecord`:

```ts
export function makeRosterBrawler(overrides: Partial<RosterBrawler> = {}): RosterBrawler {
  return {
    id: 16000101,
    name: "NORI",
    trophies: 812,
    highest: 830,
    rank: 25,
    power: 11,
    ...overrides,
  };
}

export function makePlan(overrides: Partial<PlanResponse> = {}): PlanResponse {
  return {
    mode: "ladder",
    prestige_start: "highest",
    goal_trophies: 1000,
    maxed_fallback: null,
    current: { brawler: "NORI", trophies: 812, goal: 1000 },
    roster: [
      makeRosterBrawler(),
      makeRosterBrawler({ id: 16000000, name: "SHELLY", trophies: 615, highest: 700, rank: 20 }),
      makeRosterBrawler({ id: 16000002, name: "TARA", trophies: 540, highest: 615, rank: 19 }),
    ],
    queue: ["TARA", "SHELLY"],
    roster_status: "ok",
    ...overrides,
  };
}

export function makeSchedule(overrides: Partial<SchedulePayload> = {}): SchedulePayload {
  return {
    enabled: true,
    override: null,
    plan_date: "2026-09-11",
    sessions: [
      { start: "2026-09-11T09:00:00", end: "2026-09-11T11:00:00" },
      { start: "2026-09-11T13:30:00", end: "2026-09-11T15:00:00" },
      { start: "2026-09-11T19:00:00", end: "2026-09-11T20:30:00" },
    ],
    day_end: "2026-09-11T20:30:00",
    desired: null,
    games_played_today: 12,
    now: "2026-09-11T14:15:00",
    ...overrides,
  };
}
```

- [ ] **Step 4: Write `LiveScreen`**

`brawlfarm/web/src/instance/LiveScreen.tsx`:

```tsx
import { useState } from "react";

import { screenshotUrl } from "../api/screens";
import { Button } from "../components/ui/Button";
import { Thumb } from "../components/ui/Thumb";
import { useVisiblePolling } from "../live/useVisiblePolling";

const REFRESH_MS = 15000; // the same cadence a Fleet card's thumbnail uses

/**
 * The instance's screen, refreshed every 15 s while the tab is visible. "Refresh" bumps
 * refreshKey, which is Thumb's "fetch one now" signal; "Full size" is a real link, so it
 * opens in a tab, can be copied, and reaches the keyboard like any other link.
 */
export function LiveScreen({ name }: { name: string }) {
  const refreshMs = useVisiblePolling(REFRESH_MS);
  const [refreshKey, setRefreshKey] = useState(0);
  return (
    <section className="rounded-[10px] border border-line bg-panel p-3">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="text-[13px] font-semibold">Live screen</h2>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="text" size="sm" onClick={() => setRefreshKey((k) => k + 1)}>
            Refresh
          </Button>
          <a
            className="rounded-[6px] px-2 py-1 text-[12px] text-accent hover:underline focus-visible:outline-2"
            href={screenshotUrl(name)}
            target="_blank"
            rel="noreferrer"
          >
            Full size
          </a>
        </div>
      </div>
      <div className="aspect-video w-full max-w-[760px] overflow-hidden rounded-[6px] border border-line bg-panel-2">
        <Thumb name={name} refreshMs={refreshMs} refreshKey={refreshKey} />
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Write `Instance`**

`brawlfarm/web/src/instance/Instance.tsx`:

```tsx
import { useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router";

import { ApiError } from "../api/client";
import {
  restartInstance,
  retryInstance,
  startInstance,
  stopInstance,
} from "../api/instances";
import { queryKeys } from "../api/queries";
import { screenshotUrl } from "../api/screens";
import type { InstancePayload } from "../api/types";
import { useInstances } from "../api/useInstances";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { StateChip } from "../components/ui/StateChip";
import { phaseLabel } from "../lib/states";
import { toast } from "../lib/toast";
import { LiveScreen } from "./LiveScreen";

/** Stop, Restart and Retry only mean something in some states (brief section 9). */
const NOT_RUNNING = new Set(["stopped", "scheduled_break", "offline"]);

function Header({ inst, onDone }: { inst: InstancePayload; onDone: () => void }) {
  const stoppable = !NOT_RUNNING.has(inst.state);
  /** Nothing is announced until the request has settled. A rejection speaks the ApiError's
   * own detail -- the API's sentence, or the "cannot reach brawlfarm" one a dead server
   * produces -- and the success toast never fires. */
  const run = async (call: Promise<unknown>, done: () => void) => {
    try {
      await call;
    } catch (error) {
      toast(error instanceof ApiError ? error.detail : "Request failed");
      return;
    }
    onDone();
    done();
  };
  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-2">
      <Link to="/" className="text-[12px] text-muted hover:text-text">
        Fleet
      </Link>
      <h1 className="text-[28px] leading-none font-semibold">{inst.name}</h1>
      <StateChip state={inst.state} />
      <span className="font-mono text-[12px] tabular-nums text-muted">{inst.adb_port}</span>
      {inst.player_tag === "" ? null : (
        <span data-private className="font-mono text-[12px] text-muted">
          {inst.player_tag}
        </span>
      )}
      <span className="text-[12px] text-muted">{phaseLabel(inst.phase)}</span>
      <div className="ml-auto flex items-center gap-2">
        {/* The raw PNG, for a closer look or a copied URL; LiveScreen has its own
            Refresh and Full size controls inside the frame. */}
        <a
          className="rounded-[6px] px-2 py-1 text-[12px] text-accent hover:underline"
          href={screenshotUrl(inst.name)}
          target="_blank"
          rel="noreferrer"
        >
          Screenshot
        </a>
        <Button
          variant="quiet"
          size="sm"
          disabled={!stoppable}
          disabledReason="Not running"
          onClick={() => {
            void run(stopInstance(inst.name), () => {
              toast(`Stopping ${inst.name} after this match`, {
                undo: async () => {
                  await startInstance(inst.name);
                  onDone();
                },
              });
            });
          }}
        >
          Stop
        </Button>
        <Button
          variant="quiet"
          size="sm"
          onClick={() => {
            void run(restartInstance(inst.name), () => toast(`Restarting ${inst.name}`));
          }}
        >
          Restart
        </Button>
        {inst.state === "offline" ? (
          <Button
            variant="quiet"
            size="sm"
            onClick={() => {
              void run(retryInstance(inst.name), () => toast(`Retrying ${inst.name} now`));
            }}
          >
            Retry now
          </Button>
        ) : null}
      </div>
    </header>
  );
}

/**
 * One instance, at /instances/:name. There is no per-instance GET on the API, so the
 * page reads the fleet list through useInstances and picks its own row out of it. That
 * hook carries the 15 s visible poll, and App's "instance" handler invalidates the same
 * key, so the header, the session figures and today's numbers all follow a state change
 * without this page holding any state of its own.
 */
export function Instance() {
  const { name = "" } = useParams();
  const client = useQueryClient();
  const fleet = useInstances();
  const refresh = () => {
    void client.invalidateQueries({ queryKey: queryKeys.instances() });
  };

  if (fleet.isPending) return <div />; // the shell is enough until the list lands
  if (fleet.isError) {
    return <ErrorBlock error={fleet.error} onRetry={() => void fleet.refetch()} />;
  }
  const inst = fleet.data.find((row) => row.name === name);
  if (inst === undefined) return <ErrorBlock error={new ApiError(404, "unknown instance")} />;

  return (
    <div className="flex flex-col gap-4">
      <Header inst={inst} onDone={refresh} />
      <div className="grid grid-cols-1 gap-4 min-[1100px]:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-4">
          <LiveScreen name={inst.name} />
        </div>
        <div className="flex flex-col gap-4" />
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Point the route at it**

In `brawlfarm/web/src/App.tsx`, add the import and replace the instance route line task 4
left as a placeholder:

```tsx
import { Instance } from "./instance/Instance";
```

```tsx
<Route path="/instances/:name" element={<Instance />} />
```

- [ ] **Step 7: Run the tests**

```bash
cd <repo>/brawlfarm/web
pnpm test src/instance
pnpm typecheck
```

Expected: `src/instance/LiveScreen.test.tsx` 2 passed, `src/instance/Instance.test.tsx`
7 passed; `tsc --noEmit` silent. If a test times out waiting for the image, the screenshot
path the stub answers does not match what `screenshotUrl` builds: print `calls` and fix the
test's URL, never the component.

- [ ] **Step 8: Commit**

```bash
cd <repo>
git add brawlfarm/web/src/instance/Instance.tsx brawlfarm/web/src/instance/LiveScreen.tsx \
        brawlfarm/web/src/instance/Instance.test.tsx \
        brawlfarm/web/src/instance/LiveScreen.test.tsx \
        brawlfarm/web/src/test/fixtures.ts brawlfarm/web/src/App.tsx
uv run python tools/scrub_check.py
git commit -m "feat(web): the Instance page frame and its live screen

The route the Fleet card links to: a header that names the instance,
links its raw screenshot and carries its three controls, the two-column
layout the plan, schedule, feed and session panels land in next, and the
15 s live screen. There is no per-instance GET on the API, so the page
picks its row out of the fleet list through useInstances, which carries
the poll and which the instance events already invalidate. The tag span
and the screenshot carry data-private so the PR's screenshots can blur
them.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 9: The feed and its sentences

The worker's session JSONL is a stream of `{"kind": ..., **fields}` objects. Nobody should
have to read `rotate_brawler brawler=TARA reason=absolute_floor` to know what happened, so
`lib/feedText.ts` turns every kind the core emits into one plain sentence, and `Feed` streams
them.

**Files:**
- Create: `brawlfarm/web/src/lib/feedText.ts`
- Create: `brawlfarm/web/src/instance/Feed.tsx`
- Modify: `brawlfarm/web/src/instance/Instance.tsx` (the left column, the single `<LiveScreen .../>` line inside the first `<div className="flex flex-col gap-4">`)
- Test: `brawlfarm/web/src/lib/feedText.test.ts`
- Test: `brawlfarm/web/src/instance/Feed.test.tsx`

**Interfaces:**
- Consumes: `FeedEvent`, `FeedKind`, `FeedRecord`, `FeedResponse` (`../api/types`); `getFeed(name, kind, limit)` (`../api/feed`); `queryKeys.feed(name, kind)` (`../api/queries`); `signed` (`../lib/format`); `feedTone`, `Tone`, `TONE_DOT` (`../lib/states`, task 3); `hhmmss` (`../lib/time`); `subscribe(kind, handler)` (`../live/useEvents`); `Segmented`, `Switch`, `ErrorBlock` (`../components/ui/`); `makeFeedRecord` (`../test/fixtures`, task 2); `stubFetch`, `jsonResponse`, `FetchCall` (`../test/http`, task 2); `renderWithProviders` (`../test/renderWithProviders`, task 3).
- Produces:
  - `feedText(record: FeedRecord): { text: string; tone: Tone }`, with `Tone` and the category-to-tone mapping taken from task 3's `lib/states.ts` rather than restated here
  - `Feed({ name, session }: { name: string; session: string | null })`
  - `feedKey(session: string | null, record: FeedRecord): string`
  - `appendRecord(prev: FeedResponse | undefined, session: string | null, record: FeedRecord): FeedResponse`
- Consumed by: nothing later by import. Task 11 counts this session's interrupts out of the same `["feed", name, "all"]` cache entry, which is why `Feed` writes a streamed record into All as well as into the record's own chip: the count stays live while the reader is looking at any chip, without a second subscription.

- [ ] **Step 1: Write the failing tests**

`brawlfarm/web/src/lib/feedText.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import type { FeedRecord } from "../api/types";
import { makeFeedRecord } from "../test/fixtures";
import { feedText } from "./feedText";

type Row = [string, Partial<FeedRecord>, string, string];

const M = "matches";
const I = "interrupts";
const E = "errors";
const O = "other";

const ROWS: Row[] = [
  ["phase playing", { event: "phase", category: M, fields: { to: "playing" } }, "Playing", "ok"],
  ["phase queuing", { event: "phase", category: M, fields: { to: "queuing" } }, "Queuing for Showdown", "ok"],
  ["phase at_menu", { event: "phase", category: M, fields: { to: "at_menu" } }, "At the menu", "ok"],
  ["phase returning", { event: "phase", category: M, fields: { to: "returning" } }, "Returning to the menu", "ok"],
  ["phase unknown", { event: "phase", category: M, fields: { to: "results" } }, "Phase results", "ok"],
  ["games_logged one", { event: "games_logged", category: M, fields: { count: 1 } }, "Logged 1 game", "ok"],
  ["games_logged many", { event: "games_logged", category: M, fields: { count: 3 } }, "Logged 3 games", "ok"],
  ["recap plain", { event: "recap", category: M, fields: { trophies: 86, games: 12, skins: 0 } }, "Match ended, +86 trophies", "ok"],
  ["recap negative", { event: "recap", category: M, fields: { trophies: -12, games: 4, skins: 0 } }, "Match ended, -12 trophies", "ok"],
  ["recap with skins", { event: "recap", category: M, fields: { trophies: 20, games: 4, skins: 1 } }, "Match ended, +20 trophies, 1 skin", "ok"],
  ["recap with skins plural", { event: "recap", category: M, fields: { trophies: 20, games: 4, skins: 2 } }, "Match ended, +20 trophies, 2 skins", "ok"],
  ["trophies", { event: "trophies", category: M, fields: { total: 41120 } }, "Trophies: 41120", "ok"],
  ["farming", { event: "farming", category: M, fields: { brawler: "NORI" } }, "Farming NORI", "ok"],
  ["select_brawler", { event: "select_brawler", category: M, fields: { brawler: "TARA", planned: true } }, "Brawler selected: TARA", "ok"],
  ["select_brawler with goal", { event: "select_brawler", category: M, fields: { brawler: "TARA", goal: 700 } }, "Brawler selected: TARA (goal 700)", "ok"],
  ["rotate_brawler", { event: "rotate_brawler", category: M, fields: { brawler: "SHELLY", reason: "absolute_floor" } }, "Rotated to SHELLY: absolute_floor", "ok"],
  ["reselect_brawler", { event: "reselect_brawler", category: I, fields: {} }, "Reselecting the brawler", "warn"],
  ["wrong_mode recovered", { event: "wrong_mode", category: I, fields: { score: 0.9, recovered: true } }, "Wrong mode detected, switched back", "warn"],
  ["wrong_mode stuck", { event: "wrong_mode", category: I, fields: { score: 0.9, recovered: false } }, "Wrong mode detected", "warn"],
  ["popup_close", { event: "popup_close", category: I, fields: {} }, "Popup closed", "warn"],
  ["team_invite_decline", { event: "team_invite_decline", category: I, fields: {} }, "Team invite declined", "warn"],
  ["daily_streak_claim", { event: "daily_streak_claim", category: I, fields: {} }, "Daily streak claimed", "warn"],
  ["ceremony_cleared", { event: "ceremony_cleared", category: I, fields: { kind: "rank_up" } }, "Ceremony cleared", "warn"],
  ["skin_reward", { event: "skin_reward", category: I, fields: { skin: "Bandita Shelly", rarity: "rare" } }, "Skin reward: Bandita Shelly", "warn"],
  ["ingame_modal_cleared", { event: "ingame_modal_cleared", category: I, fields: {} }, "In-game dialog closed", "warn"],
  ["gas_relocate", { event: "gas_relocate", category: I, fields: { target: "north", n: 2 } }, "Moved away from the gas", "warn"],
  ["bush_hide", { event: "bush_hide", category: I, fields: { target: "east" } }, "Hiding in a bush", "warn"],
  ["game_left_foreground", { event: "game_left_foreground", category: I, fields: { pkg: "com.android.settings" } }, "Game left the foreground (com.android.settings)", "warn"],
  ["disconnect", { event: "disconnect", category: I, fields: { count: 2, other_device: false } }, "Disconnected, reconnecting (2)", "warn"],
  ["recover", { event: "recover", category: I, fields: { reason: "stuck_menu", attempt: 1 } }, "Recovering: stuck_menu, attempt 1", "warn"],
  ["recover_dismissed", { event: "recover_dismissed", category: I, fields: { reason: "stuck_menu" } }, "Recovery dismissed: stuck_menu", "warn"],
  ["crash", { event: "crash", category: E, fields: { err: "adb did not answer" } }, "Crash: adb did not answer", "bad"],
  ["adb_error", { event: "adb_error", category: E, fields: { err: "device offline" } }, "ADB error: device offline", "bad"],
  ["adb_error with streak", { event: "adb_error", category: E, fields: { err: "device offline", streak: 3 } }, "ADB error: device offline (streak 3)", "bad"],
  ["bad_resolution", { event: "bad_resolution", category: E, fields: { got: [1920, 1080] } }, "Wrong resolution: 1920 x 1080, need 1600 x 900", "bad"],
  ["recalibrate", { event: "recalibrate", category: E, fields: { surface: "menu", detail: "drifted" } }, "Recalibration needed: menu", "bad"],
  ["other _error", { event: "select_brawler_error", category: E, fields: { err: "no brawler row" } }, "select brawler failed: no brawler row", "bad"],
  ["api_error", { event: "api_error", category: E, fields: { where: "trophies", err: "HTTP 503" } }, "api failed: HTTP 503", "bad"],
  ["start", { event: "start", category: O, fields: { max_games: 40, max_minutes: 90 } }, "Worker started", "idle"],
  ["stop", { event: "stop", category: O, fields: { reason: "panel", games: 12, minutes: 47 } }, "Worker stopped: panel (12 games, 47 min)", "idle"],
  ["launch_game", { event: "launch_game", category: O, fields: { method: "monkey" } }, "Brawl Stars opened", "idle"],
  ["game_closed", { event: "game_closed", category: O, fields: { reason: "stop" } }, "Brawl Stars closed: stop", "idle"],
  ["dnd", { event: "dnd", category: O, fields: { ok: true } }, "DND enabled", "idle"],
  ["dnd_off", { event: "dnd_off", category: O, fields: { ok: true } }, "DND disabled", "idle"],
  ["mega_quest", { event: "mega_quest", category: O, fields: { activated: true } }, "Mega quest activated", "idle"],
  ["account_maxed", { event: "account_maxed", category: O, fields: { goal: 1000 } }, "Every brawler is at the goal (1000)", "idle"],
  ["maxed_fallback_switch", { event: "maxed_fallback_switch", category: O, fields: { fallback: "SHELLY" } }, "Switched to the maxed fallback SHELLY", "idle"],
  ["step ok", { event: "step", category: O, fields: { step: 2, label: "Daily streak claimed", status: "ok" } }, "Daily streak claimed", "idle"],
  ["step error", { event: "step", category: O, fields: { step: 3, label: "Brawler selected", status: "error" } }, "Brawler selected", "bad"],
  ["unknown with fields", { event: "gas_edges_v2", category: O, fields: { edges: 4, n: 1 } }, "gas edges v2: edges=4, n=1", "idle"],
  ["unknown without fields", { event: "something_new", category: O, fields: {} }, "something new", "idle"],
];

describe("feedText", () => {
  it.each(ROWS)("%s", (_label, overrides, expected, tone) => {
    const line = feedText(makeFeedRecord(overrides));
    expect(line.text).toBe(expected);
    expect(line.tone).toBe(tone);
  });

  it("covers every event name the brief's table names", () => {
    const events = ROWS.map(([, o]) => o.event);
    expect(events.filter((e) => e === undefined)).toHaveLength(0);
    expect(ROWS).toHaveLength(51);
    expect(new Set(events).size).toBe(39); // 37 named kinds plus the two fallback cases
  });
});
```

`brawlfarm/web/src/instance/Feed.test.tsx`:

```tsx
/** This session's narration: what it loads per chip, what it appends from the stream, and
 * what Follow does when the reader scrolls back to read. */
import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Feed } from "./Feed";
import { makeFeedRecord } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const handlers: ((payload: unknown) => void)[] = [];

// Feed installs its own "feed" subscriber, so the test delivers frames straight to it.
// The real stream, its backoff and its de-duplication are task 2's own tests.
vi.mock("../live/useEvents", () => ({
  subscribe: (_kind: string, handler: (payload: unknown) => void) => {
    handlers.push(handler);
    return () => {
      handlers.splice(handlers.indexOf(handler), 1);
    };
  },
  useConnection: () => "live" as const,
}));

const SESSION = "session-20260911-101500.jsonl";
const FEED = "/api/instances/Pie64/feed";

function query(url: string): URLSearchParams {
  return new URLSearchParams(url.slice(url.indexOf("?") + 1));
}

/** Answer every feed request with whatever `records` makes of the chip it asked for. */
function stubFeed(records: (kind: string) => ReturnType<typeof makeFeedRecord>[]): FetchCall[] {
  return stubFetch((url) =>
    jsonResponse({ session: SESSION, records: records(query(url).get("kind") ?? "all") }),
  ).calls;
}

function lastFeedQuery(calls: FetchCall[]): URLSearchParams {
  return query(calls.filter((call) => call.url.startsWith(FEED)).at(-1)?.url ?? "");
}

function emit(record: ReturnType<typeof makeFeedRecord>, session = SESSION): void {
  act(() => {
    for (const handler of [...handlers]) {
      handler({ instance: "Pie64", session, record });
    }
  });
}

beforeEach(() => {
  handlers.length = 0;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Feed", () => {
  it("loads 200 lines of the chosen kind and reloads when the chip changes", async () => {
    const calls = stubFeed((kind) =>
      kind === "errors"
        ? [makeFeedRecord({ seq: 9, event: "crash", category: "errors", fields: { err: "boom" } })]
        : [makeFeedRecord({ seq: 1 })],
    );
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    expect(await screen.findByText("Playing")).toBeInTheDocument();
    const first = lastFeedQuery(calls);
    expect([first.get("kind"), first.get("limit")]).toEqual(["all", "200"]);
    await userEvent.click(screen.getByRole("radio", { name: "Errors" }));
    expect(await screen.findByText("Crash: boom")).toBeInTheDocument();
    const second = lastFeedQuery(calls);
    expect([second.get("kind"), second.get("limit")]).toEqual(["errors", "200"]);
  });

  it("shows the filter's own empty copy", async () => {
    stubFeed(() => []);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    expect(
      await screen.findByText("No lines yet. The feed fills as the worker plays."),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Interrupts" }));
    expect(await screen.findByText("No interrupts this session.")).toBeInTheDocument();
  });

  it("appends a live line once, however many times it arrives", async () => {
    stubFeed(() => [makeFeedRecord({ seq: 1 })]);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    await screen.findByText("Playing");
    const line = makeFeedRecord({
      seq: 2,
      event: "recap",
      category: "matches",
      fields: { trophies: 8, games: 1, skins: 0 },
    });
    emit(line);
    emit(line); // the same seq again: a reconnect replay, not a second match
    expect(await screen.findAllByText("Match ended, +8 trophies")).toHaveLength(1);
  });

  it("ignores a line from another instance", async () => {
    stubFeed(() => [makeFeedRecord({ seq: 1 })]);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    await screen.findByText("Playing");
    act(() => {
      for (const handler of [...handlers]) {
        handler({
          instance: "Pie64_1",
          session: SESSION,
          record: makeFeedRecord({ seq: 2, event: "farming", fields: { brawler: "TARA" } }),
        });
      }
    });
    await waitFor(() => {
      expect(screen.queryByText("Farming TARA")).not.toBeInTheDocument();
    });
  });

  it("turns Follow off when the reader scrolls up, and back on scrolls to the bottom", async () => {
    stubFeed(() => [makeFeedRecord({ seq: 1 })]);
    renderWithProviders(<Feed name="Pie64" session={SESSION} />);
    await screen.findByText("Playing");
    const list = screen.getByTestId("feed-list");
    Object.defineProperty(list, "scrollHeight", { value: 400, configurable: true });
    Object.defineProperty(list, "clientHeight", { value: 200, configurable: true });
    const follow = screen.getByRole("switch", { name: "Follow" });
    expect(follow).toHaveAttribute("aria-checked", "true");

    list.scrollTop = 190; // 400 - 190 - 200 = 10 px from the bottom: still following
    fireEvent.scroll(list);
    expect(follow).toHaveAttribute("aria-checked", "true");

    list.scrollTop = 100; // 100 px from the bottom, past the 40 px slack
    fireEvent.scroll(list);
    expect(follow).toHaveAttribute("aria-checked", "false");

    await userEvent.click(follow);
    expect(follow).toHaveAttribute("aria-checked", "true");
    expect(list.scrollTop).toBe(400);
  });
});
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test src/lib/feedText.test.ts src/instance/Feed.test.tsx
```

Expected: both files fail to collect with `Failed to resolve import "./feedText"` and
`Failed to resolve import "./Feed"`.

- [ ] **Step 3: Write `lib/feedText.ts`**

`brawlfarm/web/src/lib/feedText.ts`:

```ts
import type { FeedRecord } from "../api/types";
import { signed } from "./format";
import { type Tone, feedTone } from "./states";

type Fields = Record<string, unknown>;

const PHASES: Record<string, string> = {
  playing: "Playing",
  queuing: "Queuing for Showdown",
  at_menu: "At the menu",
  returning: "Returning to the menu",
};

/** Kinds whose whole meaning is the kind itself; the fields add nothing a reader wants. */
const PLAIN: Record<string, string> = {
  reselect_brawler: "Reselecting the brawler",
  popup_close: "Popup closed",
  team_invite_decline: "Team invite declined",
  daily_streak_claim: "Daily streak claimed",
  ceremony_cleared: "Ceremony cleared",
  ingame_modal_cleared: "In-game dialog closed",
  gas_relocate: "Moved away from the gas",
  bush_hide: "Hiding in a bush",
  start: "Worker started",
  launch_game: "Brawl Stars opened",
  dnd: "DND enabled",
  dnd_off: "DND disabled",
  mega_quest: "Mega quest activated",
};

function str(fields: Fields, key: string): string {
  const value = fields[key];
  return value === null || value === undefined ? "" : String(value);
}

function num(fields: Fields, key: string): number {
  const value = Number(fields[key]);
  return Number.isFinite(value) ? value : 0;
}

function has(fields: Fields, key: string): boolean {
  return fields[key] !== null && fields[key] !== undefined;
}

function words(event: string): string {
  return event.replaceAll("_", " ");
}

/**
 * One line of the worker's session narration as a sentence a person can read, plus the
 * colour of its dot. The core adds event kinds faster than this table does, so anything
 * unlisted degrades to the kind with its fields spelled out rather than disappearing.
 */
export function feedText(record: FeedRecord): { text: string; tone: Tone } {
  const f: Fields = record.fields ?? {};
  // The chip a line sits under decides its dot colour; lib/states.ts owns that mapping.
  const tone = feedTone(record.category);
  const plain = PLAIN[record.event];
  if (plain !== undefined) return { text: plain, tone };

  switch (record.event) {
    case "phase": {
      const to = str(f, "to");
      return { text: PHASES[to] ?? `Phase ${to}`, tone };
    }
    case "games_logged": {
      const n = num(f, "count");
      return { text: `Logged ${n} ${n === 1 ? "game" : "games"}`, tone };
    }
    case "recap": {
      // recap.trophies is the session delta; the "trophies" kind carries the total.
      const skins = num(f, "skins");
      const tail = skins > 0 ? `, ${skins} ${skins === 1 ? "skin" : "skins"}` : "";
      return { text: `Match ended, ${signed(num(f, "trophies"))} trophies${tail}`, tone };
    }
    case "trophies":
      return { text: `Trophies: ${num(f, "total")}`, tone };
    case "farming":
      return { text: `Farming ${str(f, "brawler")}`, tone };
    case "select_brawler":
      return {
        text: `Brawler selected: ${str(f, "brawler")}${has(f, "goal") ? ` (goal ${str(f, "goal")})` : ""}`,
        tone,
      };
    case "rotate_brawler":
      return { text: `Rotated to ${str(f, "brawler")}: ${str(f, "reason")}`, tone };
    case "wrong_mode":
      return {
        text: f.recovered === true ? "Wrong mode detected, switched back" : "Wrong mode detected",
        tone,
      };
    case "skin_reward":
      return { text: `Skin reward: ${str(f, "skin")}`, tone };
    case "game_left_foreground":
      return { text: `Game left the foreground (${str(f, "pkg")})`, tone };
    case "disconnect":
      return { text: `Disconnected, reconnecting (${num(f, "count")})`, tone };
    case "recover":
      return { text: `Recovering: ${str(f, "reason")}, attempt ${num(f, "attempt")}`, tone };
    case "recover_dismissed":
      return { text: `Recovery dismissed: ${str(f, "reason")}`, tone };
    case "crash":
      return { text: `Crash: ${str(f, "err")}`, tone };
    case "adb_error":
      return {
        text: `ADB error: ${str(f, "err")}${has(f, "streak") ? ` (streak ${str(f, "streak")})` : ""}`,
        tone,
      };
    case "bad_resolution": {
      const got = Array.isArray(f.got) ? f.got : [];
      return {
        text: `Wrong resolution: ${String(got[0])} x ${String(got[1])}, need 1600 x 900`,
        tone,
      };
    }
    case "recalibrate":
      return { text: `Recalibration needed: ${str(f, "surface")}`, tone };
    case "stop":
      return {
        text: `Worker stopped: ${str(f, "reason")} (${num(f, "games")} games, ${num(f, "minutes")} min)`,
        tone,
      };
    case "game_closed":
      return { text: `Brawl Stars closed: ${str(f, "reason")}`, tone };
    case "account_maxed":
      return { text: `Every brawler is at the goal (${num(f, "goal")})`, tone };
    case "maxed_fallback_switch":
      return { text: `Switched to the maxed fallback ${str(f, "fallback")}`, tone };
    case "step":
      // The narration mirror, whose label is already a sentence. Its own status wins
      // over the category, because step always classifies as "other".
      return { text: str(f, "label"), tone: f.status === "error" ? "bad" : tone };
    default:
      break;
  }

  // Every remaining *_error kind: api_error, farmplan_error, dnd_off_error, and the ones
  // the core has not added yet.
  if (record.event.endsWith("_error")) {
    const what = words(record.event.slice(0, -"_error".length));
    return { text: `${what} failed: ${str(f, "err")}`, tone };
  }
  const rest = Object.entries(f)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(", ");
  return { text: rest === "" ? words(record.event) : `${words(record.event)}: ${rest}`, tone };
}
```

- [ ] **Step 4: Write `instance/Feed.tsx`**

`brawlfarm/web/src/instance/Feed.tsx`:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { getFeed } from "../api/feed";
import { queryKeys } from "../api/queries";
import type { FeedEvent, FeedKind, FeedRecord, FeedResponse } from "../api/types";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Segmented } from "../components/ui/Segmented";
import { Switch } from "../components/ui/Switch";
import { feedText } from "../lib/feedText";
import { TONE_DOT } from "../lib/states";
import { hhmmss } from "../lib/time";
import { subscribe } from "../live/useEvents";

const KINDS: { value: FeedKind; label: string }[] = [
  { value: "all", label: "All" },
  { value: "matches", label: "Matches" },
  { value: "interrupts", label: "Interrupts" },
  { value: "errors", label: "Errors" },
];

const EMPTY: Record<FeedKind, string> = {
  all: "No lines yet. The feed fills as the worker plays.",
  matches: "No matches this session.",
  interrupts: "No interrupts this session.",
  errors: "No errors this session.",
};

const INITIAL_LIMIT = 200;
const FOLLOW_SLACK_PX = 40; // a nudge of the wheel is not "I want to read back"

/** A line's identity: its 1-based seq inside the session file that produced it. */
export function feedKey(session: string | null, record: FeedRecord): string {
  return `${session ?? ""}:${record.seq}`;
}

/**
 * Append one live record. A seq already in the list is dropped, so an SSE replay after a
 * reconnect cannot double a match; a different session filename means the worker rolled
 * the file, so the list starts again from that line.
 */
export function appendRecord(
  prev: FeedResponse | undefined,
  session: string | null,
  record: FeedRecord,
): FeedResponse {
  if (prev === undefined || prev.session !== session) return { session, records: [record] };
  const key = feedKey(session, record);
  if (prev.records.some((r) => feedKey(prev.session, r) === key)) return prev;
  return { session, records: [...prev.records, record] };
}

/**
 * This session's narration. History comes from the API once per chip; everything after
 * that arrives on the event stream and is written into the cache for All AND for the
 * record's own chip, so switching chips never loses a line and the session panel's
 * interrupt count (task 11) stays live without a second subscription.
 */
export function Feed({ name, session }: { name: string; session: string | null }) {
  const client = useQueryClient();
  const [kind, setKind] = useState<FeedKind>("all");
  const [follow, setFollow] = useState(true);
  const listRef = useRef<HTMLDivElement | null>(null);

  const query = useQuery({
    queryKey: queryKeys.feed(name, kind),
    queryFn: () => getFeed(name, kind, INITIAL_LIMIT),
  });

  useEffect(
    () =>
      subscribe("feed", (payload: unknown) => {
        const event = payload as FeedEvent;
        if (event.instance !== name) return;
        // "other" has no chip of its own, so those lines land under All alone.
        const targets: FeedKind[] =
          event.record.category === "other" ? ["all"] : ["all", event.record.category];
        for (const target of targets) {
          client.setQueryData<FeedResponse>(queryKeys.feed(name, target), (prev) =>
            appendRecord(prev, event.session, event.record),
          );
        }
      }),
    [client, name],
  );

  const records = query.data?.records ?? [];
  const active = query.data?.session ?? session;

  useEffect(() => {
    const el = listRef.current;
    if (el !== null && follow) el.scrollTop = el.scrollHeight;
  }, [records.length, follow, kind]);

  const onScroll = () => {
    const el = listRef.current;
    if (el === null || !follow) return;
    if (el.scrollHeight - el.scrollTop - el.clientHeight > FOLLOW_SLACK_PX) setFollow(false);
  };

  return (
    <section className="rounded-[10px] border border-line bg-panel p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 className="text-[13px] font-semibold">Feed</h2>
        <Segmented
          label="Feed filter"
          value={kind}
          options={KINDS}
          onChange={(next) => setKind(next as FeedKind)}
        />
        <div className="ml-auto">
          <Switch checked={follow} onChange={setFollow} label="Follow" />
        </div>
      </div>
      {query.isError ? (
        <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />
      ) : query.isPending ? null : records.length === 0 ? (
        <p className="p-2 text-[13px] text-muted">{EMPTY[kind]}</p>
      ) : (
        <div
          ref={listRef}
          onScroll={onScroll}
          data-testid="feed-list"
          className="max-h-[420px] overflow-y-auto"
        >
          <ul>
            {records.map((record) => {
              const line = feedText(record);
              return (
                <li key={feedKey(active, record)} className="flex items-baseline gap-2 py-[3px]">
                  <span className="font-mono text-[11px] tabular-nums text-muted">
                    {hhmmss(record.ts)}
                  </span>
                  <span
                    aria-hidden="true"
                    className={`h-[6px] w-[6px] shrink-0 rounded-full ${TONE_DOT[line.tone]}`}
                  />
                  <span className="text-[13px]">{line.text}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Mount it in the Instance page's left column**

In `brawlfarm/web/src/instance/Instance.tsx`, add the import and replace the single
`<LiveScreen name={inst.name} />` line:

```tsx
import { Feed } from "./Feed";
```

```tsx
          <LiveScreen name={inst.name} />
          <Feed name={inst.name} session={inst.session?.session ?? null} />
```

- [ ] **Step 6: Run the tests**

```bash
cd <repo>/brawlfarm/web
pnpm test src/lib/feedText.test.ts src/instance
pnpm typecheck
```

Expected: `feedText.test.ts` 52 passed (51 table rows plus the coverage check),
`Feed.test.tsx` 5 passed, `Instance.test.tsx` and `LiveScreen.test.tsx` still 7 and 2;
`tsc --noEmit` silent. A failure on the Errors chip usually means `Segmented` renders
buttons rather than radios: check its markup and change the query, not the component.

- [ ] **Step 7: Commit**

```bash
cd <repo>
git add brawlfarm/web/src/lib/feedText.ts brawlfarm/web/src/lib/feedText.test.ts \
        brawlfarm/web/src/instance/Feed.tsx brawlfarm/web/src/instance/Feed.test.tsx \
        brawlfarm/web/src/instance/Instance.tsx
uv run python tools/scrub_check.py
git commit -m "feat(web): the activity feed in plain sentences

Nobody should have to read rotate_brawler brawler=TARA
reason=absolute_floor to know what the worker did, so lib/feedText.ts
turns every kind the core emits into one sentence and anything new
degrades to the kind with its fields spelled out. The feed loads 200
lines per chip and then follows the event stream, de-duplicating on the
session file plus the line's seq so a reconnect replay cannot double a
match.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 10: The farm plan panel

The one screen in phase 4 that writes to the worker's own configuration. Every control
saves as it is touched, optimistically, and puts the previous values back when the save
fails, so the panel never shows a setting the worker is not actually running.

**Files:**
- Create: `brawlfarm/web/src/instance/FarmPlan.tsx`
- Modify: `brawlfarm/web/src/instance/Instance.tsx` (the right column, the empty `<div className="flex flex-col gap-4" />`)
- Test: `brawlfarm/web/src/instance/FarmPlan.test.tsx`

**Interfaces:**
- Consumes: `getPlan(name)`, `putPlan(name, plan)` (`../api/plans`); `FarmPlan` (the four-key body type) and `PlanResponse` (`../api/types`); `queryKeys.plan(name)` (`../api/queries`); `Button`, `ErrorBlock`, `Field`, `Segmented`, `Switch` (`../components/ui/`); `hhmm` (`../lib/time`); `toast`, `useToasts`, `resetToasts` (`../lib/toast`); `makePlan` (`../test/fixtures`, task 8); `stubFetch`, `jsonResponse`, `FetchCall` (`../test/http`, task 2); `renderWithProviders` (`../test/renderWithProviders`, task 3); the enriched body from task 7 (`current`, `roster`, `queue`, `roster_status`).
- Produces: `FarmPlan({ name }: { name: string })`, exported from `brawlfarm/web/src/instance/FarmPlan.tsx`.
- Consumed by: nothing later; task 11 mounts its own panels into the same column, below this one.

- [ ] **Step 1: Write the failing test**

`brawlfarm/web/src/instance/FarmPlan.test.tsx`:

```tsx
/** The one screen that writes the worker's own configuration: what each control saves,
 * when it saves it, and what it puts back when the save fails. */
import { renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FarmPlan } from "./FarmPlan";
import { resetToasts, useToasts } from "../lib/toast";
import { makePlan } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const PLAN = "/api/instances/Pie64/plan";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** Every plan body this panel has sent, parsed. */
function puts(calls: FetchCall[]): unknown[] {
  return calls
    .filter((call) => call.url === PLAN && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)));
}

/** Serve `body` on GET and echo the PUT back merged over it, which is what task 7's
 * route does: the same enriched shape, with the four stored keys replaced. */
function mount(body = makePlan(), putStatus = 200): FetchCall[] {
  return stubFetch((url, init) => {
    if (url !== PLAN) throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(body);
    return putStatus === 200
      ? jsonResponse({ ...body, ...JSON.parse(String(init.body)) })
      : jsonResponse({ detail: "adb did not answer" }, putStatus);
  }).calls;
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("FarmPlan", () => {
  it("switching to prestige saves the whole plan and offers the start end", async () => {
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    await userEvent.click(await screen.findByRole("radio", { name: "Prestige" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0]).toEqual({
      mode: "prestige",
      prestige_start: "highest",
      goal_trophies: 1000,
      maxed_fallback: null,
    });
    expect(toastMessages()).toEqual(["Plan saved"]);
    expect(await screen.findByRole("radio", { name: "Lowest" })).toBeInTheDocument();
    expect(screen.getByText("Goal 1000, the prestige threshold")).toBeInTheDocument();
  });

  it("shows the goal for ladder and hides the prestige caption", async () => {
    mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByLabelText("Goal")).toHaveValue(1000);
    expect(screen.queryByText("Goal 1000, the prestige threshold")).not.toBeInTheDocument();
  });

  it("caps the progress bar at 100 per cent", async () => {
    mount(makePlan({ current: { brawler: "SPIKE", trophies: 1400, goal: 1000 } }));
    renderWithProviders(<FarmPlan name="Pie64" />);
    const bar = await screen.findByTestId("plan-progress");
    expect(bar.style.width).toBe("100%");
  });

  it("lists the queue with its trophies and can show the whole roster", async () => {
    mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByText("TARA")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-roster")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show all brawlers" }));
    const rows = screen.getByTestId("plan-roster").querySelectorAll("li");
    expect([...rows].map((li) => li.textContent)).toEqual(["NORI812", "SHELLY615", "TARA540"]);
  });

  it("explains a missing roster in the words the reader can act on", async () => {
    mount(makePlan({ roster: null, queue: [], roster_status: "no_token" }));
    const first = renderWithProviders(<FarmPlan name="Pie64" />);
    expect(
      await screen.findByText("Add a Brawl Stars API token in Settings to see the roster."),
    ).toBeInTheDocument();
    first.unmount();

    mount(makePlan({ roster: null, queue: [], roster_status: "no_tag" }));
    const second = renderWithProviders(<FarmPlan name="Pie64" />);
    expect(
      await screen.findByText("Set this instance's player tag in Settings to see the roster."),
    ).toBeInTheDocument();
    second.unmount();

    mount(makePlan({ roster: null, queue: [], roster_status: "unavailable" }));
    const third = renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByText("Roster unavailable right now.")).toBeInTheDocument();
    third.unmount();

    mount(makePlan({ roster_status: "unavailable" }));
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(
      await screen.findByText("Roster unavailable right now; showing the last known list."),
    ).toBeInTheDocument();
  });

  it("offers the roster to the fallback box only once the switch is on", async () => {
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    const toggle = await screen.findByRole("switch", { name: "Maxed fallback" });
    expect(screen.queryByLabelText("Fallback brawler")).not.toBeInTheDocument();
    await userEvent.click(toggle);
    const box = await screen.findByLabelText("Fallback brawler");
    const list = document.getElementById(box.getAttribute("list") ?? "");
    expect(
      [...(list?.querySelectorAll("option") ?? [])].map((option) => option.getAttribute("value")),
    ).toEqual(["NORI", "SHELLY", "TARA"]);
    expect(puts(calls)).toHaveLength(0); // showing the box is not a change
  });

  it("puts the previous values back when the save fails", async () => {
    const calls = mount(makePlan(), 503);
    renderWithProviders(<FarmPlan name="Pie64" />);
    await userEvent.click(await screen.findByRole("radio", { name: "Prestige" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("radio", { name: "Ladder" })).toHaveAttribute("aria-checked", "true");
    });
    expect(toastMessages()).toEqual([]);
  });
});

describe("FarmPlan goal debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    resetToasts();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("sends one PUT 500 ms after the last keystroke, and none for a bad value", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    // vi.waitFor drives the fake clock; testing-library's own findBy would not.
    await vi.waitFor(() => {
      expect(screen.getByLabelText("Goal")).toBeInTheDocument();
    });
    const goal = screen.getByLabelText("Goal");

    await user.clear(goal);
    await user.type(goal, "850");
    expect(puts(calls)).toHaveLength(0); // still typing
    await vi.advanceTimersByTimeAsync(499);
    expect(puts(calls)).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1);
    await vi.waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0]).toEqual({
      mode: "ladder",
      prestige_start: "highest",
      goal_trophies: 850,
      maxed_fallback: null,
    });

    await user.clear(goal);
    await user.type(goal, "-4");
    await vi.advanceTimersByTimeAsync(1000);
    expect(puts(calls)).toHaveLength(1); // an integer >= 0 or nothing is sent
  });
});
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd <repo>/brawlfarm/web
pnpm test src/instance/FarmPlan.test.tsx
```

Expected: collection fails with `Failed to resolve import "./FarmPlan"`.

- [ ] **Step 3: Write `instance/FarmPlan.tsx`**

`brawlfarm/web/src/instance/FarmPlan.tsx`:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { getPlan, putPlan } from "../api/plans";
import { queryKeys } from "../api/queries";
import type { FarmPlan as FarmPlanBody, PlanResponse } from "../api/types";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { Segmented } from "../components/ui/Segmented";
import { Switch } from "../components/ui/Switch";
import { hhmm } from "../lib/time";
import { toast } from "../lib/toast";

const PRESTIGE_GOAL = 1000; // core/farmplan.PRESTIGE_GOAL: prestige finishes a brawler here
const DEBOUNCE_MS = 500; // a typed field saves once the typing stops, not per keystroke

/** The four keys the API stores, lifted out of the enriched response. */
function planOf(response: PlanResponse): FarmPlanBody {
  return {
    mode: response.mode,
    prestige_start: response.prestige_start,
    goal_trophies: response.goal_trophies,
    maxed_fallback: response.maxed_fallback,
  };
}

/** Why there is no roster, in words that say what to do about it (brief section 5). */
function rosterNote(plan: PlanResponse): string | null {
  switch (plan.roster_status) {
    case "no_token":
      return "Add a Brawl Stars API token in Settings to see the roster.";
    case "no_tag":
      return "Set this instance's player tag in Settings to see the roster.";
    case "unavailable":
      return plan.roster === null
        ? "Roster unavailable right now."
        : "Roster unavailable right now; showing the last known list.";
    default:
      return null;
  }
}

/**
 * The farm plan editor. Every control writes straight through: the cache is updated
 * first so the switch moves under the finger, the PUT follows, and a failure puts the
 * previous values back and shows the API's own sentence inline. The roster arrives on
 * the same response (task 7), so the queue, the progress bar and the fallback box never
 * need a second request.
 */
export function FarmPlan({ name }: { name: string }) {
  const client = useQueryClient();
  const query = useQuery({ queryKey: queryKeys.plan(name), queryFn: () => getPlan(name) });
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [failure, setFailure] = useState<unknown>(null);
  const [showAll, setShowAll] = useState(false);
  const [fallbackOn, setFallbackOn] = useState<boolean | null>(null);
  const [goalText, setGoalText] = useState<string | null>(null);
  const [fallbackText, setFallbackText] = useState<string | null>(null);
  const goalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fallbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (goalTimer.current !== null) clearTimeout(goalTimer.current);
      if (fallbackTimer.current !== null) clearTimeout(fallbackTimer.current);
    },
    [],
  );

  const save = async (patch: Partial<FarmPlanBody>) => {
    const before = client.getQueryData<PlanResponse>(queryKeys.plan(name));
    if (before === undefined) return;
    client.setQueryData<PlanResponse>(queryKeys.plan(name), { ...before, ...patch });
    try {
      const saved = await putPlan(name, { ...planOf(before), ...patch });
      client.setQueryData<PlanResponse>(queryKeys.plan(name), saved);
      setFailure(null);
      setSavedAt(new Date().toISOString());
      toast("Plan saved");
    } catch (error) {
      client.setQueryData<PlanResponse>(queryKeys.plan(name), before);
      setGoalText(null);
      setFallbackText(null);
      setFailure(error);
    }
  };

  const onGoal = (value: string) => {
    setGoalText(value);
    if (goalTimer.current !== null) clearTimeout(goalTimer.current);
    if (!/^\d+$/.test(value.trim())) return; // an integer >= 0; anything else waits
    const goal_trophies = Number(value.trim());
    goalTimer.current = setTimeout(() => {
      setGoalText(null);
      void save({ goal_trophies });
    }, DEBOUNCE_MS);
  };

  const onFallback = (value: string) => {
    setFallbackText(value);
    if (fallbackTimer.current !== null) clearTimeout(fallbackTimer.current);
    const trimmed = value.trim();
    fallbackTimer.current = setTimeout(() => {
      setFallbackText(null);
      void save({ maxed_fallback: trimmed === "" ? null : trimmed });
    }, DEBOUNCE_MS);
  };

  if (query.isPending) {
    return <section className="rounded-[10px] border border-line bg-panel p-3" />;
  }
  if (query.isError) {
    return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  }

  const plan = query.data;
  const prestige = plan.mode === "prestige";
  const goal = prestige ? PRESTIGE_GOAL : plan.goal_trophies;
  const roster = plan.roster ?? [];
  const trophiesOf = new Map(roster.map((b) => [b.name.toUpperCase(), b.trophies]));
  const progress =
    plan.current.trophies === null || goal <= 0
      ? 0
      : Math.min(100, Math.round((plan.current.trophies / goal) * 100));
  const showFallback = fallbackOn ?? plan.maxed_fallback !== null;
  const listId = `${name}-roster`;
  const note = rosterNote(plan);

  return (
    <section className="flex flex-col gap-3 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-baseline gap-2">
        <h2 className="text-[13px] font-semibold">Farm plan</h2>
        {savedAt === null ? null : (
          <span className="ml-auto text-[11px] text-muted">Saved {hhmm(savedAt)}</span>
        )}
      </div>
      {failure === null ? null : <ErrorBlock error={failure} />}

      <Segmented
        label="Plan"
        value={plan.mode}
        options={[
          { value: "ladder", label: "Ladder" },
          { value: "prestige", label: "Prestige" },
        ]}
        onChange={(mode) => void save({ mode: mode as FarmPlanBody["mode"] })}
      />

      {prestige ? (
        <Segmented
          label="Start with"
          value={plan.prestige_start}
          options={[
            { value: "highest", label: "Highest" },
            { value: "lowest", label: "Lowest" },
          ]}
          onChange={(start) =>
            void save({ prestige_start: start as FarmPlanBody["prestige_start"] })
          }
        />
      ) : null}

      {prestige ? (
        <p className="text-[12px] text-muted">Goal 1000, the prestige threshold</p>
      ) : (
        <Field
          label="Goal"
          id={`${name}-goal`}
          type="number"
          min={0}
          suffix="trophies"
          value={goalText ?? String(plan.goal_trophies)}
          onChange={onGoal}
        />
      )}

      <Switch
        label="Maxed fallback"
        checked={showFallback}
        onChange={(on) => {
          setFallbackOn(on);
          // Turning it off clears the stored name; turning it on only reveals the box,
          // because a blank fallback is the same as no fallback to the worker.
          if (!on && plan.maxed_fallback !== null) void save({ maxed_fallback: null });
        }}
      />
      {showFallback ? (
        <>
          <Field
            label="Fallback brawler"
            id={`${name}-fallback`}
            value={fallbackText ?? plan.maxed_fallback ?? ""}
            onChange={onFallback}
            list={listId}
            placeholder="Brawler name"
          />
          <datalist id={listId}>
            {roster.map((b) => (
              <option key={b.id} value={b.name} />
            ))}
          </datalist>
        </>
      ) : null}

      <div className="flex flex-col gap-1">
        <span className="text-[12px] text-muted">Current brawler</span>
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-[13px]">{plan.current.brawler ?? "none"}</span>
          <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
            {plan.current.trophies === null ? "none" : plan.current.trophies} / {goal}
          </span>
        </div>
        <div className="h-[3px] w-full bg-line">
          <div
            data-testid="plan-progress"
            className="h-full bg-accent"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <span className="text-[12px] text-muted">Next in queue</span>
        {plan.queue.length === 0 ? (
          <span className="text-[13px] text-muted">none</span>
        ) : (
          <ul>
            {plan.queue.map((brawler) => (
              <li key={brawler} className="flex items-baseline gap-2 text-[13px]">
                <span className="font-mono">{brawler}</span>
                <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
                  {trophiesOf.get(brawler.toUpperCase()) ?? "none"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      {roster.length === 0 ? null : (
        <div className="flex flex-col gap-1">
          <Button variant="text" size="sm" onClick={() => setShowAll((open) => !open)}>
            {showAll ? "Hide all brawlers" : "Show all brawlers"}
          </Button>
          {/* The API already sorts the roster by trophies descending. */}
          {showAll ? (
            <ul data-testid="plan-roster">
              {roster.map((b) => (
                <li key={b.id} className="flex items-baseline gap-2 text-[13px]">
                  <span className="font-mono">{b.name}</span>
                  <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
                    {b.trophies}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      )}

      {note === null ? null : <p className="text-[12px] text-muted">{note}</p>}
    </section>
  );
}
```

- [ ] **Step 4: Mount it in the Instance page's right column**

In `brawlfarm/web/src/instance/Instance.tsx`, add the import and fill the empty right column:

```tsx
import { FarmPlan } from "./FarmPlan";
```

```tsx
        <div className="flex flex-col gap-4">
          <FarmPlan name={inst.name} />
        </div>
```

- [ ] **Step 5: Run the tests**

```bash
cd <repo>/brawlfarm/web
pnpm test src/instance
pnpm typecheck
```

Expected: `FarmPlan.test.tsx` 8 passed, the other three instance files still green;
`tsc --noEmit` silent. If the debounce test hangs, `userEvent.setup` is missing
`advanceTimers`: user-event waits on real timers otherwise and fake timers never let it go.

- [ ] **Step 6: Commit**

```bash
cd <repo>
git add brawlfarm/web/src/instance/FarmPlan.tsx brawlfarm/web/src/instance/FarmPlan.test.tsx \
        brawlfarm/web/src/instance/Instance.tsx
uv run python tools/scrub_check.py
git commit -m "feat(web): the farm plan panel

The one phase 4 screen that writes the worker's own configuration.
Controls save as they are touched: the cache moves first so the switch
follows the finger, the PUT follows, and a failure restores the previous
values and shows the API's own sentence inline rather than leaving a
setting on screen that the worker is not running. The goal and the
fallback name save 500 ms after the typing stops, and the roster from
the plan response feeds the queue rows, the progress bar and the
fallback box's datalist.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 11: The schedule timeline and the session panel

The last two panels. The timeline is pure geometry with a test that pins real numbers, so a
bar that looks wrong can be argued about with arithmetic instead of screenshots. The session
panel's job is the awkward one: when a session ends the API stops reporting its figures, and
a panel that blanks to zeros the moment the worker stops is worse than useless.

**Files:**
- Create: `brawlfarm/web/src/lib/schedule.ts`
- Create: `brawlfarm/web/src/instance/Schedule.tsx`
- Create: `brawlfarm/web/src/instance/SessionPanel.tsx`
- Modify: `brawlfarm/web/src/instance/Instance.tsx` (the hook block above the early returns, and the right column)
- Test: `brawlfarm/web/src/lib/schedule.test.ts`
- Test: `brawlfarm/web/src/instance/Schedule.test.tsx`
- Test: `brawlfarm/web/src/instance/SessionPanel.test.tsx`

**Interfaces:**
- Consumes: `ApiError` (`../api/client`); `X` (`lucide-react`, 16 px, `strokeWidth={1.6}`, like every other icon in the panel); `SchedulePayload`, `InstancePayload` (`../api/types`; the patch body is typed as `Parameters<typeof patchSchedule>[1]`, so this task never has to name task 2's patch type); `getSchedule(name)`, `patchSchedule(name, patch)` (`../api/schedule`); `startInstance(name, hours?)` (`../api/instances`); `getFeed(name, kind, limit)` (`../api/feed`); `getStatsToday(instance?)` (`../api/stats`, task 2 -- there is one stats function and this task adds none); `queryKeys.schedule(name)`, `queryKeys.statsToday(name)`, `queryKeys.feed(name, "all")` (`../api/queries`); `Button`, `Chip`, `ErrorBlock`, `Field` (with `step`), `Switch` (`../components/ui/`); `hhmm`, `duration` (`../lib/time`); `signed` (`../lib/format`); `toast`, `useToasts`, `resetToasts` (`../lib/toast`); `makeSchedule`, `makeInstance`, `makePlan` (`../test/fixtures`, tasks 2 and 8); `stubFetch`, `jsonResponse`, `FetchCall` (`../test/http`, task 2); `renderWithProviders` (`../test/renderWithProviders`, task 3).
- Produces:
  - `timeline(payload: SchedulePayload, nowIso: string): { blocks: { leftPct: number; widthPct: number; state: "past" | "active" | "future" }[]; nowPct: number; ticks: { hour: number; leftPct: number }[] }`
  - `Schedule({ name }: { name: string })`
  - `SessionPanel({ inst, avgRank, interrupts, stopAt }: { inst: InstancePayload; avgRank: number | null; interrupts: number; stopAt: string | null })`
- Consumed by: task 12, which only looks at the finished page.

- [ ] **Step 1: Write the failing tests**

`brawlfarm/web/src/lib/schedule.test.ts`:

```ts
import { describe, expect, it } from "vitest";

import { makeSchedule } from "../test/fixtures";
import { timeline } from "./schedule";

const NOW = "2026-09-11T14:15:00";

describe("timeline", () => {
  it("places a day of three sessions against the wall clock", () => {
    // 09:00 to 11:00 is done, 13:30 to 15:00 is running, 19:00 to 20:30 is still to come.
    const t = timeline(makeSchedule(), NOW);
    expect(t.blocks).toHaveLength(3);

    expect(t.blocks[0].leftPct).toBeCloseTo(37.5, 6); // 09:00 of 24 h
    expect(t.blocks[0].widthPct).toBeCloseTo(8.333333, 5); // two hours
    expect(t.blocks[0].state).toBe("past");

    expect(t.blocks[1].leftPct).toBeCloseTo(56.25, 6); // 13:30
    expect(t.blocks[1].widthPct).toBeCloseTo(6.25, 6); // ninety minutes
    expect(t.blocks[1].state).toBe("active");

    expect(t.blocks[2].leftPct).toBeCloseTo(79.166666, 5); // 19:00
    expect(t.blocks[2].widthPct).toBeCloseTo(6.25, 6);
    expect(t.blocks[2].state).toBe("future");

    expect(t.nowPct).toBeCloseTo(59.375, 6); // 14:15
    expect(t.ticks).toEqual([
      { hour: 0, leftPct: 0 },
      { hour: 6, leftPct: 25 },
      { hour: 12, leftPct: 50 },
      { hour: 18, leftPct: 75 },
      { hour: 24, leftPct: 100 },
    ]);
  });

  it("clips a session that runs past midnight to the end of the day", () => {
    const t = timeline(
      makeSchedule({
        sessions: [{ start: "2026-09-11T22:00:00", end: "2026-09-12T01:00:00" }],
      }),
      NOW,
    );
    expect(t.blocks[0].leftPct).toBeCloseTo(91.666666, 5);
    expect(t.blocks[0].widthPct).toBeCloseTo(8.333333, 5);
    expect(t.blocks[0].state).toBe("future");
  });

  it("drops a session with no width and an undrawn day has no blocks", () => {
    const t = timeline(
      makeSchedule({
        sessions: [
          { start: "2026-09-11T10:00:00", end: "2026-09-11T10:00:00" },
          { start: "2026-09-10T22:00:00", end: "2026-09-10T23:00:00" },
        ],
      }),
      NOW,
    );
    expect(t.blocks).toHaveLength(0);
    expect(timeline(makeSchedule({ sessions: [] }), NOW).blocks).toHaveLength(0);
  });
});
```

`brawlfarm/web/src/instance/Schedule.test.tsx`:

```tsx
/** Today's sessions and the three things the reader can do to them: switch the schedule
 * off, run for a few hours now, and ask for a redraw. */
import { renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Schedule } from "./Schedule";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSchedule } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const SCHEDULE = "/api/instances/Pie64/schedule";
const START = "/api/instances/Pie64/start";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** api<T>() sends a GET as fetch(path, {}), so a missing method means GET. */
function matching(calls: FetchCall[], method: string, url: string): FetchCall[] {
  return calls.filter((call) => call.url === url && (call.init?.method ?? "GET") === method);
}

function countOf(calls: FetchCall[], method: string, url: string): number {
  return matching(calls, method, url).length;
}

function lastBody(calls: FetchCall[], method: string, url: string): unknown {
  const call = matching(calls, method, url).at(-1);
  return call === undefined ? undefined : JSON.parse(String(call.init?.body));
}

function mount(body = makeSchedule()): FetchCall[] {
  return stubFetch((url) => {
    if (url === SCHEDULE) return jsonResponse(body);
    if (url === START) return jsonResponse({ ok: true }, 202);
    throw new Error(`unstubbed request: ${url}`);
  }).calls;
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Schedule", () => {
  it("turns the schedule off and says so", async () => {
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    await userEvent.click(await screen.findByRole("switch", { name: "Schedule on" }));
    await waitFor(() => {
      expect(countOf(calls, "PUT", SCHEDULE)).toBe(1);
    });
    expect(lastBody(calls, "PUT", SCHEDULE)).toEqual({ enabled: false });
    expect(toastMessages()).toEqual(["Schedule off"]);
  });

  it("runs for a number of hours from the row", async () => {
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const hours = await screen.findByLabelText("Run for");
    expect(hours).toHaveAttribute("step", "0.5");
    await userEvent.clear(hours);
    await userEvent.type(hours, "3");
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => {
      expect(countOf(calls, "POST", START)).toBe(1);
    });
    expect(lastBody(calls, "POST", START)).toEqual({ hours: 3 });
    expect(toastMessages()).toEqual(["Running Pie64 for 3 h"]);
  });

  it("speaks the API's own sentence when Start fails, and says nothing else", async () => {
    stubFetch((url) => {
      if (url === SCHEDULE) return jsonResponse(makeSchedule());
      if (url === START) return jsonResponse({ detail: "adb did not answer" }, 503);
      throw new Error(`unstubbed request: ${url}`);
    });
    renderWithProviders(<Schedule name="Pie64" />);
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    // The success toast never fires, so the failure is the only line on screen.
    await waitFor(() => {
      expect(toastMessages()).toEqual(["adb did not answer"]);
    });
  });

  it("shows an override and clears it", async () => {
    const calls = mount(
      makeSchedule({
        override: { mode: "stop", until: "2026-09-11T18:00:00", set_at: "2026-09-11T12:00:00" },
      }),
    );
    renderWithProviders(<Schedule name="Pie64" />);
    expect(await screen.findByText("Override: stop until 18:00")).toBeInTheDocument();
    // An icon button: its aria-label is the only accessible name it has.
    await userEvent.click(screen.getByRole("button", { name: "Clear override" }));
    await waitFor(() => {
      expect(countOf(calls, "PUT", SCHEDULE)).toBe(1);
    });
    expect(lastBody(calls, "PUT", SCHEDULE)).toEqual({ clear_override: true });
    // The chip going away is the confirmation, so nothing is announced.
    expect(toastMessages()).toEqual([]);
  });

  it("says so when the day has not been drawn", async () => {
    mount(makeSchedule({ sessions: [], plan_date: null }));
    renderWithProviders(<Schedule name="Pie64" />);
    expect(
      await screen.findByText(
        "No sessions drawn yet. The supervisor draws today on its next tick.",
      ),
    ).toBeInTheDocument();
  });
});

describe("Schedule redraw", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    resetToasts();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("asks again 2 s and 10 s later, because the draw happens on the supervisor tick", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    // vi.waitFor drives the fake clock; testing-library's own findBy would not.
    await vi.waitFor(() => {
      expect(screen.getByRole("button", { name: "Redraw today" })).toBeInTheDocument();
    });
    expect(countOf(calls, "GET", SCHEDULE)).toBe(1);

    await user.click(screen.getByRole("button", { name: "Redraw today" }));
    await vi.advanceTimersByTimeAsync(0);
    expect(lastBody(calls, "PUT", SCHEDULE)).toEqual({ redraw: true });
    expect(toastMessages()).toEqual(["Redrawing today; new sessions appear after the next tick"]);
    // Every patch invalidates the key, so the PUT has already asked once by itself. The
    // two timers are what this test is about, so count from there.
    const asked = countOf(calls, "GET", SCHEDULE);

    await vi.advanceTimersByTimeAsync(2000);
    await vi.waitFor(() => {
      expect(countOf(calls, "GET", SCHEDULE)).toBe(asked + 1);
    });
    await vi.advanceTimersByTimeAsync(8000);
    await vi.waitFor(() => {
      expect(countOf(calls, "GET", SCHEDULE)).toBe(asked + 2);
    });
  });
});
```

`brawlfarm/web/src/instance/SessionPanel.test.tsx`:

```tsx
/** Six figures, and what happens to them when the worker stops. No providers: the panel
 * is handed everything it draws. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SessionPanel } from "./SessionPanel";
import { makeInstance } from "../test/fixtures";

const SESSION = {
  minutes_elapsed: 72,
  start_trophies: 41000,
  last_trophies: 41086,
  disconnect_count: 1,
  recovery_attempts: 0,
  session: "session-20260911-101500.jsonl",
};

const farming = makeInstance({
  name: "Pie64",
  state: "farming",
  games_played: 12,
  session: SESSION,
});

describe("SessionPanel", () => {
  it("shows the six figures of a live session", () => {
    render(<SessionPanel inst={farming} avgRank={3.42} interrupts={4} stopAt={null} />);
    expect(screen.getByText("12")).toBeInTheDocument(); // Games
    expect(screen.getByText("+86")).toBeInTheDocument(); // Trophies
    expect(screen.getByText("3.4")).toBeInTheDocument(); // Avg rank today
    expect(screen.getByText("1")).toBeInTheDocument(); // Disconnects
    expect(screen.getByText("1 h 12 min")).toBeInTheDocument(); // Duration
    expect(screen.getByText("4")).toBeInTheDocument(); // Interrupts
    expect(screen.queryByText(/Session ended/)).not.toBeInTheDocument();
  });

  it("reads a missing session as zeros, not as blanks", () => {
    render(
      <SessionPanel
        inst={makeInstance({ name: "Pie64", state: "starting", games_played: null, session: null })}
        avgRank={null}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(screen.getByText("none")).toBeInTheDocument(); // Avg rank today
    expect(screen.getByText("0 min")).toBeInTheDocument(); // Duration
    expect(screen.getAllByText("0").length).toBeGreaterThanOrEqual(3);
  });

  it("keeps the last live figures and captions the end of the session", () => {
    const { rerender } = render(
      <SessionPanel inst={farming} avgRank={3.42} interrupts={4} stopAt={null} />,
    );
    expect(screen.getByText("12")).toBeInTheDocument();
    rerender(
      <SessionPanel
        inst={makeInstance({
          name: "Pie64",
          state: "stopped",
          games_played: null,
          session: null,
        })}
        avgRank={null}
        interrupts={0}
        stopAt="2026-09-11T14:15:40"
      />,
    );
    expect(screen.getByText("12")).toBeInTheDocument(); // the figures do not blank out
    expect(screen.getByText("+86")).toBeInTheDocument();
    expect(screen.getByText("Session ended 14:15")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
cd <repo>/brawlfarm/web
pnpm test src/lib/schedule.test.ts src/instance/Schedule.test.tsx src/instance/SessionPanel.test.tsx
```

Expected: all three fail to collect with `Failed to resolve import "./schedule"`,
`"./Schedule"` and `"./SessionPanel"`.

- [ ] **Step 3: Write `lib/schedule.ts`**

`brawlfarm/web/src/lib/schedule.ts`:

```ts
import type { SchedulePayload } from "../api/types";

export type BlockState = "past" | "active" | "future";
export type Block = { leftPct: number; widthPct: number; state: BlockState };
export type Tick = { hour: number; leftPct: number };
export type Timeline = { blocks: Block[]; nowPct: number; ticks: Tick[] };

const DAY_MS = 24 * 60 * 60 * 1000;
const TICK_HOURS = [0, 6, 12, 18, 24];

/**
 * Midnight of the local calendar day `iso` falls in. The API writes its stamps with no
 * zone offset, which JavaScript reads as local time, so this stays in one zone
 * throughout and never has to think about UTC.
 */
function dayStart(iso: string): number {
  const d = new Date(iso);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function clamp(pct: number): number {
  return Math.max(0, Math.min(100, pct));
}

/**
 * The schedule bar's geometry: one block per session as a percentage of the day the
 * payload's `now` sits in, the now line, and the four-hourly ticks. A session that runs
 * past midnight is clipped to the end of the day, and one that falls entirely outside it
 * (a stale payload from yesterday) is dropped rather than drawn at zero width.
 */
export function timeline(payload: SchedulePayload, nowIso: string): Timeline {
  const start = dayStart(payload.now);
  const now = new Date(nowIso).getTime();
  const pct = (ms: number): number => ((ms - start) / DAY_MS) * 100;

  const blocks: Block[] = [];
  for (const session of payload.sessions) {
    const from = new Date(session.start).getTime();
    const to = new Date(session.end).getTime();
    if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) continue;
    const left = clamp(pct(from));
    const right = clamp(pct(to));
    if (right <= left) continue;
    blocks.push({
      leftPct: left,
      widthPct: right - left,
      state: now >= to ? "past" : now >= from ? "active" : "future",
    });
  }
  return {
    blocks,
    nowPct: clamp(pct(now)),
    ticks: TICK_HOURS.map((hour) => ({ hour, leftPct: (hour / 24) * 100 })),
  };
}
```

- [ ] **Step 4: Write `instance/Schedule.tsx`**

`brawlfarm/web/src/instance/Schedule.tsx`:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { startInstance } from "../api/instances";
import { queryKeys } from "../api/queries";
import { getSchedule, patchSchedule } from "../api/schedule";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { Switch } from "../components/ui/Switch";
import { timeline } from "../lib/schedule";
import { hhmm } from "../lib/time";
import { toast } from "../lib/toast";

const EMPTY = "No sessions drawn yet. The supervisor draws today on its next tick.";
// The draw happens on a supervisor tick, not on the request, so ask again twice: once for
// a tick that was already due, once for the poke this PUT sent.
const REDRAW_REFETCH_MS = [2000, 10_000];
const BLOCK_TONE: Record<string, string> = {
  past: "bg-idle opacity-40",
  active: "bg-ok",
  future: "bg-idle",
};

/** Today's sessions, the on/off switch, the manual override and the two manual controls. */
export function Schedule({ name }: { name: string }) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.schedule(name),
    queryFn: () => getSchedule(name),
  });
  const [hours, setHours] = useState("2");
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(
    () => () => {
      for (const id of timers.current) clearTimeout(id);
    },
    [],
  );

  const refetch = () => {
    void client.invalidateQueries({ queryKey: queryKeys.schedule(name) });
  };

  /** Nothing is announced until the request has settled. A rejection speaks the ApiError's
   * own detail -- the API's sentence, or the "cannot reach brawlfarm" one a dead server
   * produces -- and the success message never fires. A null message is a control whose
   * result is already visible, like the override chip disappearing. */
  const settle = async (call: Promise<unknown>, message: string | null) => {
    try {
      await call;
    } catch (error) {
      toast(error instanceof ApiError ? error.detail : "Request failed");
      return;
    }
    if (message !== null) toast(message);
    refetch();
  };

  const patch = (body: Parameters<typeof patchSchedule>[1], message: string | null) =>
    settle(patchSchedule(name, body), message);

  if (query.isPending) {
    return <section className="rounded-[10px] border border-line bg-panel p-3" />;
  }
  if (query.isError) {
    return <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />;
  }

  const payload = query.data;
  const bar = timeline(payload, payload.now);
  const parsed = Number(hours);
  const runnable = Number.isFinite(parsed) && parsed > 0;

  return (
    <section className="flex flex-col gap-3 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-center gap-2">
        <h2 className="text-[13px] font-semibold">Schedule</h2>
        <div className="ml-auto">
          <Switch
            label="Schedule on"
            checked={payload.enabled}
            onChange={(enabled) =>
              void patch({ enabled }, enabled ? "Schedule on" : "Schedule off")
            }
          />
        </div>
      </div>

      {payload.sessions.length === 0 ? (
        <p className="text-[13px] text-muted">{EMPTY}</p>
      ) : (
        <div
          className="relative h-6 w-full overflow-hidden rounded-[6px] bg-panel-2"
          data-testid="schedule-bar"
        >
          {bar.ticks.map((tick) => (
            <div
              key={tick.hour}
              className="absolute top-0 h-full w-px bg-line"
              style={{ left: `${tick.leftPct}%` }}
            />
          ))}
          {bar.blocks.map((block) => (
            <div
              key={`${block.leftPct}-${block.widthPct}`}
              className={`absolute top-1 h-4 rounded-[3px] ${BLOCK_TONE[block.state]}`}
              style={{ left: `${block.leftPct}%`, width: `${block.widthPct}%` }}
            />
          ))}
          <div
            className="absolute top-0 h-full w-[2px] bg-accent"
            style={{ left: `${bar.nowPct}%` }}
            data-testid="schedule-now"
          />
        </div>
      )}

      {payload.override === null ? null : (
        <div className="flex items-center gap-2">
          <Chip tone={payload.override.mode === "run" ? "ok" : "warn"}>
            {`Override: ${payload.override.mode} until ${hhmm(payload.override.until)}`}
          </Chip>
          {/* An icon, not a word: the chip beside it already says what is being cleared,
              and aria-label carries the sentence for a screen reader. Clearing the chip
              is its own confirmation, so there is no toast. */}
          <button
            type="button"
            aria-label="Clear override"
            onClick={() => void patch({ clear_override: true }, null)}
            className="rounded-[6px] p-1 text-muted transition-colors duration-[120ms] hover:text-text"
          >
            <X size={16} strokeWidth={1.6} aria-hidden="true" />
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <Field
          label="Run for"
          id={`${name}-hours`}
          type="number"
          min={0.5}
          step={0.5}
          suffix="hours"
          value={hours}
          onChange={setHours}
        />
        <Button
          variant="primary"
          size="sm"
          disabled={!runnable}
          disabledReason="Enter a number of hours"
          onClick={() => {
            void settle(startInstance(name, parsed), `Running ${name} for ${parsed} h`);
          }}
        >
          Start
        </Button>
        <Button
          variant="quiet"
          size="sm"
          onClick={() => {
            void patch({ redraw: true }, "Redrawing today; new sessions appear after the next tick");
            for (const delay of REDRAW_REFETCH_MS) {
              timers.current.push(setTimeout(refetch, delay));
            }
          }}
        >
          Redraw today
        </Button>
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Write `instance/SessionPanel.tsx`**

`brawlfarm/web/src/instance/SessionPanel.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";

import type { InstancePayload } from "../api/types";
import { signed } from "../lib/format";
import { duration, hhmm } from "../lib/time";

/** States in which the API has stopped reporting a session, so the figures are frozen. */
const FROZEN = new Set(["stopped", "scheduled_break", "offline"]);

type Figures = {
  Games: string;
  Trophies: string;
  "Avg rank today": string;
  Disconnects: string;
  Duration: string;
  Interrupts: string;
};

function figuresOf(inst: InstancePayload, avgRank: number | null, interrupts: number): Figures {
  const session = inst.session;
  const start = session?.start_trophies ?? null;
  const last = session?.last_trophies ?? null;
  return {
    Games: String(inst.games_played ?? 0),
    // One null end of the pair makes the difference meaningless, so it reads 0, not NaN.
    Trophies: start === null || last === null ? "0" : signed(last - start),
    // Rank lives in games.csv, not the feed, so it comes from the stats route for today.
    "Avg rank today": avgRank === null ? "none" : avgRank.toFixed(1),
    Disconnects: String(session?.disconnect_count ?? 0),
    Duration: duration(session?.minutes_elapsed ?? 0),
    Interrupts: String(interrupts),
  };
}

/**
 * This session at a glance. When the worker stops, the API drops status.json's session
 * block and every figure would snap to zero, which reads as "the session did nothing".
 * The panel keeps the last figures it saw live and captions when the session ended,
 * preferring the timestamp of the feed's own `stop` line over the moment the browser
 * happened to notice.
 */
export function SessionPanel({
  inst,
  avgRank,
  interrupts,
  stopAt,
}: {
  inst: InstancePayload;
  avgRank: number | null;
  interrupts: number;
  stopAt: string | null;
}) {
  const live = !FROZEN.has(inst.state);
  const lastLive = useRef<Figures>(figuresOf(inst, avgRank, interrupts));
  const [endedAt, setEndedAt] = useState<string | null>(null);
  const shown = live ? figuresOf(inst, avgRank, interrupts) : lastLive.current;

  useEffect(() => {
    if (live) {
      lastLive.current = figuresOf(inst, avgRank, interrupts);
      setEndedAt(null);
      return;
    }
    setEndedAt((previous) => previous ?? stopAt ?? new Date().toISOString());
  });

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-baseline gap-2">
        <h2 className="text-[13px] font-semibold">Session</h2>
        {endedAt === null ? null : (
          <span className="ml-auto text-[11px] text-muted">Session ended {hhmm(endedAt)}</span>
        )}
      </div>
      <dl className="grid grid-cols-3 gap-x-3 gap-y-2">
        {Object.entries(shown).map(([label, value]) => (
          <div key={label} className="flex flex-col">
            <dt className="text-[11px] text-muted">{label}</dt>
            <dd className="font-mono text-[15px] tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
```

- [ ] **Step 6: Mount both panels**

In `brawlfarm/web/src/instance/Instance.tsx`, add `useQuery` to the react-query import
(the file has only `useQueryClient` so far) and add the four imports:

```tsx
import { getFeed } from "../api/feed";
import { getStatsToday } from "../api/stats";
import { Schedule } from "./Schedule";
import { SessionPanel } from "./SessionPanel";
```

Add two queries right after the `fleet` query, above the early returns (hooks first,
always). `getStatsToday(name)` is task 2's function scoped to one instance: there is one
stats call in the panel and one `["stats", "today", ...]` key family behind it, so the
Fleet totals line and this panel cannot drift apart.

```tsx
  const stats = useQuery({
    queryKey: queryKeys.statsToday(name),
    queryFn: () => getStatsToday(name),
  });
  // The same key the Feed component fills, so its SSE appends keep these two counts live.
  const feed = useQuery({
    queryKey: queryKeys.feed(name, "all"),
    queryFn: () => getFeed(name, "all", 200),
  });
```

Just above the `return (`, derive the session panel's three inputs:

```tsx
  const records = feed.data?.records ?? [];
  const interrupts = records.filter((r) => r.category === "interrupts").length;
  const stopAt = [...records].reverse().find((r) => r.event === "stop")?.ts ?? null;
```

Replace the right column:

```tsx
        <div className="flex flex-col gap-4">
          <FarmPlan name={inst.name} />
          <Schedule name={inst.name} />
          <SessionPanel
            inst={inst}
            avgRank={stats.data?.summary.avg_rank ?? null}
            interrupts={interrupts}
            stopAt={stopAt}
          />
        </div>
```

Finally, extend `stubPage` in `brawlfarm/web/src/instance/Instance.test.tsx` so every
query the finished page makes has an answer. The stub throws on an unknown URL, which is
how a missed route announces itself:

```tsx
function stubPage(instances: ReturnType<typeof makeInstance>[]): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") return jsonResponse({ instances });
    if (url.endsWith("screenshot.png")) return pngResponse();
    // Only summary.avg_rank is read, so the rest of the stats body is left out.
    if (url.startsWith("/api/stats")) {
      return jsonResponse({ range: "today", instances: ["Pie64"], summary: { avg_rank: 3.4 } });
    }
    if (url.startsWith("/api/instances/Pie64/feed")) {
      return jsonResponse({ session: null, records: [] });
    }
    if (url === "/api/instances/Pie64/plan") return jsonResponse(makePlan());
    if (url === "/api/instances/Pie64/schedule") return jsonResponse(makeSchedule());
    return jsonResponse({ ok: true }, 202);
  }).calls;
}
```

and widen that file's fixtures import to
`import { makeInstance, makePlan, makeSchedule } from "../test/fixtures";`.

- [ ] **Step 7: Run the whole web suite**

```bash
cd <repo>/brawlfarm/web
pnpm test
pnpm typecheck
pnpm build
```

Expected: every file green, the earlier tasks' included; `tsc --noEmit` silent; `vite build` writes
`dist/index.html`. If the redraw test reports 1 GET after advancing 2000 ms, react-query has
not finished its refetch inside the fake clock: add `await vi.advanceTimersByTimeAsync(0)`
after the advance, never a real `sleep`.

- [ ] **Step 8: Commit**

```bash
cd <repo>
git add brawlfarm/web/src/lib/schedule.ts brawlfarm/web/src/lib/schedule.test.ts \
        brawlfarm/web/src/instance/Schedule.tsx brawlfarm/web/src/instance/Schedule.test.tsx \
        brawlfarm/web/src/instance/SessionPanel.tsx \
        brawlfarm/web/src/instance/SessionPanel.test.tsx \
        brawlfarm/web/src/instance/Instance.tsx brawlfarm/web/src/instance/Instance.test.tsx
uv run python tools/scrub_check.py
git commit -m "feat(web): the schedule timeline and the session panel

lib/schedule.ts is pure geometry with a fixed-input test, so a bar that
looks wrong is an arithmetic argument rather than a screenshot one. The
schedule panel asks again 2 s and 10 s after a redraw because the draw
happens on a supervisor tick, not on the request. The session panel
keeps the last figures it saw live when the worker stops, since the API
drops the session block and six zeros read as a session that did
nothing.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

---
### Task 12: Finish. Polish pass, live evidence, docs and the pull request

No new features. This task proves the eleven before it actually work in a browser against a
real BlueStacks instance, and writes the two documents that ship with them.

**This task has exactly one commit of its own, and it is a docs commit** (`README.md`). If a check below fails, the fix belongs to the component that owns it: make
it a small `fix(web): ...` commit naming that file, with the same two trailers, and re-run
that component's test file. Do not fold a behaviour fix into the docs commit.

**Files:**
- Modify: `README.md` (the status line at line 5; the `## Development` block at lines 28 to 35; the `## The panel and its API` opening paragraph at line 50; three rows of the API table)
- Create (outside the repo): `<scratchpad>/phase4-live-evidence.py`, `<scratchpad>/shots/*.png`

**Interfaces:**
- Consumes: everything tasks 1 to 11 produced. `playwright-cli`; `uv run brawlfarm`; the API at `http://127.0.0.1:8765`.
- Produces: the README's panel section, the PR body, and the blurred screenshots attached to it. The plan board on `main` is not touched here: the controller updates `docs/PLAN.md` after the merge, as in every phase.

- [ ] **Step 1: Serve the real panel**

```bash
cd <repo>
pnpm --dir brawlfarm/web build
uv run brawlfarm --no-browser
```

Expected: `vite build` writes `brawlfarm/web/dist/index.html`, and the server prints the
three panel lines. Leave it running in this shell; every step below uses another one. The
instance is the real one: `Pie64` on adb port 5555, its config already in
`%LOCALAPPDATA%\brawlfarm\config.toml`.

- [ ] **Step 2: Keyboard and focus pass**

```bash
playwright-cli open http://127.0.0.1:8765/
playwright-cli resize 1280 900
playwright-cli snapshot
```

Then, pressing Tab from the top of the page, confirm each of these and note any that fail:

- [ ] Tab order on Fleet is rail wordmark, Fleet, Stats, Settings, each instance link, Start all, Stop all, then each card: the card link, Stop, Restart, Open. Nothing is reachable that is not visible.
- [ ] Every focused control shows the 2 px accent ring (`:focus-visible`), including the card `Link`, the `Switch`, the `Segmented` radios, and the Instance page's Screenshot link, Refresh button and Full size link.
- [ ] `playwright-cli press Enter` on a focused card link opens `/instances/Pie64`; `playwright-cli press Enter` on Stop stops without also following the card link.
- [ ] The alerts `Drawer`: opening it moves focus inside, Tab cycles within it, `playwright-cli press Escape` closes it and returns focus to the Alerts button.
- [ ] On the Instance page, the `Segmented` feed filter moves with ArrowLeft and ArrowRight and reports `aria-checked`; the Follow `Switch` toggles with Space.
- [ ] No control is reachable that has no accessible name (`playwright-cli snapshot` shows a name for every button, link, switch and radio).

- [ ] **Step 3: Reduced motion, phone width and the light theme**

```bash
playwright-cli eval "matchMedia('(prefers-reduced-motion: reduce)').matches"
playwright-cli resize 390 844
playwright-cli screenshot --filename=phone-fleet.png
playwright-cli resize 1280 900
playwright-cli eval "document.documentElement.dataset.theme = 'light'"
playwright-cli screenshot --filename=light-fleet.png
playwright-cli eval "delete document.documentElement.dataset.theme"
```

- [ ] At 390 px the rail is a row of links, the instance list is hidden, the Fleet grid is one column and nothing overflows horizontally (`playwright-cli eval "document.documentElement.scrollWidth <= window.innerWidth"` is `true`).
- [ ] In the light theme every panel, chip and caption is still legible: no white-on-white chip, no accent text on an accent fill.
- [ ] With reduced motion forced on in the OS, hover and press have no transition and the toast's progress bar jumps rather than animating.

- [ ] **Step 4: Screenshots for the pull request**

Blur every private element before each shot. `[data-private]` is on the Instance header's
tag span (task 8) and on every `Thumb` image (task 3).

```bash
playwright-cli goto http://127.0.0.1:8765/
playwright-cli resize 1280 900
playwright-cli eval "document.querySelectorAll('[data-private]').forEach(el => { el.style.filter = 'blur(14px)' })"
playwright-cli screenshot --filename=fleet.png

playwright-cli goto http://127.0.0.1:8765/instances/Pie64
playwright-cli eval "document.querySelectorAll('[data-private]').forEach(el => { el.style.filter = 'blur(14px)' }); return document.querySelectorAll('[data-private]').length"
playwright-cli screenshot --filename=instance.png

playwright-cli click "getByRole('button', { name: 'Alerts' })"
playwright-cli eval "document.querySelectorAll('[data-private]').forEach(el => { el.style.filter = 'blur(14px)' })"
playwright-cli screenshot --filename=alerts.png
```

- [ ] The `eval` on the Instance page returns a number greater than 0: if it returns 0, the tag or the thumbnail lost its `data-private` attribute and the shot is not safe to publish.
- [ ] Open each PNG and read it: no player tag, no account nickname, no Windows user path in a title bar, no token anywhere. A shot that shows any of them is deleted, not cropped.
- [ ] Move the three PNGs into the scratchpad's `shots/` folder. They never enter the repo.

- [ ] **Step 5: Write and run the live-evidence script**

Save as `<scratchpad>/phase4-live-evidence.py`. It stays outside the repo: it names a real
instance and writes a transcript, and neither belongs in git.

```python
"""Phase 4 live evidence: drive the real instance through the panel's own API and record
what the panel should be showing while it happens.

Run it beside a running `uv run brawlfarm --no-browser` with the panel open in a browser,
so the transitions it forces are the ones being watched on screen. It never touches the
worker directly: every call is one the panel's own buttons make, which is the point.

The transcript is scrubbed as it is written: player_tag is dropped from every payload, so
the file can be pasted into a PR without a second pass.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "http://127.0.0.1:8765"
NAME = "Pie64"
OUT = Path(__file__).with_name("phase4-live-evidence.jsonl")


def call(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def scrub(payload: dict) -> dict:
    """Never write the tag to disk; the instance name is already an invented one."""
    return {k: v for k, v in payload.items() if k != "player_tag"}


def view() -> dict:
    _status, body = call("GET", "/api/instances")
    for instance in body["instances"]:
        if instance["name"] == NAME:
            return scrub(instance)
    raise SystemExit(f"{NAME} is not configured; check config.toml")


def note(step: str, **extra: object) -> None:
    line = {"at": datetime.now().isoformat(timespec="seconds"), "step": step, **extra}
    print(json.dumps(line))
    with OUT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def wait_for(step: str, *states: str, timeout_s: float = 300.0) -> dict:
    """Poll the list until the instance reaches one of `states`, recording every change."""
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        current = view()
        if current["state"] != last:
            note(step, state=current["state"], phase=current["phase"], note=current["note"])
            last = current["state"]
        if current["state"] in states:
            return current
        time.sleep(2.0)
    raise SystemExit(f"{step}: {NAME} never reached {states} (last {last})")


def main() -> int:
    status, health = call("GET", "/api/health")
    note("health", status=status, version=health["version"])

    # 1. Park it: a stop override, so nothing the scheduler wants interferes.
    call("POST", f"/api/instances/{NAME}/stop")
    wait_for("parked", "stopped", "scheduled_break", "offline")

    # 2. Start from the panel and watch the chip walk Starting -> Farming.
    call("POST", f"/api/instances/{NAME}/start")
    wait_for("started", "farming", timeout_s=420.0)

    # 3. Wait for one match to finish: the feed's recap line is the proof.
    deadline = time.monotonic() + 900.0
    while time.monotonic() < deadline:
        _status, feed = call("GET", f"/api/instances/{NAME}/feed?kind=matches&limit=50")
        recaps = [r for r in feed["records"] if r["event"] == "recap"]
        if recaps:
            note("match", session=feed["session"], seq=recaps[-1]["seq"], fields=recaps[-1]["fields"])
            break
        time.sleep(10.0)
    else:
        raise SystemExit("no recap line within 15 minutes")

    # 4. A plan change must reach farmplan.json, which the worker re-reads live.
    before = call("GET", f"/api/instances/{NAME}/plan")[1]
    goal = 900 if before["goal_trophies"] != 900 else 950
    call("PUT", f"/api/instances/{NAME}/plan", {**{k: before[k] for k in
         ("mode", "prestige_start", "goal_trophies", "maxed_fallback")}, "goal_trophies": goal})
    time.sleep(60.0)
    after = call("GET", f"/api/instances/{NAME}/plan")[1]
    note("plan", wrote=goal, read_back=after["goal_trophies"], roster_status=after["roster_status"])
    assert after["goal_trophies"] == goal

    # 5. Stop after this match: "Stopping after this match", then Stopped.
    call("POST", f"/api/instances/{NAME}/stop")
    wait_for("stopping", "stopping", timeout_s=60.0)
    wait_for("stopped", "stopped", "scheduled_break", timeout_s=900.0)

    # 6. Put the plan back the way it was.
    call("PUT", f"/api/instances/{NAME}/plan", {k: before[k] for k in
         ("mode", "prestige_start", "goal_trophies", "maxed_fallback")})
    note("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```bash
uv run python "<scratchpad>/phase4-live-evidence.py"
```

While it runs, watch the browser and tick these off:

- [ ] The Fleet card's chip walks Starting to Farming; the thumbnail starts updating.
- [ ] The Instance feed streams the match without a reload: phase lines, then
      "Match ended, +N trophies".
- [ ] The farm plan panel shows "Saved HH:MM" and the roster rows; `roster_status` in the
      transcript is `ok` (if it is `no_token` or `no_tag`, fill them in Settings' config.toml
      first and re-run; `unavailable` means the token's IP allowlist does not cover this
      machine, which is a configuration note for the PR, not a bug in the panel).
- [ ] Stop shows "Stopping after this match" and the chip turns Stopped when the match ends.
- [ ] Kill the `uv run brawlfarm` shell with Ctrl+C: the connection pill turns Reconnecting
      within a second or two. Start it again: the pill turns Live and the Fleet card catches
      up without a reload.

- [ ] **Step 6: Update the README**

Replace line 5:

```markdown
Status: under construction. Phase 4 of 8 (the control panel: shell, Fleet and Instance). The setup wizard and the stats screens arrive in later phases; see `docs/PLAN.md`.
```

Replace the `## Development` code block:

````markdown
```
uv sync --group dev
corepack enable
pnpm --dir brawlfarm/web install
pnpm --dir brawlfarm/web build     # the panel is served from brawlfarm/web/dist
uv run pytest
pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web typecheck
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
```

`pnpm --dir brawlfarm/web dev` serves the panel on Vite's port with hot reload and proxies `/api` to a `uv run brawlfarm` on 8765, so the two run side by side while you work on the UI.
````

Replace the `## The panel and its API` opening paragraph (line 50):

```markdown
The panel lives at `http://127.0.0.1:8765/`: a Fleet page with one card per instance led by its live screen, and an Instance page with the screen, the activity feed in plain sentences, the farm plan, today's schedule and the session's figures. Change the port in Settings (it takes effect on the next start) or for one run with `--port`. The API behind it is browsable at `http://127.0.0.1:8765/docs`.
```

In the API table, replace the plan row and the feed row in place, and add the dismiss-all
row after `POST /api/alerts/{id}/dismiss`:

```markdown
| GET, PUT | `/api/instances/{name}/plan` | the farm plan, plus the owned roster, the queue and the current brawler |
| GET | `/api/instances/{name}/feed` | session narration with a `seq` on every record, `kind=all\|matches\|interrupts\|errors` |
| POST | `/api/alerts/dismiss-all` | mark every alert read |
```

- [ ] **Step 7: Final gate, then commit the docs**

```bash
pnpm --dir brawlfarm/web typecheck && pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web build
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
uv build --wheel
uv run python -c "import zipfile,glob; z=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]); names=z.namelist(); print('index:', 'brawlfarm/web/dist/index.html' in names); print('src leaked:', any(n.startswith('brawlfarm/web/src/') for n in names))"
git status --porcelain
```

Expected: the web suite green, `tsc --noEmit` silent, `dist/index.html` written, the full
pytest suite green with no warnings, `All checks passed!`, every file formatted, `0 hit(s)`,
`index: True` and `src leaked: False`, and `git status` showing only `README.md` (the wheel
and `dist/` are gitignored).

```bash
git config user.name    # must print as9pa before committing
git add README.md
git commit -m "docs: the panel is real, and the README says how to run it

Phase 4 replaces the placeholder page with the Fleet and Instance
screens, so the README's status line, its development steps (pnpm and
the dev proxy) and the panel section now describe what is actually
served. The API table gains dismiss-all, the seq on every feed record
and the roster on the plan route. docs/PLAN.md is left alone: the board
is updated on main after the merge, as in every phase.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
git push -u origin phase-4/ui-shell-fleet-instance
```

- [ ] **Step 8: Open the pull request**

```bash
gh pr create --base main --title "Phase 4: the control panel (shell, Fleet, Instance)" --body-file /dev/stdin <<'EOF'
## What

The panel at `http://127.0.0.1:8765/` is real. A shell (left rail, top bar with a live connection pill, alerts drawer), a Fleet home page with one card per instance led by its live screen, and an Instance page with the live screen, the activity feed in plain sentences, the farm plan editor, today's schedule as a timeline and the session's six figures. Stats and Settings are named placeholders for phases 6 and 5.

Three small API additions come with it, because the UI could not be built without them: `POST /api/alerts/dismiss-all`, a `seq` on every feed record (so a server-sent line can be de-duplicated against a polled one), and the owned-brawler roster, the queue and the current brawler on `GET|PUT /api/instances/{name}/plan`, behind a five-minute per-instance cache that keeps the last good list when the Brawl Stars API is unreachable. `core/farmplan.py` gains one new pure function, `plan_queue`; nothing else in `core/` changes.

Vite 7, React 19, TypeScript strict, Tailwind v4, react-router v7, TanStack Query v5, lucide-react. CI builds and tests the web app before pytest, and the wheel now carries `brawlfarm/web/dist`.

## How to verify

```
corepack enable
pnpm --dir brawlfarm/web install --frozen-lockfile
pnpm --dir brawlfarm/web typecheck && pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web build
uv run pytest -q
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
uv run brawlfarm --no-browser      # then open http://127.0.0.1:8765/
```

Wheel check (that the built page ships and the sources do not):

```
uv build --wheel
uv run python -c "import zipfile,glob; z=zipfile.ZipFile(sorted(glob.glob('dist/*.whl'))[-1]); n=z.namelist(); print('brawlfarm/web/dist/index.html' in n, any(p.startswith('brawlfarm/web/src/') for p in n))"
```

(paste: the pytest summary line, the vitest summary line, the scrub output, the CI run URL, the wheel check's `True False`)

## Screenshots

Player tags and every live screen are blurred before the shot (`[data-private]` plus a `filter: blur(14px)`), at 1280 x 900.

- Fleet: (attach `fleet.png`)
- Instance: (attach `instance.png`)
- Alerts drawer: (attach `alerts.png`)

## Live evidence

Driven on the real instance (`Pie64`, adb 5555) from the panel itself:

- [ ] Start from the Fleet card: the chip walked Starting to Farming.
- [ ] The feed streamed a whole match without a reload, ending in "Match ended, +N trophies".
- [ ] A goal change in the farm plan reached `farmplan.json` and read back within a minute.
- [ ] Stop showed "Stopping after this match", then Stopped when the match ended.
- [ ] Stopping the server turned the connection pill Reconnecting; restarting it turned it Live and the cards caught up without a reload.

(paste: the scrubbed transcript lines from the live-evidence run)

## Safety-rail checklist

- [ ] The UI never sends a tap and never exposes a shop or purchase action; it only calls the API.
- [ ] The only file under `brawlfarm/core/` that changed is `farmplan.py`, and only by adding `plan_queue`. `controller.py`, `states.py`, `vision.py` and `config.py`'s calibration block are untouched; `tests/test_never_tap_rail.py` passes unchanged.
- [ ] Loopback only: no CORS middleware, no authentication added, the Vite proxy covers development.
- [ ] Instance names in URLs are validated by the API (`[A-Za-z0-9_-]{1,32}`) before any filesystem access.
- [ ] The Brawl Stars token and every player tag stay out of the logs, the client, the tests, the fixtures, the screenshots and this text. `tools/scrub_check.py` prints `0 hit(s)`.
- [ ] No `discord` import anywhere.

## Rollback

Revert the merge commit. `brawlfarm/web/dist` is gitignored, so a revert returns the served page to the phase 3 placeholder and changes nothing outside this repo. Workers started from the panel keep running and are reattached by any later supervisor start.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV
EOF
```

Then attach the three PNGs to the PR (`gh pr comment` with the images, or drag them into
the body in the browser), and once CI is green fill in the pasted outputs with
`gh pr edit --body-file`. Report the PR URL and the CI run URL: the board entry for phase 4
(this plan,
`docs/superpowers/plans/2026-09-11-phase-4-ui-shell-fleet-instance.md`, and the PR link) is
written on `main` after the merge, which is how every phase before this one closed.
