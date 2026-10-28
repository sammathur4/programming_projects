#!/usr/bin/env python3
"""
Load all UPSC Mains JSON files into SQLite with proper paper & year columns.
"""

import json
import sqlite3
import re
from pathlib import Path

# ---------- CONFIG ----------
DB_PATH = "/home/saksham/Documents/Codex/2026-09-16/linear-plugin-linear-openai-curated-remote-2/backend/db.sqlite3"

JSON_FOLDERS = [
    "/home/saksham/Documents/Codex/2026-09-16/linear-plugin-linear-openai-curated-remote-2/local_scripts/jsons/mains_json/essay_json",
    "/home/saksham/Documents/Codex/2026-09-16/linear-plugin-linear-openai-curated-remote-2/local_scripts/jsons/mains_json/gs_json",
    "/home/saksham/Documents/Codex/2026-09-16/linear-plugin-linear-openai-curated-remote-2/local_scripts/jsons/mains_json/lang_json",
    "/home/saksham/Documents/Codex/2026-09-16/linear-plugin-linear-openai-curated-remote-2/local_scripts/jsons/mains_json/socio_json",
]
# ----------------------------

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS mains_questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_id     INTEGER,
    paper           TEXT NOT NULL,
    year            INTEGER,
    file_name       TEXT,
    section         TEXT,
    question        TEXT NOT NULL,
    option_a        TEXT,
    option_b        TEXT,
    option_c        TEXT,
    option_d        TEXT,
    options_json    TEXT,
    answer          TEXT,
    explanation     TEXT,
    motivation      TEXT,
    difficulty      TEXT,
    nature          TEXT,
    source          TEXT,
    source_type     TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
"""

INSERT_SQL = """
INSERT INTO mains_questions (
    original_id, paper, year, file_name,
    section, question,
    option_a, option_b, option_c, option_d, options_json,
    answer, explanation, motivation,
    difficulty, nature, source, source_type
) VALUES (
    ?, ?, ?, ?,
    ?, ?,
    ?, ?, ?, ?, ?,
    ?, ?, ?,
    ?, ?, ?, ?
);
"""


def extract_paper_and_year(file_path: Path) -> tuple[str, int | None]:
    """
    Extract clean paper name and year from filename.
    Examples:
        gs_1_2023.json          → paper='gs1', year=2023
        essay_2024.json         → paper='essay', year=2024
        sociology_2_2021.json   → paper='sociology2', year=2021
        english_compulsory_2022 → paper='english', year=2022
        hindi_compulsory_2023   → paper='hindi', year=2023
    """
    name = file_path.stem.lower()

    # Extract year (4 consecutive digits)
    year_match = re.search(r'(20\d{2})', name)
    year = int(year_match.group(1)) if year_match else None

    # Remove year and clean the rest
    paper = re.sub(r'_?20\d{2}', '', name)
    paper = paper.replace('compulsory', '').strip('_')

    # Normalize paper names
    replacements = {
        'gs_1': 'gs1',
        'gs_2': 'gs2',
        'gs_3': 'gs3',
        'gs_4': 'gs4',
        'sociology_1': 'sociology1',
        'sociology_2': 'sociology2',
        'essay_1': 'essay',
    }
    for old, new in replacements.items():
        if paper.startswith(old):
            paper = new
            break

    return paper, year


def load_json(file_path: Path) -> list[dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError(f"JSON root must be a list or object → {file_path}")

    return data


def insert_records(conn: sqlite3.Connection, records: list[dict],
                   paper: str, year: int | None, file_name: str) -> int:
    cursor = conn.cursor()
    count = 0

    for rec in records:
        options = rec.get("options") or {}
        option_a = options.get("a") or options.get("A")
        option_b = options.get("b") or options.get("B")
        option_c = options.get("c") or options.get("C")
        option_d = options.get("d") or options.get("D")

        # Try common question field names
        question_text = (
            rec.get("question")
            or rec.get("ques")
            or rec.get("q")
            or rec.get("text")
            or ""
        )

        values = (
            rec.get("id"),
            paper,
            year,
            file_name,
            rec.get("section"),
            question_text,
            option_a,
            option_b,
            option_c,
            option_d,
            json.dumps(options, ensure_ascii=False) if options else None,
            rec.get("answer"),
            rec.get("explanation"),
            rec.get("motivation"),
            rec.get("difficulty"),
            rec.get("nature"),
            rec.get("source"),
            rec.get("source_type"),
        )
        cursor.execute(INSERT_SQL, values)
        count += 1

    return count


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(CREATE_TABLE_SQL)

    total_inserted = 0
    files_processed = 0

    for folder in JSON_FOLDERS:
        folder_path = Path(folder)
        if not folder_path.exists():
            print(f"⚠  Folder not found: {folder}")
            continue

        for json_file in sorted(folder_path.glob("*.json")):
            try:
                records = load_json(json_file)
                paper, year = extract_paper_and_year(json_file)

                inserted = insert_records(conn, records, paper, year, json_file.name)
                conn.commit()

                print(f"✓ {json_file.name:<35} → {inserted:3d} records | paper={paper:<12} year={year}")
                total_inserted += inserted
                files_processed += 1

            except Exception as e:
                print(f"✗ Failed: {json_file.name} → {e}")

    conn.close()

    print("\n" + "=" * 60)
    print(f"Finished!")
    print(f"Files processed : {files_processed}")
    print(f"Total records   : {total_inserted}")
    print(f"Database        : {DB_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()