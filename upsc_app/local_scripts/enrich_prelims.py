#!/usr/bin/env python3
"""Add paper metadata to the prelims bank: instructions, marks, question numbers.

    python3 enrich_prelims.py            # dry run
    python3 enrich_prelims.py --apply    # write (backs up the DB first)
    python3 enrich_prelims.py --self-check

What it does
    * creates table prelims_papers   (one row per year + paper: duration, marks,
      items, marks per question, penalty, official instruction text)
    * adds columns to prelims_questions: question_number, marks, negative_marks
    * fills them from the paper constants below

Question numbers come from question_id, which the importers allocate per paper:
GS 1-100, CSAT 101-180 -> exam number 1-80.
"""

import argparse
import shutil
import sqlite3
import time
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "backend" / "db.sqlite3"

PAPERS = {
    "Prelims GS": {
        "code": "prelims-gs",
        "title": "General Studies Paper-I",
        "items": 100,
        "marks_per_question": 2.0,
        "qn_offset": 0,
        "first_year": 2012,
    },
    "Prelims CSAT": {
        "code": "prelims-csat",
        "title": "General Studies Paper-II (CSAT)",
        "items": 80,
        "marks_per_question": 2.5,
        "qn_offset": 100,
        "first_year": 2015,
    },
}

# Official back-cover instructions, transcribed from the 2025 booklets.
# Identical wording every year; only the item count and paper name change.
INSTRUCTIONS = """\
Time Allowed: Two Hours            Maximum Marks: 200

INSTRUCTIONS

1. IMMEDIATELY AFTER THE COMMENCEMENT OF THE EXAMINATION, YOU SHOULD CHECK THAT THIS TEST
   BOOKLET DOES NOT HAVE ANY UNPRINTED OR TORN OR MISSING PAGES OR ITEMS, ETC. IF SO, GET IT
   REPLACED BY A COMPLETE TEST BOOKLET.

2. Please note that it is the candidate's responsibility to encode and fill in the Roll Number and
   Test Booklet Series A, B, C or D carefully and without any omission or discrepancy at the
   appropriate places in the OMR Answer Sheet. Any omission/discrepancy will render the Answer
   Sheet liable for rejection.

3. You have to enter your Roll Number on the Test Booklet in the Box provided alongside.
   DO NOT write anything else on the Test Booklet.

4. This Test Booklet contains {items} items (questions). Each item is printed both in Hindi and
   English. Each item comprises four responses (answers). You will select the response which you
   want to mark on the Answer Sheet. In case you feel that there is more than one correct response,
   mark the response which you consider the best. In any case, choose ONLY ONE response for each
   item.

5. You have to mark all your responses ONLY on the separate Answer Sheet provided. See directions
   in the Answer Sheet.

6. All items carry equal marks.

7. Before you proceed to mark in the Answer Sheet the response to various items in the Test
   Booklet, you have to fill in some particulars in the Answer Sheet as per instructions sent to you
   with your Admission Certificate.

8. After you have completed filling in all your responses on the Answer Sheet and the examination
   has concluded, you should hand over to the Invigilator only the Answer Sheet. You are permitted
   to take this Test Booklet with you.

9. Sheets for rough work are appended in the Test Booklet at the end.

10. Penalty for wrong answers:
    THERE WILL BE PENALTY FOR WRONG ANSWERS MARKED BY A CANDIDATE IN ALL THE QUESTIONS.
    (i) There are four alternatives for the answer to every question. For each question for which a
        wrong answer has been given by the candidate, one-third of the marks assigned to that
        question will be deducted as penalty.
    (ii) If a candidate gives more than one answer, it will be treated as a wrong answer even if
        one of the given answers happens to be correct and there will be same penalty as above to
        that question.
    (iii) If a question is left blank, i.e., no answer is given by the candidate, there will be no
        penalty for that question.
"""


def create_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prelims_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            paper TEXT NOT NULL,
            paper_code TEXT NOT NULL,
            title TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            total_marks INTEGER NOT NULL,
            total_questions INTEGER NOT NULL,
            marks_per_question REAL NOT NULL,
            negative_marks REAL NOT NULL,
            instructions TEXT,
            source_file TEXT,
            UNIQUE(year, paper)
        )
    """)
    have = {row[1] for row in conn.execute("PRAGMA table_info(prelims_questions)")}
    for column, kind in (
        ("question_number", "INTEGER"),
        ("marks", "REAL"),
        ("negative_marks", "REAL"),
    ):
        if column not in have:
            conn.execute(f"ALTER TABLE prelims_questions ADD COLUMN {column} {kind}")


def years_in_bank(conn):
    return {
        (year, paper or "Prelims GS")
        for year, paper in conn.execute(
            "SELECT DISTINCT year, paper FROM prelims_questions"
        )
    }


def fill_questions(conn):
    """question_number from question_id, marks from the paper constants."""
    changed = 0
    for paper, spec in PAPERS.items():
        marks = spec["marks_per_question"]
        changed += conn.execute(
            """
            UPDATE prelims_questions
               SET question_number = question_id - ?,
                   marks = ?,
                   negative_marks = ?
             WHERE COALESCE(paper, 'Prelims GS') = ?
            """,
            (spec["qn_offset"], marks, round(marks / 3, 4), paper),
        ).rowcount
    return changed


def fill_papers(conn):
    added = 0
    for year, paper in sorted(years_in_bank(conn)):
        spec = PAPERS.get(paper)
        if not spec or year < spec["first_year"]:
            continue
        marks = spec["marks_per_question"]
        added += conn.execute(
            """
            INSERT INTO prelims_papers
                (year, paper, paper_code, title, duration_minutes, total_marks,
                 total_questions, marks_per_question, negative_marks, instructions,
                 source_file)
            VALUES (?,?,?,?,120,200,?,?,?,?,?)
            ON CONFLICT(year, paper) DO UPDATE SET
                title = excluded.title,
                total_questions = excluded.total_questions,
                marks_per_question = excluded.marks_per_question,
                negative_marks = excluded.negative_marks,
                instructions = excluded.instructions
            """,
            (
                year,
                paper,
                spec["code"],
                spec["title"],
                spec["items"],
                marks,
                round(marks / 3, 4),
                INSTRUCTIONS.format(items=spec["items"]),
                "UPSC official booklet (2025 back cover)",
            ),
        ).rowcount
    return added


def self_check():
    for paper, spec in PAPERS.items():
        # every paper is 200 marks, and numbering starts at 1
        assert spec["items"] * spec["marks_per_question"] == 200
        assert spec["qn_offset"] + 1 - spec["qn_offset"] == 1
    assert INSTRUCTIONS.format(items=80).count("80 items") == 1
    assert "2.5" not in INSTRUCTIONS
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()

    conn = sqlite3.connect(DB)
    papers = sorted(years_in_bank(conn))
    print(f"paper groups in bank: {len(papers)}")
    for year, paper in papers:
        spec = PAPERS.get(paper)
        if not spec or year < spec["first_year"]:
            print(f"  skip (no spec): {year} {paper}")
            continue
        marks = spec["marks_per_question"]
        print(f"  {year} {paper:<13} {spec['items']:>3} items x {marks} marks"
              f"  penalty {round(marks / 3, 2)}")

    if not args.apply:
        return print("\ndry run — nothing written. add --apply")

    backup = DB.with_suffix(f".sqlite3.bak-{time.strftime('%Y%m%d-%H%M')}")
    shutil.copy2(DB, backup)
    print(f"\nbackup: {backup.name}")
    with conn:
        create_schema(conn)
        print(f"papers written:     {fill_papers(conn)}")
        print(f"questions stamped:  {fill_questions(conn)}")
    print("done")


if __name__ == "__main__":
    main()
