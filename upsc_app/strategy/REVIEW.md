# REVIEW — PRD v1.3 · TECH_PLAN v1.0 · strategy.md

| Field | Value |
|---|---|
| Date | 26 October 2026 |
| Scope | `PRD.md` (1,681 lines) · `TECH_PLAN.md` (434) · `strategy.md` (1,360) |
| Method | Read all three; verified every claim against `backend/`, `frontend/` and `db.sqlite3` |
| Verdict | Analysis is strong. **The build plan is 3–4× the product.** Ship the habit loop this week, not in 8 sessions. |

**Short version**

1. The three docs contradict each other in 6 places. Two of them would build the wrong feature (§1).
2. Four spec bugs would ship broken behaviour — including one that silently re-dates your daily streak (§2).
3. Almost every friction point is *input the design demands from you*, and the biggest one isn't in the PRD at all: **getting handwritten paper from your phone into the app** (§3.1).
4. The plan builds 19 screens and 17 modules. The product needs **4 screens and 6 modules** (§4, §6).
5. `strategy.md`'s actual mechanism — "one theme, many papers" — has no home in the app. That should be the *one* content feature you build (§5).

---

## 0. Reality check (measured today, not estimated)

| Fact | Value |
|---|---|
| Questions | **2,771** = 1,400 Prelims + 1,371 Mains (`essay` 88, gs1 225, gs2 220, gs3 220, gs4 177, soc1 218, soc2 223) |
| Papers in DB | 7 — **no English paper** |
| Prelims `section` spellings | **58**; top ones: Current Affairs 186, Environment 184, Geography 156, Economics 88, Polity & Governance 80, Economy 71, Polity 68 |
| Attempts / responses | **22 / 22** (last response **19 Sep 2026**) |
| Notes / bookmarks / reviews | 9 / 2 / 2 |
| `App.jsx` | 3,216 lines; 9 CSS files, 9,572 lines, 2 of them 0 bytes |
| Mains rows missing marks / word limit | **0 / 0** (that data is complete; only 88 rows lack `syllabus_tags`) |

Two consequences:

- **The question bank is the asset; the attempt history is not.** 22 rows. Schema changes are free. Every "preserve backward compatibility" clause in the PRD and tech plan is protecting nothing — delete the frontend and rebuild the six real pages instead of keeping 3,216 lines alive behind a new shell.
- **22 attempts in a month is the whole diagnosis.** The app doesn't open (302 login) — the PRD already got this right in defect D01. But it also means usage data can't tell you what to cut, so cut on reasoning. Nothing else should be built before the app opens and one question can be answered in under 30 seconds.

---

## 1. Contradictions between the docs (fix before any code)

| # | Where | The conflict | Resolve |
|---|---|---|---|
| 1 | PRD §13.7 is correct (`DailyChallenge(date, track)`, `unique(date, track)`) but TECH_PLAN still says *"Based on PRD.md v1.2"* and specifies `DailyChallenge(date unique, question_key)` in Phase 1 | The tech plan is one PRD version behind and builds a **single-question** daily. Build from the tech plan and you silently lose the confirmed Prelims+Mains+Essay set | Tech plan must be corrected before Phase 1; PRD needs no change here |
| 2 | PRD §2 *"Keep the timed Prelims test engine — Confirmed"* and §8.1 nav/§8.2 routes/§10.6–10.9/§3.3 metric vs PRD §16 *"Tests (parked)"* and §21 item 7 *"Tests are parked"* | Tests are simultaneously confirmed, specified in 4 page specs and 4 routes, and parked — **inside the same document** | Delete the test routes, specs and metric from the PRD; keep the park |
| 3 | PRD §8.2 *"Routing rule: real paths with query parameters"* vs TECH_PLAN §1 decision *"keep hash URLs"* | Two routing models | Hash + query params. Zero deps, no server rewrite; PRD is wrong here |
| 4 | PRD §16 (5 phases: 0–4) vs TECH_PLAN §2 (9 phases) | Two different build orders | REVIEW §6 is the order |
| 5 | strategy.md L28/L42 *"1,563 questions… covering English"* vs DB 2,771 / 7 papers / no English | Stale count feeding a strategy built on frequency | Correct to 2,771 = 1,400 + 1,371 |
| 6 | PRD §7.1 *"an upload that finishes after midnight counts for the date it was submitted"* vs §13.3 *"a response dated that local day"* | Undefined: does the 11:55pm answer that finishes at 12:05am count today or tomorrow? | Completion date = the row's `local_date`, written once at creation. No exceptions |

---

## 2. Spec bugs that would ship wrong behaviour

| # | Bug | Why it bites | Fix |
|---|---|---|---|
| **B1** | **TECH_PLAN** Phase 1 model: `DailyChallenge(date unique, question_key)` | Contradicts PRD §13.7, which is already correct. Building from the tech plan gives one question per day instead of three | `date + track` unique; `track ∈ {prelims, mains, essay}` |
| **B2** | `AttemptResponse.answered_at = auto_now=True` (`models.py:251`) | **Every save re-dates the response.** Daily completion is defined as "a response dated that local day", so editing a note or re-submitting moves a completion to today and rewrites history | `default=timezone.now` + new `local_date` (date, indexed), set once on create |
| **B3** | Six streak counters: track × {prelims, mains, essay} + tier × {bronze, silver, gold} (PRD §7.1) | Bronze is *"≥ 1 track"* → **bronze streak == the daily streak**. Silver and gold nest inside it. It is 3 numbers wearing 6 hats | Show **one streak + longest + gold-day count**. "12 days · best 21 · 4 gold" |
| **B4** | Gold = all 3 tracks = **a full essay every single day** (PRD §7.1) | 88 essay PYQs, 90–120 min each. Gold is unreachable, and PRD §17 now concedes it (*"gold is a bonus, never a requirement"*) while §3.3 still requires **40% of days gold** and a **7-day gold streak**. The document argues with itself, and the top tier of the tier system is dead decoration | Essay track accepts a **one-page plan/outline** photo (10 min). Same upload flow, one line of copy, gold becomes earnable — then §3.3 and §17 agree |
| **B5** | `pick_daily` (PRD §7.1 vs Appendix B) | The prose version and the Python version differ, and both seed `pool[seed % len(pool)]` with a pool that is filtered by *mutable* attempt history — so the "deterministic" seed guarantees nothing. It's only stable because the row is persisted, which makes the seed decorative | Pool = eligible questions only; exclude the last 30 daily picks; `index = hash(date, track) % len(pool)`. Persist the row. Done |
| **B6** | 60-day exclusion for Essay (PRD §7.1) | Pool is 88; the exclusion relaxes almost every day. It's decorative | Drop it for Essay, say so |
| **B7** | `POST /api/daily/start/` creates a separate daily attempt (PRD §13.3, TECH_PLAN Phase 1.3) | A second path to something the practice flow already does. Two code paths, two bug surfaces, identical outcome | Delete the endpoint. Answering uses the normal attempt flow with `mode="daily"` |
| **B8** | `LearnerAccount.current_streak / longest_streak` cache, updated in `submit_attempt` (`views.py:1304`) | Already wrong: it increments on **any** practice submit. Keeping it as a cache means "recompute on profile read" = a write during a GET, plus a permanent drift risk the tech plan itself lists | **Delete both columns.** Compute from `DailyChallenge` + responses (~365 rows, one indexed query). Delete the drift class, not the symptom |
| **B9** | `Progress` model (`models.py:179`) — per-node counters | Third copy of derived state (after responses and streaks), unused by any current page | Delete it. Status/accuracy/coverage is one `GROUP BY` over 22 responses |
| **B10** | Mains upload caps: 10 MB/file but **50 MB total** (PRD §7.4) | Phone photos are 3–6 MB; a 4-page photographed answer can legitimately hit the total cap and get rejected at the worst moment | 20 MB/file, 150 MB total — or compress on the client. Never reject a correct answer because of a JPEG |
| **B11** | §13.1 *"preserve existing keys where the UI already consumes them"*, TECH_PLAN *"keep untouched pages wired behind the shell"* | Protects 3,216 lines of `App.jsx` and an unused frontend. You will rewrite every page you care about anyway | Delete both clauses |

---

## 3. Friction audit — where your input actually goes

The PRD optimises screens. Friction is **steps per daily action**. Ranked by cost:

### 3.1 Paper → browser: 4 steps outside the app (the biggest hole in the PRD)

Mains is upload-only. The answer is handwritten on paper. The photos are on your phone. The PRD says bind to `127.0.0.1` (§14.4). So the real flow is:

> photograph → open WhatsApp/email → send to self → open laptop → download → find file → upload

**Four off-app steps for the single most important daily action.** The PRD's upload spec assumes a file picker on a laptop with the pages already there. They won't be.

Fix, native, zero dependencies:

1. Serve on the LAN (`0.0.0.0:8000`, trusted home network), open the app on the phone.
2. `<input type="file" accept="image/*" capture="environment">` — the OS opens the rear camera directly.
3. Photo uploads straight into the vault.

This one attribute decides whether the Mains track ever happens. It costs more to *keep* the 127.0.0.1 restriction than to drop it.

### 3.2 The submit confirmation on upload

Current spec: pick files → see previews → optional note → press **Submit** → progress → success. Defect #9 calls the *existing* auto-submit a P0 bug — it isn't. The bug is that auto-submit fires on the **first** file, so page 1 uploads while you're still adding pages 2–4.

Fix: upload each file as it's picked (background), and the answer exists the moment file 1 lands. "Add more" = pick more. **No submit button in the happy path.** This deletes the disabled-state logic, the "retry keeps your selection" requirement, the idempotency key, and the duplicate-submit class of bugs in one move.

### 3.3 Everything else, in order of annoyance

| Input the design demands | Cost | Fix |
|---|---|---|
| **Mains timer** — start / pause / stop by hand | 2 taps + remembering to stop, for a number that is never read or scored | Drop from v1. If kept: auto-start on page open, auto-stop on last file — 0 taps |
| **First-run onboarding card** asking for exam dates, optional subject, weekly targets | 3 fields on day 1, when the defaults are already correct (23 May / 20 Aug 2027, Sociology) | Delete the card. Defaults are right; they live in Settings |
| **Profile + Settings** as two pages, both holding exam dates and targets (§10.16 and §10.17 both list them) | Two places to edit one value → guaranteed drift | One page |
| **Today and Daily** as two routes, both leading with today's question + streak + countdown | You must learn which to open; two fetch paths for one state; duplicate heatmaps | Merge into `/`. Delete the "Daily" concept from the IA |
| **11 nav items / 19 routes** | Every route is a page spec, a fetch, a loading state, an empty state, an acceptance list | 4 routes (§6) |
| **Weekly targets 150 / 5 / 7** | Requires the app to count for you — it does, so this is free. Keep | Keep, show on Today only |
| **The "what will I improve" note** | Optional text field at the end of an upload | Keep — it's the only place strategy meets the file |

Build-side "input" counts too: 1,681 lines of PRD + 434 of tech plan + 230 lines of page specs for 19 screens is a document larger than the app it describes. Specs written for screens you build 6 weeks later are stale on arrival.

---

## 4. Delete list — what the plan builds and the product doesn't need

| Cut | PRD ref | Why it goes | What replaces it | Saved |
|---|---|---|---|---|
| **Timed test engine** (hub, builder, live, review) | §7.5, §10.6–10.9, D14/D16 | 4–5 sessions for a feature used ~2×/month. A 100-question negative-marking mock inside a PYQ browser is a toy next to a real test series — which `strategy.md` already budgets for (20–30 full tests) | Parked indefinitely. Not a stub in nav | ~5 sessions, 7 endpoints, 4 routes |
| **Revision engine** (intervals 1/3/7/21/45, Again/Hard/Good, snooze, state) | §7.6, §10.13, D17 | A scheduling algorithm for a single learner who already knows what he got wrong. It's a query, not a subsystem | Practice preset `?due=1` → wrong last time, ≥3 days ago. ~5 lines of SQL | ~2 sessions, 3 endpoints, 1 table |
| **Library** (Bookmarks / Notes / Submissions tabs) | §10.15, D13 | Three list pages over 2 bookmarks, 9 notes and 22 responses | `?bookmarked=1` and `?status=` on Practice; notes live on the question page | 1 route, 2 endpoints |
| **Global ⌘K search** | §10.19 | Practice already searches question + section text with debounce. A third search box over 2,771 rows is a fourth way to type the same word | Practice search | 1 endpoint, 1 component |
| **Progress page** | §10.14 | 7 cards of numbers, all derivable, all needing their own reconciliation | Streak + heatmap + counts on Today; "Drill weakest topic" button on Practice | 1 route, 1 endpoint |
| **Syllabus route tree** (`/syllabus/:paper/:subject`) | §8.2, §10.5 | 3 routes re-implementing a filter. The tree is static reference data | Left rail on Practice with `?node=` | 3 routes, 1 page |
| **Profile page** | §10.16 | Duplicate of Settings | Settings | 1 route |
| **Data-quality page spec** | §10.18 | Rebuild of a working page with 2 open reviews | Keep the existing Review page, link it from Settings | 1 page spec |
| **Two 365-day heatmaps** | §10.2, §10.14 | Same component, same data, two places | One, on Today | — |
| **M11 canonical-taxonomy module** | §12.1, TECH_PLAN M11 | `_subject_alias()` already exists in `views.py:44` and already runs on every question. You'd build a module for logic that's written | Move the alias map into the SQL that has to be rewritten anyway; add `theme` in the same table | 1 module, 1 command, 1 migration |
| **`POST /api/daily/start/`** | §13.3 | Second path to an attempt | Existing attempt flow | 1 endpoint |

Net: **19 routes → 4. 17 modules → 6. 9 phases → 4. ~40 endpoints → 8.**

---

## 5. What's missing — and it's the strategic half

### 5.1 `strategy.md`'s core operation has nowhere to happen

The strategy's whole mechanism is:

> 1,371 Mains PYQs → question families → ~15 cross-paper master themes → one knowledge module, many papers
> *"Caste: GS1 society · GS2 social justice · GS4 ethics · Sociology I stratification · Sociology II caste system · Essay equality"*

The app has **no theme object**. `theme_slug` is deferred to Phase 6/8; `is_repeated_theme` to Phase 6. So the tool you're about to build cannot do the one thing the strategy says matters most — it can only filter by paper and year.

Make **cross-paper theme filter the single content feature of v1.** It is one alias table (`raw section`/`syllabus_tags` → `theme`), one `?theme=` filter, and one line on Today ("this week: Caste — 34 PYQs across 5 papers"). That is ~40 rows of data and one `GROUP BY`. It also lets you delete the canonical-subject module (M11), because it's the same table.

### 5.2 State the boundary instead of discovering it later

The app measures **volume and habit** (questions, uploads, days). The strategy's success metric is **marks per three-hour paper**. The PRD explicitly refuses to measure marks (correctly — no AI evaluation). So the app will never tell you whether you're on the 1000-mark path.

Put that in §3 in one sentence, so that in March you don't bolt on a fake scorecard. The marks question is answered by a weekly handwritten note and real test-series feedback, not by this tool.

### 5.3 One missing data point

Nothing distinguishes *"I wrote a full 250-word answer"* from *"I wrote a 5-line outline"*. That's the difference between a 20-minute evening and a 90-minute one, and it's the number the strategy's cadence depends on (15–25 answers/week at what depth?).

Fix: one chip on the upload sheet — **Full / Outline** — stored as `depth`. One tap. No evaluation, no score, and suddenly "12 uploads this week, 3 full" is measurable.

---

## 6. Proposed v2 scope — the build contract

**Four screens. Four phases. No new frontend dependencies. One new table.**

| Route | What it is | Replaces |
|---|---|---|
| `/` | **Today** — three daily items (Prelims MCQ · Mains · Essay), streak + longest + gold count, 365-day heatmap, exam countdown, weekly counts, recent 5 uploads | PRD §10.1 + §10.2 + §10.14 |
| `/practice` | **The bank** — left rail from the syllabus tree (`?node=`), toolbar filters (stage · paper · theme · year · status · `due=1` · `bookmarked=1`), debounced search, rows with status + accuracy, 20/page, SQL-side everything | PRD §10.3 + §10.5 + §10.13 + §10.15 + §10.19 |
| `/questions/:key` | **Question** — attempt → result → explanation, submissions, note, bookmark, report; Mains mode → upload sheet | PRD §10.4 + §10.11 |
| `/mains` | **Vault** — queue with "Next up", submitted list, upload sheet (camera/LAN, instant upload, depth chip, optional note) | PRD §10.10 + §10.12 |
| `/settings` | One page: exam dates, targets, dataset counts, export JSON, data-quality link | PRD §10.16 + §10.17 + §10.18 |

Nav: **Today · Practice · Mains** (+ Settings in the footer). Mobile bottom nav is the same three.

Deliberately gone from v2: tests, revision engine, library, global search, progress page, syllabus routes, onboarding, timer, streak caches, `Progress` table, canonical-subject module.

### Schema (all of it)

```text
DailyChallenge        date, track, question_key            unique(date, track)
AttemptResponse  +    local_date (date, indexed)           set once on create
                 +    depth ('full' | 'outline')           mains/essay only
DailyChallenge        replaces nothing — new table
DROP                  LearnerAccount.current_streak, longest_streak
DROP                  Progress (model + table)
```

### Endpoints (all of them)

```text
GET  /api/health/                     smoke: learner resolved, counts
GET  /api/daily/                      three items + streak + 365-day calendar
GET  /api/dashboard/                  week counts, countdown, recent
GET  /api/questions/                  stage paper theme node year status due bookmarked q sort page
GET  /api/questions/<key>/            question + status + accuracy (no answer key pre-attempt)
GET  /api/questions/<key>/submissions/
POST /api/attempts/start/             mode=practice|daily
POST /api/attempts/<id>/responses/    upsert answer
POST /api/attempts/<id>/submit/       idempotent; returns result if it was Prelims
GET  /api/mains/queue/                unsubmitted, with next recommendation
POST /api/mains/submissions/          one file per request → append to the answer
GET  /api/mains/submissions/<id>/     files, note, depth
DEL  /api/mains/submissions/<id>/
GET  /api/taxonomy/                   papers, themes, years (kills hardcoded lists)
GET  /api/profile/  PATCH             exam dates, targets
GET  /api/export/                     JSON
```

### Phases

| Phase | Sessions | Ships | Exit gate (5 hand checks) |
|---|---|---|---|
| **P0 Unbreak** | 1 | Local learner, 4 auth endpoints + 20 `@login_required` gone, JSON errors, `/api/health/`, one nav, tokens, dead CSS deleted | No 302 anywhere · app opens straight to `/` · 360px no h-scroll · no hardcoded name/year · build + lint pass |
| **P1 Daily** | 1–2 | `DailyChallenge(date, track)`, 3 picks, streak from `local_date`, Today page + heatmap + streak chip | Same 3 questions after refresh and 1 min later · double-submit counts once · yesterday's miss → current 0, longest kept · practice submit does not move the streak · calendar matches rows |
| **P2 Bank** | 1–2 | Question page rewrite, Practice with SQL filters + status + theme, theme alias table | Filtered count == returned rows · subject/theme filter sends the right param · answer key absent before submit · refresh keeps filters · row status matches submissions tab |
| **P3 File** | 1 | Mains queue, upload sheet, camera capture from phone, instant upload, view/delete | 3 phone photos land as one answer · `.docx` rejected with a clear message · delete removes file from disk · answer reopens · no score shown anywhere |
| **P4 Trim** | 0.5 | Settings, export, delete the leftovers | Zero dead links · every number on Today reconciles with `/api/dashboard/` · no page without an empty state |

**~5 sessions to a working daily loop with a usable bank and a phone-upload vault.** Same estimate the tech plan gives, for half the surface — because tests, revision, library and search are gone.

---

## 7. Gates worth keeping (the rest are noise)

The PRD's quality gates include *"list p95 < 300 ms"* and *"FCP < 1.5 s"*. On a local SQLite app with 2,771 rows, those measure nothing and can't be checked without tooling. Keep the five that catch real regressions:

1. `curl` five endpoints → never `302`.
2. Same daily question twice, one minute apart.
3. Double-submit → one completion, streak +1.
4. Answer key absent from the pre-attempt payload.
5. Whole flow at 360px, keyboard only.

Each is a 2-minute manual check. Delete the rest.

---

## 8. Decisions I need from you (defaults are what I'd ship)

| # | Question | Default |
|---|---|---|
| 1 | Essay daily track: does a **one-page plan/outline** photo count? (Without it, gold is unreachable and the 40%-gold target is fiction) | **Yes** |
| 2 | Bind the app to the **LAN** so the phone can upload camera photos directly? (Drops "127.0.0.1 only" from §14.4; trusted home network) | **Yes** |
| 3 | Drop the Mains **timer** from v1? | **Drop** |
| 4 | **Tests** parked until the daily loop has run 30 days? | **Yes** |
| 5 | **Theme filter** as the one content feature, instead of canonical-subject taxonomy? | **Yes** |

If those five defaults are right, the next action is P0 — and `PRD.md` + `TECH_PLAN.md` should be collapsed into one ~300-line build contract so there's a single source of truth. They currently total 2,115 lines and disagree with each other; that's a bigger maintenance cost than the app.
