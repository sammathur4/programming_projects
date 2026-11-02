"""
Mission 2026 — analytics layer.

Turns raw habit logs into the things that actually keep a person going:
streaks, momentum, burnout warnings, best-time-of-day, recovery detection,
and per-goal effort attribution.

Design notes
------------
* Everything is computed from HabitLog rows (single source of truth), so the
  numbers always agree with what the user ticked.
* No hard-coded "today": every function takes `today` so results are testable
  and so back-dated screens behave sensibly.
* Burnout detection is deliberately conservative — it warns, it never scolds.
"""
import datetime as dt
from collections import defaultdict

from .models import Habit, HabitLog, Objective

WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def daterange(start, end):
    day = start
    while day <= end:
        yield day
        day += dt.timedelta(days=1)


def logs_by_date(habit=None, start=None, end=None):
    """{date: True} for done logs in the window."""
    qs = HabitLog.objects.filter(done=True)
    if habit is not None:
        qs = qs.filter(habit=habit)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    return set(qs.values_list("date", flat=True))


# ---------------------------------------------------------------- streaks
def skipped_dates(habit=None):
    """Dates explicitly marked 'skipped' — neutral for streaks, like rest days."""
    qs = HabitLog.objects.filter(status=HabitLog.STATUS_SKIPPED)
    if habit is not None:
        qs = qs.filter(habit=habit)
    return set(qs.values_list("date", flat=True))


def current_streak(habit, today):
    """Consecutive done-days ending today (today not yet done = grace; skipped = neutral)."""
    done = logs_by_date(habit)
    if not done:
        return 0
    skipped = skipped_dates(habit)
    day = today
    if day not in done:
        day -= dt.timedelta(days=1)  # today still pending isn't a break
    streak = 0
    while True:
        if day in done:
            streak += 1
            day -= dt.timedelta(days=1)
        elif day in skipped:
            day -= dt.timedelta(days=1)  # rest day: keep going, don't count
        else:
            break
    return streak


def best_streak(habit):
    """Longest run of consecutive done-days ever (skipped days are neutral)."""
    dates = sorted(logs_by_date(habit))
    if not dates:
        return 0
    skipped = skipped_dates(habit)
    best = run = 1
    day = dates[0]
    end = dates[-1]
    started = False
    while day <= end:
        if day in dates:
            run = run + 1 if started else 1
            started = True
            best = max(best, run)
        elif day not in skipped:
            started = False
            run = 0
        day += dt.timedelta(days=1)
    return best


def streak_history(habit, days=30, today=None):
    """List of (date, hit) for the last `days` days, oldest first."""
    today = today or dt.date.today()
    done = logs_by_date(habit)
    start = today - dt.timedelta(days=days - 1)
    return [(d, d in done) for d in daterange(start, today)]


# ---------------------------------------------------------------- momentum
def momentum(habit, today, window=7):
    """
    0-100 score blending short-term consistency with trend.
    Rising momentum feels good and is a better motivator than a raw %.
    """
    done = logs_by_date(habit)
    if not done:
        return {"score": 0, "trend": 0, "recent": 0, "previous": 0}

    def hits(start, end):
        ds = list(daterange(start, end))
        return sum(1 for d in ds if d in done) / len(ds) * 100 if ds else 0

    recent_start = today - dt.timedelta(days=window - 1)
    prev_end = recent_start - dt.timedelta(days=1)
    prev_start = prev_end - dt.timedelta(days=window - 1)

    recent = hits(recent_start, today)
    previous = hits(prev_start, prev_end)
    trend = round(recent - previous)
    # weight recent performance, then tilt by trend
    score = max(0, min(100, round(recent * 0.75 + (50 + trend / 2) * 0.25)))
    return {
        "score": score,
        "trend": trend,
        "recent": round(recent),
        "previous": round(previous),
    }


# ---------------------------------------------------------------- burnout
def burnout_risk(today, lookback=21):
    """
    Spot the classic overreach pattern before it becomes a crash:
      * habit load is high (many habits attempted)
      * completion is falling over the last week vs the week before
      * a long unbroken streak just broke

    Returns {'level': none|watch|high, 'reasons': [...], 'advice': str}
    """
    reasons = []
    score = 0

    habits = list(Habit.objects.filter(active=True))
    if not habits:
        return {"level": "none", "reasons": [], "advice": "", "score": 0}

    def window_rate(start, end):
        total = 0
        hit = 0
        for h in habits:
            done = logs_by_date(h, start, end)
            for d in daterange(start, end):
                total += 1
                if d in done:
                    hit += 1
        return (hit / total * 100) if total else 0

    last_week_start = today - dt.timedelta(days=6)
    prev_week_end = last_week_start - dt.timedelta(days=1)
    prev_week_start = prev_week_end - dt.timedelta(days=6)

    last_week = window_rate(last_week_start, today)
    prev_week = window_rate(prev_week_start, prev_week_end)
    drop = prev_week - last_week

    if prev_week >= 40 and drop >= 25:
        score += 45
        reasons.append(
            f"Completion fell {round(drop)} points this week "
            f"({round(prev_week)}% → {round(last_week)}%)"
        )
    elif prev_week >= 40 and drop >= 12:
        score += 20
        reasons.append(f"Momentum is cooling off ({round(drop)} point dip)")

    # streak breaks on the strongest habit
    for h in habits:
        if best_streak(h) >= 10 and current_streak(h, today) == 0:
            score += 15
            reasons.append(f"Your {h.name} streak reset — that's usually the first sign")
            break

    # too many habits at once
    if len(habits) >= 10:
        score += 10
        reasons.append(f"{len(habits)} habits at once is a heavy load")

    # nothing logged at all recently
    any_recent = any(logs_by_date(h, today - dt.timedelta(days=2), today) for h in habits)
    if not any_recent:
        score += 25
        reasons.append("Nothing logged in the last 3 days")

    if score >= 55:
        level = "high"
        advice = (
            "You're heading for a crash, not a finish line. Drop to your 3 "
            "most important habits for a week, then rebuild. Progress you can "
            "sustain beats a perfect week that ends in quitting."
        )
    elif score >= 25:
        level = "watch"
        advice = (
            "Load is creeping up. Protect sleep and pick one habit to make "
            "effortless this week — momentum first, ambition second."
        )
    else:
        level = "none"
        advice = "Pace looks healthy. Keep the streak alive."

    return {"level": level, "reasons": reasons, "advice": advice, "score": score}


# ---------------------------------------------------------------- patterns
def best_weekday(habit):
    """Which weekday this habit succeeds most (needs a little history)."""
    done = logs_by_date(habit)
    if len(done) < 7:
        return None
    counts = defaultdict(int)
    totals = defaultdict(int)
    for d in done:
        counts[d.weekday()] += 1
    start = min(done)
    for d in daterange(start, max(done)):
        totals[d.weekday()] += 1
    rates = {w: counts[w] / totals[w] for w in totals if totals[w]}
    if not rates:
        return None
    best = max(rates, key=rates.get)
    worst = min(rates, key=rates.get)
    return {
        "best_day": WEEKDAY_NAMES[best],
        "best_rate": round(rates[best] * 100),
        "worst_day": WEEKDAY_NAMES[worst],
        "worst_rate": round(rates[worst] * 100),
    }


def recovery_insight(today, window=60):
    """
    After a missed day, how fast do you bounce back?
    Fast recovery is the single best predictor of long-term consistency.
    """
    habits = list(Habit.objects.filter(active=True))
    rebounds = []
    for h in habits:
        done = logs_by_date(h)
        if len(done) < 10:
            continue
        start = today - dt.timedelta(days=window)
        days = list(daterange(start, today))
        for i, d in enumerate(days[:-1]):
            if d not in done and days[i + 1] in done:
                rebounds.append(1)
            elif d not in done and days[i + 1] not in done:
                rebounds.append(0)
    if not rebounds:
        return None
    rate = round(sum(rebounds) / len(rebounds) * 100)
    return {
        "rate": rate,
        "label": (
            "Elite recovery" if rate >= 80
            else "Solid recovery" if rate >= 60
            else "Bounce back faster" if rate >= 40
            else "Misses snowball for you"
        ),
    }


def goal_effort(objective, today):
    """
    How much work has actually gone into this goal, derived from its linked
    habits. Gives elapsed vs remaining time and a reality check on pace.
    """
    linked = objective.linked_habits or []
    analysis = {
        "linked": linked,
        "tracked_days": 0,
        "hit_days": 0,
        "effort_pct": None,
        "weekly_rate": None,
        "on_pace": None,
        "projection": None,
    }
    if not linked:
        return analysis

    start = objective.start_date or objective.created_at.date()
    end = objective.target_date
    window_end = today

    # resolve linked habit keys -> Habit rows (keys are slugs of names)
    habits = []
    for h in Habit.all_objects.all():
        key = "".join(c if c.isalnum() else "_" for c in h.name.lower()).strip("_")
        while "__" in key:
            key = key.replace("__", "_")
        if key in linked:
            habits.append(h)
    if not habits:
        return analysis

    total = 0
    hit = 0
    for d in daterange(start, window_end):
        for h in habits:
            total += 1
            if HabitLog.objects.filter(habit=h, date=d, done=True).exists():
                hit += 1

    analysis["tracked_days"] = (window_end - start).days + 1
    analysis["hit_days"] = hit
    if total:
        analysis["effort_pct"] = round(hit / total * 100)
        per_day = hit / total
        analysis["weekly_rate"] = round(per_day * 7 * 100)

    if end and end > start:
        elapsed = (window_end - start).days
        span = (end - start).days or 1
        expected = round(elapsed / span * 100)
        analysis["expected_pace_pct"] = expected
        if analysis["effort_pct"] is not None:
            analysis["on_pace"] = analysis["effort_pct"] >= expected - 10
            remaining_days = (end - window_end).days
            if analysis["weekly_rate"]:
                need = max(0, 100 - (analysis["effort_pct"] or 0))
                weeks_needed = need / max(1, analysis["weekly_rate"] / 100 * 100) if analysis["weekly_rate"] else None
                analysis["projection"] = (
                    "on track" if analysis["on_pace"]
                    else f"{remaining_days} days left — needs a stronger week"
                )
    return analysis


def build_stats(today=None):
    """Everything the Stats/Goals screens need, in one pass."""
    today = today or dt.date.today()
    habits = list(Habit.objects.filter(active=True))

    rows = []
    for h in habits:
        cur = current_streak(h, today)
        mom = momentum(h, today)
        rows.append({
            "id": h.id,
            "name": h.name,
            "emoji": h.emoji,
            "color": h.color,
            "status": h.status,
            "streak": cur,
            "best_streak": best_streak(h),
            "momentum": mom,
            "completion_30d": _completion(h, today, 30),
            "weekday": best_weekday(h),
        })

    return {
        "date": today.isoformat(),
        "habits": sorted(rows, key=lambda r: (-r["momentum"]["score"], -r["streak"])),
        "burnout": burnout_risk(today),
        "recovery": recovery_insight(today),
        "consistency_30d": _overall_completion(today, 30),
        "total_habits": len(habits),
    }


def _completion(habit, today, days):
    start = today - dt.timedelta(days=days - 1)
    done = logs_by_date(habit, start, today)
    return round(len(done) / days * 100)


def _overall_completion(today, days):
    habits = list(Habit.objects.filter(active=True))
    if not habits:
        return 0
    start = today - dt.timedelta(days=days - 1)
    total = days * len(habits)
    hit = sum(len(logs_by_date(h, start, today)) for h in habits)
    return round(hit / total * 100) if total else 0


# =====================================================================
# Legend-style training analytics
# =====================================================================
# Strength standards as multiples of bodyweight for the estimated 1RM, per
# lift family. These are the common (Strength Level / symmetric-strength
# style) brackets, keyed by the *exercise name* so we can grade any lift.
LIFT_STANDARDS = {
    "bench press": (0.50, 0.75, 1.00, 1.25, 1.50),
    "squat": (0.75, 1.25, 1.50, 2.00, 2.50),
    "deadlift": (1.00, 1.50, 2.00, 2.50, 3.00),
    "overhead press": (0.35, 0.55, 0.80, 1.00, 1.25),
    "barbell row": (0.50, 0.75, 1.00, 1.25, 1.50),
}
LEVELS = ["Beginner", "Novice", "Intermediate", "Advanced", "Elite"]


def strength_level(exercise_name, est_1rm, bodyweight_kg):
    """Grade a lift against bodyweight. Returns (level, ratio) or (None, None)."""
    if not est_1rm or not bodyweight_kg:
        return None, None
    key = (exercise_name or "").lower().strip()
    brackets = LIFT_STANDARDS.get(key)
    if not brackets:
        return None, None
    ratio = round(float(est_1rm) / float(bodyweight_kg), 2)
    level = LEVELS[0]
    for i, threshold in enumerate(brackets):
        if ratio >= threshold:
            level = LEVELS[min(i + 1, len(LEVELS) - 1)]
    return level, ratio


def working_sets(date=None, exercise_name=None):
    """Sets that count toward stats: completed, non-warm-up."""
    from .models import WorkoutSet

    qs = WorkoutSet.objects.filter(completed=True).exclude(
        set_type=WorkoutSet.TYPE_WARMUP
    )
    if date:
        qs = qs.filter(workout_exercise__date=date)
    if exercise_name:
        qs = qs.filter(workout_exercise__name__iexact=exercise_name)
    return qs


def exercise_history(exercise_name, limit=None):
    """Every day this exercise was performed, oldest first.

    One entry per date with its best working set — this is what the progress
    chart plots, and what "last time" compares against.
    """
    from .models import WorkoutExercise

    rows = (
        WorkoutExercise.objects.filter(name__iexact=exercise_name)
        .prefetch_related("sets")
        .order_by("date")
    )
    history = []
    for we in rows:
        sets = [s for s in we.sets.all() if s.completed and s.set_type != "warmup"]
        if not sets:
            continue
        best = max(sets, key=lambda s: s.volume_kg)
        history.append({
            "date": we.date.isoformat(),
            "best_set": f"{_num(best.weight_kg)}kg x {best.reps}",
            "top_weight": float(best.weight_kg or 0),
            "volume_kg": sum(s.volume_kg for s in sets),
            "total_reps": sum(s.reps or 0 for s in sets),
            "est_1rm": best.est_1rm,
        })
    if limit:
        history = history[-limit:]
    return history


def last_time_for(exercise_name, before_date):
    """What you did last time, to prefill today's targets (Legend's core idea)."""
    from .models import WorkoutExercise

    we = (
        WorkoutExercise.objects.filter(name__iexact=exercise_name, date__lt=before_date)
        .prefetch_related("sets")
        .order_by("-date")
        .first()
    )
    if not we:
        return None
    sets = [s for s in we.sets.all() if s.completed]
    working = [s for s in sets if s.set_type != "warmup"]
    if not working:
        return None
    best = max(working, key=lambda s: s.volume_kg)
    return {
        "date": we.date.isoformat(),
        "sets": [
            {
                "weight_kg": float(s.weight_kg) if s.weight_kg is not None else None,
                "reps": s.reps,
                "set_type": s.set_type,
                "rpe": float(s.rpe) if s.rpe is not None else None,
            }
            for s in sets
        ],
        "best_set": f"{_num(best.weight_kg)}kg x {best.reps}",
        "suggested_weight": float(best.weight_kg or 0),
        "suggested_reps": best.reps,
    }


def personal_bests(exercise_name):
    """Legend's PB block: heaviest set, best 1RM estimate, most reps, volume."""
    history = exercise_history(exercise_name)
    if not history:
        return None
    top_weight = max(history, key=lambda h: h["top_weight"])
    best_1rm = max(history, key=lambda h: h["est_1rm"] or 0)
    most_reps = max(history, key=lambda h: h["total_reps"])
    biggest_volume = max(history, key=lambda h: h["volume_kg"])
    return {
        "max_weight": {"value": top_weight["top_weight"], "date": top_weight["date"]},
        "best_est_1rm": {"value": best_1rm["est_1rm"], "date": best_1rm["date"]},
        "most_reps": {"value": most_reps["total_reps"], "date": most_reps["date"]},
        "max_volume": {"value": biggest_volume["volume_kg"], "date": biggest_volume["date"]},
    }


def gains_pct(exercise_name, window_days=90, today=None):
    """Progress measured by total weight moved: first vs latest session."""
    history = exercise_history(exercise_name)
    if len(history) < 2:
        return None
    today = today or dt.date.today()
    recent = [h for h in history if _parse(h["date"]) >= today - dt.timedelta(days=window_days)]
    if len(recent) < 2:
        recent = history[-2:]
    first, last = recent[0]["volume_kg"], recent[-1]["volume_kg"]
    if not first:
        return None
    return round((last - first) / first * 100, 1)


def muscle_fatigue(today=None, window_days=7):
    """Legend's fatigue map: sets per muscle over the window, most recent first.

    Returns sets (volume proxy) and days-since per muscle, so the UI can show
    a heat map: red = trained yesterday, cool = rested.
    """
    from .models import WorkoutExercise

    today = today or dt.date.today()
    start = today - dt.timedelta(days=window_days - 1)
    rows = (
        WorkoutExercise.objects.filter(date__gte=start, date__lte=today)
        .prefetch_related("sets")
    )
    muscles = {}
    for we in rows:
        muscle = we.muscle or "Other"
        working = [s for s in we.sets.all() if s.completed and s.set_type != "warmup"]
        if not working:
            continue
        entry = muscles.setdefault(muscle, {"sets": 0, "volume_kg": 0, "last_trained": None})
        entry["sets"] += len(working)
        entry["volume_kg"] += sum(s.volume_kg for s in working)
        d = we.date.isoformat()
        if entry["last_trained"] is None or d > entry["last_trained"]:
            entry["last_trained"] = d
    for muscle, entry in muscles.items():
        if entry["last_trained"]:
            entry["days_since"] = (today - _parse(entry["last_trained"])).days
    return dict(sorted(muscles.items(), key=lambda kv: -kv[1]["sets"]))


def plate_math(target_kg, bar_kg=20, plates=None):
    """Break a target weight into plates per side (Legend's plate calculator)."""
    if plates is None:
        plates = [25, 20, 15, 10, 5, 2.5, 1.25]
    target = float(target_kg or 0)
    if target < bar_kg:
        return {"possible": False, "per_side": [], "remainder": round(target, 2)}
    per_side_kg = (target - bar_kg) / 2
    per_side = []
    remaining = per_side_kg
    for p in sorted(plates, reverse=True):
        while remaining >= p - 1e-9:
            per_side.append(p)
            remaining -= p
    return {
        "possible": abs(remaining) < 1e-6,
        "bar_kg": bar_kg,
        "per_side": per_side,
        "per_side_kg": round(per_side_kg, 2),
        "remainder": round(remaining, 2),
    }


def _num(v):
    if v is None:
        return "0"
    f = float(v)
    return str(int(f)) if f == int(f) else str(f).rstrip("0").rstrip(".")


def _parse(iso):
    return dt.datetime.strptime(iso, "%Y-%m-%d").date()


# =====================================================================
# Range analytics — the Stats dashboard's single source of truth
# =====================================================================
def range_analytics(days=30, today=None):
    """Completion metrics for a date range, per-day and per-habit.

    Everything is derived from HabitLog rows. Days before a habit existed
    (i.e. before its earliest log) are excluded from that habit's denominator
    so a brand-new habit is never penalised for the days before it started.
    """
    today = today or dt.date.today()
    days = max(1, int(days))
    start = today - dt.timedelta(days=days - 1)
    habits = list(Habit.objects.filter(active=True))

    logs = HabitLog.objects.filter(date__gte=start, date__lte=today)
    per_habit_done = defaultdict(set)
    per_habit_skipped = defaultdict(set)
    per_habit_in_progress = defaultdict(set)
    per_day_done = defaultdict(set)   # date -> set of habit ids done
    per_day_in_progress = defaultdict(set)  # date -> set of habit ids started
    per_day_sched = defaultdict(set)  # date -> set of habit ids scheduled
    earliest = {}
    latest = {}

    for l in logs:
        if l.done:
            per_habit_done[l.habit_id].add(l.date)
            per_day_done[l.date].add(l.habit_id)
        elif l.status == HabitLog.STATUS_SKIPPED:
            per_habit_skipped[l.habit_id].add(l.date)
        elif l.status == HabitLog.STATUS_IN_PROGRESS:
            per_habit_in_progress[l.habit_id].add(l.date)
            per_day_in_progress[l.date].add(l.habit_id)
        per_day_sched[l.date].add(l.habit_id)
        if l.habit_id not in earliest or l.date < earliest[l.habit_id]:
            earliest[l.habit_id] = l.date
        if l.habit_id not in latest or l.date > latest[l.habit_id]:
            latest[l.habit_id] = l.date

    def habit_start(h):
        return earliest.get(h.id, start)

    # ---- per-day series (rate = done / scheduled that day) ----
    series = []
    for d in daterange(start, today):
        sched = set()
        for h in habits:
            hs = habit_start(h)
            if hs <= d:
                sched.add(h.id)
        done = per_day_done.get(d, set()) & sched
        rate = round(len(done) / len(sched) * 100) if sched else None
        series.append({
            "date": d.isoformat(),
            "weekday": WEEKDAY_NAMES[d.weekday()],
            "scheduled": len(sched),
            "done": len(done),
            "skipped": len(per_habit_skipped_ids(per_habit_skipped, sched, d)),
            "in_progress": len(per_day_in_progress.get(d, set()) & sched),
            "rate": rate,
        })

    # ---- per-habit rows ----
    prev_start = start - dt.timedelta(days=days)
    prev_end = start - dt.timedelta(days=1)
    rows = []
    for h in habits:
        hs = habit_start(h)
        w_start = max(start, hs)
        total_days = (today - w_start).days + 1
        done = {d for d in per_habit_done.get(h.id, set()) if d >= w_start}
        skipped = {d for d in per_habit_skipped.get(h.id, set()) if d >= w_start}
        missed = max(0, total_days - len(done) - len(skipped))
        completion = round(len(done) / total_days * 100) if total_days else 0

        # previous window for the "change" column
        p_done = len([d for d in per_habit_done.get(h.id, set()) if prev_start <= d <= prev_end])
        p_total = max(1, (prev_end - max(prev_start, hs)).days + 1)
        p_completion = round(p_done / p_total * 100) if p_total else 0

        rows.append({
            "id": h.id,
            "name": h.name,
            "emoji": h.emoji,
            "color": h.color,
            "completion": completion,
            "completed_days": len(done),
            "skipped_days": len(skipped),
            "missed_days": missed,
            "current_streak": current_streak(h, today),
            "best_streak": best_streak(h),
            "change": completion - p_completion,
            "days_tracked": total_days,
        })

    # ---- summary metrics ----
    def window_rate(n):
        w_start = today - dt.timedelta(days=n - 1)
        tot = hit = 0
        for h in habits:
            hs = habit_start(h)
            if hs > today:
                continue
            w_start_h = max(w_start, hs)
            span = (today - w_start_h).days + 1
            if span <= 0:
                continue
            tot += span
            hit += len([d for d in per_habit_done.get(h.id, set()) if d >= w_start_h])
        return round(hit / tot * 100) if tot else 0

    overall = window_rate(days)
    last7 = window_rate(7)
    prev7 = _window_rate_offset(per_habit_done, per_habit_skipped, habits, today, 7, 7)

    today_sched = [h.id for h in habits if habit_start(h) <= today]
    today_done = per_day_done.get(today, set()) & set(today_sched)
    today_skipped = {hid for hid in today_sched
                     if today in per_habit_skipped.get(hid, set())}

    # ---- insights ----
    insights = []
    if rows:
        best = max(rows, key=lambda r: r["completion"])
        worst = min(rows, key=lambda r: r["completion"])
        improving = max(rows, key=lambda r: r["change"])
        declining = min(rows, key=lambda r: r["change"])
        if best["completion"] > 0:
            insights.append({
                "kind": "most_consistent",
                "text": f'Most consistent: {best["emoji"]} {best["name"]} at {best["completion"]}%',
            })
        if improving["change"] > 0:
            insights.append({
                "kind": "improving",
                "text": f'Biggest improvement: {improving["emoji"]} {improving["name"]} '
                        f'({improving["change"]:+d} pts)',
            })
        if declining["change"] < 0:
            insights.append({
                "kind": "declining",
                "text": f'Needs attention: {declining["emoji"]} {declining["name"]} '
                        f'({declining["change"]:+d} pts)',
            })
        elif worst["completion"] < 40 and worst["days_tracked"] >= 5:
            insights.append({
                "kind": "attention",
                "text": f'Needs attention: {worst["emoji"]} {worst["name"]} '
                        f'at {worst["completion"]}%',
            })

    # best weekday from the series
    dow_tot = defaultdict(lambda: [0, 0])
    for s in series:
        if s["rate"] is None:
            continue
        dow_tot[s["weekday"]][0] += s["done"]
        dow_tot[s["weekday"]][1] += s["scheduled"]
    best_dow = None
    if dow_tot:
        best_dow = max(dow_tot.items(),
                       key=lambda kv: kv[1][0] / kv[1][1] if kv[1][1] else 0)[0]
        insights.append({"kind": "best_day", "text": f"Best day of the week: {best_dow}"})

    if days >= 14:
        insights.append({
            "kind": "week_compare",
            "text": f"This week {last7}% vs last week {prev7}%",
        })

    longest = max((r["best_streak"] for r in rows), default=0)
    if longest:
        insights.append({"kind": "longest", "text": f"Longest streak in range: {longest} days"})

    return {
        "days": days,
        "from": start.isoformat(),
        "to": today.isoformat(),
        "summary": {
            "overall": overall,
            "last_7": last7,
            "last_30": window_rate(30),
            "previous_7": prev7,
            "habit_count": len(habits),
            "done_today": len(today_done),
            "pending_today": len([h for h in today_sched if h not in today_done]),
            "skipped_today": len(today_skipped),
            "best_streak": longest,
        },
        "series": series,
        "habits": rows,
        "insights": insights,
    }


def per_habit_skipped_ids(per_habit_skipped, sched, d):
    return {hid for hid in sched if d in per_habit_skipped.get(hid, set())}


def _window_rate_offset(per_habit_done, per_habit_skipped, habits, today, span, offset):
    end = today - dt.timedelta(days=offset)
    start = end - dt.timedelta(days=span - 1)
    tot = hit = 0
    for h in habits:
        done = {d for d in per_habit_done.get(h.id, set()) if start <= d <= end}
        tot += span
        hit += len(done)
    return round(hit / tot * 100) if tot else 0
