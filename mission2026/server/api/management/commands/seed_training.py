"""Seed the Legend-style training data.

Creates:
  * an exercise library (with muscle groups, equipment, form cues)
  * a few weeks of realistic workout history so progressive overload,
    personal bests, strength levels and the muscle-fatigue map all have
    something real to show
  * the four training modules wired to that library

Idempotent: re-running will not duplicate. Pass --reset to wipe first.

    manage.py seed_training
    manage.py seed_training --reset
"""
import datetime as dt
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import Exercise, FitnessDay, WorkoutExercise, WorkoutModule, WorkoutSet

# ---------------------------------------------------------------------------
# The exercise library. (name, primary muscle, secondary, equipment, compound)
# ---------------------------------------------------------------------------
LIBRARY = [
    # Chest
    ("Bench Press", "Chest", ["Triceps", "Shoulders"], "barbell", True),
    ("Incline Bench Press", "Chest", ["Shoulders", "Triceps"], "barbell", True),
    ("Incline Dumbbell Press", "Chest", ["Shoulders", "Triceps"], "dumbbell", True),
    ("Cable Fly", "Chest", ["Shoulders"], "cable", False),
    ("Dumbbell Fly", "Chest", [], "dumbbell", False),
    ("Push Up", "Chest", ["Triceps", "Shoulders"], "bodyweight", True),
    ("Dips", "Chest", ["Triceps"], "bodyweight", True),
    # Back
    ("Deadlift", "Back", ["Hamstrings", "Glutes", "Traps"], "barbell", True),
    ("Barbell Row", "Back", ["Biceps", "Lats"], "barbell", True),
    ("Pull Up", "Back", ["Biceps"], "bodyweight", True),
    ("Lat Pulldown", "Back", ["Biceps"], "cable", True),
    ("Seated Cable Row", "Back", ["Biceps"], "cable", True),
    ("Dumbbell Row", "Back", ["Biceps"], "dumbbell", True),
    ("Face Pull", "Back", ["Shoulders"], "cable", False),
    # Shoulders
    ("Overhead Press", "Shoulders", ["Triceps"], "barbell", True),
    ("Dumbbell Shoulder Press", "Shoulders", ["Triceps"], "dumbbell", True),
    ("Lateral Raise", "Shoulders", [], "dumbbell", False),
    ("Rear Delt Fly", "Shoulders", ["Back"], "dumbbell", False),
    ("Arnold Press", "Shoulders", ["Triceps"], "dumbbell", True),
    # Legs
    ("Squat", "Quads", ["Glutes", "Hamstrings"], "barbell", True),
    ("Front Squat", "Quads", ["Glutes"], "barbell", True),
    ("Leg Press", "Quads", ["Glutes"], "machine", True),
    ("Bulgarian Split Squat", "Quads", ["Glutes"], "dumbbell", True),
    ("Leg Extension", "Quads", [], "machine", False),
    ("Romanian Deadlift", "Hamstrings", ["Glutes", "Back"], "barbell", True),
    ("Leg Curl", "Hamstrings", [], "machine", False),
    ("Hip Thrust", "Glutes", ["Hamstrings"], "barbell", True),
    ("Standing Calf Raise", "Calves", [], "machine", False),
    ("Seated Calf Raise", "Calves", [], "machine", False),
    # Arms
    ("Barbell Curl", "Biceps", ["Forearms"], "barbell", False),
    ("Dumbbell Curl", "Biceps", [], "dumbbell", False),
    ("Hammer Curl", "Biceps", ["Forearms"], "dumbbell", False),
    ("Preacher Curl", "Biceps", [], "machine", False),
    ("Triceps Pushdown", "Triceps", [], "cable", False),
    ("Overhead Triceps Extension", "Triceps", [], "cable", False),
    ("Skull Crusher", "Triceps", [], "barbell", False),
    ("Close Grip Bench Press", "Triceps", ["Chest"], "barbell", True),
    # Core
    ("Plank", "Core", [], "bodyweight", False),
    ("Hanging Leg Raise", "Core", [], "bodyweight", False),
    ("Cable Crunch", "Core", [], "cable", False),
    ("Ab Wheel", "Core", [], "other", False),
]

CARDIO = [
    ("Treadmill Run", "Cardio", [], "machine", False),
    ("Cycling", "Cardio", [], "machine", False),
    ("Stair Master", "Cardio", [], "machine", False),
    ("Rowing Machine", "Cardio", [], "machine", False),
    ("Jump Rope", "Cardio", [], "other", False),
]

CUES = {
    "Bench Press": "Shoulder blades tucked, bar to lower chest, elbows ~45°.",
    "Squat": "Brace hard, sit between the hips, knees track over toes.",
    "Deadlift": "Bar over mid-foot, take the slack out, push the floor away.",
    "Overhead Press": "Squeeze glutes, head through at the top, no leaning back.",
    "Pull Up": "Full hang, drive elbows to the ribs, chin over bar.",
    "Barbell Row": "Flat back, pull to the belly button, control the negative.",
    "Romanian Deadlift": "Hinge at the hips, soft knees, bar close to the legs.",
    "Lateral Raise": "Lead with the elbows, stop at shoulder height, no swinging.",
    "Lat Pulldown": "Chest proud, pull to the collarbone, hold the squeeze.",
    "Leg Press": "Feet shoulder width, don't lock the knees, full depth.",
    "Plank": "Ribs down, glutes tight, straight line from head to heels.",
    "Push Up": "Body of one piece, elbows back at 45°, chest to floor.",
    "Face Pull": "Pull to the forehead, elbows high, thumbs back.",
}

# ---------------------------------------------------------------------------
# The training week: which module runs on which weekday.
# (module name, weekday 0=Mon, exercises as (library name, sets, reps, start kg, step))
# ---------------------------------------------------------------------------
PLAN = {
    "Push": (
        "#ef4444",
        "🔥",
        [0, 3],
        [
            ("Bench Press", 4, "6-8", 60.0, 2.5),
            ("Incline Dumbbell Press", 3, "8-10", 22.0, 1.0),
            ("Overhead Press", 3, "8-10", 35.0, 1.25),
            ("Lateral Raise", 3, "12-15", 8.0, 0.5),
            ("Triceps Pushdown", 3, "10-12", 25.0, 1.25),
        ],
    ),
    "Pull": (
        "#3b82f6",
        "🪢",
        [1, 4],
        [
            ("Deadlift", 4, "5", 100.0, 5.0),
            ("Barbell Row", 3, "8-10", 50.0, 2.5),
            ("Lat Pulldown", 3, "10-12", 55.0, 2.5),
            ("Face Pull", 3, "15", 20.0, 1.25),
            ("Barbell Curl", 3, "10-12", 25.0, 1.25),
        ],
    ),
    "Legs": (
        "#22c55e",
        "🦵",
        [2, 5],
        [
            ("Squat", 4, "6-8", 80.0, 2.5),
            ("Romanian Deadlift", 3, "8-10", 60.0, 2.5),
            ("Leg Press", 3, "10-12", 120.0, 5.0),
            ("Leg Curl", 3, "12", 40.0, 2.5),
            ("Standing Calf Raise", 4, "12-15", 50.0, 2.5),
        ],
    ),
    "Cardio": (
        "#f59e0b",
        "🏃",
        [6],
        [
            ("Treadmill Run", 1, "-", 0.0, 0.0),
            ("Rowing Machine", 1, "-", 0.0, 0.0),
        ],
    ),
}

MODULE_HR = 65  # a session runs about an hour


class Command(BaseCommand):
    help = "Seed the exercise library and Legend-style workout history."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="wipe training data first")
        parser.add_argument("--weeks", type=int, default=6, help="weeks of history (default 6)")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            WorkoutSet.all_objects.all().hard_delete()
            WorkoutExercise.all_objects.all().hard_delete()
            Exercise.all_objects.all().hard_delete()
            self.stdout.write("wiped training data")

        rng = random.Random(2026)  # deterministic — same history every run

        # --- library ---------------------------------------------------
        made = 0
        for name, muscle, secondary, equipment, compound in LIBRARY + CARDIO:
            is_cardio = muscle == "Cardio"
            obj, created = Exercise.objects.get_or_create(
                name=name,
                defaults=dict(
                    muscle=muscle,
                    secondary=secondary,
                    equipment=equipment,
                    is_compound=compound if not is_cardio else False,
                    is_cardio=is_cardio,
                    instructions=CUES.get(name, ""),
                ),
            )
            made += created
        exercises = {e.name: e for e in Exercise.objects.all()}
        self.stdout.write(f"library: {len(exercises)} exercises ({made} new)")

        # --- modules ---------------------------------------------------
        for order, (mod_name, (color, emoji, weekdays, rows)) in enumerate(PLAN.items()):
            days = [["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d] for d in weekdays]
            ex_json = []
            for name, sets, reps, weight, _step in rows:
                e = exercises[name]
                ex_json.append({
                    "name": name,
                    "sets": sets,
                    "reps": reps,
                    "weight_kg": weight,
                    "muscle": e.muscle,
                    "cardio": e.is_cardio,
                })
            WorkoutModule.objects.update_or_create(
                name=mod_name,
                defaults=dict(color=color, emoji=emoji, days=days,
                              exercises=ex_json, order=order),
            )
        self.stdout.write(f"modules: {WorkoutModule.objects.count()}")

        # --- history ---------------------------------------------------
        # Walk backwards from the most recent completed weekday so the latest
        # session is always "today or a day or two ago" — that is what the
        # active-workout screen compares against.
        today = dt.date.today()
        weeks = opts["weeks"]
        # start on the Monday of the week (weeks-1) back
        start = today - dt.timedelta(days=today.weekday()) - dt.timedelta(weeks=weeks - 1)
        made_sessions = made_sets = 0

        for week in range(weeks):
            for mod_name, (_c, _e, weekdays, rows) in PLAN.items():
                for wd in weekdays:
                    date = start + dt.timedelta(weeks=week, days=wd)
                    if date > today:
                        continue
                    if WorkoutExercise.objects.filter(date=date).exists():
                        continue
                    # progressive overload: weight climbs each week
                    progression = week * 1.0  # one "step" per week on top
                    day_sets = 0
                    for order, (name, sets, reps, base, step) in enumerate(rows):
                        lib = exercises[name]
                        we = WorkoutExercise.objects.create(
                            date=date,
                            exercise=lib,
                            name=name,
                            muscle=lib.muscle,
                            order=order,
                            target_sets=sets,
                            target_reps=reps,
                            rest_seconds=180 if lib.is_compound else 60,
                        )
                        if lib.is_cardio:
                            # one cardio "set" logged by distance + time
                            dist = round(4.0 + week * 0.25, 2) if "Run" in name else round(2.0 + week * 0.1, 2)
                            dur = int(dist * (330 if "Run" in name else 150))
                            WorkoutSet.objects.create(
                                workout_exercise=we, order=0, set_type=WorkoutSet.TYPE_WORKING,
                                distance_km=dist, duration_sec=dur,
                                rpe=7.5 + rng.choice([0, 0.5]), completed=True,
                            )
                            day_sets += 1
                            continue
                        rep_range = [int(x) for x in reps.split("-")] if "-" in reps else [int(reps), int(reps)]
                        for s in range(sets):
                            # warm-up on the first two sets of a compound lift
                            is_warmup = lib.is_compound and s < 1
                            target_w = base + progression * step
                            if s == 0 and is_warmup:
                                w = round(target_w * 0.5 / 2.5) * 2.5
                            else:
                                w = target_w
                            reps_done = rng.randint(rep_range[0], rep_range[1])
                            rpe = 6.5 if is_warmup else min(10.0, 7.0 + s * 0.7 + rng.choice([-0.5, 0, 0.5]))
                            WorkoutSet.objects.create(
                                workout_exercise=we,
                                order=s,
                                weight_kg=round(w, 2),
                                reps=reps_done,
                                set_type=WorkoutSet.TYPE_WARMUP if is_warmup else WorkoutSet.TYPE_WORKING,
                                rpe=round(rpe, 1),
                                rir=max(0, 10 - int(round(rpe))),
                                rest_sec=180 if lib.is_compound else 60,
                                completed=True,
                            )
                            day_sets += 1
                    made_sessions += 1
                    made_sets += day_sets

                    # keep the day row consistent (it drives the rest of the UI)
                    day, _ = FitnessDay.objects.get_or_create(date=date)
                    day.mode = day.mode or "WFO"
                    day.status = "Done"
                    day.duration_min = MODULE_HR
                    if not day.notes:
                        day.notes = f"{mod_name} day"
                    day.save()

        self.stdout.write(
            f"history: {made_sessions} sessions, {made_sets} sets "
            f"({start.isoformat()} → {today.isoformat()})"
        )
        self.stdout.write(self.style.SUCCESS("training seed complete"))
