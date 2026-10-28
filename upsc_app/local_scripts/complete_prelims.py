#!/usr/bin/env python3
"""Make prelims rows self-contained: attach the CSAT passage and the real exam number.

The arena JSON keeps comprehension passages in a separate `passages` map and the
official question number in `s` ("UPSC Prelims 2021, CSAT Paper II, Q37"). The
first import only took `q`, so passage questions rendered as orphan stems like
"Which one of the following ... crux of the passage?" with no passage above it.

    python3 complete_prelims.py --arena <sets dir>            # dry run
    python3 complete_prelims.py --arena <sets dir> --apply
    python3 complete_prelims.py --self-check

Rows are matched to arena questions one-to-one per (year, paper): every arena
question can back at most one row, so two rows can never end up with the same
official number. A stem shared by several passage questions ("...crux of the
passage?") is disambiguated by the options.

Rows that match nothing are left untouched (they keep their bank number).
Nothing is deleted, and reruns are no-ops.
"""

import argparse
import json
import re
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_repo_pyqs import clean_text, shingles, jaccard  # noqa: E402

DB = Path(__file__).resolve().parents[1] / "backend" / "db.sqlite3"
PASSAGE_LEAD = "Read the following passage and answer the question that follows:"
NUMBER = re.compile(r"Q(\d+)")
MATCH = 0.90          # same threshold the importer uses for duplicates


def load_arena(sets_dir):
    """(year, paper) -> [ {number, passage, signature, text, options} ]."""
    groups = {}
    for path in sorted(Path(sets_dir).glob("PYQ-*.json")):
        data = json.loads(path.read_text())
        passages = data.get("passages") or {}
        for q in data["questions"]:
            found = NUMBER.search(q.get("s", ""))
            if not found:
                continue
            paper = "Prelims CSAT" if q["paper"] == "CSAT" else "Prelims GS"
            text = clean_text(q["q"])
            options = [clean_text(o) for o in q["o"]]
            groups.setdefault((int(q["y"]), paper), []).append({
                "number": int(found.group(1)),
                "passage": clean_text(passages.get(q.get("pid")) or ""),
                "text": text,
                "signature": shingles(text + "\n" + "\n".join(options)),
            })
    return groups


def signature(text, options):
    return shingles((text or "") + "\n" + "\n".join(options or []))


def assign(rows, candidates, threshold=MATCH):
    """Greedy one-to-one match, best similarity first. Returns {row: candidate}."""
    pairs = []
    for row_index, sig in enumerate(rows):
        for cand_index, cand in enumerate(candidates):
            score = jaccard(sig, cand["signature"])
            if score >= threshold:
                pairs.append((score, row_index, cand_index))
    pairs.sort(reverse=True)
    taken_rows, taken_cands, mapping = set(), set(), {}
    for score, row_index, cand_index in pairs:
        if row_index in taken_rows or cand_index in taken_cands:
            continue
        taken_rows.add(row_index)
        taken_cands.add(cand_index)
        mapping[row_index] = candidates[cand_index]
    return mapping


def already_has_passage(text):
    return PASSAGE_LEAD in text or "Read the following passage" in text


def rebuild(text, meta):
    if meta["passage"] and not already_has_passage(text):
        return f"{PASSAGE_LEAD}\n\n{meta['passage']}\n\n{text}"
    return text


def self_check():
    cands = [
        {"number": 1, "passage": "", "text": "stem", "signature": signature("stem", ["x"])},
        {"number": 2, "passage": "P", "text": "stem", "signature": signature("stem", ["y"])},
    ]
    rows = [signature("stem", ["y"]), signature("stem", ["x"])]
    mapping = assign(rows, cands)
    assert mapping[0]["number"] == 2, "shared stem must disambiguate on options"
    assert mapping[1]["number"] == 1
    assert len({m["number"] for m in mapping.values()}) == 2, "never assign twice"
    assert rebuild("q", {"passage": "P"}) == f"{PASSAGE_LEAD}\n\nP\n\nq"
    assert rebuild(f"{PASSAGE_LEAD}\n\nP\n\nq", {"passage": "P"}) == f"{PASSAGE_LEAD}\n\nP\n\nq"
    print("self-check ok")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arena", help="prelims-arena data/sets directory")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args()
    if args.self_check:
        return self_check()
    if not args.arena:
        return ap.error("give --arena")

    groups = load_arena(args.arena)
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT id, year, COALESCE(paper, 'Prelims GS'), question, question_number,"
        " option_a, option_b, option_c, option_d"
        " FROM prelims_questions ORDER BY id"
    ).fetchall()

    by_group = {}
    for row in rows:
        by_group.setdefault((row[1], row[2]), []).append(row)

    updates = []
    for key in sorted(by_group):
        group_rows = by_group[key]
        candidates = groups.get(key, [])
        if not candidates:
            print(f"  {key[0]} {key[1]:<13} no arena set, skipped")
            continue
        mapping = assign(
            [signature(row[3], row[5:9]) for row in group_rows], candidates
        )
        # Renumbering half a paper would leave two questions sharing a number and
        # one arbitrary gap. Only adopt official numbers when every row matched.
        if len(mapping) < len(group_rows):
            print(f"  {key[0]} {key[1]:<13} {len(mapping):>3}/{len(group_rows):<3} matched"
                  f" — partial, kept bank order")
            continue
        gained = 0
        for row_index, meta in mapping.items():
            row = group_rows[row_index]
            question = rebuild(row[3], meta)
            if question != row[3] or row[4] != meta["number"]:
                updates.append((question, meta["number"], row[0]))
            gained += meta["passage"] != "" and question != row[3]
        print(f"  {key[0]} {key[1]:<13} matched {len(mapping):>3}/{len(group_rows):<3}"
              f" +passages {gained:>3}")

    print(f"\nrows to update: {len(updates)}")
    if not args.apply:
        return print("dry run — nothing written. add --apply")

    backup = DB.with_suffix(f".sqlite3.bak-{time.strftime('%Y%m%d-%H%M')}")
    shutil.copy2(DB, backup)
    print(f"backup: {backup.name}")
    with conn:
        conn.executemany(
            "UPDATE prelims_questions SET question=?, question_number=? WHERE id=?", updates
        )
    print(f"updated {len(updates)} rows")


if __name__ == "__main__":
    main()
