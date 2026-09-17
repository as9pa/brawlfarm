# Phase 10b design: opt-in auto-upgrade

Supersedes section 3 of `docs/superpowers/specs/2026-09-13-phase-9-design.md` (lines 273 to 398).
Everything that spec decided still stands unless this document says otherwise. What changed is that
a real recording of the brawler detail screen now exists, and it contradicts the colour model the
phase 9 spec guessed at.

**Correction, 2026-09-16, from the second recording.** Tapping the UPGRADE panel on the detail
screen does **not** upgrade. It opens a confirmation dialog, and the currency is charged on the
dialog's confirm button, not on the first tap. The state machine below gains a CONFIRM step between
TAP and VERIFY, and the feature now makes two fixed taps, not one.

**Source frames.** The observe session recorded 2026-09-16 under the calibration recordings folder
for Pie64. Three recordings:

- `20260916-212232`. Frames 0049 (roster), 0051 to 0055 (Nori, power 1, upgrade ready, cost 20
  power points plus 20 coins), 0076 to 0078 (Maple Barley, MAX LEVEL).
- `20260916-215108`, recorded after the first pass. Frame 0012 is Nori at POWER 1; 0007 to 0011 are
  the confirmation dialog "UPGRADE TO POWER LEVEL 2?" at cost 20 plus 20; 0013 is POWER 2 with the
  sparkle animation; 0014 to 0016 are the same dialog for level 3 at cost 30 plus 35; 0017 to 0020
  are POWER 3. Balances ran 4639/26041, then 4619/26021, then 4589/25986.
- `20260916-215207`. Frames 0004 to 0009 are the shop, with a Collector's Pin priced 39 gems on a
  green button with a green gem icon. This is the positive gem sample the first draft asked for,
  still half size.

**Every pixel value in this document is provisional.** The recording is 800x450, exactly half the
locked 1600x900 working resolution. Every coordinate below was measured at 800x450 and doubled.
Doubling a half-size measurement carries a plus or minus 2 px error at full size before any
rounding in the recorder, and JPEG at half size destroys the thin colour edges the chip bands
depend on. Nothing here goes into `brawlfarm/core/config.py` until it is re-measured on session 2,
a full-size 1600x900 observe recording, and confirmed in a live pass.

## Goal

Default off. When on, once at the end of a session, on the stop path, open the farm brawler detail
screen and tap the coin-priced power Upgrade if the power points and coins are positively read as
sufficient. Verify then act, never gems, at most one upgrade per session.

## What already exists

`brawlfarm/core/upgrade_gate.py` ships `Reading` and `should_upgrade` as pure code, with the truth
table in `tests/test_upgrade_gate.py`. That is task 2 of the phase 9 task list, done. Nothing else
of feature 3 exists: no `upgrade.py`, no `UPGRADE_*` config block, no `FarmSection`, no panel
control, no rail amendment.

## Dependency on phase 10a

The way in is the by-name locate half of `brawlers.select_brawler_by_name_checked`. Frame 0049
shows the roster grid no longer matches what that function was calibrated against: it scrolls
horizontally, with the column at the right edge cut off. The roster recalibration ships in
`docs/superpowers/plans/2026-09-16-phase-10a-roster-and-quests.md`. **This plan does not start its
navigation task until phase 10a has merged and its locate path has passed a live run.** Building
the upgrade state machine on an uncalibrated locate would produce a tap on the wrong brawler's
detail screen, which is the one failure this feature cannot tolerate.

One correction for phase 10a's benefit: the fill order is column-major. Frame 0074 (sort "Rarity")
reads SHELLY, NITA, COLT down column 1, BULL, BROCK, EL PRIMO down column 2, BARLEY, POCO, ROSA down
column 3, then JESSIE, DYNAMIKE, 8-BIT in the cut-off fourth column: the game's rarity release order,
top to bottom, then the next column. Frame 0049 (sort "Least Trophies") cannot decide the fill
order: all nine visible cards sit at 0 trophies, the 1, 10 and 11 badges are the highest rank
reached, so their order is a tie-break. Frame 0049 also shows a SEARCH control in the top bar at
about half-size (645, 20), full size (1290, 40), with the magnifier at about half-size (603, 20). It
may be a cheaper way in than scrolling, at the cost of a new adb text-input primitive. Phase 10a owns
that call.

## The rail amendment, proposed verbatim

`CONTRIBUTING.md` line 9 currently reads:

> - The never-tap set: ACCEPT on a team invite, GET or Upgrade, EQUIP NOW, any shop buy button,
>   the pass VAULT, anything priced in gems. No blind taps in the shop.

Replace that single bullet with these two:

> - The never-tap set: ACCEPT on a team invite, GET or Upgrade, EQUIP NOW, any shop buy button,
>   the pass VAULT, anything priced in gems. No blind taps in the shop.
> - One narrow exception, added 2026-09-16 with the owner's approval: the power Upgrade panel on
>   the farm brawler's own detail screen may be tapped, at a fixed config coordinate, once per
>   session, on the stop path, only while the `auto_upgrade` setting is on, and only after the gate
>   in `brawlfarm/core/upgrade_gate.py` has positively read a power-point cost and a coin cost from
>   the screen and confirmed the price slot is coin gold and carries no gem colour. The first tap
>   only opens a confirmation dialog and charges nothing. The exception covers exactly two fixed
>   coordinates and no others: `config.UPGRADE_TAP`, the UPGRADE panel on the detail screen, and
>   `config.UPGRADE_CONFIRM_TAP`, the confirm button in the dialog that first tap opens, which may
>   be tapped only after the dialog title has been read as UPGRADE TO POWER LEVEL and the dialog's
>   two costs have been read and found equal to the costs read on the detail screen. Anything the
>   gate or either read cannot resolve is a refusal, and a refusal at the dialog taps
>   `config.UPGRADE_DIALOG_CLOSE`, the dialog's X, and nothing else. This exception covers no other
>   Upgrade, confirm or GET button anywhere in the game, and nothing priced in gems under any
>   circumstances.

Also amend the comment above `BRAWLER_SELECT_BUTTON` in `brawlfarm/core/config.py` line 459, which
today says the bottom-right UPGRADE button is never tapped, to point at the new `UPGRADE_*` block
and at the exception above.

This amendment lands in the same pull request as the first tapping code. It needs an explicit owner
go in chat before that pull request opens. Shipping the code without the amendment leaves the
repository self-contradictory and the rail unenforceable.

## Colour correction to the phase 9 spec

The phase 9 spec specified "the gem-purple fraction is near zero" as one of two independent guards.
That is wrong, and shipping it would make the feature refuse every screen it will ever see.

What the frames actually show:

- The power-point currency renders **pink and purple**: a magenta lightning bolt in a pink chip. It
  is the left cost chip in the UPGRADE panel, by design, on every upgradeable brawler.
- Coins render **gold**.
- Gems in this game render **green**.

So a purple guard fires on the power-point chip on every upgradeable screen and the gate returns
False forever. The guard also has to be pointed at the right box: the stats panel directly above
the UPGRADE panel carries three **green** upgrade arrows (half size, around x 745 to 757, y 232 to
322 in frame 0051), so a green-fraction check over any region overlapping the stats panel
false-positives on those arrows.

The fix, in two parts:

1. **Rename the field.** `Reading.purple_chip` becomes `Reading.gem_chip`, keeping the default of
   `True` and the fail-closed sense: a gem colour was seen in the coin slot, so refuse. The name is
   the load-bearing part. A future calibrator reading `purple_chip` would derive a purple band and
   break the feature. `should_upgrade`, its docstring and `tests/test_upgrade_gate.py` change with
   it. No behaviour changes.
2. **Confine and re-derive the bands.** `gold_chip` is the coin-gold fraction inside
   `UPGRADE_COIN_COST_REGION` only. `gem_chip` is the gem-green fraction inside
   `UPGRADE_COIN_COST_REGION` and `UPGRADE_PP_COST_REGION` only, never the stats panel. Both HSV
   bands are derived from session 2 frames, not from this recording.

Frames 0051 to 0055 show no gem-priced element anywhere on the detail screen. The shop frames in
`20260916-215207` now supply the positive sample: the Collector's Pin at 39 gems, a green gem icon
on a green button, plus a green gem balance in that screen's top bar.

That sample makes a third hazard concrete, and it is the reason the gem check must be cropped
tightly. **The upgrade dialog's own confirm button is green**, in the same family as the shop's
gem button. A gem-green fraction taken over a whole button, or over a cost chip loosely cropped so
it catches button background, fires on the one screen this feature is built to act on. So both
dialog cost regions are cropped to the dark capsule interior of the chip, inside the green button,
and the band is validated against frames 0007 and 0004 together: it must clear on the shop gem icon
and stay near zero on the dialog's cost chips.

One more caveat the shop frame exposes: the top bar carries different currencies on different
screens. The detail screen (0051) shows power points and coins only; the shop (0006) shows four
balances including gems, at different x. `UPGRADE_PP_BALANCE_REGION` and
`UPGRADE_COIN_BALANCE_REGION` are therefore only valid on the brawler detail screen, which is why
READ runs after the ON_DETAIL name check and never before it.

## Components

New: `brawlfarm/core/upgrade.py`, `tests/test_upgrade.py`.

Modified: `brawlfarm/core/upgrade_gate.py` (the `gem_chip` rename), `brawlfarm/core/config.py` (an
`UPGRADE_*` block plus two `BRAWL_*` flags), `brawlfarm/core/controller.py` (one call in `stop()`
before the `CLOSE_GAME_ON_STOP` block at line 1321), `brawlfarm/settings.py` (a `FarmSection`),
`brawlfarm/api/settings_routes.py`, `brawlfarm/web/src/settings/Behavior.tsx`,
`brawlfarm/api/feed.py`, `CONTRIBUTING.md`, `docs/calibration.md`.

## State machine

States: AT_MENU, OPEN_BRAWLERS, LOCATE, ON_DETAIL, READ, GATE, TAP, CONFIRM, VERIFY, EXIT.

Every transition re-classifies with `states.classify`. Any state that is not the expected one,
including UNKNOWN, jumps straight to EXIT, which is the existing tap-only `_exit_to_menu` path in
`brawlfarm/core/brawlers.py`. No retries beyond the existing nav retry budgets. The whole run is
wrapped so any exception logs `upgrade_error` and exits to the menu. An upgrade failure never
blocks the stop.

ON_DETAIL additionally verifies the brawler name by OCR against the farm brawler's name, reusing
the `BRAWLER_NAME_REGION` check that `select_brawler_by_name_checked` already performs. A name
mismatch is an EXIT, not a retry. EXIT always runs, including after a successful upgrade.

**The dialog must not be allowed to reach the farm loop.** `states.classify` labels all eight
dialog frames in `20260916-215108` as `popup`, so the generic popup closer would dismiss it. That
is harmless only because TAP, CONFIRM and VERIFY run inside one uninterrupted `run_once` call on
the stop path, with no farm-loop tick between them. `run_once` must never yield, sleep into a tick,
or return between TAP and CONFIRM. If it ever needs to, the dialog has to be closed first with
`UPGRADE_DIALOG_CLOSE`.

## READ

Five reads and two colour checks, all on one screencap taken in ON_DETAIL. All regions are
`(x, y, w, h)` at 1600x900, doubled from 800x450, provisional.

| Constant | Provisional value | What it holds | Derived from |
| --- | --- | --- | --- |
| `UPGRADE_PP_BALANCE_REGION` | `(1150, 6, 140, 50)` | top bar power-point balance, 4639 in 0051 | 0051, half (575, 3, 70, 25) |
| `UPGRADE_COIN_BALANCE_REGION` | `(1320, 6, 150, 50)` | top bar coin balance, 26041 | 0051, half (660, 3, 75, 25) |
| `UPGRADE_POWER_LEVEL_REGION` | `(1130, 374, 60, 52)` | the POWER chip level digit, 1 in 0051, 11 in 0076 | 0051, half (565, 187, 30, 26) |
| `UPGRADE_PP_COST_REGION` | `(1188, 726, 112, 50)` | the pink left cost chip, 20 | 0051, half (594, 363, 56, 25) |
| `UPGRADE_COIN_COST_REGION` | `(1368, 726, 112, 50)` | the gold right cost chip, 20 | 0051, half (684, 363, 56, 25) |
| `UPGRADE_HEADER_REGION` | `(1250, 680, 180, 36)` | the word UPGRADE | 0051, half (625, 340, 90, 18) |
| `UPGRADE_MAX_LEVEL_REGION` | `(1150, 696, 370, 60)` | the words MAX LEVEL! when present | 0076, half (575, 348, 185, 30) |
| `UPGRADE_TAP` | `(1336, 744)` | first tap, centre of the UPGRADE panel, opens the dialog | 0051, half (668, 372) |
| `UPGRADE_DIALOG_TITLE_REGION` | `(480, 78, 640, 56)` | the dialog title, UPGRADE TO POWER LEVEL 2? | 215108/0007, half (240, 39, 320, 28) |
| `UPGRADE_DIALOG_PP_COST_REGION` | `(1208, 792, 104, 44)` | the dialog's pink cost chip, 20 in 0007, 30 in 0014 | 215108/0007, half (604, 396, 52, 22) |
| `UPGRADE_DIALOG_COIN_COST_REGION` | `(1320, 792, 112, 44)` | the dialog's gold cost chip, 20 in 0007, 35 in 0014 | 215108/0007, half (660, 396, 56, 22) |
| `UPGRADE_CONFIRM_TAP` | `(1326, 810)` | second tap, the green confirm button. This is the tap that spends | 215108/0007, half (663, 405) |
| `UPGRADE_DIALOG_CLOSE` | `(1402, 106)` | the dialog X, the only refusal exit from the dialog | 215108/0007, half (701, 53) |

Supporting geometry, for reference only, never read: the POWER chip sits at half (578, 200), full
(1156, 400), with MAX 11 to its right and the segmented level bar beneath; the stats panel spans
half x 585 to 765, y 225 to 333, full (1170, 450, 360, 216); the UPGRADE panel spans half x 585 to
757, y 338 to 390, full (1170, 676, 344, 104); SELECT sits at half (106, 409), which doubles to
(212, 818) and confirms the shipped `BRAWLER_SELECT_BUTTON = (213, 818)` to within 1 px.

The reads map onto `Reading` as follows:

- `power_points` from `UPGRADE_PP_BALANCE_REGION`.
- `power_points_needed` from `UPGRADE_PP_COST_REGION`.
- `coins` from `UPGRADE_COIN_BALANCE_REGION`.
- `cost` from `UPGRADE_COIN_COST_REGION`.
- `gold_chip` from the coin-gold HSV fraction in `UPGRADE_COIN_COST_REGION`.
- `gem_chip` from the gem-green HSV fraction in `UPGRADE_COIN_COST_REGION` and
  `UPGRADE_PP_COST_REGION`, True when either clears the band.

Two structural preconditions run before any of that, both cheap, both refusals:

- `UPGRADE_MAX_LEVEL_REGION` must **not** read as MAX LEVEL. Frame 0076 shows that at max level the
  UPGRADE panel is gone entirely and replaced by that text, so this is the clean max-level check.
- `UPGRADE_HEADER_REGION` must read as UPGRADE. If the panel header is not there, the panel is not
  there, and every cost region is reading whatever replaced it.

Any read that does not parse to a non-negative integer stays `None`, and `should_upgrade` already
turns a `None` into a refusal.

### Unaffordable screens

The owner has no short-on-coins and no short-on-power-points account state, so neither was recorded
and neither can be recorded on demand. The game renders an unaffordable cost in red text.

This spec deliberately does **not** require red-text detection. The gate is a refusal for anything
not positively read as affordable from the numbers: `should_upgrade` already refuses unless
`points >= needed` and `coins - cost >= coin_floor`, both computed from four independently OCR'd
integers, and refuses on any unparsed value. Red text presents the same fact the numbers carry.

Red-text detection is specified as a **later, additive refusal signal**: a `red_cost` field on
`Reading`, defaulting to `True` if it is ever added, ANDed into the refusal, calibrated only if and
when a frame showing it exists. Do not add the field before that frame exists. An uncalibrated band
defaulting to True refuses everything, and defaulting to False is a guard that has never once been
observed to fire.

## GATE

Unchanged from `should_upgrade`, plus the `gem_chip` rename and the two structural preconditions
above. It passes only if: `auto_upgrade` is on, no upgrade has been done this session, the coin
slot is gold and carries no gem colour, all four numbers parsed to non-negative integers, `needed`
and `cost` are both positive, `points >= needed`, and `coins - cost >= coin_floor`. Anything
ambiguous is a no. The gate is pure: it takes a `Reading` and returns a bool, and it never reads a
screen or taps anything.

## TAP

One `adb.tap(*config.UPGRADE_TAP)`. This tap spends nothing: it opens the confirmation dialog.
The coordinate is a fixed config constant, never derived from an OCR box, so a mis-read moves no
tap. A rail test greps `upgrade.py` for any literal coordinate pair and fails on anything that is
not a `config.UPGRADE_*` reference.

## CONFIRM

The step that spends. Sleep the nav settle, screencap once, and require **all three**:

- `UPGRADE_DIALOG_TITLE_REGION` reads `UPGRADE TO POWER LEVEL`, case-insensitive, prefix match so
  the trailing level number and question mark do not matter.
- `UPGRADE_DIALOG_PP_COST_REGION` parses to an integer **equal** to the `power_points_needed`
  already read on the detail screen.
- `UPGRADE_DIALOG_COIN_COST_REGION` parses to an integer **equal** to the `cost` already read on
  the detail screen.

The two cost equalities are the point of this step. They are an independent second read of the
price, on a different screen, from different regions, and they are what makes a detail-screen
misread cost nothing: a wrong price read there cannot agree with the dialog, so the run refuses.
Frames 0007 and 0014 show the pair varying together (20 and 20 at level 2, 30 and 35 at level 3),
so an equality check is real and not a constant.

All three hold: `adb.tap(*config.UPGRADE_CONFIRM_TAP)`, then VERIFY. Anything else, including an
unparsed read or a title that is not there: log `upgrade_dialog_refused` with what was read,
`adb.tap(*config.UPGRADE_DIALOG_CLOSE)`, set the once-per-session flag, EXIT. Never tap the
confirm button twice, and never tap anywhere in the dialog except those two fixed coordinates.

## VERIFY

The post-confirm frames are now recorded: 0013 shows POWER 2 under a sparkle animation and 0017 to
0020 show POWER 3 settled. VERIFY is specified on two facts that must hold on any successful
upgrade and that are read from regions this spec already defines. Note that 0013 carries an
animation over the POWER chip, so the settle must outlast it; that is what session 2 fixes.

After the confirm tap, sleep the existing post-tap settle, re-screencap once, and require **both**:

- the integer in `UPGRADE_POWER_LEVEL_REGION` is exactly the pre-tap level plus one, and
- the integer in `UPGRADE_PP_BALANCE_REGION` is strictly less than the pre-tap balance.

Both true: log `upgrade_ok` with the brawler name, the new power level and the coin cost, set the
once-per-session flag, EXIT. Anything else, including an unparsed read: log `upgrade_unverified`
with both pre and post values, set the once-per-session flag anyway, EXIT. **Do not tap again.**
The no-retap rule from the phase 9 spec is absolute. A second tap on an unverified screen is how a
mis-navigated run buys something.

Session 2 must contain the post-tap frames so the settle delay and the power-level region can be
confirmed. Until it does, the settle delay is provisional at the existing nav settle.

## Settings and API

`brawlfarm/settings.py` gains, alongside `BehaviorSection`:

```python
class FarmSection(_Section):
    auto_upgrade: bool = False
    coin_floor: int = Field(default=0, ge=0)
```

Wired into `AppSettings` as `farm`, and into `worker_env` as `BRAWL_AUTO_UPGRADE` via `_flag` and
`BRAWL_COIN_FLOOR` as `str(f.coin_floor)`. `config.py` reads them next to the other `BRAWL_*`
flags, in the style of line 221:

```python
AUTO_UPGRADE = os.environ.get("BRAWL_AUTO_UPGRADE", "0") == "1"
COIN_FLOOR = max(0, int(os.environ.get("BRAWL_COIN_FLOOR", "0") or 0))
```

Note the default direction. `AUTO_UPGRADE` defaults **off**, so it tests for `== "1"`, not
`!= "0"`. A worker started without the env var must not upgrade.

Panel: two controls in Settings under Behavior, in `brawlfarm/web/src/settings/Behavior.tsx`. A
toggle labelled "Auto-upgrade the farm brawler" and a number input labelled "Keep at least this
many coins", the number input disabled while the toggle is off, with helper copy saying it spends
coins and power points only, never gems, and at most once per session.

Feed: `upgrade_ok` and `upgrade_unverified` classify in `brawlfarm/api/feed.py`. `upgrade_ok` is a
normal event; `upgrade_unverified` goes in ERRORS and `upgrade_error` lands there through the
existing `_error` suffix path.

## Safety-rail impact

The largest rail surface of the three phase 9 features. Beyond the `CONTRIBUTING.md` amendment:

- Both tap coordinates are fixed config values, never OCR-derived boxes, and they are the only two
  coordinates this feature ever taps besides the dialog X.
- The dialog costs must equal the detail-screen costs, which is a second independent read of the
  price before any money moves.
- The dialog's confirm button is green, the same family as the shop's gem button, so the gem check
  is cropped to the chip capsule interiors and validated against both a gem frame and a dialog
  frame.
- The gem guard and the gold guard are two independent colour checks over the same region that must
  both agree, and both are confined to the cost chips, never the stats panel with its green arrows.
- The once-per-session counter lives on the controller instance, not on disk, so a crash cannot
  resume mid-upgrade.
- The whole path is skipped when `auto_upgrade` is off, with a test that asserts zero taps.
- Every `UPGRADE_*` value ships in a dedicated calibration pull request that lists every changed
  value and carries the frames and the scores, per `CONTRIBUTING.md`.

## Test plan

Unit, on the pure gate: the existing truth table in `tests/test_upgrade_gate.py`, renamed to
`gem_chip`.

`tests/test_upgrade.py`, against a fake adb that records taps and serves canned frames:

- Flag off: zero taps, and the state machine never leaves AT_MENU.
- Happy path on frame 0051 upscaled to 1600x900: exactly one tap, at `config.UPGRADE_TAP`.
- MAX LEVEL on frame 0076 upscaled to 1600x900: zero taps, refusal logged.
- Missing UPGRADE header: zero taps.
- `coin_floor` above `coins - cost`: zero taps.
- Each of the four numbers unreadable in turn: zero taps.
- `gem_chip` True: zero taps.
- Already done this session: zero taps.
- Dialog title absent: exactly one tap plus the X tap, `upgrade_dialog_refused` logged, no confirm
  tap.
- Dialog costs disagreeing with the detail-screen costs, each of the two in turn: one tap plus the
  X tap, no confirm tap.
- Dialog cost unparsed: one tap plus the X tap, no confirm tap.
- Happy path taps exactly twice, `config.UPGRADE_TAP` then `config.UPGRADE_CONFIRM_TAP`, in that
  order, and never `config.UPGRADE_DIALOG_CLOSE`.
- VERIFY failure: exactly two taps, `upgrade_unverified` logged, no third tap.
- The gem band measured on shop frame 0004 clears, and on dialog frame 0007 stays near zero.
- UNKNOWN screen injected at each of OPEN_BRAWLERS, LOCATE, ON_DETAIL, READ: zero taps, exits to
  the menu.
- Name mismatch on the detail screen: zero taps.
- Rail test: no literal coordinate pair in `upgrade.py`.

Settings round trip through the API. Panel test for the disabled number input.

Live pass on Pie64, with the owner watching: `auto_upgrade` on and `coin_floor` set high enough
that the gate refuses, confirmed in the feed; then `coin_floor` lowered and exactly one real
upgrade on a cheap brawler.

## What session 2 must contain

A full-size 1600x900 observe recording, on the brawler detail screen, containing:

1. The farm brawler with enough power points and coins, so the UPGRADE panel is live, held still
   for several frames so the JPEG settles.
2. The full two-tap sequence: the detail screen, the first tap on UPGRADE, several frames of the
   confirmation dialog held still, the confirm tap, and the frames after it including the sparkle
   animation, so both settle delays, the four dialog regions and the power-level region can be
   fixed. Also capture a dialog that is closed with the X, so the refusal exit is evidenced.
3. A max-level brawler, to re-measure `UPGRADE_MAX_LEVEL_REGION`.
4. A gem-priced element at full size. The half-size shop frames in `20260916-215207` already give
   the positive sample, but the band must be re-derived at 1600x900 and checked against both the
   green stats arrows on the detail screen and the green confirm button in the dialog.
5. If the account ever reaches a state where a cost renders red, that frame, for the later
   `red_cost` field. Not a blocker.

Items 1 through 4 block the calibration pull request. Nothing in the `UPGRADE_*` block can be fixed
without them.
