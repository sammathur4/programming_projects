# BUILD CONTRACT — IASCode daily loop (v1)

| Field | Value |
|---|---|
| Product | IASCode (local, single-user UPSC PYQ app) |
| Document | Build contract v1 — **single source of truth for implementation** |
| Based on | `PRD.md` v1.3 (product spec) + `REVIEW.md` (scope cuts) |
| Date | 27 October 2026 |
| Status | **Approved defaults applied. Phase 0 starts now.** |

`PRD.md` stays as the product reference (what/why). This file is the build spec (how/what now). Where they disagree, **this file wins**.

---

## 1. Product in one paragraph

One local app, one learner, no login. Every day: one Prelims MCQ, one Mains question, one Essay question. Finish one → bronze, two → silver, three → gold. One streak, longest streak, gold-day count. The bank: 2,771 PYQs filterable by stage/paper/theme/year/status, with status (Solved/Attempted/Todo, Submitted/Todo) derived from your own attempts. Mains and Essay are upload-only (phone photos straight into the vault). No AI, no scoring of essays, no tests, no revision engine, no leaderboard. The single content feature is a cross-paper theme filter — the thing the study strategy actually runs on.

---

## 2. What we are NOT building (read this first)

Tests, revision engine, library tabs, global search, progress page, syllabus route tree, onboarding card, Mains timer, canonical-subject module, `Progress` table, streak cache columns, `POST /api/daily/start/`. If a request asks for one of these, point at this list.

---

## 3. Decisions (defaults from the review, applied)

1. **Essay daily counts a one-page plan/outline photo.** Without this gold is unreachable. Copy: "Plan or full answer — both count."
2. **Bind to the LAN** (`0.0.0.0:8000`), trusted home network. Phone uploads camera photos directly. Drops "127.0.0.1 only".
3. **No Mains timer in v1.** If kept later: auto-start on open, auto-stop on last file.
4. **Tests parked** until the daily loop has run 30 days.
5. **Theme filter** is the one content feature, instead of the canonical-subject taxonomy.
6. **Routing:** hash URLs with query params (`#/practice?theme=Caste&status=todo`). Zero deps.
7. **Timezone:** `TIME_ZONE = "Asia/Kolkata"`.
8. **Uploads:** 20 MB/file, 150 MB total. Never reject a correct answer because of a JPEG.
9. **Instant upload:** no submit button in the happy path. Each file uploads as picked; "Add more" picks more. Note saved on blur.
10. **No score anywhere for Mains/Essay.** One optional chip: **Full / Outline** (`depth`), stored with the upload.

---

## 4. Schema (all of it)

```text
DailyChallenge        date (indexed), track, question_key        unique(date, track)
                      track ∈ {prelims, mains, essay}
AttemptResponse  +    local_date (date, indexed)                set ONCE on create
                  +    depth ('full' | 'outline')               mains/essay only
AnswerAttachment      response FK, file, kind, sort_order, created_at
DROP (usage)          LearnerAccount.current_streak, longest_streak   (columns left in DB, unused)
DROP (usage)          Progress table                            (left in DB, unused)
```

`local_date` is written once at creation and never updated. **Completion date = `local_date`.** No exceptions, including uploads that finish after midnight.

---

## 5. Endpoints (all of them)

```text
GET  /api/health/                    learner resolved + counts
GET  /api/daily/                     3 items + tier + 6 streaks + 365-day calendar
GET  /api/dashboard/                 week counts, countdown, recent
GET  /api/questions/                 stage paper theme node year status due bookmarked q sort page
GET  /api/questions/<key>/           question + status + accuracy (no answer key pre-attempt)
GET  /api/questions/<key>/submissions/
POST /api/attempts/start/            mode=practice|daily
POST /api/attempts/<id>/responses/   upsert answer
POST /api/attempts/<id>/submit/      idempotent; returns result if Prelims
GET  /api/mains/queue/               unsubmitted, with next recommendation
POST /api/mains/submissions/         one file per request → append to the answer
GET  /api/mains/submissions/<id>/    files, note, depth
DEL  /api/mains/submissions/<id>/
GET  /api/taxonomy/                  papers, themes, years (kills hardcoded lists)
GET  /api/profile/  PATCH            exam dates, targets
GET  /api/export/                    JSON
```

`POST /api/daily/start/` is **deleted**. Answering uses the normal attempt flow with `mode="daily"`.

---

## 6. Four routes, four phases

### Routes
| Route | What it is | Replaces |
|---|---|---|
| `/` | Today — three daily items, tier, streak + longest + gold count, 365-day heatmap, countdown, weekly counts, recent 5 uploads | PRD §10.1 + §10.2 + §10.14 |
| `/practice` | The bank — left rail from syllabus tree (`?node=`), toolbar filters (stage · paper · theme · year · status · `due=1` · `bookmarked=1`), debounced search, rows with status + accuracy, 20/page, SQL-side everything | PRD §10.3 + §10.5 + §10.13 + §10.15 + §10.19 |
| `/questions/:key` | Question — attempt → result → explanation, submissions, note, bookmark, report; Mains/Essay → upload sheet | PRD §10.4 + §10.11 |
| `/mains` | Vault — queue with "Next up", submitted list, upload sheet (camera/LAN, instant upload, depth chip, optional note) | PRD §10.10 + §10.12 |
| `/settings` | One page: exam dates, targets, dataset counts, export JSON, data-quality link | PRD §10.16 + §10.17 + §10.18 |

Nav: **Today · Practice · Mains** (+ Settings in the footer). Mobile bottom nav is the same three.

### Phases
| Phase | Sessions | Ships | Exit gate (5 hand checks) |
|---|---|---|---|
| **P0 Unbreak** | 1 | Local learner, 4 auth endpoints + 20 `@login_required` gone, JSON errors, `/api/health/`, one nav, tokens, dead CSS deleted, `TIME_ZONE` fixed | No 302 anywhere · app opens straight to `/` · 360px no h-scroll · no hardcoded name/year · build + lint pass |
| **P1 Daily** | 1–2 | `DailyChallenge(date, track)`, 3 picks, streak from `local_date`, Today + heatmap + streak chip | Same 3 questions after refresh and 1 min later · double-submit counts once · yesterday's miss → current 0, longest kept · practice submit does not move the streak · calendar matches rows |
| **P2 Bank** | 1–2 | Question page rewrite, Practice with SQL filters + status + theme alias table | Filtered count == returned rows · subject/theme filter sends the right param · answer key absent before submit · refresh keeps filters · row status matches submissions tab |
| **P3 File** | 1 | Mains queue, upload sheet, camera capture from phone, instant upload, view/delete, depth chip | 3 phone photos land as one answer · `.docx` rejected with a clear message · delete removes file from disk · answer reopens · no score shown anywhere |
| **P4 Trim** | 0.5 | Settings, export, delete leftovers | Zero dead links · every number on Today reconciles with `/api/dashboard/` · no page without an empty state |

**~5 sessions to a working daily loop with a usable bank and a phone-upload vault.**

---

## 7. Modules (6, not 17)

| Module | Owns | Files |
|---|---|---|
| M1 Learner resolver | always-on learner, no session | `backend/syllabus/local.py`, `views.py`, `settings.py` |
| M2 Daily engine | picks, streaks, tiers | `backend/syllabus/daily.py`, `models.py`, `views_daily.py` |
| M3 Bank + status | SQL filters, status, submissions | `backend/syllabus/queries.py`, `views.py` |
| M4 Theme alias | raw section/tags → theme, `?theme=` | `backend/syllabus/taxonomy.py` (one table, ~40 rows) |
| M5 Mains vault | queue, upload, attachments, depth | `backend/syllabus/views_mains.py`, `models.py` |
| M6 Frontend shell + 4 pages | routing, nav, tokens, primitives | `frontend/src/...` |

---

## 8. Daily engine rules

**Picks** (deterministic, no AI): pool = eligible questions for the track; exclude the last 30 daily picks for that track (relax if empty); prefer never-done; `index = hash(date, track) % len(pool)`. Persist the row. Done.

| Track | Eligible pool | 60-day exclusion? |
|---|---|---|
| Prelims | 4 non-empty options + non-empty correct answer | yes |
| Mains | `paper` in gs1–gs4, sociology1–2 | yes |
| Essay | `paper == essay` | **no** (pool is 88; say so) |

**Tier** (per date, derived): 0 = missed, 1 = bronze, 2 = silver, 3 = gold.

**Streak:** one streak + longest + gold-day count. "12 days · best 21 · 4 gold". Six separate counters are three numbers wearing six hats — don't build them.

**Streak computation:** walk backwards from today; if today meets the threshold, start at today, otherwise yesterday; count consecutive qualifying dates; stop at the first gap.

**Gold is earnable:** an Essay daily counts a one-page plan/outline photo. Copy: "Plan or full answer — both count."

---

## 9. Cross-paper theme (the one content feature)

One alias table: `raw section` / `syllabus_tags` → `theme`. ~40 rows. One `?theme=` filter on Practice. One line on Today: "this week: Caste — 34 PYQs across 5 papers". This replaces the canonical-subject module.

Example themes: Caste, Gender, Federalism, Environment, Economy, Polity, Ethics, IR, Science & Tech, History & Culture, Society, Governance, Security, Agriculture, Education.

---

## 10. Upload sheet (Mains + Essay)

- Dropzone with `accept="image/*,application/pdf"` and `capture="environment"` (rear camera on phone).
- Each file uploads as picked (background). No submit button in the happy path. "Add more" picks more.
- Limits: 20 MB/file, 150 MB total. Reject with a clear message; never reject a correct answer because of a JPEG.
- Preview thumbnails; remove; reorder.
- **Depth chip:** Full / Outline (one tap, stored as `depth`).
- Optional note ≤ 500 chars (saved on blur).
- No timer in v1.
- Instant view after upload; delete removes file from disk.

---

## 11. Verification (5 hand checks, 2 minutes each)

1. `curl` five endpoints → never `302`.
2. Same daily 3 questions twice, one minute apart.
3. Double-submit → one completion, streak +1.
4. Answer key absent from the pre-attempt payload.
5. Whole flow at 360px, keyboard only.

Delete the rest of the PRD's quality-gate list.

---

## 12. Risks worth keeping

| Risk | Mitigation |
|---|---|
| Gold feels unreachable on busy days | Essay counts a plan photo; gold is a bonus, never a requirement |
| Uploads bloat disk | 20/150 MB caps; delete removes files; storage figure in Settings |
| Upload failure loses a scanned answer | Keep selection on failure; retry; files upload as picked so nothing is lost |
| Local data loss | JSON export; document the DB path; no silent migrations |
| Streak re-dating | `local_date` set once on create; completion = that date |
| Theme mislabels | Alias table is ~40 rows, hand-reviewed, editable in Settings |

---

## 13. Decisions I need from you (defaults applied)

All five review defaults are applied (essay outline counts, LAN binding, no timer, tests parked, theme filter). If any is wrong, say so before P1.

---

## 14. Next action

**P0 — Unbreak.** Delete auth, resolve the single learner, add `/api/health/`, fix the timezone, apply tokens, one nav, delete dead CSS. ~1 session. Say "go" and I start with the backend.