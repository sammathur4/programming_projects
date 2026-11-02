from django.contrib import admin

from .models import (
    CheckinMember,
    DailyCheckin,
    DiaryEntry,
    Exercise,
    FitnessDay,
    Food,
    GoalCheckpoint,
    Habit,
    HabitLog,
    Note,
    NutritionTarget,
    Objective,
    Setting,
    StudyDay,
    StudyResource,
    WorkoutExercise,
    WorkoutModule,
    WorkoutSet,
)


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ["name", "emoji", "color", "order", "active", "status"]
    list_editable = ["order", "active"]
    list_filter = ["status", "active"]


@admin.register(HabitLog)
class HabitLogAdmin(admin.ModelAdmin):
    list_display = ["habit", "date", "done", "value", "note"]
    list_filter = ["habit", "done"]
    date_hierarchy = "date"


@admin.register(FitnessDay)
class FitnessDayAdmin(admin.ModelAdmin):
    list_display = ["date", "mode", "location", "weight_kg", "calories_in", "water_litres", "status"]
    list_filter = ["mode", "status"]
    date_hierarchy = "date"


@admin.register(StudyDay)
class StudyDayAdmin(admin.ModelAdmin):
    list_display = ["date", "mode", "location", "aw_count", "mcq_count", "study_hours"]
    date_hierarchy = "date"


@admin.register(Objective)
class ObjectiveAdmin(admin.ModelAdmin):
    list_display = ["area", "objective", "timeline", "status", "start_date", "target_date"]
    list_filter = ["status"]
    date_hierarchy = "start_date"


@admin.register(GoalCheckpoint)
class GoalCheckpointAdmin(admin.ModelAdmin):
    list_display = ["objective", "date", "progress_pct"]
    date_hierarchy = "date"


@admin.register(StudyResource)
class StudyResourceAdmin(admin.ModelAdmin):
    list_display = ["exam", "subject", "playlist_name", "status", "priority", "track", "videos_done", "videos"]
    list_filter = ["track", "status", "exam"]


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ["key", "value"]


@admin.register(CheckinMember)
class CheckinMemberAdmin(admin.ModelAdmin):
    list_display = ["name", "external_id", "habit"]
    search_fields = ["name", "external_id"]


@admin.register(DailyCheckin)
class DailyCheckinAdmin(admin.ModelAdmin):
    list_display = ["member", "date", "source", "score"]
    list_filter = ["source", "date"]
    date_hierarchy = "date"

    def score(self, obj):
        return obj.score


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ["name", "serving", "kcal", "protein_g", "carbs_g", "fat_g", "category", "is_custom"]
    list_filter = ["category", "is_custom"]
    search_fields = ["name"]


@admin.register(DiaryEntry)
class DiaryEntryAdmin(admin.ModelAdmin):
    list_display = ["date", "meal", "food_name", "quantity", "kcal"]
    list_filter = ["meal"]
    date_hierarchy = "date"


@admin.register(NutritionTarget)
class NutritionTargetAdmin(admin.ModelAdmin):
    list_display = ["calorie_goal", "protein_goal", "carbs_goal", "fat_goal"]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["date", "tag", "ref", "pinned", "text"]
    list_filter = ["tag", "pinned"]
    date_hierarchy = "date"
    search_fields = ["text", "ref"]


@admin.register(WorkoutModule)
class WorkoutModuleAdmin(admin.ModelAdmin):
    list_display = ["name", "emoji", "days", "order"]
    list_editable = ["order"]


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ["name", "muscle", "equipment", "is_compound", "is_cardio", "is_custom"]
    list_filter = ["muscle", "equipment", "is_compound", "is_cardio"]
    search_fields = ["name", "muscle"]


class WorkoutSetInline(admin.TabularInline):
    model = WorkoutSet
    extra = 0
    fields = ["order", "weight_kg", "reps", "set_type", "rpe", "rir", "rest_sec", "completed"]


@admin.register(WorkoutExercise)
class WorkoutExerciseAdmin(admin.ModelAdmin):
    list_display = ["date", "order", "name", "muscle", "superset_group", "target_sets", "target_reps"]
    list_filter = ["muscle"]
    date_hierarchy = "date"
    search_fields = ["name"]
    inlines = [WorkoutSetInline]


@admin.register(WorkoutSet)
class WorkoutSetAdmin(admin.ModelAdmin):
    list_display = ["workout_exercise", "order", "weight_kg", "reps", "set_type", "rpe", "completed"]
    list_filter = ["set_type", "completed"]
