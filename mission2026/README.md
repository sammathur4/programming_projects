# Mission 2026

A personal habit / study / fitness / goals tracker that replaces the "Mission 2026"
Google Sheet. **Flutter** app (Android APK + iPhone + Web) talking to a
**Python/Django REST** backend on **MySQL**, plus a **WhatsApp daily check-in**
bot so people can report their day without installing anything.

```
mission2026/
├── server/                  Django + DRF + MySQL (PyMySQL)
│   ├── api/                 models, serializers, views, analytics, CSV importer
│   ├── vision_board/        the standalone HTML vision board (served at /vision-board/)
│   └── data/                the 6 Google Sheet CSV exports
├── mission_app/             Flutter app (android / ios / web)
│   └── build/web/           compiled web app — Django serves this at /
├── docs/ui_mockup/          clickable HTML design mockups + the design spec
├── run_server.sh            start the whole site (app + API) on one port
└── .venv/                   Python virtualenv
```

## Live site

Django serves **both** the API and the compiled Flutter web app, so the whole
thing lives on one origin — no CORS, no second server, no proxy.

```bash
./run_server.sh                 # http://localhost:8000/
```

| URL | What |
|---|---|
| `http://localhost:8000/` | the app |
| `http://localhost:8000/api/` | the REST API |
| `http://localhost:8000/admin/` | Django admin |
| `http://localhost:8000/vision-board/` | the HTML vision board |
| `http://localhost:8000/ui_mockup/web_mockup.html` | desktop design mockup |
| `http://<your-LAN-IP>:8000/` | open the same site from your phone |

After changing Flutter code, rebuild and just reload the page — the server picks
up the new build from disk, no restart needed:

```bash
cd mission_app && flutter build web --release
```

### UI rebuild status

The live app is being rebuilt to match `docs/ui_mockup/web_mockup.html`
pixel-for-pixel. Done so far:

- **Shell** — 236px sidebar with grouped nav (Direction / Insight / System), a
  60px header carrying the `193 · DAYS LEFT` countdown pill, and a 320px
  per-tab right rail. Below 1180px it switches to a Drawer + 5-tab bottom bar;
  below 1400px the rail folds away.
- **Today** — date bar + score ring, exactly-52px habit rows, and the
  note / study / fitness / goals side column.
- **Stats** — stat cards, a 14-day bar chart, per-habit 30-day bars, and a
  consistency heat map.

Remaining: Habits, Study, Fitness, Food, Goals, Notes, Vision, Settings.


## Features

**Habits** — daily toggles, streaks, 30/120-day heatmap, momentum score,
best/worst weekday, per-habit **per-day notes**, optional numeric target, and full
lifecycle: **add / edit / pause / resume / restart / soft-delete / restore**.

**Food** — MyFitnessPal-style diary: a searchable dish database seeded with 46
Indian + common dishes with real calories/macros, **four meal slots**
(Breakfast / Lunch / Dinner / Snack), a ring showing **calories remaining**, and
three macro bars against your daily targets (2100 kcal / 140P / 210C / 60F).
Macros are **snapshotted per entry** at log time, so editing a dish later never
rewrites what you already ate.

**Notes** — one feed for every note in the system, grouped by date with
**pinned** notes on top. Category chips (day / habit / fitness / food / goal /
idea) with live counts, plus a bottom-sheet editor.

**Study** — UPSC tracker (mode, AW, MCQs, hours, subject slots) plus a
playlist board with **Pending / In Progress / Done** columns and one-tap moves
between them; 60-day analytics (hours, answer writings, MCQs, target adherence).

**Fitness** — Legend-style **named training day modules** (Push / Pull / Legs /
Cardio) with a 7-day split strip that highlights today. Each module lists its
exercises (sets × reps × weight, or cardio distance/time) and a **derived muscle
map** that sums working sets per muscle — computed from the exercise list, never
stored, so it can't drift. Plus per-day structured workouts
(**exercise · sets · reps · weight · muscle**), cardio (**type · quantity · unit
· minutes**), and a body log (weight / calories / water / food / notes) with
weight trend + weekly rate.

**Goals** — full lifecycle (add / edit / **pause / resume / restart / complete /
soft-delete / restore**), start & target dates, **days elapsed / days left**,
habit-derived **effort analysis** ("how much work is done vs still needed"),
pace check, and dated **progress checkpoints**.

**Today** — compact, scroll-light dashboard: score hero ring + 14-day sparkline,
**streak-at-risk alert**, **focus pick** (lowest-momentum habit),
**burnout radar**, **recovery score**, then a 3-column habit grid and quick
study / fitness logging.

**Vision Board** — a tab that opens your standalone HTML vision board. Served by
the backend at `/vision-board/index.html` so it works on web and phones
(override the URL in Settings, including a `file://` path).

**Settings** — server URL, mission dates, nutrition targets, study targets,
WhatsApp check-in, notifications, and data/backup controls.

**Keep-going intelligence** (the anti-burnout layer) — momentum, burnout risk
with plain-English advice, recovery-after-a-miss rate, best weekday per habit,
"streak at risk", and goal effort attribution. All computed from your own logs.

## Data model (one per sheet tab, plus the new tabs)

| Sheet | Model | Notes |
|---|---|---|
| HabitBull | `Habit` + `HabitLog` | daily booleans, notes, values → Daily Score, streaks |
| Fitness | `FitnessDay` | body log + structured `exercises` / `cardio_items` JSON |
| — (new) | `WorkoutModule` | named training days (Push/Pull/Legs/Cardio), muscles derived |
| UPSC Tracker | `StudyDay` | up to 4 subject slots (JSON) + AW / MCQ / hours |
| Mission Objective | `Objective` + `GoalCheckpoint` | goals, dates, linked habits, checkpoints |
| Completed + Pending Subjects | `StudyResource` | playlist items, moved between tracks |
| — (new) | `Food` | dish database: serving + kcal / protein / carbs / fat |
| — (new) | `DiaryEntry` | one logged dish; macros snapshotted at log time |
| — (new) | `NutritionTarget` | daily calorie + macro goals (single row) |
| — (new) | `Note` | the Notes feed, tagged day / habit / fitness / food / goal / idea |
| (header cells) | `Setting` | targets: 1800 kcal, 75 kg, mode targets… |
| WhatsApp bot | `CheckinMember` + `DailyCheckin` | group check-ins synced from the bot |

All user-facing models support **soft delete** (`deleted_at`); history is kept
and rows can be restored. The importer uses `hard_delete` because the sheet is
the source of truth. **Diary macros are copied, not joined** — deliberate, so
history is immutable. **Module muscles are computed, not stored** — deliberate,
so the map can never disagree with the workout.

## Running the backend

```bash
./run_server.sh            # app + API on http://0.0.0.0:8000
```

DB credentials are in `~/Desktop/mysql_credentials.txt` (DB `mission2026`,
user `mission`). Django reads them from env with those as defaults, so it
works out of the box.

Re-import the sheet after editing the CSVs (idempotent):

```bash
cd server && ../.venv/bin/python manage.py import_csvs
```

Re-seed the dish database, workout modules and notes feed:

```bash
cd server && ../.venv/bin/python manage.py seed_food_notes_modules
cd server && ../.venv/bin/python manage.py seed_food_notes_modules --reset   # wipe first
```

Admin panel: `http://localhost:8000/admin/` (create a login with
`manage.py createsuperuser`).

## Running the app

The app finds the server automatically, and the server URL in **Settings** is
only an override. Defaults per platform:

| Platform | Default base URL |
|---|---|
| Web (deployed) | the page's own origin — Django serves the app *and* the API, so this works from any device |
| Web (`flutter run -d chrome`) | `http://localhost:8000` (the dev server serves the app on :5000, Django is on :8000) |
| Android emulator | `http://10.0.2.2:8000` (host loopback; detected by the emulator's 10.0.2.x address) |
| Android real phone | the built-in `mission` alias → the laptop's current LAN/tether IP |
| iOS simulator | `http://localhost:8000` |

**How the web build finds the API.** On load it probes, in order: a cached
winner, the URL saved in Settings, the page's origin, then localhost — and uses
the first that answers. If the saved URL is dead but another candidate works,
the saved URL is **cleared automatically**. That matters in practice: a phone
browser that once saved `localhost:8000` would otherwise be stuck showing
"Server unreachable" forever, with no way out.

`Settings → Server URL → Auto` clears the saved URL and re-detects.

```bash
export PATH="/home/saksham/development/flutter/bin:$PATH"
export ANDROID_HOME=/home/saksham/Android/Sdk

cd mission_app
flutter run -d chrome        # web
flutter run -d <device-id>   # phone / emulator (flutter devices)
```

Both machines must be on the same Wi-Fi for a real phone to reach the server.

> If the browser serves a stale build after a redeploy, hard-reload
> (Ctrl+Shift+R) — the Flutter service worker caches `main.dart.js`.

### Server URL aliases (`mission`)

Android has no DNS entry for the dev machine, so a bare name like `mission`
cannot resolve on a real phone. The app therefore maps friendly hostnames to a
real address in Dart, at request time — no DNS, no root, works over USB
tethering.

In **Settings → Server URL** you can type any of:

| You type | Resolves to |
|---|---|
| `mission` | `http://10.210.195.182:8000` |
| `mission:8000` | `http://10.210.195.182:8000` |
| `http://mission:8000/` | `http://10.210.195.182:8000` |
| `http://192.168.1.5:8000` | used as-is |

The alias target is `Api.hostIp` in `mission_app/lib/api.dart`. **If the
laptop's LAN/tether IP changes, update that constant and rebuild the APK.**
Check the current value with:

```bash
ip -4 -o addr show enx9e75d3f2b628 | awk '{print $4}'
```

## Mobile shell (what the APK shows)

The APK ships a focused phone shell; the web build keeps every tab. This is one
codebase — the flag is `kMobileShell = !kIsWeb` in `mission_app/lib/main.dart`.

| Build | Tabs |
|---|---|
| Web | Today, Habits, Study, Fitness, **Jaap**, Food, Goals, Notes, Stats, Timeline, Vision, Settings |
| APK | **Today · Fitness · Jaap · Timeline** (Settings pushes as a page) |

`kMobileTabIds` is the source of truth; `kMobileTabLabels` derives the visible
names from it, and `test/widget_test.dart` asserts against that list so the
tests cannot drift from the shell. Flip `kMobileShell` to `false` for the full
tab set in a native build (useful on a tablet).

## Offline mode & Sync

The app keeps working with no server. Every write is attempted normally; if the
server cannot be reached the request is stored in a local queue and the app
says so rather than losing the change.

- **Queue** — `mission_app/lib/offline.dart`. Persisted in `SharedPreferences`
  as `offline_queue_v1`, so queued work survives an app restart.
- **Writes only.** Reads always hit the server. An HTTP error (`4xx`/`5xx`)
  still throws — only *transport* failures are queued, so a bug can never turn
  into silent data loss.
- **Dedupe** — re-editing the same record (e.g. a habit/day) replaces the
  queued op instead of stacking, so the last state you chose is what uploads.
  Discrete events (drinks, diary entries) each keep their own op.
- **Sync** — pushes the queue in order, then refreshes from the server. It is
  available in two places: the cloud icon in the header (with a count badge)
  and **Settings → Sync**. The Sync screen lists exactly what is waiting.
- **Idempotent replay** — habit writes send an absolute `status`, never a
  relative `cycle`, so replaying a queued op hours later lands on the value the
  user chose instead of advancing the server's state again.

Manual verification of replay safety:

```bash
cd server
curl -s -X POST http://127.0.0.1:8000/api/habits/toggle/ \
  -H 'Content-Type: application/json' \
  -d '{"habit":12,"date":"2026-10-20","status":"done"}'   # repeat 3x
# the row stays "done" — no drift
```

## Building release artifacts

```bash
cd mission_app
flutter build web --release     # → build/web  (Django serves this at /)
flutter build apk --release     # → build/app/outputs/flutter-apk/app-release.apk
flutter build ios --release     # macOS + Xcode only — produces the .ipa
```

The web build is what `./run_server.sh` serves, so after `flutter build web` the
running site updates on the next page reload.

### iPhone note
The `ios/` project is generated and ready, but **iOS can only be compiled on
a Mac** with Xcode. On macOS: `open ios/Runner.xcworkspace`, set your signing
team, then `flutter build ipa --release`. Nothing app-side needs changing.

## API surface (`/api/…`)

```
GET    dashboard/                    today's score, at-risk streaks, focus, burnout
GET    overview/?date=YYYY-MM-DD     everything for one screen
GET    stats/                        streaks, momentum, weight, resources

GET/POST   habits/                   list / create
GET/PATCH/DELETE habits/{id}/        detail / edit / soft delete
POST   habits/{id}/{pause|resume|restart|restore|archive}/
POST   habits/toggle/  {habit, date, done?, value?, note?}
POST   habits/{id}/note/ {date, note}
GET    habits/heatmap/?days=120
GET    habit-logs/?from&to&habit&done_only

GET    fitness/?from&to&limit         GET/PATCH fitness/{date}/
GET    fitness/analytics/?days=30
POST   fitness/{date}/exercise/       DELETE ?index=N
POST   fitness/{date}/cardio/         DELETE ?index=N

GET    study/?from&to                 GET/PATCH study/{date}/
GET    study/analytics/?days=60
GET/POST resources/                   GET resources/{id}/  PATCH/DELETE
POST   resources/{id}/move/ {track: pending|in_progress|completed}

GET/POST   objectives/                GET/PATCH/DELETE objectives/{id}/
POST   objectives/{id}/{pause|resume|restart|complete|restore}/
POST   objectives/{id}/checkpoint/ {progress_pct, note, date}

GET    food/?q=&category=&limit=        search the dish database
POST   food/                            add a custom dish
PATCH/DELETE food/{id}/                 edit / soft delete a dish
GET    diary/?date=YYYY-MM-DD           day's entries, meals, totals vs targets
POST   diary/ {date, meal, food_id, quantity}    log a dish (macros snapshotted)
PATCH/DELETE diary/{id}/                change quantity / soft delete
GET/PATCH nutrition-targets/            daily calorie + macro goals

GET    notes/?tag=&from=&to=&q=         the Notes feed + per-tag counts
POST   notes/                           create a note
PATCH/DELETE notes/{id}/                edit (incl. pin) / soft delete
GET/POST day-note/ {date, note}         the Today screen's "Note for today"

GET/POST   workout-modules/             Legend-style named training days
PATCH/DELETE workout-modules/{id}/      edit / soft delete
GET    workout-schedule/                the 7-day split resolved for today

GET/POST   mission/checkins/          WhatsApp bot → app bridge
GET    mission/leaderboard/?days=30
GET    members/
GET    settings/

GET    jaap/                         the mantra library + counts
POST   jaap/tap/                     {mantra, date?, delta?} — one bead
GET    jaap/stats/?days=30           streaks, totals, per-mantra, series
GET/POST   jaap-mantras/              the chant library
PATCH/DELETE jaap-mantras/<pk>/      edit mala size, goal, name

GET    /vision-board/                 the HTML vision board + assets
GET    /                              the Flutter web app (SPA fallback to index.html)
```

### Jaap counter (mantra counter)

A tap-to-count mala ring, on its own tab in both the APK and the web app.

**Data model** — two tables:

```
JaapMantra   id · name · emoji · devanagari · transliteration
             category (naam|mantra|chalisa) · deity
             mala_size · daily_goal · color · is_active · sort_order

JaapLog      id · mantra FK · date · count · malas · duration_min
             notes · source (app|whatsapp|manual)
             unique_together (mantra, date)
```

One row per (mantra, date) — the day's total for that chant. It matches how
`FitnessDay` / `IntakeLog` already work, and it makes streaks and graphs fall
out of the same data.

**The bead count is the user's choice.** `mala_size` is the number of beads in
one round; 108 is the tradition, not a rule, and the ring is drawn from it.
Changing it re-derives the cached mala counts.

**Taps write on every tap.** `POST /api/jaap/tap/ {mantra, date, delta}` is
the hot path: it increments atomically and returns the new count, the
completed malas, and `mala_completed` — true only on the tap that lands on the
last bead, which is when the app rings the bell. Replaying a tap is safe
because it is a delta, not an absolute count.

**Offline:** the count moves locally first, then the tap is written. Each tap
gets a unique queue id, so the offline queue never collapses a hundred taps
into one.

**API**

```
GET    jaap/                      library + today's counts + summary
GET    jaap/?from&to              a range
GET    jaap/stats/?days=30        streaks, totals, per-mantra, daily series
POST   jaap/tap/                  {mantra, date?, delta?} — the hot path
GET/POST jaap-mantras/            the chant library
PATCH/DELETE jaap-mantras/<pk>/   edit mala size, goal, name…
```

**Seeding the library**

```bash
python manage.py seed_jaap          # add missing mantras
python manage.py seed_jaap --reset  # also reset the seeded rows
```

The command is idempotent and revives a soft-deleted mantra rather than
failing on the unique name.

**The bell** — `assets/sounds/bell.wav` is *generated*, not recorded:
`python3 tool/make_bell.py assets/sounds/bell.wav` synthesises a struck-bell
spectrum (inharmonic partials, fast attack, exponential decay). Played through
`audioplayers`; every failure is swallowed, because a missing sound must never
break the counter.

### Habit statuses

A habit can be in one of four states for a given day:

| Status | Meaning | Counts as done? | Breaks a streak? |
|---|---|---|---|
| `pending` | not started | no | yes (as before) |
| `in_progress` | started, not finished | no | yes |
| `done` | finished | yes | no |
| `skipped` | deliberately rested | no | no — neutral, like a rest day |

`skipped` stays the only streak-neutral state; `in_progress` is "not finished",
so it behaves like `pending`.

Set one explicitly (the API rejects anything else with a 400 — a typo must
never silently rewrite a habit):

```
POST /api/habits/toggle/ {habit, date, status}
  status ∈ pending | in_progress | done | skipped
```

- **App (Today):** tap the status button cycles the quick path
  (pending → done → skipped → pending). **Long-press** it for a picker with all
  four states.
- **App (habit detail / habits list):** four status buttons.
- **WhatsApp bot:** reply `done`, `in progress`, `pending` or `missed` (also
  `started`/`doing`/`wip` and `not yet`/`later`). Or
  `!mission in_progress <habit>` / `!mission pending <habit>`.

The bot's `pending` answer **clears** a habit that was previously marked done —
that is why `DailyCheckin` carries an explicit `pending` list rather than
leaving the habit out of the payload.

Writes are unauthenticated for local/LAN use. To lock it down, set the
`MISSION_API_KEY` env var on the server and send an `X-API-Key` header from
the client (the WhatsApp bot already supports this).

## WhatsApp daily check-in (two-way sync)

Users report their day in a group; no app install needed. Implemented in the
[`whatsapp_bot`](https://github.com/BangaloreNewbies/whatsapp_bot) repo.

- **07:00** — bot posts one Yes/No poll per habit (`✅ Done` / `❌ Missed`).
- During the day — vote updates are collected automatically.
- **22:00 / 23:55** — interim and final recap with a per-person progress bar.
- Votes are pushed to this backend via `POST /api/mission/checkins/`, so they
  show up in the app and on the leaderboard.

Bot env vars: `MISSION_GROUP_ID`, `MISSION_API_URL`, `MISSION_API_KEY` (optional).
In-group commands: `!mission`, `!mission done <habit>`, `!mission habits`.

## Notes on the imported data

- HabitBull dates are day+month only (`28-Sep`); the importer infers a
  monotonic year sequence across the campaign (29/09/2026 → 01/05/2027).
- The sheet's month-only study rows that roll past the end date land in 2027 —
  harmless, they're historical rows.
- Daily Score in the app is recomputed as `done/total`; the sheet's own
  (occasionally negative) score formula isn't reproduced.
- Imported goals inherit the campaign start/end dates, and free-text timelines
  ("May 2027", "2027") are parsed into a target date so days-left works.
