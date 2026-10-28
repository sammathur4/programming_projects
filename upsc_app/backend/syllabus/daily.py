import hashlib
from datetime import date, timedelta
from django.utils import timezone


def filter_eligible_prelims(q):
    if q.get("stage") != "prelims":
        return False
    if not q.get("options"):
        return False
    if not q.get("answer"):
        return False
    return True


def filter_eligible_mains(q):
    if q.get("stage") != "mains":
        return False
    paper = (q.get("paper") or "").lower()
    if paper in ["gs1", "gs2", "gs3", "gs4", "sociology1", "sociology2"]:
        return True
    return False


def filter_eligible_essay(q):
    if q.get("stage") != "mains":
        return False
    paper = (q.get("paper") or "").lower()
    return paper == "essay"


def pick_daily(target_date, track, candidates, recent_daily_keys):
    if track == "prelims":
        eligible = [q for q in candidates if filter_eligible_prelims(q)]
    elif track == "mains":
        eligible = [q for q in candidates if filter_eligible_mains(q)]
    elif track == "essay":
        eligible = [q for q in candidates if filter_eligible_essay(q)]
    else:
        eligible = []

    if track != "essay" and recent_daily_keys:
        excluded = set(recent_daily_keys[-30:])
        filtered = [q for q in eligible if q["id"] not in excluded]
        if filtered:
            eligible = filtered

    if not eligible:
        if track == "prelims":
            eligible = [q for q in candidates if filter_eligible_prelims(q)]
        elif track == "mains":
            eligible = [q for q in candidates if filter_eligible_mains(q)]
        elif track == "essay":
            eligible = [q for q in candidates if filter_eligible_essay(q)]

    if not eligible:
        return None

    seed = f"{target_date.isoformat()}:{track}"
    idx = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(eligible)
    return eligible[idx]


def compute_streak(completed_dates_set, today):
    if not completed_dates_set:
        return {"current": 0, "longest": 0, "last_completed": None}

    dates = sorted(completed_dates_set)
    longest = 1
    current_run = 1
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            current_run += 1
        else:
            if current_run > longest:
                longest = current_run
            current_run = 1
    if current_run > longest:
        longest = current_run

    # compute current streak from today backwards
    current = 0
    check = today
    while check in completed_dates_set:
        current += 1
        check = check - timedelta(days=1)

    last_completed = dates[-1] if dates else None
    return {"current": current, "longest": longest, "last_completed": last_completed.isoformat() if last_completed else None}
