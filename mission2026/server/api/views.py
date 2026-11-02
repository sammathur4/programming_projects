"""REST endpoints for the Mission 2026 app (Flutter clients + WhatsApp bot)."""
import datetime as dt

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import analytics
from .models import (
    DRINK_PRESETS,
    BodyMeasurement,
    CheckinMember,
    DailyCheckin,
    DiaryEntry,
    DrinkLog,
    Exercise,
    FitnessDay,
    Food,
    GoalCheckpoint,
    Habit,
    HabitLog,
    IntakeLog,
    JaapLog,
    JaapMantra,
    Note,
    NutritionTarget,
    Objective,
    Setting,
    StudyActivity,
    StudyDay,
    StudyResource,
    WeightLog,
    WorkoutExercise,
    WorkoutModule,
    WorkoutSet,
)
from .serializers import (
    BodyMeasurementSerializer,
    CheckinMemberSerializer,
    DailyCheckinSerializer,
    DiaryEntrySerializer,
    DrinkLogSerializer,
    ExerciseSerializer,
    FitnessDaySerializer,
    FoodSerializer,
    GoalCheckpointSerializer,
    HabitLogSerializer,
    HabitSerializer,
    IntakeLogSerializer,
    JaapLogSerializer,
    JaapMantraSerializer,
    NoteSerializer,
    NutritionTargetSerializer,
    ObjectiveSerializer,
    SettingSerializer,
    StudyActivitySerializer,
    StudyDaySerializer,
    StudyResourceSerializer,
    WeightLogSerializer,
    WorkoutExerciseSerializer,
    WorkoutModuleSerializer,
    WorkoutSetSerializer,
)


def parse_date(s, default=None):
    try:
        return dt.date.fromisoformat(s)
    except (TypeError, ValueError):
        return default


def habit_key(name):
    """'5L Water' -> '5l_water' (must match the bot's slug())."""
    key = "".join(c if c.isalnum() else "_" for c in (name or "").lower())
    while "__" in key:
        key = key.replace("__", "_")
    return key.strip("_")


def sync_checkin_to_habit_logs(date, done_keys, missed_keys, in_progress_keys=None, pending_keys=None):
    """Mirror a WhatsApp check-in into HabitLog so the app's Today screen sees it.

    The app reads HabitLog (overview/), the bot writes DailyCheckin — this keeps
    the two in step. Only habits the app knows about are touched; the same
    habit_key() mapping the bot uses ties them together.

    `in_progress_keys` is a third bucket: started but not finished. It is
    neither done nor missed, so it is written as its own status and never
    inflates the done/missed counts.

    `pending_keys` explicitly clears a habit back to "not started" — without
    it, a habit the member had already marked done would keep that status.

    Returns {habit_key: status} for everything that was written.
    """
    done_keys = list(done_keys or [])
    missed_keys = list(missed_keys or [])
    in_progress_keys = list(in_progress_keys or [])
    pending_keys = list(pending_keys or [])
    if not any([done_keys, missed_keys, in_progress_keys, pending_keys]):
        return {}

    wanted = {}
    for name in done_keys:
        wanted[name] = HabitLog.STATUS_DONE
    for name in missed_keys:
        wanted[name] = HabitLog.STATUS_SKIPPED
    for name in in_progress_keys:
        wanted[name] = HabitLog.STATUS_IN_PROGRESS
    for name in pending_keys:
        wanted[name] = HabitLog.STATUS_PENDING
    if not wanted:
        return {}

    # habit_key(h.name) → habit, so a check-in's slug finds its Habit row
    by_key = {habit_key(h.name): h for h in Habit.objects.all()}

    written = {}
    for key, target_status in wanted.items():
        habit = by_key.get(key)
        if not habit:
            continue  # a habit the bot knows but the app doesn't (yet)
        # all_objects: a soft-deleted row still occupies (habit, date) thanks to
        # unique_together, so we must find and resurrect it rather than insert.
        log = HabitLog.all_objects.filter(habit=habit, date=date).first()
        if not log:
            log = HabitLog(habit=habit, date=date)
        elif log.deleted_at:
            log.deleted_at = None
        log.set_status(target_status)
        log.save()
        written[key] = target_status
    return written


class ApiKeyMixin:
    """Optional shared-secret protection (MISSION_API_KEY env var)."""

    def initial(self, request, *args, **kwargs):
        from django.conf import settings

        key = getattr(settings, "MISSION_API_KEY", "")
        if key and request.headers.get("X-API-Key") != key:
            return Response(
                {"detail": "Missing/invalid X-API-Key"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return super().initial(request, *args, **kwargs)


def decorate_habits(habits, today=None):
    today = today or dt.date.today()
    for h in habits:
        h._streak = analytics.current_streak(h, today)
        h._best_streak = analytics.best_streak(h)
        h._completion_30d = analytics._completion(h, today, 30)
    return habits


def habits_with_marks(habits, today=None):
    """decorate_habits + the last 30 days of done dates per habit."""
    today = today or dt.date.today()
    decorate_habits(habits, today)
    start = today - dt.timedelta(days=29)
    marks = {}
    for l in HabitLog.objects.filter(date__gte=start, date__lte=today, done=True):
        marks.setdefault(l.habit_id, []).append(l.date.isoformat())
    for h in habits:
        h._marks = sorted(marks.get(h.id, []))
    return habits


# ---------------------------------------------------------------- habits
class HabitsView(ApiKeyMixin, APIView):
    def get(self, request):
        qs = Habit.objects.all()
        status_q = request.query_params.get("status")
        if status_q:
            qs = qs.filter(status=status_q)
        if request.query_params.get("include_deleted") == "1":
            qs = Habit.all_objects.all()
        habits = habits_with_marks(list(qs))
        return Response(HabitSerializer(habits, many=True).data)

    def post(self, request):
        data = dict(request.data)
        data.setdefault("order", (Habit.objects.count() or 0) + 1)
        ser = HabitSerializer(data=data)
        ser.is_valid(raise_exception=True)
        habit = ser.save()
        return Response(HabitSerializer(decorate_habits([habit])[0]).data, status=status.HTTP_201_CREATED)


class HabitDetailView(ApiKeyMixin, APIView):
    def _get(self, pk):
        return Habit.all_objects.filter(pk=pk).first()

    def get(self, request, pk):
        habit = self._get(pk)
        if not habit:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(HabitSerializer(decorate_habits([habit])[0]).data)

    def patch(self, request, pk):
        habit = self._get(pk)
        if not habit:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = HabitSerializer(habit, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(HabitSerializer(decorate_habits([habit])[0]).data)

    def delete(self, request, pk):
        """Soft delete (habit disappears from the app, history is kept)."""
        habit = self._get(pk)
        if not habit:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        habit.delete()  # soft
        return Response({"deleted": pk, "soft": True})


class HabitActionView(ApiKeyMixin, APIView):
    """POST habits/{pk}/<action>/ — pause, resume, restart, restore."""

    ACTIONS = {"pause", "resume", "restart", "restore", "archive"}

    def post(self, request, pk, action):
        if action not in self.ACTIONS:
            return Response({"detail": f"unknown action {action}"}, status=status.HTTP_400_BAD_REQUEST)
        habit = Habit.all_objects.filter(pk=pk).first()
        if not habit:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)

        if action == "pause":
            habit.pause()
        elif action == "resume":
            habit.restore() if habit.deleted_at else None
            habit.resume()
        elif action == "archive":
            habit.active = False
            habit.save(update_fields=["active", "updated_at"])
        elif action == "restore":
            habit.restore()
            habit.active = True
            habit.resume()
        elif action == "restart":
            # keep history, clear the streak by "starting fresh" today
            habit.restore()
            habit.resume()
            habit.active = True
            habit.save(update_fields=["active", "status", "paused_at", "updated_at"])
        return Response(HabitSerializer(decorate_habits([habit])[0]).data)


class HabitToggleView(ApiKeyMixin, APIView):
    """POST {habit, date, done?, status?, cycle?, value?, note?}

    - `cycle: true` advances the day's status: untouched → done → pending →
      skipped → done … (matches the app's tap-to-cycle button)
    - `status: "pending"|"in_progress"|"done"|"skipped"` sets it explicitly
    - `done: true/false` legacy mirror, still supported
    """

    def post(self, request):
        habit_id = request.data.get("habit")
        date = parse_date(request.data.get("date"), dt.date.today())
        habit = Habit.objects.filter(pk=habit_id).first()
        if not habit:
            return Response({"detail": "habit not found"}, status=status.HTTP_404_NOT_FOUND)

        # Validate the status BEFORE touching the database. A rejected request
        # must not leave a half-written row behind.
        requested_status = request.data.get("status")
        if "status" in request.data and requested_status not in HabitLog.STATUSES:
            return Response(
                {
                    "detail": "invalid status",
                    "status": requested_status,
                    "allowed": list(HabitLog.STATUSES),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.db import IntegrityError, transaction

        log = HabitLog.all_objects.filter(habit=habit, date=date).first()
        if log is None:
            try:
                with transaction.atomic():
                    log = HabitLog.objects.create(
                        habit=habit, date=date, status=HabitLog.STATUS_PENDING, done=False
                    )
            except IntegrityError:
                # a concurrent request won the race — reuse its row
                log = HabitLog.all_objects.filter(habit=habit, date=date).first()
        if log is None:
            return Response({"detail": "could not create log"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if getattr(log, "deleted_at", None):
            # resurrect a soft-deleted row so corrections work on old days
            log.deleted_at = None
            log.save(update_fields=["deleted_at", "updated_at"])

        if request.data.get("cycle"):
            # pending → done → skipped → pending.
            # An in-progress habit cycles forward to done, so a half-finished
            # day can be completed with one more tap.
            order = {
                "": HabitLog.STATUS_PENDING,
                HabitLog.STATUS_PENDING: HabitLog.STATUS_DONE,
                HabitLog.STATUS_IN_PROGRESS: HabitLog.STATUS_DONE,
                HabitLog.STATUS_DONE: HabitLog.STATUS_SKIPPED,
                HabitLog.STATUS_SKIPPED: HabitLog.STATUS_PENDING,
            }
            log.set_status(order.get(log.status, HabitLog.STATUS_PENDING))
        elif "status" in request.data:
            # Already validated above, so this is a known status.
            log.set_status(requested_status)
        elif "done" in request.data:
            log.set_status(
                HabitLog.STATUS_DONE if bool(request.data["done"]) else HabitLog.STATUS_PENDING
            )
        else:
            # legacy flip
            log.set_status(HabitLog.STATUS_PENDING if log.done else HabitLog.STATUS_DONE)

        if "value" in request.data:
            v = request.data["value"]
            log.value = None if v in (None, "") else v
        if "note" in request.data:
            log.note = request.data.get("note") or ""
        log.save()

        return Response({
            "habit": habit.id,
            "date": date.isoformat(),
            "status": log.status or HabitLog.STATUS_PENDING,
            "done": log.done,
            "value": log.value,
            "note": log.note,
        })


class HabitLogsView(ApiKeyMixin, APIView):
    """GET ?from&to&habit — habit logs with notes, for the grid + day notes."""

    def get(self, request):
        d_from = parse_date(request.query_params.get("from")) or (dt.date.today() - dt.timedelta(days=29))
        d_to = parse_date(request.query_params.get("to")) or dt.date.today()
        qs = HabitLog.objects.filter(date__gte=d_from, date__lte=d_to)
        habit_id = request.query_params.get("habit")
        if habit_id and habit_id.isdigit():
            qs = qs.filter(habit_id=int(habit_id))
        if request.query_params.get("done_only") == "1":
            qs = qs.filter(done=True)
        return Response([
            {
                "habit": l.habit_id,
                "date": l.date.isoformat(),
                "status": l.status or ("done" if l.done else "pending"),
                "done": l.done,
                "value": l.value,
                "note": l.note,
            }
            for l in qs
        ])


class HabitNoteView(ApiKeyMixin, APIView):
    """POST habits/{pk}/note/ {date, note} — per-habit, per-day note (legacy)."""

    def post(self, request, pk):
        habit = Habit.objects.filter(pk=pk).first()
        if not habit:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        date = parse_date(request.data.get("date"), dt.date.today())
        log, _ = HabitLog.objects.get_or_create(habit=habit, date=date)
        log.note = request.data.get("note") or ""
        log.save(update_fields=["note", "updated_at"])
        return Response({"habit": pk, "date": date.isoformat(), "note": log.note})


class HabitNotesView(ApiKeyMixin, APIView):
    """GET/POST habits/{pk}/notes/ — append-only list of notes on a habit.

    Notes live in the shared Note feed (tag='habit', ref=habit name), so they
    also show up in the Notes screen. GET returns newest-first.
    """

    def _habit(self, pk):
        return Habit.objects.filter(pk=pk).first()

    def get(self, request, pk):
        habit = self._habit(pk)
        if not habit:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        qs = Note.objects.filter(tag=Note.TAG_HABIT, ref=habit.name)
        d = parse_date(request.query_params.get("date"))
        if d:
            qs = qs.filter(date=d)
        return Response([
            {
                "id": n.id,
                "date": n.date.isoformat(),
                "text": n.text,
                "pinned": n.pinned,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in qs[:100]
        ])

    def post(self, request, pk):
        habit = self._habit(pk)
        if not habit:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        text = (request.data.get("text") or "").strip()
        if not text:
            return Response({"detail": "text is required"}, status=status.HTTP_400_BAD_REQUEST)
        date = parse_date(request.data.get("date"), dt.date.today())
        n = Note.objects.create(date=date, tag=Note.TAG_HABIT, ref=habit.name, text=text)
        return Response(
            {"id": n.id, "date": n.date.isoformat(), "text": n.text, "pinned": n.pinned},
            status=status.HTTP_201_CREATED,
        )


class HabitHeatmapView(ApiKeyMixin, APIView):
    """GET ?days=90 — grid data + 30-day trend for the Habits screen."""

    def get(self, request):
        days = int(request.query_params.get("days", 90) or 90)
        today = dt.date.today()
        start = today - dt.timedelta(days=days - 1)
        habits = decorate_habits(list(Habit.objects.all()))
        logs = HabitLog.objects.filter(date__gte=start, date__lte=today)
        marks = {}
        for l in logs:
            if l.done:
                marks.setdefault(l.date.isoformat(), []).append(l.habit_id)
        return Response({
            "from": start.isoformat(),
            "to": today.isoformat(),
            "habits": HabitSerializer(habits, many=True).data,
            "marks": marks,
        })


# ---------------------------------------------------------------- fitness
class FitnessListView(ApiKeyMixin, APIView):
    def get(self, request):
        qs = FitnessDay.objects.all()
        d_from = parse_date(request.query_params.get("from"))
        d_to = parse_date(request.query_params.get("to"))
        if d_from:
            qs = qs.filter(date__gte=d_from)
        if d_to:
            qs = qs.filter(date__lte=d_to)
        limit = request.query_params.get("limit")
        if limit and limit.isdigit():
            qs = qs[: int(limit)]
        return Response(FitnessDaySerializer(qs, many=True).data)


class FitnessDayView(ApiKeyMixin, APIView):
    def get(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        obj, _ = FitnessDay.objects.get_or_create(date=d)
        return Response(FitnessDaySerializer(obj).data)

    def put(self, request, date):
        return self._upsert(request, date, partial=False)

    def patch(self, request, date):
        return self._upsert(request, date, partial=True)

    def _upsert(self, request, date, partial):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        obj, _ = FitnessDay.objects.get_or_create(date=d)
        data = dict(request.data)
        data["date"] = d.isoformat()
        ser = FitnessDaySerializer(obj, data=data, partial=partial)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class FitnessAnalyticsView(ApiKeyMixin, APIView):
    """Weight trend, calorie adherence, training volume, streaks."""

    def get(self, request):
        today = dt.date.today()
        days = int(request.query_params.get("days", 30) or 30)
        start = today - dt.timedelta(days=days - 1)

        weights = list(
            FitnessDay.objects.exclude(weight_kg__isnull=True)
            .order_by("date").values_list("date", "weight_kg")
        )
        series = [{"date": d.isoformat(), "kg": float(w)} for d, w in weights]

        recent = [s for s in series if s["date"] >= start.isoformat()]
        first_w = series[0]["kg"] if series else None
        last_w = series[-1]["kg"] if series else None
        # 7-day rate of change (kg/week) — the number that actually matters
        weekly_rate = None
        if len(series) >= 2:
            cutoff = (today - dt.timedelta(days=7)).isoformat()
            week = [s for s in series if s["date"] >= cutoff]
            if len(week) >= 2:
                span = (dt.date.fromisoformat(week[-1]["date"]) - dt.date.fromisoformat(week[0]["date"])).days or 1
                weekly_rate = round((week[-1]["kg"] - week[0]["kg"]) / span * 7, 2)

        # calorie adherence (target from Settings, default 1800)
        target = 1800
        s = Setting.objects.filter(key="fit_daily_calorie").first()
        if s and str(s.value).isdigit():
            target = int(s.value)
        cal_days = FitnessDay.objects.filter(date__gte=start, calories_in__isnull=False)
        cals = [c for c in cal_days.values_list("calories_in", flat=True)]
        on_target = sum(1 for c in cals if c <= target)
        adherence = round(on_target / len(cals) * 100) if cals else None

        # training volume
        workouts = FitnessDay.objects.filter(date__gte=start)
        workout_days = workouts.filter(exercises__isnull=False).exclude(exercises=[]).count()
        total_sets = 0
        for ex in workouts.values_list("exercises", flat=True):
            for item in ex or []:
                try:
                    total_sets += int(item.get("sets") or 0)
                except (TypeError, ValueError):
                    pass

        water_days = [
            float(w) for w in FitnessDay.objects.filter(
                date__gte=start, water_litres__isnull=False
            ).values_list("water_litres", flat=True)
        ]
        return Response({
            "days": days,
            "series": series,
            "recent": recent,
            "first": first_w,
            "latest": last_w,
            "lost_kg": round(first_w - last_w, 1) if first_w and last_w else None,
            "weekly_rate_kg": weekly_rate,
            "goal_weight": 75.0,
            "calorie_target": target,
            "calorie_adherence_pct": adherence,
            "workout_days": workout_days,
            "total_sets": total_sets,
            "avg_water_l": round(sum(water_days) / len(water_days), 2) if water_days else None,
        })


class FitnessExerciseView(ApiKeyMixin, APIView):
    """POST fitness/{date}/exercise/ {name, sets, reps, weight_kg, muscle} — add.
    DELETE ?index=N removes one."""

    def post(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        obj, _ = FitnessDay.objects.get_or_create(date=d)
        item = {
            "name": (request.data.get("name") or "").strip(),
            "sets": request.data.get("sets"),
            "reps": request.data.get("reps"),
            "weight_kg": request.data.get("weight_kg"),
            "muscle": (request.data.get("muscle") or "").strip(),
        }
        if not item["name"]:
            return Response({"detail": "name required"}, status=status.HTTP_400_BAD_REQUEST)
        obj.exercises = (obj.exercises or []) + [item]
        muscles = {m.strip() for m in (obj.muscles or "").split(",") if m.strip()}
        if item["muscle"]:
            muscles.add(item["muscle"])
        obj.muscles = ", ".join(sorted(muscles))
        obj.save(update_fields=["exercises", "muscles", "updated_at"])
        return Response(FitnessDaySerializer(obj).data)

    def delete(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        obj = FitnessDay.objects.filter(date=d).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        idx = request.query_params.get("index")
        if idx is not None and idx.isdigit() and int(idx) < len(obj.exercises or []):
            items = list(obj.exercises)
            items.pop(int(idx))
            obj.exercises = items
            obj.save(update_fields=["exercises", "updated_at"])
        return Response(FitnessDaySerializer(obj).data)


class FitnessCardioView(ApiKeyMixin, APIView):
    """POST fitness/{date}/cardio/ {type, quantity, unit, minutes} — add."""

    def post(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        obj, _ = FitnessDay.objects.get_or_create(date=d)
        item = {
            "type": (request.data.get("type") or "").strip(),
            "quantity": request.data.get("quantity"),
            "unit": (request.data.get("unit") or "").strip(),
            "minutes": request.data.get("minutes"),
        }
        if not item["type"]:
            return Response({"detail": "type required"}, status=status.HTTP_400_BAD_REQUEST)
        obj.cardio_items = (obj.cardio_items or []) + [item]
        obj.cardio = ", ".join(
            f"{c['type']} {c.get('quantity') or ''}{c.get('unit') or ''}".strip()
            for c in obj.cardio_items
        )
        obj.save(update_fields=["cardio_items", "cardio", "updated_at"])
        return Response(FitnessDaySerializer(obj).data)

    def delete(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        obj = FitnessDay.objects.filter(date=d).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        idx = request.query_params.get("index")
        if idx is not None and idx.isdigit() and int(idx) < len(obj.cardio_items or []):
            items = list(obj.cardio_items)
            items.pop(int(idx))
            obj.cardio_items = items
            obj.cardio = ", ".join(
                f"{c['type']} {c.get('quantity') or ''}{c.get('unit') or ''}".strip()
                for c in items
            )
            obj.save(update_fields=["cardio_items", "cardio", "updated_at"])
        return Response(FitnessDaySerializer(obj).data)


# ---------------------------------------------------------------- study
class StudyListView(ApiKeyMixin, APIView):
    def get(self, request):
        qs = StudyDay.objects.all()
        d_from = parse_date(request.query_params.get("from"))
        d_to = parse_date(request.query_params.get("to"))
        if d_from:
            qs = qs.filter(date__gte=d_from)
        if d_to:
            qs = qs.filter(date__lte=d_to)
        return Response(StudyDaySerializer(qs, many=True).data)


class StudyDayView(ApiKeyMixin, APIView):
    def get(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        obj, _ = StudyDay.objects.get_or_create(date=d)
        return Response(StudyDaySerializer(obj).data)

    def put(self, request, date):
        return self._upsert(request, date, partial=False)

    def patch(self, request, date):
        return self._upsert(request, date, partial=True)

    def _upsert(self, request, date, partial):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        obj, _ = StudyDay.objects.get_or_create(date=d)
        data = dict(request.data)
        data["date"] = d.isoformat()
        ser = StudyDaySerializer(obj, data=data, partial=partial)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class StudyAnalyticsView(ApiKeyMixin, APIView):
    """Study volume vs mode targets, subject breakdown, in-progress totals."""

    def get(self, request):
        today = dt.date.today()
        days = int(request.query_params.get("days", 30) or 30)
        start = today - dt.timedelta(days=days - 1)
        qs = StudyDay.objects.filter(date__gte=start, date__lte=today)

        mode_targets = {}
        for mode in ("WFO", "WFH", "Holiday"):
            s = Setting.objects.filter(key=f"study_target_{mode}").first()
            if s:
                mode_targets[mode] = s.value

        def target_for(mode):
            v = mode_targets.get(mode or "", "")
            try:
                return int("".join(c for c in v.split("|")[0] if c.isdigit()) or 0)
            except (ValueError, IndexError):
                return 0

        total_hours = 0.0
        total_aw = 0
        total_mcq = 0
        target_hit = 0
        target_due = 0
        per_subject = {}
        per_mode = {}

        for day in qs:
            hours = float(day.study_hours or 0)
            total_hours += hours
            total_aw += day.aw_count or 0
            total_mcq += day.mcq_count or 0
            m = (day.mode or "").strip()
            if m:
                per_mode.setdefault(m, {"days": 0, "hours": 0.0})
                per_mode[m]["days"] += 1
                per_mode[m]["hours"] = round(per_mode[m]["hours"] + hours, 1)
                aw_target = target_for(m)
                if aw_target:
                    target_due += 1
                    if (day.aw_count or 0) >= aw_target:
                        target_hit += 1
            for slot in day.slots or []:
                subj = (slot.get("subject") or "").strip()
                if not subj:
                    continue
                rec = per_subject.setdefault(subj, {"done": 0, "missed": 0, "total": 0})
                rec["total"] += 1
                if str(slot.get("status", "")).lower() == "done":
                    rec["done"] += 1
                else:
                    rec["missed"] += 1

        resources = {}
        for track in ("pending", "in_progress", "completed"):
            items = StudyResource.objects.filter(track=track)
            videos = sum(i.videos or 0 for i in items)
            done = sum(i.videos_done or 0 for i in items)
            resources[track] = {
                "items": items.count(),
                "videos": videos,
                "videos_done": done,
                "pct": round(done / videos * 100) if videos else 0,
            }

        # Detailed activity records (MCQ / answer-writing / revision / mocks)
        acts = StudyActivity.objects.filter(date__gte=start, date__lte=today)
        act_minutes = sum(a.time_spent_minutes or 0 for a in acts)
        act_attempted = sum(a.questions_attempted or 0 for a in acts)
        act_completed = sum(a.questions_completed or 0 for a in acts)
        act_correct = sum(a.correct_answers or 0 for a in acts)
        act_incorrect = sum(a.incorrect_answers or 0 for a in acts)
        act_answers = sum(a.answers_written or 0 for a in acts)
        by_type = {}
        for a in acts:
            rec = by_type.setdefault(a.activity_type, {"count": 0, "minutes": 0, "attempted": 0, "completed": 0, "answers": 0})
            rec["count"] += 1
            rec["minutes"] += a.time_spent_minutes or 0
            rec["attempted"] += a.questions_attempted or 0
            rec["completed"] += a.questions_completed or 0
            rec["answers"] += a.answers_written or 0

        return Response({
            "days": days,
            "total_hours": round(total_hours + act_minutes / 60, 1),
            "avg_hours_per_day": round((total_hours + act_minutes / 60) / max(1, qs.count()), 1),
            "total_aw": total_aw + act_answers,
            "total_mcq": total_mcq + act_completed,
            "activity": {
                "records": acts.count(),
                "minutes": act_minutes,
                "attempted": act_attempted,
                "completed": act_completed,
                "correct": act_correct,
                "incorrect": act_incorrect,
                "answers_written": act_answers,
                "accuracy": round(act_correct / (act_correct + act_incorrect) * 100)
                if (act_correct + act_incorrect) else None,
                "by_type": [
                    {"type": k, **v} for k, v in sorted(by_type.items(), key=lambda kv: -kv[1]["minutes"])
                ],
            },
            "target_hit_days": target_hit,
            "target_due_days": target_due,
            "target_adherence_pct": round(target_hit / target_due * 100) if target_due else None,
            "per_subject": [
                {"subject": k, **v, "pct": round(v["done"] / v["total"] * 100) if v["total"] else 0}
                for k, v in sorted(per_subject.items(), key=lambda kv: -kv[1]["total"])
            ],
            "per_mode": per_mode,
            "mode_targets": mode_targets,
            "resources": resources,
            "days_logged": qs.count(),
        })


# ---------------------------------------------------------------- resources
class StudyResourcesView(ApiKeyMixin, APIView):
    def get(self, request):
        qs = StudyResource.objects.all()
        track = request.query_params.get("track")
        if track:
            qs = qs.filter(track=track)
        exam = request.query_params.get("exam")
        if exam:
            qs = qs.filter(exam__iexact=exam)
        status_q = request.query_params.get("status")
        if status_q:
            qs = qs.filter(status__iexact=status_q)
        return Response(StudyResourceSerializer(qs, many=True).data)

    def post(self, request):
        data = dict(request.data)
        # keep the sheet-facing status in step with the board column
        track = data.get("track")
        if track and not data.get("status"):
            data["status"] = {
                "pending": "Pending",
                "in_progress": "In-Progress",
                "completed": "Completed",
            }.get(track, "Pending")
        ser = StudyResourceSerializer(data=data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class StudyResourceDetailView(ApiKeyMixin, APIView):
    def patch(self, request, pk):
        obj = StudyResource.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        data = dict(request.data)
        track = data.get("track")
        if track and not data.get("status"):
            data["status"] = {
                "pending": "Pending",
                "in_progress": "In-Progress",
                "completed": "Completed",
            }.get(track, obj.status)
        ser = StudyResourceSerializer(obj, data=data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        obj = StudyResource.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()  # soft
        return Response({"deleted": pk, "soft": True})


class StudyResourceMoveView(ApiKeyMixin, APIView):
    """POST resources/{pk}/move/ {track} — pending / in_progress / completed."""

    def post(self, request, pk):
        obj = StudyResource.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        track = (request.data.get("track") or "").strip()
        if track not in ("pending", "in_progress", "completed"):
            return Response({"detail": "bad track"}, status=status.HTTP_400_BAD_REQUEST)
        obj.track = track
        obj.moved_at = timezone.now()
        # keep the sheet-facing status in step with the board column
        obj.status = {"pending": "Pending", "in_progress": "In-Progress", "completed": "Completed"}[track]
        if track == "completed" and not obj.videos_done and obj.videos:
            obj.videos_done = obj.videos
        obj.save()
        return Response(StudyResourceSerializer(obj).data)


# ---------------------------------------------------------------- goals
def decorate_goals(objs, today=None):
    today = today or dt.date.today()
    for o in objs:
        start = o.start_date or o.created_at.date()
        o._days_elapsed = (today - start).days
        o._days_left = (o.target_date - today).days if o.target_date else None
        o._habit_analysis = analytics.goal_effort(o, today)
        # progress: prefer habit-derived effort, else manual value
        eff = o._habit_analysis.get("effort_pct")
        o._progress = eff if eff is not None else o.progress_pct
    return objs


class ObjectivesView(ApiKeyMixin, APIView):
    def get(self, request):
        qs = Objective.objects.all()
        status_q = request.query_params.get("status")
        if status_q:
            qs = qs.filter(status=status_q)
        if request.query_params.get("include_deleted") == "1":
            qs = Objective.all_objects.all()
        return Response(ObjectiveSerializer(decorate_goals(list(qs)), many=True).data)

    def post(self, request):
        data = dict(request.data)
        data.setdefault("order", (Objective.objects.count() or 0) + 1)
        ser = ObjectiveSerializer(data=data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        if not obj.start_date:
            obj.start_date = dt.date.today()
            obj.save(update_fields=["start_date"])
        return Response(ObjectiveSerializer(decorate_goals([obj])[0]).data, status=status.HTTP_201_CREATED)


class ObjectiveDetailView(ApiKeyMixin, APIView):
    def get(self, request, pk):
        obj = Objective.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(ObjectiveSerializer(decorate_goals([obj])[0]).data)

    def patch(self, request, pk):
        obj = Objective.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = ObjectiveSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ObjectiveSerializer(decorate_goals([obj])[0]).data)

    def delete(self, request, pk):
        obj = Objective.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()  # soft
        return Response({"deleted": pk, "soft": True})


class ObjectiveActionView(ApiKeyMixin, APIView):
    """POST objectives/{pk}/<action>/ — pause, resume, restart, complete, restore."""

    ACTIONS = {"pause", "resume", "restart", "complete", "restore"}

    def post(self, request, pk, action):
        if action not in self.ACTIONS:
            return Response({"detail": "bad action"}, status=status.HTTP_400_BAD_REQUEST)
        obj = Objective.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)

        if action == "pause":
            obj.status = Objective.STATUS_PAUSED
            obj.paused_at = timezone.now()
        elif action == "resume":
            if obj.paused_at:
                obj.paused_days = (obj.paused_days or 0) + (timezone.now() - obj.paused_at).days
            obj.status = Objective.STATUS_ACTIVE
            obj.paused_at = None
            obj.deleted_at = None
        elif action == "restart":
            obj.status = Objective.STATUS_ACTIVE
            obj.start_date = dt.date.today()
            obj.paused_at = None
            obj.paused_days = 0
            obj.progress_pct = 0
            obj.deleted_at = None
        elif action == "complete":
            obj.status = Objective.STATUS_DONE
            obj.progress_pct = 100
        elif action == "restore":
            obj.deleted_at = None
            obj.status = Objective.STATUS_ACTIVE
        obj.save()
        return Response(ObjectiveSerializer(decorate_goals([obj])[0]).data)


class ObjectiveCheckpointView(ApiKeyMixin, APIView):
    """POST objectives/{pk}/checkpoint/ {progress_pct, note, date} — log progress."""

    def post(self, request, pk):
        obj = Objective.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        date = parse_date(request.data.get("date"), dt.date.today())
        pct = request.data.get("progress_pct")
        cp = GoalCheckpoint.objects.create(
            objective=obj,
            date=date,
            progress_pct=int(pct) if pct not in (None, "") else obj.progress_pct,
            note=request.data.get("note") or "",
        )
        if pct not in (None, ""):
            obj.progress_pct = int(pct)
            obj.save(update_fields=["progress_pct", "updated_at"])
        return Response(GoalCheckpointSerializer(cp).data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------- misc
class SettingsView(ApiKeyMixin, APIView):
    """GET settings/ — every key/value row.

    POST settings/ {key, value} upserts one row, so the app can persist
    preferences (server URL, height, goal weight…) without a migration.
    """

    def get(self, request):
        return Response(SettingSerializer(Setting.objects.all(), many=True).data)

    def post(self, request):
        key = (request.data.get("key") or "").strip()
        if not key:
            return Response({"detail": "key required"}, status=status.HTTP_400_BAD_REQUEST)
        if len(key) > 64:
            return Response({"detail": "key too long"}, status=status.HTTP_400_BAD_REQUEST)
        obj, _ = Setting.objects.update_or_create(
            key=key, defaults={"value": str(request.data.get("value", ""))})
        return Response(SettingSerializer(obj).data)


class OverviewView(ApiKeyMixin, APIView):
    """GET ?date= — everything the Today screen needs in one round trip."""

    def get(self, request):
        date = parse_date(request.query_params.get("date")) or dt.date.today()
        d_from = parse_date(request.query_params.get("from")) or (date - dt.timedelta(days=29))
        d_to = parse_date(request.query_params.get("to")) or date

        habits = decorate_habits(list(Habit.objects.filter(active=True)), dt.date.today())
        logs = HabitLog.objects.filter(date__gte=d_from, date__lte=d_to)
        done_set = {(l.habit_id, l.date.isoformat()) for l in logs if l.done}
        status_map = {
            (l.habit_id, l.date.isoformat()): (l.status or ("done" if l.done else ""))
            for l in logs
        }
        notes = {
            f"{l.habit_id}:{l.date.isoformat()}": l.note
            for l in logs if l.note
        }
        # completion / skip timestamps (local timezone) for today
        stamp_map = {}
        days_done = {}
        for l in logs:
            key = (l.habit_id, l.date.isoformat())
            if l.status or l.done:
                ts = l.updated_at or l.created_at
                if ts:
                    stamp_map[key] = timezone.localtime(ts).isoformat()
            if l.done:
                days_done.setdefault(l.habit_id, []).append(l.date.isoformat())

        habit_rows = []
        done_today = 0
        skipped_today = 0
        in_progress_today = 0
        for h in habits:
            done = (h.id, date.isoformat()) in done_set
            today_status = status_map.get((h.id, date.isoformat()), "") or (
                "done" if done else "pending"
            )
            if done:
                done_today += 1
            elif today_status == "skipped":
                skipped_today += 1
            elif today_status == "in_progress":
                in_progress_today += 1
            due_days = hit = 0
            day = d_from
            while day <= d_to:
                due_days += 1
                if (h.id, day.isoformat()) in done_set:
                    hit += 1
                day += dt.timedelta(days=1)
            row = HabitSerializer(h).data
            row.update({
                "done_today": done,
                "status_today": today_status,
                "completion_pct": round(hit / due_days * 100) if due_days else 0,
                "today_note": notes.get(f"{h.id}:{date.isoformat()}", ""),
                "logged_at": stamp_map.get((h.id, date.isoformat())),
                "marks": sorted(days_done.get(h.id, [])),
            })
            habit_rows.append(row)

        fitness, _ = FitnessDay.objects.get_or_create(date=date)
        study, _ = StudyDay.objects.get_or_create(date=date)
        total = len(habits)
        day_note = Note.objects.filter(tag=Note.TAG_DAY, ref=date.isoformat()).first()

        fitness_data = FitnessDaySerializer(fitness).data
        # The dedicated WeightLog table is the source of truth for bodyweight;
        # the legacy FitnessDay column is only a fallback.
        effective_weight, weight_date, weight_time = _effective_weight(date)
        fitness_data["weight_kg"] = effective_weight
        fitness_data["weight_date"] = (
            weight_date.isoformat() if weight_date else None
        )
        fitness_data["weight_time"] = weight_time.isoformat() if weight_time else None
        # change vs the previous distinct weigh-in
        fitness_data["weight_change_kg"] = _weight_change(effective_weight, weight_date)

        return Response({
            "date": date.isoformat(),
            "habits": habit_rows,
            "daily_score": round(done_today / total * 100) if total else 0,
            "done_today": done_today,
            "skipped_today": skipped_today,
            "in_progress_today": in_progress_today,
            "habit_total": total,
            "day_note": day_note.text if day_note else "",
            "fitness": fitness_data,
            "study": StudyDaySerializer(study).data,
            "range": {"from": d_from.isoformat(), "to": d_to.isoformat()},
        })


class HabitAnalyticsView(ApiKeyMixin, APIView):
    """GET habit-analytics/?days=30 — the Stats dashboard's data."""

    def get(self, request):
        try:
            days = int(request.query_params.get("days", 30) or 30)
        except ValueError:
            days = 30
        days = max(7, min(365, days))
        return Response(analytics.range_analytics(days))


class StatsView(ApiKeyMixin, APIView):
    """Headline numbers + burnout/momentum intelligence."""

    def get(self, request):
        today = dt.date.today()
        data = analytics.build_stats(today)

        weights = list(
            FitnessDay.objects.exclude(weight_kg__isnull=True)
            .order_by("date").values_list("date", "weight_kg")
        )
        first_w = float(weights[0][1]) if weights else None
        last_w = float(weights[-1][1]) if weights else None

        study_today = StudyDay.objects.filter(date=today).first()
        return Response({
            **data,
            "weight": {
                "first": first_w,
                "latest": last_w,
                "lost_kg": round(first_w - last_w, 1) if first_w and last_w else None,
                "goal": 75.0,
                "series": [{"date": d.isoformat(), "kg": float(w)} for d, w in weights[-60:]],
            },
            "resources": {
                "pending": StudyResource.objects.filter(track="pending").count(),
                "in_progress": StudyResource.objects.filter(track="in_progress").count(),
                "completed": StudyResource.objects.filter(track="completed").count(),
            },
            "study_slots_today": len(study_today.slots) if study_today else 0,
        })


# ---------------------------------------------------------------- whatsapp
class CheckinView(ApiKeyMixin, APIView):
    """
    WhatsApp bot → app bridge.

    POST {member, name?, date, done: [keys], missed: [keys], in_progress: [keys], note?}
    GET  ?date=YYYY-MM-DD | ?from&to  → everyone's check-ins
    """

    def get(self, request):
        qs = DailyCheckin.objects.all()
        date = parse_date(request.query_params.get("date"))
        d_from = parse_date(request.query_params.get("from"))
        d_to = parse_date(request.query_params.get("to"))
        if date:
            qs = qs.filter(date=date)
        if d_from:
            qs = qs.filter(date__gte=d_from)
        if d_to:
            qs = qs.filter(date__lte=d_to)

        out = []
        for c in qs.select_related("member"):
            out.append({
                "member": c.member.external_id,
                "name": c.member.name or c.member.external_id,
                "whatsapp_id": c.member.whatsapp_id or "",
                "date": c.date.isoformat(),
                "done": c.done,
                "missed": c.missed,
                "in_progress": c.in_progress or [],
                "pending": c.pending or [],
                "score": c.score,
                "note": c.note,
            })
        return Response(out)

    def post(self, request):
        ext = (request.data.get("member") or "").strip()
        if not ext:
            return Response({"detail": "member required"}, status=status.HTTP_400_BAD_REQUEST)
        date = parse_date(request.data.get("date"), dt.date.today())
        wid = (request.data.get("whatsapp_id") or "").strip()
        member, _ = CheckinMember.objects.get_or_create(
            external_id=ext, defaults={"name": request.data.get("name") or ext}
        )
        changed = []
        if request.data.get("name"):
            member.name = request.data["name"]
            changed.append("name")
        if wid and member.whatsapp_id != wid:
            member.whatsapp_id = wid
            changed.append("whatsapp_id")
        if changed:
            member.save(update_fields=changed)

        checkin, _ = DailyCheckin.objects.update_or_create(
            member=member,
            date=date,
            defaults={
                "done": request.data.get("done") or [],
                "missed": request.data.get("missed") or [],
                "in_progress": request.data.get("in_progress") or [],
                "pending": request.data.get("pending") or [],
                "note": request.data.get("note") or "",
                "source": request.data.get("source") or DailyCheckin.SOURCE_WHATSAPP,
            },
        )
        mirrored = sync_checkin_to_habit_logs(
            date, checkin.done, checkin.missed, checkin.in_progress, checkin.pending
        )
        return Response({
            "member": member.external_id,
            "date": checkin.date.isoformat(),
            "done": checkin.done,
            "missed": checkin.missed,
            "in_progress": checkin.in_progress or [],
            "pending": checkin.pending or [],
            "score": checkin.score,
            "habit_logs": mirrored,
        }, status=status.HTTP_201_CREATED)


class CheckinLeaderboardView(ApiKeyMixin, APIView):
    """Group standings — streaks and scores, for the night summary & app."""

    def get(self, request):
        days = int(request.query_params.get("days", 30) or 30)
        today = dt.date.today()
        start = today - dt.timedelta(days=days - 1)
        members = CheckinMember.objects.all()
        rows = []
        for m in members:
            checkins = {
                c.date: c for c in DailyCheckin.objects.filter(
                    member=m, date__gte=start, date__lte=today
                )
            }
            if not checkins:
                continue
            scores = [c.score for c in checkins.values()]
            streak = 0
            day = today
            while day in checkins and checkins[day].score >= 50:
                streak += 1
                day -= dt.timedelta(days=1)
            rows.append({
                "member": m.external_id,
                "name": m.name or m.external_id,
                "whatsapp_id": m.whatsapp_id or "",
                "avg_score": round(sum(scores) / len(scores)) if scores else 0,
                "days_reported": len(checkins),
                "streak": streak,
                "today_score": checkins[today].score if today in checkins else None,
            })
        rows.sort(key=lambda r: (-r["streak"], -r["avg_score"]))
        return Response({"from": start.isoformat(), "to": today.isoformat(), "members": rows})


class MembersView(ApiKeyMixin, APIView):
    def get(self, request):
        return Response(CheckinMemberSerializer(CheckinMember.objects.all(), many=True).data)


# ---------------------------------------------------------------- dashboard
class DashboardView(ApiKeyMixin, APIView):
    """
    The 'powerhouse' screen: today's score, focus suggestion, streak at risk,
    momentum movers, burnout state, one-line advice.
    """

    def get(self, request):
        today = dt.date.today()
        habits = decorate_habits(list(Habit.objects.filter(active=True)), today)
        total = len(habits)
        done_logs = HabitLog.objects.filter(date=today, done=True)
        done_ids = set(done_logs.values_list("habit_id", flat=True))

        # streak at risk = longest current streak, not done yet today
        at_risk = []
        for h in habits:
            if h.id not in done_ids and h._streak >= 3:
                at_risk.append({
                    "id": h.id, "name": h.name, "emoji": h.emoji,
                    "color": h.color, "streak": h._streak,
                })
        at_risk.sort(key=lambda r: -r["streak"])

        # focus suggestion: lowest momentum among active habits
        movers = []
        for h in habits:
            m = analytics.momentum(h, today)
            movers.append({
                "id": h.id, "name": h.name, "emoji": h.emoji, "color": h.color,
                "momentum": m["score"], "trend": m["trend"], "streak": h._streak,
            })
        movers.sort(key=lambda r: r["momentum"])
        focus = next((m for m in movers if m["id"] not in done_ids), None)

        burnout = analytics.burnout_risk(today)
        recovery = analytics.recovery_insight(today)

        # 14-day score sparkline
        spark = []
        for d in analytics.daterange(today - dt.timedelta(days=13), today):
            hit = HabitLog.objects.filter(date=d, done=True).count()
            spark.append({
                "date": d.isoformat(),
                "score": round(hit / total * 100) if total else 0,
            })

        improving = sorted(
            [m for m in movers if m["trend"] > 0], key=lambda r: -r["trend"]
        )[:3]

        return Response({
            "date": today.isoformat(),
            "score": round(len(done_ids) / total * 100) if total else 0,
            "done_today": len(done_ids),
            "habit_total": total,
            "at_risk": at_risk[:5],
            "focus": focus,
            "improving": improving,
            "burnout": burnout,
            "recovery": recovery,
            "consistency_30d": analytics._overall_completion(today, 30),
            "spark": spark,
            "habits": HabitSerializer(habits, many=True).data,
        })


# =====================================================================
# Food — dish database + diary
# =====================================================================
class FoodListView(ApiKeyMixin, APIView):
    """GET food/?q=roti&meal=&limit=  — search the dish database."""

    def get(self, request):
        qs = Food.objects.all()
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category__iexact=category)
        total = qs.count()
        try:
            limit = int(request.query_params.get("limit") or 50)
        except ValueError:
            limit = 50
        return Response({"count": total, "results": FoodSerializer(qs[:limit], many=True).data})

    def post(self, request):
        """Add a custom dish."""
        data = request.data.copy()
        data["is_custom"] = True
        ser = FoodSerializer(data=data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class FoodDetailView(ApiKeyMixin, APIView):
    def patch(self, request, pk):
        obj = Food.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = FoodSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        obj = Food.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()  # soft
        return Response({"deleted": pk, "soft": True})


def diary_totals(entries):
    """Sum a day's entries and compare against the targets."""
    total = {"kcal": 0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for e in entries:
        total["kcal"] += e.kcal
        total["protein_g"] += float(e.protein_g)
        total["carbs_g"] += float(e.carbs_g)
        total["fat_g"] += float(e.fat_g)
    for k in ("protein_g", "carbs_g", "fat_g"):
        total[k] = round(total[k], 1)
    return total


class DiaryView(ApiKeyMixin, APIView):
    """GET/POST diary/?date=YYYY-MM-DD — one day of logged food."""

    def get(self, request):
        date = parse_date(request.query_params.get("date"), dt.date.today())
        entries = DiaryEntry.objects.filter(date=date)
        targets = NutritionTarget.objects.first() or NutritionTarget()
        totals = diary_totals(entries)

        # group by meal slot so the client does not have to
        meals = []
        for meal in DiaryEntry.MEALS:
            items = [e for e in entries if e.meal == meal]
            meals.append({
                "meal": meal,
                "kcal": sum(i.kcal for i in items),
                "entries": DiaryEntrySerializer(items, many=True).data,
            })

        return Response({
            "date": date.isoformat(),
            "entries": DiaryEntrySerializer(entries, many=True).data,
            "meals": meals,
            "totals": totals,
            "targets": NutritionTargetSerializer(targets).data,
            "remaining_kcal": targets.calorie_goal - totals["kcal"],
        })

    def post(self, request):
        """Log a dish: {date, meal, food_id, quantity}."""
        ser = DiaryEntrySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class DiaryEntryView(ApiKeyMixin, APIView):
    def patch(self, request, pk):
        """Change quantity — re-snapshots the macros from the dish."""
        obj = DiaryEntry.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        qty = request.data.get("quantity")
        if qty is not None and obj.food:
            qty = float(qty)
            obj.quantity = qty
            obj.kcal = round(float(obj.food.kcal) * qty)
            obj.protein_g = round(float(obj.food.protein_g) * qty, 1)
            obj.carbs_g = round(float(obj.food.carbs_g) * qty, 1)
            obj.fat_g = round(float(obj.food.fat_g) * qty, 1)
        if "meal" in request.data:
            obj.meal = request.data["meal"]
        obj.save()
        return Response(DiaryEntrySerializer(obj).data)

    def delete(self, request, pk):
        obj = DiaryEntry.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()  # soft
        return Response({"deleted": pk, "soft": True})


class NutritionTargetView(ApiKeyMixin, APIView):
    def get(self, request):
        obj = NutritionTarget.objects.first() or NutritionTarget()
        return Response(NutritionTargetSerializer(obj).data)

    def patch(self, request):
        obj = NutritionTarget.objects.first()
        if not obj:
            obj = NutritionTarget.objects.create(**request.data)
        else:
            for k, v in request.data.items():
                if hasattr(obj, k):
                    setattr(obj, k, v)
            obj.save()
        return Response(NutritionTargetSerializer(obj).data)


# =====================================================================
# Notes — one feed for every note
# =====================================================================
class NotesView(ApiKeyMixin, APIView):
    """GET notes/?tag=&from=&to=&q= — the Notes tab feed."""

    def get(self, request):
        qs = Note.objects.all()
        tag = request.query_params.get("tag")
        if tag and tag != "all":
            qs = qs.filter(tag=tag)
        date_from = parse_date(request.query_params.get("from"))
        if date_from:
            qs = qs.filter(date__gte=date_from)
        date_to = parse_date(request.query_params.get("to"))
        if date_to:
            qs = qs.filter(date__lte=date_to)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(text__icontains=q) | Q(ref__icontains=q))

        # counts per tag, so the client can label the chips without a 2nd call
        counts = {"all": Note.objects.count()}
        for t in Note.TAGS:
            counts[t] = Note.objects.filter(tag=t).count()

        return Response({
            "count": qs.count(),
            "counts": counts,
            "results": NoteSerializer(qs, many=True).data,
        })

    def post(self, request):
        ser = NoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class NoteDetailView(ApiKeyMixin, APIView):
    def patch(self, request, pk):
        obj = Note.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = NoteSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        obj = Note.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()  # soft
        return Response({"deleted": pk, "soft": True})


class DayNoteView(ApiKeyMixin, APIView):
    """GET/POST day-note/ {date, note} — the single "Note for today".

    Stored as a `Note` row with `tag='day'` and `ref` = the ISO date, so it also
    shows up in the Notes tab feed alongside every other note.
    """

    def _row(self, date):
        return Note.objects.filter(tag=Note.TAG_DAY, ref=date.isoformat()).first()

    def get(self, request):
        date = parse_date(request.query_params.get("date")) or dt.date.today()
        row = self._row(date)
        return Response({"date": date.isoformat(), "note": row.text if row else ""})

    def post(self, request):
        date = parse_date(request.data.get("date")) or dt.date.today()
        text = (request.data.get("note") or "").strip()
        row = self._row(date)
        if row is None:
            if not text:
                return Response({"date": date.isoformat(), "note": ""})
            row = Note.objects.create(date=date, tag=Note.TAG_DAY, ref=date.isoformat(), text=text)
        else:
            if not text:
                row.delete()  # soft — clearing the text removes it from the feed
                return Response({"date": date.isoformat(), "note": ""})
            row.text = text
            row.save(update_fields=["text", "updated_at"])
        return Response({"date": date.isoformat(), "note": row.text})


# =====================================================================
# Workout modules (Legend-style)
# =====================================================================
class WorkoutModulesView(ApiKeyMixin, APIView):
    def get(self, request):
        qs = WorkoutModule.objects.all()
        return Response(WorkoutModuleSerializer(qs, many=True).data)

    def post(self, request):
        ser = WorkoutModuleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class WorkoutModuleDetailView(ApiKeyMixin, APIView):
    def patch(self, request, pk):
        obj = WorkoutModule.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = WorkoutModuleSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        obj = WorkoutModule.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()  # soft
        return Response({"deleted": pk, "soft": True})


class WorkoutScheduleView(ApiKeyMixin, APIView):
    """GET workout-schedule/ — the 7-day split strip, resolved server-side."""

    def get(self, request):
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        today_name = dt.date.today().strftime("%a")
        modules = list(WorkoutModule.objects.all())
        week = []
        for name in day_names:
            mod = next((m for m in modules if name in (m.days or [])), None)
            week.append({
                "day": name,
                "module": mod.name if mod else None,
                "emoji": mod.emoji if mod else "😴",
                "color": mod.color if mod else None,
                "exercise_count": len(mod.exercises or []) if mod else 0,
                "is_today": name == today_name,
            })
        return Response({"week": week, "today": today_name, "modules": WorkoutModuleSerializer(modules, many=True).data})


# =====================================================================
# Legend-style training — library, logging, history, progress
# =====================================================================
def _bodyweight():
    """Latest logged bodyweight, used for strength-level grading."""
    entry = WeightLog.objects.order_by("-date", "-id").first()
    if entry and entry.weight_kg:
        return float(entry.weight_kg)
    day = FitnessDay.objects.exclude(weight_kg__isnull=True).order_by("-date").first()
    return float(day.weight_kg) if day and day.weight_kg else None


def _round2(value):
    """Round a numeric value to at most 2 decimal places (None-safe)."""
    if value is None:
        return None
    return round(float(value), 2)


def _effective_weight(date):
    """The weight shown for `date`: latest WeightLog on/before it, else the
    legacy FitnessDay column. Returns (kg, date, time) with kg rounded to 2dp.
    """
    entry = (
        WeightLog.objects.filter(date__lte=date).order_by("-date", "-id", "-time").first()
    )
    if entry and entry.weight_kg is not None:
        return _round2(entry.weight_kg), entry.date, entry.time
    day = FitnessDay.objects.filter(date=date).first()
    if day and day.weight_kg is not None:
        return _round2(day.weight_kg), date, None
    return None, None, None


def _weight_change(current, current_date):
    """Difference between the current weigh-in and the previous distinct one."""
    if current is None or current_date is None:
        return None
    previous = (
        WeightLog.objects.filter(date__lt=current_date)
        .order_by("-date", "-id")
        .first()
    )
    if not previous or previous.weight_kg is None:
        return None
    return _round2(current - float(previous.weight_kg))


class ExercisesView(ApiKeyMixin, APIView):
    """GET exercises/?q=&muscle= — the exercise library."""

    def get(self, request):
        qs = Exercise.objects.all()
        q = request.query_params.get("q", "").strip()
        muscle = request.query_params.get("muscle", "").strip()
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(muscle__icontains=q))
        if muscle:
            qs = qs.filter(muscle__iexact=muscle)
        return Response({
            "count": qs.count(),
            "muscles": sorted(
                {m for m in Exercise.objects.values_list("muscle", flat=True) if m}
            ),
            "results": ExerciseSerializer(qs[:300], many=True).data,
        })

    def post(self, request):
        ser = ExerciseSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ser.save(is_custom=True)
        return Response(ser.data, status=status.HTTP_201_CREATED)


def _workout_payload(date):
    """Everything the active-workout screen needs for one date."""
    exercises = (
        WorkoutExercise.objects.filter(date=date)
        .prefetch_related("sets")
        .order_by("order", "id")
    )
    day = FitnessDay.objects.filter(date=date).first()
    bodyweight = _bodyweight()
    rows, total_volume, total_sets, total_reps = [], 0, 0, 0
    for we in exercises:
        sets = list(we.sets.all())
        working = [s for s in sets if s.completed and s.set_type != "warmup"]
        vol = sum(s.volume_kg for s in working)
        total_volume += vol
        total_sets += len(working)
        total_reps += sum(s.reps or 0 for s in working)
        best = max(working, key=lambda s: s.volume_kg) if working else None
        level, ratio = analytics.strength_level(we.name, best.est_1rm if best else None, bodyweight)
        rows.append({
            "id": we.id,
            "exercise": we.exercise_id,
            "name": we.name,
            "muscle": we.muscle,
            "order": we.order,
            "superset_group": we.superset_group,
            "target_sets": we.target_sets,
            "target_reps": we.target_reps,
            "rest_seconds": we.rest_seconds,
            "note": we.note,
            "is_cardio": bool(we.exercise and we.exercise.is_cardio),
            "sets": WorkoutSetSerializer(sets, many=True).data,
            "summary": we.summary,
            "volume_kg": vol,
            "est_1rm": best.est_1rm if best else None,
            "strength_level": level,
            "strength_ratio": ratio,
            # Legend prefills from history: what you did on the previous day this
            # exercise appeared. Sent per-exercise so the UI can show "last time".
            "last_time": analytics.last_time_for(we.name, date),
        })
    return {
        "date": date.isoformat(),
        "module": day.mode if day else "",
        "status": day.status if day else "Pending",
        "notes": day.notes if day else "",
        "exercises": rows,
        "totals": {
            "volume_kg": total_volume,
            "sets": total_sets,
            "reps": total_reps,
            "exercise_count": len(rows),
        },
        "bodyweight_kg": bodyweight,
    }


class WorkoutView(ApiKeyMixin, APIView):
    """GET/PATCH workout/<date>/ — the whole workout for a day.

    PATCH updates the day's status/notes (Legend's "finish workout" action):
    Body: {status?, notes?, mode?}
    """

    def get(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(_workout_payload(d))

    def patch(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        day, _ = FitnessDay.objects.get_or_create(date=d)
        status_value = request.data.get("status")
        if status_value is not None:
            status_value = str(status_value).strip()
            if status_value not in ("Pending", "Completed", "Done", "Skipped"):
                return Response({"detail": "bad status"}, status=status.HTTP_400_BAD_REQUEST)
            day.status = status_value
        if "notes" in request.data:
            day.notes = str(request.data.get("notes") or "")
        if "mode" in request.data:
            day.mode = str(request.data.get("mode") or "")
        day.save(update_fields=["status", "notes", "mode", "updated_at"])
        return Response(_workout_payload(d))


class WorkoutExercisesView(ApiKeyMixin, APIView):
    """POST workout/<date>/exercise/ — add an exercise to the day's workout.

    Body: {name, muscle?, exercise?, order?, target_sets?, target_reps?,
           rest_seconds?, superset_group?}
    If the name isn't in the library it is added automatically.
    """

    def post(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data["date"] = d.isoformat()

        name = (data.get("name") or "").strip()
        if not name:
            return Response({"name": "required"}, status=status.HTTP_400_BAD_REQUEST)
        if not data.get("exercise"):
            lib = Exercise.objects.filter(name__iexact=name).first()
            if not lib:
                lib = Exercise.objects.create(
                    name=name,
                    muscle=(data.get("muscle") or "").strip(),
                    is_custom=True,
                )
            data["exercise"] = lib.id
            if not data.get("muscle"):
                data["muscle"] = lib.muscle
        if not data.get("order"):
            last = (
                WorkoutExercise.objects.filter(date=d).order_by("-order").first()
            )
            data["order"] = (last.order + 1) if last else 0

        ser = WorkoutExerciseSerializer(data=data)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class WorkoutExerciseDetailView(ApiKeyMixin, APIView):
    """PATCH/DELETE one exercise in a day's workout (delete cascades its sets)."""

    def patch(self, request, pk):
        obj = WorkoutExercise.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = WorkoutExerciseSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        obj = WorkoutExercise.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()  # soft; sets cascade to hard delete with the parent
        return Response({"deleted": pk, "soft": True})


class WorkoutSetsView(ApiKeyMixin, APIView):
    """POST workout/exercise/<pk>/sets/ — log a set.

    Body: {weight_kg?, reps?, set_type?, rpe?, rir?, rest_sec?, completed?,
           duration_sec?, distance_km?, note?}
    """

    def post(self, request, pk):
        we = WorkoutExercise.objects.filter(pk=pk).first()
        if not we:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        if data.get("order") is None:
            last = we.sets.order_by("-order").first()
            data["order"] = (last.order + 1) if last else 0
        data["workout_exercise"] = we.id
        ser = WorkoutSetSerializer(data=data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        obj.sync_rpe_rir()
        obj.save(update_fields=["rir", "rpe"])
        return Response(WorkoutSetSerializer(obj).data, status=status.HTTP_201_CREATED)


class WorkoutSetDetailView(ApiKeyMixin, APIView):
    """PATCH/DELETE a single set (tick it complete, change weight, RPE…)."""

    def patch(self, request, pk):
        obj = WorkoutSet.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = WorkoutSetSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        obj.sync_rpe_rir()
        obj.save(update_fields=["rir", "rpe"])
        return Response(WorkoutSetSerializer(obj).data)

    def delete(self, request, pk):
        obj = WorkoutSet.objects.filter(pk=pk, deleted_at__isnull=True).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()  # soft
        return Response({"deleted": pk, "soft": True})


class WorkoutHistoryView(ApiKeyMixin, APIView):
    """GET workout-history/?limit=20 — Legend's workout list.

    One row per training day: duration, muscle groups, gains, sets/reps/volume.
    """

    def get(self, request):
        limit = int(request.query_params.get("limit", 20))
        dates = (
            WorkoutExercise.objects.values_list("date", flat=True)
            .distinct()
            .order_by("-date")[:limit]
        )
        history = []
        for d in dates:
            rows = WorkoutExercise.objects.filter(date=d).prefetch_related("sets")
            muscles, sets_n, reps_n, volume = set(), 0, 0, 0
            for we in rows:
                working = [
                    s for s in we.sets.all() if s.completed and s.set_type != "warmup"
                ]
                if we.muscle:
                    muscles.add(we.muscle)
                sets_n += len(working)
                reps_n += sum(s.reps or 0 for s in working)
                volume += sum(s.volume_kg for s in working)
            day = FitnessDay.objects.filter(date=d).first()
            history.append({
                "date": d.isoformat(),
                "module": day.mode if day else "",
                "status": day.status if day else "Pending",
                "muscles": sorted(muscles),
                "sets": sets_n,
                "reps": reps_n,
                "volume_kg": volume,
                "exercise_count": rows.count(),
                "duration_min": day.duration_min if day else None,
                "notes": day.notes if day else "",
            })
        return Response({"count": len(history), "results": history})


class ExerciseProgressView(ApiKeyMixin, APIView):
    """GET exercise-progress/?name=Bench%20Press&window=90

    Legend's exercise analysis: gains %, chart points, personal bests,
    est-1RM, strength level, and the recent set history.
    """

    def get(self, request):
        name = request.query_params.get("name", "").strip()
        if not name:
            return Response({"detail": "name required"}, status=status.HTTP_400_BAD_REQUEST)
        window = int(request.query_params.get("window", 90))
        history = analytics.exercise_history(name)
        if not history:
            return Response({"name": name, "found": False})
        bws = _bodyweight()
        best_1rm = max((h["est_1rm"] or 0) for h in history) or None
        level, ratio = analytics.strength_level(name, best_1rm, bws)
        return Response({
            "name": name,
            "found": True,
            "gains_pct": analytics.gains_pct(name, window),
            "history": history,
            "personal_bests": analytics.personal_bests(name),
            "est_1rm": best_1rm,
            "strength_level": level,
            "strength_ratio": ratio,
            "bodyweight_kg": bws,
            "total_sets": len(analytics.working_sets(exercise_name=name)),
            "last_time": analytics.last_time_for(name, dt.date.today() + dt.timedelta(days=1)),
        })


class MuscleFatigueView(ApiKeyMixin, APIView):
    """GET muscle-fatigue/?days=7 — the fatigue heat map."""

    def get(self, request):
        days = int(request.query_params.get("days", 7))
        return Response({"days": days, "muscles": analytics.muscle_fatigue(window_days=days)})


class PlateCalculatorView(ApiKeyMixin, APIView):
    """GET plate-calc/?target=100&bar=20&plates=25,20,10,5,2.5

    Pure math, but kept server-side so the web and phone builds agree.
    """

    def get(self, request):
        target = request.query_params.get("target")
        if target is None:
            return Response({"detail": "target required"}, status=status.HTTP_400_BAD_REQUEST)
        bar = float(request.query_params.get("bar", 20))
        plates_param = request.query_params.get("plates")
        plates = (
            [float(p) for p in plates_param.split(",") if p.strip()]
            if plates_param
            else None
        )
        return Response(analytics.plate_math(float(target), bar_kg=bar, plates=plates))


class BodyMeasurementsView(ApiKeyMixin, APIView):
    """GET/POST body-measurements/ — dated circumference + bodyweight records.

    GET params: from, to, limit. Returns a list (newest first) plus the
    `sites` list so the UI can offer the right fields.
    """

    SITES = [
        "bodyweight_kg", "neck_cm", "chest_cm", "waist_cm", "hips_cm",
        "left_arm_cm", "right_arm_cm", "left_thigh_cm", "right_thigh_cm",
        "left_calf_cm", "right_calf_cm", "body_fat_pct",
    ]

    def get(self, request):
        qs = BodyMeasurement.objects.all()
        d_from = parse_date(request.query_params.get("from"))
        d_to = parse_date(request.query_params.get("to"))
        if d_from:
            qs = qs.filter(date__gte=d_from)
        if d_to:
            qs = qs.filter(date__lte=d_to)
        limit = request.query_params.get("limit")
        if limit and limit.isdigit():
            qs = qs[: int(limit)]
        rows = list(qs)
        # per-site history for charts: oldest → newest, only non-null points
        ordered = sorted(rows, key=lambda r: r.date)
        series = {
            site: [
                {"date": r.date.isoformat(), "value": _round2(getattr(r, site))}
                for r in ordered
                if getattr(r, site) is not None
            ]
            for site in self.SITES
        }
        return Response({
            "count": len(rows),
            "sites": self.SITES,
            "results": BodyMeasurementSerializer(rows, many=True).data,
            # latest non-null value per site, for the "current" summary row
            "latest": {
                site: next(
                    (getattr(r, site) for r in rows if getattr(r, site) is not None),
                    None,
                )
                for site in self.SITES
            },
            "series": series,
        })

    def post(self, request):
        """Create or replace the record for a date (one row per date)."""
        date = parse_date(request.data.get("date"))
        if not date:
            return Response({"detail": "date required"}, status=status.HTTP_400_BAD_REQUEST)
        obj = BodyMeasurement.objects.filter(date=date).first()
        ser = BodyMeasurementSerializer(obj, data={**request.data, "date": date},
                                        partial=obj is not None)
        ser.is_valid(raise_exception=True)
        ser.save()
        code = status.HTTP_200_OK if obj else status.HTTP_201_CREATED
        return Response(ser.data, status=code)


class BodyMeasurementDetailView(ApiKeyMixin, APIView):
    def patch(self, request, pk):
        obj = BodyMeasurement.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = BodyMeasurementSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        obj = BodyMeasurement.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({"deleted": pk, "soft": True})


class IntakeView(ApiKeyMixin, APIView):
    """GET/POST intake/?date= — daily water / protein / calorie intake.

    POST upserts the row for the date. `mode=add` increments instead of
    replacing, so a "+250ml" quick-log works without a read-modify-write.
    """

    def get(self, request):
        date = parse_date(request.query_params.get("date")) or dt.date.today()
        obj = IntakeLog.objects.filter(date=date).first()
        target = NutritionTarget.objects.first()
        data = IntakeLogSerializer(obj).data if obj else {
            "id": None, "date": date.isoformat(), "water_ml": 0,
            "protein_g": 0, "calories": 0,
        }
        data["targets"] = {
            "water_ml": target.water_goal_ml if target else 3000,
            "protein_g": target.protein_goal if target else 140,
            "calories": target.calorie_goal if target else 2100,
        }
        data["drinks"] = _drinks_summary(date)
        return Response(data)

    def post(self, request):
        date = parse_date(request.data.get("date")) or dt.date.today()
        obj = IntakeLog.objects.filter(date=date).first()
        payload = dict(request.data)
        payload["date"] = date
        if (request.data.get("mode") or "").strip() == "add":
            base = obj or IntakeLog(date=date)
            for field in ("water_ml", "protein_g", "calories"):
                delta = request.data.get(field)
                if delta is not None:
                    setattr(base, field, max(0, (getattr(base, field) or 0) + int(delta)))
            base.save()
            return Response(IntakeLogSerializer(base).data)
        ser = IntakeLogSerializer(obj, data=payload, partial=obj is not None)
        ser.is_valid(raise_exception=True)
        ser.save()
        code = status.HTTP_200_OK if obj else status.HTTP_201_CREATED
        return Response(ser.data, status=code)


def _drinks_summary(date):
    """Roll up one day's drinks: hydration vs water goal, caffeine and kcal."""
    rows = list(DrinkLog.objects.filter(date=date))
    by_type = {}
    for r in rows:
        b = by_type.setdefault(r.drink_type, {"drink_type": r.drink_type, "volume_ml": 0, "count": 0})
        b["volume_ml"] += r.volume_ml
        b["count"] += 1
    water = sum(r.volume_ml for r in rows if r.drink_type == "water")
    target = NutritionTarget.objects.first()
    goal = target.water_goal_ml if target else 3000
    return {
        "total_ml": sum(r.volume_ml for r in rows),
        "water_ml": water,
        "water_goal_ml": goal,
        "hydration_pct": min(100, round(water / goal * 100)) if goal else 0,
        "caffeine_mg": sum(r.caffeine_mg for r in rows),
        "calories": sum(r.calories for r in rows),
        "count": len(rows),
        "by_type": sorted(by_type.values(), key=lambda b: -b["volume_ml"]),
    }


class DrinksView(ApiKeyMixin, APIView):
    """GET/POST drinks/ — individual beverages, one row per drink.

    GET params: date (single day) or from/to (range). Response always carries
    the day's roll-up under `summary` when a single `date` is given.
    POST body: {drink_type, volume_ml?, time?, notes?, date?, caffeine_mg?,
                calories?} — caffeine/kcal default from the drink preset.
    """

    def get(self, request):
        qs = DrinkLog.objects.all()
        date = parse_date(request.query_params.get("date"))
        if date:
            qs = qs.filter(date=date)
        else:
            d_from = parse_date(request.query_params.get("from"))
            d_to = parse_date(request.query_params.get("to"))
            if d_from:
                qs = qs.filter(date__gte=d_from)
            if d_to:
                qs = qs.filter(date__lte=d_to)
        limit = request.query_params.get("limit")
        if limit and limit.isdigit():
            qs = qs[: int(limit)]
        rows = list(qs)
        return Response({
            "count": len(rows),
            "presets": [
                {"drink_type": k, **v} for k, v in DRINK_PRESETS.items()
            ],
            "results": DrinkLogSerializer(rows, many=True).data,
            "summary": _drinks_summary(date) if date else None,
        })

    def post(self, request):
        date = parse_date(request.data.get("date")) or dt.date.today()
        payload = dict(request.data)
        payload["date"] = date
        preset = DRINK_PRESETS.get((payload.get("drink_type") or "water").strip().lower())
        if preset and payload.get("volume_ml") in (None, ""):
            payload["volume_ml"] = preset["ml"]
        ser = DrinkLogSerializer(data=payload)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        obj.apply_preset()
        obj.save(update_fields=["caffeine_mg", "calories"])
        # keep the daily IntakeLog.water_ml in step with logged water drinks
        water = sum(r.volume_ml for r in DrinkLog.objects.filter(date=date, drink_type="water"))
        intake, _ = IntakeLog.objects.get_or_create(date=date)
        intake.water_ml = water
        intake.save(update_fields=["water_ml", "updated_at"])
        return Response(DrinkLogSerializer(obj).data, status=status.HTTP_201_CREATED)


class DrinkDetailView(ApiKeyMixin, APIView):
    def patch(self, request, pk):
        obj = DrinkLog.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = DrinkLogSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        self._resync_water(obj.date)
        return Response(ser.data)

    def delete(self, request, pk):
        obj = DrinkLog.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        date = obj.date
        obj.delete()
        self._resync_water(date)
        return Response({"deleted": pk, "soft": True})

    @staticmethod
    def _resync_water(date):
        water = sum(r.volume_ml for r in DrinkLog.objects.filter(date=date, drink_type="water"))
        IntakeLog.objects.filter(date=date).update(water_ml=water)


class WeightInsightsView(ApiKeyMixin, APIView):
    """GET weight-insights/ — BMI, healthy range, goal progress and trends.

    Height/sex/goal/birth-year live in Settings (`height_cm`, `sex`,
    `goal_weight_kg`, `birth_year`) so no extra profile table is needed.
    """

    def get(self, request):
        def setting(key, fallback=None):
            row = Setting.objects.filter(key=key).first()
            return row.value if row and row.value not in (None, "") else fallback

        def num(key):
            try:
                return float(setting(key))
            except (TypeError, ValueError):
                return None

        entry = WeightLog.objects.order_by("-date", "-id").first()
        weight = float(entry.weight_kg) if entry and entry.weight_kg else _bodyweight()
        height_cm = num("height_cm")
        goal = num("goal_weight_kg")
        out = {
            "weight_kg": _round2(weight),
            "height_cm": _round2(height_cm),
            "goal_weight_kg": _round2(goal),
            "bmi": None,
            "bmi_category": None,
            "healthy_min_kg": None,
            "healthy_max_kg": None,
            "to_goal_kg": None,
            "age": None,
        }
        if height_cm and weight:
            m = height_cm / 100.0
            bmi = weight / (m * m)
            out["bmi"] = round(bmi, 2)
            out["bmi_category"] = _bmi_category(bmi)
            out["healthy_min_kg"] = round(18.5 * m * m, 1)
            out["healthy_max_kg"] = round(24.9 * m * m, 1)
        if goal and weight:
            out["to_goal_kg"] = _round2(weight - goal)
        birth_year = num("birth_year")
        if birth_year:
            out["age"] = dt.date.today().year - int(birth_year)
        # lightweight trend: first vs latest in the last 30 days
        recent = list(
            WeightLog.objects.filter(date__gte=dt.date.today() - dt.timedelta(days=30))
            .order_by("date")
        )
        if len(recent) >= 2:
            out["trend_30d_kg"] = _round2(float(recent[-1].weight_kg) - float(recent[0].weight_kg))
        else:
            out["trend_30d_kg"] = None
        return Response(out)


def _bmi_category(bmi):
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25:
        return "Normal"
    if bmi < 30:
        return "Overweight"
    return "Obese"


class JournalView(ApiKeyMixin, APIView):
    """GET journal/?from=&to=&types= — a unified, date-sorted activity feed.

    Merges habits, workouts, weigh-ins, measurements and drinks into one
    timeline so the phone can review history without the individual screens.
    """

    def get(self, request):
        types = {
            t.strip()
            for t in (request.query_params.get("types") or "habits,fitness,weight,measurements,drinks,jaap").split(",")
            if t.strip()
        }
        d_to = parse_date(request.query_params.get("to")) or dt.date.today()
        d_from = parse_date(request.query_params.get("from")) or (d_to - dt.timedelta(days=59))
        limit = request.query_params.get("limit")
        limit = int(limit) if limit and limit.isdigit() else 400

        events = []
        if "habits" in types:
            logs = (
                HabitLog.objects.filter(date__gte=d_from, date__lte=d_to)
                .select_related("habit")
                .order_by("-date")
            )
            for l in logs:
                state = l.status or ("done" if l.done else "pending")
                if state == "pending":
                    continue
                events.append({
                    "date": l.date.isoformat(),
                    "kind": "habit",
                    "title": f"{l.habit.emoji} {l.habit.name}".strip(),
                    "subtitle": "Skipped" if state == "skipped" else "Done",
                    "state": state,
                    "color": l.habit.color,
                    "at": l.done_at.isoformat() if getattr(l, "done_at", None) else None,
                })
        if "fitness" in types:
            days = (
                FitnessDay.objects.filter(date__gte=d_from, date__lte=d_to)
                .order_by("-date")
            )
            for day in days:
                exs = WorkoutExercise.objects.filter(date=day.date)
                sets = WorkoutSet.objects.filter(workout_exercise__date=day.date, completed=True)
                working = [s for s in sets if s.set_type != WorkoutSet.TYPE_WARMUP]
                if not exs.exists() and not working:
                    continue
                volume = sum(s.volume_kg for s in working)
                muscles = sorted({e.muscle for e in exs if e.muscle})
                events.append({
                    "date": day.date.isoformat(),
                    "kind": "fitness",
                    "title": day.mode or (", ".join(muscles) if muscles else "Workout"),
                    "subtitle": f"{len(working)} sets · {round(volume)}kg",
                    "state": day.status,
                    "muscles": muscles,
                })
        if "weight" in types:
            for w in WeightLog.objects.filter(date__gte=d_from, date__lte=d_to).order_by("-date"):
                events.append({
                    "date": w.date.isoformat(),
                    "kind": "weight",
                    "title": f"{_round2(w.weight_kg)} kg",
                    "subtitle": (w.notes or "Weigh-in"),
                    "at": w.time.isoformat() if w.time else None,
                })
        if "measurements" in types:
            for m in BodyMeasurement.objects.filter(date__gte=d_from, date__lte=d_to).order_by("-date"):
                parts = [
                    f"{field.replace('_cm', '').replace('_', ' ')} {_round2(getattr(m, field))}"
                    for field in ("chest_cm", "waist_cm", "hips_cm", "neck_cm")
                    if getattr(m, field) is not None
                ]
                events.append({
                    "date": m.date.isoformat(),
                    "kind": "measurements",
                    "title": "Measurements",
                    "subtitle": " · ".join(parts) if parts else "Measurements logged",
                })
        if "drinks" in types:
            by_day = {}
            for d in DrinkLog.objects.filter(date__gte=d_from, date__lte=d_to):
                b = by_day.setdefault(d.date, {"ml": 0, "caffeine": 0, "kcal": 0, "count": 0})
                b["ml"] += d.volume_ml
                b["caffeine"] += d.caffeine_mg
                b["kcal"] += d.calories
                b["count"] += 1
            for day, b in by_day.items():
                events.append({
                    "date": day.isoformat(),
                    "kind": "drinks",
                    "title": f"{b['ml']} ml",
                    "subtitle": f"{b['count']} drinks · {b['caffeine']}mg caffeine · {b['kcal']} kcal",
                })
        if "jaap" in types:
            for j in (
                JaapLog.objects.filter(date__gte=d_from, date__lte=d_to)
                .exclude(count=0)
                .select_related("mantra")
                .order_by("-date")
            ):
                beads = j.mantra.beads
                parts = [f"{j.count} jaap{'s' if j.count != 1 else ''}"]
                if j.malas:
                    parts.append(f"{j.malas} mala{'s' if j.malas != 1 else ''}")
                if j.duration_min:
                    parts.append(f"{j.duration_min} min")
                events.append({
                    "date": j.date.isoformat(),
                    "kind": "jaap",
                    "title": f"{j.mantra.emoji} {j.mantra.name}".strip(),
                    "subtitle": " · ".join(parts),
                    "state": "done",
                    "color": j.mantra.color,
                    "count": j.count,
                    "malas": j.malas,
                    "beads": beads,
                })

        events.sort(key=lambda e: (e["date"], e.get("at") or ""), reverse=True)
        events = events[:limit]
        counts_by_kind = {}
        for e in events:
            counts_by_kind[e["kind"]] = counts_by_kind.get(e["kind"], 0) + 1
        return Response({
            "from": d_from.isoformat(),
            "to": d_to.isoformat(),
            "count": len(events),
            "counts": counts_by_kind,
            "events": events,
        })


class StartRoutineView(ApiKeyMixin, APIView):
    """POST workout/<date>/start/ {module} — prefill a day from a routine.
    Copies the module's planned exercises onto the date as WorkoutExercise rows
    (with empty sets), so the user just logs numbers. Existing exercises on the
    date are left alone; the module name is stored as the day's mode.
    """

    def post(self, request, date):
        d = parse_date(date)
        if not d:
            return Response({"detail": "bad date"}, status=status.HTTP_400_BAD_REQUEST)
        module_id = request.data.get("module")
        module = WorkoutModule.objects.filter(pk=module_id).first() if module_id else None
        if not module:
            return Response({"detail": "module not found"}, status=status.HTTP_404_NOT_FOUND)

        existing_names = set(
            WorkoutExercise.objects.filter(date=d).values_list("name", flat=True)
        )
        created = 0
        order = WorkoutExercise.objects.filter(date=d).count()
        for plan in module.exercises or []:
            name = (plan.get("name") or "").strip()
            if not name or name in existing_names:
                continue
            ex = Exercise.objects.filter(name=name).first()
            if not ex:
                ex = Exercise.objects.create(
                    name=name,
                    muscle=(plan.get("muscle") or "").strip(),
                    is_custom=True,
                )
            sets = plan.get("sets") or plan.get("target_sets") or 0
            reps = plan.get("reps") or plan.get("target_reps") or ""
            we = WorkoutExercise.objects.create(
                date=d,
                exercise=ex,
                name=name,
                muscle=(plan.get("muscle") or ex.muscle or "").strip(),
                order=order,
                target_sets=int(sets) if str(sets).isdigit() else None,
                target_reps=str(reps),
                rest_seconds=plan.get("rest_seconds") or 90,
            )
            # Pre-fill planned working sets (uncompleted) so the UI shows rows.
            n_sets = int(sets) if str(sets).isdigit() else 0
            for i in range(n_sets):
                WorkoutSet.objects.create(
                    workout_exercise=we, order=i, completed=False, set_type="working",
                )
            existing_names.add(name)
            order += 1
            created += 1

        day, _ = FitnessDay.objects.get_or_create(date=d)
        day.mode = module.name
        day.save(update_fields=["mode", "updated_at"])
        return Response(
            {"started": module.name, "created": created, "workout": _workout_payload(d)},
            status=status.HTTP_201_CREATED,
        )


class StudyActivityView(ApiKeyMixin, APIView):
    def get(self, request):
        qs = StudyActivity.objects.all()
        d_from = parse_date(request.query_params.get("from"))
        d_to = parse_date(request.query_params.get("to"))
        if d_from:
            qs = qs.filter(date__gte=d_from)
        if d_to:
            qs = qs.filter(date__lte=d_to)
        limit = request.query_params.get("limit")
        if limit and limit.isdigit():
            qs = qs[: int(limit)]
        return Response(StudyActivitySerializer(qs, many=True).data)

    def post(self, request):
        ser = StudyActivitySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(StudyActivitySerializer(obj).data, status=status.HTTP_201_CREATED)


class StudyActivityDetailView(ApiKeyMixin, APIView):
    def get(self, request, pk):
        obj = StudyActivity.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(StudyActivitySerializer(obj).data)

    def patch(self, request, pk):
        obj = StudyActivity.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = StudyActivitySerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(StudyActivitySerializer(obj).data)

    def delete(self, request, pk):
        obj = StudyActivity.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({"deleted": pk})


class WeightLogView(ApiKeyMixin, APIView):
    def get(self, request):
        qs = WeightLog.objects.all()
        d_from = parse_date(request.query_params.get("from"))
        d_to = parse_date(request.query_params.get("to"))
        if d_from:
            qs = qs.filter(date__gte=d_from)
        if d_to:
            qs = qs.filter(date__lte=d_to)
        limit = request.query_params.get("limit")
        if limit and limit.isdigit():
            qs = qs[: int(limit)]
        return Response(WeightLogSerializer(qs, many=True).data)

    def post(self, request):
        ser = WeightLogSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(WeightLogSerializer(obj).data, status=status.HTTP_201_CREATED)


class WeightLogDetailView(ApiKeyMixin, APIView):
    def get(self, request, pk):
        obj = WeightLog.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(WeightLogSerializer(obj).data)

    def patch(self, request, pk):
        obj = WeightLog.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = WeightLogSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(WeightLogSerializer(obj).data)

    def delete(self, request, pk):
        obj = WeightLog.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({"deleted": pk})

# =====================================================================
# Data management — CSV export / import
# =====================================================================
CSV_DATASETS = ["habits", "habit_logs", "weights", "resources", "study_activity"]


class DataExportView(ApiKeyMixin, APIView):
    """GET data/export/?dataset=habits&from=&to=  → CSV (or a ZIP for 'all')."""

    def get(self, request):
        import csv
        import io
        import zipfile
        from django.http import HttpResponse

        dataset = (request.query_params.get("dataset") or "all").strip()
        d_from = parse_date(request.query_params.get("from"))
        d_to = parse_date(request.query_params.get("to"))
        stamp = dt.date.today().isoformat()

        def write_csv(files, name):
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(files["headers"])
            for row in files["rows"]:
                w.writerow(row)
            return buf.getvalue()

        if dataset == "all":
            zbuf = io.BytesIO()
            with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
                for ds in CSV_DATASETS:
                    content = write_csv(self._dataset(ds, d_from, d_to), ds)
                    z.writestr(f"{ds}_{stamp}.csv", content)
                z.writestr("README.txt", self._readme())
            resp = HttpResponse(zbuf.getvalue(), content_type="application/zip")
            resp["Content-Disposition"] = f'attachment; filename="mission2026_complete_{stamp}.zip"'
            return resp

        if dataset not in CSV_DATASETS:
            return Response({"detail": f"unknown dataset '{dataset}'"},
                            status=status.HTTP_400_BAD_REQUEST)
        content = write_csv(self._dataset(dataset, d_from, d_to), dataset)
        resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{dataset}_{stamp}.csv"'
        return resp

    def _dataset(self, ds, d_from, d_to):
        logs = HabitLog.objects.all()
        if d_from:
            logs = logs.filter(date__gte=d_from)
        if d_to:
            logs = logs.filter(date__lte=d_to)

        if ds == "habits":
            return {
                "headers": ["id", "name", "emoji", "color", "order", "active", "status",
                            "description", "target_value", "target_unit"],
                "rows": [
                    [h.id, h.name, h.emoji, h.color, h.order, h.active, h.status,
                     h.description, h.target_value, h.target_unit]
                    for h in Habit.all_objects.all()
                ],
            }
        if ds == "habit_logs":
            return {
                "headers": ["id", "habit_id", "date", "status", "done", "value", "note"],
                "rows": [
                    [l.id, l.habit_id, l.date.isoformat(), l.status or "", l.done,
                     l.value, l.note]
                    for l in logs.select_related("habit")
                ],
            }
        if ds == "weights":
            w = WeightLog.objects.all()
            if d_from:
                w = w.filter(date__gte=d_from)
            if d_to:
                w = w.filter(date__lte=d_to)
            return {
                "headers": ["id", "date", "weight_kg", "time", "notes"],
                "rows": [
                    [x.id, x.date.isoformat(), x.weight_kg,
                     x.time.isoformat() if x.time else "", x.notes]
                    for x in w
                ],
            }
        if ds == "resources":
            return {
                "headers": ["id", "track", "status", "subject", "exam", "paper",
                            "playlist_name", "playlist_url", "videos", "videos_done",
                            "duration_hms", "start_date", "end_date", "notes"],
                "rows": [
                    [r.id, r.track, r.status, r.subject, r.exam, r.paper,
                     r.playlist_name, r.playlist_url, r.videos, r.videos_done,
                     r.duration_hms, r.start_date, r.end_date, r.notes]
                    for r in StudyResource.all_objects.all()
                ],
            }
        # study_activity
        a = StudyActivity.objects.all()
        if d_from:
            a = a.filter(date__gte=d_from)
        if d_to:
            a = a.filter(date__lte=d_to)
        return {
            "headers": ["id", "date", "activity_type", "subject", "resource_id",
                        "time_spent_minutes", "questions_attempted", "questions_completed",
                        "correct_answers", "incorrect_answers", "answers_written",
                        "word_count", "notes"],
            "rows": [
                [x.id, x.date.isoformat(), x.activity_type, x.subject, x.resource_id,
                 x.time_spent_minutes, x.questions_attempted, x.questions_completed,
                 x.correct_answers, x.incorrect_answers, x.answers_written,
                 x.word_count, x.notes]
                for x in a
            ],
        }

    def _readme(self):
        return (
            "Mission 2026 — complete data export\n"
            f"Generated: {dt.date.today().isoformat()}\n\n"
            "Files\n"
            "-----\n"
            "habits_*.csv          id, name, emoji, color, order, active, status, "
            "description, target_value, target_unit\n"
            "habit_logs_*.csv      id, habit_id, date (ISO), status "
            "(pending|done|skipped), done, value, note\n"
            "weights_*.csv         id, date (ISO), weight_kg, time (ISO), notes\n"
            "resources_*.csv       id, track, status, subject, exam, paper, playlist_name, "
            "playlist_url, videos, videos_done, duration_hms, start_date, end_date, notes\n"
            "study_activity_*.csv  id, date (ISO), activity_type, subject, resource_id, "
            "time_spent_minutes, questions_attempted, questions_completed, correct_answers, "
            "incorrect_answers, answers_written, word_count, notes\n\n"
            "Notes\n"
            "-----\n"
            "* All dates/timestamps are ISO-8601. Weights are kilograms. Durations are minutes.\n"
            "* The 'id' column is a stable identifier; habit_logs links via habit_id and\n"
            "  study_activity links via resource_id.\n"
            "* No credentials or tokens are ever exported.\n"
        )


class DataImportView(ApiKeyMixin, APIView):
    """POST data/import/ — validate and import one CSV dataset.

    Body: {dataset, mode: 'new'|'skip_duplicates'|'update', rows: [ {...}, ... ]}
    The browser parses the CSV and sends JSON rows; the server validates every
    row, wraps the write in a transaction and returns a per-row report.
    """

    def post(self, request):
        from django.db import transaction

        dataset = (request.data.get("dataset") or "").strip()
        mode = (request.data.get("mode") or "skip_duplicates").strip()
        rows = request.data.get("rows")
        if dataset not in CSV_DATASETS:
            return Response({"detail": f"unknown dataset '{dataset}'"},
                            status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(rows, list):
            return Response({"detail": "rows must be a list"},
                            status=status.HTTP_400_BAD_REQUEST)

        created = updated = skipped = 0
        errors = []
        try:
            with transaction.atomic():
                for idx, raw in enumerate(rows):
                    if not isinstance(raw, dict):
                        errors.append({"row": idx + 2, "reason": "not a key/value row"})
                        continue
                    try:
                        action = self._import_row(dataset, raw, mode)
                    except ValueError as e:
                        errors.append({"row": idx + 2, "reason": str(e)})
                        continue
                    if action == "created":
                        created += 1
                    elif action == "updated":
                        updated += 1
                    else:
                        skipped += 1
        except Exception as e:  # pragma: no cover - safety net
            return Response(
                {"detail": f"Import failed, no changes were saved: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "dataset": dataset,
            "mode": mode,
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "invalid": len(errors),
            "errors": errors[:200],
        })

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _int(v, default=None):
        if v is None or str(v).strip() == "":
            return default
        return int(float(str(v).strip()))

    @staticmethod
    def _date(v, required=True):
        v = (str(v).strip() if v is not None else "")
        if not v:
            if required:
                raise ValueError("date is required")
            return None
        try:
            return dt.date.fromisoformat(v[:10])
        except ValueError:
            raise ValueError(f"invalid date '{v}' (expected YYYY-MM-DD)")

    def _import_row(self, dataset, raw, mode):
        if dataset == "habits":
            name = (raw.get("name") or "").strip()
            if not name:
                raise ValueError("name is required")
            rid = self._int(raw.get("id"))
            existing = Habit.all_objects.filter(pk=rid).first() if rid else None
            if existing is None:
                existing = Habit.all_objects.filter(name=name).first()
            if existing:
                if mode == "skip_duplicates":
                    return "skipped"
                if mode == "update":
                    existing.emoji = raw.get("emoji") or existing.emoji
                    existing.color = raw.get("color") or existing.color
                    existing.status = raw.get("status") or existing.status
                    existing.active = str(raw.get("active", "True")).lower() in ("1", "true", "yes")
                    existing.description = raw.get("description") or ""
                    existing.save()
                    return "updated"
                return "skipped"
            Habit.all_objects.create(
                id=rid,
                name=name,
                emoji=raw.get("emoji") or "✅",
                color=raw.get("color") or "#22c55e",
                order=self._int(raw.get("order"), 0) or 0,
                active=str(raw.get("active", "True")).lower() in ("1", "true", "yes"),
                status=raw.get("status") or Habit.STATUS_ACTIVE,
                description=raw.get("description") or "",
            )
            return "created"

        if dataset == "habit_logs":
            habit_id = self._int(raw.get("habit_id"))
            if not habit_id or not Habit.all_objects.filter(pk=habit_id).exists():
                raise ValueError(f"unknown habit_id '{raw.get('habit_id')}'")
            date = self._date(raw.get("date"))
            status_v = (raw.get("status") or "").strip()
            if status_v and status_v not in ("pending", "done", "skipped"):
                raise ValueError(f"invalid status '{status_v}'")
            done = str(raw.get("done", "")).lower() in ("1", "true", "yes")
            if not status_v:
                status_v = "done" if done else "pending"
            done = status_v == "done"
            existing = HabitLog.all_objects.filter(habit_id=habit_id, date=date).first()
            if existing:
                if mode == "skip_duplicates":
                    return "skipped"
                if mode == "update":
                    existing.status = status_v
                    existing.done = done
                    existing.value = raw.get("value") or None
                    existing.note = raw.get("note") or ""
                    existing.save()
                    return "updated"
                return "skipped"
            HabitLog.all_objects.create(
                habit_id=habit_id, date=date, status=status_v, done=done,
                value=raw.get("value") or None, note=raw.get("note") or "",
            )
            return "created"

        if dataset == "weights":
            date = self._date(raw.get("date"))
            kg = raw.get("weight_kg")
            try:
                kg = float(str(kg).strip())
            except (TypeError, ValueError):
                raise ValueError(f"invalid weight_kg '{kg}'")
            if kg <= 0:
                raise ValueError("weight_kg must be positive")
            existing = WeightLog.all_objects.filter(date=date, weight_kg=kg).first()
            if existing:
                if mode == "update":
                    existing.notes = raw.get("notes") or existing.notes
                    existing.save()
                    return "updated"
                return "skipped"
            WeightLog.all_objects.create(date=date, weight_kg=kg, notes=raw.get("notes") or "")
            return "created"

        if dataset == "resources":
            subject = (raw.get("subject") or "").strip()
            if not subject:
                raise ValueError("subject is required")
            rid = self._int(raw.get("id"))
            existing = StudyResource.all_objects.filter(pk=rid).first() if rid else None
            if existing is None:
                existing = StudyResource.all_objects.filter(
                    subject=subject, playlist_name=raw.get("playlist_name") or "").first()
            if existing:
                if mode == "update":
                    existing.track = raw.get("track") or existing.track
                    existing.status = raw.get("status") or existing.status
                    existing.videos_done = self._int(raw.get("videos_done"), existing.videos_done)
                    existing.notes = raw.get("notes") or existing.notes
                    existing.save()
                    return "updated"
                return "skipped"
            StudyResource.all_objects.create(
                id=rid,
                track=raw.get("track") or StudyResource.TRACK_PENDING,
                status=raw.get("status") or "Pending",
                subject=subject,
                exam=raw.get("exam") or "",
                paper=raw.get("paper") or "",
                playlist_name=raw.get("playlist_name") or "",
                playlist_url=raw.get("playlist_url") or "",
                videos=self._int(raw.get("videos")),
                videos_done=self._int(raw.get("videos_done"), 0) or 0,
                duration_hms=raw.get("duration_hms") or "",
                start_date=raw.get("start_date") or "",
                end_date=raw.get("end_date") or "",
                notes=raw.get("notes") or "",
            )
            return "created"

        # study_activity
        date = self._date(raw.get("date"))
        atype = (raw.get("activity_type") or "study_session").strip()
        allowed = ("study_session", "mcq", "answer_writing", "revision", "mock_test")
        if atype not in allowed:
            raise ValueError(f"invalid activity_type '{atype}'")
        attempted = self._int(raw.get("questions_attempted"))
        completed = self._int(raw.get("questions_completed"))
        correct = self._int(raw.get("correct_answers"))
        incorrect = self._int(raw.get("incorrect_answers"))
        for label, v in (("questions_attempted", attempted), ("questions_completed", completed),
                         ("correct_answers", correct), ("incorrect_answers", incorrect)):
            if v is not None and v < 0:
                raise ValueError(f"{label} must be non-negative")
        if attempted is not None and completed is not None and completed > attempted:
            raise ValueError("questions_completed cannot exceed questions_attempted")
        if attempted is not None and (correct or 0) + (incorrect or 0) > attempted:
            raise ValueError("correct + incorrect cannot exceed questions_attempted")
        rid = self._int(raw.get("resource_id"))
        resource = StudyResource.all_objects.filter(pk=rid).first() if rid else None
        StudyActivity.all_objects.create(
            date=date,
            activity_type=atype,
            subject=raw.get("subject") or "",
            resource=resource,
            time_spent_minutes=self._int(raw.get("time_spent_minutes")),
            questions_attempted=attempted,
            questions_completed=completed,
            correct_answers=correct,
            incorrect_answers=incorrect,
            answers_written=self._int(raw.get("answers_written")),
            word_count=self._int(raw.get("word_count")),
            notes=raw.get("notes") or "",
        )
        return "created"


# =====================================================================
# Jaap — the mantra counter
# =====================================================================
def _jaap_day_summary(date):
    """Today's jaap roll-up, shared by the jaap and stats endpoints."""
    logs = list(JaapLog.objects.filter(date=date).select_related("mantra"))
    total = sum(l.count for l in logs)
    malas = sum(l.malas for l in logs)
    return {
        "date": date.isoformat(),
        "total": total,
        "malas": malas,
        "by_mantra": {
            l.mantra_id: {
                "count": l.count,
                "malas": l.malas,
                "beads": l.mantra.beads,
                "goal": l.mantra.goal,
            }
            for l in logs
        },
    }


def _jaap_streak(mantra, today):
    """Consecutive days up to today where the mantra's goal was met.

    A day qualifies when count >= the mantra's goal. With no goal set, any
    count qualifies (goal falls back to 1).
    """
    goal = mantra.goal
    rows = (
        JaapLog.objects.filter(mantra=mantra, date__lte=today, count__gte=goal)
        .order_by("-date")
        .values_list("date", flat=True)
    )
    dates = set(rows)
    if not dates:
        return 0
    streak = 0
    day = today if today in dates else today - dt.timedelta(days=1)
    while day in dates:
        streak += 1
        day -= dt.timedelta(days=1)
    return streak


class JaapMantrasView(ApiKeyMixin, APIView):
    """GET/POST jaap-mantras/ — the chant library.

    GET params: include_deleted=1 to see retired mantras too.
    POST body: {name, devanagari?, transliteration?, category?, deity?,
                mala_size?, daily_goal?, color?, is_active?, sort_order?}
    """

    def get(self, request):
        qs = JaapMantra.objects.all()
        if request.query_params.get("include_deleted") == "1":
            qs = JaapMantra.all_objects.all()
        else:
            qs = qs.filter(is_active=True)
        return Response(JaapMantraSerializer(qs, many=True).data)

    def post(self, request):
        ser = JaapMantraSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        return Response(JaapMantraSerializer(obj).data, status=status.HTTP_201_CREATED)


class JaapMantraDetailView(ApiKeyMixin, APIView):
    """PATCH/DELETE jaap-mantras/<pk>/"""

    def patch(self, request, pk):
        obj = JaapMantra.objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = JaapMantraSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        # the bead count changed, so every cached mala count is now stale
        for log in JaapLog.objects.filter(mantra=obj):
            old = log.malas
            new = log.recalc_malas()
            if new != old:
                log.save(update_fields=["malas", "updated_at"])
        return Response(JaapMantraSerializer(obj).data)

    def delete(self, request, pk):
        obj = JaapMantra.all_objects.filter(pk=pk).first()
        if not obj:
            return Response({"detail": "not found"}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response({"deleted": pk, "soft": True})


class JaapView(ApiKeyMixin, APIView):
    """GET jaap/ — counts for a day or a range.

    GET params: date (single day) or from/to (range). Always returns the
    library so the app can render the mantra picker in one round trip.
    """

    def get(self, request):
        date = parse_date(request.query_params.get("date"))
        d_from = parse_date(request.query_params.get("from"))
        d_to = parse_date(request.query_params.get("to"))
        qs = JaapLog.objects.all()
        if date:
            qs = qs.filter(date=date)
        else:
            if d_from:
                qs = qs.filter(date__gte=d_from)
            if d_to:
                qs = qs.filter(date__lte=d_to)
        logs = list(qs.select_related("mantra"))
        today = date or dt.date.today()
        return Response({
            "date": today.isoformat(),
            "logs": JaapLogSerializer(logs, many=True).data,
            "mantras": JaapMantraSerializer(
                JaapMantra.objects.filter(is_active=True), many=True
            ).data,
            "summary": _jaap_day_summary(today),
        })


class JaapTapView(ApiKeyMixin, APIView):
    """POST jaap/tap/ — the counter's hot path.

    Body: {mantra, date?, delta?}  (delta defaults to 1, -1 undoes)

    Every tap is its own request, so this has to be cheap and safe to repeat:
    the count is incremented atomically and the response carries the new
    total, the completed malas and the streak.
    """

    def post(self, request):
        mantra_id = request.data.get("mantra")
        mantra = JaapMantra.objects.filter(pk=mantra_id).first()
        if not mantra:
            return Response({"detail": "mantra not found"}, status=status.HTTP_404_NOT_FOUND)
        date = parse_date(request.data.get("date")) or dt.date.today()
        try:
            delta = int(request.data.get("delta", 1))
        except (TypeError, ValueError):
            delta = 1
        if delta == 0:
            delta = 1

        from django.db import IntegrityError, transaction

        with transaction.atomic():
            log = (
                JaapLog.all_objects.select_for_update()
                .filter(mantra=mantra, date=date)
                .first()
            )
            if log is None:
                try:
                    log = JaapLog.objects.create(
                        mantra=mantra, date=date, count=0, source=JaapLog.SOURCE_APP
                    )
                except IntegrityError:
                    log = JaapLog.objects.select_for_update().get(mantra=mantra, date=date)
            if log.deleted_at:
                log.deleted_at = None
            # a count never goes below zero
            log.count = max(0, int(log.count or 0) + delta)
            log.recalc_malas()
            log.save(update_fields=["count", "malas", "deleted_at", "updated_at"])

        return Response({
            "mantra": mantra.id,
            "date": date.isoformat(),
            "count": log.count,
            "malas": log.malas,
            "beads": mantra.beads,
            "goal": mantra.goal,
            # true when this tap completed a round — the app rings the bell
            "mala_completed": log.malas > 0 and log.count % mantra.beads == 0,
            "streak": _jaap_streak(mantra, date),
            "log": JaapLogSerializer(log).data,
        })


class JaapStatsView(ApiKeyMixin, APIView):
    """GET jaap/stats/ — streaks, totals and a daily series.

    GET params: days (window for the series, default 30), date (anchor).
    """

    def get(self, request):
        days = int(request.query_params.get("days", 30) or 30)
        days = max(1, min(days, 365))
        today = parse_date(request.query_params.get("date")) or dt.date.today()
        start = today - dt.timedelta(days=days - 1)

        mantras = list(JaapMantra.objects.filter(is_active=True))
        logs = list(
            JaapLog.objects.filter(date__gte=start, date__lte=today).select_related("mantra")
        )
        by_date = {}
        for l in logs:
            by_date[l.date] = by_date.get(l.date, 0) + l.count

        series = []
        for i in range(days):
            d = start + dt.timedelta(days=i)
            series.append({
                "date": d.isoformat(),
                "count": by_date.get(d, 0),
            })

        per_mantra = []
        lifetime = 0
        for m in mantras:
            m_logs = [l for l in logs if l.mantra_id == m.id]
            total = sum(l.count for l in m_logs)
            lifetime += total
            per_mantra.append({
                "mantra": m.id,
                "name": m.name,
                "devanagari": m.devanagari,
                "color": m.color,
                "beads": m.beads,
                "goal": m.goal,
                "total": total,
                "malas": sum(l.malas for l in m_logs),
                "days": len([l for l in m_logs if l.count > 0]),
                "streak": _jaap_streak(m, today),
                "today": next((l.count for l in m_logs if l.date == today), 0),
            })
        per_mantra.sort(key=lambda r: -r["total"])

        return Response({
            "date": today.isoformat(),
            "from": start.isoformat(),
            "to": today.isoformat(),
            "days": days,
            "lifetime": lifetime,
            "total_malas": sum(l.malas for l in logs),
            "today_total": by_date.get(today, 0),
            "per_mantra": per_mantra,
            "series": series,
        })
