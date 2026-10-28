from django.db import models
from django.contrib.auth.models import User
from pathlib import Path
from django.db import models
from django.conf import settings


def answer_upload_path(instance, filename):
    suffix = Path(filename).suffix.lower() or ".bin"
    learner = instance.attempt.learner.user.username
    return f"answer_uploads/{learner}/attempt-{instance.attempt_id}/{instance.question_key}{suffix}"


class SyllabusPaper(models.Model):
    code = models.CharField(max_length=50, unique=True)
    track = models.CharField(max_length=30)
    name = models.CharField(max_length=255)
    subtitle = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=30, blank=True, null=True)
    created_at = models.DateTimeField(null=True, editable=False)
    updated_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        managed = False
        db_table = "syllabus_papers"
        ordering = ["id"]

    def __str__(self):
        return self.name


class SyllabusSection(models.Model):
    paper = models.ForeignKey(
        SyllabusPaper,
        db_column="paper_id",
        on_delete=models.DO_NOTHING,
        related_name="sections",
    )
    name = models.CharField(max_length=255)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, editable=False)
    updated_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        managed = False
        db_table = "syllabus_sections"
        ordering = ["paper_id", "sort_order"]

    def __str__(self):
        return f"{self.paper.code}: {self.name}"


class SyllabusPoint(models.Model):
    section = models.ForeignKey(
        SyllabusSection,
        db_column="section_id",
        on_delete=models.DO_NOTHING,
        related_name="points",
    )
    point = models.TextField()
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(null=True, editable=False)
    updated_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        managed = False
        db_table = "syllabus_points"
        ordering = ["section_id", "sort_order"]

    def __str__(self):
        return self.point


class PrelimsQuestion(models.Model):
    question_id = models.IntegerField()
    year = models.IntegerField()
    section = models.TextField(blank=True, null=True)
    question = models.TextField(blank=True, null=True)
    option_a = models.TextField(blank=True, null=True)
    option_b = models.TextField(blank=True, null=True)
    option_c = models.TextField(blank=True, null=True)
    option_d = models.TextField(blank=True, null=True)
    correct_answer = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    motivation = models.TextField(blank=True, null=True)
    difficulty = models.TextField(blank=True, null=True)
    nature = models.TextField(blank=True, null=True)
    source = models.TextField(blank=True, null=True)
    source_type = models.TextField(blank=True, null=True)
    source_file = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(null=True, editable=False)
    updated_at = models.DateTimeField(null=True, editable=False)

    class Meta:
        managed = False
        db_table = "prelims_questions"
        ordering = ["-year", "question_id"]

    def __str__(self):
        return f"Prelims {self.year} Q{self.question_id}"


class MainsQuestion(models.Model):
    id = models.AutoField(primary_key=True)

    question_id = models.TextField(unique=True)
    year = models.IntegerField()
    paper = models.TextField()
    subject = models.TextField(blank=True, null=True)
    question = models.TextField()

    syllabus_tags = models.TextField(blank=True, null=True)
    section = models.TextField(blank=True, null=True)

    option_a = models.TextField(blank=True, null=True)
    option_b = models.TextField(blank=True, null=True)
    option_c = models.TextField(blank=True, null=True)
    option_d = models.TextField(blank=True, null=True)

    correct_answer = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)
    motivation = models.TextField(blank=True, null=True)

    difficulty = models.TextField(blank=True, null=True)
    nature = models.TextField(blank=True, null=True)

    source = models.TextField(blank=True, null=True)
    source_type = models.TextField(blank=True, null=True)
    source_file = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(null=True, editable=False)
    updated_at = models.DateTimeField(null=True, editable=False)

    tags = models.TextField(blank=True, null=True)

    relevance = models.TextField(blank=True, null=True)
    current_affairs_linkage = models.TextField(blank=True, null=True)
    is_repeated_theme = models.BooleanField(default=False)

    option_a_explanation = models.TextField(blank=True, null=True)
    option_b_explanation = models.TextField(blank=True, null=True)
    option_c_explanation = models.TextField(blank=True, null=True)
    option_d_explanation = models.TextField(blank=True, null=True)

    why_correct = models.TextField(blank=True, null=True)

    marks = models.FloatField(blank=True, null=True)
    max_word_limit = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "mains_questions"
        ordering = ["-year", "paper", "question_id"]

    def __str__(self):
        return f"{self.paper} {self.year} {self.question_id}"


class LearnerAccount(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="learner_account"
    )
    target_year = models.PositiveIntegerField(blank=True, null=True)
    display_name = models.CharField(max_length=120, blank=True)
    age = models.PositiveIntegerField(blank=True, null=True)
    target_exam = models.CharField(max_length=120, blank=True)
    optional_subject = models.CharField(max_length=120, blank=True)
    daily_study_target_minutes = models.PositiveIntegerField(blank=True, null=True)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.user.username


class Progress(models.Model):
    learner = models.ForeignKey(
        LearnerAccount, on_delete=models.CASCADE, related_name="progress_records"
    )
    node_id = models.CharField(max_length=120)
    node_type = models.CharField(max_length=20, default="topic")
    questions_seen = models.PositiveIntegerField(default=0)
    questions_attempted = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    last_attempted_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "node_id"], name="unique_learner_progress_node"
            ),
        ]

    @property
    def accuracy(self):
        if not self.questions_attempted:
            return 0
        return round(self.correct_answers * 100 / self.questions_attempted, 2)

    def __str__(self):
        return f"{self.learner} · {self.node_id}"


class Attempt(models.Model):
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SUBMITTED = "submitted"
    STATUS_CHOICES = (
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_SUBMITTED, "Submitted"),
    )

    learner = models.ForeignKey(
        LearnerAccount, on_delete=models.CASCADE, related_name="attempts"
    )
    stage = models.CharField(max_length=20)
    paper = models.CharField(max_length=80, blank=True)
    node_id = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS
    )
    total_questions = models.PositiveIntegerField(default=0)
    answered_questions = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    score = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.learner} · {self.stage} · {self.started_at:%Y-%m-%d %H:%M}"


class AttemptResponse(models.Model):
    attempt = models.ForeignKey(
        Attempt, on_delete=models.CASCADE, related_name="responses"
    )
    question_key = models.CharField(max_length=120)
    question_stage = models.CharField(max_length=20)
    selected_answer = models.CharField(max_length=20, blank=True)
    response_text = models.TextField(blank=True)
    attachment = models.FileField(upload_to=answer_upload_path, blank=True, null=True)
    is_correct = models.BooleanField(blank=True, null=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, blank=True, null=True)
    answered_at = models.DateTimeField(auto_now=True)
    elapsed_seconds = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question_key"],
                name="unique_attempt_question_response",
            ),
        ]
        ordering = ["answered_at"]

    def __str__(self):
        return f"{self.attempt_id} · {self.question_key}"


class QuestionBookmark(models.Model):
    learner = models.ForeignKey(
        LearnerAccount, on_delete=models.CASCADE, related_name="bookmarks"
    )
    question_key = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "question_key"],
                name="unique_learner_question_bookmark",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.learner} · {self.question_key}"


class QuestionNote(models.Model):
    learner = models.ForeignKey(
        LearnerAccount, on_delete=models.CASCADE, related_name="notes"
    )
    question_key = models.CharField(max_length=120)
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.learner} · {self.question_key}"


class Goal(models.Model):
    learner = models.ForeignKey(
        LearnerAccount, on_delete=models.CASCADE, related_name="goals"
    )
    name = models.CharField(max_length=160)
    exam = models.CharField(max_length=120)
    target_year = models.PositiveIntegerField(blank=True, null=True)
    exam_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["exam_date", "-created_at"]

    def __str__(self):
        return f"{self.learner} · {self.name}"


class QuestionReview(models.Model):
    STATUS_OPEN = "open"
    STATUS_RESOLVED = "resolved"
    STATUS_CHOICES = (
        (STATUS_OPEN, "Open"),
        (STATUS_RESOLVED, "Resolved"),
    )

    REASON_CHOICES = (
        ("incorrect_option", "Incorrect option"),
        ("incorrect_question", "Incorrect question"),
        ("incorrect_answer_explanation", "Incorrect answer/explanation"),
        ("wrong_subject", "Wrong subject"),
        ("wrong_topic_tag", "Wrong topic/tag"),
        ("wrong_year", "Wrong year"),
        ("duplicate_question", "Duplicate question"),
        ("formatting_issue", "Formatting issue"),
        ("missing_information", "Missing information"),
        ("other", "Other"),
    )

    learner = models.ForeignKey(
        LearnerAccount, on_delete=models.CASCADE, related_name="question_reviews"
    )
    question_key = models.CharField(max_length=120)
    reasons = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["learner", "question_key"],
                name="unique_learner_question_review",
            )
        ]

    def __str__(self):
        return f"{self.learner} · {self.question_key} · {self.status}"


class ApiLog(models.Model):
    """
    Stores request + response of every API call.
    Logging happens only on the way out (in the middleware's process_response).
    """

    METHOD_CHOICES = [
        ("GET", "GET"),
        ("POST", "POST"),
        ("PUT", "PUT"),
        ("PATCH", "PATCH"),
        ("DELETE", "DELETE"),
        ("OPTIONS", "OPTIONS"),
        ("HEAD", "HEAD"),
    ]

    # Request side
    path = models.CharField(max_length=512, db_index=True)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, db_index=True)
    query_params = models.JSONField(default=dict, blank=True)
    request_body = models.JSONField(null=True, blank=True)  # sanitized input
    headers = models.JSONField(default=dict, blank=True)  # selected headers only

    # Response side
    status_code = models.PositiveSmallIntegerField(db_index=True)
    response_body = models.JSONField(null=True, blank=True)  # sanitized output

    # Context
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="api_logs",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Timing & error
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)  # filled by helper or exception
    traceback = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "api_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["path", "method"]),
            models.Index(fields=["status_code", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.method} {self.path} → {self.status_code}"
