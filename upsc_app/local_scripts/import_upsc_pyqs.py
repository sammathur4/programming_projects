#!/usr/bin/env python3
"""UPSC PYQ extractor - prelims options + compulsory language papers."""

import re
import json
import pymupdf
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

SOURCE_DIR = Path(
    "/media/saksham/80645C95645C9030/saksham/EXAM/01 upsc sociology 2027/02. PYQPs 2014-25"
)

OUTPUT_DIR = Path.home() / "upsc_pyq_extracted"

QUESTIONS_DIR = OUTPUT_DIR / "questions"

QUESTIONS_JSON = QUESTIONS_DIR / "questions.json"
REVIEW_JSON = QUESTIONS_DIR / "needs_review.json"

QUESTIONS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# PAPERS WE WANT
# ============================================================

PAPER_TYPES = {
    "gs1_prelims": {
        "stage": "prelims",
        "paper": "prelims-gs"
    },

    "gs2_prelims": {
        "stage": "prelims",
        "paper": "prelims-csat"
    },

    # UPSC Mains compulsory language papers
    "compulsory_english": {
        "stage": "mains",
        "paper": "compulsory-english"
    },

    "compulsory_hindi": {
        "stage": "mains",
        "paper": "compulsory-hindi"
    },

    "gs1_mains": {
        "stage": "mains",
        "paper": "gs1"
    },

    "gs2_mains": {
        "stage": "mains",
        "paper": "gs2"
    },

    "gs3_mains": {
        "stage": "mains",
        "paper": "gs3"
    },

    "gs4_mains": {
        "stage": "mains",
        "paper": "gs4"
    },

    "essay": {
        "stage": "mains",
        "paper": "essay"
    },

    "sociology_1": {
        "stage": "optional",
        "paper": "sociology-1"
    },

    "sociology_2": {
        "stage": "optional",
        "paper": "sociology-2"
    }
}


# ============================================================
# FILE CLASSIFICATION
# ============================================================

def extract_year(path):
    """
    Extract year from parent directory.

    Example:
        PYQPs 2024 -> 2024
    """

    match = re.search(
        r"20\d{2}",
        path.parent.name
    )

    if match:
        return int(match.group())

    # Fallback: search filename
    match = re.search(
        r"20\d{2}",
        path.name
    )

    if match:
        return int(match.group())

    return None


def classify_paper(filename):
    """
    Determine stage + paper from filename.

    Includes:
      - Prelims GS Paper I
      - Prelims CSAT / GS Paper II
      - Mains GS I-IV
      - Essay
      - Sociology Paper I-II
      - Compulsory English
      - Compulsory Hindi

    Important:
      Hindi translations inside English-language PDFs are NOT treated as
      separate questions. Only the paper itself is classified as Hindi when
      the filename clearly identifies it as the compulsory Hindi paper.
    """

    name = filename.lower()

    normalized = re.sub(r"[-_()]+", " ", name)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    # --------------------------------------------------------
    # Compulsory language papers
    # --------------------------------------------------------
    # Check these BEFORE generic "mains" matching.
    # The filename patterns intentionally cover common UPSC naming styles.

    if (
        re.search(r"\bcompulsory\b.*\benglish\b", normalized)
        or re.search(r"\benglish\b.*\bcompulsory\b", normalized)
        or re.search(r"\bcompulsory english\b", normalized)
        or re.search(r"\benglish language\b", normalized)
    ):
        return PAPER_TYPES["compulsory_english"]

    if (
        re.search(r"\bcompulsory\b.*\bhindi\b", normalized)
        or re.search(r"\bhindi\b.*\bcompulsory\b", normalized)
        or re.search(r"\bcompulsory hindi\b", normalized)
        or re.search(r"\bhindi language\b", normalized)
    ):
        return PAPER_TYPES["compulsory_hindi"]

    # --------------------------------------------------------
    # Sociology
    # --------------------------------------------------------

    if "sociology" in normalized:
        if re.search(
            r"paper\s*[- ]?i\b|sociology1\b|sociology i\b",
            normalized
        ):
            return PAPER_TYPES["sociology_1"]

        if re.search(
            r"paper\s*[- ]?ii\b|sociology2\b|sociology ii\b",
            normalized
        ):
            return PAPER_TYPES["sociology_2"]

    # --------------------------------------------------------
    # Essay
    # --------------------------------------------------------

    if "essay" in normalized:
        return PAPER_TYPES["essay"]

    # --------------------------------------------------------
    # CSAT
    # --------------------------------------------------------

    if "csat" in normalized:
        if "pre" in normalized or "prelims" in normalized:
            return PAPER_TYPES["gs2_prelims"]

    # --------------------------------------------------------
    # Prelims
    # --------------------------------------------------------

    if (
        "prelims" in normalized
        or re.search(r"\bpre\b", normalized)
    ):
        if re.search(r"gs\s*1|gs1|paper\s*i\b", normalized):
            return PAPER_TYPES["gs1_prelims"]

        if re.search(r"gs\s*2|gs2|paper\s*ii\b", normalized):
            return PAPER_TYPES["gs2_prelims"]

    # --------------------------------------------------------
    # Mains
    # --------------------------------------------------------

    if "mains" in normalized:
        if re.search(r"gs\s*1|gs1|general studies\s*i\b", normalized):
            return PAPER_TYPES["gs1_mains"]

        if re.search(r"gs\s*2|gs2|general studies\s*ii\b", normalized):
            return PAPER_TYPES["gs2_mains"]

        if re.search(r"gs\s*3|gs3|general studies\s*iii\b", normalized):
            return PAPER_TYPES["gs3_mains"]

        if re.search(r"gs\s*4|gs4|general studies\s*iv\b", normalized):
            return PAPER_TYPES["gs4_mains"]

    return None


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_pages(pdf_path):

    document = pymupdf.open(pdf_path)

    pages = []

    for page_number, page in enumerate(
        document,
        start=1
    ):

        text = page.get_text("text")

        text = text.replace(
            "\r",
            "\n"
        )

        # Normalize spaces
        text = re.sub(
            r"[ \t]+",
            " ",
            text
        )

        # Normalize blank lines
        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )

        pages.append({
            "page": page_number,
            "text": text.strip()
        })

    document.close()

    return pages


# ============================================================
# QUESTION NUMBER DETECTION
# ============================================================

QUESTION_PATTERN = re.compile(
    r"""
    (?m)
    ^
    \s*
    (?:
        Q(?:uestion)?\s*
    )?
    (
        \d{1,3}
    )
    [\.\):]
    \s+
    """,
    re.IGNORECASE | re.VERBOSE
)


def find_questions(text):

    matches = list(
        QUESTION_PATTERN.finditer(text)
    )

    questions = []

    for index, match in enumerate(matches):

        question_number = int(
            match.group(1)
        )

        start = match.end()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        question_text = text[start:end].strip()

        if not question_text:
            continue

        questions.append({
            "question_number": question_number,
            "question": question_text
        })

    return questions


# ============================================================
# MARKS DETECTION
# ============================================================

def detect_marks(question_text):

    # Common UPSC patterns
    patterns = [
        r"\b10\s*marks?\b",
        r"\b15\s*marks?\b",
        r"\b20\s*marks?\b"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            question_text,
            re.IGNORECASE
        )

        if match:

            number = re.search(
                r"\d+",
                match.group()
            )

            if number:
                return int(number.group())

    return None


# ============================================================
# SECTION DETECTION
# ============================================================

def detect_section(text):

    match = re.search(
        r"\bSECTION\s+([AB])\b",
        text,
        re.IGNORECASE
    )

    if match:
        return f"Section {match.group(1).upper()}"

    return None


# ============================================================
# TOPIC KEYWORDS
# ============================================================

TOPIC_KEYWORDS = {

    # --------------------------------------------------------
    # GS1
    # --------------------------------------------------------

    "culture": [
        "art",
        "architecture",
        "literature",
        "temple",
        "painting",
        "culture",
        "heritage"
    ],

    "modern-history": [
        "freedom struggle",
        "national movement",
        "gandhi",
        "congress",
        "british",
        "colonial",
        "independence",
        "revolt"
    ],

    "world-history": [
        "industrial revolution",
        "world war",
        "colonisation",
        "decolonisation",
        "communism",
        "capitalism",
        "socialism"
    ],

    "indian-society": [
        "indian society",
        "women",
        "population",
        "poverty",
        "urbanisation",
        "globalisation",
        "communalism",
        "regionalism",
        "secularism"
    ],

    "geography": [
        "earthquake",
        "tsunami",
        "cyclone",
        "volcano",
        "monsoon",
        "river",
        "mountain",
        "climate",
        "resource",
        "agriculture"
    ],

    # --------------------------------------------------------
    # GS2
    # --------------------------------------------------------

    "constitution": [
        "constitution",
        "constitutional",
        "fundamental rights",
        "directive principles",
        "amendment",
        "basic structure"
    ],

    "parliament": [
        "parliament",
        "rajya sabha",
        "lok sabha",
        "legislature",
        "speaker",
        "bill"
    ],

    "judiciary": [
        "supreme court",
        "high court",
        "judiciary",
        "judicial",
        "judge"
    ],

    "governance": [
        "governance",
        "transparency",
        "accountability",
        "e governance",
        "citizen charter"
    ],

    "social-justice": [
        "welfare",
        "social justice",
        "health",
        "education",
        "poverty",
        "vulnerable",
        "scheme"
    ],

    "international-relations": [
        "international",
        "bilateral",
        "neighbourhood",
        "united nations",
        "diaspora",
        "grouping"
    ],

    # --------------------------------------------------------
    # GS3
    # --------------------------------------------------------

    "economy": [
        "economy",
        "economic",
        "inflation",
        "employment",
        "growth",
        "budget",
        "tax",
        "investment",
        "banking"
    ],

    "agriculture": [
        "agriculture",
        "farmer",
        "crop",
        "irrigation",
        "msp",
        "subsidy",
        "food processing",
        "land reform"
    ],

    "science-technology": [
        "technology",
        "artificial intelligence",
        "space",
        "robotics",
        "biotechnology",
        "nanotechnology",
        "computer",
        "digital"
    ],

    "environment": [
        "environment",
        "biodiversity",
        "pollution",
        "climate change",
        "conservation",
        "forest",
        "ecosystem"
    ],

    "security": [
        "security",
        "cyber",
        "terrorism",
        "border",
        "extremism",
        "money laundering"
    ],

    # --------------------------------------------------------
    # GS4
    # --------------------------------------------------------

    "ethics": [
        "ethics",
        "ethical",
        "moral",
        "values"
    ],

    "integrity": [
        "integrity",
        "impartiality",
        "objectivity",
        "accountability"
    ],

    "emotional-intelligence": [
        "emotional intelligence",
        "empathy",
        "compassion"
    ],

    "probity": [
        "probity",
        "corruption",
        "transparency",
        "public service"
    ],

    # --------------------------------------------------------
    # Sociology Paper I
    # --------------------------------------------------------

    "sociology-theory": [
        "sociology",
        "sociological",
        "social theory",
        "theory"
    ],

    "marx": [
        "marx",
        "marxist",
        "class struggle",
        "alienation",
        "historical materialism"
    ],

    "durkheim": [
        "durkheim",
        "social fact",
        "division of labour",
        "suicide",
        "anomie"
    ],

    "weber": [
        "weber",
        "social action",
        "ideal type",
        "bureaucracy",
        "authority",
        "protestant ethic"
    ],

    "social-stratification": [
        "stratification",
        "social class",
        "inequality",
        "mobility",
        "status",
        "caste"
    ],

    "politics-society": [
        "power",
        "politics",
        "state",
        "democracy",
        "citizenship",
        "political"
    ],

    "religion": [
        "religion",
        "secularisation",
        "secularization",
        "fundamentalism"
    ],

    "kinship": [
        "family",
        "marriage",
        "kinship",
        "patriarchy",
        "descent"
    ],

    "social-change": [
        "social change",
        "modernisation",
        "development",
        "dependency",
        "education",
        "technology"
    ],

    # --------------------------------------------------------
    # Sociology Paper II
    # --------------------------------------------------------

    "indian-society": [
        "indian society",
        "indology",
        "ghurye",
        "srinivas",
        "desai"
    ],

    "caste": [
        "caste",
        "untouchability",
        "jati",
        "srinivas",
        "dumont",
        "beteille"
    ],

    "tribes": [
        "tribe",
        "tribal",
        "indigenous",
        "autonomy",
        "integration"
    ],

    "agrarian-structure": [
        "agrarian",
        "land reform",
        "land tenure",
        "farmer",
        "rural"
    ],

    "social-movements": [
        "social movement",
        "peasant movement",
        "women movement",
        "dalit movement",
        "environmental movement"
    ],

    "population": [
        "population",
        "fertility",
        "mortality",
        "migration",
        "sex ratio",
        "ageing"
    ],

    "urbanisation": [
        "urbanisation",
        "urbanization",
        "slum",
        "city",
        "urban",
        "industrialisation"
    ]
}


# ============================================================
# TOPIC CLASSIFIER
# ============================================================

def classify_topics(question):

    text = question.lower()

    topics = []

    for topic, keywords in TOPIC_KEYWORDS.items():

        for keyword in keywords:

            if keyword.lower() in text:

                topics.append(topic)

                break

    return topics


# ============================================================
# QUESTION CLEANUP
# ============================================================

def clean_question(question):

    # Remove excessive spaces
    question = re.sub(
        r"[ \t]+",
        " ",
        question
    )

    # Remove excessive blank lines
    question = re.sub(
        r"\n{3,}",
        "\n\n",
        question
    )

    return question.strip()



# ============================================================
# PRELIMS OPTIONS + CORRECT OPTION
# ============================================================

# Common option formats found in UPSC PDFs:
#   (a) ...
#   (b) ...
#   (c) ...
#   (d) ...
# and occasionally:
#   (A) ...
#   (B) ...
#
# We only parse options for prelims papers.
OPTION_PATTERN = re.compile(
    r"""
    (?m)
    ^\s*
    [\(\[]?([A-Da-d])[\)\].:-]\s*
    (.+?)
    (?=
        \n\s*[\(\[]?[A-Da-d][\)\].:-]\s+
        |
        \Z
    )
    """,
    re.IGNORECASE | re.VERBOSE | re.DOTALL
)


def is_prelims_paper(paper_info):
    return paper_info["stage"] == "prelims"


def extract_prelims_options(question_text):
    """
    Extract four prelims options from a question.

    Returns:
        {
            "option_a": "...",
            "option_b": "...",
            "option_c": "...",
            "option_d": "...",
            "options": {...}
        }

    If the PDF does not expose recognizable options, the values are None.
    """
    # Normalize line endings while preserving option boundaries.
    text = question_text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)

    matches = list(OPTION_PATTERN.finditer(text))

    options = {
        "option_a": None,
        "option_b": None,
        "option_c": None,
        "option_d": None,
    }

    for match in matches:
        letter = match.group(1).lower()
        value = re.sub(r"\s+", " ", match.group(2)).strip()

        key = f"option_{letter}"
        if key in options and value:
            options[key] = value

    options["options"] = {
        "A": options["option_a"],
        "B": options["option_b"],
        "C": options["option_c"],
        "D": options["option_d"],
    }

    return options


def detect_correct_option(question_text):
    """
    Detect a correct option only if an answer is explicitly present in the
    extracted PDF text.

    Normal question papers normally do NOT contain answer keys, so this
    returns None in that case. It deliberately does not guess answers.

    Supported explicit forms include:
      Correct Answer: B
      Answer: (B)
      Correct option: C
    """
    patterns = [
        r"\bcorrect\s+(?:answer|option)\s*[:\-]\s*\(?([A-D])\)?\b",
        r"\banswer\s*[:\-]\s*\(?([A-D])\)?\b",
        r"\bans(?:wer)?\s*[:\-]\s*\(?([A-D])\)?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, question_text, re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return None


def remove_hindi_translation(question_text):
    """
    Remove Hindi translations when they are embedded after the English
    question/options.

    This is intentionally conservative. It removes text only when a clear
    Hindi-script block is present. English content is retained.

    The rule is:
      - Keep the English portion.
      - If Devanagari begins after a newline, truncate at that point.
      - Do not use this function for the standalone compulsory Hindi paper.
    """
    lines = question_text.splitlines()

    english_lines = []

    for line in lines:
        # Devanagari Unicode block.
        devanagari_chars = re.findall(r"[\u0900-\u097F]", line)

        if devanagari_chars:
            # If a line is predominantly Hindi, it is the translation.
            letters = re.findall(r"[A-Za-z\u0900-\u097F]", line)
            if letters:
                hindi_ratio = len(devanagari_chars) / len(letters)
                if hindi_ratio >= 0.5:
                    break

        english_lines.append(line)

    return "\n".join(english_lines).strip()


# ============================================================
# PROCESS PDF
# ============================================================

def process_pdf(pdf_path):

    year = extract_year(pdf_path)

    paper_info = classify_paper(
        pdf_path.name
    )

    if paper_info is None:

        print(
            f"SKIP: {pdf_path.name}"
        )

        return [], []

    print()
    print(
        f"Processing: {pdf_path.name}"
    )

    pages = extract_pages(
        pdf_path
    )

    all_questions = []

    for page in pages:

        page_questions = find_questions(
            page["text"]
        )

        for q in page_questions:

            question_text = clean_question(
                q["question"]
            )

            # For prelims, keep the English question and options only.
            # Hindi translations embedded in the same PDF are ignored.
            if is_prelims_paper(paper_info):
                question_text = remove_hindi_translation(question_text)

            topics = classify_topics(
                question_text
            )

            question = {

                "year": year,

                "stage": paper_info["stage"],

                "paper": paper_info["paper"],

                "question_number":
                    q["question_number"],

                "question":
                    question_text,

                "option_a":
                    None,

                "option_b":
                    None,

                "option_c":
                    None,

                "option_d":
                    None,

                "options":
                    None,

                "correct_option":
                    None,

                "marks":
                    detect_marks(
                        question_text
                    ),

                "section":
                    detect_section(
                        page["text"]
                    ),

                "topics":
                    topics,

                "source_pdf":
                    str(pdf_path),

                "source_file":
                    pdf_path.name,

                "source_page":
                    page["page"],

                "needs_review":
                    len(topics) == 0
            }

            # Prelims-specific fields.
            if is_prelims_paper(paper_info):
                option_data = extract_prelims_options(question_text)

                question["option_a"] = option_data["option_a"]
                question["option_b"] = option_data["option_b"]
                question["option_c"] = option_data["option_c"]
                question["option_d"] = option_data["option_d"]
                question["options"] = option_data["options"]
                question["correct_option"] = detect_correct_option(
                    question_text
                )

                # Flag questions when option extraction looks incomplete.
                if not all(
                    question[f"option_{letter}"]
                    for letter in "abcd"
                ):
                    question["needs_review"] = True

            all_questions.append(
                question
            )

    # --------------------------------------------------------
    # Remove duplicate question numbers caused by
    # question continuing across pages
    # --------------------------------------------------------

    unique_questions = {}

    for question in all_questions:

        key = (
            question["year"],
            question["paper"],
            question["question_number"]
        )

        if key not in unique_questions:

            unique_questions[key] = question

        else:

            existing = unique_questions[key]

            # Keep the longer extracted text
            if len(question["question"]) > len(
                existing["question"]
            ):

                unique_questions[key] = question

    questions = list(
        unique_questions.values()
    )

    questions.sort(
        key=lambda q: q["question_number"]
    )

    return questions, []


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("UPSC PYQ QUESTION EXTRACTOR")
    print("=" * 70)

    if not SOURCE_DIR.exists():

        print(
            f"\nERROR: Folder does not exist:\n"
            f"{SOURCE_DIR}"
        )

        return

    pdf_files = sorted(
        SOURCE_DIR.rglob("*.pdf")
    )

    print(
        f"\nPDFs found: {len(pdf_files)}"
    )

    all_questions = []

    skipped = []

    for pdf_path in pdf_files:

        paper_info = classify_paper(
            pdf_path.name
        )

        if paper_info is None:

            skipped.append(
                str(pdf_path)
            )

            print(
                f"SKIP: {pdf_path.name}"
            )

            continue

        try:

            questions, _ = process_pdf(
                pdf_path
            )

            all_questions.extend(
                questions
            )

            print(
                f"  Questions: {len(questions)}"
            )

        except Exception as e:

            print(
                f"  ERROR: {e}"
            )

    # ========================================================
    # SORT
    # ========================================================

    all_questions.sort(
        key=lambda q: (
            q["year"] or 0,
            q["stage"],
            q["paper"],
            q["question_number"]
        )
    )

    # ========================================================
    # SAVE QUESTIONS
    # ========================================================

    with open(
        QUESTIONS_JSON,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            all_questions,
            file,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # SAVE QUESTIONS NEEDING REVIEW
    # ========================================================

    review_questions = [
        q
        for q in all_questions
        if q["needs_review"]
    ]

    with open(
        REVIEW_JSON,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            review_questions,
            file,
            indent=2,
            ensure_ascii=False
        )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("EXTRACTION COMPLETE")
    print("=" * 70)

    print(
        f"PDFs processed : "
        f"{len(pdf_files) - len(skipped)}"
    )

    print(
        f"PDFs skipped   : "
        f"{len(skipped)}"
    )

    print(
        f"Questions      : "
        f"{len(all_questions)}"
    )

    print(
        f"Needs review   : "
        f"{len(review_questions)}"
    )

    # Per-paper summary
    paper_counts = {}
    for q in all_questions:
        key = q["paper"]
        paper_counts[key] = paper_counts.get(key, 0) + 1

    print("\nQuestions by paper:")
    for paper, count in sorted(paper_counts.items()):
        print(f"  {paper:20s}: {count}")

    print()
    print(
        f"Questions JSON:\n"
        f"{QUESTIONS_JSON}"
    )

    print()
    print(
        f"Review JSON:\n"
        f"{REVIEW_JSON}"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()