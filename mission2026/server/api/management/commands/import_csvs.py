"""
Import the Mission 2026 Google Sheet CSV exports into MySQL.

    python manage.py import_csvs [--dir /path/to/csvs]

Idempotent: habit/fitness/study rows are upserted by natural keys;
objectives & study resources are re-synced from the sheet (sheet = source of truth).
"""
import csv
import datetime as dt
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import FitnessDay, Habit, HabitLog, Objective, StudyDay, StudyResource, Setting, WeightLog

HABITBULL_CSV = "Mission 2026 - HabitBull.csv"
FITNESS_CSV = "Mission 2026 - Fitness.csv"
UPSC_CSV = "Mission 2026 - UPSC Tracker.csv"
OBJECTIVE_CSV = "Mission 2026 - Mission Objective.csv"
COMPLETED_CSV = "Mission 2026 - Completed Subjects.csv"
PENDING_CSV = "Mission 2026 - Pending Subjects.csv"
DAILY_CSV = "Mission 2026 - Daily Subjects.csv"

HABIT_STYLE = {
    "wake": ("⏰", "#f59e0b"),
    "hanuman": ("🙏", "#a855f7"),
    "upsc": ("📚", "#3b82f6"),
    "gym": ("🏋️", "#22c55e"),
    "diet": ("🥗", "#84cc16"),
    "bath": ("🧴", "#06b6d4"),
    "smoke": ("🚫", "#ef4444"),
    "water": ("💧", "#38bdf8"),
    "photo": ("📸", "#ec4899"),
    "sleep": ("😴", "#6366f1"),
}
FALLBACK_STYLE = ("✅", "#22c55e")

PRIORITY_RE = re.compile(r"^P\d$", re.I)
STATUS_VOCAB = {"completed", "pending", "in-progress", "in progress", "done", "skipped"}
PAPER_WORDS = ("gs", "prelims", "mains", "csat", "essay", "interview", "english", "aptitude")
TIME_RE = re.compile(r"^\d{1,3}:\d{2}(:\d{2})?$")


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.reader(fh))


def clean(rows):
    return [r for r in rows if any(c.strip() for c in r)]


def find_header(rows, first_cell):
    for i, r in enumerate(rows):
        if r and r[0].strip() == first_cell:
            return i
    return None


def parse_dd_mon(raw, prev):
    """'28-Sep' with no year — infer a monotonic year sequence."""
    try:
        tmp = dt.datetime.strptime(raw.strip(), "%d-%b")
    except ValueError:
        return None
    year = prev.year if prev else 2026
    try:
        cand = dt.date(year, tmp.month, tmp.day)
    except ValueError:  # 29-Feb on non-leap year
        return None
    if prev and cand < prev:
        year += 1
        try:
            cand = dt.date(year, tmp.month, tmp.day)
        except ValueError:
            return None
    return cand


def parse_full_date(raw):
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(raw.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def as_float(v):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v.replace("kg", "").replace("L", ""))
    except ValueError:
        return None


def as_int(v):
    v = (v or "").strip()
    return int(v) if v.isdigit() else None


class Command(BaseCommand):
    help = "Import Mission 2026 CSV exports into the database"

    def add_arguments(self, parser):
        base = os.path.join(settings.BASE_DIR, "data")
        parser.add_argument("--dir", default=base, help="Directory containing the CSV files")

    def handle(self, *args, **opts):
        d = opts["dir"]
        missing = [f for f in [HABITBULL_CSV, FITNESS_CSV, UPSC_CSV, OBJECTIVE_CSV] if not os.path.exists(os.path.join(d, f))]
        if missing:
            raise CommandError(f"Missing CSVs in {d}: {missing}")

        with transaction.atomic():
            self.import_habitbull(os.path.join(d, HABITBULL_CSV))
            self.import_fitness(os.path.join(d, FITNESS_CSV))
            self.import_upsc(os.path.join(d, UPSC_CSV))
            self.import_objectives(os.path.join(d, OBJECTIVE_CSV))
            if os.path.exists(os.path.join(d, COMPLETED_CSV)):
                self.import_resources(os.path.join(d, COMPLETED_CSV), StudyResource.TRACK_COMPLETED)
            if os.path.exists(os.path.join(d, PENDING_CSV)):
                self.import_resources(os.path.join(d, PENDING_CSV), StudyResource.TRACK_PENDING)
            if os.path.exists(os.path.join(d, DAILY_CSV)):
                self.import_resources(os.path.join(d, DAILY_CSV), StudyResource.TRACK_IN_PROGRESS)

        self.stdout.write(self.style.SUCCESS("Import complete ✓"))

    # ---------------------------------------------------------- settings
    def set(self, key, value):
        if value is None or str(value).strip() == "":
            return
        Setting.objects.update_or_create(key=key, defaults={"value": str(value).strip()})

    def _setting_date(self, key):
        s = Setting.objects.filter(key=key).first()
        if not s:
            return None
        return parse_full_date(str(s.value)) or self._date_from_timeline(str(s.value))

    def _date_from_timeline(self, text):
        """Best-effort date out of free text: 'May 2027', '31-May-2027', 'Dec 2026'."""
        if not text:
            return None
        text = text.strip()
        direct = parse_full_date(text)
        if direct:
            return direct
        m = re.search(r"([A-Za-z]{3,9})\s*[' ]?\s*(\d{4})", text)
        if m:
            for fmt in ("%B %Y", "%b %Y"):
                try:
                    return dt.datetime.strptime(f"{m.group(1)} {m.group(2)}", fmt).date()
                except ValueError:
                    continue
        m = re.search(r"(\d{4})", text)
        if m:
            return dt.date(int(m.group(1)), 12, 31)
        return None

    # ---------------------------------------------------------- 1. HabitBull
    def import_habitbull(self, path):
        rows = read_rows(path)
        habits = {}
        # meta rows
        for r in rows[:3]:
            if not r:
                continue
            label = r[0].strip().lower()
            if label == "start" and len(r) > 1:
                self.set("mission_start", r[1])
                self.set("mission_days_left", r[3] if len(r) > 3 else "")
            elif label == "today" and len(r) > 1:
                self.set("mission_sheet_today", r[1])
            elif label == "end" and len(r) > 1:
                self.set("mission_end", r[1])

        h_idx = find_header(rows, "Weeks")
        if h_idx is None:
            self.stderr.write("HabitBull header not found")
            return
        header = [h.replace("\n", " ").strip() for h in rows[h_idx]]
        habit_cols = {}  # col index -> (habit obj)
        for i, name in enumerate(header):
            if i < 3 or name in ("Daily Score", "Notes", ""):
                continue
            emoji, color = FALLBACK_STYLE
            low = name.lower()
            for key, style in HABIT_STYLE.items():
                if key in low:
                    emoji, color = style
                    break
            habit, _ = Habit.objects.update_or_create(
                name=name, defaults={"emoji": emoji, "color": color, "order": i - 3, "active": True}
            )
            habits[i] = habit

        prev = None
        imported = 0
        for r in rows[h_idx + 1:]:
            if len(r) < 4:
                continue
            raw_date = r[1].strip()
            if not raw_date:
                continue  # separator / blank rows
            day = parse_dd_mon(raw_date, prev)
            if not day:
                continue
            prev = day
            for col, habit in habits.items():
                if col >= len(r):
                    continue
                val = r[col].strip().upper()
                if val not in ("TRUE", "FALSE"):
                    continue  # blank = not logged yet
                HabitLog.objects.update_or_create(
                    habit=habit, date=day, defaults={"done": val == "TRUE"}
                )
                imported += 1
        self.stdout.write(f"  HabitBull: {len(habits)} habits, {imported} logs")

    # ---------------------------------------------------------- 2. Fitness
    def import_fitness(self, path):
        rows = read_rows(path)
        # config rows (before header)
        h_idx = find_header(rows, "Weeks")
        mode_plans = {}
        for r in rows[:h_idx]:
            if len(r) > 7 and r[6].strip() and r[7].strip():
                key = re.sub(r"[^a-z0-9]+", "_", r[6].strip().lower()).strip("_")
                self.set(f"fit_{key}", r[7])
            if len(r) > 9 and r[8].strip() and r[9].strip():
                key = re.sub(r"[^a-z0-9]+", "_", r[8].strip().lower()).strip("_")
                self.set(f"fit_{key}", r[9])
            if r[0].strip() in ("WFO", "WFH", "Holiday"):
                mode_plans[r[0].strip()] = " | ".join(c.strip() for c in r[1:6] if c.strip())
        for mode, plan in mode_plans.items():
            self.set(f"fit_plan_{mode}", plan)

        header = [h.strip() for h in rows[h_idx]]
        idx = {name: i for i, name in enumerate(header)}

        def get(row, name):
            i = idx.get(name)
            if i is None or i >= len(row):
                return ""
            return row[i].strip()

        imported = 0
        weights = 0
        last_weight = None
        for r in rows[h_idx + 1:]:
            if len(r) <= idx.get("Date", 1):
                continue
            day = parse_full_date(get(r, "Date"))
            if not day:
                continue  # weekly summary rows
            weight = as_float(get(r, "Weight (kg)"))
            FitnessDay.objects.update_or_create(
                date=day,
                defaults={
                    "location": get(r, "Location"),
                    "mode": get(r, "Mode"),
                    "muscles": get(r, "Muscles"),
                    "cardio": get(r, "Cardio"),
                    "weight_kg": weight,
                    "calories_in": as_int(get(r, "Calories In")),
                    "water_litres": as_float(get(r, "Water (Litre)")),
                    "status": get(r, "Status") or "Pending",
                    "notes": get(r, "Notes"),
                    "food": get(r, "Food"),
                },
            )
            # Mirror the day's weigh-in into WeightLog (the weight-history table
            # that drives the trend chart + logger). Daily rows repeat the same
            # value, so only write when it differs from the previous weigh-in.
            if weight is not None and weight != last_weight:
                WeightLog.objects.update_or_create(
                    date=day, defaults={"weight_kg": weight}
                )
                last_weight = weight
                weights += 1
            imported += 1
        self.stdout.write(f"  Fitness: {imported} days, {weights} weigh-ins")

    # ---------------------------------------------------------- 3. UPSC tracker
    def import_upsc(self, path):
        rows = read_rows(path)
        h_idx = find_header(rows, "Weeks")
        # mode targets config rows
        for r in rows[:h_idx]:
            mode = r[0].strip()
            if mode in ("WFO", "WFH", "Holiday"):
                parts = [c.strip() for c in r[1:4] if c.strip()]
                self.set(f"study_target_{mode}", " | ".join(parts))

        header = [h.strip() for h in rows[h_idx]]
        pairs = []
        for i, name in enumerate(header):
            if name.startswith("Subject") and i + 1 < len(header) and header[i + 1] == "Status":
                pairs.append((i, i + 1))

        imported = 0
        for r in rows[h_idx + 1:]:
            if len(r) < 5:
                continue
            day = parse_full_date(r[1].strip())
            if not day:
                continue
            slots = []
            for si, ti in pairs:
                if si < len(r):
                    subj = r[si].strip()
                    if not subj:
                        continue
                    status = r[ti].strip() if ti < len(r) else ""
                    slots.append({"subject": subj, "status": status or "Pending"})
            notes = r[len(header) - 1].strip() if len(r) >= len(header) else (r[-1].strip() if r else "")
            StudyDay.objects.update_or_create(
                date=day,
                defaults={
                    "location": r[3].strip() if len(r) > 3 else "",
                    "mode": r[4].strip() if len(r) > 4 else "",
                    "slots": slots,
                    "notes": notes,
                },
            )
            imported += 1
        self.stdout.write(f"  UPSC tracker: {imported} days")

    # ---------------------------------------------------------- 4. Objectives
    def import_objectives(self, path):
        rows = clean(read_rows(path))
        # imports are authoritative re-syncs from the sheet → hard delete
        Objective.all_objects.all().hard_delete()
        status = Objective.STATUS_ACTIVE
        order = 0
        current = None

        # campaign window — every goal without its own dates inherits it
        mission_start = self._setting_date("mission_start")
        mission_end = self._setting_date("mission_end")

        for r in rows[1:]:  # skip header
            r = (r + [""] * 7)[:7]
            area = r[1].strip()
            if area.lower() == "not pursuing anymore":
                status = Objective.STATUS_NOT_PURSUING
                current = None
                continue
            if area:
                timeline = r[3].strip()
                current = {
                    "area": area,
                    "objective": r[2].strip(),
                    "timeline": timeline,
                    "target": r[4].strip(),
                    "notes": "\n".join(x.strip() for x in [r[5], r[6]] if x.strip()),
                    "status": status,
                    "order": order,
                }
                objective = Objective.objects.create(**current)
                # dates: explicit timeline wins, else the mission campaign window
                objective.start_date = mission_start
                objective.target_date = self._date_from_timeline(timeline) or mission_end
                objective.save(update_fields=["start_date", "target_date"])
                order += 1
            else:
                # continuation line — append to previous objective's notes/target
                extra = "\n".join(x.strip() for x in r[2:] if x.strip())
                if extra and current:
                    obj = Objective.objects.get(order=current["order"], area=current["area"])
                    obj.notes = (obj.notes + "\n" + extra).strip()
                    obj.save(update_fields=["notes"])
        self.stdout.write(f"  Objectives: {order}")

    # ---------------------------------------------------------- 5. Subjects (resources)
    def import_resources(self, path, track):
        rows = clean(read_rows(path))
        StudyResource.all_objects.filter(track=track).hard_delete()
        header = [h.strip() for h in rows[0]]
        positional = header[:8] == ["Months", "Exam", "Paper", "Priority", "Status", "Subject", "Playlist Name", "Playlist Url"]

        order = 0
        for r in rows[1:]:
            row = [c.strip() for c in r]
            if positional:
                rec = self._parse_resource_positional(row, track, order)
            else:
                rec = self._parse_resource_heuristic(row, track, order)
            if rec:
                StudyResource.objects.create(**rec)
                order += 1
        self.stdout.write(f"  {track} subjects: {order}")

    def _parse_resource_positional(self, r, track, order):
        r = r + [""] * (17 - len(r)) if len(r) < 17 else r
        months, exam, paper, priority, status = r[0], r[1], r[2], r[3], r[4]
        subject, playlist, url = r[5], r[6], r[7]
        if not any([subject, playlist, status]):
            return None
        if not subject and not playlist:
            return None
        videos = next((as_int(v) for v in r[10:14] if v and v.isdigit()), None)
        duration = next((v for v in r[11:16] if TIME_RE.match(v)), "")
        return dict(
            track=track, months=months, exam=exam, paper=paper, priority=priority,
            status=status or "Pending", subject=subject, playlist_name=playlist,
            playlist_url=url if url.lower() != "telegram" or url else "",
            videos=videos, duration_hms=duration,
            start_date=r[8], end_date=r[9], notes=r[16] if len(r) > 16 else "",
            order=order,
        )

    def _parse_resource_heuristic(self, r, track, order):
        """Completed Subjects sheet has ragged columns — classify fields by vocabulary."""
        if len(r) < 5:
            return None
        months, exam = r[0], r[1]
        if not exam and months:
            return None  # section marker row like 'UPSC', 'GATE'
        priority = status = paper = subject = playlist = url = ""
        videos = None
        duration = ""
        notes = r[-1] if len(r) > 14 else ""

        for v in r[2:]:
            v = v.strip()
            if not v:
                continue
            if not priority and PRIORITY_RE.match(v):
                priority = v
            elif not status and v.lower() in STATUS_VOCAB:
                status = v
            elif not paper and any(w in v.lower() for w in PAPER_WORDS) and "http" not in v.lower():
                paper = v
            elif not subject and "http" not in v.lower() and not TIME_RE.match(v):
                subject = v
            elif not playlist and "http" not in v.lower() and not TIME_RE.match(v) and not v.isdigit():
                playlist = v
            elif not url and ("http" in v.lower() or v.lower() == "telegram" or "youtube" in v.lower()):
                url = v
            elif not videos and v.isdigit():
                videos = int(v)
            elif not duration and TIME_RE.match(v):
                duration = v
        if not subject and not playlist:
            return None
        return dict(
            track=track, months=months, exam=exam, paper=paper, priority=priority,
            status=status or "Pending", subject=subject, playlist_name=playlist,
            playlist_url=url, videos=videos, duration_hms=duration,
            start_date="", end_date="", notes=notes if notes != subject else "",
            order=order,
        )
