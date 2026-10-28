import os
import json
from pathlib import Path

import django
from django.db import connection, transaction


# ============================================================
# DJANGO SETUP
# ============================================================

# CHANGE THIS if your settings.py is under a different package.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Your extracted JSON
JSON_FILE = Path.home() / "upsc_pyq_extracted" / "questions" / "questions.json"


# ============================================================
# CREATE TABLES
# ============================================================

CREATE_TABLES_SQL = """

-- ============================================================
-- PYQ QUESTIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS pyq_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    year INTEGER NOT NULL,

    stage TEXT NOT NULL,
    paper_code TEXT NOT NULL,

    question_number INTEGER NOT NULL,
    question TEXT NOT NULL,

    marks INTEGER,
    section TEXT,

    topics TEXT,

    source_pdf TEXT,
    source_file TEXT,
    source_page INTEGER,

    needs_review INTEGER NOT NULL DEFAULT 0,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(year, paper_code, question_number)
);


-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_pyq_year
ON pyq_questions(year);

CREATE INDEX IF NOT EXISTS idx_pyq_stage
ON pyq_questions(stage);

CREATE INDEX IF NOT EXISTS idx_pyq_paper
ON pyq_questions(paper_code);

CREATE INDEX IF NOT EXISTS idx_pyq_year_paper
ON pyq_questions(year, paper_code);

CREATE INDEX IF NOT EXISTS idx_pyq_review
ON pyq_questions(needs_review);

"""


# ============================================================
# INSERT / UPDATE
# ============================================================

INSERT_SQL = """

INSERT INTO pyq_questions (
    year,
    stage,
    paper_code,
    question_number,
    question,
    marks,
    section,
    topics,
    source_pdf,
    source_file,
    source_page,
    needs_review
)

VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s
)

ON CONFLICT(year, paper_code, question_number)

DO UPDATE SET

    stage = excluded.stage,
    question = excluded.question,
    marks = excluded.marks,
    section = excluded.section,
    topics = excluded.topics,
    source_pdf = excluded.source_pdf,
    source_file = excluded.source_file,
    source_page = excluded.source_page,
    needs_review = excluded.needs_review,
    updated_at = CURRENT_TIMESTAMP

"""


# ============================================================
# CREATE DATABASE STRUCTURE
# ============================================================

def create_tables():

    print("\nCreating PYQ tables...")

    with connection.cursor() as cursor:

        # SQLite accepts multiple statements through executescript.
        cursor.connection.executescript(CREATE_TABLES_SQL)

    print("✓ pyq_questions table ready")
    print("✓ indexes ready")


# ============================================================
# LOAD JSON
# ============================================================

def load_questions():

    if not JSON_FILE.exists():

        raise FileNotFoundError(
            f"\nquestions.json not found:\n{JSON_FILE}\n"
        )

    print(f"\nReading:\n{JSON_FILE}")

    with open(JSON_FILE, "r", encoding="utf-8") as file:

        data = json.load(file)

    # --------------------------------------------------------
    # Support both:
    #
    # [
    #   {...},
    #   {...}
    # ]
    #
    # and:
    #
    # {
    #   "questions": [...]
    # }
    # --------------------------------------------------------

    if isinstance(data, list):

        questions = data

    elif isinstance(data, dict):

        questions = data.get("questions", [])

    else:

        raise ValueError(
            "Invalid JSON format. Expected a list or "
            "{'questions': [...]}"
        )

    print(f"✓ Found {len(questions)} questions")

    return questions


# ============================================================
# NORMALIZE QUESTION
# ============================================================

def normalize_question(q):

    topics = q.get("topics", [])

    if topics is None:
        topics = []

    if not isinstance(topics, list):
        topics = [str(topics)]

    # Convert boolean to SQLite integer
    needs_review = q.get("needs_review", False)

    if isinstance(needs_review, str):

        needs_review = needs_review.lower() in (
            "true",
            "1",
            "yes"
        )

    needs_review = 1 if needs_review else 0

    return [
        q.get("year"),
        q.get("stage"),
        q.get("paper"),

        q.get("question_number"),
        q.get("question"),

        q.get("marks"),
        q.get("section"),

        json.dumps(
            topics,
            ensure_ascii=False
        ),

        q.get("source_pdf"),
        q.get("source_file"),
        q.get("source_page"),

        needs_review,
    ]


# ============================================================
# VALIDATE QUESTION
# ============================================================

def validate_question(q):

    required_fields = [
        "year",
        "stage",
        "paper",
        "question_number",
        "question",
    ]

    missing = [
        field
        for field in required_fields
        if q.get(field) is None
    ]

    return missing


# ============================================================
# INSERT QUESTIONS
# ============================================================

def insert_questions(questions):

    inserted = 0
    skipped = 0
    errors = []

    print("\nImporting questions...")

    with transaction.atomic():

        with connection.cursor() as cursor:

            for index, question in enumerate(
                questions,
                start=1
            ):

                missing = validate_question(question)

                if missing:

                    skipped += 1

                    errors.append({
                        "index": index,
                        "missing": missing,
                        "question": question,
                    })

                    continue

                try:

                    cursor.execute(
                        INSERT_SQL,
                        normalize_question(question)
                    )

                    inserted += 1

                except Exception as e:

                    skipped += 1

                    errors.append({
                        "index": index,
                        "error": str(e),
                        "question": question,
                    })

    print(f"\n✓ Imported/updated: {inserted}")
    print(f"✓ Skipped:           {skipped}")

    return errors


# ============================================================
# DATABASE SUMMARY
# ============================================================

def print_summary():

    print("\n" + "=" * 60)
    print("DATABASE SUMMARY")
    print("=" * 60)

    with connection.cursor() as cursor:

        cursor.execute(
            "SELECT COUNT(*) FROM pyq_questions"
        )

        total = cursor.fetchone()[0]

        print(f"\nTotal questions: {total}")

        # ----------------------------------------------------
        # By year
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT year, COUNT(*)
            FROM pyq_questions
            GROUP BY year
            ORDER BY year
            """
        )

        print("\nQuestions by year:")

        for year, count in cursor.fetchall():

            print(f"  {year}: {count}")

        # ----------------------------------------------------
        # By paper
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT paper_code, COUNT(*)
            FROM pyq_questions
            GROUP BY paper_code
            ORDER BY paper_code
            """
        )

        print("\nQuestions by paper:")

        for paper, count in cursor.fetchall():

            print(f"  {paper}: {count}")

        # ----------------------------------------------------
        # Review
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM pyq_questions
            WHERE needs_review = 1
            """
        )

        review = cursor.fetchone()[0]

        print(f"\nNeeds review: {review}")

    print("\n" + "=" * 60)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("UPSC PYQ DATABASE IMPORT")
    print("=" * 60)

    try:

        # 1. Create tables
        create_tables()

        # 2. Load JSON
        questions = load_questions()

        # 3. Insert questions
        errors = insert_questions(questions)

        # 4. Print summary
        print_summary()

        # 5. Save import errors
        if errors:

            error_file = (
                Path.home()
                / "upsc_pyq_extracted"
                / "questions"
                / "import_errors.json"
            )

            with open(
                error_file,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    errors,
                    file,
                    indent=2,
                    ensure_ascii=False
                )

            print(
                f"\n⚠ Import errors saved to:\n"
                f"{error_file}"
            )

        else:

            print("\n✓ No import errors.")

        print("\n✓ PYQ database setup complete.")

    except Exception as e:

        print("\n❌ ERROR:")
        print(e)

        raise


if __name__ == "__main__":
    main()