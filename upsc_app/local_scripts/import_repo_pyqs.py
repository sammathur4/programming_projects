#!/usr/bin/env python3
"""Import UPSC prelims PYQs from the open question repos into IASCode.

    git clone https://github.com/ilakkiyagpi-sketch/prelims-arena
    git clone https://github.com/utkrashtkumar/UPSCSphere   # optional, unverified
    python3 import_repo_pyqs.py \
        --arena  prelims-arena/data/sets \
        --sphere UPSCSphere/data/pyqVault

    add --apply to write. Default is a dry run that prints what it would do.

Sources
    prelims-arena  data/sets/PYQ-GS-YYYY.json, PYQ-CSAT-YYYY.json
    UPSCSphere     data/pyqVault/pyqYYYY_{gs,csat}_{1,2}.ts  (parsed with node)

Rules
    * dedupe on text: same year + 4-word-shingle Jaccard >= 0.90 -> duplicate
    * existing rows are never deleted or renumbered, attempts point at them
    * adds a `paper` column (GS = ids 1-100, CSAT = 101-180, UNIQUE(year, id))
"""

import argparse
import html
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "backend" / "db.sqlite3"
TAG = re.compile(r"<[^>]+>")
SUFFIX = re.compile(r"\s*\((?:upsc[^)]*)\)\s*$", re.I)
NOISE = re.compile(r"[^a-z0-9]+")
THRESHOLD = 0.90
PASSAGE_LEAD = "Read the following passage and answer the question that follows:"


def clean_text(raw):
    text = html.unescape(raw or "")
    text = re.sub(r"(?:<br\s*/?>)+", "\n", text, flags=re.I)
    text = TAG.sub(" ", text)
    text = re.sub(r"^\s*Question:\s*", "", text, flags=re.I)
    text = SUFFIX.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def words(text):
    return NOISE.sub(" ", SUFFIX.sub(" ", clean_text(text).lower())).split()


def shingles(text, k=4):
    w = words(text)
    return {tuple(w[i:i + k]) for i in range(max(len(w) - k + 1, 1))}


def signature(record):
    """Question + options: CSAT passage questions share a stem, differ by options."""
    return shingles(record["question"] + "\n" + "\n".join(record["options"]))


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def title(value):
    value = " ".join(part.capitalize() for part in (value or "").split())
    return {"Csat": "CSAT", "Gs": "GS", "Ir": "IR"}.get(value, value)


def load_arena(sets_dir):
    out = []
    for path in sorted(Path(sets_dir).glob("PYQ-*.json")):
        data = json.loads(path.read_text())
        passages = data.get("passages") or {}
        for q in data["questions"]:
            passage = clean_text(passages.get(q.get("pid")) or "")
            question = clean_text(q["q"])
            if passage:
                question = f"{PASSAGE_LEAD}\n\n{passage}\n\n{question}"
            number = re.search(r"Q(\d+)", q.get("s", ""))
            out.append({
                "year": int(q["y"]),
                "paper": "Prelims CSAT" if q["paper"] == "CSAT" else "Prelims GS",
                "section": title(q.get("sub")),
                "topic": q.get("u", ""),
                "question": question,
                "number": int(number.group(1)) if number else None,
                "options": [clean_text(o) for o in q["o"]],
                "answer": q["a"],
                "explanation": clean_text(q.get("e", "")),
                "difficulty": "Medium",
                "source_file": f"prelims-arena:{path.stem}",
            })
    return out


NODE_DUMP = """
import fs from 'fs';
const src = fs.readFileSync(process.argv[2], 'utf8')
  .replace(/^import .*$/gm, '')
  .replace(/export const /g, 'const ')
  .replace(/:\\s*Question\\[\\]\\s*=/g, ' =');
const name = src.match(/const (\\w+)/)[1];
const data = eval(src + `; ${name}`);
console.log(JSON.stringify(data));
"""


def load_sphere(vault_dir):
    files = sorted(Path(vault_dir).glob("pyq20*_*.ts"))
    if not files:
        raise SystemExit(f"no pyq*.ts files in {vault_dir}")
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        dump = Path(tmp) / "dump.mjs"
        dump.write_text(NODE_DUMP)
        for path in files:
            res = subprocess.run(
                ["node", str(dump), str(path)], capture_output=True, text=True
            )
            if res.returncode:
                raise SystemExit(f"{path.name}: {res.stderr.strip().splitlines()[-1]}")
            for q in json.loads(res.stdout):
                parts = path.stem.split("_")          # pyq2025_gs_1
                paper = "Prelims CSAT" if parts[1] == "csat" else "Prelims GS"
                out.append({
                    "year": int(q.get("pyqYear") or parts[0][3:]),
                    "paper": paper,
                    # sphere subjects are slugs ("csat_reading"); CSAT is one paper
                    "section": "CSAT" if paper == "Prelims CSAT" else title(q.get("subject")),
                    "topic": q.get("topic", ""),
                    "question": clean_text(q["question"]),
                    "number": None,
                    "options": [clean_text(o) for o in q["options"]],
                    "answer": q.get("correctAnswer"),
                    "explanation": clean_text(q.get("explanation", "")),
                    "difficulty": q.get("difficulty")
                    if q.get("difficulty") in ("Easy", "Medium", "Difficult")
                    else "Medium",
                    "source_file": f"UPSCSphere:{path.stem}",
                })
    return out


def load_local(conn):
    """year -> [signatures]; also the ids already used per year."""
    seen, used = {}, {}
    for year, qid, text, *opts in conn.execute(
        "SELECT year, question_id, question, option_a, option_b, option_c, option_d"
        " FROM prelims_questions"
    ):
        rec = {"question": text or "", "options": [o or "" for o in opts]}
        seen.setdefault(year, []).append(signature(rec))
        used.setdefault(year, set()).add(qid)
    return seen, used


def covered_papers(conn, minimum=50):
    """(year, paper) groups the bank already holds in full."""
    cols = [r[1] for r in conn.execute("PRAGMA table_info(prelims_questions)")]
    paper_col = "COALESCE(paper, 'Prelims GS')" if "paper" in cols else "'Prelims GS'"
    rows = conn.execute(
        f"SELECT year, {paper_col}, COUNT(*) FROM prelims_questions GROUP BY 1, 2"
    ).fetchall()
    return {(year, paper) for year, paper, count in rows if count >= minimum}


def dedupe(records, seen, used, threshold=THRESHOLD):
    new, borderline = [], []
    for rec in records:
        sig = signature(rec)
        pool = seen.setdefault(rec["year"], [])
        best = max((jaccard(sig, s) for s in pool), default=0.0)
        if best >= threshold:
            continue
        if best >= 0.80:
            borderline.append((round(best, 2), rec["question"][:90]))
        blocked = used.setdefault(rec["year"], set())
        start = 101 if rec["paper"] == "Prelims CSAT" else 1
        while start in blocked:
            start += 1
        blocked.add(start)
        rec["question_id"] = start
        new.append(rec)
        pool.append(sig)
    return new, borderline


def insert(conn, records):
    marks = {"Prelims CSAT": 2.5, "Prelims GS": 2.0}
    rows = [(
        r["question_id"], r["year"], r["paper"], r["section"],
        r["question"], *r["options"][:4],
        "abcd"[r["answer"]], r["explanation"], "", r["difficulty"],
        r["paper"], "UPSC CSE", "Previous Year Question", r["source_file"],
        ";".join(x for x in (r["section"], r["topic"]) if x),
        r.get("number"), marks[r["paper"]], round(marks[r["paper"]] / 3, 4),
    ) for r in records]
    conn.executemany(
        """
        INSERT INTO prelims_questions
            (question_id, year, paper, section, question,
             option_a, option_b, option_c, option_d, correct_answer,
             explanation, motivation, difficulty, nature, source, source_type,
             source_file, tags, question_number, marks, negative_marks)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    return len(rows)


def normalise_existing(conn):
    """Old rows carry literal <br>/<strong> and get rendered as text."""
    changed = 0
    for row_id, text in conn.execute(
        "SELECT id, question FROM prelims_questions WHERE question LIKE '%<%'"
    ).fetchall():
        cleaned = clean_text(text)
        if cleaned != text:
            conn.execute("UPDATE prelims_questions SET question=? WHERE id=?", (cleaned, row_id))
            changed += 1
    return changed


def self_check():
    assert clean_text("A<br>B<br><br>C") == "A\nB\nC"
    assert clean_text("Q (UPSC CSE Prelims 2025)") == "Q"
    a = shingles("Consider the following statements: 1. one 2. two")
    c = shingles("Consider the following statements: 1. one 2. two")
    assert jaccard(a, c) == 1.0
    assert jaccard(shingles("completely different wording here"), c) < 0.2
    one = {"question": "Which is the crux of the passage?", "options": ["A one", "B one"]}
    two = {"question": "Which is the crux of the passage?", "options": ["C two", "D two"]}
    assert jaccard(signature(one), signature(two)) < 0.5, "same stem, different options"
    assert jaccard(signature(one), signature(one)) == 1.0
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arena", help="prelims-arena data/sets directory")
    ap.add_argument("--sphere", help="UPSCSphere data/pyqVault directory")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="also fill gaps in (year, paper) groups already covered")
    ap.add_argument("--year", type=int, help="restrict to one year")
    ap.add_argument("--paper", help="restrict to 'Prelims GS' or 'Prelims CSAT'")
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    if not (args.arena or args.sphere):
        return ap.error("give --arena and/or --sphere")

    records = []
    if args.arena:
        records += load_arena(args.arena)
    if args.sphere:
        records += load_sphere(args.sphere)
    records = [r for r in records
               if len(r["options"]) == 4 and isinstance(r["answer"], int)
               and 0 <= r["answer"] < 4]
    if args.year:
        records = [r for r in records if r["year"] == args.year]
    if args.paper:
        records = [r for r in records if r["paper"] == args.paper]
    print(f"source questions: {len(records)}")

    conn = sqlite3.connect(DB)
    seen, used = load_local(conn)

    # A (year, paper) the bank already holds in full is the same exam paper:
    # the handful of rows that fail the fuzzy match are wording drift, not
    # missing questions. Skip the whole group, which also makes reruns no-ops.
    covered = set() if args.force else covered_papers(conn)
    skipped_groups = sorted({(r["year"], r["paper"]) for r in records
                             if (r["year"], r["paper"]) in covered})
    records = [r for r in records if (r["year"], r["paper"]) not in covered]
    for year, paper in skipped_groups:
        print(f"  already covered, skipped: {year} {paper}")

    new, borderline = dedupe(records, seen, used, args.threshold)

    by_year = {}
    for r in new:
        key = (r["year"], r["paper"])
        by_year[key] = by_year.get(key, 0) + 1
    print(f"duplicates skipped: {len(records) - len(new)}")
    print(f"new questions: {len(new)}")
    for key in sorted(by_year):
        print(f"  {key[0]} {key[1]:<13} +{by_year[key]}")
    if borderline:
        print(f"borderline (0.80-{args.threshold}) kept, eyeball these: {len(borderline)}")
        for score, text in borderline[:10]:
            print(f"  {score}  {text}")

    if not args.apply:
        print("\ndry run — nothing written. add --apply")
        return

    backup = DB.with_suffix(f".sqlite3.bak-{__import__('time').strftime('%Y%m%d-%H%M')}")
    shutil.copy2(DB, backup)
    print(f"\nbackup: {backup.name}")
    with conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(prelims_questions)")]
        if "paper" not in cols:
            conn.execute("ALTER TABLE prelims_questions ADD COLUMN paper TEXT")
            print("added column paper")
        added = insert(conn, new)
        touched = normalise_existing(conn)
    print(f"inserted {added} rows, normalised text of {touched} old rows")


if __name__ == "__main__":
    main()
