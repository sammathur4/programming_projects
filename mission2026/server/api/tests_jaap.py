"""Tests for the jaap (mantra counter) feature.

The counter is the one place where the app writes on *every* tap, so these
tests lean hard on the hot path: increments must be exact, mala completion
must be detected on the right tap, and a replayed tap must never double count.
"""
import datetime as dt

from django.test import TestCase
from rest_framework.test import APIClient

from .models import JaapLog, JaapMantra


class JaapTestBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.mantra = JaapMantra.objects.create(
            name="Ram Naam",
            emoji="🙏",
            devanagari="राम राम",
            mala_size=108,
            daily_goal=108,
        )
        self.small = JaapMantra.objects.create(
            name="Short",
            emoji="🕉",
            mala_size=10,
            daily_goal=10,
        )
        self.d = dt.date(2026, 10, 21)

    def _tap(self, mantra=None, date=None, delta=None):
        body = {"mantra": (mantra or self.mantra).id, "date": (date or self.d).isoformat()}
        if delta is not None:
            body["delta"] = delta
        return self.client.post("/api/jaap/tap/", body, format="json")


class JaapTapTests(JaapTestBase):
    def test_tap_increments_and_returns_the_new_count(self):
        r = self._tap()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["malas"], 0)
        self.assertFalse(r.data["mala_completed"])

    def test_each_tap_is_its_own_write(self):
        for expected in range(1, 6):
            r = self._tap()
            self.assertEqual(r.data["count"], expected)

    def test_mala_completes_exactly_on_the_bead(self):
        for n in range(1, 108):
            r = self._tap()
            self.assertEqual(r.data["count"], n)
            self.assertFalse(r.data["mala_completed"], "must not ring early")
        r = self._tap()
        self.assertEqual(r.data["count"], 108)
        self.assertEqual(r.data["malas"], 1)
        self.assertTrue(r.data["mala_completed"], "the bell rings on the 108th tap")
        # one past the mala — no second bell
        r = self._tap()
        self.assertEqual(r.data["count"], 109)
        self.assertFalse(r.data["mala_completed"])

    def test_mala_size_is_the_users_choice(self):
        # a 10-bead mala rings on the 10th tap, not the 108th
        for _ in range(9):
            r = self._tap(self.small)
            self.assertFalse(r.data["mala_completed"])
        r = self._tap(self.small)
        self.assertEqual(r.data["count"], 10)
        self.assertEqual(r.data["malas"], 1)
        self.assertTrue(r.data["mala_completed"])

    def test_undo(self):
        for _ in range(3):
            self._tap()
        r = self._tap(delta=-1)
        self.assertEqual(r.data["count"], 2)

    def test_count_never_goes_negative(self):
        r = self._tap(delta=-500)
        self.assertEqual(r.data["count"], 0)

    def test_zero_delta_is_treated_as_one(self):
        r = self._tap(delta=0)
        self.assertEqual(r.data["count"], 1)

    def test_unknown_mantra_is_404(self):
        r = self.client.post(
            "/api/jaap/tap/", {"mantra": 99999, "date": self.d.isoformat()}, format="json"
        )
        self.assertEqual(r.status_code, 404)

    def test_one_row_per_mantra_per_day(self):
        for _ in range(5):
            self._tap()
        self.assertEqual(JaapLog.objects.filter(mantra=self.mantra, date=self.d).count(), 1)

    def test_different_days_are_separate_rows(self):
        self._tap()
        self._tap(date=self.d - dt.timedelta(days=1))
        self.assertEqual(JaapLog.objects.count(), 2)


class JaapLibraryTests(JaapTestBase):
    def test_list_returns_active_mantras(self):
        r = self.client.get("/api/jaap-mantras/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_create_a_custom_mantra(self):
        r = self.client.post(
            "/api/jaap-mantras/",
            {"name": "Gayatri", "devanagari": "ॐ भूर्भुवः स्वः", "mala_size": 27},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["beads"], 27)
        self.assertTrue(JaapMantra.objects.filter(name="Gayatri").exists())

    def test_zero_mala_size_is_rejected(self):
        r = self.client.post(
            "/api/jaap-mantras/", {"name": "Bad", "mala_size": 0}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_beads_never_reports_zero(self):
        # a mantra saved with a zero size must still be countable
        m = JaapMantra.objects.create(name="Zero", mala_size=0)
        self.assertEqual(m.beads, 1)
        r = self._tap(mantra=m)
        self.assertEqual(r.data["count"], 1)

    def test_editing_the_bead_count_recals_the_malas(self):
        for _ in range(10):
            self._tap(self.small)
        self.assertEqual(JaapLog.objects.get(mantra=self.small).malas, 1)
        r = self.client.patch(
            f"/api/jaap-mantras/{self.small.id}/", {"mala_size": 5}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(JaapLog.objects.get(mantra=self.small).malas, 2)


class JaapStatsTests(JaapTestBase):
    def test_streak_counts_days_that_met_the_goal(self):
        # today plus two days back all hit the goal
        for d in (self.d, self.d - dt.timedelta(days=1), self.d - dt.timedelta(days=2)):
            for _ in range(108):
                self._tap(date=d)
        r = self.client.get(f"/api/jaap/stats/?date={self.d.isoformat()}")
        pm = r.data["per_mantra"][0]
        self.assertEqual(pm["streak"], 3)
        self.assertEqual(pm["total"], 324)
        self.assertEqual(pm["malas"], 3)

    def test_a_day_below_the_goal_does_not_extend_the_streak(self):
        for _ in range(108):
            self._tap(date=self.d - dt.timedelta(days=1))
        for _ in range(10):  # today: only 10 of 108
            self._tap()
        r = self.client.get(f"/api/jaap/stats/?date={self.d.isoformat()}")
        pm = r.data["per_mantra"][0]
        # today doesn't qualify, so the streak is the run up to yesterday —
        # the same rule the habit streak uses (today pending isn't a break)
        self.assertEqual(pm["streak"], 1)
        self.assertEqual(pm["today"], 10)

    def test_series_covers_the_window(self):
        self._tap()
        r = self.client.get(f"/api/jaap/stats/?days=7&date={self.d.isoformat()}")
        self.assertEqual(len(r.data["series"]), 7)
        self.assertEqual(r.data["series"][-1]["count"], 1)
        self.assertEqual(r.data["today_total"], 1)

    def test_day_summary(self):
        for _ in range(3):
            self._tap()
        r = self.client.get(f"/api/jaap/?date={self.d.isoformat()}")
        self.assertEqual(r.data["summary"]["total"], 3)
        self.assertEqual(len(r.data["mantras"]), 2)


class JaapJournalTests(JaapTestBase):
    def test_jaap_appears_in_the_timeline(self):
        for _ in range(108):
            self._tap()
        r = self.client.get(f"/api/journal/?from={self.d.isoformat()}&to={self.d.isoformat()}")
        kinds = [e["kind"] for e in r.data["events"]]
        self.assertIn("jaap", kinds)
        ev = next(e for e in r.data["events"] if e["kind"] == "jaap")
        self.assertIn("108", ev["subtitle"])
        self.assertIn("1 mala", ev["subtitle"])
        self.assertIn("Ram Naam", ev["title"])
