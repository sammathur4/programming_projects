from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Attempt,
    AttemptResponse,
    LearnerAccount,
    MainsQuestion,
    PrelimsQuestion,
    Progress,
    QuestionBookmark,
    QuestionNote,
    SyllabusPaper,
    SyllabusPoint,
    SyllabusSection,
    ApiLog,
)


@admin.register(QuestionBookmark)
class QuestionBookmarkAdmin(admin.ModelAdmin):
    list_display = ("learner", "question_key", "created_at")
    search_fields = ("learner__user__username", "question_key")
    list_select_related = ("learner", "learner__user")


@admin.register(QuestionNote)
class QuestionNoteAdmin(admin.ModelAdmin):
    list_display = ("learner", "question_key", "short_note", "updated_at")
    search_fields = ("learner__user__username", "question_key", "note")
    list_select_related = ("learner", "learner__user")

    @admin.display(description="Note")
    def short_note(self, obj):
        return obj.note[:100]


@admin.register(LearnerAccount)
class LearnerAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "display_name",
        "target_year",
        "current_streak",
        "longest_streak",
        "last_activity_date",
    )
    list_filter = ("target_year", "last_activity_date")
    search_fields = ("user__username", "user__email", "display_name")
    list_select_related = ("user",)


@admin.register(Progress)
class ProgressAdmin(admin.ModelAdmin):
    list_display = (
        "learner",
        "node_id",
        "node_type",
        "questions_attempted",
        "correct_answers",
        "accuracy_display",
        "last_attempted_at",
    )
    list_filter = ("node_type", "last_attempted_at")
    search_fields = ("learner__user__username", "node_id")
    list_select_related = ("learner", "learner__user")

    @admin.display(description="Accuracy")
    def accuracy_display(self, obj):
        return f"{obj.accuracy}%"


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "learner",
        "stage",
        "paper",
        "node_id",
        "status",
        "score",
        "started_at",
        "submitted_at",
    )
    list_filter = ("status", "stage", "paper", "started_at", "submitted_at")
    search_fields = ("learner__user__username", "paper", "node_id")
    ordering = ("-started_at",)
    list_select_related = ("learner", "learner__user")


@admin.register(AttemptResponse)
class AttemptResponseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "attempt",
        "question_key",
        "selected_answer",
        "is_correct",
        "score",
        "attachment",
        "answered_at",
    )
    list_filter = ("question_stage", "is_correct", "answered_at")
    search_fields = (
        "question_key",
        "attempt__learner__user__username",
        "response_text",
    )
    ordering = ("-answered_at",)
    list_select_related = ("attempt", "attempt__learner", "attempt__learner__user")


@admin.register(SyllabusPaper)
class SyllabusPaperAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "track", "name", "subtitle", "color")
    list_filter = ("track", "color")
    search_fields = ("code", "name", "subtitle")
    ordering = ("id",)


@admin.register(SyllabusSection)
class SyllabusSectionAdmin(admin.ModelAdmin):
    list_display = ("id", "paper", "name", "sort_order")
    list_filter = ("paper",)
    search_fields = ("name", "paper__code", "paper__name")
    ordering = ("paper", "sort_order")
    list_select_related = ("paper",)


@admin.register(SyllabusPoint)
class SyllabusPointAdmin(admin.ModelAdmin):
    list_display = ("id", "section", "short_point", "sort_order")
    list_filter = ("section__paper", "section")
    search_fields = ("point", "section__name", "section__paper__code")
    ordering = ("section", "sort_order")
    list_select_related = ("section", "section__paper")

    @admin.display(description="Point")
    def short_point(self, obj):
        return obj.point[:120]


@admin.register(PrelimsQuestion)
class PrelimsQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "year",
        "question_id",
        "section",
        "difficulty",
        "correct_answer",
        "source_file",
    )
    list_filter = ("year", "section", "difficulty", "nature", "source_type")
    search_fields = ("question", "section", "explanation", "motivation", "source_file")
    ordering = ("-year", "question_id")
    list_per_page = 50
    fieldsets = (
        ("Question", {"fields": ("year", "question_id", "section", "question")}),
        (
            "Options and answer",
            {
                "fields": (
                    "option_a",
                    "option_b",
                    "option_c",
                    "option_d",
                    "correct_answer",
                )
            },
        ),
        (
            "Explanation",
            {"fields": ("explanation", "motivation", "difficulty", "nature")},
        ),
        ("Source", {"fields": ("source", "source_type", "source_file")}),
    )


@admin.register(MainsQuestion)
class MainsQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "question_id",
        "year",
        "paper",
        "subject",
        "section",
        "source_file",
    )

    list_filter = (
        "year",
        "paper",
        "subject",
        "difficulty",
        "nature",
        "relevance",
        "is_repeated_theme",
    )

    search_fields = (
        "question_id",
        "question",
        "paper",
        "subject",
        "section",
        "source_file",
    )

    ordering = (
        "-year",
        "paper",
        "question_id",
    )


@admin.register(ApiLog)
class ApiLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "method",
        "path_short",
        "status_code_colored",
        "user",
        "duration_ms",
        "ip_address",
        "has_error",
    )
    list_filter = (
        "method",
        "status_code",
        "created_at",
        ("user", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = (
        "path",
        "error_message",
        "ip_address",
        "user__username",
    )
    readonly_fields = (
        "path",
        "method",
        "query_params",
        "request_body",
        "headers",
        "status_code",
        "response_body",
        "user",
        "ip_address",
        "user_agent",
        "duration_ms",
        "error_message",
        "traceback",
        "created_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_per_page = 50

    # Make the detail view easier to read
    fieldsets = (
        (
            "Request",
            {
                "fields": (
                    "method",
                    "path",
                    "query_params",
                    "request_body",
                    "headers",
                )
            },
        ),
        (
            "Response",
            {
                "fields": (
                    "status_code",
                    "response_body",
                    "duration_ms",
                )
            },
        ),
        (
            "Context",
            {
                "fields": (
                    "user",
                    "ip_address",
                    "user_agent",
                    "created_at",
                )
            },
        ),
        (
            "Error",
            {
                "fields": (
                    "error_message",
                    "traceback",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def path_short(self, obj):
        if len(obj.path) > 60:
            return obj.path[:57] + "…"
        return obj.path

    path_short.short_description = "Path"

    def status_code_colored(self, obj):
        code = obj.status_code
        if code >= 500:
            color = "#dc3545"  # red
        elif code >= 400:
            color = "#fd7e14"  # orange
        elif code >= 300:
            color = "#0d6efd"  # blue
        else:
            color = "#198754"  # green
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            color,
            code,
        )

    status_code_colored.short_description = "Status"
    status_code_colored.admin_order_field = "status_code"

    def has_error(self, obj):
        return bool(obj.error_message or obj.traceback)

    has_error.boolean = True
    has_error.short_description = "Error?"

    # Logs are append-only – prevent accidental edits / deletes from the UI
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # Optional: only superusers can delete old logs
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
