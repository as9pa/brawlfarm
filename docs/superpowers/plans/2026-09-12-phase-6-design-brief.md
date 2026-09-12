# Phase 6 design brief: Stats with brawler icons

This is the binding design for the phase 6 implementation plan. Plan writers copy its
values verbatim; they do not re-decide anything here. The spec is
`docs/superpowers/specs/2026-09-10-brawlfarm-design.md` (section 8's Stats paragraph and
its "Brawler icons" section, section 9 the safety rails, section 10 hygiene, section 11
testing). Every fact below about the API and the web code as they stand today was read
against the source before this brief was written, and the line references are to that
reading. The phase 5 brief next to this file is the template and the inheritance. The
owner reviewed the phase 6 proposal page and pressed "Looks right" on 2026-09-12, answering
two of its five questions; the three he left blank are decided here and marked as such.

## 1. Outcome

`brawlfarm` has a Stats screen. `/stats` replaces the phase 4 placeholder with a toolbar
(range tabs, instance chips, Export CSV), an inline metrics row, a hand-drawn SVG chart of
cumulative trophy change, a per-brawler table beside a rank distribution, and the last
twenty games, all driven by the `GET /api/stats` route that already exists and all of it
reflected in the URL so a reload keeps the view. Every brawler named on Stats and on the
Instance farm plan gets a 22 px icon in front of it, served by a new local route with a
disk cache. A stopped instance shows its last finished session on a cold load instead of
zeros. When the Brawl Stars API token is missing, unset or dead, one quiet strip says so in
the same words on Stats and in the Instance roster. Nothing new is collected: every number
comes from the `games.csv` and `session-*.jsonl` files the workers already write.

## 2. What phase 6 inherits unchanged (decided)

Everything the phase 4 and phase 5 briefs established carries into phase 6 without
restatement or amendment: the tokens, fonts, type scale, radii, motion and focus ring in
`brawlfarm/web/src/styles/theme.css`; the state vocabulary in `lib/states.ts`; the copy
rules; `api/client.ts` (`ApiError`, `errorFrom`, `NETWORK_DETAIL`), `api/queries.ts`
(`queryKeys`, `createQueryClient`), `lib/toast.ts` and `lib/time.ts`; the settings data
layer `settings/useSettingsPatch.ts` and its `settingsFieldErrors` mapper; every phase 4
and phase 5 component keeping its props exactly, including `Table` and `Field`; the vitest
and pytest conventions with `stubFetch`, `jsonResponse`, `renderWithProviders`,
`makeInstance`, `makePlan`, `makeSettings`, `make_client`, `build_settings` and
`FakeWorld`; the commit trailers; the scrub rules; and the safety rails of spec section 9.
Phase 6 adds to that surface and edits none of it, with the three exceptions named in
sections 5 and 7 (`Table` gains optional sort props, `app/Rail.tsx` loses one badge,
`instance/FarmPlan.tsx` and `instance/SessionPanel.tsx` gain icons and a cold-load block).
No new web dependency, no new Python dependency, no new token, no chart library.

## 3. Routes and layout (decided)

| Route | Renders |
| --- | --- |
| `/stats` | `stats/Stats.tsx` inside `Shell`, replacing the `Placeholder` at `App.tsx:87` |

`App.tsx`'s `ShellRoutes` swaps
`<Route path="/stats" element={<Placeholder title="Stats" body="Stats arrive in phase 6." />} />`
for `<Route path="/stats" element={<Stats />} />`. Nothing else in the route table moves,
and `TopBar.pageTitle` already maps `/stats` to "Stats".

**URL state.** Two query params, read and written with `useSearchParams`: `range` (one of
`today`, `7d`, `30d`, `all`) and `instances` (a comma-separated list of configured names).
An absent or unparsable `range` is `7d` (the owner's answer to q-range: Today is empty
every morning until the first match). An absent `instances` means every configured
instance. A name in `instances` that is not configured is dropped before the request goes
out, so a stale link degrades to a narrower selection instead of a 404 from `_selected`.
Changing a tab or a chip does a `replace`, not a `push`, so Back leaves Stats rather than
walking the ranges.

**Layout, top to bottom.** All of it inside one `Shell` content column.

1. Toolbar row: the range tabs at the left, the instance chips in the middle, Export CSV at
   the right. One row at >= 900 px; below that the chips wrap to their own row under the
   tabs and Export CSV stays with the tabs.
2. Metrics row: six figures on one line, the value at 18 px and its label at 11 px muted
   under it, separated by the 1 px `--line`, on `--panel`. No tiles, no big numbers.
3. Chart: full width, 180 px tall, on `--panel`, with the Table toggle at its top right.
4. Two-column band at >= 900 px: `BrawlerTable` left at `1fr`, `RankBars` right at `320px`.
   Below 900 px they stack, table first.
5. Recent games: full width, twenty rows.

At phone width everything stacks in that order and each block keeps its own
`overflow-x-auto` box, which `Table` already provides.

## 4. API additions (Python, decided)

All loopback-only behind the existing middleware. No auth, no CORS. Routes reach the
supervisor and the data directory through `brawlfarm/api/deps.py` (`get_sup`, `get_home`,
`resolve_instance`) exactly as every other router does.

### a. `GET /api/brawlers/{name}/icon.png`

New router `brawlfarm/api/brawlers.py`, registered in `app.py` after `stats`. New pure
module `brawlfarm/core/icons.py` holding the cache and the fetching, so the route is
twenty lines of HTTP and the logic is testable without a client.

```python
CDN_URL = "https://cdn.brawlify.com/brawlers/borderless/{id}.png"
MAX_AGE_S = 604800          # one week, the Cache-Control the route sends
REFRESH_S = 3600.0          # at most one catalog refresh an hour
BRAWLER_NAME_RE = re.compile(r"^[A-Za-z0-9 .'&_-]{1,32}$")

def catalog_path(home: Path) -> Path:      # <home>/cache/brawlers.json
def icon_path(home: Path, brawler_id: int) -> Path:   # <home>/cache/brawlers/<id>.png
def load_catalog(home: Path) -> dict[str, int]:
def resolve_id(home: Path, name: str, token: str, *, now: Callable[[], float] = time.monotonic,
               fetch: Callable[[str], list[dict]] = fetch_brawlers) -> int | None
def ensure_icon(home: Path, brawler_id: int,
                fetch: Callable[[str], bytes] = fetch_icon_bytes) -> bytes | None
def fetch_brawlers(token: str) -> list[dict]:   # ApiClient(token=token).get_brawlers()
```

- The catalog is `{UPPERCASED NAME: id}` written to `<home>/cache/brawlers.json` with the
  existing `jsonio` atomic write. Names are matched upper-cased and stripped, because
  `games.csv` stores the official API's names and the plan queue stores the same.
- `resolve_id` answers from the cached catalog first. Only when the name is missing does it
  refresh, and only if `REFRESH_S` has passed since the last refresh attempt (success or
  failure, held in a module-level monotonic stamp), so a run of unknown names costs one
  call an hour and not one call each. A refresh with a blank token, or one that raises, is
  a miss: `resolve_id` returns `None` and the catalog on disk is left as it was.
- `ensure_icon` returns the bytes from `<home>/cache/brawlers/<id>.png` when the file
  exists, otherwise fetches `CDN_URL` once with a 10 s timeout, writes it atomically
  (temp file in the same folder, then replace, so a torn download never becomes a cached
  icon), and returns the bytes. A non-200, a timeout, a body that does not begin with the
  PNG magic `\x89PNG\r\n\x1a\n`, or a body over 512 KiB returns `None` and writes nothing.
- The route: `name` is rejected with 404 when `BRAWLER_NAME_RE` does not match, before
  anything touches the filesystem. The path on disk is built from the integer id and never
  from `name`. `resolve_id` returning `None` is 404; `ensure_icon` returning `None` is 404.
  The 404 detail is "no icon" in every case, because telling a bad token apart from a bad
  name only helps someone probing.
- Success is 200 `image/png` with `Cache-Control: public, max-age=604800` and
  `ETag: "<sha256 of the bytes, first 16 hex chars>"`. A request whose `If-None-Match`
  equals that ETag gets 304 with the same two headers and no body.
- Both blocking calls run through `asyncio.to_thread`. Per-id fetches are serialised by an
  `asyncio.Lock` per id held in the router's module state, mirroring `RosterCache.Entry`,
  so eight rows asking for the same new brawler cost one CDN request.
- The token is read from `get_sup(request).settings.connection.brawl_api_token` and is
  never put in a log line, a header, a URL or a response. Only the exception type and, for
  the CDN, the HTTP status are logged, the way `roster.py` already does it.

**Prewarm (decided, the owner's answer to q-prewarm).** On server start, one background
pass fetches the icons for the brawlers in every configured instance's cached roster:
`brawlfarm/api/brawlers.py` exposes `prewarm(home, token, names)` and `app.py`'s lifespan
starts it with `asyncio.create_task(asyncio.to_thread(prewarm, ...))` without awaiting it,
so startup never blocks on the CDN. It runs at most once per process, is skipped entirely
when the token is blank, resolves the catalog once, fetches only ids with no file on disk,
sleeps 100 ms between fetches, and swallows every failure. If no roster is cached yet,
there is nothing to warm and the pass ends immediately; icons then arrive on first use as
before.

**Never from a worker.** Only the API process talks to the CDN. Nothing under
`brawlfarm/core/controller.py`, `states.py`, `vision.py` or the supervisor's worker path
imports `core/icons.py`.

### b. `GET /api/connection/check`

New router `brawlfarm/api/connection.py`, registered in `app.py` after `plans`.

```python
TTL_S = 300.0   # five minutes, the same budget roster.py spends

def credential_status(token: str, tag: str) -> str | None:
    """"no_token", "no_tag", or None when both are present. plans.py imports this."""

class ConnectionCache:
    async def get(self, token: str, tag: str) -> tuple[str, str]:  # (status, checked_at)
```

- The route reads the token from settings and the tag from the first configured instance
  with a non-blank `player_tag`, calls the cache, and returns
  `{"status": ..., "checked_at": ...}` where `status` is one of `ok`, `no_token`, `no_tag`,
  `rejected`, `unreachable` and `checked_at` is a local ISO timestamp to seconds. Always
  200.
- `no_token` and `no_tag` come from `credential_status` and cost no network call and no
  cache entry. The other three come from one `GET /players/{tag}` through `fetch_player`,
  at most once per `TTL_S`, with one `asyncio.Lock` so two open panels share one call.
- `rejected` is HTTP 401 or 403 from that call. Anything else, including a connection
  error, a timeout and a 5xx, is `unreachable`. `ok` is a clean 200.
- `brawlfarm/core/api.py` `ApiError` gains one optional attribute so the caller can tell
  those apart without parsing a message: `ApiError.__init__` keeps its single message
  argument and sets `self.status: int | None = None`, and `ApiClient._get` sets
  `err.status = resp.status_code` on the non-200 raise before raising. Today the status is
  only readable inside the message string `f"{path} -> HTTP {resp.status_code}: {body}"`,
  and that message also carries the encoded player tag, so it must never be parsed, logged
  or returned. The message text does not change, so `controller.py`'s three `except
  ApiError` blocks behave exactly as they do now.
- `plans.py` `enrich_plan` (lines 60 to 98) replaces its inline
  `if not token: ... elif not tag: ...` with `credential_status(token, tag)`, keeping the
  same two strings and the same `roster.get` call for everything else. `roster_status`
  therefore keeps its four values `ok | no_token | no_tag | unavailable` on the plan route;
  `rejected` and `unreachable` live only on the connection route.
- Never echoes, logs or returns the token or the tag.

### c. `last_session` on the instance status

New module `brawlfarm/api/sessions.py`, called from `instance_payload` in
`brawlfarm/api/instances.py`, which already reads that instance's files for
`today_counts`. The proposal put this read in `brawlfarm/supervisor`; it goes beside the
other route-side file readers instead, because the supervisor's tick must not grow a
per-status disk walk and `instances.py` is where `games.csv` and `status.json` are already
read.

```python
def last_session(inst_dir: Path) -> dict | None
```

- Picks the newest `session-*.jsonl` in the instance directory by filename (the name is
  `session-%Y%m%d-%H%M%S.jsonl`, so the names sort chronologically, which beats an mtime
  sort on a folder copied between machines). No file means `None`.
- Session start is that filename's timestamp, parsed with `%Y%m%d-%H%M%S` as local time.
  `ended_at` is the `ts` of the last parsable line. `duration_s` is `ended_at` minus the
  start, floored at 0 and returned as an int.
- `interrupts` counts the lines whose kind `feed.classify` puts under `"interrupts"`;
  `disconnects` counts the lines with `kind == "disconnect"`, which is what
  `controller.handle_disconnect` writes.
- `games`, `trophies` and `avg_rank` come from `games.csv` in the same folder, counting the
  rows whose `logged_at` falls between the session start and `ended_at` inclusive: the
  session log narrates, and `games.csv` is the only place the rank and the trophy change
  are written. `trophies` is the signed sum of `trophyChange`; `avg_rank` is the mean of
  `rank` rounded to 1 dp, or `null` when no row in the window carries a rank.
- The result is cached in a module-level dict keyed by the resolved instance directory,
  holding `(session filename, session mtime, games.csv mtime, value)`. The work is redone
  only when one of those three changes, so a Fleet poll every few seconds costs two
  `stat` calls per instance.
- Every read is wrapped: `OSError`, `csv.Error`, `UnicodeDecodeError`, a bad JSON line and
  an unparsable timestamp are skipped, and a file that cannot be read at all is `None`.
  A broken session file must never break a Fleet card.
- `instance_payload` gains `payload["last_session"] = last_session(inst_dir)` beside
  `payload["session"]` and `payload["today"]`. The existing `_session` block, which returns
  `minutes_elapsed`, `start_trophies`, `last_trophies`, `disconnect_count`,
  `recovery_attempts` and `session` from `status.json`, is not touched.

The block's shape, which is also the TypeScript type in section 10:

```python
{"games": int, "trophies": int, "avg_rank": float | None, "disconnects": int,
 "duration_s": int, "interrupts": int, "ended_at": "2026-09-12T22:14:07"}
```

### d. `brawlfarm/api/stats.py` (two lines)

- `trophies_per_hour` becomes `_num(net / hours) if hours >= MIN_HOURS else None`, with
  `MIN_HOURS = 0.5` next to `RECENT_LIMIT`. Today the guard is `hours > 0`, so one game
  logged in ninety seconds reads as hundreds of trophies an hour. This is the phase 3
  deferral.
- `hours_farmed` becomes `_num(hours, 2)`. `_num`'s default is 1 digit, and "3.2 h" hides
  the difference between two short sessions and one.

Nothing else in `stats.py` changes. `aggregate` keeps its shape
(`range`, `instances`, `summary{games, trophies, trophies_per_hour, avg_rank, top4_rate,
hours_farmed}`, `series[{instance, points[{t, cum}]}]`,
`brawlers[{name, games, net, avg_rank, top4_rate}]`, `ranks[{rank, games}]`,
`recent[{instance, t, brawler, rank, trophy_change, map, mode}]`), both routes keep their
`range` and `instances` query params and their 404 on an unknown instance, and
`RECENT_LIMIT` stays 20, which is already the owner's answer to q-recent.

## 5. Web foundations (props are the contract)

- `components/ui/BrawlerIcon.tsx`:

  ```ts
  export interface BrawlerIconProps {
    name: string | null;
    size?: number;      // default 22
  }
  ```

  A `<span>` of exactly `size` square with `border-radius: 6px`, `overflow: hidden`,
  `background: var(--panel-2)` and `flex: none`, holding an `<img>` of the same size with
  `src={`/api/brawlers/${encodeURIComponent(name)}/icon.png`}`, `alt=""` (the name is
  always beside it, so the icon is decorative), `loading="lazy"` and `decoding="async"`.
  On the image's `onError`, and when `name` is null or blank, the span renders the first
  character of the name upper-cased at 11 px in `--muted` instead, centred. The square is
  laid out before the image resolves and keeps its size in every state, so no row ever
  shifts. No retry, no timer, no cache of its own: the browser's HTTP cache plus the
  route's week-long `Cache-Control` is the cache.
- `components/ui/Table.tsx` gains three optional props and changes nothing else, so every
  phase 5 call site renders byte-for-byte as it does today:

  ```ts
  export interface Column<Row> {
    key: string; label: string; mono?: boolean; width?: string;
    render?: (row: Row) => ReactNode;
    sortable?: boolean;                       // new
  }
  export interface TableProps<Row> {
    columns: readonly Column<Row>[]; rows: readonly Row[];
    rowKey: (row: Row) => string; empty: ReactNode;
    sort?: { key: string; dir: "asc" | "desc" };            // new
    onSort?: (key: string) => void;                          // new
  }
  ```

  A column with `sortable` renders its header label inside a full-width `<button>` that
  calls `onSort(column.key)`; its `<th>` carries `aria-sort` of `"ascending"`,
  `"descending"` or `"none"`. A lucide `ChevronUp` or `ChevronDown` at 12 px follows the
  label of the sorted column only. Without `sort` and `onSort` no header is a button and no
  `aria-sort` is written. Sorting is the caller's job; `Table` never reorders `rows`.
- `api/stats.ts` keeps `getStatsToday` untouched and gains:

  ```ts
  export function getStats(range: StatsRange, instances: string[]): Promise<StatsResponse>;
  export function statsCsvHref(range: StatsRange, instances: string[]): string;
  ```

  Both build the same query string from the same helper: `?range=${range}` plus
  `&instances=${instances.join(",")}` when the list is shorter than the configured one.
  `statsCsvHref` returns `/api/stats/export.csv?...` as a string for an anchor's `href`;
  the download is a plain link, not a fetch, so the browser's own download is the feedback.
- `api/connection.ts` (new): `export function getConnection(): Promise<ConnectionCheck>`
  over `GET /api/connection/check`.
- `api/brawlers.ts` (new): `export function brawlerIconHref(name: string): string`, the one
  place the icon URL is built, used by `BrawlerIcon` and by nothing else.
- `api/queries.ts` `queryKeys` gains two keys beside the existing `statsToday`:

  ```ts
  stats: (range: string, instances: string[]) => ["stats", "range", range, instances.join(",")] as const,
  connection: () => ["connection"] as const,
  ```

  `statsToday` keeps its `["stats", "today", ...]` prefix, so the phase 4 invalidation still
  covers the Fleet and session reads and does not fight the new key.
- The connection query uses `staleTime: 300_000` and `refetchOnWindowFocus: false` at its
  call site, matching the server's five-minute cache; everything else keeps the client
  defaults.

## 6. Stats page components (decided)

Files: `web/src/stats/Stats.tsx`, `StatsToolbar.tsx`, `MetricsRow.tsx`, `TrophyChart.tsx`,
`BrawlerTable.tsx`, `RankBars.tsx`, `RecentGames.tsx`, `ConnectionStrip.tsx`.

**`Stats.tsx`.** Owns the URL params, reads `useInstances()` for the configured names, runs
the stats query and the connection query, and renders the toolbar, the strip, the metrics
row, the chart, the band and the recent list. A failed stats query renders `ErrorBlock`
with the error and nothing else. While the first request is in flight it renders the
skeleton of section 9. With `summary.games === 0` it renders the toolbar, the strip and the
empty sentence, and no chart, band or list.

**`StatsToolbar.tsx`.** Props
`{ range; instances; selected; onRange; onInstances; csvHref }`. The four ranges are a
`role="radiogroup"` labelled "Range" of four `role="radio"` buttons carrying
`aria-checked`, with Left and Right moving between them (the phase 4 `Segmented` shape, not
a new component). The instance chips are the existing `Chip` with `aria-pressed`; clicking
toggles one; clicking the last enabled chip does nothing, so at least one always stays on.
Export CSV is an `<a>` with `href={csvHref}` and `download`, styled as the quiet button.

**`MetricsRow.tsx`.** Props `{ summary }`. Six figures in this order with these labels:
games, trophies, trophies per hour, average rank, top-4 rate, time farmed. Trophies is
signed and tinted: `--accent` when positive, `--bad` when negative, `--muted` at zero.
Trophies per hour shows "after 30 min" in muted 12 px when `trophies_per_hour` is null and
`games > 0`, and "none" when there are no games at all. Average rank is one
decimal, top-4 rate is a whole percent with "%", time farmed is two decimals with " h".
Every number is `font-mono tabular-nums`.

**`TrophyChart.tsx`.** Props `{ series; instances }`, where `series` is the response's
`series` array. One `<svg viewBox="0 0 640 180" preserveAspectRatio="none">` at
`width: 100%`, `height: 180px`, with `vectorEffect="non-scaling-stroke"` on every path so
the 1.5 px stroke survives the stretch.

- One y axis at the left: three labels (min, zero or mid, max) and one 1 px `--line` rule
  at zero. No x axis, no gridlines; the first and last timestamps sit under the ends as
  11 px muted text.
- One `<path>` per selected instance, plotted on a shared time domain (the earliest to the
  latest point across the selection) and a shared value domain padded by 5 %. An instance
  with no points draws no path and still appears in the legend, so the legend matches the
  chips.
- Colours in series order: `--accent`, then `--ok`, `--warn`, `--series-1`, `--series-2`,
  `--series-3`, cycling. The proposal named an `--info` tone; `theme.css` has no such token,
  and `--series-1` is the chart-series token that does exist.
- An end label per series: the instance name at 11 px in the series colour, placed at its
  last point, nudged vertically when two labels would overlap. The legend is a row of name
  plus a 8 px colour dot above the chart.
- Crosshair: a 1 px vertical `--line` rule at the hovered or focused index with a readout
  panel giving the timestamp and one `name: value` line per series. The svg has
  `tabIndex={0}`, `role="img"` and an `aria-label` of "Cumulative trophy change"; Left and
  Right move the crosshair by one point, Home and End jump to the ends, Escape clears it,
  and a visually hidden `aria-live="polite"` region announces the same readout text.
- A "Table" text button at the top right toggles to a `Table` of the same points, columns
  Time, then one per instance, and back. The toggle is component state, not a URL param.
- No animation in any state: no draw-in, no transition on the crosshair, nothing to disable
  for reduced motion.

**`BrawlerTable.tsx`.** Props `{ rows }`. A `Table` with columns icon (label "", width
"34px", renders `BrawlerIcon`), Brawler (mono), Games, Net, Avg rank, Top 4. Every column
but the icon is `sortable`. Sort state is component state, default `{ key: "games", dir:
"desc" }`; clicking a header sorts descending first, then toggles. Ties break on name
ascending, which is the order the API already returns. Net is signed and tinted like the
metrics row. Empty renders "No games in this range."

**`RankBars.tsx`.** Props `{ rows }`, the response's `ranks`. Ten rows, rank 1 at the top
through rank 10, including ranks with no games. Each row is the rank in mono at the left, a
4 px tall bar in `--accent` on a `--panel-2` track scaled to the largest count, and the
direct label `${games} (${percent}%)` at the end of the bar in 11 px muted. No axis, no
gridlines. Percent is of the ranked games in the range, rounded to a whole number.

**`RecentGames.tsx`.** Props `{ rows }`. A `Table` of the twenty rows the API returns,
newest first, columns Time (mono, `hhmm`), Instance (mono), Brawler (the icon then the name),
Mode, Map, Rank (mono), Trophies (mono, signed, tinted). A null `mode` or `map` renders as
"none" in muted. Empty renders "No games in this range."

**`ConnectionStrip.tsx`.** Props `{ status; instanceWithoutTag }`. One quiet strip under the
toolbar, `--panel-2` with a 1 px `--line` and a 3 px left border in the tone, never a modal
and never a toast. Tones: `bad` for `rejected`, `warn` for `no_token`, `no_tag` and
`unreachable`. It renders nothing for `ok`. The sentences and their links are in section 8.
The strip is shown above the empty state when both apply, because a missing token explains
the empty page.

## 7. Instance page changes (decided)

- **`instance/FarmPlan.tsx`.** A `BrawlerIcon` with the default 22 px goes before the
  current brawler's name, before each name in the "Next in queue" list, and before each
  name in the "Show all brawlers" list. Each is added inside the existing flex row ahead of
  the `font-mono` span, with `gap-2` unchanged. Row heights do not change: the icon is
  22 px, the rows already clear that. Nothing else in the file moves.
- **`instance/FarmPlan.tsx` roster note (decided, the owner's blank q-rejected).** When the
  token is rejected, the roster shows the same sentence Stats shows. `rosterNote` gains one
  branch: the component reads the connection query, and when `plan.roster_status` is
  `"unavailable"` and the connection status is `"rejected"`, the note becomes "The Brawl
  Stars API rejected the token. Check the token, and the IP address it was created for, in
  Settings, Connection." with "Settings, Connection" linking to `/settings/connection`. Its
  three existing branches, and the wording of the `unavailable` fallback, are untouched.
- **`instance/SessionPanel.tsx`.** The `lastLive` ref at lines 41 to 60 keeps doing exactly
  what it does now while the tab is open: live figures are mirrored into the ref, and a stop
  freezes them with the feed's own `stop` timestamp. What changes is the cold load. When the
  panel first mounts with a frozen state and has therefore never seen live figures, it seeds
  `lastLive` from `inst.last_session` instead of from the zeroed `status.json` session, and
  seeds `endedAt` from `last_session.ended_at`, so the caption reads "Session ended 22:14"
  with that session's real figures. The mapping is games to Games, trophies to Trophies,
  `avg_rank` to Avg rank, disconnects to Disconnects, `duration_s` to Duration through the
  existing `duration` formatter, interrupts to Interrupts. With `last_session` null the
  panel behaves exactly as it does today. Once a worker goes live the panel follows it and
  never reads `last_session` again for that mount.
- **`app/Rail.tsx`.** `SECTIONS[1]` becomes `{ to: "/stats", label: "Stats", soon: false }`.
  The `soon` field, the span at line 47 and the Settings row stay as they are.
  `app/Rail.test.tsx`'s assertion that the Stats link reads "Stats soon" becomes an
  assertion that it reads "Stats" and that no "soon" text remains.

## 8. Copy (verbatim)

Every string the screen shows. The plan and the tests quote from here.

**Page.** Title "Stats". Range tabs "Today", "7 days", "30 days", "All". Group label
"Range". Button "Export CSV". Chart toggle "Table". Chart label "Cumulative trophy change".

**Metrics labels, in order.** "games", "trophies", "trophies per hour", "average rank",
"top-4 rate", "time farmed". The trophies-per-hour placeholder "after 30 min". The
no-value placeholder "none".

**Brawler table.** Columns "Brawler", "Games", "Net", "Avg rank", "Top 4". Empty "No games
in this range."

**Rank bars.** Heading "Rank distribution". Row label "1" through "10". Direct label
"12 (24%)".

**Recent games.** Heading "Recent games". Columns "Time", "Instance", "Brawler", "Mode",
"Map", "Rank", "Trophies". Empty "No games in this range."

**Empty state.** "Stats appear after the first match."

**The five prompt strips.**

- No token: "Battle log unavailable. Add a Brawl Stars API token in Settings to see
  per-game stats." with "Settings" linking to `/settings/connection`.
- No tag, naming the selected instance: "Add a player tag for Pie64 in Settings, Instances
  to see its games." with "Settings, Instances" linking to `/settings/instances`.
- Rejected: "The Brawl Stars API rejected the token. Check the token, and the IP address it
  was created for, in Settings, Connection." with "Settings, Connection" linking to
  `/settings/connection`.
- Unreachable: "The Brawl Stars API did not answer. Stats show what was logged so far."
- Nothing at all for `ok`.

The first two are the spec's own sentences and are quoted from it letter for letter.

**Instance page.** Session caption "Session ended 22:14". Session figure labels stay as
they are today. The roster's rejected note is the rejected sentence above, unchanged.

**README.** One line in the attribution paragraph: "Brawler art is served from the Brawlify
CDN and belongs to Supercell under its fan content policy."

**Shared errors.** `ErrorBlock` behaviour is unchanged from phase 4. There is no toast
anywhere in phase 6: the CSV download is its own feedback and every failure is either a
strip or an `ErrorBlock`.

## 9. States, empty and error strips (verbatim, binding)

These are what the screenshots and the tests pin.

- Loading: a skeleton of six 18 px `--panel-2` blocks in the metrics row and one 180 px
  `--panel-2` block where the chart goes, with no spinner and no pulse animation. The
  toolbar renders immediately, because its state comes from the URL and not from the
  request.
- Empty, no games in range: the toolbar, then "Stats appear after the first match.", and no
  chart, band or list.
- The no-token strip, warn tone, with "Settings" linked.
- The no-tag strip, warn tone, naming the instance, with "Settings, Instances" linked.
- The rejected strip, bad tone, with "Settings, Connection" linked.
- The unreachable strip, warn tone, and every number still on the page below it.
- The chart's Table view: the same points as a `Table`, the toggle reading "Table" in both
  directions.
- A sorted table header: the focus ring on the header button, the chevron, and
  `aria-sort="descending"` on that `<th>` and `"none"` on the others.
- The icon fallback: the 22 px square in `--panel-2` with the brawler's initial, on the
  exact baseline the loaded icon sits on.
- The Session panel on a cold load: the last session's figures with the caption "Session
  ended 22:14".
- A visible focus ring on every range radio, every instance chip, the Export CSV link,
  every sortable header and the chart itself.

## 10. Web types and API client additions

`api/types.ts` grows these and edits nothing that exists except `InstanceView`, which gains
one optional field.

```ts
export type StatsRange = "today" | "7d" | "30d" | "all";

export interface StatsPoint { t: string; cum: number }
export interface StatsSeries { instance: string; points: StatsPoint[] }
export interface StatsBrawler {
  name: string; games: number; net: number;
  avg_rank: number | null; top4_rate: number | null;
}
export interface StatsRank { rank: number; games: number }
export interface StatsGame {
  instance: string | null; t: string; brawler: string | null;
  rank: number | null; trophy_change: number | null;
  map: string | null; mode: string | null;
}

/** StatsResponse grows from the summary-only phase 4 shape to the whole aggregate. */
export interface StatsResponse {
  range: string;
  instances: string[];
  summary: StatsSummary;
  series: StatsSeries[];
  brawlers: StatsBrawler[];
  ranks: StatsRank[];
  recent: StatsGame[];
}

export type ConnectionStatus = "ok" | "no_token" | "no_tag" | "rejected" | "unreachable";
export interface ConnectionCheck { status: ConnectionStatus; checked_at: string }

export interface LastSession {
  games: number; trophies: number; avg_rank: number | null;
  disconnects: number; duration_s: number; interrupts: number; ended_at: string;
}
```

`InstancePayload` gains `last_session: LastSession | null`. `StatsSummary` and
`RosterStatus` keep their current definitions; `RosterStatus` deliberately stays
`"ok" | "no_token" | "no_tag" | "unavailable"`, because the plan route still answers with
those four.

`web/src/test/fixtures.ts` gains `makeStats(overrides)`, `makeConnection(overrides)` and
`makeLastSession(overrides)` in the style of `makePlan`, and `makeInstance` gains
`last_session: null` in its defaults, so no test hand-writes an aggregate.

## 11. Safety, hygiene and process constraints (Global Constraints for the plan)

- The safety rails of spec section 9 are absolute and untouched. The UI never sends a tap,
  never exposes a shop or purchase action, never bypasses the API. Tap coordinates, OCR
  needles, HSV windows and the calibration block of `brawlfarm/core/config.py` are not
  edited. `controller.py`, `states.py`, `vision.py` and `farmplan.py` are not edited. The
  only files under `brawlfarm/core` that change in phase 6 are the new `icons.py` and the
  one optional `status` attribute on `api.py`'s `ApiError`. The never-tap rail tests must
  pass unchanged.
- One worker per instance, ever. Nothing in this phase starts, stops or kills a process.
- No user-supplied string reaches a shell or a filesystem path. A brawler name is matched
  against `BRAWLER_NAME_RE` and then discarded: the cached icon's path is built from the
  integer id. Instance names keep going through `resolve_instance`.
- No chart library and no new web dependency of any kind. The chart, the bars and the
  crosshair are hand-written SVG and CSS. No new Python dependency either: the CDN fetch
  uses `requests`, which `core/api.py` already imports.
- No CDN fetch from a worker. Only the API process talks to `cdn.brawlify.com`, only from
  `core/icons.py`, only on a request or the single start-up prewarm.
- The icon cache lives under the data directory only: `<home>/cache/brawlers.json` and
  `<home>/cache/brawlers/<id>.png`, both created by the API process. Nothing is written to
  the repository, to a temp directory outside that folder, or to any instance folder.
- The Brawl Stars API token never appears in a URL, a log line, an error message, a
  response body, a header the browser can see, or a screenshot. Only the exception type and
  an HTTP status code are logged. The player tag is subject to the same rule, and
  `ApiError`'s message, which embeds the requested path and therefore the tag, is never
  logged or returned.
- Copy: no em-dashes, no emoji, no exclamation marks; state is a word plus a colour; copy
  says what happened, what went wrong and how to fix it.
- Scrub: `uv run python tools/scrub_check.py` prints `0 hit(s)` before every commit, and
  the commit is chained on its exit code. No player tag, nickname, user path or token
  appears in code, tests, fixtures, screenshots or PR text. Fixtures use Pie64 / Pie64_1 /
  Pie64_3, ports 5555 / 5565 / 5585, and the made-up tag `#2P0YLQ9`. Docs show a data
  folder as `instances/Pie64`, never as an absolute path.
- Every commit carries a conventional message plus these two trailer lines exactly:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV`.
  `git config user.name` is `as9pa`.
- Green before every commit: `pnpm typecheck`, `pnpm test`, `pnpm build`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`.
- The branch is `phase-6/stats-with-brawler-icons` from `main`; one PR; the PR carries
  screenshots of the real panel with any player tag and every thumbnail blurred
  (playwright-cli `eval` sets `filter: blur(14px)` on `[data-private]` before the shot).

## 12. Tests

**pytest**, every one of them with a stubbed CDN and a stubbed official API; no test makes
a network call.

- `core/icons.py`: `resolve_id` from a cached catalog with no fetch; a miss triggering one
  refresh; a second miss inside the hour triggering none; a refresh with a blank token
  returning `None` and leaving the file alone; a refresh that raises leaving the file
  alone; `ensure_icon` serving an existing file without fetching; fetching and writing on a
  miss; rejecting a non-PNG body, an oversized body and a non-200.
- `GET /api/brawlers/{name}/icon.png`: 200 with the two headers and the PNG bytes; 304 on a
  matching `If-None-Match`; 404 for an unknown name, a blank token, a CDN failure and a
  name that fails `BRAWLER_NAME_RE`; one test that two concurrent requests for the same new
  id cause exactly one CDN call; one test that neither the token nor the tag appears in the
  captured log records.
- `prewarm`: with no token it makes no call; with a token and a cached roster it fetches
  only the ids with no file; a raising fetch does not propagate.
- `GET /api/connection/check`: `ok`, `no_token`, `no_tag`, `rejected` from a 403 and from a
  401, `unreachable` from a `RequestException` and from a 500; a second call inside the TTL
  making no second fetch; `checked_at` present in all five; the token absent from the body
  and from the log.
- `credential_status` used by `plans.py`: the existing plan-route tests for `no_token` and
  `no_tag` must pass unchanged.
- `last_session`: a folder with no session file is `None`; one finished session file plus a
  matching `games.csv` gives the seven fields; a session with no ranked game gives
  `avg_rank` null; a session file with a broken JSON line still counts the rest; a
  half-written `games.csv` gives zeros instead of raising; the newest of three session files
  is the one read; the second call with nothing changed does not re-read the files.
- `aggregate`: `trophies_per_hour` is null at 0.4 h farmed and a number at 0.6 h;
  `hours_farmed` carries two decimals.

**vitest**, one file per component.

- `BrawlerIcon`: the image src, the fallback initial after an error, the fallback for a null
  name, and that the rendered box is the same size in both states.
- `Table`: no `aria-sort` and no header button without the new props; `aria-sort` and one
  `onSort` call per header click with them; the existing phase 5 `Table` tests unchanged.
- `Stats`: the default range is `7d` with no query string; a `?range=30d&instances=Pie64`
  URL reaches the request; toggling a chip rewrites the URL and refetches; the last enabled
  chip cannot be turned off; an unknown name in the URL is dropped; the skeleton, the empty
  sentence and the `ErrorBlock` path.
- `StatsToolbar`: Left and Right move between the range radios; Export CSV's `href` carries
  the current query.
- `MetricsRow`: the six labels, the signed tint, "after 30 min", two decimals on hours.
- `TrophyChart`: one path per non-empty series and a legend entry per selected instance;
  Left, Right, Home, End and Escape moving and clearing the crosshair; the live region's
  text; the Table toggle swapping the views; no element carries a transition.
- `BrawlerTable`: the default games-descending order; a click sorting descending then
  ascending; `aria-sort` following it; the empty sentence.
- `RankBars`: ten rows including ranks with no games; the direct label text.
- `RecentGames`: twenty rows, newest first, "none" for a null map or mode.
- `ConnectionStrip`: one test per status including that `ok` renders nothing, and that each
  link points at the right settings section.
- `FarmPlan`: an icon before the current brawler, before each queue row and in the full
  list; the rejected note when the connection says `rejected`; the three existing notes
  unchanged.
- `SessionPanel`: a cold load with `last_session` showing its figures and "Session ended
  22:14"; a cold load with `last_session` null behaving as today; a live worker never
  reading `last_session`; the existing freeze-on-stop tests unchanged.
- `Rail`: the Stats link has no "soon".

**The live pass** is the last task, not a test file: the real install on a scratch home,
with the real token and one real instance, checked against section 9's list of states.

## 13. Task list for the plan (10 tasks, this order)

1. **Icons, Python.** `brawlfarm/core/icons.py` and `brawlfarm/api/brawlers.py` with the
   catalog cache, the disk cache, the headers, the 404 cases, the per-id lock and the
   prewarm hook in `app.py`. Consumes: `core/api.py:get_brawlers`, `deps.get_sup`,
   `deps.get_home`, `jsonio`. Produces: `GET /api/brawlers/{name}/icon.png`,
   `icons.resolve_id`, `icons.ensure_icon`, `brawlers.prewarm`. Review must check: the
   cached path is built from the integer id and never from the name; the refresh is rate
   limited; no token or tag reaches a log; nothing is written outside `<home>/cache`; the
   prewarm cannot block or crash startup.
2. **Connection check, Python.** `brawlfarm/api/connection.py`, `credential_status` shared
   into `plans.py`, and the `status` attribute on `ApiError`. Consumes: `roster.fetch_player`,
   `core/api.py:ApiClient`. Produces: `GET /api/connection/check`, `credential_status`.
   Review must check: 401 and 403 map to `rejected` and everything else to `unreachable`;
   the TTL holds; the plan route's four statuses are unchanged; the `ApiError` message text
   is unchanged so `controller.py` still behaves; nothing echoes the token.
3. **`last_session`, Python.** `brawlfarm/api/sessions.py` and the one line in
   `instance_payload`. Consumes: `feed.classify`, `datalog.GAME_FIELDS`, `deps`. Produces:
   `sessions.last_session` and the `last_session` block on every instance payload. Review
   must check: the newest file is chosen by name; every read is guarded; the mtime cache
   invalidates on all three inputs; `_session` and `today_counts` are untouched.
4. **Stats aggregation, Python.** `MIN_HOURS` and the two-decimal hours in
   `brawlfarm/api/stats.py`. Consumes: nothing new. Produces: the corrected `summary`.
   Review must check: only those two expressions changed, and the existing stats tests still
   pass.
5. **`BrawlerIcon` and the farm plan icons.** `components/ui/BrawlerIcon.tsx`,
   `api/brawlers.ts`, the three call sites in `instance/FarmPlan.tsx`. Consumes: the icon
   route. Produces: `BrawlerIcon`. Review must check: no layout shift in either state, the
   `alt` is empty, and no farm-plan row changed height.
6. **Stats shell.** `stats/Stats.tsx`, `StatsToolbar.tsx`, `MetricsRow.tsx`,
   `ConnectionStrip.tsx`, `api/stats.ts`'s two new functions, `api/connection.ts`, the
   `queryKeys` additions, the types, the fixtures, and the route swap in `App.tsx`.
   Consumes: `GET /api/stats`, `GET /api/connection/check`. Produces: the page, the toolbar
   and the strip. Review must check: the URL is the single source of range and selection;
   the five strips render their exact sentences; the skeleton and empty states match
   section 9.
7. **`TrophyChart`.** `stats/TrophyChart.tsx` with the axis, the paths, the legend, the end
   labels, the crosshair, the keyboard handling, the live region and the Table toggle.
   Consumes: `StatsResponse.series`. Produces: `TrophyChart`. Review must check: no library
   import; no animation or transition anywhere; the keyboard path reaches every point; the
   colours are only tokens that exist in `theme.css`.
8. **Table sorting, brawlers, ranks, recent.** The three new `Table` props,
   `BrawlerTable.tsx`, `RankBars.tsx`, `RecentGames.tsx`. Consumes: `StatsResponse.brawlers`,
   `.ranks`, `.recent`, `BrawlerIcon`. Produces: the two-column band and the recent list.
   Review must check: `aria-sort` is correct on all three states; `Table` never reorders
   rows itself; every phase 5 `Table` call site is visually unchanged.
9. **Session panel cold load and the rail.** `instance/SessionPanel.tsx` seeded from
   `last_session`, the rejected note in `FarmPlan.tsx`, `app/Rail.tsx` and its test.
   Consumes: `last_session`, `GET /api/connection/check`. Produces: the cold-load figures
   and the caption. Review must check: a live worker still wins over `last_session`; the
   null case is byte-for-byte today's behaviour; the freeze-on-stop tests did not need
   editing.
10. **Finish.** The README attribution line; the API route list in the README gains the
    three new routes; `docs/PLAN.md`'s phase 6 row; a keyboard and focus pass over the
    toolbar, the chart and the sortable headers; reduced motion; phone width; light theme;
    the live pass against the real install on a scratch home; blurred screenshots; the PR
    body. Review must check: every sentence on the screen matches section 8 letter for
    letter, and `tools/scrub_check.py` prints `0 hit(s)`.

## 14. Accepted proposal ids (all 14, for traceability in task briefs)

stats-range, stats-metrics, stats-chart, stats-brawlers, stats-ranks, stats-recent,
stats-export, stats-empty, stats-nav, inst-icons, inst-last-session, api-icons,
api-connection, readme-attribution.
