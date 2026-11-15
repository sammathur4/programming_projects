"""
Import the Opencode UPSC plan CSVs into the three question-bank tables.

    python manage.py import_question_bank            # import
    python manage.py import_question_bank --dry-run  # validate only

Sources (fixed paths):
    /home/saksham/Downloads/Opencode_upsc_plan - Prelims.csv
    /home/saksham/Downloads/Opencode_upsc_plan - CSAT.csv
    /home/saksham/Downloads/Opencode_upsc_plan - Mains + Sociology.csv
"""

import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from syllabus.models import PrelimsGsQuestion, CsatQuestion, MainsQuestion

DOWNLOADS = Path("/home/saksham/Downloads")
SOURCES = {
    "prelims": DOWNLOADS / "Opencode_upsc_plan - Prelims.csv",
    "csat": DOWNLOADS / "Opencode_upsc_plan - CSAT.csv",
    "mains": DOWNLOADS / "Opencode_upsc_plan - Mains + Sociology.csv",
}


def read_csv(path):
    """The CSVs carry a blank line and a comma-only line before the header."""
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        rows = list(csv.reader(handle))
    header_index = next(
        i for i, row in enumerate(rows) if row and row[0].strip() == "id"
    )
    header = [cell.strip() for cell in rows[header_index]]
    records = []
    for row in rows[header_index + 1 :]:
        if not any(cell.strip() for cell in row):
            continue
        records.append(
            {
                header[i]: (row[i].strip() if i < len(row) else "")
                for i in range(len(header))
            }
        )
    return records


def as_int(value):
    return int(value) if value else None


def as_float(value):
    return float(value) if value else None


def as_word_limit(value):
    """Essay rows carry '1000-1200 words'; keep the lower bound."""
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def build_prelims(records):
    questions = []
    for row in records:
        questions.append(
            PrelimsGsQuestion(
                question_id=as_int(row["question_id"]),
                year=as_int(row["year"]),
                paper=row["paper"] or "Prelims GS",
                section=row["section"],
                question=row["question"],
                option_a=row["option_a"],
                option_b=row["option_b"],
                option_c=row["option_c"],
                option_d=row["option_d"],
                correct_answer=row["correct_answer"],
                explanation=row["explanation"],
                motivation=row["motivation"],
                difficulty=row["difficulty"],
                nature=row["nature"],
                source=row["source"],
                source_type=row["source_type"],
                tags=row["tags"],
                relevance=row["relevance"],
                current_affairs_linkage=row["current_affairs_linkage"],
                why_correct=row["why_correct"],
                marks=as_float(row["marks"]),
                negative_marks=as_float(row["negative_marks"]),
                question_key=f"prelims-gs-{row['year']}-{row['question_id']}",
            )
        )
    return questions


def build_csat(records):
    questions = []
    for row in records:
        questions.append(
            CsatQuestion(
                question_id=as_int(row["question_id"]),
                year=as_int(row["year"]),
                paper=row["paper"] or "Prelims CSAT",
                section=row["section"],
                question=row["question"],
                option_a=row["option_a"],
                option_b=row["option_b"],
                option_c=row["option_c"],
                option_d=row["option_d"],
                correct_answer=row["correct_answer"],
                explanation=row["explanation"],
                motivation=row["motivation"],
                difficulty=row["difficulty"],
                nature=row["nature"],
                source=row["source"],
                tags=row["tags"],
                marks=as_float(row["marks"]),
                negative_marks=as_float(row["negative_marks"]),
                question_key=f"csat-{row['year']}-{row['question_id']}",
            )
        )
    return questions


def build_mains(records):
    questions = []
    for row in records:
        questions.append(
            MainsQuestion(
                question_id=row["question_id"],
                year=as_int(row["year"]),
                paper=row["paper"],
                subject=row["subject"],
                question=row["question"],
                section=row["section"],
                marks=as_float(row["marks"]),
                max_word_limit=as_word_limit(row["max_word_limit"]),
                source_question_ids=row["source_question_ids"],
                source_file=row["source_file"],
                difficulty=row["difficulty"],
                nature=row["nature"],
                master_theme=row["master_theme"],
                syllabus_tags=row["syllabus_tags"],
                question_key=f"mains-{row['question_id']}",
            )
        )
    return questions


class Command(BaseCommand):
    help = "Import the Opencode UPSC plan CSVs into the question bank."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        builders = {
            "prelims": (PrelimsGsQuestion, build_prelims),
            "csat": (CsatQuestion, build_csat),
            "mains": (MainsQuestion, build_mains),
        }

        for name, (model, builder) in builders.items():
            path = SOURCES[name]
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"missing {path}"))
                return
            records = read_csv(path)
            questions = builder(records)

            keys = [question.question_key for question in questions]
            duplicate_keys = len(keys) - len(set(keys))
            empty_questions = sum(1 for question in questions if not question.question)
            self.stdout.write(
                f"{name}: {len(questions)} rows, "
                f"{duplicate_keys} duplicate keys, "
                f"{empty_questions} empty questions"
            )

            if options["dry_run"]:
                continue

            model.objects.all().delete()
            model.objects.bulk_create(questions, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f"{name}: imported"))

        if not options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("question bank updated"))
