# IMPLEMENTATION TECH DOC - IASCode v2 (Daily Loop Focus)

| Field | Value |
| --- | --- |
| Product | IASCode (local, single-user UPSC PYQ app) |
| Document | Implementation Tech Doc v2.0 |
| Based on | PRD v1.3, TECH_PLAN v1, REVIEW analysis, current codebase audit |
| Date | 28 October 2026 |
| Status | Ready for implementation |
| Goal | Make app more usable with better filters, updated UI/UX. Focus on daily loop, problem bank, and Mains upload. |

---

## Table of Contents
1. [Current State Assessment](#1-current-state-assessment)
2. [Target State (v2)](#2-target-state-v2)
3. [Architecture Overview](#3-architecture-overview)
4. [Database Schema Changes](#4-database-schema-changes)
5. [Backend Implementation](#5-backend-implementation)
6. [Frontend Implementation](#6-frontend-implementation)
7. [API Contracts](#7-api-contracts)
8. [Implementation Plan (Phased)](#8-implementation-plan-phased)
9. [File-by-File Changes](#9-file-by-file-changes)
10. [Testing & Verification](#10-testing--verification)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Quick Start for Developer](#12-quick-start-for-developer)

---

## 1. Current State Assessment

### What exists
- **Backend**: Django app with SQLite (`db.sqlite3`), ~2771 questions (1400 Prelims + 1371 Mains), auth system with `@login_required` everywhere, middleware auto-assigns local user
- **Frontend**: React + Vite monolith `App.jsx` (3216 lines), 9 CSS files, hash-based routing
- **Issues**: App requires login (302 redirects), 17 modules planned but over-engineered, tests/revision/library/search all present but unused, streak logic has bugs

### Key bugs to fix
- `AttemptResponse.answered_at` uses `auto_now=True` - re-dates on every save (breaks daily completion)
- `LearnerAccount` has `current_streak`/`longest_streak` updated on every practice submit (wrong)
- Auth required everywhere, blocks app usage
- Daily challenge not implemented as per corrected spec (needs 3 tracks: prelims, mains, essay)
- No theme filtering (core strategy feature missing)

---

## 2. Target State (v2)

**4 routes, 6 modules, minimal surface area**

| Route | Purpose | Notes |
| --- | --- | --- |
| `/` | Today - 3 daily items (Prelims/Mains/Essay), streak, heatmap, countdown | Default route, replaces multiple pages |
| `/practice` | Question bank with filters (stage/paper/theme/year/status), SQL-side | Core browsing with smart filters |
| `/questions/:key` | Question detail - attempt MCQ or upload for Mains/Essay | Unified question view |
| `/mains` | Mains/Essay vault - queue, upload with camera, view submitted | Phone-friendly upload |
| `/settings` | Settings, export, data info | Single settings page |

**Nav**: Today · Practice · Mains (+ Settings in footer). Mobile bottom nav same 3 items.

**Key Features**:
- No login - single local learner always resolved
- 3-track daily (Prelims MCQ + Mains + Essay), bronze/silver/gold tiers
- Streak computed from `local_date` (set once), gold achievable with essay outline photo
- Cross-paper theme filter (replaces complex taxonomy)
- Phone camera upload for Mains/Essay with instant upload
- Status derived from attempts (Solved/Attempted/Todo, Submitted/Todo)
- Hash routing with query params

---

## 3. Architecture Overview

```
upsc_app/
├── backend/
│   ├── config/          # Django settings/urls
│   ├── syllabus/        # Main app
│   │   ├── models.py    # DB models (trimmed)
│   │   ├── views.py     # API views (refactored)
│   │   ├── daily.py     # Daily engine logic
│   │   ├── local.py     # Local learner resolver
│   │   ├── views_daily.py
│   │   ├── views_mains.py
│   │   ├── queries.py   # SQL-optimized queries
│   │   ├── taxonomy.py  # Theme aliases
│   │   └── middleware.py
│   └── db.sqlite3
└── frontend/
    └── src/
        ├── app/         # Shell, router, nav
        ├── api/         # API client
        ├── pages/       # Today, Practice, Question, Mains, Settings
        ├── components/  # Primitives, Heatmap, etc.
        └── styles/      # tokens.css
```

---

## 4. Database Schema Changes

### New Tables
```sql
-- DailyChallenge: one per (date, track)
CREATE TABLE syllabus_dailychallenge (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    track VARCHAR(10) NOT NULL CHECK(track IN ('prelims','mains','essay')),
    question_key VARCHAR(120) NOT NULL,
    created_at DATETIME NOT NULL,
    UNIQUE(date, track)
);
CREATE INDEX idx_dailychallenge_date ON syllabus_dailychallenge(date);
```

### Modify Existing Tables
```sql
-- AttemptResponse: add local_date (set once) and depth
ALTER TABLE syllabus_attemptresponse ADD COLUMN local_date DATE;
ALTER TABLE syllabus_attemptresponse ADD COLUMN depth VARCHAR(10) CHECK(depth IN ('full','outline')) DEFAULT NULL;

-- Create index
CREATE INDEX idx_attemptresponse_local_date ON syllabus_attemptresponse(local_date);

-- Backfill local_date from answered_at for existing rows
UPDATE syllabus_attemptresponse 
SET local_date = date(answered_at) 
WHERE local_date IS NULL;
```

### Drop/Deprecate (leave columns, don't use)
- `LearnerAccount.current_streak`, `longest_streak` - compute from daily data
- `Progress` table - not used, can leave

### Theme Alias Table (optional but clean)
```sql
CREATE TABLE syllabus_theme_alias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_value VARCHAR(255) NOT NULL,
    theme VARCHAR(100) NOT NULL,
    UNIQUE(raw_value)
);
-- Seed with ~40 mappings
```

---

## 5. Backend Implementation

### 5.1 Local Learner (`syllabus/local.py`) - NEW
```python
from django.contrib.auth.models import User
from django.conf import settings
from .models import LearnerAccount

LOCAL_LEARNER_USERNAME = getattr(settings, "LOCAL_LEARNER_USERNAME", "user")

def local_learner(request=None):
    """Always returns the single local learner, creates if missing."""
    user, _ = User.objects.get_or_create(
        username=LOCAL_LEARNER_USERNAME,
        defaults={"is_active": True}
    )
    learner, _ = LearnerAccount.objects.get_or_create(
        user=user,
        defaults={"display_name": user.username}
    )
    return learner

def local_learner_required(view_func):
    """Decorator that attaches request.learner without redirect."""
    def wrapper(request, *args, **kwargs):
        request.learner = local_learner(request)
        return view_func(request, *args, **kwargs)
    return wrapper
```

### 5.2 Settings Updates
In `config/settings.py`:
```python
TIME_ZONE = "Asia/Kolkata"
LOCAL_LEARNER_USERNAME = "user"
ALLOWED_HOSTS = ["*", "localhost", "0.0.0.0"]  # for LAN access
```

### 5.3 Remove Auth (`config/urls.py`)
Remove these routes:
- `api/learners/register/`
- `api/auth/session/`
- `api/auth/login/`
- `api/auth/logout/`

Keep `/admin/` only.

### 5.4 Daily Engine (`syllabus/daily.py`) - NEW
Core logic with deterministic picking by date+track, streak computation from local_date, tier calculation (bronze/silver/gold).

### 5.5 Daily Views (`syllabus/views_daily.py`) - NEW
```python
@local_learner_required
def daily_challenge(request):
    """GET /api/daily/ - returns 3 items + streak + calendar"""
    ...
    
@local_learner_required  
def dashboard(request):
    """GET /api/dashboard/ - week counts, countdown"""
    ...
```

### 5.6 Mains Views (`syllabus/views_mains.py`) - NEW
Queue, instant file upload (one per request), view/delete submissions with file cleanup.

### 5.7 Update Views (`syllabus/views.py`)
- Replace all 20 `@login_required` with `@local_learner_required`
- Replace `request.user` with `request.learner`
- Fix `AttemptResponse` - set `local_date = timezone.localdate()` on create, never auto-update
- Remove streak mutation from `submit_attempt`

### 5.8 HTTP Helpers (`syllabus/http.py`) - NEW
JSON error responses with consistent format.

---

## 6. Frontend Implementation

### 6.1 New Structure
```
frontend/src/
├── api/client.js          # Fetch wrapper, ApiError
├── app/router.js          # Hash router
├── app/nav.js             # Navigation config
├── app/Shell.jsx          # Layout with sidebar/bottom nav
├── app/App.jsx            # Main app with routes
├── pages/Today.jsx, Practice.jsx, Question.jsx, Mains.jsx, Settings.jsx
├── components/Heatmap.jsx, StreakChip.jsx, UploadSheet.jsx, primitives/*
└── styles/tokens.css
```

### 6.2 API Client, Router, Shell
Standard patterns - hash routing, fetch wrapper with error handling, responsive shell with nav.

### 6.3 Pages
- **Today**: 3 daily cards, streak, heatmap, countdown
- **Practice**: Filters (stage/paper/theme/year/status), debounced search, left rail, SQL-backed
- **Question**: MCQ for Prelims, upload sheet for Mains/Essay
- **Mains**: Queue + submitted list, camera upload
- **Settings**: Exam dates, targets, export, info

---

## 7. API Contracts

See full contracts in doc - health, daily (3 items + streak + calendar), questions with status/accuracy, attempts, mains uploads, taxonomy, export.

---

## 8. Implementation Plan (Phased)

| Phase | Sessions | Goal | Gate |
| --- | --- | --- | --- |
| **P0 Unbreak** | 1 | Remove auth, local learner, health, shell, tokens | No 302s, app opens to `/`, build passes |
| **P1 Daily** | 1-2 | 3-track daily, streaks, Today page | Stable picks, correct streak, gold works with outline |
| **P2 Bank** | 1-2 | Filters, theme, status, SQL queries | Correct filtering, status badges right |
| **P3 File** | 1 | Mains/Essay upload, camera, instant upload | Upload works, limits enforced, files deletable |
| **P4 Trim** | 0.5 | Settings, export, cleanup | All checks pass, no dead links |

**Total: ~5 sessions**

---

## 9. File-by-File Changes

Detailed list of creates/modifies/deletes for backend and frontend.

---

## 10. Testing & Verification

**Automated**: manage.py check, migrate, lint, build, smoke curl tests
**Manual (5 checks)**: No auth redirects, daily stability, streak accuracy, answer key hidden, mobile responsive

---

## 11. Risks & Mitigations

Key risks with mitigations - auth removal, streak bugs, file uploads, data integrity.

---

## 12. Quick Start for Developer

Setup instructions, dev commands, key files to read first, environment notes.

---

**Follow phases in order. Pass gates. Ship the habit loop first.**
