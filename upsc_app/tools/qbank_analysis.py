#!/usr/bin/env python3
"""
qbank_analysis.py — what the PYQ bank can and cannot tell you.

Reads data/final_pyq_data/*.csv, normalises the inconsistent section labels into
canonical syllabus buckets, then emits the tables worth acting on:

  topic_weight.csv   expected marks per bucket per year (prelims 2/q, mains by marks)
  periodicity.csv    bucket x year hit matrix + gap stats
  format_shift.csv   question-format mix per year (statement / how-many / direct)
  data_health.csv    per-file completeness: nulls, dups, key balance, dead cols
  findings.txt       the heuristic tests (does longest-option / fixed-letter beat 25%?)

Run:  .venv/bin/python upsc_app/tools/qbank_analysis.py
"""
from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parents[2] / "data" / "final_pyq_data"
OUT = Path(__file__).resolve().parents[1] / "strategy" / "qbank"

PRELIMS = DATA / "UPSC IAS PYQs - prelims_2013_2026.csv"
CSAT = DATA / "UPSC IAS PYQs - csat_2013_2026.csv"
MAINS = DATA / "UPSC IAS PYQs - mains_2013_2026_corrected.csv"

# messy section label -> canonical bucket. Add rows, never rename in place.
PRELIMS_MAP = {
    "Polity & Governance": "Polity",
    "Government Schemes": "Polity",
    "Current Affairs (Government Schemes)": "Polity",
    "Current Affairs (Polity & Governance)": "Polity",
    "Current Affairs/Schemes": "Polity",
    "Social Issues/Schemes": "Polity",
    "Economy": "Economy",
    "Current Affairs (Economics)": "Economy",
    "Agriculture": "Economy",
    "Geography": "Geography",
    "Current Affairs (Geography)": "Geography",
    "Environment & Ecology": "Environment",
    "Science & Technology": "S&T",
    "Current Affairs (S&T)": "S&T",
    "Modern History": "History",
    "Ancient History": "History",
    "Medieval History": "History",
    "History": "History",
    "Art & Culture": "History",
    "Current Affairs (Art & Culture)": "History",
    "International Relations": "IR",
    "Current Affairs (International Relations)": "IR",
    "Current Affairs (Internal Security)": "IR",
    "Current Affairs (Social Schemes)": "Polity",
    # unattributed current affairs: keep separate, it is a real category
    "Current Affairs": "Current Affairs",
    "Current Affairs/General Awareness": "Current Affairs",
    "Miscellaneous (General Awareness)": "Current Affairs",
}

MAINS_MAP = {
    "Ethics, Integrity & Aptitude": "Ethics",
    "International Relations": "IR",
    "Internal Security": "IR",
    "Polity & Constitution": "Polity",
    "Governance & Accountability": "Polity",
    "Social Justice & Inclusion": "Polity",
    "Economy & Inclusive Growth": "Economy",
    "Agriculture & Food Systems": "Economy",
    "Work & Economic Life": "Economy",
    "Urbanization": "Economy",
    "Science & Technology": "S&T",
    "Environment & Climate": "Environment",
    "Geography": "Geography",
    "Modern & World History": "History",
    "Indian Culture & Heritage": "History",
    "Essay: Philosophy, Society & Contemporary Issues": "Essay",
    "Disaster Management": "Disaster Mgmt",
}
# everything else in mains is sociology optional
SOCIOLOGY = {
    "Sociological Thinkers",
    "Sociology Fundamentals & Social Structure",
    "Caste, Tribe & Social Stratification",
    "Social Change & Modernization",
    "Indian Society & Social Change",
    "Research Methods",
    "Women & Gender",
    "Religion & Secularism",
    "Rural & Agrarian Society",
    "Social Stratification",
    "Social Structure",
    "Education",
}


def load():
    p = pd.read_csv(PRELIMS)
    c = pd.read_csv(CSAT)
    m = pd.read_csv(MAINS)
    p["bucket"] = p.section.map(PRELIMS_MAP).fillna("UNMAPPED")
    m["bucket"] = m.master_theme.map(
        lambda t: MAINS_MAP.get(t, "Sociology" if t in SOCIOLOGY else "UNMAPPED")
    )
    return p, c, m


def topic_weight(p, m):
    """Expected marks per bucket per year. Essay is normalised to 250/yr (8 topics
    are listed per year but only 2 are attempted), so shares compare like with like."""
    pl = p.groupby(["year", "bucket"]).size().unstack(fill_value=0) * 2  # 2 marks/q
    mm = m.copy()
    mm["marks"] = mm["marks"].astype(float)
    is_essay = mm.bucket == "Essay"
    mm.loc[is_essay, "marks"] = 250 / max(is_essay.sum() / mm.year.nunique(), 1)
    mn = mm.groupby(["year", "bucket"]).marks.sum().unstack(fill_value=0)
    rows = []
    for b in sorted(set(pl.columns) | set(mn.columns)):
        py = pl[b] if b in pl else pd.Series(0, index=pl.index)
        my = mn[b] if b in mn else pd.Series(0, index=mn.index)
        rows.append(
            {
                "bucket": b,
                "block": "optional" if b in ("Sociology", "Essay") else "gs",
                "prelims_marks_per_yr": round(py.mean(), 1),
                "prelims_share_%": round(100 * py.mean() / pl.sum(axis=1).mean(), 1),
                "mains_marks_per_yr": round(my.mean(), 1),
                "mains_share_%": round(100 * my.mean() / mn.sum(axis=1).mean(), 1),
                "years_seen_prelims": int((py > 0).sum()),
                "years_seen_mains": int((my > 0).sum()),
                "prelims_cv": round(float(py.std(ddof=0) / py.mean()), 2) if py.mean() else None,
                "mains_cv": round(float(my.std(ddof=0) / my.mean()), 2) if my.mean() else None,
            }
        )
    return pd.DataFrame(rows).sort_values("prelims_marks_per_yr", ascending=False)


def periodicity(p, m):
    """Bucket x year grid + last-seen, for the 'due again' read."""
    out = []
    for name, df, col in [("prelims", p, "bucket"), ("mains", m, "bucket")]:
        grid = pd.crosstab(df[col], df.year)
        for b in grid.index:
            seen = [y for y in grid.columns if grid.loc[b, y] > 0]
            out.append(
                {
                    "paper": name,
                    "bucket": b,
                    "years_seen": len(seen),
                    "last_seen": max(seen) if seen else None,
                    "gap_since_last": 2026 - max(seen) if seen else None,
                    "hits": int(grid.loc[b].sum()),
                    "per_year": round(grid.loc[b].mean(), 1),
                }
            )
    return pd.DataFrame(out)


FORMATS = {
    "multi_statement": r"statement[s]? (?:given )?(?:above )?(?:is|are)|which of the (?:above|following) statements",
    "how_many_of_above": r"how many of the (?:above|following)",
    "codes_given_below": r"codes? given below|using the code",
    "numbered_list": r"\n\s*1\.",
    "match_pairs": r"consider the following pairs?",
    "match_list": r"match list",
    "assertion_reason": r"assertion",
}


def format_shift(p):
    q = p.question.fillna("").str.lower()
    rows = []
    for y, g in p.assign(q=q).groupby("year"):
        row = {"year": y, "n": len(g)}
        for name, pat in FORMATS.items():
            row[name] = round(100 * g.q.str.contains(pat, regex=True, na=False).mean(), 0)
        rows.append(row)
    return pd.DataFrame(rows)


def key_balance(series):
    vc = series.str.strip().str.lower().value_counts()
    n, k = vc.sum(), len(vc)
    chi2 = float((((vc - n / k) ** 2) / (n / k)).sum())
    # chi2 p-value without scipy: Wilson-Hilferty normal approx
    z = ((chi2 / (k - 1)) ** (1 / 3) - (1 - 2 / (9 * (k - 1)))) / np.sqrt(2 / (9 * (k - 1)))
    return dict(counts=vc.to_dict(), chi2=round(chi2, 1), p_approx=round(float(0.5 * math.erfc(z / math.sqrt(2))), 4))


def heuristics(p):
    """Do the coaching myths beat 25%? Tested against the real answer key."""
    key = p.correct_answer.str.strip().str.lower()
    oi = {i: p["option_" + i].fillna("") for i in "abcd"}
    lens = pd.DataFrame({i: oi[i].str.len().replace(0, np.nan) for i in "abcd"})
    extreme = r"(?:\b(?:always|never|only|must|cannot|entirely|solely)\b|all of the above|none of the above)"
    mask = pd.DataFrame({i: oi[i].str.lower().str.contains(extreme, regex=True) for i in "abcd"})
    safe = lens.mask(mask).fillna(-1)
    pick = safe.idxmax(axis=1)
    valid = (safe >= 0).sum(axis=1) >= 2
    return {
        "baseline_random": 0.25,
        "always_B": round(float((key == "b").mean()), 3),
        "longest_option": round(float((lens.fillna(-1).idxmax(axis=1) == key).mean()), 3),
        "longest_non_extreme": round(float((pick[valid] == key[valid]).mean()), 3),
        "n_longest_non_extreme": int(valid.sum()),
        "correct_has_extreme_word": round(
            float(mask.values[np.arange(len(p)), key.map({k: i for i, k in enumerate("abcd")}).fillna(0).astype(int)].mean()),
            3,
        ),
    }


# words that pass the capital-letter test but carry no topic
ENTITY_NOISE = {
    "according", "these", "those", "there", "what", "when", "which", "some",
    "recently", "house", "region", "location", "protection", "state", "states",
    "way", "manner", "case", "type", "types", "size", "number", "part", "form",
}


def extract_entities(df):
    """Capitalised phrases per question. Kept only if they contain at least one
    token that appears in <2% of the corpus — that filters 'State'/'India' out and
    keeps 'Lok Sabha'/'Hilton-Young Commission' in."""
    q = df.question.fillna("").map(lambda s: re.split(r"\n?\s*\(a\)", s)[0])
    n = max(len(q), 1)
    tokfreq: dict[str, int] = {}
    for s in q:
        for t in set(re.findall(r"[A-Za-z][A-Za-z'\-]+", s.lower())):
            tokfreq[t] = tokfreq.get(t, 0) + 1
    pat = re.compile(r"\b([A-Z][A-Za-z'’\-]{2,}(?:\s+(?:of|the|and|de|al)?\s*[A-Z][A-Za-z'’\-]{2,}){0,3})\b")
    rows = []
    for s, y in zip(q, df.year):
        for m in pat.finditer(s):
            e = re.sub(r"\s+", " ", m.group(1)).strip()
            toks = [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z'\-]+", e)]
            if not toks or len(e) < 5:
                continue
            if any(t in ENTITY_NOISE for t in toks):
                continue
            # a lone capitalised word at the start of a sentence is just capitalisation
            pre = s[max(0, m.start() - 2):m.start()]
            if len(toks) == 1 and (m.start() == 0 or re.search(r"[.:;!?]\s?$", pre) or pre.endswith("\n")):
                continue
            if min(tokfreq.get(t, 0) for t in toks) / n > 0.02:
                continue
            rows.append((e, y))
    return pd.DataFrame(rows, columns=["entity", "year"])


def forecast(p, m):
    """How much of the paper can be predicted at all, and what recurs."""
    out = {}
    for name, df in [("prelims", p), ("mains", m)]:
        E = extract_entities(df)
        g = (
            E.groupby("entity")
            .year.agg(yrs="nunique", hits="count", first="min", last="max")
            .reset_index()
        )
        out[name] = g
        g.sort_values(["yrs", "hits"], ascending=False).to_csv(OUT / f"entity_recurrence_{name}.csv", index=False)
        g[(g.yrs >= 2) & (g.last <= 2022)].sort_values(["yrs", "hits"], ascending=False).to_csv(
            OUT / f"due_candidates_{name}.csv", index=False
        )
    return out


def data_health(p, c, m):
    rows = []
    for name, df in [("prelims", p), ("csat", c), ("mains", m)]:
        dead = [col for col in df.columns if df[col].isna().all()]
        rows.append(
            {
                "file": name,
                "rows": len(df),
                "years": f"{int(df.year.min())}-{int(df.year.max())}",
                "dup_questions": int(df.question.str.lower().str.strip().duplicated().sum()),
                "fully_empty_cols": len(dead),
                "empty_col_names": ",".join(dead),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    p, c, m = load()
    OUT.mkdir(parents=True, exist_ok=True)

    tw = topic_weight(p, m)
    per = periodicity(p, m)
    fmt = format_shift(p)
    health = data_health(p, c, m)
    heur = heuristics(p)
    key_p = key_balance(p.correct_answer)
    key_c = key_balance(c.correct_answer)
    fc = forecast(p, m)

    tw.to_csv(OUT / "topic_weight.csv", index=False)
    per.to_csv(OUT / "periodicity.csv", index=False)
    fmt.to_csv(OUT / "format_shift.csv", index=False)
    health.to_csv(OUT / "data_health.csv", index=False)

    lines = ["== heuristic tests (prelims GS, n=%d) ==" % len(p)]
    lines += [f"  {k:26} {v}" for k, v in heur.items()]
    lines += ["", "== answer key balance ==", f"  prelims {key_p}", f"  csat    {key_c}"]
    lines += ["", "== topic weight ==", tw.to_string(index=False)]
    lines += ["", "== format shift % ==", fmt.to_string(index=False)]
    lines += ["", "== data health ==", health.drop(columns=["empty_col_names"]).to_string(index=False)]
    lines += ["", "== repeat behaviour (how predictable is the paper?) =="]
    for name, g in fc.items():
        n = len(g)
        lines.append(f"  {name}: {n} distinct entities; seen in only 1 year "
                     f"{(g.yrs == 1).mean():.0%}; seen in >=3 years {(g.yrs >= 3).mean():.0%}")
        top = g.sort_values(["yrs", "hits"], ascending=False).head(8)
        lines.append("    most recurring: " + ", ".join(f"{r.entity} ({r.yrs}y)" for r in top.itertuples()))
    text = "\n".join(lines)
    (OUT / "findings.txt").write_text(text + "\n")

    print(text)
    return 0 if (p.bucket == "UNMAPPED").sum() == 0 and (m.bucket == "UNMAPPED").sum() == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
