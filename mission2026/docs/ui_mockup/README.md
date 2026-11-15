# Mission 2026 — UI design

This folder is the **design source of truth** for the Flutter app. Nothing in
`mission_app/lib/screens/` should be restyled without matching what is here first.

## Files

| File | What it is |
|---|---|
| `mockup.html` | **Phone** prototype (390×806 frames). One self-contained file, no build step. |
| `web_mockup.html` | **Desktop web** prototype (sidebar + right rail, multi-column). |
| `shot_*.png` | Phone screenshots — Today / Habits / Study / Fitness / Food / Goals / Notes / Stats / Vision. |
| `web_*.png` | Desktop screenshots at 1600×1400 — same nine screens plus Settings. |
| `README.md` | This spec — the numbers both ports must hit. |

Open either prototype:

```bash
xdg-open docs/ui_mockup/mockup.html          # phone
xdg-open docs/ui_mockup/web_mockup.html      # web
```

Both are also served alongside the web build:

- <http://localhost:8080/ui_mockup/mockup.html>
- <http://localhost:8080/ui_mockup/web_mockup.html>

## Phone vs web — the two are deliberately different

A 390px phone layout stretched to 1600px looks broken, so the web version keeps
the **same tokens and the same 52px habit row** but changes the structure:

| | Phone (`mockup.html`) | Web (`web_mockup.html`) |
|---|---|---|
| Navigation | Bottom nav, **9 tabs** | **Persistent left sidebar**, grouped (main / Direction / Insight / System) |
| Score + intel | A strip inside Today | **Sticky right rail**, always visible while scrolling |
| Days remaining | **Compact header chip** — `193 · DAYS LEFT · until 1 May 2027` | **Header countdown pill**, same numbers |
| Today | Single column | **Two columns** — habits left, note/study/fitness/goals right |
| Habits | Grid table + list below | **Master–detail split** — habit list left, selected habit's stats + full grid right |
| Study | Stacked cards with move buttons | **Data table** with a header row, columns: priority / subject / resource / progress / move-to |
| Fitness | Flat exercise list | **Named day modules** (Push / Pull / Legs / Cardio) with a derived muscle map |
| Food | **Ring + 4 meal cards + dish list** | **MyFitnessPal-style** — ring, macros, meal slots, searchable dish table |
| Notes | **Chips + grouped feed** | Grouped feed with category chips and a counts rail |
| Settings | Not present | **Nine-section control panel** with its own sub-nav |
| Goals | Single column, paused collapsed | **Responsive card grid** (`auto-fit, minmax(340px,1fr)`) — 2–3 across, nothing collapsed |
| Stats | Stacked | **Grid**; the consistency map spans the full width |
| Breakpoints | n/a | Rail drops at **1180px**, sidebar becomes a drawer at **820px** |

There is **no search field** — it was cut deliberately. The data set is ~10 habits,
13 goals and 53 resources, all reachable in one or two clicks from the sidebar and
the Habits master list. A search box would be decoration.

The **days-remaining countdown lives in the header**, not the rail. It is the one
number that frames every other one, so it stays visible on every screen rather
than scrolling away in a side panel. Measured with no overlap between the page
title and the countdown from 1024px up to 1600px.

The rail is hidden entirely on Vision, which is a full-width hero — the shell
switches to two columns there. Same on **Settings**, which is its own
sub-nav + content split and does not need a habit rail.

The rail is not always the habit score. It **changes to match the tab**: Food
shows calories-remaining plus macro bars, Fitness shows weekly muscle coverage,
Notes shows the category breakdown and the pinned note. A rail that always shows
the same habit ring on a food screen would be dead weight.

Everything else is shared on purpose: the palette, the type scale, the 52px row,
the semantic colours, and the hold that **habit data is 10 booleans/day** — so
the trend is a "% of due habits done" bar chart and a consistency map, not a
painted heatmap that would imply a density you do not have.


## Where the design came from

The layout is **ported from `habit_tracker/` (Momentum)** — a working habit
tracker already in this repo — rather than invented. That layout was chosen
because it is the pattern HabitBull and Momentum both use, and it solves the
exact complaints raised about the previous Flutter UI.

| Problem reported | How the new design fixes it |
|---|---|
| 3-col grid looks cramped | Habit cards are **full-width rows**: emoji chip → name + tag → meta → one big round check on the right. |
| Too much scrolling | Reference viewport is **658px of content height**. Every screen was measured against it. Today went **1267px → 996px**; Goals **1391px → 1000px**; Stats **949px → 822px**. |
| Colours/gradients feel off | No decorative gradient heroes. Colour is **semantic only** — see the palette table below. |
| Cards too big / too much padding | Cards are `11px 12px` padding, `9px` gaps. Habit rows are a fixed **52px** tall. |
| Dense text, poor typography | One scale only (see below). Name and meta are single-line with ellipsis. |
| Doesn't feel like a real habit tracker | Habits tab is the **HabitBull grid table** with a sticky name column and one square per day. |

## Palette — colour means something

| Token | Hex | Meaning |
|---|---|---|
| `bg` | `#0b0f1a` | App background |
| `panel` | `#121828` | Card fill (top of gradient) |
| `panel-2` | `#182036` | Inputs, secondary buttons |
| `line` | `#232c45` | Borders, dividers |
| `text` | `#e7ecf7` | Primary text |
| `muted` | `#8b96b5` | Labels, meta |
| `accent` | `#22c55e` | Done, primary action, active nav |
| `accent-2` | `#3b82f6` | Info, study, links |
| `warn` | `#f59e0b` | Streaks, at-risk, paused |
| `danger` | `#ef4444` | Missed, delete, burnout |
| `violet` | `#a855f7` | Goals, notes |

Each habit also carries its **own colour** (`--hc`), used for its emoji chip,
its check button when done, its grid squares, and its progress bar. That is what
makes the Habits grid readable.

## Type scale (do not add sizes outside this)

| Role | Size / weight |
|---|---|
| Page / section title | 11px / 800, uppercase, 1.1px letter-spacing |
| Card title | 14px / 800 |
| Habit name | 13.5px / 700 |
| Body / meta | 11–12px / 400–600 |
| Micro label | 8.5–9.5px / 800, uppercase |

## Layout contract — the numbers to hit

Reference device is a **390 × 806** phone. The scrollable region is **658px**.

| Screen | Content height | Fits first screen |
|---|---|---|
| Today | 996px | date bar, score strip, **9 of 10 habit rows** |
| Habits | 1160px | 14-day grid for all 10 habits, no scroll inside the card |
| Study | 682px | analytics strip + all 3 tabs + 3 rows — essentially one screen |
| Fitness | 1082px | hero, mode card, **all 4 exercises** |
| Food | 1260px | ring + macros + **3 of 4 meal slots** |
| Goals | 1000px | health card + **4 of 5 active goals** |
| Notes | 1527px | pinned block + chips + **3 day groups** |
| Stats | 822px | 4 metric cards, 14-day bars, heatmap |
| Vision | 658px | fits exactly, no scroll |

The **header countdown chip** is present on every phone screen and is the twin of
the web header pill: `193 · DAYS LEFT · until 1 May 2027`. It is verified not to
overlap the brand at 390px and to stay inside the app bar's padding.

**Hard rule: a Today habit row is exactly 52px, enforced with `height`, not
`min-height`.** A note or a progress bar must never grow a row — the middle
column is a fixed 48px clip box. Ten rows plus the header must be reachable with
at most one short flick. If a change makes a row taller, it is wrong.

Verified automatically: all 7 tabs render, all 10 Today rows measure 52px, 9 are
above the fold, all 140 grid cells exist, and every interaction mutates state.

## Screen-by-screen

### Today
- **Date bar** — `‹ ›` day steppers, centred date, and a **score ring** (conic
  gradient) showing % done. Ring colour: ≥100% green, ≥50% blue, else amber.
- **Score strip** — one row: a 94px score tile (`7/10 habits done` + mini bar) and
  three intel tiles: 🔥 **At risk** (streak about to break), 🎯 **Next** (lowest
  momentum), 🫀 **Load** (burnout/recovery). This replaced two stacked cards.
- **Habit rows** — sorted un-done first. Check habits get the round ✓ button;
  count habits (`5L Water`, `UPSC 6 hrs`) get `− value +`, a target and a
  progress bar. A habit with a note shows a 📝 line.
- **Day note** — one textarea at the bottom.
- **Quick log** — Study hours and Fitness in two half-width tiles with inline
  `−` / `+` / `Log`.

### Habits
- **Toolbar** — range selector (14/30/60 days), category filter, `＋ Habit`.
- **The grid table** — sticky habit column on the left; one square per day.
  Square states: **solid habit colour** = done, **45% colour** = partial,
  **empty slate** = missed, **dashed outline** = rest day, **white ring** =
  today. Squares are tappable to backfill any past day.
- **Manage list** — per habit: streak, best streak, 30-day %, a progress bar and
  a `⋮` menu with Edit / Pause / Restart streak / Delete.
  **Delete is always a soft delete** — history is preserved and the habit moves
  to the paused/archived group.

### Study
- **Analytics strip** — hours/60d, answer writings, MCQs, target-hit %, in-progress count.
- **Three tabs** — Pending · In Progress · Done, each with a count.
- Every row has one-tap **move buttons** between the lists, so a subject is
  never stuck in the wrong bucket. In-progress rows show a progress bar.

### Fitness
- **Hero** — current weight, kg lost, weekly delta, calories hit, sets today.
- **Mode / Status** segmented controls — WFO/WFH/Holiday, Done/Pending/Skipped.
- **Weekly split strip** — seven day cards naming the module scheduled for each
  day (Push / Pull / Legs / Cardio / Rest), with today highlighted.
- **Workout day modules (Legend-style)** — a named module per training day.
  Each module card carries its own colour and shows:
  - an **exercise list** — name · `sets × reps @ kg` · muscle group, or for
    cardio `quantity unit · minutes`;
  - a **muscle map**, one bar per muscle group with the total sets it receives.
- **The muscle map is derived from the exercise list**, never hand-written. Add,
  edit or delete an exercise and the bars change with it, so the map can never
  disagree with the workout. This is enforced by a test.
- **Cardio** is a first-class exercise type inside a module, not a separate
  screen — type + quantity + minutes.
- **Body log** — weight, body fat, waist, steps.

### Food  *(web only)*
- **Calorie ring** — SVG donut showing **calories remaining**, not consumed.
  Green under 85%, amber to 100%, red when over. The centre number flips between
  "remaining" and "over".
- **Macro bars** — protein / carbs / fat against daily goals, each its own colour.
- **Four meal slots** — Breakfast, Lunch, Dinner, Snack. Each is a card with its
  own kcal subtotal and an `＋ Add` button.
- **Diary rows** — food · qty · kcal · P · C · F · remove, in a fixed column grid.
- **Dish database** — ~46 Indian staples and common foods with **per-serving**
  calories and macros (roti, dal, paneer, biryani, dosa, idli, oats, eggs…).
  Searchable server-side in the real app.
- **Arithmetic is real.** Every diary row's kcal equals `per-serving kcal × qty`,
  and the ring matches the sum of the rows — both asserted by the test harness.

### Notes  *(web only)*
One place for **every note in the system**, regardless of where it was written.
- **Category chips** — All / Day / Habits / Fitness / Food / Goals / Ideas, each
  with a live count. Filtering actually filters.
- **Grouped by date**, newest first, with sticky day headers that read Today /
  Yesterday / weekday+date.
- Each note shows a **category pill**, the thing it refers to, its text, and
  pin / edit / delete actions (delete is a soft delete).
- A **pinned block** sits at the top of the unfiltered view.

### Settings  *(web only)*
A nine-section control panel with a sticky sub-nav: General · Habits & streaks ·
Fitness & workouts · Food & calories · Study · WhatsApp check-in · Notifications ·
Data & backup · About.
- **General** — units, date format, first day of week, currency, mission
  start/end (these drive the header countdown), theme, accent, dense mode.
- **Habits & streaks** — new-habit default state, perfect-day target, partial-day
  streak rules, rest days, streak freeze, grid range.
- **Fitness** — edit the workout modules, tracked muscles, warm-up-set counting,
  body-fat/waist fields, weigh-in reminder.
- **Food** — calorie and macro goals (the same numbers the ring uses), meal slots,
  custom dishes.
- **WhatsApp check-in** — enable, morning post time, night summary time, group
  name, reply sync. This is the settings surface for the bot feature.
- **Data & backup** — export/import, CSV export, and a **Deleted items** section
  that exposes soft-deleted habits and goals with restore, plus empty-trash.
- **About** — version, backend status, days remaining, keyboard shortcuts.

### Goals
- **Health card** — plain-language pace summary ("Pace is healthy… two goals are
  behind pace").
- **Goal cards** — title, target, a progress bar whose colour is *pace-aware*
  (green = at/above expected, amber = close, rose = behind), then a foot row of
  `%`, `pace N%`, `⏳ Nd in`, `Nd left`, and a **timeline bar with an elapsed
  marker**.
- Linked goals get a pace note telling you exactly how much more effort is
  needed.
- **Paused and Archived collapse into one 40px row each** — that alone removed
  ~390px of scroll.

### Stats
- Four metric cards in one row (Today %, This week, Top streak, Total check-ins).
- Last-14-days bar chart, a 6-month **consistency heatmap**, per-habit 30-day
  bars with streaks, and personal records.

### Vision
- A violet hero with **Open Vision Board ↗**, the hosted source URL (override in
  Settings), and a short stack of anti-burnout reminders.

## Interactions to keep

`S.done[id]` toggles on tap · count habits `−`/`+` · date `‹ ›` steps back and
forward (forward disabled on today) · grid squares backfill any day · Study rows
move between lists · `⋮` menus expose Edit / Pause / Resume / Restart / Delete ·
Notes chips filter the feed · Settings sub-nav switches sections · the header
gear opens Settings from anywhere.

## New data the mockup implies

The design introduces four new concepts the backend does not have yet:

| Concept | Shape |
|---|---|
| **Workout module** | `name`, `color`, `days[]`, `exercises[]` |
| **Exercise** | `name`, `sets`, `reps`, `kg`, `muscle`, `cardio?`, `qty?`, `unit?`, `min?` |
| **Food** | `name`, `serving`, `kcal`, `protein`, `carbs`, `fat` |
| **Diary entry** | `date`, `meal`, `food`, `qty`, `kcal`, `p`, `c`, `f` |
| **Note** | `date`, `tag` (day/habit/fitness/food/goal/idea), `ref`, `text`, `pinned` |

Two rules worth carrying into the models:

1. **Muscle totals are computed, not stored.** `moduleMuscles()` sums the sets of
   the module's exercises. Storing a separate muscle list would let it drift.
2. **Diary macros are snapshotted.** A row keeps its own kcal/macros at the time
   of logging, so editing a dish later does not rewrite history.

## Porting to Flutter

The prototype is deliberately plain CSS so the mapping is 1:1:

| Prototype | Flutter |
|---|---|
| `.card` | `AppCard` in `lib/theme.dart` |
| `.habit-card` (52px) | a fixed-height `SizedBox`/`ConstrainedBox` row widget |
| `.pill` / `.tag` | `Pill` |
| `.bar` / `.mini-progress` | `ProgressBar` |
| `.ring` | `CustomPaint` conic gradient |
| `.hgrid` | `Table` inside horizontal `SingleChildScrollView` |
| `.tabs` / `.seg` | `SegmentedButton` or custom |
| `.strip` | `Row` of `Expanded` tiles |
| `.modgrid` / `.mod` | `Wrap` or `GridView` of module cards |
| `.musc-row` | `Row`: label + `ProgressBar` + count |
| `.macro-ring` | `CustomPaint` donut (reuse the Today score ring) |
| `.foodrow` | fixed-column `Row`, tabular figures |
| `.note` / `.notegroup` | `ListView` with sticky date headers (`SliverStickyHeader`) |
| `.setgrid` / `.setnav` | `Row`: narrow rail + `Expanded` list, or a `Drawer` on phone |
| `.toggle` | `Switch` |

Before committing a Flutter change, re-check the row height and the fold count
against the table above.

---

## Pixel-parity rebuild (Flutter)

The web mockup is the **authoritative visual spec**; the Flutter app is being
rebuilt screen-by-screen to match it, starting with Today.

### Shell

| Mockup | Flutter |
|---|---|
| `.shell` grid `236px | 1fr | 320px` | `Row`: `_Sidebar` (236) + `Expanded` main + `_Rail` (320) |
| `.side` / `.side.collapsed` | `_Sidebar` — width `236` / `64`, toggled by the ☰ button |
| `.navsec` group titles | `DIRECTION` / `INSIGHT` / `SYSTEM` headers in the sidebar list |
| `.navbtn` / `.navbtn.on` | `_navBtn` — 3px green left bar + `--panel-3` fill when active |
| `.streakbox` | the sidebar footer "Longest streak" tile |
| `.header` (60px) | `AppBar(toolbarHeight: 60)` |
| `.countdown` | `_Countdown` — `193 · DAYS LEFT · until 1 May 2027` violet pill |
| `.rail` | `_Rail`, 320px, content chosen per tab |
| `.no-rail` | `MissionTab.rail == false` (Vision, Settings) |

Breakpoints live in `lib/responsive.dart`:

* `< 1180px` — no sidebar; a `Drawer` + 5-tab `NavigationBar` instead
* `< 1400px` — no right rail; rail content folds into the main column
* `< 980px` — two-column views stack

### Tokens

`AppColors` mirrors the mockup's `:root` exactly:

```
bg #0b0f1a  surface #121828  surface2 #182036  surface3 #1e2845
border #232c45  track #1d2540
text #e7ecf7  dim #8b96b5  faint #5d7086
emerald #22c55e  blue #3b82f6  danger #ef4444  amber #f59e0b  violet #a855f7
radius 14px  sidebar 236px  rail 320px  header 60px
```

Pill text tints used by the mockup: green `#86efac`, blue `#93c5fd`,
amber `#fcd34d`, rose `#fca5a5`, violet `#d8b4fe`.

### Rebuilt so far

* **Today** (`lib/screens/today.dart`) — date bar + score ring, 52px habit rows
  with a fixed 48px clip box, note/study/fitness/goals side column. Two columns
  at ≥980px, stacked below.
* **Shell** (`lib/main.dart`) — sidebar, header with countdown, per-tab rail,
  mobile Drawer + bottom bar.
* **Stats** (`lib/screens/stats.dart`) — 4 stat cards, 14-day bar chart,
  per-habit 30-day bars, consistency heat map from `habits/heatmap/`.

### New endpoints added for the rebuild

| Endpoint | Purpose |
|---|---|
| `GET/POST /api/day-note/` | the "Note for today" card; stored as a `Note` with `tag="day"`, `ref=<ISO date>` |
| `overview/` now returns `day_note` | so Today loads the note in one round trip |

### Verification

Every tab is swept in headless Chrome at **430×900** (bottom nav) and
**1600×1000** (sidebar), clicking each destination and collecting
`Runtime.exceptionThrown` + console errors. Both viewports pass with **0 app
errors** across all 10 destinations. `flutter analyze` is clean and all widget
tests pass, including one that asserts no `RenderFlex` overflow with a fully
populated Today screen.

