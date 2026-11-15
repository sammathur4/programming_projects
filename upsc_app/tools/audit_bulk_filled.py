#!/usr/bin/env python3
"""
audit_bulk_filled.py — finds columns that were filled with one value for a whole
year, and replaces Prelims-2026's fake "Medium" difficulty with something measured.

Two problems, one cause: a value that is identical on every row of a year was
typed in bulk, not judged. 2026 difficulty is the obvious one ("Medium" x99), but
it is not the only one, and the same sweep finds the rest.

So:
  1. scan every column of every year for a single repeated value  -> bulk_filled.csv
  2. for 2026, blank the fake difficulty and add `question_load`, a transparent
     count of verification steps (statements to check, count-format, matching)

Why not just guess the difficulty? Because it was tried and it does not work:
structure explains almost none of the human labels (in-sample mean error 0.90 on a
1-3 scale). A made-up number would be worse than an honest blank.

Writes: strategy/qbank/bulk_filled.csv
        strategy/qbank/prelims_2026_difficulty.csv
Run:    .venv/bin/python upsc_app/tools/audit_bulk_filled.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "final_pyq_data"
OUT = Path(__file__).resolve().parents[1] / "strategy" / "qbank"

FILES = {
    "prelims": DATA / "UPSC IAS PYQs - prelims_2013_2026.csv",
    "csat": DATA / "UPSC IAS PYQs - csat_2013_2026.csv",
    "mains": DATA / "UPSC IAS PYQs - mains_2013_2026_corrected.csv",
}
MIN_ROWS = 20  # a year+column needs this many rows before "all the same" means anything


def bulk_filled() -> pd.DataFrame:
    rows = []
    for name, path in FILES.items():
        df = pd.read_csv(path).fillna({"year": 0})
        for year, g in df.groupby("year"):
            for col in df.columns:
                if col in ("year",):
                    continue
                vals = g[col].dropna()
                if len(vals) < MIN_ROWS:
                    continue
                if vals.nunique() == 1:
                    rows.append({"file": name, "year": int(year), "column": col,
                                 "rows": len(vals), "value": str(vals.iloc[0])[:60]})
    return pd.DataFrame(rows).sort_values(["file", "column", "year"])


def question_load(df: pd.DataFrame) -> pd.Series:
    """1-5, higher = more steps before you can answer. Countable, not judged."""
    q = df.question.fillna("")
    n = q.map(lambda s: len(re.findall(r"(?:^|\n)\s*(?:[1-9]\.|[IVX]{1,4}\.)\s", s)))
    count_fmt = q.str.contains(r"how many of the (?:above|following)", case=False)
    match = q.str.contains(r"match list|consider the following pairs?", case=False)
    load = (
        1
        + (n >= 2).astype(int)
        + (n >= 3).astype(int)
        + (count_fmt | match).astype(int)
        + (q.str.len() > 320).astype(int)
    )
    return load.clip(1, 5)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    bulk = bulk_filled()
    bulk.to_csv(OUT / "bulk_filled.csv", index=False)

    p = pd.read_csv(FILES["prelims"])
    p["question_load"] = question_load(p)
    out = p.loc[p.year == 2026, ["id", "year", "section", "question", "difficulty", "question_load"]].copy()
    out["difficulty_old"] = out.pop("difficulty")
    out["difficulty_new"] = pd.NA
    out["difficulty_note"] = "source value was bulk-filled; use question_load instead"
    out.to_csv(OUT / "prelims_2026_difficulty.csv", index=False)

    print(f"bulk-filled year/column pairs: {len(bulk)}")
    print(bulk.groupby("file").size().to_string())
    print("\n== the ones that matter (judgement columns) ==")
    judge = {"difficulty", "nature", "relevance", "current_affairs_linkage", "source", "source_type"}
    print(bulk[bulk.column.isin(judge)].to_string(index=False) or "  none")
    print("\n== all bulk-filled pairs ==")
    print(bulk.to_string(index=False))
    print("\n2026 question_load distribution:", out.question_load.value_counts().sort_index().to_dict())
    print("2023-25 question_load for comparison:",
          question_load(p[p.year.between(2023, 2025)]).value_counts().sort_index().to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
