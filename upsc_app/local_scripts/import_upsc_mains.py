#!/usr/bin/env python3

"""
UPSC CSE Mains PYQ PDF -> JSON extractor

Supported papers:
    ESSAY
    GS1
    GS2
    GS3
    GS4
    SOCIOLOGY1
    SOCIOLOGY2

Output:
    output/
    └── json/
        ├── all.json
        ├── essay.json
        ├── gs1.json
        ├── gs2.json
        ├── gs3.json
        ├── gs4.json
        ├── sociology1.json
        └── sociology2.json

Requirements:
    pip install pymupdf
"""

from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import json
import re


# ============================================================
# PAPER DETECTION
# ============================================================

PAPER_NAMES = {
    "ESSAY": "Essay",
    "GS1": "General Studies Paper I",
    "GS2": "General Studies Paper II",
    "GS3": "General Studies Paper III",
    "GS4": "General Studies Paper IV",
    "SOCIOLOGY1": "Sociology Paper I",
    "SOCIOLOGY2": "Sociology Paper II",
}


def detect_paper(filename):
    """
    Detect paper from filename.

    Examples:
        GS1 mains 2024.pdf
        GS2 mains 2023.pdf
        SOCIOLOGY1 mains 2024.pdf
        Sociology Paper II 2024.pdf
        ESSAY mains 2025.pdf
    """

    name = filename.upper()

    # Sociology first because it may contain numbers.
    if re.search(
        r"SOCIOLOGY[\s_-]*(?:PAPER[\s_-]*)?(?:2|II)\b",
        name,
    ):
        return "SOCIOLOGY2"

    if re.search(
        r"SOCIOLOGY[\s_-]*(?:PAPER[\s_-]*)?(?:1|I)\b",
        name,
    ):
        return "SOCIOLOGY1"

    if re.search(r"\bESSAY\b", name):
        return "ESSAY"

    if re.search(r"\bGS[\s_-]*1\b", name):
        return "GS1"

    if re.search(r"\bGS[\s_-]*2\b", name):
        return "GS2"

    if re.search(r"\bGS[\s_-]*3\b", name):
        return "GS3"

    if re.search(r"\bGS[\s_-]*4\b", name):
        return "GS4"

    # Some files may use "GENERAL STUDIES PAPER I"
    if re.search(r"GENERAL\s+STUDIES.*\bPAPER\b.*\bI\b", name):
        return "GS1"

    if re.search(r"GENERAL\s+STUDIES.*\bPAPER\b.*\bII\b", name):
        return "GS2"

    if re.search(r"GENERAL\s+STUDIES.*\bPAPER\b.*\bIII\b", name):
        return "GS3"

    if re.search(r"GENERAL\s+STUDIES.*\bPAPER\b.*\bIV\b", name):
        return "GS4"

    return None


# ============================================================
# YEAR DETECTION
# ============================================================

def detect_year(filename, full_text):
    """
    Detect year from filename first, then PDF text.
    """

    match = re.search(
        r"\b(20(?:1[3-9]|2[0-9]))\b",
        filename,
    )

    if match:
        return int(match.group(1))

    match = re.search(
        r"\b(20(?:1[3-9]|2[0-9]))\b",
        full_text[:5000],
    )

    if match:
        return int(match.group(1))

    return None


# ============================================================
# TEXT CLEANING
# ============================================================

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def remove_hindi(text):
    """
    Remove Hindi/Devanagari characters.

    This is important because UPSC PDFs are often bilingual.
    """

    text = DEVANAGARI_RE.sub(" ", text)

    # Remove excessive spaces created by Hindi removal.
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def clean_line(line):
    line = line.replace("\r", " ")
    line = remove_hindi(line)

    # Normalize whitespace.
    line = re.sub(r"\s+", " ", line)

    return line.strip()


# ============================================================
# PDF EXTRACTION
# ============================================================

def extract_pdf(path):
    """
    Extract English text page-by-page.

    Returns:
        [
            {
                "page": 1,
                "text": "..."
            },
            ...
        ]
    """

    try:
        import fitz
    except ImportError:
        raise SystemExit(
            "\nPyMuPDF is not installed.\n"
            "Install it using:\n\n"
            "    pip install pymupdf\n"
        )

    document = fitz.open(path)

    pages = []

    for page_number, page in enumerate(document, start=1):

        text = page.get_text("text")

        text = remove_hindi(text)

        pages.append(
            {
                "page": page_number,
                "text": text,
            }
        )

    document.close()

    return pages


# ============================================================
# NOISE FILTER
# ============================================================

NOISE_PATTERNS = [
    r"^\s*page\s+\d+\s*$",
    r"^\s*\d+\s*/\s*\d+\s*$",
    r"^\s*union public service commission",
    r"^\s*upsc",
    r"^\s*civil services examination",
    r"^\s*civil services \(main\)",
]


def is_noise(line):
    if not line:
        return True

    for pattern in NOISE_PATTERNS:
        if re.search(pattern, line, re.I):
            return True

    return False


# ============================================================
# QUESTION DETECTION
# ============================================================

QUESTION_RE = re.compile(
    r"^\s*(\d{1,2})\s*[\.\)]\s+(.*)"
)


def is_question_start(line):
    match = QUESTION_RE.match(line)

    if not match:
        return False

    number = int(match.group(1))

    # UPSC questions normally fall in this range.
    return 1 <= number <= 40


def question_number(line):
    match = QUESTION_RE.match(line)

    if not match:
        return None

    return int(match.group(1))


def question_text_from_line(line):
    match = QUESTION_RE.match(line)

    if not match:
        return line

    return match.group(2).strip()


# ============================================================
# METADATA
# ============================================================

WORD_LIMIT_RE = re.compile(
    r"(?:answer\s+in\s+)?"
    r"(\d{2,4})"
    r"\s+words?",
    re.I,
)


MARKS_RE = re.compile(
    r"\b(10|15|20)\b"
)


def extract_metadata(text):
    """
    Extract:

        word_limit
        marks

    Examples:

        (Answer in 150 words) 10
        (Answer in 250 words) 15
        Answer in 150 words 10
    """

    compact = re.sub(r"\s+", " ", text)

    word_limit = None
    marks = None

    word_match = WORD_LIMIT_RE.search(compact)

    if word_match:
        word_limit = int(word_match.group(1))

        # Look after word-limit text for marks.
        remaining = compact[word_match.end():word_match.end() + 80]

        marks_match = MARKS_RE.search(remaining)

        if marks_match:
            marks = int(marks_match.group(1))

    return word_limit, marks


# ============================================================
# REMOVE ANSWER METADATA FROM QUESTION
# ============================================================

def clean_question_text(text):
    """
    Remove:

        (Answer in 150 words) 10
        (Answer in 250 words) 15

    from the actual question.
    """

    # Remove "(Answer in 150 words) 10"
    text = re.sub(
        r"\(?\s*answer\s+in\s+\d{2,4}\s+words?\s*\)?"
        r"\s*(?:10|15|20)?",
        " ",
        text,
        flags=re.I,
    )

    # Remove remaining "150 words 10" patterns.
    text = re.sub(
        r"\b\d{2,4}\s+words?\b\s*(?:10|15|20)?",
        " ",
        text,
        flags=re.I,
    )

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip(" -:;,")


# ============================================================
# SECTION DETECTION
# ============================================================

SECTION_RE = re.compile(
    r"^\s*(?:section|sect\.?)\s*[-:]?\s*([A-D])\b",
    re.I,
)


def detect_section(lines):
    """
    Search the first few lines for:

        Section A
        SECTION-A
        Section B
    """

    for line in lines[:10]:

        match = SECTION_RE.match(line)

        if match:
            return match.group(1).upper()

    return None


# ============================================================
# SUBQUESTION DETECTION
# ============================================================

SUBQUESTION_RE = re.compile(
    r"^\s*[\(\[]?([a-hA-H])[\)\].:\-]\s+(.*)"
)


def detect_subquestions(lines):
    """
    Detect:

        (a) ...
        (b) ...
        a. ...
        b. ...

    Returns:

        [
            {
                "label": "a",
                "text": "..."
            }
        ]
    """

    subquestions = []

    current = None

    for line in lines:

        match = SUBQUESTION_RE.match(line)

        if match:

            if current:
                subquestions.append(current)

            current = {
                "label": match.group(1).lower(),
                "text": match.group(2).strip(),
            }

        elif current:

            current["text"] += " " + line

    if current:
        subquestions.append(current)

    return subquestions


# ============================================================
# SPLIT INTO QUESTIONS
# ============================================================

def split_questions(pages):
    """
    Convert PDF pages into question blocks.

    Each block contains:

        question_number
        lines
        source_page
    """

    questions = []

    current = None

    for page in pages:

        page_number = page["page"]

        lines = page["text"].splitlines()

        for raw_line in lines:

            line = clean_line(raw_line)

            if is_noise(line):
                continue

            if not line:
                continue

            if is_question_start(line):

                if current:

                    questions.append(current)

                current = {
                    "question_number": question_number(line),
                    "lines": [
                        question_text_from_line(line)
                    ],
                    "source_page": page_number,
                }

            elif current:

                current["lines"].append(line)

    if current:
        questions.append(current)

    return questions


# ============================================================
# ESSAY PARSER
# ============================================================

def parse_essay_question(block, year, source_pdf):
    """
    Essay has a different structure from GS/Sociology.

    Standard UPSC essay paper:
        8 topics
        choose one from each pair
        1000-1200 words
        125 marks
    """

    text = " ".join(block["lines"])

    text = clean_question_text(text)

    if len(text) < 10:
        return None

    return {
        "year": year,
        "paper_code": "ESSAY",
        "paper_name": PAPER_NAMES["ESSAY"],
        "section": None,
        "question_number": block["question_number"],
        "sub_question": None,
        "question": text,
        "marks": 125,
        "word_limit": "1000-1200",
        "word_limit_min": 1000,
        "word_limit_max": 1200,
        "source_pdf": source_pdf,
        "source_page": block["source_page"],
        "needs_review": False,
        "review_reason": None,
    }


# ============================================================
# GENERAL PAPER PARSER
# ============================================================

def parse_general_question(block, year, paper_code, source_pdf):

    lines = block["lines"]

    full_text = " ".join(lines)

    word_limit, marks = extract_metadata(full_text)

    section = detect_section(lines)

    question_text = clean_question_text(full_text)

    review_reasons = []

    if marks is None:
        review_reasons.append("marks_not_detected")

    if word_limit is None:
        review_reasons.append("word_limit_not_detected")

    # Detect subquestions.
    subquestions = detect_subquestions(lines)

    # --------------------------------------------------------
    # Parent question
    # --------------------------------------------------------

    record = {
        "year": year,
        "paper_code": paper_code,
        "paper_name": PAPER_NAMES[paper_code],
        "section": section,
        "question_number": block["question_number"],
        "sub_question": None,
        "question": question_text,
        "marks": marks,
        "word_limit": word_limit,
        "word_limit_min": None,
        "word_limit_max": None,
        "source_pdf": source_pdf,
        "source_page": block["source_page"],
        "needs_review": bool(review_reasons),
        "review_reason": (
            ", ".join(review_reasons)
            if review_reasons
            else None
        ),
    }

    return record


# ============================================================
# PARSE ONE PDF
# ============================================================

def parse_pdf(path):

    paper_code = detect_paper(path.name)

    if not paper_code:
        return []

    pages = extract_pdf(path)

    full_text = "\n".join(
        page["text"]
        for page in pages
    )

    year = detect_year(
        path.name,
        full_text,
    )

    if not year:
        print(
            f"WARNING: Could not determine year: {path}"
        )
        return []

    blocks = split_questions(pages)

    records = []

    for block in blocks:

        if paper_code == "ESSAY":

            record = parse_essay_question(
                block,
                year,
                path.name,
            )

        else:

            record = parse_general_question(
                block,
                year,
                paper_code,
                path.name,
            )

        if record:
            records.append(record)

    return records


# ============================================================
# OUTPUT
# ============================================================

def save_json(records, output_directory):

    json_directory = (
        output_directory / "json"
    )

    json_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # all.json
    # --------------------------------------------------------

    all_file = (
        json_directory / "all.json"
    )

    with all_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            records,
            file,
            ensure_ascii=False,
            indent=2,
        )

    # --------------------------------------------------------
    # Individual paper files
    # --------------------------------------------------------

    by_paper = defaultdict(list)

    for record in records:

        by_paper[
            record["paper_code"]
        ].append(record)

    for paper_code in PAPER_NAMES:

        paper_records = by_paper.get(
            paper_code,
            [],
        )

        if not paper_records:
            continue

        file_path = (
            json_directory
            / f"{paper_code.lower()}.json"
        )

        with file_path.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                paper_records,
                file,
                ensure_ascii=False,
                indent=2,
            )


# ============================================================
# REPORT
# ============================================================

def save_report(
    records,
    processed_files,
    failed_files,
    output_directory,
):

    report = {

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "processed_files":
            len(processed_files),

        "failed_files":
            len(failed_files),

        "total_questions":
            len(records),

        "questions_needing_review":
            sum(
                r["needs_review"]
                for r in records
            ),

        "papers": {
            paper: sum(
                1
                for r in records
                if r["paper_code"] == paper
            )
            for paper in PAPER_NAMES
        },

        "failed": failed_files,
    }

    path = (
        output_directory
        / "report.json"
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Extract UPSC CSE Mains "
            "PYQs from PDFs into JSON."
        )
    )

    parser.add_argument(
        "--pdf-root",
        required=True,
        help=(
            "Root directory containing "
            "UPSC PYQ PDFs."
        ),
    )

    parser.add_argument(
        "--output-dir",
        default="~/upsc_pyq_extracted",
        help=(
            "Directory where JSON files "
            "will be created."
        ),
    )

    args = parser.parse_args()

    pdf_root = (
        Path(args.pdf_root)
        .expanduser()
        .resolve()
    )

    output_directory = (
        Path(args.output_dir)
        .expanduser()
        .resolve()
    )

    if not pdf_root.exists():

        raise SystemExit(
            f"\nPDF directory does not exist:\n"
            f"{pdf_root}\n"
        )

    # --------------------------------------------------------
    # Find PDFs recursively
    # --------------------------------------------------------

    pdf_files = sorted(
        pdf_root.rglob("*.pdf")
    )

    print()
    print("=" * 70)
    print("UPSC CSE MAINS PYQ JSON EXTRACTOR")
    print("=" * 70)

    print(
        f"PDF root : {pdf_root}"
    )

    print(
        f"PDFs found: {len(pdf_files)}"
    )

    print("=" * 70)
    print()

    all_records = []

    processed_files = []

    failed_files = []

    # --------------------------------------------------------
    # Process PDFs
    # --------------------------------------------------------

    for index, pdf in enumerate(
        pdf_files,
        start=1,
    ):

        paper_code = detect_paper(
            pdf.name
        )

        if not paper_code:

            print(
                f"[SKIP] {pdf.name}"
            )

            continue

        print(
            f"[{index}/{len(pdf_files)}] "
            f"{paper_code:<12} "
            f"{pdf.name}"
        )

        try:

            records = parse_pdf(pdf)

            all_records.extend(
                records
            )

            processed_files.append(
                str(pdf)
            )

            print(
                f"       -> "
                f"{len(records)} questions"
            )

        except Exception as error:

            print(
                f"       ERROR: {error}"
            )

            failed_files.append(
                {
                    "file": str(pdf),
                    "error": str(error),
                }
            )

    # --------------------------------------------------------
    # Stable sorting
    # --------------------------------------------------------

    all_records.sort(
        key=lambda record: (
            record["year"],
            record["paper_code"],
            record["question_number"],
        )
    )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        all_records,
        output_directory,
    )

    save_report(
        all_records,
        processed_files,
        failed_files,
        output_directory,
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)

    print(
        f"Questions extracted : "
        f"{len(all_records)}"
    )

    print(
        f"Needs review        : "
        f"{sum(r['needs_review'] for r in all_records)}"
    )

    print(
        f"Failed PDFs         : "
        f"{len(failed_files)}"
    )

    print()
    print("JSON files:")

    json_directory = (
        output_directory / "json"
    )

    for file in sorted(
        json_directory.glob("*.json")
    ):

        print(
            f"  {file}"
        )

    print()
    print(
        f"Report: "
        f"{output_directory / 'report.json'}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()