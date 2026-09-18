# Panel PR 5: Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Stats page answers its own questions at rest: the chart says what it plots, with round y ticks and dated x ticks; the Table view is one row per day instead of one per game; rank distribution stops drawing six empty rows; the instance filter tells the truth about whether it can filter; and the range plus the chart-or-table choice survive a reload and a shared link.

**Architecture:** No new screen. `stats/TrophyChart.tsx` splits its two views: the chart frame gains a caption, a tick scale and gridlines; the Table view becomes a day rollup computed in a new pure module `stats/days.ts`, so the rollup is testable without rendering. The chart-or-table choice leaves component state and joins `range` and `instances` in the URL, owned by `stats/Stats.tsx` and passed down. `stats/RankBars.tsx` changes its row set and its bar basis. `stats/StatsToolbar.tsx` gains a one-instance form. `components/ui/Table.tsx` gains two additive, opt-in props (`minWidth`, `headers`) so recent games can scroll and the day table can read in sentence case without touching the six other tables.

**Tech Stack:** React 19 and TypeScript under `pnpm`, vitest plus Testing Library, Python 3.13 under `uv` for the gate only.

**Spec:** the panel critique, items `stats-chart`, `stats-table-view`, `stats-rank-bars`, `stats-chip-noop`, `stats-url`, `stats-brawlers-empty-space`, `stats-table-phone`, `stats-metrics-case`. Layout target: `build_critique.py`, `W_stats()`, the desktop wireframe.

**Branch:** `panel/stats`, cut from the merge of PR 2. Worktree `.claude/worktrees/phase-10`.

## Global Constraints

- No em-dashes and no emoji anywhere: prose, code, comments, tests, commit messages, pull request body.
- Never write the word bsutil or any legacy tag anywhere.
- Nothing under `brawlfarm/core` changes.
- No API change. If a task turns out to need one it stops and reports; any accepted API change must be named by the task, must name the endpoint, and must be additive.
- Per `CLAUDE.md`, code review is on: every task gets a spec-compliance and code-quality review pass on **sonnet** before it counts as complete, and the branch gets a whole-branch review on **sonnet** before its pull request opens. Findings are fixed by an implementer, then re-reviewed once.
- Conventional commit subjects with a scope (`feat(scope):`, `fix(scope):`, `refactor(scope):`, `test(scope):`). Every commit message ends with the trailers:

```
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01E1U94d3i2jWe3tvmSRjcki
```

## The gate command block

Every task ends by running this, in this order, from the worktree root:

```
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
uv run pytest -q -p no:cacheprovider
uv run ruff check .
uv run ruff format --check .
uv run python tools/scrub_check.py
```

`tools/scrub_check.py` must print `0 hit(s)`. No live pass is required: nothing here touches the farm loop.

## Owner rulings that bind this pull request

- Only the owner uses the panel at this PC. Recent games gets a scrolling container now (overflow-x auto, no clipped cells, a visible right-edge cue). Two-line phone rows below 640 px are **deferred** and must be named in the pull request body as the remaining half of `stats-table-phone`.
- The chart gets a visible caption that follows the range, y ticks at round values, x ticks with dates, gridlines and a unit. The sr-only accessible name stays exactly as it is.
- Rank distribution shows ranks 1, 2, 3 and 4 each on their own row and one final row `5 to 10`. Bars are a percent of total and sit on a base line. The count and the percentage are one column.
- The Brawlers panel sizes to its rows.
- The instance chip row renders as a static label when there is one instance and as a real filter when there are several, with a disabled state carrying a reason.
- `range` and the chart-or-table choice both live in the URL query.
- Export CSV is a secondary button.
- The Table view is one row per day: date, games, net trophies, cumulative. Capped at 14 rows with a Show all control. Headers in sentence case. The instance name is a column value, never a column header.
- Mono with tabular numerals for figures (`t-figure`), Archivo for names (`t-name`).

## Blocking dependencies, and what this plan must not redo

This pull request lands after PR 1 and PR 2. Read both before Task 1 and do not repeat their work.

- **PR 1 already shipped:** `src/lib/copy.ts` with `count(n)`, `modeName(raw)` and `NOT_RECORDED`; `stats/RecentGames.tsx` renders mode names and a zero trophy change as `0`; `stats/MetricsRow.tsx` labels are already sentence case. Task 6 must not re-case those labels. If a label is still lowercase on the merge base, PR 1 regressed: stop and report rather than fixing it here.
- **PR 2 already shipped:** `Button` with `variant="primary" | "secondary" | "quiet" | "danger"` (default `secondary`); a focus ring on sortable `Table` headers; `src/lib/format.ts` with module-scope Intl helpers (`num`, `signed`, `clock`, `dateTime`); the `t-figure` and `t-name` utilities in `styles/theme.css`.
- **Read `src/lib/format.ts` and `src/lib/copy.ts` on the merge base first.** Use `num` for every raw number this plan renders, and `count` where PR 1 already established it in that file. Do not add a third number formatter, and never construct an Intl formatter inside a render or a map callback: these run per chart tick, per table cell and per crosshair move.
- `src/lib/time.ts` already exports `hoursText(h)`, which is `duration(Math.round(h * 60))`. Task 6 uses it rather than inventing an hours-and-minutes format.

## File Structure

- `brawlfarm/web/src/stats/TrophyChart.tsx` (353 lines): caption, ticks, gridlines, end label, the lifted view prop, the day table. Tasks 1, 2, 3.
- `brawlfarm/web/src/stats/days.ts` and `days.test.ts`: new. The pure day rollup. Task 3.
- `brawlfarm/web/src/stats/Stats.tsx` (169 lines): the view query param, the stale-name toast, the grid alignment. Tasks 2, 5.
- `brawlfarm/web/src/stats/RankBars.tsx` (57 lines): five rows, percent-of-total bars, one count column. Task 4.
- `brawlfarm/web/src/stats/StatsToolbar.tsx` (88 lines): the one-instance label, the disabled chip, the export button. Task 5.
- `brawlfarm/web/src/stats/RecentGames.tsx` (102 lines) and `components/ui/Table.tsx` (130 lines): the scroll container. Tasks 3, 6.
- `brawlfarm/web/src/stats/MetricsRow.tsx` (74 lines): hours and minutes, the non-breaking space, `t-figure`. Task 6.
- Tests touched: `stats/TrophyChart.test.tsx` (212 lines), `stats/Stats.test.tsx` (221), `stats/RankBars.test.tsx` (63), `stats/StatsToolbar.test.tsx` (87), `stats/RecentGames.test.tsx` (98), `stats/MetricsRow.test.tsx` (113), `components/ui/Table.test.tsx`.

**The 17 existing cases in `stats/TrophyChart.test.tsx` stay green.** The keyboard crosshair cases (`moves the crosshair with Left and Right and clears it with Escape`, `jumps to the ends with Home and End`, `draws the crosshair rule only while there is a crosshair`, `announces the same readout in a polite live region`, `reads none for a series with no point yet at that moment`) are the best-executed code in the audited scope. Do not touch `onKeyDown`, `onMouseMove`, `msOf`, `valueAt`, `xFor`, the `aria-live` readout or `vectorEffect="non-scaling-stroke"`. Exactly three cases change, by design: `drops a y-axis label that would overprint the zero one` (Task 1), `swaps to a table of the same points and back, with the toggle reading Table both ways` and `says whether the table view is the one showing` (Task 2).

The non-breaking space is U+00A0. Write it as `\u{00A0}` in a template literal, never as a bare space that looks the same in a diff.

---

### Task 1: The chart says what it plots

**Files**
- Modify: `brawlfarm/web/src/stats/TrophyChart.tsx`: the tick builder at lines 120-126, the end-label placer at 137-149, the axis column at 260-274, the `svg` at 265-280.
- Test: `brawlfarm/web/src/stats/TrophyChart.test.tsx`.

**Closes:** `stats-chart`.

**Component API after the change:** `TrophyChartProps` is unchanged in this task (`series`, `instances`, `range`). Two new module-scope exports: `CHART_UNIT = "trophies"` and `captionFor(range: StatsRange): string`.

**Exact strings.** `captionFor` returns, per range: `today` gives `"Trophies, cumulative, today"`; `7d` gives `"Trophies, cumulative, last 7 days"`; `30d` gives `"Trophies, cumulative, last 30 days"`; `all` gives `"Trophies, cumulative, all time"`. The caption renders as the panel heading, `<h2 className="text-[13px] font-semibold">`, in the panel header row left of the legend, as in `W_stats()`. `CHART_LABEL` stays `"Cumulative trophy change"` on the `svg` `aria-label`, unchanged, so screen readers keep the name they have and sighted users gain the caption. The y axis column gets one unit label under the lowest tick: `<span className="text-[11px] text-muted">trophies</span>`.

**Ticks, before and after.** Before: `ticks` is `[{ value: 0 }]` plus `rawHi` and `rawLo` when they clear the label height, so a real chart shows two numbers. After: a module-scope `niceTicks(lo: number, hi: number): number[]`, exported for test, picks a step from `[1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000]` such that the count of multiples of that step inside `[rawLo, rawHi]` is 3, 4 or 5, prefers the smallest such step, always includes 0, and returns descending. For the wireframe data that yields `0 25 50 75`. Each tick renders through `num()` and carries `t-figure`. Each tick also draws a gridline inside the `svg`: `<line data-gridline="" x1={0} x2={PLOT_W} stroke="var(--line)" strokeWidth={1} vectorEffect="non-scaling-stroke" className="opacity-40" />` at `yFor(tick)`. The existing zero line stays and is drawn after the gridlines so it wins at full opacity.

**X ticks, before and after.** Before: no x axis in the chart view; only the first and last moments are visible, through the legend and the end labels. After: a row under the plot, `data-testid="chart-x-axis"`, of up to five dated labels: the first moment, the last, and evenly spaced moments between, each formatted with `formatMoment(iso, range)` from `stats/format.ts` and positioned with `left: ${(xFor(ms) / PLOT_W) * 100}%`. Deduplicate identical adjacent labels rather than printing `Sep 12` twice. Labels carry `t-figure`.

**End label, before and after.** Before: `endLabels` is built for every drawn series, so a single-instance chart names the instance twice (legend and end label). After: `const endLabels = drawn.length > 1 ? placed : []`. The legend keeps every selected instance, points or not.

**Steps**
- [ ] **Step 1: Write the failing tests** in `stats/TrophyChart.test.tsx`: `niceTicks(-3, 78)` returns `[75, 50, 25, 0]` and always contains 0; the panel heading reads `Trophies, cumulative, last 7 days` for `range="7d"` and `Trophies, cumulative, today` for `range="today"`; the axis prints the word `trophies` once; `chart-x-axis` holds at least two labels and the first contains a month name; there is one `[data-gridline]` per tick; a one-series chart has no end label while a two-series chart has two.
- [ ] **Step 2: Rewrite the existing tick case.** `drops a y-axis label that would overprint the zero one` describes the old three-tick rule. Replace it with `never draws two ticks closer than the label height`, asserting on `niceTicks` output spacing through `yFor`. Say in the commit body that the case was rewritten, not dropped.
- [ ] **Step 3: Implement** `niceTicks`, `captionFor`, `CHART_UNIT`, the gridlines, the x axis row and the end-label guard.
- [ ] **Step 4: Run the 17 existing cases** and confirm every keyboard and crosshair case is green with no edit to its body.
- [ ] **Step 5: Run the gate.**

**Acceptance:** at `range="7d"` on the fixture the chart shows a visible caption, four round y ticks with gridlines, the word `trophies` on the axis, dated x ticks, one legend entry per selected instance, and no end label when one instance is selected; `aria-label` is still `Cumulative trophy change`; no test body under `onKeyDown` changed.

**Commit:** `feat(stats): a captioned chart with round ticks, gridlines and dated x labels`

---

### Task 2: The chart-or-table choice lives in the URL

**Files**
- Modify: `brawlfarm/web/src/stats/Stats.tsx`: `parseRange` at 38-40, `write` at 83-92, the `TrophyChart` call at 156.
- Modify: `brawlfarm/web/src/stats/TrophyChart.tsx`: the `showTable` state at line 83 and the toggle button in the panel header.
- Test: `brawlfarm/web/src/stats/Stats.test.tsx`, `brawlfarm/web/src/stats/TrophyChart.test.tsx`.

**Closes:** the URL half of `stats-table-view`, and the Chart or Table segmented control in `W_stats()`.

**Component API after the change:**
- `TrophyChart.tsx` declares and exports `type StatsView = "chart" | "table"`, so the chart owns its own vocabulary; `Stats.tsx` imports it.
- `Stats.tsx` exports `VIEWS: readonly StatsView[] = ["chart", "table"]` and `parseView(raw: string | null): StatsView`, defaulting to `"chart"`.
- `write` grows one field: `(next: { range?: StatsRange; instances?: string[]; view?: StatsView })`. `view` is written only as `?view=table`; `chart` is the default and is omitted, exactly as `7d` and a full selection are omitted today. Keep `{ replace: true }`.
- `TrophyChartProps` gains `view: StatsView` and `onView: (next: StatsView) => void`. Delete the `showTable` `useState`. The component becomes controlled for this one concern and keeps its own `hover` and `cursor` state.

**Before and after.** Before: a button reading `Table` toggles local state, so a reload loses the view and a link cannot carry it. After: `<Segmented label="View" value={view} options={[{ value: "chart", label: "Chart" }, { value: "table", label: "Table" }]} onChange={onView} />` in the panel header row, right-aligned after the caption and the legend. `Segmented` already gives radio-group semantics plus arrow, Home and End keys; do not hand-roll a toggle.

**Steps**
- [ ] **Step 1: Write the failing tests.** In `Stats.test.tsx`: `?view=table` renders the day table and no `svg`; clicking `Chart` rewrites the URL to drop `view`; clicking `Table` sets `?view=table` and leaves `range` and `instances` alone; `?view=pie` falls back to the chart. In `TrophyChart.test.tsx`: rewrite the two toggle cases as `calls onView with the other view when the segmented control is used` and `renders the table when view is table`, driving the component through the prop.
- [ ] **Step 2: Implement** `parseView`, the `write` field, the two props and the `Segmented` control. Remove `showTable`.
- [ ] **Step 3: Run the gate.**

**Acceptance:** `/stats?range=30d&view=table` reloads into the day table on the 30-day range; Back still leaves Stats rather than walking the views; no `push` is introduced; the chart view URL carries no `view` param.

**Commit:** `feat(stats): keep the chart or table choice in the URL`

---

### Task 3: The Table view is one row per day

**Files**
- Create: `brawlfarm/web/src/stats/days.ts`, `brawlfarm/web/src/stats/days.test.ts`.
- Modify: `brawlfarm/web/src/stats/TrophyChart.tsx`: `columns` at 189-204, `rows` at 205-208, the `Table` call at 240.
- Modify: `brawlfarm/web/src/components/ui/Table.tsx`: the `<table>` element at line 59, the `<th>` className at line 74.
- Test: `brawlfarm/web/src/stats/TrophyChart.test.tsx`, `brawlfarm/web/src/components/ui/Table.test.tsx`.

**Closes:** the rest of `stats-table-view`.

**Component API after the change:**
- `days.ts` exports `interface DayRow { date: string; games: number; net: number; cum: number }` and `rollUpDays(series: StatsSeries[]): DayRow[]`. `date` is the local calendar day as `YYYY-MM-DD`, ascending. `games` is the count of points on that day across every series. `net` is the day last `cum` minus the previous day last `cum`, summed across series. `cum` is the summed last `cum` of every series on or before that day. A series with no point on a day carries its last known `cum` forward rather than counting as zero. Pure: no React, no Intl, no date mutation.
- `Table` gains two optional props, both additive and both defaulting to current behaviour: `minWidth?: string`, applied as `style={{ minWidth }}` on the `<table>`; and `headers?: "caps" | "sentence"`, default `"caps"`, where `"sentence"` drops `uppercase tracking-wide` from the `<th>` className and changes nothing else. No other call site passes either prop, so the six other tables stay byte-identical.

**Before and after.** Before: `columns` is `Time` plus one column per instance labelled with the instance name, which the shared header style prints as `PIE64`; `rows` is one row per moment, so a 30-day range prints hundreds of rows of a running total with no delta and no games count. After: four columns, `headers="sentence"`, and no instance column at all (the selection is already named by the toolbar and the legend):

| key | label | width | render |
| --- | --- | --- | --- |
| `date` | `Date` | `120px` | the day through a module-scope `Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" })`, `t-figure` |
| `games` | `Games` | `80px` | `num(row.games)`, `t-figure` |
| `net` | `Net trophies` | `120px` | `signed(row.net)`, toned `text-accent` above zero, `text-bad` below, `text-muted` at zero, `t-figure` |
| `cum` | `Cumulative` | `120px` | `num(row.cum)`, `t-figure` |

The cap: render `rows.slice(0, DAY_CAP)` with `const DAY_CAP = 14`. When `rows.length > DAY_CAP`, a control under the table reads `Show all 30 days` with the real count through `num()`, rendered as `<Button variant="quiet" size="sm">`, expanding in place through a local `useState` boolean. Expanded, it reads `Show 14 days` and collapses. This is view-only local state and deliberately does **not** go in the URL: the owner ruling names `range` and the chart-or-table choice, not the expansion. The empty state stays `EMPTY` (`"No games in this range."`).

**Steps**
- [ ] **Step 1: Write the failing tests** in `days.test.ts` first, on a fixture of two series crossing a local midnight: three days come back ascending; `net` for day two is day two last `cum` minus day one last `cum`; `cum` on the last day is the sum of both series final `cum`; a series with no point on day two carries its day-one `cum` forward; an empty `series` returns `[]`; a single point returns one row whose `net` equals its `cum`.
- [ ] **Step 2: Write the failing tests** in `TrophyChart.test.tsx`: the table has exactly the headers `Date`, `Games`, `Net trophies`, `Cumulative`, and none of them is an instance name; with 30 days of points only 14 rows render and a control named `Show all 30 days` appears; clicking it renders 30 rows and the control reads `Show 14 days`; with 13 days no such control renders. In `Table.test.tsx`: `headers="sentence"` renders a `columnheader` whose className has no `uppercase` while the default still does; `minWidth="720px"` lands on the `table` element.
- [ ] **Step 3: Implement** `days.ts`, then the `Table` props, then the columns and the cap. In that order: `days.ts` holds the only real logic and is testable with no DOM.
- [ ] **Step 4: Run the gate,** then `grep -rn "headers=\|minWidth=" src --include=*.tsx` and confirm the only call sites are the ones this plan names.

**Acceptance:** `?view=table` on a 30-day range shows 14 day rows and a `Show all 30 days` control; no header is an instance name; these headers read in sentence case while every other table in the app still reads in caps; `days.ts` imports no React.

**Commit:** `feat(stats): a day-by-day table view capped at 14 rows`

---

### Task 4: Rank distribution stops drawing six empty rows

**Files**
- Modify: `brawlfarm/web/src/stats/RankBars.tsx`: `RANKS` at line 15, the body at 17-56.
- Test: `brawlfarm/web/src/stats/RankBars.test.tsx`.

**Closes:** `stats-rank-bars`.

**Component API after the change:** `RankBarsProps` is unchanged (`rows: StatsRank[]`). One new module-scope export for test: `rankRows(rows: StatsRank[]): { label: string; games: number; percent: number }[]`.

**Before and after.** Before: ten rows, one per rank 1 to 10; bar width is `games / largest` while the printed text is `games / total`, so a bar half as long as another can read a very different percent; six empty bars at the bottom on every real dataset. After: exactly five rows. Ranks 1, 2, 3 and 4 keep their own rows, labelled `1`, `2`, `3`, `4`. Ranks 5 through 10 are summed into one final row labelled `5 to 10`. Bar width becomes `total === 0 ? 0 : Math.round((games / total) * 100)`, the same basis as the printed percent, so bar and text can no longer disagree. Every row keeps its full-width track (`bg-panel-2`), which is the base line the owner asked for, drawn even at zero games. Count and percent stay one column and one string: `${num(games)} (${percent}%)`, with `t-figure`. A zero row keeps `text-muted` on its label and its count, matching the `muted` class on the wireframe `5 to 10` row. Keep the test ids `rank-row`, `rank-label`, `rank-bar`, `rank-count`.

**Steps**
- [ ] **Step 1: Write the failing tests.** Rewrite `draws ten rows from 1 to 10, including the empty ones` as `draws five rows, ranks 1 to 4 and one for 5 to 10`; rewrite `scales every bar to the largest count` as `scales every bar to the total, so the bar and the percent share a basis`, asserting the widest bar width equals its printed percent; rewrite `draws ten empty rows when nothing was ranked` as `draws five empty rows when nothing was ranked`. Add: ranks 5 to 10 with counts 1, 0, 2, 0, 0, 1 render one row reading `4`; the `5 to 10` row at zero games is muted. Leave `is headed Rank distribution` and `labels each bar with its count and its whole-percent share` untouched.
- [ ] **Step 2: Implement** `rankRows` and the render.
- [ ] **Step 3: Run the gate.**

**Acceptance:** five rows on every dataset; every bar width equals its printed percent; the panel is short enough that it no longer sets the height of the Brawlers panel beside it.

**Commit:** `fix(stats): rank bars share one basis and collapse ranks 5 to 10`

---

### Task 5: The toolbar tells the truth, and the panels size to their rows

**Files**
- Modify: `brawlfarm/web/src/stats/StatsToolbar.tsx`: `toggle` at 49-54, the chip row at 60-77, the export anchor at 79-85.
- Modify: `brawlfarm/web/src/stats/Stats.tsx`: the narrowing at 61-69, the grid at line 157.
- Test: `brawlfarm/web/src/stats/StatsToolbar.test.tsx`, `brawlfarm/web/src/stats/Stats.test.tsx`.

**Closes:** `stats-chip-noop`, `stats-url`, `stats-brawlers-empty-space`.

**Component API after the change:** `StatsToolbarProps` is unchanged. The one-instance form is derived from `instances.length === 1`, not passed in.

**The chips, before and after.** Before: `if (on && selected.length === 1) return;` is a silent no-op, and a single configured instance still renders a pressable chip that does nothing. After, three cases:
1. `instances.length === 1`: a static, non-interactive `<span data-testid="instance-label" className="t-figure ...">Pie64</span>`. No `button`, no `aria-pressed`, nothing to click. A filter with one option is not a filter.
2. `instances.length > 1` and this chip is not the last one on: the pressable chip exactly as today, with `aria-pressed`.
3. `instances.length > 1` and this chip is the last one on: `disabled`, `aria-disabled="true"`, and the reason `Keep at least one` carried the way the rest of the app carries `disabledReason` (read one existing call site and match it rather than inventing a second convention). Delete the bare `return` from `toggle`: the control now carries the reason instead of swallowing the click.

**Export CSV, before and after.** Before: a muted text anchor pushed right with `ml-auto`. After: the same `<a href={csvHref} download>` in the PR 2 secondary style: `<Button as="a" ...>` if `Button` supports an `as` prop on the merge base, otherwise the anchor with the secondary variant class string plus a one-line comment saying why it is not a `Button`. It stays an anchor with `download`: the browser download is the feedback, and a fetch would need a pending state and a toast this pull request does not want. Keep it last in the row, keep `ml-auto`.

**The stale link, before and after.** Before: `narrowed` silently drops names that are not configured. After: the dropped names raise one toast, once, through `useEffect` keyed on the joined dropped list: `toast(dropped.length === 1 ? dropped[0] + " is no longer configured" : dropped.join(", ") + " are no longer configured", { tone: "info" })`. It must fire only after `instancesQuery.isSuccess`, or a pending list would report every asked name as missing. Guard with a ref so a re-render on the same dropped set does not re-toast.

**The grid, before and after.** `className="grid gap-3 min-[900px]:grid-cols-[1fr_320px]"` becomes `className="grid items-start gap-3 min-[900px]:grid-cols-[1fr_320px]"`. One word, and the Brawlers panel then sizes to its rows instead of matching the rank panel.

**Steps**
- [ ] **Step 1: Write the failing tests.** In `StatsToolbar.test.tsx`: rewrite `refuses to turn off the last enabled chip` as `disables the last enabled chip and says why`, asserting the button is disabled and carries `Keep at least one`; add `renders one instance as a label, not a chip`, asserting no button with that name exists; extend `exports the current query as a download link` to assert the secondary style. In `Stats.test.tsx`: extend `drops a name that is not configured` to assert a toast reading `Pie32 is no longer configured`; add a case that a fully configured selection raises no toast; add a case that the grid carries `items-start`.
- [ ] **Step 2: Implement** the three chip cases, the export button, the toast effect and the one grid class.
- [ ] **Step 3: Run the gate,** then confirm `resetToasts()` runs in the `Stats.test.tsx` setup so toast state does not leak between cases.

**Acceptance:** with one configured instance there is no pressable chip; with three, the last one on is visibly disabled with a reason and clicking it does not change the URL; a stale `?instances=` raises exactly one toast; Brawlers has no dead space under its single row.

**Commit:** `fix(stats): a real instance filter, a secondary export and a word for a stale link`

---

### Task 6: Recent games scrolls, and the metrics row reads in hours and minutes

**Files**
- Modify: `brawlfarm/web/src/stats/RecentGames.tsx`: the `Table` call, around lines 37-88.
- Modify: `brawlfarm/web/src/components/ui/Table.tsx`: the already-`relative` scroll wrapper at line 57.
- Modify: `brawlfarm/web/src/stats/MetricsRow.tsx`: `Figure` at 34-51, the row at 53-73, `hours_farmed` at line 71.
- Test: `brawlfarm/web/src/stats/RecentGames.test.tsx`, `brawlfarm/web/src/stats/MetricsRow.test.tsx`.

**Closes:** the accepted half of `stats-table-phone`, and the remainder of `stats-metrics-case`.

**Recent games, before and after.** Before: a seven-column table inside the `overflow-x-auto` wrapper, but `table w-full` squeezes the columns instead of overflowing, so at 400 px Map, Rank and Trophies are clipped with no scroll cue. After: pass `minWidth="720px"` (the Task 3 prop) so the table overflows and the wrapper actually scrolls, and add the edge cue the critique asks for inside the wrapper: `<span aria-hidden="true" className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-panel to-transparent" />`, rendered only when `minWidth` is set. No column is dropped, no cell is clipped, and the seven columns are otherwise untouched. **Deferred, and named in the pull request body:** the two-line card row below 640 px.

**MetricsRow, before and after.** Labels are already sentence case from PR 1; do not touch them. Three changes only:
1. Time farmed: `${summary.hours_farmed.toFixed(2)} h` becomes `hoursText(summary.hours_farmed)` from `lib/time.ts`, which gives `1 h 51 min`.
2. No value wraps between its number and its unit. `hoursText` is shared with other screens, so do not edit `lib/time.ts` to chase a non-breaking space: wrap the value span in `whitespace-nowrap` at this call site instead, and say so in the commit body. Leave the percent in `top-4 rate` alone; it has no space today (`100%`).
3. The `Figure` value span swaps its hand-rolled `font-mono ... tabular-nums` for the PR 2 `t-figure` utility, keeping the tone class and the `metric-value` test id. `games` and `trophies per hour` render through `num()`.

**Steps**
- [ ] **Step 1: Write the failing tests.** In `MetricsRow.test.tsx`: `hours_farmed: 1.85` renders `1 h 51 min`; the value span className contains `t-figure`; `games: 110738` renders `110,738`. In `RecentGames.test.tsx`: the `table` element carries a `min-width` style; the wrapper renders the edge cue; all seven headers are still present.
- [ ] **Step 2: Implement.** `Table` and `RecentGames` first (a prop and a span), then `MetricsRow`.
- [ ] **Step 3: Run the gate.**

**Acceptance:** at 400 px the recent games table scrolls to Trophies with a visible right-edge cue and no clipped cell; time farmed reads `1 h 51 min`; no metric label differs from what PR 1 shipped.

**Commit:** `fix(stats): scroll the recent games table and read time in hours and minutes`

---

## Whole-branch close-out

- [ ] Whole-branch code review on **sonnet** before the pull request opens. Findings fixed by an implementer, then re-reviewed once.
- [ ] Build the verification fixture: three instances, a 30-day range, at least 40 games, one instance with no points in the range, one day with no games at all, and one negative day. Extend the existing `Stats.test.tsx` fixture pattern; do not depend on a live run.
- [ ] Capture at **1440 px** and **400 px**, both themes: the chart view, the table view collapsed and expanded, the toolbar with three instances (last chip disabled) and with one instance (static label), and recent games scrolled to its right edge.
- [ ] Confirm by hand: `/stats?range=30d&view=table&instances=Pie64,Pie32` reloads into the same view, and a removed name in `?instances=` raises exactly one toast.
- [ ] The pull request body lists the eight critique ids this pull request closes and names the deferred items: the two-line recent games phone row below 640 px, the expandable session second level under each day row, and the missing `aria-busy` plus visible loading text on `Skeleton` (audit `Stats.tsx:42-53`, outside this item set).
