"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app import views
    2. Add a URL to urlpatterns:  path('', include('other_app.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from syllabus.views import (
    learner_profile,
    learner_register,
    auth_session,
    auth_login,
    auth_logout,
    questions_overview,
    prelims_papers,
    record_response,
    start_attempt,
    submit_attempt,
    question_bookmark,
    question_note,
    syllabus_hierarchy,
    syllabus_overview,
    question_detail,
    question_note_detail,
    question_history,
    learner_bookmarks,
    random_question,

    # Goals
    learner_goals,
    learner_goal_detail,

    # Progress
    progress_overview,
    prelims_progress,
    mains_progress,

    # Reviews
    question_review,
    reviews,
    review_detail,
    resolve_review,
)


urlpatterns = [
    path("admin/", admin.site.urls),

    # ------------------------------------------------------------------
    # Syllabus / Questions
    # ------------------------------------------------------------------

    path(
        "api/syllabus/",
        syllabus_overview,
        name="syllabus-overview",
    ),

    path(
        "api/questions/",
        questions_overview,
        name="questions-overview",
    ),

    path(
        "api/prelims-papers/",
        prelims_papers,
        name="prelims-papers",
    ),

    path(
        "api/syllabus/hierarchy/",
        syllabus_hierarchy,
        name="syllabus-hierarchy",
    ),

    # ------------------------------------------------------------------
    # Authentication / Learner
    # ------------------------------------------------------------------

    path(
        "api/learners/register/",
        learner_register,
        name="learner-register",
    ),

    path(
        "api/auth/session/",
        auth_session,
        name="auth-session",
    ),

    path(
        "api/auth/login/",
        auth_login,
        name="auth-login",
    ),

    path(
        "api/auth/logout/",
        auth_logout,
        name="auth-logout",
    ),

    path(
        "api/learners/me/",
        learner_profile,
        name="learner-profile",
    ),

    # ------------------------------------------------------------------
    # Attempts
    # ------------------------------------------------------------------

    path(
        "api/attempts/start/",
        start_attempt,
        name="start-attempt",
    ),

    path(
        "api/attempts/<int:attempt_id>/responses/",
        record_response,
        name="record-response",
    ),

    path(
        "api/attempts/<int:attempt_id>/submit/",
        submit_attempt,
        name="submit-attempt",
    ),

    # ------------------------------------------------------------------
    # Question actions
    # ------------------------------------------------------------------

    path(
        "api/questions/<str:question_key>/bookmark/",
        question_bookmark,
        name="question-bookmark",
    ),

    path(
        "api/questions/<str:question_key>/note/",
        question_note,
        name="question-note",
    ),

    # IMPORTANT:
    # Random must come before the dynamic question_key route.
    path(
        "api/questions/random/",
        random_question,
        name="random-question",
    ),

    # Review for a specific question
    path(
        "api/questions/<str:question_key>/review/",
        question_review,
        name="question-review",
    ),

    path(
        "api/questions/<str:question_key>/notes/",
        question_note,
        name="question-notes",
    ),

    path(
        "api/questions/<str:question_key>/notes/<int:note_id>/",
        question_note_detail,
        name="question-note-detail",
    ),

    # Generic question detail MUST remain after the more specific routes.
    path(
        "api/questions/<str:question_key>/",
        question_detail,
        name="question-detail",
    ),

    # ------------------------------------------------------------------
    # History / Bookmarks
    # ------------------------------------------------------------------

    path(
        "api/history/",
        question_history,
        name="question-history",
    ),

    path(
        "api/bookmarks/",
        learner_bookmarks,
        name="learner-bookmarks",
    ),

    # ------------------------------------------------------------------
    # Goals
    # ------------------------------------------------------------------

    path(
        "api/goals/",
        learner_goals,
        name="learner-goals",
    ),

    path(
        "api/goals/<int:goal_id>/",
        learner_goal_detail,
        name="learner-goal-detail",
    ),

    # ------------------------------------------------------------------
    # Progress
    # ------------------------------------------------------------------

    path(
        "api/progress/",
        progress_overview,
        name="progress-overview",
    ),

    path(
        "api/progress/prelims/",
        prelims_progress,
        name="prelims-progress",
    ),

    path(
        "api/progress/mains/",
        mains_progress,
        name="mains-progress",
    ),

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    path(
        "api/reviews/",
        reviews,
        name="reviews",
    ),

    path(
        "api/reviews/<int:review_id>/",
        review_detail,
        name="review-detail",
    ),

    path(
        "api/reviews/<int:review_id>/resolve/",
        resolve_review,
        name="resolve-review",
    ),
]


# ----------------------------------------------------------------------
# Media files
# ----------------------------------------------------------------------

urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT,
)