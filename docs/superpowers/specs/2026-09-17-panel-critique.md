# Panel critique: decisions and scope

A design critique of the React panel (`brawlfarm/web`) was published as a review artifact on
2026-09-17, and the owner answered it. This spec records the decisions the eight follow-up pull
requests build from. Critique artifact: https://claude.ai/artifact/BnS6FS2LG5GDerqt6eymSN. Build
plan artifact: https://claude.ai/artifact/V28iMRPL3uvT4BV8t7WXjK.

## Owner answers and rulings

### Instance page below 1100 px

The owner left the layout to the maintainer. Ruling: two columns on desktop, a sticky jump bar
below 1100 px. Affected item: 22.

### Who opens the panel

The owner answered only me, this PC. Ruling: phone-only items drop to the end of the queue.
Affected items: 5, 48, 70.

### Worker, supervisor, tick

The owner answered yes. Ruling: the three words are retired from the UI; the instance name and
brawlfarm are the only actors. Affected items: 31, 46, 64.

### Where calibration lives

The owner left the placement to the maintainer. Ruling: calibration stays a top-level page, with a
plain intro. Affected item: 56.

### Remove, delete data, reset

The owner left the choice between the two grouping options to the maintainer. Ruling: option 1, one
Danger zone at the end of Settings, Data. Affected items: 61, 62.

### Mono or Archivo

The owner left the choice between the mono options to the maintainer. Ruling: option 3, JetBrains
Mono for figures, Archivo for names. Affected item: 79.

### Alert strip on Fleet

The owner left the strip's behavior to the maintainer. Ruling: keep the strip, fixed, for alerts
that need the owner's attention; recovered interrupts go to the drawer only. Affected items: 3, 10,
20.

### Appearance section

The owner said to keep About as it is, reasoning that there is currently only one control (the
theme picker) that would belong in a separate Appearance section, so a whole section is not worth it
for one option; if more customization arrives later, an Appearance section can be added then.
Ruling: About stays; the theme picker moves to the top of About under its own heading. Affected
item: 67.

The owner's note on the critique page also asked for a new release once everything in this spec is
done.

## Scope rules

Nothing under `brawlfarm/core` changes in this work. No API contract changes unless a task says so.
The never-tap rails, the dark-first palette and gold accent, and the type-the-word confirmation
dialogs all stay as they are.

Vocabulary rule: worker, supervisor and tick leave the UI. Logs, code and the API keep their names;
only strings the panel shows change.

Type rule: mono (JetBrains Mono, tabular numerals) for figures, ids, ports, tags and times; Archivo
for brawler and instance names, in sentence case.

Casing rule: sentence case throughout, except table headers and the rail eyebrow, which stay
uppercase.

Number rule: numbers and dates go through Intl formatting (`Intl.NumberFormat`,
`Intl.DateTimeFormat`) instead of hand-rolled strings.

State rule: every screen has its empty, loading, error, saving and focus states designed, not just
its populated state.

## Pull requests

| # | Title | Branch | Items | Verification |
|---|---|---|---|---|
| 1 | Copy and glossary | `panel/copy-glossary` | 10, 14, 28, 30, 31, 38, 43, 47, 83, 84, 85, 86 | Snapshot tests for feedText over every event kind; a vitest that greps web/src for worker, supervisor, tick, True, =0.; pnpm typecheck and test; sonnet task review and whole-branch review. |
| 2 | Component kit | `panel/kit` | 6, 76, 77, 78, 79, 80, 81, 82 | A kit route under /dev in the Vite build shows every variant; keyboard walk of the four pages; axe on each route; pnpm typecheck and test; sonnet reviews. |
| 3 | Fleet and shell | `panel/fleet-shell` | 1, 2, 3, 4, 7, 8, 9, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21 | playwright-cli captures at 1440 in both themes compared against the wireframe; a two-instance mock; the drawer opened on a long page; sonnet reviews. |
| 4 | Instance page | `panel/instance` | 22, 23, 24, 25, 26, 27, 29, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45 | Live pass on Pie64 with the feed open while a session starts and stops; pytest unchanged; captures at 1440 and 1000; sonnet reviews. |
| 5 | Stats | `panel/stats` | 48, 49, 50, 51, 52, 53, 54, 55 | Captures at 1440 and 400; a fixture with three instances and a 30-day range; sonnet reviews. |
| 6 | Settings and setup | `panel/settings-setup` | 46, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71, 72, 73, 74, 75 | Walk the wizard on a fresh config in a temp home; every destructive flow still needs the typed word; captures of each section; sonnet reviews. |
| 7 | Calibration | `panel/calibration` | 56, 57, 58, 59, 60 | Captures at 1440 with an instance running; nothing under brawlfarm/core changes; sonnet reviews. |
| 8 | Narrow screens and release | `panel/narrow-and-release` | 5, 70 | Captures at 400; CHANGELOG or release notes assembled from the seven PR bodies; tag v1.1.0 and a GitHub release after the last merge. |

## Items

| # | Id | Sev | Screen | Title | Adjusted |
|---|---|---|---|---|---|
| 1 | shell-two-titles | major | shell | Every page shows its title twice | |
| 2 | shell-live-pill | major | shell | Connection state is an 11 px pill nobody reads, and the instance page never mentions it | |
| 3 | shell-alerts-count | minor | shell | "Alerts 6" is two words and a number with no relationship | |
| 4 | shell-rail-instances | minor | shell | Instance names in the rail are mono with a colour-only dot | |
| 5 | shell-rail-narrow | minor | shell | Under 820 px the instance list disappears with no way back to an instance | Deferred to the last PR (narrow screens only). |
| 6 | shell-skip-focus | minor | shell | No skip link, and three controls have no visible focus ring | |
| 7 | shell-alerts-drawer | minor | shell | Alerts drawer: time only, no date, no loading state, dismiss all without undo | |
| 8 | shell-theme-color | nit | shell | No theme-color meta, so the browser chrome does not match either theme | |
| 9 | shell-drawer-scrim | minor | shell | The alert drawer and its scrim stop at the first screen height | |
| 10 | fleet-alert-strip-repr | blocker | fleet | The alert strip prints Python: "score=0.456, recovered=True" | Strip shows only alerts that need action; recovered interrupts appear in the drawer only. |
| 11 | fleet-status-three-places | major | fleet | One card shows its state in three places, three styles | |
| 12 | fleet-port-unlabeled | major | fleet | "5555" next to the name means nothing to most people | |
| 13 | fleet-metrics-formats | major | fleet | Four metrics, three number formats, one changing label | |
| 14 | fleet-restart-means-start | major | fleet | A stopped instance has no Start button, only Restart | |
| 15 | fleet-open-twice | minor | fleet | Open twice: the name is a link and there is an Open button | |
| 16 | fleet-stop-all-undo | major | fleet | Stop all has no confirmation and no undo; a single Stop has undo | |
| 17 | fleet-loading-zero | major | fleet | Fleet renders "0 instance" and a line of zeros while loading | |
| 18 | fleet-totals-line | minor | fleet | The totals line is mono text with middle dots | |
| 19 | fleet-thumbnail-chip | nit | fleet | The age stamp sits on the live frame in mono with a space before "s" | |
| 20 | fleet-alert-more | minor | fleet | "5 more" is a button with no object | The 5 more button becomes the drawer link with the count; the strip itself never lists more than one alert. |
| 21 | fleet-offline-copy | minor | fleet | Offline card copy is authored twice: in the client and in the server note | |
| 22 | inst-five-panels | major | instance | Five panels in one scroll, no tabs, no anchors | Jump bar below 1100 px instead of tabs; two columns on desktop unchanged. |
| 23 | inst-header-clutter | major | instance | The header row is a bag of tokens | |
| 24 | inst-restart-no-confirm | major | instance | Restart is more disruptive than Stop but has neither confirmation nor undo | |
| 25 | inst-screenshot-two-words | nit | instance | Screenshot and Full size open the same URL | |
| 26 | inst-live-refresh | minor | instance | Refresh has no in-flight state and the frame age has no absolute time | |
| 27 | inst-pending-blank | minor | instance | The instance page renders an empty div while loading | |
| 28 | inst-session-none | minor | instance | Session panel: "none" as a value, 0 for missing data, three time notations | |
| 29 | inst-figures-live | nit | instance | Session figures update live with no live region | |
| 30 | feed-fallback-repr | major | feed | Unknown feed events print key=value pairs in lowercase | |
| 31 | feed-worker-word | major | feed | "Worker", "supervisor" and "tick" are internal words shown as copy | |
| 32 | feed-no-grouping | minor | feed | The feed is a flat list with a colour dot for severity and no day markers | |
| 33 | feed-follow | nit | feed | Follow switches itself off when you scroll and never says so | |
| 34 | feed-live-region | minor | feed | A live narration with no role=log | |
| 35 | feed-height | nit | feed | Feed is capped at 420 px regardless of viewport | |
| 36 | plan-goal-silent | major | plan | Goal rejects input silently | |
| 37 | plan-saved-toast | minor | plan | "Plan saved" toasts on every keystroke burst, plus a Saved hh:mm tag | |
| 38 | plan-none-values | minor | plan | "none" and unformatted numbers in the progress row | |
| 39 | plan-fallback-field | minor | plan | Fallback brawler accepts any text and hints "Brawler name" | |
| 40 | plan-roster-list | nit | plan | Show all brawlers has no aria-expanded and renders the whole roster unvirtualised | |
| 41 | plan-maxed-help | minor | plan | "Maxed fallback" has no help line | |
| 42 | sched-bar-unreadable | major | schedule | The day bar has no hour labels, no legend and no accessible description | |
| 43 | sched-override-copy | major | schedule | "Override: stop until 05:23" interpolates an enum into English | |
| 44 | sched-run-for | minor | schedule | Run for [2] hours: no max, no reason for 2, Start and Redraw double-submit | |
| 45 | sched-timezone | nit | schedule | No timezone anywhere | |
| 46 | sched-settings-page | minor | schedule | Settings, Schedule is a whole page for one switch | |
| 47 | stats-mode-enum | major | stats | Recent games prints "trioShowdown" and "none" trophies | |
| 48 | stats-table-phone | minor | stats | Recent games is cut off at phone width | Now: the table scrolls inside its own container at any width. Later: two-line rows. Severity drops to minor. |
| 49 | stats-metrics-case | minor | stats | Metric labels are lowercase, "1.85 h" is decimal hours, "100%" wraps oddly | |
| 50 | stats-chart | major | stats | The chart has two y values, two x dates and no visible title | |
| 51 | stats-rank-bars | minor | stats | Rank bars scale to the largest rank while the text is a percent of total | |
| 52 | stats-chip-noop | minor | stats | Deselecting the last instance chip does nothing, silently | |
| 53 | stats-brawlers-empty-space | nit | stats | The Brawlers panel keeps a fixed height with one row | |
| 54 | stats-url | nit | stats | A stale ?instances= link is silently narrowed | |
| 55 | stats-table-view | minor | stats | The chart's Table view is 42 rows of cumulative totals under a header that is the instance name in capitals | |
| 56 | cal-jargon | major | calibration | The page explains itself in file names | |
| 57 | cal-overlay-clutter | major | calibration | The overlay draws every label at once and they overlap into noise | |
| 58 | cal-overrides-equal | minor | calibration | Overrides table lists values that equal their defaults | |
| 59 | cal-last-seen | nit | calibration | "Last seen" mixes now, hh:mm and never, with a hand-rolled clock | |
| 60 | cal-observe-switch | minor | calibration | Record while I play starts a 512 MB recording from a bare switch | |
| 61 | set-danger-cues | major | settings | Remove and Delete data look like Edit | Option 1: one Danger zone in Settings, Data. The Instances row keeps Edit only. |
| 62 | set-confirm-word | minor | settings | Type-the-word dialogs hide the word once you start typing | |
| 63 | set-adb-path-clipped | minor | settings | The ADB path is clipped without an ellipsis and there is no test button | |
| 64 | set-behavior-jargon | major | settings | Behavior switches are named after the code, and Advanced leaks adb, templates, detector | |
| 65 | set-notifications | minor | settings | Notifications: empty inputs with no placeholders, channels named two ways, checkbox grid reads sideways | |
| 66 | set-instances-table | minor | settings | Instances: ADB port as a header, #TAG placeholder, no scan explanation | |
| 67 | set-theme-in-about | minor | settings | Theme lives under About | No Appearance section. Theme heading at the top of About. |
| 68 | set-saved-caption | nit | settings | "Applies to a worker the next time it starts" appears twice, and "Saved 05:22" has no object | |
| 69 | set-data-path | nit | settings | The data folder path is in a hover title only | |
| 70 | set-nav-narrow | nit | settings | The settings section list scrolls sideways on phones with no cue | Deferred to the last PR (narrow screens only). |
| 71 | set-behavior-advanced-reset | minor | settings | Seven Advanced switches default on, with no way back to defaults and no word on what turning one off costs | |
| 72 | setup-typed-path | major | setup | Typing the adb path never enables Continue | |
| 73 | setup-rail-checks | minor | setup | The step rail never checks Display, and step 1 is unchecked on a return visit | |
| 74 | setup-answers-chip | nit | setup | "Answers" as a status word, "1600 x 900" with a letter x | |
| 75 | setup-done-start | nit | setup | Done hides the Start switch when there are no instances and says why nowhere | |
| 76 | kit-toast-tone | major | kit | Success and failure toasts look identical | |
| 77 | kit-switch-disabled | minor | kit | A disabled checked switch is just a dimmer checked switch | |
| 78 | kit-field-props | minor | kit | Field has no error slot, no inputmode, no spellcheck, no autocomplete control | |
| 79 | kit-mono-overuse | minor | kit | JetBrains Mono is used for anything numeric or named, which flattens hierarchy | Figures stay mono with tabular numerals; names move to Archivo in sentence case. |
| 80 | kit-button-styles | minor | kit | Three action styles on one row with no rule | |
| 81 | kit-radius-shape | nit | kit | Chips are pills, buttons are 6 px, panels are 10 px, inputs are 6 px, the alert strip is 10 px | |
| 82 | kit-numbers-intl | minor | kit | No Intl.NumberFormat or DateTimeFormat anywhere | |
| 83 | copy-casing | minor | copy | Casing is inconsistent across labels | |
| 84 | copy-errors-fix | minor | copy | Some errors say what, not what to do | |
| 85 | copy-ellipsis | nit | copy | In-progress strings do not end with an ellipsis, and one apostrophe is straight | |
| 86 | copy-1600 | nit | copy | "need 1600 x 900" is hardcoded in the feed text | |

## Gate and review

Every pull request runs the full gate: `pnpm typecheck` and `pnpm test` in `brawlfarm/web`,
`uv run pytest -q -p no:cacheprovider`, `uv run ruff check .`, `uv run ruff format --check .`, and
`uv run python tools/scrub_check.py` printing `0 hit(s)`.

Each task gets a sonnet spec-compliance and code-quality review, and each branch gets a whole-branch
sonnet review before its pull request opens, with findings fixed by an implementer and re-reviewed
once. Pull request 4 touches the instance page the farm loop reports into, so it also gets a live
pass on Pie64.

After pull request 8 merges, the panel ships as release 1.1.0: the version bumps in
`pyproject.toml`, `brawlfarm/__init__.py` and `brawlfarm/web/package.json`, a `v1.1.0` tag is cut,
and a GitHub release is published, which triggers the PyPI publish workflow.
