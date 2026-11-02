from django.urls import path

from . import views

urlpatterns = [
    # dashboard / overview
    path("dashboard/", views.DashboardView.as_view()),
    path("overview/", views.OverviewView.as_view()),
    path("stats/", views.StatsView.as_view()),
    path("habit-analytics/", views.HabitAnalyticsView.as_view()),
    # data management — CSV import / export
    path("data/export/", views.DataExportView.as_view()),
    path("data/import/", views.DataImportView.as_view()),

    # settings
    path("settings/", views.SettingsView.as_view()),

    # habits
    path("habits/", views.HabitsView.as_view()),
    path("habits/heatmap/", views.HabitHeatmapView.as_view()),
    path("habits/toggle/", views.HabitToggleView.as_view()),
    path("habits/<int:pk>/", views.HabitDetailView.as_view()),
    path("habits/<int:pk>/note/", views.HabitNoteView.as_view()),
    path("habits/<int:pk>/notes/", views.HabitNotesView.as_view()),
    path("habits/<int:pk>/<str:action>/", views.HabitActionView.as_view()),
    path("habit-logs/", views.HabitLogsView.as_view()),

    # fitness
    path("fitness/", views.FitnessListView.as_view()),
    path("fitness/analytics/", views.FitnessAnalyticsView.as_view()),
    path("fitness/weight/", views.WeightLogView.as_view()),
    path("fitness/weight/<int:pk>/", views.WeightLogDetailView.as_view()),
    path("body-measurements/", views.BodyMeasurementsView.as_view()),
    path("body-measurements/<int:pk>/", views.BodyMeasurementDetailView.as_view()),
    path("intake/", views.IntakeView.as_view()),
    path("drinks/", views.DrinksView.as_view()),
    path("drinks/<int:pk>/", views.DrinkDetailView.as_view()),
    path("weight-insights/", views.WeightInsightsView.as_view()),
    path("journal/", views.JournalView.as_view()),

    # jaap — the mantra counter
    path("jaap-mantras/", views.JaapMantrasView.as_view()),
    path("jaap-mantras/<int:pk>/", views.JaapMantraDetailView.as_view()),
    path("jaap/", views.JaapView.as_view()),
    path("jaap/tap/", views.JaapTapView.as_view()),
    path("jaap/stats/", views.JaapStatsView.as_view()),    path("fitness/<str:date>/", views.FitnessDayView.as_view()),
    path("fitness/<str:date>/exercise/", views.FitnessExerciseView.as_view()),
    path("fitness/<str:date>/cardio/", views.FitnessCardioView.as_view()),

    # study
    path("study/", views.StudyListView.as_view()),
    path("study/analytics/", views.StudyAnalyticsView.as_view()),
    path("study/activity/", views.StudyActivityView.as_view()),
    path("study/activity/<int:pk>/", views.StudyActivityDetailView.as_view()),
    path("study/<str:date>/", views.StudyDayView.as_view()),

    # study resources (playlists, moved between lists)
    path("resources/", views.StudyResourcesView.as_view()),
    path("resources/<int:pk>/", views.StudyResourceDetailView.as_view()),
    path("resources/<int:pk>/move/", views.StudyResourceMoveView.as_view()),

    # goals
    path("objectives/", views.ObjectivesView.as_view()),
    path("objectives/<int:pk>/", views.ObjectiveDetailView.as_view()),
    path("objectives/<int:pk>/checkpoint/", views.ObjectiveCheckpointView.as_view()),
    path("objectives/<int:pk>/<str:action>/", views.ObjectiveActionView.as_view()),

    # whatsapp bridge
    path("mission/checkins/", views.CheckinView.as_view()),
    path("mission/leaderboard/", views.CheckinLeaderboardView.as_view()),
    path("members/", views.MembersView.as_view()),

    # food — dish database + diary
    path("food/", views.FoodListView.as_view()),
    path("food/<int:pk>/", views.FoodDetailView.as_view()),
    path("diary/", views.DiaryView.as_view()),
    path("diary/<int:pk>/", views.DiaryEntryView.as_view()),
    path("nutrition-targets/", views.NutritionTargetView.as_view()),

    # notes — one feed for every note
    path("notes/", views.NotesView.as_view()),
    path("notes/<int:pk>/", views.NoteDetailView.as_view()),
    path("day-note/", views.DayNoteView.as_view()),

    # workout modules (Legend-style named training days)
    path("workout-modules/", views.WorkoutModulesView.as_view()),
    path("workout-modules/<int:pk>/", views.WorkoutModuleDetailView.as_view()),
    path("workout-schedule/", views.WorkoutScheduleView.as_view()),

    # Legend-style training: library, active workout, history, progress
    path("exercises/", views.ExercisesView.as_view()),
    path("workout/<str:date>/", views.WorkoutView.as_view()),
    path("workout/<str:date>/start/", views.StartRoutineView.as_view()),
    path("workout/<str:date>/exercise/", views.WorkoutExercisesView.as_view()),
    path("workout-exercise/<int:pk>/", views.WorkoutExerciseDetailView.as_view()),
    path("workout-exercise/<int:pk>/sets/", views.WorkoutSetsView.as_view()),
    path("workout-set/<int:pk>/", views.WorkoutSetDetailView.as_view()),
    path("workout-history/", views.WorkoutHistoryView.as_view()),
    path("exercise-progress/", views.ExerciseProgressView.as_view()),
    path("muscle-fatigue/", views.MuscleFatigueView.as_view()),
    path("plate-calc/", views.PlateCalculatorView.as_view()),
]
