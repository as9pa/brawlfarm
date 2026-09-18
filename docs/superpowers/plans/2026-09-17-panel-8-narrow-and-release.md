# Panel PR 8: Narrow screens and release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two deferred narrow-screen items so a phone can reach an instance from any page and can tell that the settings section row scrolls, then bump the package to 1.1.0 and refresh the four README screenshots so the owner can cut the release.

**Architecture:** Two small local UI changes and a release bump. Nothing new is invented: the instance sheet reuses the existing `Drawer` (scrim, focus trap, Escape, Close button) and the existing rail link classes, and the settings cue is one absolutely positioned gradient element. The version lives in three files that have to agree, and the release workflow checks the `pyproject.toml` one against the tag.

**Tech Stack:** React 19, TypeScript 5.9, Vite 7, Tailwind 4, vitest 3, react-router 7, `pnpm`; Python 3.13, FastAPI, `uv`, hatchling.

**Source:** panel critique items 5 (`shell-rail-narrow`, minor) and 70 (`set-nav-narrow`, nit), both marked "Deferred to the last PR (narrow screens only)" in `docs/superpowers/specs/2026-09-17-panel-critique.md`, plus the PR 8 row of that spec's pull request table.

**Branch:** `panel/narrow-and-release`, cut from `main` after PR 7 (`panel/calibration`) merges.

## Global Constraints

- No em-dashes and no emoji anywhere: code, comments, tests, prose, commit messages, pull request body.
- Never write the legacy tool name or any legacy tag anywhere. The sibling reference checkout is read-only and its name, tags, nicknames and path stay out of this repository. `tools/scrub_check.py` is the check.
- The gate, run from the worktree root before every commit:

```
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
uv run pytest -q -p no:cacheprovider
uv run ruff check .
uv run ruff format --check .
uv run python tools/scrub_check.py
```

  `tools/scrub_check.py` must print `0 hit(s)`.
- Code review is on. Every task gets a spec-compliance and code-quality review pass on **sonnet** before it counts as complete, and the branch gets a whole-branch review on **sonnet** before the pull request opens. Findings are fixed by an implementer, then re-reviewed once.
- Conventional commit subjects with a scope. Every commit message ends with these two trailers:

```
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01E1U94d3i2jWe3tvmSRjcki
```

- Sentence case for every string a reader sees, except table headers and the rail eyebrow, which stay uppercase.
- Reuse what the kit already ships: `src/lib/copy.ts` for shared strings, `Button` with its four variants (`primary`, `secondary`, `quiet`, `danger`), the one focus ring, `t-name` for instance names. Do not add a second overlay primitive; `components/ui/Drawer.tsx` is the one.
- **The 820 px breakpoint value does not change.** Every class added here reuses the existing `min-[820px]:` prefix verbatim. No new breakpoint, no change to `Shell.tsx`.
- Nothing here touches `brawlfarm/core/`. The safety rails in `CONTRIBUTING.md` (never-tap logic, verify-then-act, the 1600x900 assertion, tap coordinates, OCR needles and templates) are out of scope and must not be edited. This is not a calibration pull request.
- No API change. No new endpoint, no changed response shape, no new query key.
- Scope is fixed by the owner's ruling that only he uses the panel, at this PC. These two items stay small. Do not take the chance to restyle the rail or the settings nav.

## Decisions already made, do not re-open

- **Item 5 takes the sheet, not the Fleet disclosure.** A disclosure inside the Fleet link would nest a toggle button inside a `NavLink`, making one row two controls and giving the rail a second navigation model at one width only. The sheet reuses `Drawer` whole: scrim, `useFocusTrap` (focus in, Tab cycles, Escape closes, focus returns) and the Close button. `Drawer` is `w-[360px]`, which fits a 400 px viewport, so **`Drawer.tsx` is not edited**; changing its width would change the alerts drawer too and is out of scope.
- **The sheet's open state is local `useState` in `Rail.tsx`, not a module store.** `src/lib/alertsDrawer.ts` exists because the top bar and the Fleet alert strip have no common parent below `Shell`. Here the button and the sheet are in one component, so a store would be ceremony. Do not add `src/lib/instancesSheet.ts`.
- **Item 70 takes the fade mask, not a select.** `SettingsNav.tsx` is a `ul` of `NavLink`s and its own comment says NavLink is used so the current section gets `aria-current="page"` without the component tracking the route. A `select` cannot reproduce that: it would drop the links, move routing into an `onChange` and lose `aria-current`. The fade is one `aria-hidden` element with no scroll listener.
- **The release notes are not a repo file.** There is no CHANGELOG and `docs/release.md` already states the convention: `gh release create v1.1.0 --generate-notes`, then edit the generated list. The notes for this release are assembled from the eight PR bodies grouped by page and pasted into the GitHub release body. Do not add a CHANGELOG.md and do not edit `docs/release.md`.

## Blocking dependencies

- **The branch is blocked on PRs 3 to 7.** PR 3 (`panel/fleet-shell`) rewrites the rail's instance row: the instance name gets the `t-name` class and the colour-only dot becomes a `StateChip`. Task 1 applies **on top of** that. Before writing Task 1, read `brawlfarm/web/src/app/Rail.tsx` on the merge base and use whatever the instance row renders there as the body of the extracted `InstanceLink`. Do not reintroduce the `TONE_DOT` dot or the `font-mono` name if PR 3 has removed them.
- Task 3 (screenshots) runs after Tasks 1 and 2 and after PRs 3 to 7 are merged, because the captures have to show the finished panel.
- Task 4 (version bump) runs last, so the bumped version is what the screenshots and the release tag describe.
- Tasks 1 and 2 are independent of each other.

## File Structure

- `brawlfarm/web/src/app/Rail.tsx`, `brawlfarm/web/src/app/Rail.test.tsx`: the fifth narrow-only link and the instances sheet. Task 1.
- `brawlfarm/web/src/settings/SettingsNav.tsx`, new `brawlfarm/web/src/settings/SettingsNav.test.tsx`: the scroll fade cue. Task 2.
- `docs/img/fleet.png`, `docs/img/instance.png`, `docs/img/settings.png`, `docs/img/calibration.png`, `README.md`: refreshed captures. Task 3.
- `pyproject.toml`, `brawlfarm/__init__.py`, `brawlfarm/web/package.json`, `README.md`: 1.1.0. Task 4.

---

### Task 1: An instances sheet on narrow screens

**Files:**
- Modify: `brawlfarm/web/src/app/Rail.tsx` (the file header comment; the `ul` whose class begins `flex gap-1 px-2 pb-2 min-[820px]:block`; the `div` whose class is `hidden min-[820px]:block`)
- Modify: `brawlfarm/web/src/app/Rail.test.tsx` (add cases to the existing `describe("Rail", ...)`, reusing its `stubInstances()` helper, which stubs `Pie64`, `Pie64_1` and `Pie64_3`)
- Do not modify: `brawlfarm/web/src/components/ui/Drawer.tsx`

**Interfaces:**
- Consumes: `useInstances` (already imported), `Drawer` from `../components/ui/Drawer`, `useState` from `react`.
- Produces: no new export. `InstanceLink` is a module-local component inside `Rail.tsx`. Its prop type is derived from the hook rather than imported, so the row type cannot drift:

```ts
type InstanceRow = NonNullable<ReturnType<typeof useInstances>["data"]>[number];
```

Notes for the implementer:
- The desktop instance list stays where it is and stays hidden under 820 px. The sheet is a second way into the same data, not a replacement.
- Extract today's instance row into one local component and call it from both places, so the desktop list and the sheet can never disagree:

```tsx
function InstanceLink({ inst, onNavigate }: { inst: InstanceRow; onNavigate?: () => void }) {
```

  Its body is the `NavLink` the desktop list renders on the merge base (`to={`/instances/${inst.name}`}`, `className={({ isActive }) => linkClass(isActive)}`, and whatever chip and name markup PR 3 left there), plus `onClick={onNavigate}`.
- The fifth link is a `button`, not a `NavLink`: it opens a dialog, it does not navigate. Add it as the last `li` of the sections `ul`, after the `SECTIONS.map(...)`, verbatim:

```tsx
<li className="min-[820px]:hidden">
  <button
    type="button"
    onClick={() => setSheetOpen(true)}
    aria-haspopup="dialog"
    aria-expanded={sheetOpen}
    className={linkClass(false)}
  >
    <span className="flex-1">Instances</span>
  </button>
</li>
```

- Return a fragment so the sheet is a sibling of the `nav` rather than a child of it:

```tsx
<Drawer open={sheetOpen} onClose={() => setSheetOpen(false)} title="Instances">
  {(instances ?? []).length === 0 ? (
    <p className="px-3 py-2 text-[13px] text-muted">No instances yet.</p>
  ) : (
    <ul className="space-y-0.5 p-2">
      {(instances ?? []).map((inst) => (
        <li key={inst.name}>
          <InstanceLink inst={inst} onNavigate={() => setSheetOpen(false)} />
        </li>
      ))}
    </ul>
  )}
</Drawer>
```

- Choosing an instance closes the sheet. Without `onNavigate` the route changes behind an open modal and the focus trap holds focus on a panel the reader has already left.
- Update the file header comment. Its second paragraph says the instance list hides under 820 px and that "on a phone the fleet grid is the navigation"; that sentence is now false. Replace it with one saying the list hides and a fifth link opens the same list as a sheet, so Stats and Settings still have a path to an instance on a phone. Keep the existing NavLink sentence.
- Test queries have to be scoped. The desktop list is in the DOM at every width (it is hidden by CSS, which jsdom does not apply), so with the sheet open there are two links named `Pie64`. Use `within(await screen.findByRole("dialog", { name: "Instances" }))` for every assertion about the sheet. The button itself is unique: `screen.getByRole("button", { name: "Instances" })`.
- The existing Rail cases query instance links unscoped and keep passing, because the sheet is closed by default and `Drawer` returns `null` when closed. Do not rewrite them.

- [ ] **Step 1: Write the failing tests.** Three cases in `Rail.test.tsx`:
  1. `it("offers an instances link that is hidden on wide screens", ...)`: after `stubInstances()` and `renderWithProviders(<Rail />)`, assert `screen.getByRole("button", { name: "Instances" })` exists, that `button.closest("li")` has a `className` containing `min-[820px]:hidden`, and that the button has `aria-expanded` of `"false"`.
  2. `it("opens the instance list in a sheet", ...)`: click that button, `const sheet = await screen.findByRole("dialog", { name: "Instances" })`, then `expect(within(sheet).getByRole("link", { name: /Pie64_1/ })).toBeInTheDocument()`.
  3. `it("closes the sheet when an instance is chosen", ...)`: open it, click the link inside the sheet, then `await waitFor(() => expect(screen.queryByRole("dialog", { name: "Instances" })).toBeNull())`.
- [ ] **Step 2: Run them and confirm they fail.** `pnpm --dir brawlfarm/web test`. Expected: three failures naming the missing button and dialog.
- [ ] **Step 3: Edit `Rail.tsx`.** Add the `useState` and `Drawer` imports, the `InstanceRow` type and the `InstanceLink` component; point the desktop list at `InstanceLink`; add the fifth `li`; wrap the return in a fragment and add the `Drawer`.
- [ ] **Step 4: Rewrite the header comment paragraph.**
- [ ] **Step 5: Run the gate.**

**Acceptance:** the three new tests pass and every existing Rail case still passes untouched; the sheet lists every instance with the same chip and name markup as the desktop list; Escape and Close both dismiss it; choosing an instance navigates and closes it; at 1440 nothing changes, because the button is `min-[820px]:hidden`; `Drawer.tsx` is not in the diff; `820` appears only inside the existing `min-[820px]:` prefixes.

**Commit:** `feat(shell): an instances sheet on narrow screens`

---

### Task 2: A fade cue on the scrolling settings nav

**Files:**
- Modify: `brawlfarm/web/src/settings/SettingsNav.tsx` (the file header comment; the `ul` inside `SettingsNav()`)
- Create: `brawlfarm/web/src/settings/SettingsNav.test.tsx` (there is no test file for this component today)

**Interfaces:**
- Consumes: nothing new, no new import.
- Produces: no export change. `SETTINGS_SECTIONS`, `SectionId` and `SettingsSection` keep their current shapes and `Settings.tsx` is not touched.

Notes for the implementer:
- The cue is a static gradient, not a scroll listener. Seven sections never fit 400 px, so the right edge always has more to show; a listener would buy a few pixels of correctness at the far end in exchange for a ref, a scroll handler and a resize observer, which this nit does not justify.
- Wrap the existing `ul` in a positioned container and add the mask after it, verbatim:

```tsx
<div className="relative min-w-0">
  <ul className="flex gap-1 overflow-x-auto min-[820px]:block min-[820px]:space-y-0.5">
    ...
  </ul>
  <div
    aria-hidden="true"
    data-edge-fade=""
    className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-[linear-gradient(to_right,transparent,var(--ground))] min-[820px]:hidden"
  />
</div>
```

- `var(--ground)` is the page background and `styles/theme.css` redefines it for the light theme at `--ground: #F3F4F6`, so the one class covers both themes. Do not hard-code a hex value.
- `data-edge-fade` follows the `data-tone` convention already used in `Rail.tsx`: a decorative element with no role is unreachable by any accessible query, so it needs an attribute a test can find.
- The `ul` keeps its class string exactly as it is today. The only change to it is that it now sits inside the wrapper. The `nav` keeps `aria-label="Settings sections"` and `shrink-0 min-[820px]:w-[200px]`.
- Update the header comment's last paragraph, which says the column becomes a horizontal row that scrolls. Add that the scrolling edge carries a fade, so the sections past it, About last, read as cut off rather than absent.

- [ ] **Step 1: Write the failing tests.** New `SettingsNav.test.tsx` with `describe("SettingsNav", ...)` and two cases, using `renderWithProviders` from `../test/renderWithProviders`:
  1. `it("links every settings section", ...)`: assert `screen.getAllByRole("link")` has length 7 and that `screen.getByRole("link", { name: "About" })` has an `href` ending `/settings/about`.
  2. `it("marks the scrolling edge with a fade the reader sees and a screen reader ignores", ...)`: `const { container } = renderWithProviders(<SettingsNav />)`, `const fade = container.querySelector("[data-edge-fade]")`, assert it is not null, that it has `aria-hidden` of `"true"`, and that its `className` contains `pointer-events-none` and `min-[820px]:hidden`.
- [ ] **Step 2: Run them and confirm the second fails.** `pnpm --dir brawlfarm/web test`. Expected: one failure saying the element is null.
- [ ] **Step 3: Edit `SettingsNav.tsx`.** Add the wrapper `div` and the mask.
- [ ] **Step 4: Rewrite the header comment paragraph.**
- [ ] **Step 5: Run the gate.**

**Acceptance:** both new tests pass; at 1440 the settings nav is unchanged, because the mask is `min-[820px]:hidden` and the `ul` class string is the same; the mask never eats a click; the fade colour follows the theme; no `select` anywhere; `Settings.tsx` is not in the diff.

**Commit:** `fix(settings): a fade cue on the scrolling section nav`

---

### Task 3: Retake the four README screenshots

**Files:**
- Replace: `docs/img/fleet.png`, `docs/img/instance.png`, `docs/img/settings.png`, `docs/img/calibration.png`
- Modify: `README.md`, only the captions that no longer describe their capture

**The README does embed screenshots**, four of them, under `## Screenshots`: the `![...](docs/img/fleet.png)` line and the three that follow, each with a one-line caption beneath it. They were taken for v1.0.0 and predate PRs 3 to 7, so all four are stale.

Notes for the implementer:
- This task runs after PRs 3 to 7 are merged and after Tasks 1 and 2, against a build of this branch. A capture of an unmerged tree would ship a panel that does not exist.
- Capture with `playwright-cli`, viewport 1440 x 900, one file per page, the same four file names at the same four paths. Do not rename a file and do not add a fifth.
- Use the default dark theme, which is what the existing four use and what the dark-first palette is. If the owner asks for light instead, the only change is toggling the theme in Settings, About before capturing. Do not decide that here.
- Run the panel against a scratch data directory with the fixture instances only, matching the README's own sentence ("running against a scratch data directory with three example instances: one offline, two stopped"). If the fixture set has changed, update that sentence to match the new captures.
- **Nothing identifying may appear in any capture:** no account name, no email address, no player tag, no club name, no real instance nickname, no Windows user path in a visible field, no API token. Check the Settings, Connection section and the instance page header before saving each file. `tools/scrub_check.py` does not read PNGs, so this check is the implementer's eyes and it is the one step in this plan with no automated backstop.
- What each capture must show:
  1. `fleet.png`: the Fleet page with the three fixture instances and the alert strip in whatever state the fixtures produce.
  2. `instance.png`: one instance page with the live screen, the farm plan, the schedule and the session totals.
  3. `settings.png`: Settings, Instances, so the section nav is visible in its wide form.
  4. `calibration.png`: the Calibration page with the anchor scores and the threshold overrides.
- Read each caption against its new capture and fix any that has gone wrong. The caption under `calibration.png` currently says "what the workers see"; the vocabulary rule retires worker from what a reader sees, so reword it, for example to "what the panel sees". The guard in `src/lib/words.guard.test.ts` only reads `web/src`, so this one is on the implementer, not on the suite.

- [ ] **Step 1: Build and serve the panel from this branch** with a scratch data home, following `docs/setup.md`.
- [ ] **Step 2: Capture the four pages** at 1440 x 900 and write them over the existing files in `docs/img/`.
- [ ] **Step 3: Open each PNG** and confirm no account identifier, no player tag and no real path is legible.
- [ ] **Step 4: Read the four captions** and reword any that no longer matches, including the worker wording.
- [ ] **Step 5: Run the gate.**

**Acceptance:** the four files at the four existing paths are new; each is 1440 x 900; nothing identifying is legible in any of them; each caption describes what its capture shows; no new image file, no renamed file.

**Commit:** `docs(readme): retake the four panel screenshots for 1.1.0`

---

### Task 4: Version 1.1.0

**Files:**
- Modify: `pyproject.toml` (line 3, `version = "1.0.0"`, directly under `name = "brawlfarm"`)
- Modify: `brawlfarm/__init__.py` (line 3, `__version__ = "1.0.0"`)
- Modify: `brawlfarm/web/package.json` (line 3, `"version": "1.0.0",`, directly under `"name": "brawlfarm-web",`)
- Modify: `README.md` (line 5, the sentence starting `Status: v1.0.0.`)

**Interfaces:**
- Consumes: nothing.
- Produces: the three version strings that step 1 of `docs/release.md` says have to agree.

**Every place `1.0.0` appears outside `.venv/` and `node_modules/`, and what happens to each:**

| Path | Line | Change? |
|---|---|---|
| `pyproject.toml` | 3 | **Yes.** `version = "1.1.0"`. This is the one `release.yml` compares against the tag. |
| `brawlfarm/__init__.py` | 3 | **Yes.** `__version__ = "1.1.0"`. The About page and `brawlfarm --version` both read this one. |
| `brawlfarm/web/package.json` | 3 | **Yes.** `"version": "1.1.0",` |
| `README.md` | 5 | **Yes.** The status sentence. |
| `brawlfarm/web/pnpm-lock.yaml` | 365, 830, 833, 1319, 1531, 1763, 1939 | **No.** Every hit is a dependency version (`@rolldown/pluginutils@1.0.0-rc.3`, `gensync@1.0.0-beta.2`, a node engines range). The lock file does not record the root package's own version, so it does not change and `pnpm install --frozen-lockfile` in CI stays green. Do not run `pnpm install` for this task. |
| `brawlfarm/web/src/settings/About.test.tsx` | 20, 94 | **No.** That `"1.0.0"` is a stubbed `/api/health` response and the string asserted from it. It is a fixture, not a pin; leaving it proves the About page renders whatever the API reports. |
| `brawlfarm/web/src/settings/Data.test.tsx` | 37 | **No.** The same stubbed health response. |
| `tests/test_api_app.py` | 30 | **No.** It asserts `body["version"].startswith("1.")`, which 1.1.0 satisfies. |
| `docs/PLAN.md`, `docs/superpowers/plans/2026-09-12-phase-8-design-brief.md` | various | **No.** History. Do not rewrite past records. |

Notes for the implementer:
- `README.md` line 5 currently reads: `Status: v1.0.0. Phases 1 to 7 of the plan are done; phase 8 (a calibration page, recalibration for the current game version, a desktop window and tray icon, a labeled frame recorder) follows. See ` plus a link to `docs/PLAN.md`. That is stale twice over: phase 8 shipped, and phases 9, 10 and the panel critique work followed it. Replace it with a sentence that says `Status: v1.1.0.`, that every phase in the plan has shipped, that this release is the panel pass over copy, the component kit, fleet, instance, stats, settings, calibration and narrow screens, and that `docs/PLAN.md` holds the history. Sentence case, no em-dash.
- Do not add a CHANGELOG and do not edit `docs/release.md`; its example command already says `v1.1.0`.
- Do not create the tag or the GitHub release in this task. That is the owner's step after the pull request merges.

**What `.github/workflows/release.yml` checks, which this bump has to satisfy:**

1. It runs only `on: release: types: [published]`, so nothing fires until the owner publishes a GitHub release.
2. The `build` job on `windows-latest` runs `pnpm install --frozen-lockfile` then `pnpm build` in `brawlfarm/web`, then `uv build --wheel`. A lock file that disagrees with `package.json` fails here, which is why the lock file is not edited.
3. Step "the wheel version matches the tag" loads `['project']['version']` from `pyproject.toml` with `tomllib` and asserts it equals `github.event.release.tag_name` with a leading `v` removed. So `pyproject.toml` must say exactly `1.1.0` and the tag must be exactly `v1.1.0`.
4. Step "the wheel carries the built panel" asserts `brawlfarm/web/dist/index.html` is a member of the wheel and that no member starts with `brawlfarm/web/src/`.
5. The `publish` job runs in the `pypi` GitHub environment with `id-token: write` and uploads through `pypa/gh-action-pypi-publish` using trusted publishing.

`release.yml` never reads `brawlfarm/__init__.py` or `package.json`, so those two can drift from `pyproject.toml` without CI noticing. That is exactly why `docs/release.md` names all three and why this task changes all three in one commit.

- [ ] **Step 1: Edit the three version lines** in `pyproject.toml`, `brawlfarm/__init__.py` and `brawlfarm/web/package.json`.
- [ ] **Step 2: Rewrite the README status sentence.**
- [ ] **Step 3: Confirm nothing else moved.** `git diff --stat` names exactly four files, and `grep -n "1\.0\.0" pyproject.toml brawlfarm/__init__.py brawlfarm/web/package.json` returns nothing.
- [ ] **Step 4: Run the gate,** then `uv run brawlfarm --version` and confirm it prints `1.1.0`.
- [ ] **Step 5: Run the workflow's own assertion by hand:** `uv run python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"` prints `1.1.0`.

**Acceptance:** the three version strings agree at 1.1.0; the README status line is current; `pnpm --dir brawlfarm/web test` is green with the About and Data fixtures untouched; `tests/test_api_app.py` is green; `pnpm-lock.yaml` is not in the diff; no CHANGELOG file exists.

**Commit:** `chore(release): version 1.1.0`

---

## Verification, not tasks

Captures for the pull request body, taken by hand after Task 2:

1. **400 px wide, Stats page:** the rail row shows five links and the fifth is Instances.
2. **400 px wide, the sheet open:** the instances sheet over the Stats page, every fixture instance listed with its state chip.
3. **400 px wide, Settings:** the section row with the fade over its right edge, About off-screen but visibly cut off.
4. **1440 px wide, Settings, as the control:** identical to the PR 6 capture, proving neither change reached the wide layout.

Keyboard walk at 400 px: Tab to the Instances button, Enter opens the sheet, Tab cycles inside it, Escape closes it and focus returns to the button.

## After the merge, owner steps

Not tasks, and not done by an agent:

1. Assemble the release notes from the eight panel pull request bodies, grouped by page: copy and glossary, component kit, fleet and shell, instance, stats, settings and setup, calibration, narrow screens and release.
2. `gh release create v1.1.0 --generate-notes`, then paste the assembled notes over the generated list.
3. `gh run watch`, and confirm the build job's two assertions pass and the publish job uploads.
4. The pending publisher on PyPI and the `pypi` GitHub environment described in `docs/release.md` are still open one-time steps. If they are not done the publish job fails with an OIDC error, and PyPI never allows reuploading a version, so a failed publish costs a patch bump.
