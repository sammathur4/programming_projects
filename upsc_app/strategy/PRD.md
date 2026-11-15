# TECH PLAN — IASCode daily-loop build

| Field | Value |
| --- | --- |
| Product | IASCode (local, single-user UPSC PYQ app) |
| Document | Technical plan v1.0 |
| Based on | `PRD.md` v1.2 (approved scope, decisions confirmed) |
| Date | 26 October 2026 |
| Purpose | Break every feature into a module, phase it, and let you reorder before code |
| Status | **Awaiting phase priority. No code until Phase 0 is approved.** |

**How to use this doc:** read §2 (priorities) and §3 (module map). If the order is right, say "start Phase 0". If not, reorder §2 and I will follow that order.

> **Not building: login, registration, accounts, sessions, auth screens.**
> Phase 0 **deletes** the four auth endpoints that already exist in the codebase
> (`auth_login`, `auth_logout`, `auth_session`, `learner_register`) and removes all 20
> `@login_required` decorators. There is no login state and no session: one learner row
> exists in the database and every request resolves it. The app opens straight into
> Today. "Local mode" means *less* auth code, not more.

---

## 1. Constraints that shape every decision

| Constraint | Consequence for this plan |
| --- | --- |
| Local, single user, no login | One `local_learner()` resolver; every `@login_required` removed from learner APIs; no auth routes |
| Mains is upload-only | No text field in the new Mains UI; files + timer + note only |
| No AI / no Mains evaluation | No model calls, no scoring columns for Mains, no rubric |
| Tests are de-prioritised | Test engine and builder move to the parked phase, after the daily loop and Mains |
| Existing DB is live and unmanaged | New tables use migrations; changes to `prelims_questions`, `mains_questions`, `syllabus_*` use a reviewed SQL command with dry-run |
| 2,771 PYQs already imported | No re-ingestion needed for existing years; only 2024 Mains + 2026 papers are new data |
| Single monolith `App.jsx` (3,216 lines) | Split pages **as they are rewritten**, never a big-bang refactor |
| No router dependency today | Keep hash URLs, add typed query params inside the hash (0 new deps) |
| Timeline | ~209 days to Prelims; the daily loop must ship before content polish |

### Two decisions I am making unless you object

1. **Routing:** keep hash URLs and upgrade them to `#/practice?status=todo&section=Polity`. Refresh, back/forward, and deep links all work; zero dependencies; no server rewrite rules. PRD routes map 1:1 in meaning. If we ever deploy publicly, swap to `react-router` then.
2. **Timezone:** set `TIME_ZONE = "Asia/Kolkata"` in `settings.py`. One line, correct local dates for daily/streak, storage stays UTC. No per-user timezone, no custom date math.

---

## 2. Phase priorities (reorder this table)

| Phase | Contents | Priority | Effort | Ships |
| --- | --- | --- | --- | --- |
| **0** | **Delete auth**, then routing, app shell, design tokens, API client | **Must** | 1–2 sessions | App opens with no login |
| **1** | Daily challenge, streak, heatmap, Today, Daily | **Must — headline feature** | 2–3 sessions | LeetCode loop |
| **2** | Problem status, submissions, filters, syllabus drill, taxonomy | **Must** | 2–3 sessions | Real problem bank |
| **3** | Mains upload vault (multi-file, preview, timer) | **Must** | 2 sessions | Handwritten answer filing |
| **4** | Revision + progress dashboard + JSON export | Should | 2 sessions | Retention + proof |
| **5** | Mains upload fixes in Practice, search, library, settings | Should | 1–2 sessions | Polish |
| **6** | Content: 2024 Mains, 2026 Prelims/Mains, tagging | Should (data-blocked) | 1–2 sessions | Completeness |
| **7** | Test hub, builder, live test, review | **Parked — your call** | 4–5 sessions | Timed mocks |
| **8** | Dark mode, theme taxonomy, PYQ heatmap, a11y/perf audit | Later | open | Depth |

**Recommended order:** 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8. Phase 7 is parked per your instruction; nothing in 0–6 depends on it.

**Why Phase 0 before the streak:** every existing API returns a 302 HTML login redirect without a Django session. The daily endpoints would inherit the same failure. Fixing local mode first is one helper plus decorator removal, and it unblocks everything else.

**What I would cut if you want speed:** Phase 5 and 8. Phases 0–3 are the product.

---

## 3. Module map (one module per feature)

| Module | Owns | New/changed files | Depends on |
| --- | --- | --- | --- |
| M1 Learner resolver | One learner, always resolved, no session | `backend/syllabus/local.py`, `views.py`, `settings.py` | — |
| M2 API client + errors | Fetch wrapper, abort, error envelope | `frontend/src/api/client.js` | M1 |
| M3 App shell + routing | Hash router, nav, layout, mobile | `frontend/src/app/router.js`, `Shell.jsx`, `nav.js` | M2 |
| M4 Design system | Tokens, primitives | `frontend/src/styles/tokens.css`, `components/*.jsx` | — |
| M5 Daily engine | Selection, persistence, streak math | `backend/syllabus/daily.py`, `models.py`, `views_daily.py`, `urls.py` | M1 |
| M6 Daily UI | Today page, Daily page, heatmap, streak chip | `pages/Today.jsx`, `pages/Daily.jsx`, `components/Heatmap.jsx` | M3, M4, M5 |
| M7 Problem status | Derived status, accuracy, filters, sorting | `backend/syllabus/queries.py`, `views.py` | M1 |
| M8 Practice UI | Faceted filters, debounced search, URL state, rows | `pages/Practice.jsx`, `styles/practice.css` | M3, M4, M7 |
| M9 Question detail | Attempt, result, submissions tab, notes, bookmark | `pages/Question.jsx`, `styles/question.css` | M7 |
| M10 Syllabus drill | Clickable topics → filtered practice | `pages/Syllabus.jsx`, `views.py` | M8 |
| M11 Taxonomy | Canonical subjects, years, counts | `backend/syllabus/taxonomy.py`, `management/commands/normalize_taxonomy.py`, `views_taxonomy.py` | M7 |
| M12 Mains vault | Queue, upload, attachments, timer, preview | `backend/syllabus/models.py`, `views_mains.py`, `urls.py`, `pages/Mains.jsx`, `MainsUpload.jsx` | M1, M4 |
| M13 Revision | Due queue, intervals, reviewer | `backend/syllabus/revision.py`, `views_revision.py`, `pages/Revision.jsx` | M7 |
| M14 Progress | Heatmap, coverage, accuracy, weak topics | `views_progress.py`, `pages/Progress.jsx` | M5, M7 |
| M15 Library + search | Bookmarks, notes, submissions, ⌘K | `pages/Library.jsx`, `components/Search.jsx`, `views_search.py` | M7, M12 |
| M16 Settings/Profile | Exam dates, targets, data quality, export | `pages/Settings.jsx`, `pages/Profile.jsx` | M1 |
| M17 Tests | Builder, live test, review | `pages/Tests*.jsx`, `views_tests.py` | M7 — **parked** |

**Deletion list (not a module, do it in Phase 0):** `frontend/src/Learner.css` and `PageSwitch.css` (0 bytes), duplicate topbar nav, `#settings` dead link, hardcoded "177 topics"/"2012 to 2025"/name strings, `@login_required` on learner APIs.

---

## 4. Phase details

Each phase lists: goal → backend → frontend → verification → exit gate. Nothing later is allowed to start before the gate passes.

### Phase 0 — Remove auth + app shell (must)

**Goal:** delete the existing login/registration endpoints, open every route directly, and give the app one navigation model and one visual language. Nothing new auth-related is created.

**Backend**

1. `backend/syllabus/local.py`
   - `LOCAL_LEARNER_USERNAME = getattr(settings, "LOCAL_LEARNER_USERNAME", "user")`
   - `local_learner(request=None)`: always returns the one `LearnerAccount`; creates it if absent. No login state, no session, no "logged in" flag — every request gets the same learner.
   - `local_learner_required` decorator that attaches `request.learner` (no redirect, returns 500 JSON if the learner row truly cannot be created).
2. `settings.py`: `TIME_ZONE = "Asia/Kolkata"`, `LOCAL_LEARNER_USERNAME = "user"`.
3. `views.py`: replace all **20** `@login_required` occurrences (lines 342, 912, 968, 989, 1017, 1022, 1027, 1049, 1075, 1093, 1114, 1130, 1180, 1286, 1327, 1344, 1410, 1474, 1541, 1574) with `@local_learner_required`; replace every `request.user` learner lookup with `request.learner`.
4. Remove `auth_session`, `auth_login`, `auth_logout`, `learner_register` views and their routes in `config/urls.py`. Keep `django.contrib.auth` installed (admin only).
5. Add `backend/syllabus/http.py`: `json_error(message, status=400, fields=None)` and make every view return it instead of `HttpResponse(status=302)` or bare 400s.
6. Add a `/api/health/` route returning `{ok: true, learner, counts}` for the smoke check.

**Frontend**

1. `src/api/client.js` — `api.get/post/patch/delete`, `AbortSignal`, parses JSON, throws `ApiError{message, status, fields}`, never follows an auth redirect.
2. `src/app/router.js` — parse `#/path?query`, `navigate(path, params)`, subscribe to `hashchange`, typed helpers `getParam/setParam`.
3. `src/app/nav.js` — one nav model: Today, Daily, Syllabus, Practice, Revision / Mains, Tests / Progress, Library; Settings + Profile in the footer. Sidebar and topbar both render from it; no duplicates.
4. `src/app/Shell.jsx` — sidebar (248px), topbar (breadcrumb, search, streak chip placeholder, countdown, profile), mobile bottom nav (Today · Daily · Practice · Mains · More sheet).
5. `src/styles/tokens.css` — tokens from PRD §11.2, imported first in `main.jsx`; body font `DM Sans` (already imported), display `Fraunces`.
6. Primitives: `Button`, `IconButton`, `Field`, `Card`, `Chip`, `StatusBadge`, `EmptyState`, `Skeleton`, `Tabs`, `Dialog`, `ProgressBar`.
7. Move existing pages behind the shell without rewriting their internals: `practice`, `syllabus`, `bookmarks`, `history`, `review`, `quiz`/`account` keep working.
8. Delete dead CSS files and dead nav; fix `#settings` to a real stub page.

**Verification**

```bash
cd backend && .venv/bin/python manage.py check
curl -s localhost:8000/api/health/ | head
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/questions/     # expect 200, never 302
cd ../frontend && npm run lint && npm run build
```

Manual: open each nav item, hard-refresh, confirm no login prompt and no blank panel; 360px width with no horizontal scroll.

**Exit gate:** zero 302s on `/api/*`, zero auth screens, one nav, tokens applied, build passes. Nothing else starts before this.

---

### Phase 1 — Daily challenge + streak + heatmap (must, headline)

**Goal:** open app → one question → submit → streak moves. Stable all day, resets on a miss.

**Backend**

1. `models.py`:

```python
class DailyChallenge(models.Model):
    date = models.DateField(unique=True, db_index=True)
    question_key = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
```

   Managed model → normal migration `0010_dailychallenge.py`.
2. `backend/syllabus/daily.py` — pure functions, no ORM in the algorithm:

- `pick_daily(date, candidates, attempted_recent, recent_daily)` per PRD §7.1 / Appendix B.
- `compute_streak(completed_dates, today)` → `(current, longest, last_completed)`.
- `if __name__ == "__main__":` assert self-check: same date → same pick; 60-day exclusion respected when alternatives exist; gap resets current; longest survives; multiple submissions on one date count once. **This is the one runnable check for the streak logic.**

3. `views_daily.py`:
   - `GET /api/daily/` → `{date, challenge, completed, result, streak, calendar}` (calendar 365 days, two booleans per day).
   - `GET /api/daily/?date=` → past challenge + result (read-only).
   - `POST /api/daily/start/` → creates/reuses a `DailyChallenge` row and an `Attempt(mode="daily")`, returns question + attempt id.
   - No `complete` endpoint: completion is derived from a response dated that local day (matches PRD §13.3 note).
   - Eligibility: Prelims, four non-empty options, non-empty `correct_answer`.
   - Fallbacks logged to `ApiLog` and surfaced as `pool_health` in `GET /api/daily/`.
2. `submit_attempt`: remove the streak mutation for non-daily modes. Keep `LearnerAccount.current_streak` as a **cache** recomputed from daily completions on write/profile read; `DailyChallenge` + responses stay the source of truth.
3. `GET /api/dashboard/` → `{date, daily, streak, week, recent_submissions, exam_countdown, plan[]}`. Plan rules from PRD §10.1 (daily → revision if ≥10 due → Mains if target unmet → drill). Revision/Mains items return `null` until those modules exist; the API shape stays stable.

**Frontend**

1. `pages/Today.jsx` — daily hero card (solve/review), streak, countdown, weekly targets (placeholders where data is absent), recent submissions, first-run empty state.
2. `pages/Daily.jsx` — today's card, current/longest streak, countdown to next question, last-7-days list, calendar.
3. `components/Heatmap.jsx` — 53×7 SVG-free grid, 3 intensities + today ring + future disabled, tooltip, `<table>` alternative for screen readers.
4. `components/StreakChip.jsx` — `🔥 12` in topbar, links to Daily, tooltip, `aria-label`.
5. Question page in `mode=daily`: submit → result → "Back to Daily"; Daily shows Completed.
6. On app load, fetch `/api/dashboard/`; Today is the default route.

**Verification**

```bash
cd backend && .venv/bin/python -m syllabus.daily   # self-check asserts
curl -s localhost:8000/api/daily/ | python -m json.tool | head -40
# twice, compare question_key → must be identical
```

Manual: submit daily twice → streak increments once; backdate a `DailyChallenge` row with no response → yesterday missed → current streak 0, longest preserved; refresh at 23:59 and 00:01 → date rolls over.

**Exit gate:** stable question, exact-once streak, reset on miss, calendar matches data, practice submits do not move the streak.

---

### Phase 2 — Problem bank: status, submissions, filters, syllabus drill (must)

**Goal:** every question shows Solved / Attempted / Todo; filters are real; syllabus topics open filtered lists.

**Backend**

1. `queries.py` — annotate Prelims rows in SQL with `attempt_count`, `correct_count`, `last_attempted_at`, `status`:

```sql
CASE WHEN r.correct_count > 0 THEN 'solved'
     WHEN r.attempt_count > 0 THEN 'attempted'
     ELSE 'todo' END
```

   `questions_overview`: filter/order/paginate in SQL (stop loading all rows and slicing in Python), `page_size` max 100, accept `section`, `difficulty`, `status`, `year`, `stage`, `q`, `sort`.
2. `question_detail`: add `status`, `attempt_count`, `accuracy`, `last_attempted_at`. Keep the answer key out of the payload until an attempt exists (already true; assert it in a response check).
3. New `GET /api/questions/<key>/submissions/` → every attempt newest first: `{date, selected_answer, correct_answer_after_submit, is_correct, elapsed_seconds, mode}`.
4. New `GET /api/submissions/?stage=&status=&from=&to=&page=` → unified Prelims attempts + Mains uploads (Mains part returns empty until Phase 3).
5. `taxonomy.py` + `management/commands/normalize_taxonomy.py`:

- `--dry-run` prints the alias diff; `--apply` writes `canonical_subject`.
- Alias map exactly as PRD §12.1; unknown → `Unclassified`.
- Column added by an idempotent SQL command (unmanaged table): `ALTER TABLE prelims_questions ADD COLUMN canonical_subject TEXT`.

6. New `GET /api/taxonomy/` → papers, canonical subjects with counts + year range, years, stages. This kills every hardcoded year list and subject list in the UI.

**Frontend**

1. `pages/Practice.jsx` — segmented stage, paper/subject/year/difficulty/status selects, debounced search (300 ms, `AbortController`), removable chips, "Clear all", header counts, sort, 20/page pagination, skeleton/empty/error.
2. All filter state in the hash query (`#/practice?status=todo&section=Polity&page=2`).
3. Row: year · paper · Q no. · excerpt · subject · difficulty dot · status badge · `Your accuracy 67% · 3 attempts`.
4. `pages/Question.jsx` — two columns ≥1100px, options, explicit Submit (no auto-submit), result + explanation after submit, tabs Question · Submissions · Notes, keyboard 1–4 + Enter, prev/next inside the current filter set, report issue.
5. `pages/Syllabus.jsx` — paper cards → sections → topic row `n PYQs · accuracy · Practice` → `#/practice?node=<id>` with visible chip.
6. `pages/Library.jsx` tabs: Bookmarks, Notes, Submissions — each with search/filter/sort and URL state.

**Verification**

```bash
curl -s "localhost:8000/api/questions/?status=solved&page_size=20" | python -m json.tool | head
curl -s "localhost:8000/api/questions/?section=Polity" | python -c "import sys,json; d=json.load(sys.stdin); print(d['pagination'])"
.venv/bin/python manage.py normalize_taxonomy --dry-run   # expect only known aliases, no surprises
```

Manual: subject filter must send `section` (check the network tab); typing one word fires one request; refresh keeps filters; topic count equals filtered list count; status badge matches the submissions tab.

**Exit gate:** status filters correct, no full-table Python slicing, taxonomy 100% canonical, syllabus rows clickable, counts reconcile.

---

### Phase 3 — Mains upload vault (must)

**Goal:** pick a Mains PYQ, upload 1–10 PDFs/images, optional timer and note, reopen later. No scoring.

**Backend**

1. `models.py`:

```python
class AnswerAttachment(models.Model):
    response = models.ForeignKey("AttemptResponse", related_name="attachments", on_delete=models.CASCADE)
    file = models.FileField(upload_to=answer_attachment_path)
    kind = models.CharField(max_length=10)      # pdf | image
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
```

   `upload_to`: `answer_uploads/mains/<question_key>/<uuid>.<ext>`; never trust the original name.
2. `Attempt`: add `mode` (default `practice`), `question_keys` JSON, `config` JSON, `time_limit_seconds`, `max_score`. `AttemptResponse`: add `marked_for_review`. One migration.
3. `views_mains.py`:

- `GET /api/mains/queue/?paper=&year=&page=` — questions with no uploaded answer; `next` = paper rotation, least recently uploaded.
- `POST /api/mains/submissions/` multipart: `question_key`, `files[]`, `elapsed_seconds`, `note`. Validate server-side: 1–10 files, ≤10 MB each, ≤50 MB total, extension **and** content type in `{pdf, jpg, jpeg, png, webp}`; reject others with the exact field error. Idempotency key = `(learner, question_key, client_upload_id)`; a retry must not duplicate.
- `GET /api/mains/submissions/`, `GET/PATCH/DELETE /api/mains/submissions/<id>/` — delete removes DB row + files from disk.
- No score, no rubric, no AI field anywhere.

4. Reuse `Attempt(mode='mains')` + `AttemptResponse` as the container; `response_text` stays empty and is never written by the UI.

**Frontend**

1. `pages/Mains.jsx` — weekly target, papers covered, time spent; Next up card; Queue/Submitted tabs; filters; no score columns.
2. `pages/MainsUpload.jsx` — question header (paper, year, marks, word limit), dropzone (drag + click), file cards with thumbnail/PDF icon, size, remove, reorder, client-side pre-validation mirroring the server, optional start/pause/stop timer, optional note ≤500 chars, submit disabled until one valid file, upload progress, failure keeps the selection.
3. `pages/MainsSubmission.jsx` — files grid (images inline, PDFs new tab), date, time spent, note; replace/delete with confirm.
4. Question page (Mains): single "Upload answer" button; **no textarea anywhere**.

**Verification**

```bash
curl -s -F question_key=<key> -F files=@a.jpg -F files=@b.pdf localhost:8000/api/mains/submissions/ | python -m json.tool
curl -s -F files=@big.pdf localhost:8000/api/mains/submissions/   # 11 MB → 400 with field error
```

Manual: 3 images upload and reopen; 11th file rejected; `.docx` rejected; delete removes the files from `media/answer_uploads/`; retry after a forced network failure creates one submission, not two.

**Exit gate:** only PDF/images accepted, limits enforced server-side, typed answers impossible, files persist and delete cleanly, no score displayed.

---

### Phase 4 — Revision + progress + export (should)

**Backend:** `revision.py` interval ladder (1/3/7/21/45 by attempt count), reasons `wrong_recent | bookmarked | stale_correct`, `GET /api/revision/`, `POST /api/revision/<key>/grade/` (`again|hard|good`), snooze 3 days. `GET /api/progress/?range=week|4w|all` → heatmap, coverage, accuracy, weak topics (≥5 attempts), 8-week trend, Mains uploads. `GET /api/export/` → JSON of attempts, responses, notes, bookmarks, Mains metadata.

**Frontend:** `pages/Revision.jsx` (grouped queue, focused reviewer with three buttons), `pages/Progress.jsx` (explicit range switch, heatmap, coverage table with Drill links, weak topics, trend), export button in Settings.

**Gate:** revision count equals Today's plan item; every weak-topic action opens the right filtered Practice; all numbers reconcile with `AttemptResponse`.

---

### Phase 5 — Search, library polish, settings (should)

Global `⌘K`/`Ctrl+K` search over questions/topics/notes/bookmarks (`GET /api/search/?q=`), settings page (exam dates, targets, density, shortcuts, dataset counts, data quality link), profile page (no logout), data-quality queue moved out of primary nav. **Gate:** search returns grouped results with counts and keyboard nav; no dead links.

---

### Phase 6 — Content completion (should, data-blocked)

Add 2024 Mains and 2026 Prelims/Mains only when the source data exists. Validate: unique keys, 4 options + correct answer, explanations ≥99%, marks + word limit on every Mains row, canonical subject + tags. Backfill the 88 untagged Mains rows; `is_repeated_theme` only where a theme appears ≥3 times. **Gate:** counts recorded in Settings → About; no UI year list hardcoded.

---

### Phase 7 — Tests + builder (PARKED per your instruction)

Deferred until you ask. When it resumes: `Attempt.mode` already supports it (Phase 3 migration), so this is mostly UI + composition + a review endpoint. Scope stays in PRD §7.5 / §10.6–10.9. Do not start before Phases 0–3 ship.

---

### Phase 8 — Depth (later)

Theme taxonomy, subject × year PYQ heatmap, dark mode, saved views, bulk actions, performance/a11y audit.

---

## 5. Data and schema changes

| Change | Mechanism | Reversible |
| --- | --- | --- |
| `DailyChallenge` new table | Django migration | yes (drop table) |
| `AnswerAttachment` new table | Django migration | yes |
| `Attempt.mode/question_keys/config/time_limit_seconds/max_score` | Django migration | yes |
| `AttemptResponse.marked_for_review` | Django migration | yes |
| `LearnerAccount` exam dates + weekly targets | Django migration | yes |
| `prelims_questions.canonical_subject`, `mains_questions.canonical_subject/theme_slug` | Idempotent SQL command `content_schema --apply` (unmanaged tables) | column drop |
| Subject normalization values | `normalize_taxonomy --apply` | re-run from the alias map |
| 2024/2026 rows | Import command with `--dry-run` diff first | delete by year |

**Rule:** never `makemigrations --fake` an unmanaged table, and never run a write command without first printing the diff.

---

## 6. Cross-cutting contracts

### API response envelope

```json
{ "items": [], "pagination": { "page": 1, "page_size": 20, "total": 0, "pages": 0 } }
{ "error": "Only PDF and images are accepted.", "fields": { "files": "..." } }
```

Existing keys the current UI reads (`questions`, `total`, `has_more`, …) stay until that page is rewritten, then the page and the API move together in the same commit.

### Status derivation (single source)

```
prelims: solved = any response.is_correct; attempted = any response; else todo
mains:   submitted = any uploaded answer; else todo
```

### Daily completion (single source)

```
completed(date) = exists response to DailyChallenge(date).question_key
                  with answered_at local date == date
```

No extra completion table. `LearnerAccount` streak fields are cache only.

### Error handling

5xx → inline retry, keep filters and file selection. Network failure → offline banner, no data loss. No auth redirect ever.

---

## 7. Risks specific to the build

| Risk | Where | Mitigation |
| --- | --- | --- |
| Removing `@login_required` breaks an endpoint that assumed `request.user` | all views | grep every `request.user` usage; `@local_learner_required` sets `request.learner`; smoke-test every route |
| `App.jsx` rewrite stalls feature work | frontend | split only the pages being rewritten; keep untouched pages wired behind the shell |
| Unmanaged-table SQL breaks the live DB | taxonomy | backup `db.sqlite3`, dry-run diff, idempotent `ADD COLUMN IF NOT EXISTS` equivalent (check `PRAGMA table_info`) |
| Streak cache drifts from derived data | `LearnerAccount` | recompute on profile/daily read; self-check asserts; cache is never read by the API as truth |
| Daily pool too small or repeats | daily engine | 30/60-day exclusions with relax-not-fail, `pool_health` in the response |
| Uploads bloat disk | Mains | 10 MB × 10 × 50 MB caps, delete removes files, storage shown in Settings |
| Timezone bugs at midnight | all date logic | `Asia/Kolkata`, `timezone.localdate()` only, never `datetime.now()` |
| Filters silently ignored | `questions_overview` | counts in the response header must equal returned rows; manual count check per filter |
| Scope creep back to LeetCode social features | planning | PRD §19 non-goals stay in force |

---

## 8. Verification per phase (copy-paste)

```bash
# backend
cd "/media/saksham/phone data/programming_projects/upsc_app/backend"
.venv/bin/python manage.py check
.venv/bin/python manage.py migrate
.venv/bin/python -m syllabus.daily            # streak/pick self-check
.venv/bin/python manage.py normalize_taxonomy --dry-run

# frontend
cd ../frontend
npm run lint
npm run build

# smoke (backend running on 127.0.0.1:8000)
for u in /api/health/ /api/daily/ /api/taxonomy/ /api/questions/ /api/dashboard/; do
  printf "%s " "$u"; curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:8000$u"
done
```

Any `302` is a Phase 0 regression. Any mismatch between a filtered count and its rows is a Phase 2 regression.

---

## 9. Time estimate

| Phase | Sessions | Can run in parallel with |
| --- | --- | --- |
| 0 | 1–2 | — |
| 1 | 2–3 | — |
| 2 | 2–3 | Mains backend (Phase 3) |
| 3 | 2 | Phase 2 UI |
| 4 | 2 | content import |
| 5 | 1–2 | — |
| 6 | 1–2 | anything |
| 7 (parked) | 4–5 | — |

Realistic path to "daily streak + problem bank + Mains upload works": **5–8 sessions**.

---

## 10. Decide now

1. **Phase order** — keep 0 → 1 → 2 → 3, or move Mains before Practice?
2. **Phase 7 (tests)** — parked entirely, or keep the test hub as a stub in nav?
3. **Routing** — hash URLs with query params (0 deps) or add `react-router`?
4. **Phase 6 data** — do you have 2024 Mains / 2026 papers, or should it wait?
5. **Backup** — JSON export only, or also copy `db.sqlite3` before each write command?

Reply with the order (or "start Phase 0") and I will open the build there.
