from rest_framework import serializers

from .models import (
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


class HabitSerializer(serializers.ModelSerializer):
    streak = serializers.SerializerMethodField()
    best_streak = serializers.SerializerMethodField()
    completion_30d = serializers.SerializerMethodField()
    marks = serializers.SerializerMethodField()
    is_paused = serializers.BooleanField(read_only=True)

    class Meta:
        model = Habit
        fields = [
            "id", "name", "emoji", "color", "order", "active", "status", "is_paused",
            "description", "target_value", "target_unit", "paused_at", "created_at",
            "streak", "best_streak", "completion_30d", "marks",
        ]
        read_only_fields = ["created_at", "paused_at"]

    def get_streak(self, obj):
        return getattr(obj, "_streak", None)

    def get_best_streak(self, obj):
        return getattr(obj, "_best_streak", None)

    def get_completion_30d(self, obj):
        return getattr(obj, "_completion_30d", None)

    def get_marks(self, obj):
        return getattr(obj, "_marks", [])


class HabitLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitLog
        fields = ["habit", "date", "done", "value", "note"]


class FitnessDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = FitnessDay
        fields = [
            "date", "location", "mode", "muscles", "cardio", "weight_kg",
            "calories_in", "water_litres", "status", "notes", "food",
            "exercises", "cardio_items", "duration_min", "steps",
        ]


class StudyDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyDay
        fields = ["date", "location", "mode", "slots", "aw_count", "mcq_count", "study_hours", "notes"]


class GoalCheckpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = GoalCheckpoint
        fields = ["id", "objective", "date", "progress_pct", "note"]


class ObjectiveSerializer(serializers.ModelSerializer):
    days_elapsed = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    habit_analysis = serializers.SerializerMethodField()
    checkpoints = GoalCheckpointSerializer(many=True, read_only=True)

    class Meta:
        model = Objective
        fields = [
            "id", "area", "objective", "timeline", "target", "notes", "status",
            "order", "start_date", "target_date", "paused_at", "paused_days",
            "progress_pct", "linked_habits", "color", "created_at",
            "days_elapsed", "days_left", "progress", "habit_analysis", "checkpoints",
        ]
        read_only_fields = ["created_at", "paused_at", "paused_days"]

    def get_days_elapsed(self, obj):
        return getattr(obj, "_days_elapsed", None)

    def get_days_left(self, obj):
        return getattr(obj, "_days_left", None)

    def get_progress(self, obj):
        return getattr(obj, "_progress", None)

    def get_habit_analysis(self, obj):
        return getattr(obj, "_habit_analysis", None)


class StudyResourceSerializer(serializers.ModelSerializer):
    progress_pct = serializers.SerializerMethodField()

    class Meta:
        model = StudyResource
        fields = [
            "id", "track", "months", "exam", "paper", "priority", "status",
            "subject", "playlist_name", "playlist_url", "videos",
            "duration_hms", "start_date", "end_date", "notes", "order",
            "videos_done", "moved_at", "progress_pct",
        ]

    def validate(self, attrs):
        # merge with the instance so partial PATCHes are still validated
        videos = attrs.get("videos", getattr(self.instance, "videos", None))
        done = attrs.get("videos_done", getattr(self.instance, "videos_done", 0))
        if done is not None and done < 0:
            raise serializers.ValidationError({"videos_done": "must be non-negative"})
        if videos is not None and done is not None and done > videos:
            raise serializers.ValidationError(
                {"videos_done": "cannot exceed total videos"})
        return attrs

    def get_progress_pct(self, obj):
        if not obj.videos:
            return 100 if obj.track == StudyResource.TRACK_COMPLETED else 0
        return min(100, round(obj.videos_done / obj.videos * 100))


class StudyActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyActivity
        fields = [
            "id", "date", "activity_type", "subject", "resource", "time_spent_minutes",
            "questions_attempted", "questions_completed", "correct_answers", "incorrect_answers",
            "answers_written", "word_count", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        # merge with the instance so partial PATCHes are still validated
        def val(name):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, None) if self.instance else None

        for name in ("time_spent_minutes", "questions_attempted", "questions_completed",
                     "correct_answers", "incorrect_answers", "answers_written", "word_count"):
            v = val(name)
            if v is not None and v < 0:
                raise serializers.ValidationError({name: "must be non-negative"})

        attempted = val("questions_attempted")
        completed = val("questions_completed")
        correct = val("correct_answers") or 0
        incorrect = val("incorrect_answers") or 0
        if attempted is not None and completed is not None and completed > attempted:
            raise serializers.ValidationError(
                {"questions_completed": "cannot exceed questions_attempted"})
        if attempted is not None and correct + incorrect > attempted:
            raise serializers.ValidationError(
                {"correct_answers": "correct + incorrect cannot exceed questions_attempted"})
        return attrs


class WeightLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightLog
        fields = ["id", "date", "weight_kg", "time", "notes", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_weight_kg(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("weight must be a positive number")
        return value


class BodyMeasurementSerializer(serializers.ModelSerializer):
    class Meta:
        model = BodyMeasurement
        fields = [
            "id", "date", "bodyweight_kg", "neck_cm", "chest_cm", "waist_cm",
            "hips_cm", "left_arm_cm", "right_arm_cm", "left_thigh_cm", "right_thigh_cm",
            "left_calf_cm", "right_calf_cm", "body_fat_pct", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        for name, value in attrs.items():
            if name == "date" or value is None:
                continue
            if isinstance(value, (int, float)) or hasattr(value, "quantize"):
                try:
                    if float(value) < 0:
                        raise serializers.ValidationError({name: "must be non-negative"})
                except (TypeError, ValueError):
                    pass
        return attrs


class IntakeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntakeLog
        fields = ["id", "date", "water_ml", "protein_g", "calories", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        for name in ("water_ml", "protein_g", "calories"):
            v = attrs.get(name)
            if v is not None and v < 0:
                raise serializers.ValidationError({name: "must be non-negative"})
        return attrs


class DrinkLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrinkLog
        fields = [
            "id", "date", "drink_type", "volume_ml", "caffeine_mg", "calories",
            "time", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_drink_type(self, value):
        from .models import DRINK_PRESETS

        value = (value or "").strip().lower()
        if value not in DRINK_PRESETS:
            raise serializers.ValidationError(
                f"unknown drink type; expected one of {', '.join(DRINK_PRESETS)}")
        return value

    def validate_volume_ml(self, value):
        if value is not None and value > 5000:
            raise serializers.ValidationError("a single drink can't exceed 5000 ml")
        return value


class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = ["key", "value"]


class CheckinMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckinMember
        fields = ["id", "external_id", "name", "whatsapp_id", "habit"]


class DailyCheckinSerializer(serializers.ModelSerializer):
    member_id = serializers.CharField(write_only=True, required=False)
    member_name = serializers.CharField(source="member.name", read_only=True)
    member_external = serializers.CharField(source="member.external_id", read_only=True)
    score = serializers.IntegerField(read_only=True)

    class Meta:
        model = DailyCheckin
        fields = [
            "id", "member", "member_id", "member_name", "member_external",
            "date", "source", "done", "missed", "note", "score",
        ]
        read_only_fields = ["member"]


# ---------------------------------------------------------------------
# Food
# ---------------------------------------------------------------------
class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = [
            "id", "name", "serving", "kcal", "protein_g", "carbs_g", "fat_g",
            "category", "is_custom",
        ]


class DiaryEntrySerializer(serializers.ModelSerializer):
    """Read shape plus a `food_id` write-only input for logging a dish."""

    food_id = serializers.IntegerField(write_only=True, required=False)
    quantity = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = DiaryEntry
        fields = [
            "id", "date", "meal", "food", "food_id", "food_name", "quantity",
            "kcal", "protein_g", "carbs_g", "fat_g",
        ]
        read_only_fields = ["food", "food_name", "kcal", "protein_g", "carbs_g", "fat_g"]

    def create(self, validated_data):
        """Snapshot the dish's nutrition at log time, scaled by quantity.

        Macros are copied rather than joined so that editing or deleting a dish
        later cannot rewrite what you already ate.
        """
        qty = validated_data.pop("quantity", None) or 1
        food_id = validated_data.pop("food_id", None)
        if food_id is None:
            raise serializers.ValidationError({"food_id": "Required to log a dish."})
        try:
            dish = Food.objects.get(pk=food_id)
        except Food.DoesNotExist:
            raise serializers.ValidationError({"food_id": f"No dish with id {food_id}."})

        validated_data.update(
            food=dish,
            food_name=dish.name,
            quantity=qty,
            kcal=round(float(dish.kcal) * float(qty)),
            protein_g=round(float(dish.protein_g) * float(qty), 1),
            carbs_g=round(float(dish.carbs_g) * float(qty), 1),
            fat_g=round(float(dish.fat_g) * float(qty), 1),
        )
        return super().create(validated_data)


class NutritionTargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionTarget
        fields = ["calorie_goal", "protein_goal", "carbs_goal", "fat_goal", "water_goal_ml"]


# ---------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------
class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "date", "tag", "ref", "text", "pinned", "created_at"]
        read_only_fields = ["created_at"]


# ---------------------------------------------------------------------
# Workout modules
# ---------------------------------------------------------------------
class WorkoutModuleSerializer(serializers.ModelSerializer):
    muscles = serializers.SerializerMethodField()
    total_sets = serializers.SerializerMethodField()
    volume_kg = serializers.SerializerMethodField()

    class Meta:
        model = WorkoutModule
        fields = [
            "id", "name", "color", "emoji", "days", "exercises", "order",
            "muscles", "total_sets", "volume_kg",
        ]

    def get_muscles(self, obj):
        return obj.muscles

    def get_total_sets(self, obj):
        """Working sets only — cardio contributes no sets."""
        return sum(0 if e.get("cardio") else int(e.get("sets") or 0) for e in obj.exercises or [])

    def get_volume_kg(self, obj):
        """Rough planned volume. Reps may be a range ('6-8') — use its lower
        bound, since it is an estimate for a plan, not a logged session."""
        total = 0
        for e in obj.exercises or []:
            if e.get("cardio"):
                continue
            total += int(e.get("sets") or 0) * _rep_count(e.get("reps")) * float(e.get("weight_kg") or 0)
        return round(total)


def _rep_count(reps):
    """'8' -> 8, '6-8' -> 6, 'AMRAP' -> 0. Plans store rep ranges as strings."""
    if reps is None:
        return 0
    s = str(reps).strip()
    if "-" in s:
        s = s.split("-")[0].strip()
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------
# Legend-style training — exercise library, performed exercises, sets
# ---------------------------------------------------------------------
class ExerciseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = [
            "id", "name", "muscle", "secondary", "equipment", "is_compound",
            "instructions", "is_cardio", "is_custom",
        ]


class WorkoutSetSerializer(serializers.ModelSerializer):
    volume_kg = serializers.ReadOnlyField()
    est_1rm = serializers.ReadOnlyField()
    # write-only: sets are always read nested under their parent exercise, so
    # the FK only needs to be settable (POST workout-exercise/<pk>/sets/).
    workout_exercise = serializers.PrimaryKeyRelatedField(
        queryset=WorkoutSet._meta.get_field("workout_exercise").related_model.objects.all(),
        write_only=True,
    )

    class Meta:
        model = WorkoutSet
        fields = [
            "id", "order", "weight_kg", "reps", "duration_sec", "distance_km",
            "set_type", "rpe", "rir", "rest_sec", "completed", "note",
            "volume_kg", "est_1rm", "workout_exercise",
        ]

    def validate(self, data):
        """RPE and RIR must agree, and a set needs *something* measurable."""
        rpe = data.get("rpe", getattr(self.instance, "rpe", None))
        rir = data.get("rir", getattr(self.instance, "rir", None))
        if rpe is not None and not (WorkoutSet.RPE_MIN <= float(rpe) <= WorkoutSet.RPE_MAX):
            raise serializers.ValidationError({"rpe": "RPE must be between 0 and 10."})
        # if only one is supplied, derive the other so they can never disagree
        if rpe is not None and rir is None:
            data["rir"] = max(0, 10 - int(round(float(rpe))))
        elif rir is not None and rpe is None:
            data["rpe"] = 10 - int(rir)
        return data


class WorkoutExerciseSerializer(serializers.ModelSerializer):
    sets = WorkoutSetSerializer(many=True, read_only=True)
    summary = serializers.ReadOnlyField()

    class Meta:
        model = WorkoutExercise
        fields = [
            "id", "date", "exercise", "name", "muscle", "order",
            "superset_group", "target_sets", "target_reps", "rest_seconds",
            "note", "sets", "summary",
        ]

    def validate_sets(self, value):
        return value


def set_volume(sets_qs):
    """Total weight moved, warm-ups excluded."""
    return sum(s.volume_kg for s in sets_qs)


class JaapMantraSerializer(serializers.ModelSerializer):
    beads = serializers.IntegerField(read_only=True)
    goal = serializers.IntegerField(read_only=True)

    class Meta:
        model = JaapMantra
        fields = [
            "id", "name", "emoji", "devanagari", "transliteration", "category", "deity",
            "mala_size", "daily_goal", "color", "is_active", "sort_order",
            "beads", "goal", "created_at", "updated_at",
        ]

    def validate_mala_size(self, v):
        # A zero-bead mala would break every division on it.
        v = int(v or 0)
        if v < 1:
            raise serializers.ValidationError("Mala size must be at least 1.")
        if v > 100000:
            raise serializers.ValidationError("Mala size is unreasonably large.")
        return v

    def validate_category(self, v):
        v = (v or "").strip().lower()
        if v and v not in JaapMantra.CATEGORIES:
            raise serializers.ValidationError(
                "Category must be one of: %s" % ", ".join(JaapMantra.CATEGORIES)
            )
        return v or JaapMantra.CATEGORY_NAAM


class JaapLogSerializer(serializers.ModelSerializer):
    mantra_name = serializers.CharField(source="mantra.name", read_only=True)
    mantra_color = serializers.CharField(source="mantra.color", read_only=True)
    beads = serializers.IntegerField(source="mantra.beads", read_only=True)

    class Meta:
        model = JaapLog
        fields = [
            "id", "mantra", "mantra_name", "mantra_color", "beads", "date",
            "count", "malas", "duration_min", "notes", "source",
            "created_at", "updated_at",
        ]
