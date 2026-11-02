"""Tests for the PRD features: weight logging, timezones, habit calendar
states, range analytics, MCQ/answer-writing aggregation, study-activity
edits/deletes and CSV import/export edge cases."""
import datetime as dt
import io
import zipfile

from django.test import TestCase
from rest_framework.test import APIClient

from . import analytics
from .models import (
    CheckinMember,
    DailyCheckin,
    DrinkLog,
    Setting,
    BodyMeasurement,
    Habit,
    HabitLog,
    IntakeLog,
    StudyActivity,
    StudyResource,
    WeightLog,
    WorkoutModule,
)


class ApiTestBase(TestCase):
    def setUp(self):
        self.client = APIClient()


# ---------------------------------------------------------------- weight logs
class WeightLogTests(ApiTestBase):
    def test_create_and_edit_weight(self):
        r = self.client.post(
            "/api/fitness/weight/", {"date": "2026-10-21", "weight_kg": 104.8}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        pk = r.data["id"]
        self.assertEqual(float(r.data["weight_kg"]), 104.8)

        r = self.client.patch(
            f"/api/fitness/weight/{pk}/", {"weight_kg": 104.2}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(float(r.data["weight_kg"]), 104.2)

    def test_patch_previous_record(self):
        for i, kg in enumerate([105.0, 104.5, 104.0]):
            self.client.post(
                "/api/fitness/weight/",
                {"date": f"2026-10-{18 + i}", "weight_kg": kg},
                format="json",
            )
        r = self.client.get("/api/fitness/weight/?limit=90")
        self.assertEqual(len(r.data), 3)
        # newest first (ordering is -date)
        self.assertEqual(r.data[0]["date"], "2026-10-20")

        older = WeightLog.objects.order_by("date").first()
        r = self.client.patch(
            f"/api/fitness/weight/{older.id}/",
            {"weight_kg": 105.7, "time": "07:15:00"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(float(r.data["weight_kg"]), 105.7)
        self.assertEqual(r.data["time"], "07:15:00")

    def test_delete_weight(self):
        r = self.client.post(
            "/api/fitness/weight/", {"date": "2026-10-21", "weight_kg": 100}, format="json"
        )
        pk = r.data["id"]
        self.assertEqual(self.client.delete(f"/api/fitness/weight/{pk}/").status_code, 200)
        self.assertEqual(WeightLog.objects.count(), 0)

    def test_weight_requires_positive_value(self):
        r = self.client.post(
            "/api/fitness/weight/", {"date": "2026-10-21", "weight_kg": -3}, format="json"
        )
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------- habit calendar
class HabitCalendarTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.h = Habit.objects.create(name="Wake", emoji="⏰", color="#f59e0b")

    def _log(self, date, status):
        return self.client.post(
            "/api/habits/toggle/",
            {"habit": self.h.id, "date": date, "status": status,
             "done": status == "done"},
            format="json",
        )

    def test_backdated_correction_sets_status(self):
        self._log("2026-10-18", "skipped")
        log = HabitLog.objects.get(habit=self.h, date=dt.date(2026, 10, 18))
        self.assertEqual(log.status, "skipped")

        self._log("2026-10-18", "done")
        log.refresh_from_db()
        self.assertEqual(log.status, "done")
        self.assertTrue(log.done)

        self._log("2026-10-18", "pending")
        log.refresh_from_db()
        self.assertEqual(log.status, "pending")
        self.assertFalse(log.done)

    def test_marks_exposed_in_habit_list(self):
        self._log(dt.date.today().isoformat(), "done")
        r = self.client.get("/api/habits/")
        row = next(x for x in r.data if x["id"] == self.h.id)
        self.assertIn(dt.date.today().isoformat(), row["marks"])

    def test_in_progress_is_accepted_and_stored(self):
        self._log("2026-10-18", "in_progress")
        log = HabitLog.objects.get(habit=self.h, date=dt.date(2026, 10, 18))
        self.assertEqual(log.status, "in_progress")
        self.assertFalse(log.done, "in progress is not done")

    def test_in_progress_can_be_promoted_to_done(self):
        self._log("2026-10-18", "in_progress")
        self._log("2026-10-18", "done")
        log = HabitLog.objects.get(habit=self.h, date=dt.date(2026, 10, 18))
        self.assertEqual(log.status, "done")
        self.assertTrue(log.done)

    def test_pending_clears_a_previously_done_habit(self):
        self._log("2026-10-18", "done")
        self._log("2026-10-18", "pending")
        log = HabitLog.objects.get(habit=self.h, date=dt.date(2026, 10, 18))
        self.assertEqual(log.status, "pending")
        self.assertFalse(log.done)

    def test_invalid_status_is_rejected_not_silently_flipped(self):
        # A typo must not rewrite the habit (e.g. "in progress" with a space).
        r = self.client.post(
            "/api/habits/toggle/",
            {"habit": self.h.id, "date": "2026-10-18", "status": "in progress"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn("allowed", r.data)
        self.assertIn("in_progress", r.data["allowed"])
        self.assertFalse(
            HabitLog.objects.filter(habit=self.h, date=dt.date(2026, 10, 18)).exists()
        )

    def test_cycle_from_in_progress_goes_to_done(self):
        self.client.post(
            "/api/habits/toggle/",
            {"habit": self.h.id, "date": "2026-10-18", "status": "in_progress"},
            format="json",
        )
        r = self.client.post(
            "/api/habits/toggle/",
            {"habit": self.h.id, "date": "2026-10-18", "cycle": True},
            format="json",
        )
        self.assertEqual(r.data["status"], "done")

    def test_overview_reports_in_progress_count(self):
        today = dt.date.today().isoformat()
        self._log(today, "in_progress")
        r = self.client.get(f"/api/overview/?date={today}")
        self.assertEqual(r.data["in_progress_today"], 1)
        row = next(x for x in r.data["habits"] if x["id"] == self.h.id)
        self.assertEqual(row["status_today"], "in_progress")
        self.assertFalse(row["done_today"])

    def test_timestamps_are_localised(self):
        self._log(dt.date.today().isoformat(), "done")
        r = self.client.get(f"/api/overview/?date={dt.date.today().isoformat()}")
        row = next(x for x in r.data["habits"] if x["id"] == self.h.id)
        self.assertIsNotNone(row["logged_at"])
        # localtime iso strings carry an explicit offset
        self.assertTrue("+" in row["logged_at"] or row["logged_at"].endswith("Z"))


# ---------------------------------------------------------------- check-in bridge
class CheckinBridgeTests(ApiTestBase):
    """The WhatsApp bot pushes done/missed/in_progress/pending; HabitLog follows."""

    def setUp(self):
        super().setUp()
        self.h = Habit.objects.create(name="Wake 4 AM", emoji="⏰", color="#f59e0b")
        self.d = "2026-10-18"

    def _post(self, **extra):
        body = {"member": "274925319360578", "name": "Saksham", "date": self.d}
        body.update(extra)
        return self.client.post("/api/mission/checkins/", body, format="json")

    def test_in_progress_becomes_a_habit_log_in_progress(self):
        r = self._post(in_progress=["wake_4_am"])
        self.assertEqual(r.status_code, 201)
        log = HabitLog.objects.get(habit=self.h, date=dt.date(2026, 10, 18))
        self.assertEqual(log.status, "in_progress")
        self.assertFalse(log.done)

    def test_pending_clears_a_previously_done_habit(self):
        self._post(done=["wake_4_am"])
        log = HabitLog.objects.get(habit=self.h, date=dt.date(2026, 10, 18))
        self.assertEqual(log.status, "done")

        self._post(pending=["wake_4_am"])
        log.refresh_from_db()
        self.assertEqual(log.status, "pending")
        self.assertFalse(log.done)

    def test_buckets_are_stored_separately(self):
        self._post(done=["wake_4_am"], in_progress=["upsc"], pending=["diet"])
        c = DailyCheckin.objects.get(date=dt.date(2026, 10, 18))
        self.assertEqual(c.done, ["wake_4_am"])
        self.assertEqual(c.in_progress, ["upsc"])
        self.assertEqual(c.pending, ["diet"])

    def test_score_ignores_in_progress(self):
        # in-progress is not a decision, so it must not drag the score down.
        self._post(done=["wake_4_am"], in_progress=["upsc"])
        c = DailyCheckin.objects.get(date=dt.date(2026, 10, 18))
        self.assertEqual(c.score, 100)

    def test_get_returns_every_bucket(self):
        self._post(done=["wake_4_am"], in_progress=["upsc"], pending=["diet"])
        r = self.client.get(f"/api/mission/checkins/?date={self.d}")
        row = r.data[0]
        self.assertEqual(row["in_progress"], ["upsc"])
        self.assertEqual(row["pending"], ["diet"])

    def test_habit_the_app_does_not_know_is_ignored(self):
        self._post(in_progress=["a_habit_that_does_not_exist"])
        # nothing to write, but the check-in itself is still recorded
        self.assertTrue(
            DailyCheckin.objects.filter(date=dt.date(2026, 10, 18)).exists()
        )


# ---------------------------------------------------------------- range analytics
class RangeAnalyticsTests(ApiTestBase):
    def setUp(self):
        super().setUp()
        self.h = Habit.objects.create(name="Wake", emoji="⏰", color="#f59e0b")
        today = dt.date(2026, 10, 21)
        # 4 done out of the last 10 days, 1 skipped
        for offset, status in [(0, "done"), (1, "done"), (2, "skipped"),
                               (3, "done"), (4, "done")]:
            HabitLog.objects.create(
                habit=self.h, date=today - dt.timedelta(days=offset),
                status=status, done=status == "done",
            )

    def test_summary_and_series(self):
        data = analytics.range_analytics(10, today=dt.date(2026, 10, 21))
        s = data["summary"]
        self.assertEqual(s["habit_count"], 1)
        self.assertEqual(s["done_today"], 1)
        self.assertEqual(s["skipped_today"], 0)
        self.assertGreater(s["overall"], 0)
        # a day with no schedule is None, not 0
        self.assertIn(None, [row["rate"] for row in data["series"]])

    def test_habit_row_counts(self):
        data = analytics.range_analytics(10, today=dt.date(2026, 10, 21))
        row = data["habits"][0]
        self.assertEqual(row["completed_days"], 4)
        self.assertEqual(row["skipped_days"], 1)
        # window starts at the habit's first log (today-4) → 4 of 5 days = 80%
        self.assertEqual(row["completion"], 80)
        self.assertEqual(row["days_tracked"], 5)
        self.assertIsInstance(row["change"], int)

    def test_empty_range_is_neutral(self):
        HabitLog.objects.all().delete()
        data = analytics.range_analytics(30, today=dt.date(2026, 10, 21))
        # habit exists but was never logged in range: it is scheduled/missed
        self.assertEqual(data["habits"][0]["completed_days"], 0)
        # no habits at all → truly neutral, every cell None
        Habit.objects.all().delete()
        data = analytics.range_analytics(30, today=dt.date(2026, 10, 21))
        self.assertTrue(all(row["rate"] is None for row in data["series"]))
        self.assertEqual(data["habits"], [])


# ---------------------------------------------------------------- study activity
class StudyActivityTests(ApiTestBase):
    def test_mcq_aggregation_is_exact(self):
        for attempted, completed, correct, incorrect in [
            (50, 45, 36, 9), (30, 30, 28, 2),
        ]:
            r = self.client.post(
                "/api/study/activity/",
                {"date": "2026-10-21", "activity_type": "mcq",
                 "subject": "History", "questions_attempted": attempted,
                 "questions_completed": completed, "correct_answers": correct,
                 "incorrect_answers": incorrect, "time_spent_minutes": 30},
                format="json",
            )
            self.assertEqual(r.status_code, 201)

        r = self.client.get("/api/study/activity/")
        self.assertEqual(len(r.data), 2)
        # no auto-increment: values are stored exactly as sent
        self.assertEqual(r.data[0]["questions_attempted"], 30)

    def test_activity_edit_and_delete(self):
        r = self.client.post(
            "/api/study/activity/",
            {"date": "2026-10-21", "activity_type": "answer_writing",
             "answers_written": 2, "word_count": 500},
            format="json",
        )
        pk = r.data["id"]
        r = self.client.patch(
            f"/api/study/activity/{pk}/", {"answers_written": 3}, format="json"
        )
        self.assertEqual(r.data["answers_written"], 3)
        self.assertEqual(r.status_code, 200)

        self.assertEqual(
            self.client.delete(f"/api/study/activity/{pk}/").status_code, 200
        )
        self.assertEqual(StudyActivity.objects.count(), 0)

    def test_multiple_sessions_same_day(self):
        for t in ["study_session", "revision"]:
            self.client.post(
                "/api/study/activity/",
                {"date": "2026-10-21", "activity_type": t, "time_spent_minutes": 45},
                format="json",
            )
        self.assertEqual(
            StudyActivity.objects.filter(date=dt.date(2026, 10, 21)).count(), 2
        )

    def test_validation_rejects_impossible_counts(self):
        r = self.client.post(
            "/api/study/activity/",
            {"date": "2026-10-21", "activity_type": "mcq",
             "questions_attempted": 10, "questions_completed": 20},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_analytics_include_activity(self):
        self.client.post(
            "/api/study/activity/",
            {"date": dt.date.today().isoformat(), "activity_type": "mcq",
             "questions_attempted": 40, "questions_completed": 40,
             "correct_answers": 32, "incorrect_answers": 8,
             "time_spent_minutes": 60},
            format="json",
        )
        r = self.client.get("/api/study/analytics/?days=60")
        self.assertEqual(r.data["activity"]["completed"], 40)
        self.assertEqual(r.data["activity"]["accuracy"], 80)


class StudyResourceProgressTests(ApiTestBase):
    def test_videos_done_updates_progress_pct(self):
        res = StudyResource.objects.create(
            subject="Sociology", track=StudyResource.TRACK_IN_PROGRESS,
            status="In-Progress", videos=114,
        )
        r = self.client.patch(
            f"/api/resources/{res.id}/", {"videos_done": 57}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["videos_done"], 57)
        self.assertEqual(r.data["progress_pct"], 50)

    def test_videos_done_cannot_exceed_total(self):
        res = StudyResource.objects.create(
            subject="Economy", track=StudyResource.TRACK_IN_PROGRESS, videos=10)
        r = self.client.patch(
            f"/api/resources/{res.id}/", {"videos_done": 11}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("videos_done", r.data)

    def test_videos_done_rejects_negative(self):
        res = StudyResource.objects.create(
            subject="Polity", track=StudyResource.TRACK_IN_PROGRESS, videos=10)
        r = self.client.patch(
            f"/api/resources/{res.id}/", {"videos_done": -1}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_moving_to_completed_marks_all_videos_done(self):
        res = StudyResource.objects.create(
            subject="History", track=StudyResource.TRACK_IN_PROGRESS, videos=40)
        r = self.client.post(
            f"/api/resources/{res.id}/move/", {"track": "completed"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["videos_done"], 40)
        self.assertEqual(r.data["progress_pct"], 100)


# ---------------------------------------------------------------- csv export/import
class CsvExportTests(ApiTestBase):
    def test_single_dataset_has_header_and_iso_dates(self):
        Habit.objects.create(name="Wake", emoji="⏰", color="#f59e0b")
        r = self.client.get("/api/data/export/?dataset=habits")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8")
        self.assertTrue(body.startswith("id,name,emoji"))
        self.assertNotIn("password", body.lower())

    def test_zip_export_contains_readme(self):
        r = self.client.get("/api/data/export/?dataset=all")
        self.assertEqual(r.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            names = z.namelist()
            self.assertTrue(any(n.startswith("habits_") for n in names))
            self.assertIn("README.txt", names)

    def test_unicode_round_trip_escaped(self):
        Habit.objects.create(name='Wake, "early"', emoji="⏰", color="#f59e0b")
        r = self.client.get("/api/data/export/?dataset=habits")
        body = r.content.decode("utf-8")
        self.assertIn('"Wake, ""early"""', body)


class CsvImportTests(ApiTestBase):
    def test_skip_duplicates_and_report(self):
        h = Habit.objects.create(name="Wake", emoji="⏰", color="#f59e0b")
        HabitLog.objects.create(habit=h, date=dt.date(2026, 10, 20), status="done", done=True)
        r = self.client.post(
            "/api/data/import/",
            {"dataset": "habit_logs", "mode": "skip_duplicates",
             "rows": [
                 {"habit_id": h.id, "date": "2026-10-20", "status": "done"},
                 {"habit_id": h.id, "date": "2026-10-21", "status": "done"},
                 {"habit_id": h.id, "date": "bad", "status": "done"},
             ]},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["created"], 1)
        self.assertEqual(r.data["skipped"], 1)
        self.assertEqual(r.data["invalid"], 1)
        self.assertEqual(r.data["errors"][0]["row"], 4)

    def test_update_mode_overwrites_match(self):
        h = Habit.objects.create(name="Wake", emoji="⏰", color="#f59e0b")
        HabitLog.objects.create(habit=h, date=dt.date(2026, 10, 20), status="pending", done=False)
        self.client.post(
            "/api/data/import/",
            {"dataset": "habit_logs", "mode": "update",
             "rows": [{"habit_id": h.id, "date": "2026-10-20", "status": "done"}]},
            format="json",
        )
        log = HabitLog.objects.get(habit=h, date=dt.date(2026, 10, 20))
        self.assertEqual(log.status, "done")
        self.assertTrue(log.done)

    def test_invalid_dataset_rejected(self):
        r = self.client.post(
            "/api/data/import/", {"dataset": "nope", "rows": []}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_weight_import_validates_positive(self):
        r = self.client.post(
            "/api/data/import/",
            {"dataset": "weights", "mode": "new",
             "rows": [{"date": "2026-10-21", "weight_kg": "x"}]},
            format="json",
        )
        self.assertEqual(r.data["invalid"], 1)

    def test_study_activity_import_validates_counts(self):
        r = self.client.post(
            "/api/data/import/",
            {"dataset": "study_activity", "mode": "new",
             "rows": [{"date": "2026-10-21", "activity_type": "mcq",
                       "questions_attempted": 5, "questions_completed": 9}]},
            format="json",
        )
        self.assertEqual(r.data["invalid"], 1)
        self.assertEqual(StudyActivity.objects.count(), 0)


# ---------------------------------------------------------------- legend fitness
class BodyMeasurementTests(ApiTestBase):
    def test_post_upserts_one_row_per_date(self):
        r = self.client.post(
            "/api/body-measurements/",
            {"date": "2026-10-21", "chest_cm": 102.5, "waist_cm": 88},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        # posting the same date again replaces rather than duplicates
        r2 = self.client.post(
            "/api/body-measurements/",
            {"date": "2026-10-21", "waist_cm": 87},
            format="json",
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(BodyMeasurement.objects.count(), 1)
        self.assertEqual(float(BodyMeasurement.objects.first().waist_cm), 87.0)

    def test_latest_summary_and_negative_rejected(self):
        self.client.post(
            "/api/body-measurements/",
            {"date": "2026-10-20", "chest_cm": 101},
            format="json",
        )
        self.client.post(
            "/api/body-measurements/",
            {"date": "2026-10-21", "chest_cm": 102},
            format="json",
        )
        r = self.client.get("/api/body-measurements/")
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(r.data["latest"]["chest_cm"], 102.0)
        bad = self.client.post(
            "/api/body-measurements/",
            {"date": "2026-10-22", "chest_cm": -5},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)


class IntakeTests(ApiTestBase):
    def test_add_mode_accumulates(self):
        self.client.post(
            "/api/intake/",
            {"date": "2026-10-21", "water_ml": 500, "protein_g": 30},
            format="json",
        )
        self.client.post(
            "/api/intake/",
            {"date": "2026-10-21", "mode": "add", "water_ml": 250, "protein_g": 25},
            format="json",
        )
        row = IntakeLog.objects.get(date=dt.date(2026, 10, 21))
        self.assertEqual(row.water_ml, 750)
        self.assertEqual(row.protein_g, 55)

    def test_get_returns_targets(self):
        r = self.client.get("/api/intake/?date=2026-10-21")
        self.assertEqual(r.data["water_ml"], 0)
        self.assertIn("water_ml", r.data["targets"])
        self.assertIn("protein_g", r.data["targets"])


class WorkoutSessionTests(ApiTestBase):
    def test_patch_workout_finishes_with_status_and_notes(self):
        r = self.client.patch(
            "/api/workout/2026-10-21/",
            {"status": "Completed", "notes": "solid session"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "Completed")
        self.assertEqual(r.data["notes"], "solid session")

    def test_patch_workout_rejects_unknown_status(self):
        r = self.client.patch(
            "/api/workout/2026-10-21/", {"status": "Banana"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_start_routine_prefills_exercises(self):
        module = WorkoutModule.objects.create(
            name="Push",
            exercises=[
                {"name": "Bench Press", "muscle": "Chest", "sets": 3, "reps": "6-8"},
                {"name": "Overhead Press", "muscle": "Shoulders", "sets": 3, "reps": "8-10"},
            ],
        )
        r = self.client.post(
            "/api/workout/2026-10-21/start/", {"module": module.id}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["created"], 2)
        names = [e["name"] for e in r.data["workout"]["exercises"]]
        self.assertIn("Bench Press", names)
        self.assertEqual(r.data["workout"]["module"], "Push")
        # each planned set is created uncompleted so the user just logs numbers
        bench = next(e for e in r.data["workout"]["exercises"] if e["name"] == "Bench Press")
        self.assertEqual(len(bench["sets"]), 3)
        self.assertTrue(all(s["completed"] is False for s in bench["sets"]))

    def test_start_routine_unknown_module_is_404(self):
        r = self.client.post(
            "/api/workout/2026-10-21/start/", {"module": 9999}, format="json")
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------- drinks / insights
class DrinkLogTests(ApiTestBase):
    def test_preset_fills_caffeine_and_calories(self):
        r = self.client.post("/api/drinks/", {"drink_type": "coffee"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["volume_ml"], 150)   # preset serving
        self.assertEqual(r.data["caffeine_mg"], 95)
        self.assertEqual(r.data["calories"], 2)

    def test_water_drink_syncs_intake_total(self):
        self.client.post("/api/drinks/", {"drink_type": "water", "volume_ml": 500}, format="json")
        r = self.client.get("/api/drinks/?date=2026-10-21")
        # POST defaults to today; query that day explicitly
        today = dt.date.today().isoformat()
        r = self.client.get(f"/api/drinks/?date={today}")
        self.assertEqual(r.data["summary"]["water_ml"], 500)
        intake = self.client.get(f"/api/intake/?date={today}")
        self.assertEqual(intake.data["water_ml"], 500)

    def test_unknown_drink_type_rejected(self):
        r = self.client.post("/api/drinks/", {"drink_type": "beer"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("drink_type", r.data)

    def test_delete_resyncs_water(self):
        r = self.client.post("/api/drinks/", {"drink_type": "water", "volume_ml": 300}, format="json")
        self.client.delete(f"/api/drinks/{r.data['id']}/")
        today = dt.date.today().isoformat()
        summary = self.client.get(f"/api/drinks/?date={today}").data["summary"]
        self.assertEqual(summary["water_ml"], 0)


class WeightInsightsTests(ApiTestBase):
    def test_bmi_computed_from_height_setting(self):
        Setting.objects.create(key="height_cm", value="178")
        WeightLog.objects.create(date=dt.date(2026, 10, 21), weight_kg=80)
        r = self.client.get("/api/weight-insights/")
        self.assertEqual(r.data["bmi"], 25.25)
        self.assertEqual(r.data["bmi_category"], "Overweight")
        self.assertEqual(r.data["healthy_min_kg"], 58.6)

    def test_no_height_means_no_bmi(self):
        WeightLog.objects.create(date=dt.date(2026, 10, 21), weight_kg=80)
        r = self.client.get("/api/weight-insights/")
        self.assertIsNone(r.data["bmi"])

    def test_settings_upsert(self):
        self.client.post("/api/settings/", {"key": "height_cm", "value": "180"}, format="json")
        self.client.post("/api/settings/", {"key": "height_cm", "value": "181"}, format="json")
        self.assertEqual(Setting.objects.filter(key="height_cm").count(), 1)
        self.assertEqual(Setting.objects.get(key="height_cm").value, "181")


class MeasurementSeriesTests(ApiTestBase):
    def test_series_is_chronological(self):
        for d, v in [("2026-10-20", 100), ("2026-10-18", 98), ("2026-10-21", 101)]:
            BodyMeasurement.objects.create(date=dt.date.fromisoformat(d), waist_cm=v)
        r = self.client.get("/api/body-measurements/")
        series = r.data["series"]["waist_cm"]
        dates = [p["date"] for p in series]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(series[-1]["value"], 101.0)


class JournalTests(ApiTestBase):
    def test_feed_merges_and_sorts_desc(self):
        HabitLog.objects.create(habit=Habit.objects.create(name="Wake"),
                                date=dt.date(2026, 10, 20), status="done", done=True)
        WeightLog.objects.create(date=dt.date(2026, 10, 21), weight_kg=80)
        DrinkLog.objects.create(date=dt.date(2026, 10, 21), drink_type="water", volume_ml=250)
        r = self.client.get("/api/journal/?from=2026-10-18&to=2026-10-21")
        dates = [e["date"] for e in r.data["events"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        kinds = {e["kind"] for e in r.data["events"]}
        self.assertTrue({"habit", "weight", "drinks"}.issubset(kinds))

    def test_types_filter(self):
        WeightLog.objects.create(date=dt.date(2026, 10, 21), weight_kg=80)
        DrinkLog.objects.create(date=dt.date(2026, 10, 21), drink_type="water", volume_ml=250)
        r = self.client.get("/api/journal/?from=2026-10-18&to=2026-10-21&types=weight")
        self.assertEqual({e["kind"] for e in r.data["events"]}, {"weight"})
