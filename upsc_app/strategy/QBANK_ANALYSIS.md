# Question bank analysis — what it actually buys you

Run: `.venv/bin/python upsc_app/tools/qbank_analysis.py`
Outputs: `upsc_app/strategy/qbank/{topic_weight,periodicity,format_shift,data_health}.csv` + `findings.txt`

---

## 0. The blunt answer first

The bank is ~3,974 questions (1,399 prelims GS + 960 CSAT + 1,615 mains). **Every serious
aspirant already has this exact bank** — it is on every Telegram channel in India. As a
*document* it is worth nothing. It is worth something only as a **measurement instrument**,
and right now it is only half-instrumented:

| What you'd want | Status in the bank |
|---|---|
| Section weightage per year | ✅ works, and surprising (stable) |
| Question-format mix per year | ✅ works, and changes your mock strategy |
| Answer-key exploit ("elimination tricks") | ❌ measured, does not exist |
| Sub-topic recurrence ("this will be asked again") | ❌ **impossible today** — `sub_theme` is 100% empty |
| Your own weakness map | ❌ no `question_id` link to attempts exists |
| CSAT weakness breakdown | ❌ all 960 rows tagged `CSAT`, nothing else |

So: the "10 years ahead" thing is **not** in this file. It is in the two things the file
makes possible and which nobody does — a sub-topic layer, and a per-question error loop.
Section 5 covers that. Everything before it is the measurement that tells you where to spend
the effort.

---

## 1. Prelims weightage is stable enough to plan against (the useful finding)

Normalised into canonical buckets (raw section labels change between years — 2026 files
everything pre-1857 under one `History` label, which silently corrupts any naive trend):

| Bucket | Marks/yr | Share | CV | Years present |
|---|---|---|---|---|
| History (incl. culture) | 33.3 | 16.7% | 0.18 | 14/14 |
| Environment & Ecology | 31.6 | 15.8% | 0.20 | 14/14 |
| Current Affairs (unattributed) | 30.7 | 15.4% | 0.73 | 12/14 |
| Polity & Governance | 29.9 | 14.9% | 0.27 | 14/14 |
| Economy | 28.7 | 14.4% | 0.24 | 14/14 |
| Geography | 23.0 | 11.5% | 0.40 | 14/14 |
| Science & Tech | 19.3 | 9.6% | 0.36 | 14/14 |
| International Relations | 3.4 | 1.7% | 1.63 | 4/14 |

Read: **CV 0.18–0.40 means the weightage moves by ±2 questions a year.** Your study
allocation can be set once and left alone — roughly 17/16/15/15/14/12/10 for
History/Env/CA/Polity/Economy/Geo/S&T. And because all seven buckets appeared in all 14
years, **there is no topic you can safely skip** — the "I'll leave Geography" strategy is
mathematically dead.

The only volatile item is IR (0 in 2013, 2–7 questions most years, 24 total) — it is a
lottery ticket, not an allocation.

---

## 2. The format changed twice, and old mocks are mis-weighted

% of that year's paper:

| Year | Multi-statement | "How many of the above" | "Codes given below" |
|---|---|---|---|
| 2013–17 | 20–35 | 0 | 26–34 |
| 2018–22 | 34–48 | 0–1 | 11–19 |
| **2023** | 33 | **40** | **0** |
| 2024 | 29 | 13 | 16 |
| 2025 | 40 | 17 | 8 |
| 2026 | 47 | 2 | — |

Two hard breaks: the codes format was dropped outright in 2023, and the count-format
("How many of the above are correct?") appeared in 2023 at 40% after never existing before.
It has been walking back down since.

Consequences you can act on:
- A 2015–2020 mock trains a format that is ~25% of the current paper. Code-based elimination
  practice is training for a question type that no longer exists.
- Multi-statement (verify 3–4 statements, answer partially-correct) is now the dominant
  format and it is the *most* content-hungry format. It rewards depth per topic, not breadth.
- ⚠️ Caveat: 2025–26 extraction uses inconsistent numbering (`I.` vs `1.`), so format
  percentages for those two years are partly artifacts. 2013–2024 is clean.

---

## 3. There is no option-level trick. Measured, not argued.

Tested against the real answer key, n=1,399:

| Strategy | Accuracy |
|---|---|
| Random | 25.0% |
| Always pick (B) | 27.3% |
| Longest option | **22.4%** |
| Longest option, after dropping options with *only/always/never/all of the above* | **22.1%** (n=897) |
| "All of these" always correct | 0.0% — the option appears in **3** questions total |
| "None of these" always correct | 0.0% — appears in **18** |

The single most-taught prelims trick ("longest option is usually right") is **worse than
guessing** on 14 years of data. The reason is structural: the correct answer contains the
word "only" 37% of the time, because the old codes format made "1 only / 2 and 3 only" the
answer itself. The trick was never measuring the thing it claimed to measure.

Fixed-letter bias: prelims is balanced (A 330 / B 382 / C 355 / D 332, χ²=5.1, p=0.17 — noise).
CSAT is **not** balanced (A 189 / B 271 / C 261 / D 239, χ²=16.7, p=0.0009). That is a
statistically real skew, and it is almost certainly a **key-mapping defect in the source**,
not a betting edge. Do not build a strategy on it; do not trust CSAT answer keys here
without spot-checking against the official paper.

---

## 4. Where the data is broken (fix before you build anything on it)

| Issue | Count | Why it matters |
|---|---|---|
| `sub_theme`, `theme_*`, `related_question_ids`, `tags` fully empty (mains) | **24 columns** | This is the entire prediction layer. It was designed and never populated. |
| GS4 case studies = 0 in 2017, 2018, 2020, 2025 | 4 years | GS4 marks sum to 170/120/130 in those years instead of 250. GS4 cannot be trended. |
| 2013 mains = 25 GS1 questions only; 2026 = GS1 + sociology only | 2 years | "14 years of mains" is really **12 usable years**. |
| `mains_2013_2026.csv` and `_corrected.csv` are byte-identical | 736K each | The correction pass produced no diff. Nobody can say which is authoritative. |
| CSAT starts 2015 | 2 years missing | 2013–14 CSAT absent; can't claim a 14-year CSAT trend. |
| `option_d` missing | 65 prelims rows | 4.6% of questions are unanswerable as loaded. |
| Options embedded inside `question` text | 100 rows (all 2013) | Will double-render in the app. |
| Per-option explanations | 99.9% empty | No option-level "why wrong" content exists despite 4 columns for it. |
| `source` unknown | 76.5% of prelims | Can't answer "which book covers the most PYQs" — the single most requested stat. |
| `pyq_2025_to_2026_map.csv` | 1,122 rows | Top match for a Carnatic-raga question is "Nature Solutions Finance Hub" at 0.133 similarity. TF-IDF noise with no threshold. Unusable. |

Only ~35% of prelims rows have `motivation` filled, 64% have `nature`, 92% have
`current_affairs_linkage`. The tagging is roughly one-third done, and the missing third was
never filled for the recent years.

---

## 5. So what actually makes you 10 years ahead

Not the bank. These three, in this order:

**1. Sub-topic tagging (the missing layer).** 29 master themes across 14 years means every
theme is asked every year — recurrence is 100%, which predicts nothing. The unit that
repeats is smaller: "Hilton-Young Commission", not "Modern History". `sub_theme` exists as a
column and is empty in all 1,615 rows. Until it is filled, any "2027 prediction" is a
horoscope. **This is the only piece of work that creates an edge; everything else in this
repo is bookkeeping around it.**

**2. A per-question error loop.** `question_id` exists and is unused. When an attempt is
logged against `question_id`, you can compute error rate per sub-topic, per format, per
bucket, per year-of-asking. That converts a static PDF into a diagnostic that narrows every
week. No coaching institute can give you that, because it requires *your* attempts.

**3. Calibration against the real format.** 1,292 of 1,615 mains questions are 10 marks /
150 words. That is a fixed exchange rate: **15 words per mark, 20 questions in 180 minutes
≈ 9 minutes per answer ≈ 17 words/minute sustained.** Any practice that doesn't hit that
rate is rehearsing a different exam.

The compounding claim, stated honestly: a bank is acquired once and depreciates. A loop of
(attempt → per-question result → sub-topic error rate → revision queue) compounds for as
long as you run it. Ten years ahead is a loop, not a dataset — and the gap between the two
is exactly the three items above, none of which exist yet.

---

## 6. If you only do three things

1. Fill `sub_theme` for the **last 4 years** (2023–2026), prelims + mains. ~800 rows. That is
   enough to test whether prediction is even possible before tagging all 3,974.
2. Delete the dead columns (`theme_*`, `tags`, `related_question_ids`, 24 of them) so nobody
   mistakes them for data, and delete `pyq_2025_to_2026_map.csv` or regenerate it with a
   similarity floor of ~0.45.
3. Fix the mains files: confirm which of the two is authoritative, recover GS2/GS3/GS4 for
   2026 and GS2–GS4 for 2013, and re-derive GS4 case studies for 2017/18/20/25.
