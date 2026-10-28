from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db import connection

from .local import local_learner_required
from .models import DailyChallenge, Attempt, AttemptResponse
from . import daily as daily_engine
from .views import _read_questions, _map_question, _load_hierarchy


@local_learner_required
def daily_challenge(request):
    today = timezone.localdate()
    questions = _read_questions()
    hierarchy = _load_hierarchy()
    for q in questions:
        _map_question(q, hierarchy)

    # recent daily keys
    recent_keys = list(
        DailyChallenge.objects.filter(date__gte=today - timezone.timedelta(days=60))
        .order_by("date", "track")
        .values_list("question_key", flat=True)
    )

    items = []
    for track in ["prelims", "mains", "essay"]:
        dc = DailyChallenge.objects.filter(date=today, track=track).first()
        if not dc:
            picked = daily_engine.pick_daily(today, track, questions, recent_keys)
            if picked:
                dc = DailyChallenge.objects.create(date=today, track=track, question_key=picked["id"])
            else:
                dc = None
        qobj = None
        if dc:
            qobj = next((x for x in questions if x["id"] == dc.question_key), None)
            if qobj:
                qobj.pop("answer", None)
                qobj.pop("explanation", None)
                qobj.pop("motivation", None)
        completed = False
        if dc and qobj:
            completed = AttemptResponse.objects.filter(
                question_key=dc.question_key,
                local_date=today,
            ).exists()
        items.append({"track": track, "question": qobj, "completed": completed, "result": None})

    # streak
    gold_dates = set()
    all_dates = set()
    for dc in DailyChallenge.objects.all():
        all_dates.add(dc.date)
        # gold if all 3 done that day? simplified: check
        pass

    # compute simple streak from days with >=1 completion? use requirement: gold = all 3
    days_done = set()
    for d in sorted(set(DailyChallenge.objects.values_list("date", flat=True))):
        cnt = 0
        for track in ["prelims", "mains", "essay"]:
            if AttemptResponse.objects.filter(question_key__in=DailyChallenge.objects.filter(date=d, track=track).values_list("question_key", flat=True), local_date=d).exists():
                cnt += 1
        if cnt >= 1:
            days_done.add(d)
        if cnt == 3:
            gold_dates.add(d)

    streak = daily_engine.compute_streak(days_done, today)
    streak["gold_count"] = len(gold_dates)
    streak["tier_today"] = 0
    cnt_today = 0
    for track in ["prelims", "mains", "essay"]:
        dc = DailyChallenge.objects.filter(date=today, track=track).first()
        if dc and AttemptResponse.objects.filter(question_key=dc.question_key, local_date=today).exists():
            cnt_today += 1
    if cnt_today == 1: streak["tier_today"] = 1
    elif cnt_today == 2: streak["tier_today"] = 2
    elif cnt_today == 3: streak["tier_today"] = 3

    # calendar last 365
    calendar = []
    for i in range(364, -1, -1):
        d = today - timezone.timedelta(days=i)
        g = d in gold_dates
        calendar.append({"date": d.isoformat(), "gold": g})

    return JsonResponse({
        "date": today.isoformat(),
        "items": items,
        "streak": streak,
        "calendar": calendar,
    })


@local_learner_required
def dashboard(request):
    today = timezone.localdate()
    week = []
    for i in range(6, -1, -1):
        d = today - timezone.timedelta(days=i)
        week.append({"date": d.isoformat()})
    return JsonResponse({
        "date": today.isoformat(),
        "daily": {"items": []},
        "streak": {},
        "week": week,
        "recent_submissions": [],
        "exam_countdown": None,
        "plan": [],
    })
