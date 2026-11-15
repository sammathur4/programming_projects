# IASCode revamp — build tracker

| Field | Value |
|---|---|
| Product | IASCode (local, single-user UPSC PYQ app) |
| Updated | 10 November 2026 |
| Current state | **Question bank rebuilt. App backend works. Frontend still the old monolith.** |
| Next up | P1 Shell (delete auth + old frontend, 5 routes) **or** P2 Theme engine |

Status key: ✅ done · 🟡 in progress · ⬜ not started · 🧊 parked

---

## 1. Done

| # | Task | Notes |
|---|---|---|
| ✅ | Question bank rebuilt from the 3 Opencode CSVs | 3 separate tables, 3,974 questions |
| ✅ | `prelims_gs_questions` | 1,399 rows, 2013–2026 |
| ✅ | `csat_questions` | 960 rows, 2015–2026 |
| ✅ | `mains_questions` | 1,615 rows, 2013–2026 (incl. 2024 + 2026), 7 papers |
| ✅ | `import_question_bank` command | `--dry-run` validate, then import |
| ✅ | Models / views / admin moved to the new tables | raw SQL updated; answer lookup by `question_key` |
| ✅ | Syllabus hierarchy preserved | 9 papers · 60 sections · 177 points (from `upsc-syllabus.pdf`) |
| ✅ | `prelims_papers` metadata preserved | 27 rows (duration, marks, instructions) |
| ✅ | `TIME_ZONE = "Asia/Kolkata"` | |
| ✅ | `DailyChallenge` model + `AttemptResponse.local_date`/`depth` | schema ready for the daily loop |
| ✅ | Old DB backed up | `backend/db.sqlite3.bak-20261110` (delete when satisfied) |

---

## 2. Left — P1 Shell (unblock the app)

| # | Task | Status | Depends on | Done when |
|---|---|---|---|---|
| 1.1 | Delete auth: 20 `@login_required` + 4 endpoints (`login`/`logout`/`session`/`register`) | ✅ | — | zero 302s, zero auth screens |
| 1.1b | `local_learner_required` decorator + `local.py` | ✅ | — | every API resolves the one learner |
| 1.1c | `/api/health/` smoke endpoint | ✅ | 1.1b | `{ok, learner, counts}` returns 200 |
| 1.2 | Delete old frontend (`App.jsx` 3,216 lines + 9 CSS) and rebuild the shell | ⬜ | 1.1 | app opens to Today, no login |
| 1.3 | 5 routes: Today · Practice · Theme · Question · Mains · Settings | ⬜ | 1.2 | hash routing + deep links work |
| 1.4 | Design tokens + primitives (Button, Card, Chip, Dialog, Skeleton…) | ✅ | 1.2 | design system v2 in `strategy/design/preview.html` (light + dark, states) |
| 1.5 | Mobile bottom nav (Today · Practice · Mains · More) | ⬜ | 1.3 | 360 px, no horizontal scroll |
| 1.6 | CSAT stage in the UI | ⬜ | 1.3 | API already supports `stage=csat`; UI has a CSAT tab/filter |

**Exit gate:** app opens straight to `/`, no 302 anywhere, 360 px clean, build + lint pass.

---

## 3. Left — P2 Theme engine (the strategy's core)

| # | Task | Status | Depends on | Done when |
|---|---|---|---|---|
| 2.1 | Theme alias table: raw `section`/`tags`/`syllabus_tags` → theme, for all 3 tables | ⬜ | P1 | every question has a theme; counts reconcile |
| 2.2 | Theme API + Theme page (`/themes/:slug`) | ⬜ | 2.1 | PYQs grouped by paper, coverage ring, "Practice this theme" |
| 2.3 | Practice theme rail (`?theme=`) | ⬜ | 2.1 | filter sends `theme`, refresh keeps it |
| 2.4 | Question page: similar PYQs + notes panel | ⬜ | 2.1, P3 | similar questions render; notes link works |
| 2.5 | Import similar-question map (`data/pyq_2025_to_2026_map.csv`, 1,122 pairs) | ⬜ | P1 | pairs stored and queryable |
| 2.6 | Master-theme field on Prelims/CSAT (Mains already has `master_theme`) | ⬜ | 2.1 | cross-paper themes work for all stages |

**Exit gate:** a theme page shows "Caste — 34 PYQs across 5 papers"; counts equal the filtered Practice list.

---

## 4. Left — P3 Notes index

| # | Task | Status | Depends on | Done when |
|---|---|---|---|---|
| 3.1 | `notes` table: path + frontmatter (title, subject, paper, tags, pyq_years) from `/home/saksham/Desktop/upsc` | ⬜ | P1 | 1,568 vault files indexed |
| 3.2 | Theme → notes mapping | ⬜ | 3.1, 2.1 | every theme lists its notes |
| 3.3 | Notes panel on Theme + Question pages | ⬜ | 3.2 | a note opens from a question |

**Exit gate:** no dead note links; search/find works.

---

## 5. Left — P4 Daily loop

| # | Task | Status | Depends on | Done when |
|---|---|---|---|---|
| 4.1 | Daily engine: deterministic picks, streak, tier, 365-day calendar | ⬜ | P1 | same 3 questions after refresh; double-submit counts once |
| 4.2 | Today page: 3 daily items + streak + heatmap + countdown | ⬜ | 4.1 | LeetCode-style loop |
| 4.3 | 3-track daily (Prelims MCQ · Mains · Essay), essay outline counts | ⬜ | 4.1 | gold is earnable |
| 4.4 | Daily picks follow the week's focus theme | ⬜ | 4.1, 2.1 | picks match the weekly plan |

**Exit gate:** yesterday's miss → current streak 0, longest kept; practice submit does not move the streak.

---

## 6. Left — P5 Answer studio (Mains + Essay)

| # | Task | Status | Depends on | Done when |
|---|---|---|---|---|
| 5.1 | Answer sheet: question + marks + word limit + framework sidebar | ⬜ | P1 | framework shows; no textarea for typed answers |
| 5.2 | Camera upload from phone (LAN binding, `capture="environment"`) | ⬜ | 5.1 | 3 photos land as one answer |
| 5.3 | Depth chip (Full / Outline) | ⬜ | 5.1 | stored as `depth` |
| 5.4 | Submitted vault: view / delete, files removed from disk | ⬜ | 5.2 | delete cleans DB + disk; no score shown |

**Exit gate:** `.docx` rejected; no score anywhere; answer reopens.

---

## 7. Left — P6 Current affairs + progress

| # | Task | Status | Depends on | Done when |
|---|---|---|---|---|
| 6.1 | Import CA pointers (`data/ca_pointers_refined.csv`, 84,911 rows) | ⬜ | P1 | table populated, dated |
| 6.2 | CA → theme mapping (category + keyword; 53% are `other`) | ⬜ | 6.1, 2.1 | every CA item maps to a theme |
| 6.3 | CA feed on Today + theme pages | ⬜ | 6.2 | "CA this week for your themes" |
| 6.4 | Theme coverage matrix (theme × paper, attempted/accuracy) | ⬜ | 2.1 | reconciles with responses |
| 6.5 | Writing volume (full vs outline uploads per week) | ⬜ | 5.3 | weekly count visible |

**Exit gate:** every number reconciles with `AttemptResponse`; no fake scorecard.

---

## 8. Parked (per `REVIEW.md` — do not build unless asked)

Tests · revision engine · library tabs · global ⌘K search · progress page · syllabus route tree · onboarding card · Mains timer · streak cache columns.

---

## 9. One-line status

| Phase | State |
|---|---|
| P0 Data foundation | ✅ question bank + syllabus + schema |
| P1 Shell | 🟡 auth removed + health endpoint; frontend rebuild left |
| P2 Theme engine | ⬜ not started |
| P3 Notes index | ⬜ not started |
| P4 Daily loop | ⬜ not started |
| P5 Answer studio | ⬜ not started |
| P6 CA + progress | ⬜ not started |

**Suggested next:** P1 Shell first (the app cannot be used until auth is gone and the old frontend is replaced), then P2 Theme engine (the strategy's core mechanism).
