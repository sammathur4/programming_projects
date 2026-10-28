#!/usr/bin/env python3
"""Turn a scanned prelims question paper into review JSON (no DB writes).

    python3 parse_prelims_pdf.py "Prelims GS2 CSAT 2025.pdf" --out review/csat_2025.json

Layout it expects (official UPSC booklets): numbered questions 1..N, four
options marked (a)-(d), passages printed before the questions that use them.
Hindi is skipped: OCR keeps the English column readable, and lines that are
mostly non-ASCII are dropped.

`--self-check` runs the parser on a synthetic snippet.

Output carries questions + options + marks. Answer keys are NOT in the question
paper, so `answer` stays null until a key PDF is added.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_ocr import ocr  # noqa: E402

OPTION = re.compile(r"^\s*\(([a-d])\)\s*(.*)$")
QUESTION = re.compile(r"^\s*(\d{1,2})\.\s*(.*)$")
MARKS = {"Prelims GS": 2.0, "Prelims CSAT": 2.5}


def english(lines):
    """Keep lines that are mostly ASCII (OCR'd Hindi is noise)."""
    out = []
    for line in lines:
        letters = [c for c in line if c.isalpha()]
        if not letters:
            out.append(line)
            continue
        ascii_letters = sum(1 for c in letters if c.isascii())
        if ascii_letters / len(letters) >= 0.8:
            out.append(line)
    return out


def tidy(block):
    text = "\n".join(block)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def parse(text, paper):
    """Return [{number, question, options, passage}] for one paper's OCR text."""
    lines = [line for line in text.splitlines() if not line.startswith("--- PAGE")]
    lines = english(lines)

    questions, expected, prefix = [], 1, []
    current = None

    def flush():
        nonlocal current
        if not current:
            return
        body, options = [], {}
        for line in current["lines"]:
            match = OPTION.match(line)
            if match:
                options.setdefault(match.group(1), []).append(match.group(2))
            elif options:
                options[max(options)].append(line)  # wrapped option text
            else:
                body.append(line)
        record = {
            "number": current["number"],
            "passage": tidy(current["prefix"]),
            "question": tidy(current["prefix"] + body),
            "options": {key: tidy(value) for key, value in options.items()},
            "marks": MARKS.get(paper),
        }
        questions.append(record)
        current = None

    for line in lines:
        match = QUESTION.match(line)
        if match and int(match.group(1)) == expected:
            flush()
            current = {
                "number": expected,
                "prefix": [p for p in prefix if p.strip()] + [""],
                "lines": [match.group(2)] if match.group(2).strip() else [],
            }
            prefix = []
            expected += 1
            continue
        if current:
            current["lines"].append(line)
        else:
            prefix.append(line)
    flush()

    clean = []
    for record in questions:
        record["question"] = record["question"].lstrip("\n")
        if record["question"]:
            clean.append(record)
    return clean


def problems(records, paper):
    """Human-review checklist: what a reviewer should look at first."""
    issues = []
    for record in records:
        missing = [key for key in "abcd" if not record["options"].get(key)]
        if missing:
            issues.append({"number": record["number"],
                           "issue": f"missing options {', '.join(missing)}"})
        elif len(record["question"]) < 15:
            issues.append({"number": record["number"], "issue": "question text too short"})
    numbers = [record["number"] for record in records]
    gaps = [n for n in range(1, max(numbers) + 1) if n not in numbers] if numbers else []
    if gaps:
        issues.append({"number": None, "issue": f"missing question numbers: {gaps}"})
    return issues


def self_check():
    sample = """Directions for the following 2 items:
Read the passage and answer.

Passage - 1

Bees are important for crops.

1. What is the passage about ?
(a) Bees
(b) Cars

2. Which is true ?
(a) Bees matter
(b) Bees do not
(c) Nothing
(d) Unknown

3. Unrelated statement
(a) x
"""
    records = parse(sample, "Prelims CSAT")
    assert [r["number"] for r in records] == [1, 2, 3]
    assert records[0]["options"]["a"] == "Bees", records[0]
    assert records[0]["question"].startswith("Directions for the following 2 items"), records[0]
    assert records[1]["options"]["c"] == "Nothing"
    assert problems(records, "Prelims CSAT"), "2-option question must be flagged"
    hindi = english(["भारत सरकार का निर्णय", "The answer is (b)"])
    assert hindi == ["The answer is (b)"], hindi
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--year", type=int)
    ap.add_argument("--paper", default="Prelims CSAT")
    ap.add_argument("--pages", help="page range, default whole file")
    ap.add_argument("--out", help="output JSON path")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    if not args.pdf:
        return ap.error("give a pdf")

    pages = None
    if args.pages:
        first, _, last = args.pages.partition("-")
        pages = (int(first), int(last or first))
    year = args.year or int(re.search(r"(20\d{2})", Path(args.pdf).name).group(1))
    text = ocr(args.pdf, pages)
    records = parse(text, args.paper)
    issues = problems(records, args.paper)

    payload = {
        "year": year,
        "paper": args.paper,
        "source_pdf": Path(args.pdf).name,
        "extracted": len(records),
        "issues": issues,
        "questions": records,
    }
    out = Path(args.out) if args.out else Path(f"review/{args.paper.split()[-1].lower()}_{year}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{year} {args.paper}: {len(records)} questions, {len(issues)} review flags")
    for issue in issues[:8]:
        print(f"  Q{issue['number']}: {issue['issue']}")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
