"""Mission 2026 — data models mapping the Google Sheet tabs."""
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """Default manager hides soft-deleted rows; use .all_objects for everything."""

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        """Soft delete."""
        return self.update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class AllObjectsManager(models.Manager):
    """Same queryset API (incl. hard_delete/alive/dead) but no deleted filter."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class BaseModel(models.Model):
    """Common base: soft delete + timestamps.

    Timestamps are nullable so this base can be retro-fitted onto tables that
    already hold imported rows (no default needed during migration).
    """

    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])


class Habit(BaseModel):
    """One row of the HabitBull tab (10 daily habits)."""

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"

    name = models.CharField(max_length=64, unique=True)
    emoji = models.CharField(max_length=8, default="✅")
    color = models.CharField(max_length=16, default="#22c55e")
    order = models.PositiveSmallIntegerField(default=0)
    active = models.BooleanField(default=True)
    status = models.CharField(max_length=16, default=STATUS_ACTIVE)  # active / paused
    paused_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    # Optional measurable target, e.g. "5" litres or "20" pages
    target_value = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    target_unit = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.emoji} {self.name}"

    @property
    def is_paused(self):
        return self.status == self.STATUS_PAUSED

    def pause(self):
        self.status = self.STATUS_PAUSED
        self.paused_at = timezone.now()
        self.save(update_fields=["status", "paused_at", "updated_at"])

    def resume(self):
        self.status = self.STATUS_ACTIVE
        self.paused_at = None
        self.save(update_fields=["status", "paused_at", "updated_at"])


class HabitLog(BaseModel):
    """A habit's status for a date, plus optional per-day note & value.

    `status` is the source of truth: pending / done / skipped.
    "" (blank) means the day was never touched — cycling from it goes to done.
    `done` is kept as a legacy mirror (status == done) for old queries.
    """

    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_DONE = "done"
    STATUS_SKIPPED = "skipped"
    STATUSES = [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_DONE, STATUS_SKIPPED]

    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField()
    # pending / in_progress / done / skipped. Wide enough for "in_progress".
    status = models.CharField(max_length=16, blank=True, default="")
    done = models.BooleanField(default=False)  # legacy mirror of status == done
    value = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    note = models.TextField(blank=True, default="")

    def set_status(self, status):
        self.status = status
        self.done = status == self.STATUS_DONE

    class Meta:
        unique_together = [("habit", "date")]
        indexes = [models.Index(fields=["date"])]
        ordering = ["-date"]


class FitnessDay(BaseModel):
    """One row of the Fitness tab."""

    date = models.DateField(unique=True)
    location = models.CharField(max_length=32, blank=True, default="")
    mode = models.CharField(max_length=16, blank=True, default="")  # WFO / WFH / Holiday
    muscles = models.CharField(max_length=128, blank=True, default="")
    cardio = models.CharField(max_length=128, blank=True, default="")
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    calories_in = models.PositiveIntegerField(null=True, blank=True)
    water_litres = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=16, default="Pending")  # Skipped / Pending / Done
    notes = models.TextField(blank=True, default="")
    food = models.CharField(max_length=255, blank=True, default="")
    # Structured workout: [{"name","sets","reps","weight_kg","muscle"}, ...]
    exercises = models.JSONField(default=list, blank=True)
    # Structured cardio: [{"type","quantity","unit","minutes"}, ...]
    cardio_items = models.JSONField(default=list, blank=True)
    duration_min = models.PositiveSmallIntegerField(null=True, blank=True)
    steps = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["date"])]


class StudyDay(BaseModel):
    """One row of the UPSC Tracker tab + AW/MCQ/hours progress."""

    date = models.DateField(unique=True)
    location = models.CharField(max_length=32, blank=True, default="")
    mode = models.CharField(max_length=16, blank=True, default="")
    # [{"subject": "History", "status": "Done"} ...] — up to 4 slots, order kept
    slots = models.JSONField(default=list, blank=True)
    aw_count = models.PositiveSmallIntegerField(default=0)     # answer writings done
    mcq_count = models.PositiveSmallIntegerField(default=0)    # MCQs done
    study_hours = models.DecimalField(max_digits=4, decimal_places=1, default=0)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["date"])]


class Objective(BaseModel):
    """A row of the Mission Objective tab (big life goals)."""

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_DONE = "done"
    STATUS_NOT_PURSUING = "not_pursuing"

    area = models.CharField(max_length=64, blank=True, default="")
    objective = models.TextField(blank=True, default="")
    timeline = models.CharField(max_length=64, blank=True, default="")
    target = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    status = models.CharField(max_length=24, default=STATUS_ACTIVE)
    order = models.PositiveSmallIntegerField(default=0)

    # Progress tracking
    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    paused_days = models.PositiveIntegerField(default=0)
    progress_pct = models.PositiveSmallIntegerField(default=0)  # manual override / baseline
    # Which habits drive this goal: ["upsc", "wake_4_am"] (slug keys)
    linked_habits = models.JSONField(default=list, blank=True)
    color = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.area} — {self.objective[:40]}"


class GoalCheckpoint(BaseModel):
    """A dated progress entry / milestone on a goal (weekly review fodder)."""

    objective = models.ForeignKey(Objective, on_delete=models.CASCADE, related_name="checkpoints")
    date = models.DateField()
    progress_pct = models.PositiveSmallIntegerField(default=0)
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-date"]


class StudyResource(BaseModel):
    """Rows of Completed / Pending Subjects tabs (playlist-based study items)."""

    TRACK_COMPLETED = "completed"
    TRACK_PENDING = "pending"
    TRACK_IN_PROGRESS = "in_progress"

    track = models.CharField(max_length=16, default=TRACK_PENDING)
    months = models.CharField(max_length=64, blank=True, default="")
    exam = models.CharField(max_length=32, blank=True, default="")
    paper = models.CharField(max_length=128, blank=True, default="")
    priority = models.CharField(max_length=8, blank=True, default="")
    status = models.CharField(max_length=16, default="Pending")  # Completed / Pending / In-Progress
    subject = models.CharField(max_length=64, blank=True, default="")
    playlist_name = models.TextField(blank=True, default="")
    playlist_url = models.TextField(blank=True, default="")
    videos = models.IntegerField(null=True, blank=True)
    duration_hms = models.CharField(max_length=32, blank=True, default="")  # "46:30:45"
    start_date = models.CharField(max_length=32, blank=True, default="")
    end_date = models.CharField(max_length=32, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)
    # progress of a playlist the user is working through
    videos_done = models.IntegerField(default=0)
    moved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]


class StudyActivity(BaseModel):
    """Detailed study activity log for MCQ, answer writing, revision, etc."""

    ACTIVITY_STUDY = "study_session"
    ACTIVITY_MCQ = "mcq"
    ACTIVITY_ANSWER = "answer_writing"
    ACTIVITY_REVISION = "revision"
    ACTIVITY_MOCK = "mock_test"

    date = models.DateField()
    activity_type = models.CharField(max_length=32, default=ACTIVITY_STUDY)
    subject = models.CharField(max_length=64, blank=True, default="")
    resource = models.ForeignKey(StudyResource, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    time_spent_minutes = models.PositiveIntegerField(null=True, blank=True)
    questions_attempted = models.PositiveIntegerField(null=True, blank=True)
    questions_completed = models.PositiveIntegerField(null=True, blank=True)
    correct_answers = models.PositiveIntegerField(null=True, blank=True)
    incorrect_answers = models.PositiveIntegerField(null=True, blank=True)
    answers_written = models.PositiveIntegerField(null=True, blank=True)
    word_count = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["date"])]


class WeightLog(BaseModel):
    """Body weight measurements over time."""

    date = models.DateField()
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2)
    time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [models.Index(fields=["date"])]


class Setting(models.Model):
    """Key/value config imported from sheet header cells (targets, dates...)."""

    key = models.CharField(max_length=64, unique=True)
    value = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.key} = {self.value}"


class CheckinMember(models.Model):
    """A person reporting through the WhatsApp group (no app install needed)."""

    external_id = models.CharField(max_length=64, unique=True)  # phone number
    name = models.CharField(max_length=64, blank=True, default="")
    # WhatsApp addressing id for @-mentions, e.g. "274925319360578@lid" or
    # "919876543210@c.us". external_id is the bare form; this keeps the suffix.
    whatsapp_id = models.CharField(max_length=64, blank=True, default="")
    habit = models.ForeignKey(
        Habit, null=True, blank=True, on_delete=models.SET_NULL, related_name="checkin_members"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "external_id"]

    def __str__(self):
        return self.name or self.external_id


class DailyCheckin(BaseModel):
    """One member's answers for one day, from WhatsApp polls or the app."""

    SOURCE_WHATSAPP = "whatsapp"
    SOURCE_APP = "app"

    member = models.ForeignKey(CheckinMember, on_delete=models.CASCADE, related_name="checkins")
    date = models.DateField()
    source = models.CharField(max_length=16, default=SOURCE_WHATSAPP)
    # habit slugs, e.g. ["wake_4_am", "upsc"]
    done = models.JSONField(default=list, blank=True)
    missed = models.JSONField(default=list, blank=True)
    # started but not finished — a third bucket, counted separately so it
    # never inflates the done/missed ratio that `score` is built from.
    in_progress = models.JSONField(default=list, blank=True)
    # explicitly "not started". Carried explicitly so it can CLEAR a habit the
    # member had already marked done/missed — an absent key would leave the
    # old status in place.
    pending = models.JSONField(default=list, blank=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        unique_together = [("member", "date")]
        ordering = ["-date"]
        indexes = [models.Index(fields=["date"])]

    @property
    def score(self):
        total = len(self.done) + len(self.missed)
        return round(len(self.done) / total * 100) if total else 0


# =====================================================================
# Food — MyFitnessPal-style dish database + daily diary
# =====================================================================
class Food(BaseModel):
    """A dish with per-serving nutrition. The searchable food database."""

    name = models.CharField(max_length=128, unique=True)
    serving = models.CharField(max_length=64, blank=True, default="")  # "1 medium (40g)"
    kcal = models.PositiveIntegerField(default=0)
    protein_g = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    carbs_g = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    fat_g = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    category = models.CharField(max_length=32, blank=True, default="")  # Indian / Western / ...
    is_custom = models.BooleanField(default=False)  # user-added vs seeded

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["name"])]

    def __str__(self):
        return f"{self.name} ({self.kcal} kcal)"


class DiaryEntry(BaseModel):
    """One logged food item on a date, in a meal slot.

    Macros are SNAPSHOTTED at log time: editing a dish later must not rewrite
    history, so these fields are copied from Food when the row is created.
    """

    MEALS = ["Breakfast", "Lunch", "Dinner", "Snack"]

    date = models.DateField()
    meal = models.CharField(max_length=16, default="Breakfast")  # one of MEALS
    food = models.ForeignKey(
        Food, null=True, blank=True, on_delete=models.SET_NULL, related_name="diary_entries"
    )
    food_name = models.CharField(max_length=128, blank=True, default="")  # keeps name if dish deleted
    quantity = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    # snapshot of nutrition for `quantity` servings
    kcal = models.PositiveIntegerField(default=0)
    protein_g = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    fat_g = models.DecimalField(max_digits=6, decimal_places=1, default=0)

    class Meta:
        ordering = ["date", "meal", "id"]
        indexes = [models.Index(fields=["date"])]

    def __str__(self):
        return f"{self.date} {self.meal}: {self.food_name} x{self.quantity}"


class NutritionTarget(models.Model):
    """Daily calorie + macro + water goals. Single row (pk=1) — mirrors Settings."""

    calorie_goal = models.PositiveIntegerField(default=2100)
    protein_goal = models.PositiveIntegerField(default=140)
    carbs_goal = models.PositiveIntegerField(default=210)
    fat_goal = models.PositiveIntegerField(default=60)
    water_goal_ml = models.PositiveIntegerField(default=3000)

    def __str__(self):
        return f"{self.calorie_goal} kcal / {self.protein_goal}P {self.carbs_goal}C {self.fat_goal}F"


# =====================================================================
# Notes — one feed for every note in the system
# =====================================================================
class Note(BaseModel):
    """A free note, tagged by where it came from.

    Deliberately standalone rather than a view over every note field in the
    schema: habit notes and fitness notes stay with their own rows, and this
    table holds the notes that are *not* owned by a single record (day notes,
    ideas, and roll-ups). `ref` says what it is about.
    """

    TAG_DAY = "day"
    TAG_HABIT = "habit"
    TAG_FITNESS = "fitness"
    TAG_FOOD = "food"
    TAG_GOAL = "goal"
    TAG_IDEA = "idea"
    TAGS = [TAG_DAY, TAG_HABIT, TAG_FITNESS, TAG_FOOD, TAG_GOAL, TAG_IDEA]

    date = models.DateField()
    tag = models.CharField(max_length=16, default=TAG_DAY)
    ref = models.CharField(max_length=128, blank=True, default="")  # "Diet", "Push · Bench Press"
    text = models.TextField(blank=True, default="")
    pinned = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date", "-pinned", "-id"]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["tag"])]

    def __str__(self):
        return f"{self.date} [{self.tag}] {self.text[:40]}"


# =====================================================================
# Workout modules — Legend-style named training days
# =====================================================================
class WorkoutModule(BaseModel):
    """A named training day: Push / Pull / Legs / Cardio.

    `exercises` is a list of dicts:
        {"name","sets","reps","weight_kg","muscle"}  — strength
        {"name","cardio":true,"quantity","unit","minutes","muscle":"Cardio"}
    """

    name = models.CharField(max_length=48, unique=True)
    color = models.CharField(max_length=16, blank=True, default="#3b82f6")
    emoji = models.CharField(max_length=8, blank=True, default="💪")
    # which weekdays this module runs, e.g. ["Mon","Thu"]
    days = models.JSONField(default=list, blank=True)
    exercises = models.JSONField(default=list, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return f"{self.name} ({', '.join(self.days)})"

    @property
    def muscles(self):
        """Muscle -> total working sets. Derived, never stored.

        Computed from `exercises` so the muscle map can never disagree with
        the workout it describes.
        """
        totals = {}
        for ex in self.exercises or []:
            muscle = (ex.get("muscle") or "").strip()
            if not muscle:
                continue
            sets = 0 if ex.get("cardio") else int(ex.get("sets") or 0)
            totals[muscle] = totals.get(muscle, 0) + sets
        return dict(sorted(totals.items(), key=lambda kv: -kv[1]))

# =====================================================================
# Legend-style training — the exercise library, what you did on a day,
# and every individual set. Day-based: one FitnessDay == one workout.
# =====================================================================
class Exercise(BaseModel):
    """An entry in the exercise library (Legend has 1600+; we seed what we use).

    Bodyweight/machine exercises carry no plate math; barbell ones do.
    """

    EQUIPMENT = ["barbell", "dumbbell", "machine", "cable", "bodyweight", "other"]

    name = models.CharField(max_length=96, unique=True)
    muscle = models.CharField(max_length=32, blank=True, default="")      # primary muscle
    secondary = models.JSONField(default=list, blank=True)                # ["Triceps", ...]
    equipment = models.CharField(max_length=16, default="barbell")
    is_compound = models.BooleanField(default=False)
    # cue shown while training ("elbows tucked, bar to sternum")
    instructions = models.TextField(blank=True, default="")
    # log the set by distance/time instead of weight x reps (treadmill, plank)
    is_cardio = models.BooleanField(default=False)
    is_custom = models.BooleanField(default=False)

    class Meta:
        ordering = ["muscle", "name"]
        indexes = [models.Index(fields=["muscle"]), models.Index(fields=["name"])]

    def __str__(self):
        return self.name


class WorkoutExercise(BaseModel):
    """One exercise performed as part of a day's workout.

    This links the library exercise to *your* session on a date, so the same
    exercise can appear twice in a day (e.g. a heavy and a back-off block).
    """

    date = models.DateField()
    exercise = models.ForeignKey(
        Exercise, null=True, blank=True, on_delete=models.SET_NULL, related_name="performed"
    )
    # name kept even if the library row is deleted, so history stays readable
    name = models.CharField(max_length=96)
    muscle = models.CharField(max_length=32, blank=True, default="")
    order = models.PositiveSmallIntegerField(default=0)
    # supersets: exercises sharing the same group letter are performed back-to-back
    superset_group = models.CharField(max_length=2, blank=True, default="")
    # target used when the workout was planned (Legend shows "target 4x8")
    target_sets = models.PositiveSmallIntegerField(null=True, blank=True)
    target_reps = models.CharField(max_length=16, blank=True, default="")
    rest_seconds = models.PositiveSmallIntegerField(default=90)
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["date", "order", "id"]
        indexes = [models.Index(fields=["date"]), models.Index(fields=["name"])]

    def __str__(self):
        return f"{self.date} #{self.order} {self.name}"

    @property
    def summary(self):
        """Legend-style one-liner: the best working set, e.g. '70kg x 8'."""
        best, best_vol = None, 0
        for s in self.sets.all():
            if not s.completed or s.set_type == WorkoutSet.TYPE_WARMUP:
                continue
            vol = float(s.weight_kg or 0) * (s.reps or 0)
            if vol >= best_vol:
                best, best_vol = s, vol
        if best is None:
            return ""
        if self.exercise and self.exercise.is_cardio:
            return f"{best.distance_km or 0}km · {best.duration_sec or 0}s"
        return f"{_trim(best.weight_kg)}kg × {best.reps}"


class WorkoutSet(BaseModel):
    """A single set — the atom of the whole training system.

    Per-set detail is what makes progressive overload, RPE and personal bests
    possible; a summary "4 x 8" cannot express a warm-up, a drop set or how
    hard the last set actually felt.
    """

    TYPE_WORKING = "working"
    TYPE_WARMUP = "warmup"
    TYPE_DROP = "drop"
    TYPE_FAILURE = "failure"
    TYPE_AMRAP = "amrap"
    SET_TYPES = [TYPE_WORKING, TYPE_WARMUP, TYPE_DROP, TYPE_FAILURE, TYPE_AMRAP]
    # warm-ups are excluded from volume, personal bests and progress charts
    TYPES_EXCLUDED_FROM_STATS = [TYPE_WARMUP]

    # RPE 0-10; RIR is stored too and the two are kept consistent by the API.
    RPE_MIN, RPE_MAX = 0, 10

    workout_exercise = models.ForeignKey(
        WorkoutExercise, on_delete=models.CASCADE, related_name="sets"
    )
    order = models.PositiveSmallIntegerField(default=0)

    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    reps = models.PositiveSmallIntegerField(null=True, blank=True)
    # cardio / timed work
    duration_sec = models.PositiveIntegerField(null=True, blank=True)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    # effort
    set_type = models.CharField(max_length=12, default=TYPE_WORKING)
    rpe = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    rir = models.PositiveSmallIntegerField(null=True, blank=True)
    # rest actually taken after this set, filled by the break timer
    rest_sec = models.PositiveIntegerField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    note = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["workout_exercise", "order", "id"]
        indexes = [models.Index(fields=["workout_exercise"])]

    def __str__(self):
        return f"{self.workout_exercise.name} set {self.order + 1}"

    @property
    def volume_kg(self):
        """Weight moved by this set. Warm-ups never count toward volume."""
        if self.set_type in self.TYPES_EXCLUDED_FROM_STATS:
            return 0
        return round(float(self.weight_kg or 0) * (self.reps or 0))

    @property
    def est_1rm(self):
        """Epley estimate: w x (1 + reps/30). The basis for strength levels."""
        if not self.weight_kg or not self.reps:
            return None
        if self.reps >= 37:  # the formula breaks down at very high reps
            return None
        return round(float(self.weight_kg) * (1 + self.reps / 30), 1)

    def sync_rpe_rir(self):
        """Keep RPE and RIR consistent: RIR = 10 - RPE."""
        if self.rpe is not None:
            self.rir = max(0, 10 - int(round(float(self.rpe))))
        elif self.rir is not None:
            self.rpe = 10 - self.rir


def _trim(v):
    """2.00 -> '2', 72.50 -> '72.5' — weights read better without trailing zeros."""
    if v is None:
        return "0"
    f = float(v)
    return str(int(f)) if f == int(f) else str(f).rstrip("0").rstrip(".")


# =====================================================================
# Body measurements & daily intake — Legend's "measurements" block
# =====================================================================
class BodyMeasurement(BaseModel):
    """A dated set of body-part circumferences (cm) plus bodyweight.

    One row per date; only the fields the user filled are stored. Legend keeps
    a table of these so you can chart each site over time.
    """

    date = models.DateField(unique=True)
    bodyweight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    neck_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    chest_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    waist_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    hips_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    left_arm_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    right_arm_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    left_thigh_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    right_thigh_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    left_calf_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    right_calf_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    body_fat_pct = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["date"])]

    def __str__(self):
        return f"{self.date} measurements"


class IntakeLog(BaseModel):
    """Daily nutrition intake — water and protein (Legend's intake tracking).

    Grams/kcal are stored directly rather than derived, so a quick top-up
    doesn't need a food entry.
    """

    date = models.DateField(unique=True)
    water_ml = models.PositiveIntegerField(default=0)
    protein_g = models.PositiveIntegerField(default=0)
    calories = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["date"])]

    def __str__(self):
        return f"{self.date} {self.water_ml}ml {self.protein_g}g"


# Beverage presets: one tap logs a sensible serving. Caffeine/kcal are per
# serving so a day's totals are meaningful without a nutrition database.
DRINK_PRESETS = {
    "water": {"label": "Water", "emoji": "💧", "ml": 250, "caffeine_mg": 0, "calories": 0, "color": "#4F9BFF"},
    "coffee": {"label": "Coffee", "emoji": "☕", "ml": 150, "caffeine_mg": 95, "calories": 2, "color": "#B98A5A"},
    "tea": {"label": "Tea", "emoji": "🍵", "ml": 150, "caffeine_mg": 47, "calories": 2, "color": "#7AC77A"},
    "juice": {"label": "Juice", "emoji": "🧃", "ml": 200, "caffeine_mg": 0, "calories": 90, "color": "#F5A623"},
    "milk": {"label": "Milk", "emoji": "🥛", "ml": 200, "caffeine_mg": 0, "calories": 120, "color": "#E8E8F0"},
    "soda": {"label": "Soda", "emoji": "🥤", "ml": 330, "caffeine_mg": 34, "calories": 140, "color": "#EF6B6B"},
    "other": {"label": "Other", "emoji": "🍶", "ml": 250, "caffeine_mg": 0, "calories": 0, "color": "#B9A6FF"},
}


class DrinkLog(BaseModel):
    """A single logged drink — water, coffee, juice and friends.

    Unlike `IntakeLog` (one row per day), a drink is an event with a time, so
    the Timeline can show *when* you drank and totals can split by type.
    """

    date = models.DateField(db_index=True)
    drink_type = models.CharField(max_length=24, default="water")
    volume_ml = models.PositiveIntegerField(default=250)
    caffeine_mg = models.PositiveIntegerField(default=0)
    calories = models.PositiveIntegerField(default=0)
    time = models.TimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-date", "-time", "-id"]
        indexes = [models.Index(fields=["date"])]

    def __str__(self):
        return f"{self.date} {self.drink_type} {self.volume_ml}ml"

    def apply_preset(self):
        """Fill caffeine/kcal from the preset when the caller didn't specify."""
        preset = DRINK_PRESETS.get(self.drink_type)
        if not preset:
            return
        if self.caffeine_mg in (None, 0) and preset["caffeine_mg"]:
            self.caffeine_mg = preset["caffeine_mg"]
        if self.calories in (None, 0) and preset["calories"]:
            self.calories = preset["calories"]

    @property
    def is_hydrating(self):
        """Only water counts toward the hydration ring."""
        return self.drink_type == "water"


# =====================================================================
# Jaap — the mantra counter
# =====================================================================
class JaapMantra(BaseModel):
    """A chant you can count: a naam, a mantra or a chalisa.

    `mala_size` is the number of beads in one round (traditionally 108, but
    the user decides — 27, 54, 1008 and custom sizes are all normal). The
    counter's ring is drawn from this value, so changing it changes the bead
    count on screen.
    """

    CATEGORY_NAAM = "naam"
    CATEGORY_MANTRA = "mantra"
    CATEGORY_CHALISA = "chalisa"
    CATEGORIES = [CATEGORY_NAAM, CATEGORY_MANTRA, CATEGORY_CHALISA]

    name = models.CharField(max_length=64, unique=True)
    emoji = models.CharField(max_length=8, default="🙏", blank=True)
    devanagari = models.CharField(max_length=160, blank=True, default="")
    transliteration = models.CharField(max_length=160, blank=True, default="")
    category = models.CharField(max_length=16, default=CATEGORY_NAAM)
    deity = models.CharField(max_length=48, blank=True, default="")
    # beads per round — the user picks this (108 is the tradition, not a rule)
    mala_size = models.PositiveIntegerField(default=108)
    # target jaaps per day; 0 means "no target", and any count then counts
    daily_goal = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=16, default="#F5C96E")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    @property
    def beads(self):
        """Beads in one round. Never zero — a zero-sized mala would be a
        division by zero the moment anyone counts."""
        return max(1, int(self.mala_size or 1))

    @property
    def goal(self):
        """Daily target in jaaps; 1 when unset, so "any count" qualifies."""
        return max(1, int(self.daily_goal or 0))


class JaapLog(BaseModel):
    """One row per (mantra, date) — that chant's total for the day.

    A single row per day per mantra keeps the streak and graph maths trivial
    and matches how FitnessDay / IntakeLog already work in this app. Taps
    increment the counter on this row.
    """

    SOURCE_APP = "app"
    SOURCE_WHATSAPP = "whatsapp"
    SOURCE_MANUAL = "manual"

    mantra = models.ForeignKey(JaapMantra, on_delete=models.CASCADE, related_name="logs")
    date = models.DateField()
    count = models.PositiveIntegerField(default=0)
    # completed rounds = count // mantra.beads, cached so the UI need not divide
    malas = models.PositiveIntegerField(default=0)
    duration_min = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    source = models.CharField(max_length=16, default=SOURCE_APP)

    class Meta:
        unique_together = [("mantra", "date")]
        indexes = [models.Index(fields=["date"])]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} {self.mantra.name} x{self.count}"

    def recalc_malas(self):
        """Keep `malas` in step with `count` and the mantra's bead count."""
        self.malas = int(self.count or 0) // self.mantra.beads
        return self.malas


