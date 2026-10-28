from django.http import JsonResponse
from django.db import connection
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from .models import (
    Attempt,
    AttemptResponse,
    LearnerAccount,
    Progress,
    QuestionBookmark,
    QuestionNote,
    Goal,
    QuestionReview,
)
from .local import local_learner_required, local_learner
from .http import json_error
import re
import json
import random
from datetime import timedelta
from pathlib import Path


def _key(value):
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _paper_code(stage, paper, source_file=""):
    if stage == "prelims":
        return "prelims-csat" if _key(paper).startswith("prelims csat") else "prelims-gs"
    return {
        "essay": "essay",
        "gs1": "gs1",
        "gs2": "gs2",
        "gs3": "gs3",
        "gs4": "gs4",
        "sociology1": "sociology-1",
        "sociology2": "sociology-2",
    }.get(_key(paper).replace(" ", ""), paper)


def _subject_alias(stage, section):
    value = _key(section)
    aliases = {
        "polity": "polity governance",
        "polity governance": "polity governance",
        "politics governance": "polity governance",
        "economy": "economy society",
        "economics": "economy society",
        "economic social development": "economy society",
        "environment ecology": "environment",
        "environment ecology climate change": "environment",
        "science technology": "science",
        "s t": "science",
        "modern india": "history",
        "modern history": "history",
        "ancient history": "history",
        "medieval history": "history",
        "art culture": "history",
        "art and culture": "history",
    }
    return aliases.get(value, value)


def _load_hierarchy():
    hierarchy = []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT id, code, track, name, subtitle, color FROM syllabus_papers ORDER BY id"
        )
        papers = cursor.fetchall()
        cursor.execute(
            "SELECT id, paper_id, name, sort_order FROM syllabus_sections ORDER BY paper_id, sort_order"
        )
        sections = cursor.fetchall()
        cursor.execute(
            "SELECT id, section_id, point, sort_order FROM syllabus_points ORDER BY section_id, sort_order"
        )
        points = cursor.fetchall()

    points_by_section = {}
    for point_id, section_id, point, sort_order in points:
        points_by_section.setdefault(section_id, []).append(
            {
                "id": f"topic-{point_id}",
                "label": point,
                "question_count": 0,
                "questions": [],
            }
        )

    sections_by_paper = {}
    for section_id, paper_id, name, sort_order in sections:
        sections_by_paper.setdefault(paper_id, []).append(
            {
                "id": f"subject-{section_id}",
                "label": name,
                "key": _key(name),
                "topics": points_by_section.get(section_id, []),
                "question_count": 0,
            }
        )

    for paper_id, code, track, name, subtitle, color in papers:
        hierarchy.append(
            {
                "id": code,
                "track": track,
                "name": name,
                "subtitle": subtitle,
                "color": color,
                "subjects": sections_by_paper.get(paper_id, []),
                "question_count": 0,
            }
        )
    return hierarchy


def _map_question(question, hierarchy):
    paper_code = _paper_code(
        question["stage"], question["paper"], question.get("source_file", "")
    )
    paper = next((item for item in hierarchy if item["id"] == paper_code), None)
    if not paper:
        return question

    subject_key = _subject_alias(question["stage"], question.get("section"))
    subject = next(
        (item for item in paper["subjects"] if item["key"] == subject_key), None
    )
    if not subject and paper["subjects"]:
        subject = paper["subjects"][0]
    if not subject:
        return question

    question["paper"] = paper["id"]
    question["paper_name"] = paper["name"]
    question["subject"] = subject["label"]
    question["subject_id"] = subject["id"]
    subject["question_count"] += 1
    paper["question_count"] += 1

    # The imported syllabus stores official points as the topic level. A
    # question is the browseable leaf beneath its exact topic.
    question_words = set(
        _key(f'{question.get("section")} {question.get("question")}').split()
    )
    topic = max(
        subject["topics"],
        key=lambda item: len(question_words & set(_key(item["label"]).split())),
        default=None,
    )
    if topic:
        question["topic"] = topic["label"]
        question["topic_id"] = topic["id"]
        question["subtopic"] = question["question"]
        question["subtopic_id"] = question["id"]
        topic["question_count"] += 1
        topic["questions"].append(question["id"])
    return question


def _read_questions():
    questions = []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT id, question_id, paper, year, section, question, option_a,
                   option_b, option_c, option_d, correct_answer, explanation,
                   motivation, difficulty, source_file, question_number, marks,
                   negative_marks
            FROM prelims_questions
            ORDER BY year DESC, question_id
        """)
        for row in cursor.fetchall():
            questions.append(
                {
                    "id": f"prelims-{row[0]}",
                    "stage": "prelims",
                    "paper": row[2] or "Prelims GS",
                    "year": row[3],
                    "question_number": row[15] or row[1],
                    "exam_question_id": row[1],
                    "section": row[4],
                    "question": row[5],
                    "options": _question_options(row[6:10]),
                    "answer": row[10],
                    "explanation": row[11],
                    "motivation": row[12],
                    "difficulty": row[13],
                    "source_file": row[14],
                    "marks": row[16],
                    "negative_marks": row[17],
                    "word_limit": None,
                }
            )
        cursor.execute("""
            SELECT
                id,
                question_id,
                paper,
                year,
                subject,
                question,
                syllabus_tags,
                section,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer,
                explanation,
                motivation,
                difficulty,
                nature,
                source,
                source_type,
                source_file,
                tags,
                relevance,
                current_affairs_linkage,
                is_repeated_theme,
                option_a_explanation,
                option_b_explanation,
                option_c_explanation,
                option_d_explanation,
                why_correct,
                marks,
                max_word_limit
            FROM mains_questions
            ORDER BY year DESC, paper, id
        """)
        for row in cursor.fetchall():
            questions.append(
                {
                    "id": f"mains-{row[0]}",
                    "stage": "mains",
                    "paper": row[2],
                    "year": row[3],
                    "question_id": row[1],
                    "question_number": row[1],
                    "subject": row[4],
                    "question": row[5],
                    "syllabus_tags": row[6],
                    "section": row[7],
                    "options": _question_options(row[8:12]),
                    "answer": row[12],
                    "explanation": row[13],
                    "motivation": row[14],
                    "difficulty": row[15],
                    "nature": row[16],
                    "source": row[17],
                    "source_type": row[18],
                    "source_file": row[19],
                    "tags": row[20],
                    "relevance": row[21],
                    "current_affairs_linkage": row[22],
                    "is_repeated_theme": bool(row[23]),
                    "option_explanations": {
                        "a": row[24],
                        "b": row[25],
                        "c": row[26],
                        "d": row[27],
                    },
                    "why_correct": row[28],
                    "marks": row[29],
                    "word_limit": row[30],
                }
            )
    return questions


def syllabus_hierarchy(request):
    hierarchy = _load_hierarchy()
    questions = _read_questions()
    for question in questions:
        _map_question(question, hierarchy)

    for paper in hierarchy:
        for subject in paper["subjects"]:
            for topic in subject["topics"]:
                topic.pop("questions", None)
                topic["subtopics"] = [
                    {
                        "id": question_id,
                        "label": "Mapped questions",
                        "question_count": 1,
                    }
                    for question_id in topic.pop("questions", [])
                ]

    return JsonResponse({"papers": hierarchy})


def prelims_papers(request):
    """Paper-level metadata for prelims: duration, marks, instructions."""
    year = request.GET.get("year", "all")
    paper = request.GET.get("paper", "all")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT year, paper, paper_code, title, duration_minutes, total_marks,
                   total_questions, marks_per_question, negative_marks,
                   instructions, source_file
            FROM prelims_papers
            WHERE (%s = 'all' OR year = %s)
              AND (%s = 'all' OR paper = %s)
            ORDER BY year DESC, paper
            """,
            [year, year if year.isdigit() else -1, paper, paper],
        )
        columns = [item[0] for item in cursor.description]
        papers = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return JsonResponse({"papers": papers})


def _question_options(row):
    options = {}
    for key, value in zip(("a", "b", "c", "d"), row):
        if value:
            options[key] = value
    return options


def _prelims_option_explanations(question_id):
    """
    Return per-option explanations when the optional explanation columns
    exist in prelims_questions.
    """
    allowed_columns = {
        "option_a_explanation",
        "option_b_explanation",
        "option_c_explanation",
        "option_d_explanation",
    }

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA table_info(prelims_questions)")
        table_columns = {row[1] for row in cursor.fetchall()}

    available = sorted(allowed_columns.intersection(table_columns))
    if not available:
        return {}

    select_sql = ", ".join(available)

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {select_sql} FROM prelims_questions WHERE id = %s",
            [question_id],
        )
        row = cursor.fetchone()

    if not row:
        return {}

    explanations = {}
    for column, value in zip(available, row):
        if value:
            key = column.replace("option_", "").replace("_explanation", "")
            explanations[key] = value

    return explanations


@local_learner_required
def question_detail(request, question_key):
    """
    Return one learner-facing question.

    The answer key and explanations are withheld until the question has
    been attempted. Once a learner has attempted a prelims question,
    its result/explanation is returned so it remains visible on reload.
    """
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    # `/api/questions/<question_key>/` also matches the literal `random`
    # when the dynamic URL is registered before `/api/questions/random/`.
    # Delegate that reserved key to the random-question handler so the quiz
    # endpoint works even before the URL patterns are reordered.
    if question_key == "random":
        return random_question(request)

    questions = _read_questions()
    question = next(
        (item for item in questions if item["id"] == question_key),
        None,
    )

    if not question:
        return JsonResponse({"error": "question not found"}, status=404)

    hierarchy = _load_hierarchy()
    _map_question(question, hierarchy)

    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))

    response_objects = list(
        AttemptResponse.objects.filter(
            attempt__learner=learner,
            question_key=question_key,
        )
        .select_related("attempt")
        .order_by("-answered_at")
    )

    # Keep every attempt for the question detail page.  History is intentionally
    # deduplicated separately, while the question page acts as the full attempt
    # timeline.
    responses = []
    for response in response_objects:
        responses.append({
            "id": response.id,
            "attempt_id": response.attempt_id,
            "question_stage": response.question_stage,
            "selected_answer": response.selected_answer,
            "response_text": response.response_text,
            "is_correct": response.is_correct,
            "score": response.score,
            "answered_at": response.answered_at,
            "elapsed_seconds": response.elapsed_seconds,
            "attachment_url": (
                request.build_absolute_uri(response.attachment.url)
                if response.attachment else None
            ),
            "attachment_name": response.attachment.name.rsplit("/", 1)[-1] if response.attachment else None,
            "attachment_type": (
                "pdf" if response.attachment and response.attachment.name.lower().endswith(".pdf")
                else "image" if response.attachment else None
            ),
            "attempt_started_at": response.attempt.started_at,
            "attempt_submitted_at": response.attempt.submitted_at,
        })

    latest_response = responses[0] if responses else None
    latest_result = None

    if latest_response and question["stage"] == "prelims":
        latest_result = {
            "is_correct": latest_response["is_correct"],
            "correct_answer": _answer_for_question(question_key),
            "explanation": _explanation_for_question(question_key),
        }

        prefix, _, raw_id = question_key.partition("-")
        if prefix == "prelims" and raw_id.isdigit():
            latest_result["option_explanations"] = _prelims_option_explanations(
                int(raw_id)
            )

    # Never expose answer/explanation before submission.
    question.pop("answer", None)
    question.pop("correct_answer", None)
    question.pop("explanation", None)
    question.pop("motivation", None)

    # Keep the learner page focused on the question and attempt.
    question.pop("source", None)
    question.pop("source_type", None)
    question.pop("source_file", None)
    question.pop("tags", None)

    notes = list(
    QuestionNote.objects
    .filter(
        learner=learner,
        question_key=question_key,
    )
    .order_by("-created_at")
    .values(
        "id",
        "note",
        "created_at",
        "updated_at",
    )
)

    bookmarked = QuestionBookmark.objects.filter(
        learner=learner,
        question_key=question_key,
    ).exists()

    return JsonResponse(
        {
            "question": question,
            "attempted": bool(responses),
            "attempt_count": len(responses),
            "latest_response": latest_response,
            "responses": responses,
            "latest_result": latest_result,
            "note": notes or [],
            "bookmarked": bookmarked,
        }
    )


def questions_overview(request):
    stage = request.GET.get("stage", "all").lower()
    paper = request.GET.get("paper", "all")
    year = request.GET.get("year", "all")
    search = request.GET.get("search", "").strip()
    node = request.GET.get("node", "")
    theme = request.GET.get("theme", "").strip().lower()

    try:
        page = max(int(request.GET.get("page", 1)), 1)
        page_size = min(max(int(request.GET.get("page_size", 20)), 1), 50)
    except ValueError:
        page, page_size = 1, 20

    questions = []
    hierarchy = _load_hierarchy()
    with connection.cursor() as cursor:
        if stage in ("all", "prelims"):
            cursor.execute(
                """
                SELECT id, question_id, paper, year, section, question,
                       option_a, option_b, option_c, option_d,
                       correct_answer, explanation, motivation, difficulty,
                       source_file, question_number, marks, negative_marks
                FROM prelims_questions
                                WHERE (%s = 'all' OR year = %s)
                                    AND (%s = 'all' OR COALESCE(paper, 'Prelims GS') = %s)
                                    AND (%s = '' OR question LIKE %s OR section LIKE %s)
                ORDER BY year DESC, question_id
                """,
                [
                    year,
                    year if year.isdigit() else -1,
                    paper,
                    paper,
                    search,
                    f"%{search}%",
                    f"%{search}%",
                ],
            )
            for row in cursor.fetchall():
                questions.append(
                    _map_question(
                        {
                            "id": f"prelims-{row[0]}",
                            "stage": "prelims",
                            "paper": row[2] or "Prelims GS",
                            "year": row[3],
                            "question_number": row[15] or row[1],
                            "exam_question_id": row[1],
                            "section": row[4],
                            "question": row[5],
                            "options": _question_options(row[6:10]),
                            "answer": row[10],
                            "explanation": row[11],
                            "motivation": row[12],
                            "difficulty": row[13],
                            "source_file": row[14],
                            "marks": row[16],
                            "negative_marks": row[17],
                            "word_limit": None,
                        },
                        hierarchy,
                    )
                )

        if stage in ("all", "mains"):
            cursor.execute(
                """
                SELECT
                    id,
                    question_id,
                    paper,
                    year,
                    subject,
                    question,
                    syllabus_tags,
                    section,
                    option_a,
                    option_b,
                    option_c,
                    option_d,
                    correct_answer,
                    explanation,
                    motivation,
                    difficulty,
                    nature,
                    source,
                    source_type,
                    source_file,
                    tags,
                    relevance,
                    current_affairs_linkage,
                    is_repeated_theme,
                    option_a_explanation,
                    option_b_explanation,
                    option_c_explanation,
                    option_d_explanation,
                    why_correct,
                    marks,
                    max_word_limit
                FROM mains_questions
                WHERE (%s = 'all' OR paper = %s)
                  AND (%s = 'all' OR year = %s)
                  AND (
                      %s = ''
                      OR question LIKE %s
                      OR section LIKE %s
                      OR subject LIKE %s
                  )
                ORDER BY year DESC, paper, id
                """,
                [
                    paper,
                    paper,
                    year,
                    year if year.isdigit() else -1,
                    search,
                    f"%{search}%",
                    f"%{search}%",
                    f"%{search}%",
                ],
            )
            for row in cursor.fetchall():
                questions.append(
                    _map_question(
                        {
                            "id": f"mains-{row[0]}",
                            "stage": "mains",
                            "paper": row[2],
                            "year": row[3],
                            "question_id": row[1],
                            "question_number": row[1],
                            "subject": row[4],
                            "question": row[5],
                            "syllabus_tags": row[6],
                            "section": row[7],
                            "options": _question_options(row[8:12]),
                            "answer": row[12],
                            "explanation": row[13],
                            "motivation": row[14],
                            "difficulty": row[15],
                            "nature": row[16],
                            "source": row[17],
                            "source_type": row[18],
                            "source_file": row[19],
                            "tags": row[20],
                            "relevance": row[21],
                            "current_affairs_linkage": row[22],
                            "is_repeated_theme": bool(row[23]),
                            "option_explanations": {
                                "a": row[24],
                                "b": row[25],
                                "c": row[26],
                                "d": row[27],
                            },
                            "why_correct": row[28],
                            "marks": row[29],
                            "word_limit": row[30],
                        },
                        hierarchy,
                    )
                )

    if stage == "all":
        questions.sort(
            key=lambda item: (
                -(item["year"] or 0),
                item["stage"],
                item["paper"],
                item["question_number"] or 0,
            )
        )

    if paper != "all" and stage == "prelims":
        wanted = _paper_code("prelims", paper)
        questions = [question for question in questions if question["paper"] == wanted]
    if node:
        questions = [
            question
            for question in questions
            if node
            in (
                question.get("subject_id"),
                question.get("topic_id"),
                question.get("subtopic_id"),
            )
        ]

    total = len(questions)
    start = (page - 1) * page_size
    end = start + page_size

    # Answers remain available to staff/admin models, but are never sent to
    # the learner-facing question API.
    for question in questions:
        question.pop("answer", None)
        question.pop("explanation", None)
        question.pop("motivation", None)

    return JsonResponse(
        {
            "questions": questions[start:end],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size,
            },
        }
    )


def _request_json(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return None


def _request_payload(request):
    if request.content_type.startswith("multipart/"):
        return request.POST.dict()
    return _request_json(request) or {}


def _learner_for_user(user=None):
    if user is not None and getattr(user, "is_authenticated", False):
        learner, _ = LearnerAccount.objects.get_or_create(
            user=user,
            defaults={"display_name": user.get_full_name() or user.username},
        )
        return learner
    return local_learner()


def health(request):
    learner = local_learner()
    counts = {}
    with connection.cursor() as cursor:
        try:
            cursor.execute("SELECT COUNT(*) FROM prelims_questions")
            counts["prelims"] = cursor.fetchone()[0]
        except Exception:
            counts["prelims"] = 0
        try:
            cursor.execute("SELECT COUNT(*) FROM mains_questions")
            counts["mains"] = cursor.fetchone()[0]
        except Exception:
            counts["mains"] = 0
    return JsonResponse(
        {
            "ok": True,
            "learner": {"id": learner.id, "username": learner.user.username},
            "counts": counts,
        }
    )


def _serialize_goal(goal):
    return {
        "id": goal.id,
        "name": goal.name,
        "exam": goal.exam,
        "target_year": goal.target_year,
        "exam_date": goal.exam_date,
        "description": goal.description,
        "is_active": goal.is_active,
        "created_at": goal.created_at,
        "updated_at": goal.updated_at,
    }


def _normalize_review_reasons(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    allowed = {key for key, _ in QuestionReview.REASON_CHOICES}
    return [str(item) for item in value if str(item) in allowed]


def _question_metadata_map():
    hierarchy = _load_hierarchy()
    result = {}
    for question in _read_questions():
        _map_question(question, hierarchy)
        result[question["id"]] = question
    return result


def _is_attempted_response(response):
    return bool(
        response.selected_answer
        or response.response_text
        or response.attachment
    )


def _progress_bucket(label, stage, total, attempted_keys, responses):
    attempted = len(attempted_keys)
    objective = [r for r in responses if r.question_stage == "prelims" and r.is_correct is not None]
    correct = sum(1 for r in objective if r.is_correct)
    return {
        "id": label,
        "label": label,
        "stage": stage,
        "attempted": attempted,
        "total": total,
        "coverage": round(attempted * 100 / total, 2) if total else 0,
        "correct": correct,
        "objective_answered": len(objective),
        "accuracy": round(correct * 100 / len(objective), 2) if objective else None,
    }


def _build_progress(learner):
    question_map = _question_metadata_map()
    all_questions = list(question_map.values())
    responses = list(AttemptResponse.objects.filter(attempt__learner=learner).select_related("attempt"))
    attempted_responses = [r for r in responses if _is_attempted_response(r)]

    prelim_questions = [q for q in all_questions if q.get("stage") == "prelims"]
    mains_questions = [q for q in all_questions if q.get("stage") == "mains"]
    prelim_attempted = {}
    mains_attempted = {}
    for response in attempted_responses:
        if response.question_key not in question_map:
            continue
        if response.question_stage == "prelims":
            prelim_attempted.setdefault(response.question_key, []).append(response)
        elif response.question_stage == "mains":
            mains_attempted.setdefault(response.question_key, []).append(response)

    subject_totals = {}
    subject_keys = {}
    subject_responses = {}
    for q in prelim_questions:
        label = str(q.get("subject") or q.get("section") or "Other")
        subject_totals[label] = subject_totals.get(label, 0) + 1
        subject_keys.setdefault(label, set()).add(q["id"])
    for key, rows in prelim_attempted.items():
        q = question_map[key]
        label = str(q.get("subject") or q.get("section") or "Other")
        subject_responses.setdefault(label, []).extend(rows)

    prelim_subjects = []
    for label in sorted(subject_totals):
        keys = {key for key in prelim_attempted if key in subject_keys[label]}
        prelim_subjects.append(_progress_bucket(label, "prelims", subject_totals[label], keys, subject_responses.get(label, [])))

    paper_defs = [
        ("gs1", "GS1"), ("gs2", "GS2"), ("gs3", "GS3"), ("gs4", "GS4"),
        ("essay", "Essay"), ("sociology1", "Sociology Paper 1"), ("sociology2", "Sociology Paper 2"),
    ]
    mains_groups = []
    for code, label in paper_defs:
        qs = [q for q in mains_questions if _paper_code("mains", q.get("paper"), q.get("source_file")) == code]
        keys = {q["id"] for q in qs}
        attempted_keys = keys.intersection(mains_attempted.keys())
        rows = [r for k in attempted_keys for r in mains_attempted[k]]
        word_counts = []
        for r in rows:
            if r.response_text:
                word_counts.append(len(r.response_text.split()))
        mains_groups.append({
            "id": code,
            "label": label,
            "stage": "mains",
            "attempted": len(attempted_keys),
            "total": len(qs),
            "coverage": round(len(attempted_keys) * 100 / len(qs), 2) if qs else 0,
            "average_marks": None if not rows else round(sum(float(r.score) for r in rows if r.score is not None) / max(1, sum(r.score is not None for r in rows)), 2),
            "average_word_count": round(sum(word_counts) / len(word_counts), 2) if word_counts else None,
        })

    prelim_overall = _progress_bucket("Overall", "prelims", len(prelim_questions), set(prelim_attempted), [r for r in attempted_responses if r.question_stage == "prelims"])
    mains_overall = {
        "id": "Overall", "label": "Overall", "stage": "mains",
        "attempted": len(mains_attempted), "total": len(mains_questions),
        "coverage": round(len(mains_attempted) * 100 / len(mains_questions), 2) if mains_questions else 0,
    }
    return {
        "prelims": {"overall": prelim_overall, "subjects": prelim_subjects},
        "mains": {"overall": mains_overall, "papers": mains_groups},
    }


@local_learner_required
@csrf_exempt
def learner_profile(request):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    if request.method == "PATCH":
        payload = _request_json(request) or {}
        if "display_name" in payload:
            learner.display_name = str(payload.get("display_name") or "").strip()[:120]
        if "email" in payload:
            request.user.email = str(payload.get("email") or "").strip()
            request.user.save(update_fields=["email"])
        if "age" in payload:
            learner.age = payload.get("age") or None
        if "target_exam" in payload:
            learner.target_exam = str(payload.get("target_exam") or "").strip()[:120]
        if "target_year" in payload:
            learner.target_year = payload.get("target_year") or None
        if "optional_subject" in payload:
            learner.optional_subject = str(payload.get("optional_subject") or "").strip()[:120]
        if "daily_study_target_minutes" in payload:
            learner.daily_study_target_minutes = payload.get("daily_study_target_minutes") or None
        learner.save()
    elif request.method != "GET":
        return JsonResponse({"error": "GET or PATCH required"}, status=405)

    answer_history = list(AttemptResponse.objects.filter(attempt__learner=learner).values(
        "attempt_id", "question_key", "question_stage", "selected_answer", "response_text",
        "is_correct", "score", "answered_at", "elapsed_seconds"
    ))
    bookmarks = list(learner.bookmarks.values_list("question_key", flat=True))
    notes = {}
    for note in learner.notes.all().order_by("-created_at"):
        notes.setdefault(note.question_key, []).append({
            "id": note.id, "note": note.note, "created_at": note.created_at, "updated_at": note.updated_at,
        })
    unique_attempted = {r["question_key"] for r in answer_history if r["selected_answer"] or r["response_text"]}
    if any(r.get("question_stage") == "mains" for r in answer_history):
        unique_attempted |= {r["question_key"] for r in answer_history if r.get("question_stage") == "mains"}
    review_count = learner.question_reviews.filter(status=QuestionReview.STATUS_OPEN).count()
    return JsonResponse({
        "learner": {
            "id": learner.id, "username": request.user.username, "display_name": learner.display_name,
            "email": request.user.email, "age": learner.age, "target_exam": learner.target_exam,
            "target_year": learner.target_year, "optional_subject": learner.optional_subject,
            "daily_study_target_minutes": learner.daily_study_target_minutes,
        },
        "streak": {"current": learner.current_streak, "longest": learner.longest_streak, "last_activity_date": learner.last_activity_date},
        "stats": {"questions_attempted": len(unique_attempted), "bookmarks": len(bookmarks), "review": review_count},
        "progress": _build_progress(learner),
        "attempts": list(learner.attempts.values("id", "stage", "paper", "node_id", "status", "score", "started_at", "submitted_at")),
        "answer_history": answer_history,
        "bookmarks": bookmarks,
        "notes": notes,
    })


@local_learner_required
@csrf_exempt
def learner_goals(request):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    if request.method == "GET":
        return JsonResponse({"goals": [_serialize_goal(g) for g in learner.goals.all()]})
    if request.method != "POST":
        return JsonResponse({"error": "GET or POST required"}, status=405)
    payload = _request_json(request) or {}
    if not payload.get("name") or not payload.get("exam"):
        return JsonResponse({"error": "name and exam are required"}, status=400)
    if payload.get("is_active"):
        learner.goals.update(is_active=False)
    goal = Goal.objects.create(
        learner=learner, name=str(payload["name"]).strip(), exam=str(payload["exam"]).strip(),
        target_year=payload.get("target_year") or None, exam_date=payload.get("exam_date") or None,
        description=str(payload.get("description") or "").strip(), is_active=bool(payload.get("is_active", True)),
    )
    return JsonResponse({"goal": _serialize_goal(goal)}, status=201)


@local_learner_required
@csrf_exempt
def learner_goal_detail(request, goal_id):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    try:
        goal = learner.goals.get(id=goal_id)
    except Goal.DoesNotExist:
        return JsonResponse({"error": "Goal not found"}, status=404)
    if request.method in ("PATCH", "PUT"):
        payload = _request_json(request) or {}
        for field in ("name", "exam", "description"):
            if field in payload:
                setattr(goal, field, str(payload.get(field) or "").strip())
        for field in ("target_year", "exam_date"):
            if field in payload:
                setattr(goal, field, payload.get(field) or None)
        if "is_active" in payload:
            goal.is_active = bool(payload["is_active"])
            if goal.is_active:
                learner.goals.exclude(id=goal.id).update(is_active=False)
        goal.save()
        return JsonResponse({"goal": _serialize_goal(goal)})
    if request.method == "DELETE":
        goal.delete()
        return JsonResponse({"deleted": True, "id": goal_id})
    return JsonResponse({"error": "PATCH, PUT or DELETE required"}, status=405)


@local_learner_required
def progress_overview(request):
    return JsonResponse(_build_progress(_learner_for_user(request.user)))


@local_learner_required
def prelims_progress(request):
    return JsonResponse(_build_progress(_learner_for_user(request.user))["prelims"])


@local_learner_required
def mains_progress(request):
    return JsonResponse(_build_progress(_learner_for_user(request.user))["mains"])


def _review_payload(review, question=None, request=None):
    result = {
        "id": review.id, "question_key": review.question_key, "status": review.status,
        "reasons": review.reasons or [], "note": review.note, "created_at": review.created_at,
        "updated_at": review.updated_at, "resolved_at": review.resolved_at,
    }
    if question is not None:
        result.update({
            "year": question.get("year"), "stage": question.get("stage"), "paper": question.get("paper"),
            "paper_name": question.get("paper_name"), "subject": question.get("subject"),
            "section": question.get("section"), "topic": question.get("topic"),
            "question_number": question.get("question_number"), "question": question.get("question"),
            "options": question.get("options", {}),
        })
    return result


@local_learner_required
@csrf_exempt
def question_review(request, question_key):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    if request.method == "POST":
        payload = _request_json(request) or {}
        reasons = _normalize_review_reasons(payload.get("reasons", []))
        note = str(payload.get("note") or "").strip()
        review, _ = QuestionReview.objects.get_or_create(learner=learner, question_key=question_key)
        review.reasons = reasons
        review.note = note
        review.status = QuestionReview.STATUS_OPEN
        review.resolved_at = None
        review.save()
        return JsonResponse({"review": _review_payload(review, _question_metadata_map().get(question_key))}, status=201)
    if request.method == "DELETE":
        QuestionReview.objects.filter(learner=learner, question_key=question_key).delete()
        return JsonResponse({"deleted": True, "question_key": question_key})
    if request.method == "GET":
        review = learner.question_reviews.filter(question_key=question_key).first()
        if not review:
            return JsonResponse({"review": None})
        return JsonResponse({"review": _review_payload(review, _question_metadata_map().get(question_key))})
    return JsonResponse({"error": "GET, POST or DELETE required"}, status=405)


@local_learner_required
@csrf_exempt
def reviews(request):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    question_map = _question_metadata_map()
    qs = learner.question_reviews.all()
    status = request.GET.get("status", "open")
    reason = request.GET.get("reason", "")
    if status != "all":
        qs = qs.filter(status=status)
    result = []
    for review in qs:
        if reason and reason not in (review.reasons or []):
            continue
        result.append(_review_payload(review, question_map.get(review.question_key)))
    return JsonResponse({"reviews": result, "unresolved_count": learner.question_reviews.filter(status=QuestionReview.STATUS_OPEN).count()})


@local_learner_required
@csrf_exempt
def review_detail(request, review_id):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    try:
        review = learner.question_reviews.get(id=review_id)
    except QuestionReview.DoesNotExist:
        return JsonResponse({"error": "Review not found"}, status=404)
    if request.method in ("PATCH", "PUT"):
        payload = _request_json(request) or {}
        if "reasons" in payload:
            review.reasons = _normalize_review_reasons(payload["reasons"])
        if "note" in payload:
            review.note = str(payload.get("note") or "").strip()
        review.save()
        return JsonResponse({"review": _review_payload(review, _question_metadata_map().get(review.question_key))})
    if request.method == "GET":
        return JsonResponse({"review": _review_payload(review, _question_metadata_map().get(review.question_key))})
    return JsonResponse({"error": "GET or PATCH required"}, status=405)


@local_learner_required
@csrf_exempt
def resolve_review(request, review_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    try:
        review = learner.question_reviews.get(id=review_id)
    except QuestionReview.DoesNotExist:
        return JsonResponse({"error": "Review not found"}, status=404)
    review.status = QuestionReview.STATUS_RESOLVED
    review.resolved_at = timezone.now()
    review.save(update_fields=["status", "resolved_at", "updated_at"])
    return JsonResponse({"review": _review_payload(review, _question_metadata_map().get(review.question_key))})


@local_learner_required
@csrf_exempt
def start_attempt(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    payload = _request_json(request) or {}
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    attempt = Attempt.objects.create(
        learner=learner,
        stage=payload.get("stage", "mixed"),
        paper=payload.get("paper", ""),
        node_id=payload.get("node_id", ""),
        total_questions=payload.get("total_questions", 0),
    )
    return JsonResponse(
        {"id": attempt.id, "status": attempt.status, "started_at": attempt.started_at}
    )


def _answer_for_question(question_key):
    prefix, _, raw_id = question_key.partition("-")
    if not raw_id.isdigit():
        return None
    with connection.cursor() as cursor:
        if prefix == "prelims":
            cursor.execute(
                "SELECT correct_answer FROM prelims_questions WHERE id = %s", [raw_id]
            )
        elif prefix == "mains":
            cursor.execute(
                "SELECT correct_answer FROM mains_questions WHERE id = %s", [raw_id]
            )
        else:
            return None
        row = cursor.fetchone()
    return row[0] if row else None


def _explanation_for_question(question_key):
    prefix, _, raw_id = question_key.partition("-")
    if prefix != "prelims" or not raw_id.isdigit():
        return None
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT explanation FROM prelims_questions WHERE id = %s", [raw_id]
        )
        row = cursor.fetchone()
    return row[0] if row else None


@local_learner_required
@csrf_exempt
def record_response(request, attempt_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    payload = _request_payload(request)
    question_key = payload.get("question_key")
    if not question_key:
        return JsonResponse({"error": "question_key is required"}, status=400)
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    uploaded_file = request.FILES.get("attachment")
    if uploaded_file:
        allowed_types = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
        allowed_suffixes = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
        if (
            uploaded_file.content_type not in allowed_types
            or Path(uploaded_file.name).suffix.lower() not in allowed_suffixes
        ):
            return JsonResponse(
                {"error": "Only PDF, JPG, PNG, and WEBP files are accepted"}, status=400
            )
    try:
        attempt = learner.attempts.get(id=attempt_id, status=Attempt.STATUS_IN_PROGRESS)
    except Attempt.DoesNotExist:
        return JsonResponse({"error": "active attempt not found"}, status=404)

    expected = _answer_for_question(question_key)
    selected = str(payload.get("selected_answer", ""))
    is_correct = None if expected is None else selected.lower() == str(expected).lower()
    with transaction.atomic():
        response, created = AttemptResponse.objects.update_or_create(
            attempt=attempt,
            question_key=question_key,
            defaults={
                "question_stage": payload.get("question_stage", attempt.stage),
                "selected_answer": selected,
                "response_text": payload.get("response_text", ""),
                "is_correct": is_correct,
                "score": payload.get("score"),
                "elapsed_seconds": payload.get("elapsed_seconds"),
                "depth": payload.get("depth"),
            },
        )
        if response.local_date is None:
            response.local_date = timezone.localdate()
            response.save(update_fields=["local_date"])
        if uploaded_file:
            response.attachment = uploaded_file
            response.save(update_fields=["attachment"])
        attempted_filter = (
            Q(selected_answer__gt="")
            | Q(response_text__gt="")
            | Q(attachment__isnull=False)
        )

        attempt.answered_questions = attempt.responses.filter(attempted_filter).count()
        attempt.correct_answers = attempt.responses.filter(is_correct=True).count()
        attempt.save(
            update_fields=[
                "answered_questions",
                "correct_answers",
                "updated_at",
            ]
        )

        progress_node = attempt.node_id or payload.get("node_id", "")
        if progress_node:
            learner_responses = AttemptResponse.objects.filter(
                attempt__learner=learner,
                attempt__node_id=progress_node,
            )
            question_keys = set(
                learner_responses.values_list("question_key", flat=True)
            )

            Progress.objects.update_or_create(
                learner=learner,
                node_id=progress_node,
                defaults={
                    "node_type": payload.get("node_type", "topic"),
                    "questions_seen": len(question_keys),
                    "questions_attempted": learner_responses.filter(
                        attempted_filter
                    ).count(),
                    "correct_answers": learner_responses.filter(
                        is_correct=True
                    ).count(),
                    "last_attempted_at": response.answered_at,
                },
            )

    result = {
        "id": response.id,
        "attempt_id": attempt.id,
        "attempted": True,
        "is_correct": is_correct,
        "answered_at": response.answered_at,
    }

    if response.question_stage == "prelims":
        result["correct_answer"] = _answer_for_question(question_key)
        result["explanation"] = _explanation_for_question(question_key)

        prefix, _, raw_id = question_key.partition("-")
        if prefix == "prelims" and raw_id.isdigit():
            result["option_explanations"] = _prelims_option_explanations(int(raw_id))

    return JsonResponse(result)


@local_learner_required
@csrf_exempt
def submit_attempt(request, attempt_id):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    try:
        attempt = learner.attempts.get(id=attempt_id, status=Attempt.STATUS_IN_PROGRESS)
    except Attempt.DoesNotExist:
        return JsonResponse({"error": "active attempt not found"}, status=404)
    now = timezone.now()
    attempt.status = Attempt.STATUS_SUBMITTED
    attempt.submitted_at = now
    attempt.score = attempt.correct_answers
    attempt.save(update_fields=["status", "submitted_at", "score", "updated_at"])
    today = timezone.localdate()
    if learner.last_activity_date != today:
        learner.last_activity_date = today
        learner.save(update_fields=["last_activity_date", "updated_at"])
    return JsonResponse(
        {
            "id": attempt.id,
            "status": attempt.status,
            "score": attempt.score,
            "submitted_at": attempt.submitted_at,
        }
    )


@local_learner_required
@csrf_exempt
def question_bookmark(request, question_key):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    if request.method == "POST":
        QuestionBookmark.objects.get_or_create(
            learner=learner, question_key=question_key
        )
        return JsonResponse({"bookmarked": True})
    if request.method == "DELETE":
        QuestionBookmark.objects.filter(
            learner=learner, question_key=question_key
        ).delete()
        return JsonResponse({"bookmarked": False})
    return JsonResponse({"error": "POST or DELETE required"}, status=405)


@local_learner_required
@csrf_exempt
def question_note(request, question_key):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))

    # ---------------------------------------------------------
    # GET — return all notes for this question
    # ---------------------------------------------------------
    if request.method == "GET":
        notes = list(
            QuestionNote.objects.filter(
                learner=learner,
                question_key=question_key,
            )
            .order_by("-created_at")
            .values(
                "id",
                "note",
                "created_at",
                "updated_at",
            )
        )

        return JsonResponse(
            {
                "notes": notes,
            }
        )

    # ---------------------------------------------------------
    # POST — CREATE a brand-new note
    # ---------------------------------------------------------
    if request.method == "POST":
        payload = _request_json(request) or {}
        note_text = str(payload.get("note", "")).strip()

        if not note_text:
            return JsonResponse(
                {"error": "Note cannot be empty"},
                status=400,
            )

        record = QuestionNote.objects.create(
            learner=learner,
            question_key=question_key,
            note=note_text,
        )

        return JsonResponse(
            {
                "note": {
                    "id": record.id,
                    "note": record.note,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            },
            status=201,
        )

    return JsonResponse(
        {"error": "GET or POST required"},
        status=405,
    )


@local_learner_required
@csrf_exempt
def question_note_detail(request, question_key, note_id):
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))

    try:
        record = QuestionNote.objects.get(
            id=note_id,
            learner=learner,
            question_key=question_key,
        )
    except QuestionNote.DoesNotExist:
        return JsonResponse(
            {"error": "Note not found"},
            status=404,
        )

    # ---------------------------------------------------------
    # PATCH — edit existing note
    # ---------------------------------------------------------
    if request.method in ("PATCH", "PUT"):
        payload = _request_json(request) or {}
        note_text = str(payload.get("note", "")).strip()

        if not note_text:
            return JsonResponse(
                {"error": "Note cannot be empty"},
                status=400,
            )

        record.note = note_text
        record.save(update_fields=["note", "updated_at"])

        return JsonResponse(
            {
                "note": {
                    "id": record.id,
                    "note": record.note,
                    "created_at": record.created_at,
                    "updated_at": record.updated_at,
                }
            }
        )

    # ---------------------------------------------------------
    # DELETE — delete only this note
    # ---------------------------------------------------------
    if request.method == "DELETE":
        record.delete()

        return JsonResponse(
            {
                "deleted": True,
                "id": note_id,
            }
        )

    return JsonResponse(
        {"error": "PATCH, PUT or DELETE required"},
        status=405,
    )



@local_learner_required
def question_history(request):
    """
    Return the learner's attempted questions enriched with question metadata.
    This powers the History tab without requiring the frontend to make one
    request per attempt.
    """
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    hierarchy = _load_hierarchy()

    question_map = {}
    for question in _read_questions():
        _map_question(question, hierarchy)
        question_map[question["id"]] = question

    rows = list(
        AttemptResponse.objects.filter(attempt__learner=learner)
        .select_related("attempt")
        .order_by("-answered_at")
    )

    # History is a question index, not an attempt log.  Show only the most
    # recent response for each question; the question detail page exposes the
    # complete attempt history.
    history = []
    seen_question_keys = set()
    attempt_counts = {}
    for row in rows:
        attempt_counts[row.question_key] = attempt_counts.get(row.question_key, 0) + 1

    for row in rows:
        if row.question_key in seen_question_keys:
            continue
        seen_question_keys.add(row.question_key)
        question = question_map.get(row.question_key, {})
        history.append(
            {
                "id": row.id,
                "attempt_id": row.attempt_id,
                "question_key": row.question_key,
                "question_stage": row.question_stage,
                "selected_answer": row.selected_answer,
                "response_text": row.response_text,
                "is_correct": row.is_correct,
                "score": row.score,
                "answered_at": row.answered_at,
                "elapsed_seconds": row.elapsed_seconds,
                "attachment_url": (
                    request.build_absolute_uri(row.attachment.url)
                    if row.attachment else None
                ),
                "attachment_name": row.attachment.name.rsplit("/", 1)[-1] if row.attachment else None,
                "attempt_count": attempt_counts[row.question_key],
                "year": question.get("year"),
                "paper": question.get("paper"),
                "paper_name": question.get("paper_name"),
                "question_number": question.get("question_number"),
                "subject": question.get("subject"),
                "section": question.get("section"),
                "topic": question.get("topic"),
                "question": question.get("question"),
            }
        )

    return JsonResponse({"history": history, "total_unique_questions": len(history)})


@local_learner_required
def learner_bookmarks(request):
    """Return bookmarked questions with the same learner-facing metadata as Practice."""
    learner = getattr(request, "learner", None) or _learner_for_user(getattr(request, "user", None))
    hierarchy = _load_hierarchy()

    bookmarked_keys = list(
        learner.bookmarks.values_list("question_key", flat=True)
    )
    bookmarked_set = set(bookmarked_keys)

    questions = []
    for question in _read_questions():
        if question["id"] not in bookmarked_set:
            continue

        _map_question(question, hierarchy)

        # Never expose answer keys or explanations in the browse response.
        question.pop("answer", None)
        question.pop("correct_answer", None)
        question.pop("explanation", None)
        question.pop("motivation", None)

        questions.append(question)

    # Preserve newest bookmark order where possible.
    order = {key: index for index, key in enumerate(bookmarked_keys)}
    questions.sort(key=lambda item: order.get(item["id"], 999999))

    return JsonResponse({"bookmarks": questions})


@local_learner_required
def random_question(request):
    """
    Return one random learner-facing question.

    Optional filters:
      stage=prelims|mains
      paper=<paper code>
      subject=<subject name>
    """
    stage = request.GET.get("stage", "all").lower()
    paper = request.GET.get("paper", "all")
    subject = request.GET.get("subject", "").strip().lower()

    hierarchy = _load_hierarchy()
    candidates = []

    for question in _read_questions():
        _map_question(question, hierarchy)

        if stage != "all" and question.get("stage") != stage:
            continue

        if paper != "all" and question.get("paper") != paper:
            continue

        if subject:
            values = {
                str(question.get("subject") or "").lower(),
                str(question.get("section") or "").lower(),
            }
            if subject not in values and not any(
                subject in value for value in values
            ):
                continue

        candidates.append(question)

    if not candidates:
        return JsonResponse(
            {"error": "No questions match the requested filters"},
            status=404,
        )

    question = random.choice(candidates)

    # Random quiz is still learner-facing; do not leak the answer.
    question.pop("answer", None)
    question.pop("correct_answer", None)
    question.pop("explanation", None)
    question.pop("motivation", None)

    return JsonResponse({"question": question})

def syllabus_overview(request):
    papers = []

    with connection.cursor() as cursor:

        # -----------------------------------------
        # Get papers
        # -----------------------------------------
        cursor.execute("""
            SELECT
                id,
                code,
                track,
                name,
                subtitle,
                color
            FROM syllabus_papers
            ORDER BY id
        """)

        paper_rows = cursor.fetchall()

        # -----------------------------------------
        # Get sections
        # -----------------------------------------
        cursor.execute("""
            SELECT
                id,
                paper_id,
                name,
                sort_order
            FROM syllabus_sections
            ORDER BY paper_id, sort_order
        """)

        section_rows = cursor.fetchall()

        # -----------------------------------------
        # Get points
        # -----------------------------------------
        cursor.execute("""
            SELECT
                id,
                section_id,
                point,
                sort_order
            FROM syllabus_points
            ORDER BY section_id, sort_order
        """)

        point_rows = cursor.fetchall()

    # -----------------------------------------
    # Build points lookup
    # -----------------------------------------

    points_by_section = {}

    for point_id, section_id, point, sort_order in point_rows:

        if section_id not in points_by_section:
            points_by_section[section_id] = []

        points_by_section[section_id].append(point)

    # -----------------------------------------
    # Build sections lookup
    # -----------------------------------------

    sections_by_paper = {}

    for section_id, paper_id, name, sort_order in section_rows:

        if paper_id not in sections_by_paper:
            sections_by_paper[paper_id] = []

        sections_by_paper[paper_id].append(
            {"name": name, "points": points_by_section.get(section_id, [])}
        )

    # -----------------------------------------
    # Build final API response
    # -----------------------------------------

    for paper_id, code, track, name, subtitle, color in paper_rows:

        papers.append(
            {
                "id": code,
                "track": track,
                "name": name,
                "subtitle": subtitle,
                "color": color,
                "topics": sections_by_paper.get(paper_id, []),
            }
        )

    # -----------------------------------------
    # Totals
    # -----------------------------------------

    total_papers = len(papers)

    total_topics = sum(len(paper["topics"]) for paper in papers)

    total_points = sum(
        len(topic["points"]) for paper in papers for topic in paper["topics"]
    )

    return JsonResponse(
        {
            "papers": papers,
            "totals": {
                "papers": total_papers,
                "topics": total_topics,
                "points": total_points,
            },
        }
    )
