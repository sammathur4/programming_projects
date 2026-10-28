#!/usr/bin/env python3

import argparse
import json
import re
import sqlite3
from pathlib import Path


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS prelims_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    question_id INTEGER NOT NULL,
    year INTEGER NOT NULL,

    section TEXT,
    question TEXT,

    option_a TEXT,
    option_b TEXT,
    option_c TEXT,
    option_d TEXT,

    correct_answer TEXT,

    explanation TEXT,
    motivation TEXT,

    difficulty TEXT,
    nature TEXT,

    source TEXT,
    source_type TEXT,

    source_file TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(year, question_id)
);
"""


INSERT_SQL = """
INSERT INTO prelims_questions (
    question_id,
    year,
    section,
    question,
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
    source_file
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

ON CONFLICT(year, question_id)
DO UPDATE SET
    section = excluded.section,
    question = excluded.question,
    option_a = excluded.option_a,
    option_b = excluded.option_b,
    option_c = excluded.option_c,
    option_d = excluded.option_d,
    correct_answer = excluded.correct_answer,
    explanation = excluded.explanation,
    motivation = excluded.motivation,
    difficulty = excluded.difficulty,
    nature = excluded.nature,
    source = excluded.source,
    source_type = excluded.source_type,
    source_file = excluded.source_file,
    updated_at = CURRENT_TIMESTAMP;
"""


def clean_text(value):
    """Clean whitespace from text fields."""

    if value is None:
        return None

    value = str(value)

    value = value.replace("\r\n", "\n")
    value = value.replace("\r", "\n")

    # Remove excessive spaces/tabs
    value = re.sub(r"[ \t]+", " ", value)

    # Remove excessive blank lines
    value = re.sub(r"\n\s*\n+", "\n\n", value)

    return value.strip()


def normalize_answer(answer):
    """
    Convert answer to lowercase option letter.

    Examples:
        A     -> a
        B     -> b
        (C)   -> c
        Option D -> d
    """

    if answer is None:
        return None

    answer = str(answer).strip().lower()

    match = re.search(r"\b([abcd])\b", answer)

    if match:
        return match.group(1)

    # Handle "(a)", "(b)" etc.
    match = re.search(r"\(([abcd])\)", answer)

    if match:
        return match.group(1)

    return answer


def get_year_from_filename(file_path):
    filename = file_path.name

    # Extract any 4-digit year starting with 20 from the filename.
    match = re.search(r"(20\d{2})", filename)

    if not match:
        raise ValueError(
            f"Could not determine year from filename: {filename}"
        )

    year = int(match.group(1))

    if not 2010 <= year <= 2030:
        raise ValueError(
            f"Invalid UPSC year {year} in filename: {filename}"
        )

    return year


def load_json(file_path):
    """Load JSON file."""

    with open(file_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    # Support:
    # [
    #   {...},
    #   {...}
    # ]

    if isinstance(data, list):
        return data

    # Also support:
    # {
    #   ...
    # }

    if isinstance(data, dict):
        return [data]

    raise ValueError(
        f"Invalid JSON structure in {file_path}"
    )


def create_table(connection):
    """Create table and indexes."""

    connection.execute(CREATE_TABLE_SQL)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_prelims_questions_year
        ON prelims_questions(year)
    """)

    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_prelims_questions_section
        ON prelims_questions(section)
    """)

    connection.commit()


def insert_question(
    connection,
    item,
    year,
    source_file
):
    """Insert or update one question."""

    options = item.get("options") or {}

    question_id = item.get("id")

    if question_id is None:
        raise ValueError(
            f"Missing question id in {source_file}"
        )

    values = (
        int(question_id),
        year,

        clean_text(item.get("section")),
        clean_text(item.get("question")),

        clean_text(options.get("a")),
        clean_text(options.get("b")),
        clean_text(options.get("c")),
        clean_text(options.get("d")),

        normalize_answer(item.get("answer")),

        clean_text(item.get("explanation")),
        clean_text(item.get("motivation")),

        clean_text(item.get("difficulty")),
        clean_text(item.get("nature")),

        clean_text(item.get("source")),
        clean_text(item.get("source_type")),

        source_file,
    )

    connection.execute(INSERT_SQL, values)


def import_files(json_root, database):
    """Import every JSON file recursively."""

    json_root = Path(json_root)

    if not json_root.exists():
        raise FileNotFoundError(
            f"Directory does not exist: {json_root}"
        )

    json_files = sorted(
        json_root.rglob("*.json")
    )

    if not json_files:
        print("No JSON files found.")
        return

    print("=" * 70)
    print("UPSC PRELIMS JSON IMPORT")
    print("=" * 70)

    print(f"JSON directory : {json_root}")
    print(f"Database       : {database}")
    print(f"JSON files     : {len(json_files)}")
    print()

    connection = sqlite3.connect(database)

    try:
        create_table(connection)

        total_questions = 0
        total_files = 0
        failed_files = 0

        for file_path in json_files:

            try:
                # IMPORTANT:
                # Year comes ONLY from filename
                year = get_year_from_filename(file_path)

                questions = load_json(file_path)

                file_count = 0

                for item in questions:

                    if not isinstance(item, dict):
                        print(
                            f"WARNING: Skipping invalid item "
                            f"in {file_path.name}"
                        )
                        continue

                    insert_question(
                        connection=connection,
                        item=item,
                        year=year,
                        source_file=file_path.name,
                    )

                    file_count += 1

                connection.commit()

                total_questions += file_count
                total_files += 1

                print(
                    f"✓ {file_path.name:<35} "
                    f"Year: {year} | "
                    f"Questions: {file_count}"
                )

            except Exception as error:

                connection.rollback()

                failed_files += 1

                print(
                    f"✗ {file_path.name:<35} "
                    f"ERROR: {error}"
                )

        print()
        print("-" * 70)

        cursor = connection.execute(
            "SELECT COUNT(*) FROM prelims_questions"
        )

        db_count = cursor.fetchone()[0]

        print(f"Files processed : {total_files}")
        print(f"Files failed    : {failed_files}")
        print(f"Questions read  : {total_questions}")
        print(f"Questions in DB : {db_count}")

        print()
        print("Questions by year:")
        print()

        cursor = connection.execute("""
            SELECT year, COUNT(*)
            FROM prelims_questions
            GROUP BY year
            ORDER BY year
        """)

        for year, count in cursor.fetchall():
            print(f"  {year}: {count}")

        print("=" * 70)

    finally:
        connection.close()


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Import UPSC Prelims JSON files into SQLite"
        )
    )

    parser.add_argument(
        "--json-root",
        required=True,
        help="Directory containing JSON files"
    )

    parser.add_argument(
        "--database",
        default="upsc_pyq.sqlite3",
        help="SQLite database path"
    )

    args = parser.parse_args()

    import_files(
        json_root=args.json_root,
        database=args.database,
    )


if __name__ == "__main__":
    main()