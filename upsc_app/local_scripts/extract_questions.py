#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image


# ============================================================
# CONFIG
# ============================================================

DEFAULT_WORD_LIMIT = None
DEFAULT_MARKS = None


# ============================================================
# PDF -> TEXT
# ============================================================

def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF.

    First tries native PDF text extraction.
    If the PDF is scanned/image-based, OCR is used.
    """

    doc = fitz.open(pdf_path)

    pages = []

    for page_number, page in enumerate(doc, start=1):

        text = page.get_text("text").strip()

        # If enough text exists, use it.
        if len(text) >= 100:
            pages.append({
                "page": page_number,
                "text": text
            })
            continue

        # Otherwise OCR the page.
        print(f"[OCR] Page {page_number}")

        pix = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False
        )

        image = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples
        )

        # English only.
        ocr_text = pytesseract.image_to_string(
            image,
            lang="eng"
        )

        pages.append({
            "page": page_number,
            "text": ocr_text
        })

    doc.close()

    return pages


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text):
    if not text:
        return None

    # Normalize line endings.
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove repeated spaces/tabs.
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_question_text(text):
    """
    Clean OCR artefacts without aggressively changing
    the original wording.
    """

    text = clean_text(text)

    if not text:
        return None

    # Join words split by line breaks.
    text = re.sub(r"(?<![.!?:])\n(?=[a-z])", " ", text)

    # Remaining line breaks inside questions -> spaces.
    text = re.sub(r"\s*\n\s*", " ", text)

    # Normalize spaces.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# SECTION DETECTION
# ============================================================

SECTION_PATTERNS = [
    (r"\bSECTION[\s\-]*A\b", "Section A"),
    (r"\bSECTION[\s\-]*B\b", "Section B"),

    (r"\bHISTORY\b", "History"),
    (r"\bWORLD HISTORY\b", "World History"),
    (r"\bINDIAN SOCIETY\b", "Indian Society"),
    (r"\bGEOGRAPHY\b", "Geography"),
    (r"\bART\s*(?:AND|&)\s*CULTURE\b", "Art & Culture"),
    (r"\bECONOMICS\b", "Economics"),
    (r"\bPOLITY\b", "Polity"),
    (r"\bENVIRONMENT\b", "Environment"),
    (r"\bSCIENCE\s*(?:AND|&)\s*TECHNOLOGY\b", "Science & Technology"),
]


def detect_section(text, current_section=None):
    """
    Detect section/topic headings.

    Returns the detected section or keeps the
    previous section.
    """

    upper = text.upper()

    # Prefer longer/more specific headings.
    patterns = sorted(
        SECTION_PATTERNS,
        key=lambda x: len(x[0]),
        reverse=True
    )

    for pattern, section in patterns:
        if re.search(pattern, upper):
            return section

    return current_section


# ============================================================
# WORD LIMIT
# ============================================================

def detect_word_limit(text):
    """
    Detect word limits such as:

        150 words
        NOT MORE THAN 150 words
        about 1000-1200 words
        1000–1200 words each
    """

    if not text:
        return None

    # 1000-1200 words
    match = re.search(
        r"\b(\d{3,4})\s*[-–—]\s*(\d{3,4})\s*words?\b",
        text,
        flags=re.I
    )

    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # 150 words
    match = re.search(
        r"\b(?:not\s+more\s+than\s+)?(\d{2,4})\s*words?\b",
        text,
        flags=re.I
    )

    if match:
        return int(match.group(1))

    return None


# ============================================================
# MARKS
# ============================================================

def detect_question_marks(text):
    """
    Detect marks appearing at the end of a question.

    Examples:

        10
        10 marks
        20
        15
    """

    if not text:
        return None

    patterns = [
        r"\b(\d{1,3})\s*marks?\s*$",
        r"\s(\d{1,3})\s*$",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.I
        )

        if match:
            value = int(match.group(1))

            # Avoid treating random years as marks.
            if value <= 100:
                return value

    return None


# ============================================================
# QUESTION DETECTION
# ============================================================

QUESTION_START_RE = re.compile(
    r"(?:^|\n)\s*Q(?:uestion)?\.?\s*(\d{1,3})\s*[\.\):\-]?\s*",
    re.I
)


def split_questions(text):
    """
    Split a paper into numbered questions.

    Supports:

        Q1.
        Q.1
        Q 1
        Question 1.
        1.
    """

    matches = list(QUESTION_START_RE.finditer(text))

    # If Q1/Q2 style wasn't detected, try plain numbering.
    if not matches:

        plain_re = re.compile(
            r"(?:^|\n)\s*(\d{1,3})\s*[\.\)]\s+"
        )

        matches = list(plain_re.finditer(text))

    questions = []

    for index, match in enumerate(matches):

        start = match.end()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        question_number = int(match.group(1))

        question_text = text[start:end].strip()

        questions.append({
            "number": question_number,
            "text": question_text
        })

    return questions


# ============================================================
# REMOVE HINDI TRANSLATION
# ============================================================

def remove_hindi_lines(text):
    """
    The UPSC papers generally contain Hindi first and
    English immediately below it.

    This function removes lines containing Devanagari
    characters.

    English text is preserved.
    """

    if not text:
        return text

    lines = text.splitlines()

    english_lines = []

    for line in lines:

        # Remove lines containing Devanagari.
        if re.search(r"[\u0900-\u097F]", line):
            continue

        english_lines.append(line)

    return "\n".join(english_lines)


# ============================================================
# REMOVE QUESTION FOOTER MARKS
# ============================================================

def remove_trailing_marks(text):
    """
    Remove marks printed after a question.

    Example:

        ... Discuss. 10

    becomes:

        ... Discuss.
    """

    if not text:
        return text

    text = re.sub(
        r"\s+\b\d{1,2}\s*$",
        "",
        text
    )

    text = re.sub(
        r"\s+\b\d{1,2}\s*marks?\s*$",
        "",
        text,
        flags=re.I
    )

    return text.strip()


# ============================================================
# OPTIONS
# ============================================================

def extract_options(text):
    """
    Extract MCQ options if present.

    Example:

        (a) Option A
        (b) Option B
        (c) Option C
        (d) Option D
    """

    if not text:
        return None

    patterns = {
        "a": r"(?:^|\n)\s*\(?a\)?[\.\:\-]\s*(.*?)(?=\n\s*\(?b\)?[\.\:\-])",
        "b": r"(?:^|\n)\s*\(?b\)?[\.\:\-]\s*(.*?)(?=\n\s*\(?c\)?[\.\:\-])",
        "c": r"(?:^|\n)\s*\(?c\)?[\.\:\-]\s*(.*?)(?=\n\s*\(?d\)?[\.\:\-])",
        "d": r"(?:^|\n)\s*\(?d\)?[\.\:\-]\s*(.*?)(?=\n|$)",
    }

    options = {}

    for key, pattern in patterns.items():

        match = re.search(
            pattern,
            text,
            flags=re.I | re.S
        )

        if match:
            value = normalize_question_text(
                match.group(1)
            )

            if value:
                options[key] = value

    return options if options else None


# ============================================================
# QUESTION OBJECT
# ============================================================

def build_question(
    question_id,
    question_number,
    raw_text,
    section,
    default_marks=None,
    default_word_limit=None
):
    """
    Build the standard UPSC JSON object.
    """

    raw_text = remove_hindi_lines(raw_text)

    marks = detect_question_marks(raw_text)

    word_limit = detect_word_limit(raw_text)

    options = extract_options(raw_text)

    question_text = remove_trailing_marks(raw_text)

    # Remove options from the main question.
    if options:

        for key, value in options.items():
            question_text = re.sub(
                re.escape(value),
                "",
                question_text,
                flags=re.I
            )

    question_text = normalize_question_text(
        question_text
    )

    return {
        "id": question_id,
        "section": section,
        "question": question_text,
        "options": options,
        "answer": None,
        "explanation": None,
        "motivation": None,
        "difficulty": None,
        "nature": None,
        "marks": marks if marks is not None else default_marks,
        "word_limit": (
            word_limit
            if word_limit is not None
            else default_word_limit
        )
    }


# ============================================================
# MAIN PARSER
# ============================================================

def convert_pdf_to_json(
    pdf_path,
    output_path,
    default_marks=None,
    default_word_limit=None
):

    print(f"\nReading: {pdf_path}")

    pages = extract_text_from_pdf(pdf_path)

    all_text = ""

    for page in pages:
        all_text += "\n" + page["text"]

    all_text = clean_text(all_text)

    print(f"Extracted characters: {len(all_text)}")

    # --------------------------------------------------------
    # Detect paper-level word limit.
    # --------------------------------------------------------

    detected_word_limit = detect_word_limit(
        all_text
    )

    if detected_word_limit is not None:
        default_word_limit = detected_word_limit

    # --------------------------------------------------------
    # Split questions.
    # --------------------------------------------------------

    question_chunks = split_questions(
        all_text
    )

    print(
        f"Detected questions: {len(question_chunks)}"
    )

    # --------------------------------------------------------
    # Determine default marks.
    #
    # For GS papers, the paper usually says:
    #
    # 10 × 25 = 250
    #
    # and each question carries 10 marks.
    #
    # We don't blindly assume this unless supplied.
    # --------------------------------------------------------

    questions = []

    current_section = None

    for index, chunk in enumerate(question_chunks, start=1):

        raw_text = chunk["text"]

        current_section = detect_section(
            raw_text,
            current_section
        )

        # Fallback section.
        if current_section is None:
            current_section = "General Studies"

        item = build_question(
            question_id=index,
            question_number=chunk["number"],
            raw_text=raw_text,
            section=current_section,
            default_marks=default_marks,
            default_word_limit=default_word_limit
        )

        questions.append(item)

    # --------------------------------------------------------
    # Write JSON.
    # --------------------------------------------------------

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            questions,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"\nJSON written to: {output_path}"
    )

    print(
        f"Questions written: {len(questions)}"
    )


# ============================================================
# CLI
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description=(
            "Convert UPSC question paper PDF "
            "into structured JSON."
        )
    )

    parser.add_argument(
        "pdf",
        help="Input PDF"
    )

    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON file"
    )

    parser.add_argument(
        "--marks",
        type=int,
        default=None,
        help="Default marks per question"
    )

    parser.add_argument(
        "--word-limit",
        default=None,
        help=(
            "Default word limit. "
            "Examples: 150 or 1000-1200"
        )
    )

    args = parser.parse_args()

    pdf_path = Path(args.pdf)

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    # Automatically create output name.
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = pdf_path.with_suffix(
            ".json"
        )

    convert_pdf_to_json(
        pdf_path=pdf_path,
        output_path=output_path,
        default_marks=args.marks,
        default_word_limit=args.word_limit
    )


if __name__ == "__main__":
    main()