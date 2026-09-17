# Phase 10a design: roster recalibration and quest-aware brawler choice

Date: 2026-09-16. Supersedes feature 2 of docs/superpowers/specs/2026-09-13-phase-9-design.md (lines
160 to 272), which assumed a vertical quest list, a swipe down and one brawler name per quest. Both
are wrong on the live screens. Source: observe recording Pie64/20260916-212232.

## Provenance and the doubling rule

Every frame is 800x450, half of the locked 1600x900. Every coordinate below was measured half size
and doubled, so all are PROVISIONAL, plus or minus 8 px full size. Nothing ships until re-measured
on a full-size session (session 2, checklist at the end) and confirmed in a live pass on Pie64.
Below, h marks a half-size measurement. Every quests and roster frame is labeled unknown by
states.py: there is no quests state and no brawlers state. Frames 0058-0073 are an account switch.

## Goal

1. phase-10/roster-recal (calibration PR): the game rebuilt the roster as a horizontally scrolling
   3-row grid. Four constants land on the wrong control and the select-by-name scroll moves the
   wrong axis.
2. phase-10/quest-pick (feature PR, depends on 1): pick the farm brawler so the session also clears
   an active quest, read once per session inside the startup quests visit (phase 9 approach B).

## What the frames show

Quests: a 3-row grid scrolling horizontally; sections left to right are the mega card, Daily quests,
Season quests, each with its own header and timer. REROLL QUEST top right at (715,86)h. Titles wrap
over two and sometimes three centered lines; progress sits bottom left of the card and the reward
bottom right, on a lower line. Wording seen: WIN 5 BATTLES WITH NITA, PAM OR MINA / WITH PAM, LOLA
OR MEEPLE / WITH SPIKE, EDGAR OR JAE-YONG / WITH MORTIS, DARRYL OR BUZZ / WITH LEON, SURGE OR FINX /
WITH GALE, BYRON OR MINA; DEAL 100000 POINTS OF DAMAGE WITH BONNIE, MEEPLE OR FINX; DEAL 160000
POINTS OF DAMAGE with no target; WIN 5 BATTLES IN RANKED; WIN 5 BATTLES IN GEM GRAB OR ANY SHOWDOWN;
DEFEAT 24 ENEMIES; DEFEAT 15 ENEMIES IN BRAWL BALL OR ANY SHOWDOWN; PLAY 6 BATTLES; PLAY 5 MATCHES
IN A TEAM; USE "PLAY AGAIN" 10 TIMES.

Corrections to the working notes: frame 0030 reads WITH BONNIE, MEEPLE OR FINX, not "BONNIE, MEEG,
FINX"; names can carry a hyphen (JAE-YONG), which norm_name already collapses; and non-quest cards
share the grid, a gold BRAWL PASS EXCLUSIVE banner and a BRAWL PASS EXP card at 8/8.

Roster: 3 rows, horizontal scroll, a 4th column cut at the right edge. Top bar left to right: back
arrow, sort label, quest clipboard toggle, heart toggle, SEARCH, HOME; the BRAWLERS 105/107 header
sits below the bar. A red shop offer panel holds x below about 270 full with a live buy control:
never-tap under the existing shop rule, and no swipe endpoint may land there.

The grid is COLUMN-MAJOR: frame 0074, sorted by Rarity, reads SHELLY, NITA, COLT down column 1,
BULL, BROCK, EL PRIMO down column 2, BARLEY, POCO, ROSA down column 3 and JESSIE, DYNAMIKE, 8-BIT
in the cut-off column 4, which is the game's rarity release order top to bottom then across. Frame
0049 cannot decide the question: every visible card shows 0 trophies at bottom left and the 1, 10,
11 badges are the highest rank reached, so their order under the Least Trophies sort is a tie-break
only. So an index maps to a column, never a row, and the scroll axis is horizontal.

Detail (0051, NORI): BRAWLER_SELECT_BUTTON (213,818) still hits SELECT, centre (220,816). The name
sits x 120-280, y 180-230, inside BRAWLER_NAME_REGION with 20 px of bottom margin; a long name is
unverified. UPGRADE with Gem and Coin prices is bottom right and stays never-tap.

## Data flow

Quest read, inside the existing startup visit: open QUESTS, confirm with _on_quests_screen, activate
the mega quest first when one is available (it adds a card the read should see), do not exit between
the two. Then vision.read_lines_boxes(screen, region=QUEST_LIST_REGION), which returns
(text, conf, (cx, cy)) and gives CENTRES ONLY, never rectangles, so every grouping rule works on
centres. questpick.group_cards buckets lines by cy into three row bands and into a title or a
progress line, then clusters a row's title lines by cx: a line joins the running cluster while it is
within QUEST_CARD_X_TOL of the cluster mean, else it starts a new card. Title lines join with one
space in cy order; a card's progress is the progress token nearest its cluster mean in cx within
half a card pitch. Drop cards whose cluster mean cx is nearer than QUEST_EDGE_MARGIN_X to a region
edge: those are cut off and truncated. Swipe right to left in the lane, read again, stop when the
page text repeats or after QUEST_SWEEP_MAX swipes, deduplicate by joined title text, exit through
the existing _exit_to_menu.

Parsing: "WIN [n] BATTLES? WITH [names]" and "DEAL [n] (POINTS OF )?DAMAGE WITH [names]". The names
part splits on commas and on the word OR into a candidate list. A damage quest with no WITH is
dropped. A candidate in CLASSES keeps KIND_CLASS, which still resolves to None; mode quests still
resolve to None. Quest gains candidates, a tuple of normalized names in screen order; target stays,
redefined as a property returning candidates[0], so every existing test and caller keeps working. A
progress of N/M with N equal to M counts as claimed and is dropped, alongside the existing CLAIMED,
COLLECTED, COMPLETE and COMPLETED words; that also drops the BRAWL PASS EXP 8/8 card.

Resolving, resolve(quests, owned, trophies=None, prefer=None): return prefer when it is an owned
candidate; else the owned candidate with the lowest trophies when trophies is given, ties by
candidate order; else the first owned candidate in candidate order; else None, and the existing plan
or lowest-trophy path runs unchanged. The trophies come from a new farmplan.owned_trophy_map(api)
returning a dict keyed by questpick.norm_name(b["name"]) valued b.get("trophies") or 0, built from
api.get_player()["brawlers"]. farmplan.resolve_target is left untouched, because
tests/test_controller_reselect.py monkeypatches it with a three-tuple lambda and it drops the
trophies at farmplan.py:548. Cost: one extra get_player call per session when quest_aware is on.

Selecting: sorted by Name, names increase left to right across columns under the column-major fill. So OCR the visible card names; when the target is absent, compare it with the
alphabetically smallest and largest visible name, swipe right when it sorts before the smallest and
left when it sorts after the largest, bounded by BRAWLER_SELECT_MAX_SWIPES. No index arithmetic, no
pitch multiplication. The RECALIB_TRIPWIRE behaviour on a zero-name sweep is unchanged.

Frame 0049 also shows a SEARCH control, magnifier at (603,20)h and label at (645,20)h. Typing a
name into it would replace scrolling outright, but it needs an adb text-input primitive the project
does not have. Noted as a later alternative, deliberately not a task in this plan.

## Config block: provisional values and how each was derived

Quests, all new, all full size, doubled from frame 0020:

    QUEST_LIST_REGION = (0, 220, 1600, 850)   # row 1 card top y=112h to row 3 card bottom y=418h
    QUEST_ROW_PITCH = 213                     # card tops 112h, 218h, 325h; mean pitch 106.5h
    QUEST_TITLE_BAND0 = (256, 364)            # row 1 title lines span y 128h to 182h, 3-line case
    QUEST_PROGRESS_BAND0 = (376, 424)         # row 1 progress centre y=197h, 12h either side
    QUEST_CARD_PITCH_X = 457                  # card left edges 160h, 390h, 635h; pitch 228.5h
    QUEST_CARD_X_TOL = 150                    # one card's title lines vary under 40 full in cx
    QUEST_EDGE_MARGIN_X = 180                 # drops cut columns: 0020 col1 cx=96, col4 cx=1490
    QUEST_SWIPE_Y = 490                       # row 2 card mid-band, below any BRAWL PASS banner
    QUEST_SWIPE_X_START = 1300                # clear of REROLL (1430,172) and HOME (1525,47)
    QUEST_SWIPE_X_END = 700                   # clear of QUESTS_MEGA_CARD (312,540) by about 190 px
    QUEST_SWIPE_MS = 600                      # so long it can never register as a tap
    QUEST_SWEEP_MAX = 8                       # about 4 cards per page, 3 sections; bail-out budget
    QUEST_REROLL_BUTTON = (1430, 172)         # never-tap landmark, measured (715,86)h

Roster, revisions of existing values, doubled from frame 0049:

    BRAWLERS_HEADER_REGION = (260, 80, 620, 140)   # was (0,0,900,80); header x135-285h y47-60h
    BRAWLER_SORT_LABEL     = (710, 40)             # was (1010,42); label at (355,20)h
    BRAWLER_QUEST_TOGGLE   = (956, 40)             # was (1215,55); clipboard at (478,20)h
    BRAWLER_HEART_TOGGLE   = (1106, 40)            # was (1360,55); heart at (553,20)h
    BRAWLER_SEARCH_FIELD   = (1290, 40)            # new never-tap landmark; label (645,20)h
    BRAWLER_FIRST_CARD     = (456, 244)            # was (330,300); NORI card centre (228,122)h
    BRAWLER_GRID_COL0_X    = 456                   # replaces BRAWLER_GRID_COLS_X
    BRAWLER_GRID_COL_W     = 374                   # card centres 228h, 413h, 601h; pitch 187h
    BRAWLER_GRID_ROWS_Y    = (244, 488, 732)       # replaces ROW0_Y and ROW_H; 122h, 244h, 366h
    BRAWLER_GRID_REGION    = (270, 130, 1600, 850) # was (150,80,1430,880); past the offer panel
    BRAWLER_NAME_LABEL_DX  = 64                    # label is bottom RIGHT in the card, (258,154)h
    BRAWLER_NAME_LABEL_DY  = 64                    # was 63 below centre; magnitude unchanged
    BRAWLER_SCROLL_Y       = 488                   # row 2 centre; the lane is horizontal now
    BRAWLER_SCROLL_X_RIGHT = 1400                  # swipe-left start, swipe-right end
    BRAWLER_SCROLL_X_LEFT  = 500                   # swipe-left end; clear of the offer panel
    BRAWLER_SCROLL_MS      = 600
    BRAWLER_SORT_DROPDOWN_REGION                   # UNVERIFIED: the dropdown never opened
    BRAWLER_TOGGLE_ORANGE_LO and _HI               # UNVERIFIED: no toggle was ever ON

Unchanged and confirmed on a frame: BRAWLER_SELECT_BUTTON (213,818), BRAWLER_NAME_REGION
(0,0,520,250), QUESTS_CLOSE_BUTTON (55,52), HOME_BUTTON (1525,47) (measured (1540,34), same icon).
Deleted with the vertical loop: BRAWLER_SCROLL_BOTTOM_Y, BRAWLER_SCROLL_TOP_Y, BRAWLER_SCROLL_MAX_PX,
BRAWLER_SCROLL_MIN_PX, BRAWLER_SCROLL_FACTOR, BRAWLER_GRID_TARGET_Y.

## Safety-rail impact

- REROLL QUEST joins the never-tap set in CONTRIBUTING.md. A reroll destroys a quest the owner may
  want and cannot be undone. QUEST_REROLL_BUTTON exists only so a test can assert nothing goes near.
- The roster shop offer panel at x below 270 is never-tap under the existing shop rule. Every roster
  swipe endpoint stays at x 500 or greater.
- Both new swipes are read-only gestures on read-only screens, 600 ms over more than 500 px, so
  neither can degrade into a tap.
- Verify then act is unchanged: the read runs only after _on_quests_screen passes, and selection
  still verifies the name on the detail screen before tapping SELECT.
- A zero-line quests read behaves like the RECALIB_TRIPWIRE case: log, alert, fall back, never guess.
- No change to the 1600x900 assertion, one worker per instance, kill by recorded PID, or no-shell.

## Test plan

parse: the six brawler-quest strings, including JAE-YONG, give the right candidate tuples; DEAL
160000 POINTS OF DAMAGE with no WITH is dropped; DEFEAT, PLAY, USE "PLAY AGAIN" and BRAWL PASS EXP
are dropped; 0/5 keeps a quest, 8/8 and 5/5 drop it; mangled OCR (W1TH, BATTLE5) still parses;
norm_name still agrees with brawlers._norm. group_cards: line lists with frame 0020 centres group
into the right cards, join three-line titles in order, attach the right progress token, drop both
edge columns. resolve: prefers the plan target; picks the lowest-trophy owned candidate; falls back
to candidate order without trophies; None when nothing is owned; None for class and mode quests.
brawlers: the scan swipes left when the target sorts after the largest visible name and right when
before the smallest, stops at BRAWLER_SELECT_MAX_SWIPES, and a zero-name sweep sets the tripwire.
controller: quest_aware off is byte-identical to today and never calls owned_trophy_map; on with a
resolved name passes it to select_brawler_by_name_checked; on with nothing resolved runs the old
chain. Rails: no module taps QUEST_REROLL_BUTTON and every swipe endpoint sits outside a 120 px box
around REROLL, HOME, the back arrow and the mega card.

Gate, per CLAUDE.md: pnpm typecheck, pnpm test, uv run pytest, uv run ruff check ., uv run ruff
format --check ., uv run python tools/scrub_check.py printing 0 hit(s), and a live pass on Pie64 for
anything touching the farm loop.

## Session 2 recording checklist

Record in observe mode at the locked 1600x900, in one continuous session:

- [ ] Brawlers screen from the menu, untouched, two frames.
- [ ] Open the sort dropdown, hold two frames.
- [ ] Pick "Name", hold the sorted grid two frames.
- [ ] Scroll the grid slowly left to right, end to end, pausing every screenful.
- [ ] Scroll back to the left end.
- [ ] Quest clipboard toggle ON two frames, OFF two frames.
- [ ] Heart toggle ON two frames, OFF two frames.
- [ ] Set the sort back to "Least Trophies".
- [ ] Open a long-named brawler (EL PRIMO), hold two frames, go back.
- [ ] Open a short-named brawler, hold two frames, go back.
- [ ] Menu, then QUESTS, scroll left to right end to end, pausing every screenful.
- [ ] Scroll back to the left end, leave through the back arrow.
