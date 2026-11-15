# Data fixes — what was wrong, what changed

Run both:
```
.venv/bin/python upsc_app/tools/tag_subthemes.py
.venv/bin/python upsc_app/tools/audit_bulk_filled.py
```
Nothing in `data/final_pyq_data/` was modified. Every fix is a new file beside the source.

---

## 1. The real size of the "bulk-filled" problem

I scanned every column of every year for a value that is identical on every row. A
column where all 100 rows say the same thing was typed in bulk, not judged.

**273 year/column pairs are bulk-filled.** The ones that matter:

| File | Column | Years affected | What it means |
|---|---|---|---|
| csat | `difficulty` | **all 11 (2015–2026)** | every single CSAT question is "Medium". Not one was judged. |
| prelims | `difficulty` | 2026 | the one year I flagged |
| prelims | `nature` | 2026 | all null |
| prelims | `relevance` | **13 of 14** | every row is "High" — the column cannot rank anything |
| prelims | `is_repeated_theme` | 12 of 14 | same value per year, so it carries no per-question information |
| mains | `current_affairs_window` | **all 14** | one value per year, i.e. just the year again in disguise |
| mains | `difficulty` | 3 years | |
| mains | `source`, `source_type` | all 14 | constant, but these are legitimately constant |

So my earlier claim that "2026 is the weakest year" was too kind. **CSAT difficulty is
the weakest column in the whole bank** — 960 rows, one judgment, never made.

Full list: `qbank/bulk_filled.csv`.

---

## 2. What I did about difficulty

I tried to derive it and it failed, which is worth writing down: a model using
question structure (number of statements, count-format, stem length) predicts the
1,300 hand-labelled rows with a **mean error of 0.90 levels on a 1-3 scale**. That is
noise. Question structure does not explain perceived difficulty.

So I did not invent 99 new labels. Instead:

- `qbank/prelims_2026_difficulty.csv` — 2026 difficulty is **blanked** (with the old
  value kept in `difficulty_old` and a note), and replaced with **`question_load`**,
  a count of how many steps the question takes: statements to verify, count-format,
  matching, stem over 320 characters. Load 1–5.
- 2026 load distribution: `{1:19, 2:5, 3:12, 4:59, 5:4}` — 60% of the 2026 paper
  is at load 4+ (three or more statements), against 22% in 2023–25. The 2026
  paper genuinely asks you to check more statements per question.

Load is measurable and repeatable. "Difficulty" was neither.

---

## 3. What I did about `sub_theme`

`qbank/mains_subthemed.csv` — all 1,615 mains rows now have a sub_theme.

| Source | Rows | Share |
|---|---|---|
| rule matched (GS papers) | 811 | 50% |
| existing `subject` column (sociology) | 553 | 34% |
| `nature` = Case Study | 48 | 3% |
| fallback `General <paper>` | 203 | 13% |

114 distinct sub-themes. **93% of non-essay rows got a real label** (1,412 of 1,519);
the essay paper is the other 96 and is labelled "Essay" on purpose.

Why the fallback exists: the rules are matched on `paper`, **not** on `master_theme`,
because `master_theme` is wrong on a large block of rows. See below.

---

## 4. `master_theme` is wrong on 110 rows

`qbank/suspected_master_theme.csv` lists rows whose master theme cannot belong to
their paper. The worst offender: **43 GS1 questions are tagged "Science & Technology"**
and 36 more "International Relations" — e.g. *"Gandhara sculpture owed as much to the
Romans as to the Greeks"* and *"Suez Crisis of 1956"* are both filed under S&T.

GS1 has no science section, so those labels cannot be right. That is why the tagger
dispatches on paper and ignores master_theme. The 110 rows are a worklist; I did not
silently re-label them.

There is already a `suspected_wrong_subjects.json` in the data folder with 59 entries
— someone started this check and stopped. This run extends it to 110 and adds the
paper-consistency rule.

---

## 5. Still broken (not fixed, needs a human or the official papers)

- 51 GS1 questions still fall back to `General GS1` — they need hand labels.
- 203 fallbacks overall; the essay paper is 96 of them and that is intentional.
- GS4 case studies: `nature` only marks 48 across 12 years, but GS4 should have
  ~6 per year (~72). The 2017/2018/2020/2025 zeroes are wrong.
- 2013 mains has only GS1 (25 questions); 2026 mains has only GS1 + sociology.
- CSAT `difficulty` cannot be fixed from this data at all — needs a real pass over
  960 questions, or the column should be dropped.
- `relevance`, `current_affairs_window`, `is_repeated_theme` should be dropped
  outright; they are constant and will mislead any analysis built on them.

---

## 6. What the new sub-theme column buys you

`qbank/subtheme_recurrence.csv` — sub-themes that recur across years, which the
master themes could not show (every master theme is asked every year, so it
"predicts" nothing).

Top GS sub-themes by years present: Agriculture/MSP (12/14), Social Movements &
Diversity (12), Ethics & Human Values (11), Values in Public Service (11), Ancient &
Medieval India (11), Climatology (11), Parliament (11), Disaster Preparedness (11),
Freedom Struggle (10), Terrorism & Radicalisation (10).

That list is the first version of "what actually comes back" at a useful grain.
It is a starting point, not a finished predictor: 13% of rows are still unlabelled
and the rules are keyword-based, so treat the counts as ±1 year.

---

## 7. Prelims tagged the same way (step 3)

`qbank/prelims_subthemed.csv` — all 1,399 prelims rows, same sub-theme vocabulary as
mains, so the two papers can be joined.

| Source | Rows | Share |
|---|---|---|
| rule matched on the row's own `section` | 922 | 66% |
| rule matched after content fallback (unattributed current affairs) | 183 | 13% |
| no match → `General <section>` | 294 | 21% |

85 distinct sub-themes. The 21% fallback is honest: those are basic-physics one-liners
("why do ball bearings reduce friction"), species-list questions, and one-off state
schemes — none of which belong to a recurring sub-topic.

Per-year coverage of the big ones: Biodiversity 14/14, Parliament 14/14,
Agriculture/MSP 14/14, Water Resources 14/14, Climate Change 13/14.

### The new file that matters: `cross_paper_subthemes.csv`

58 sub-themes appear in **both** papers. Those are the ones where one block of
study pays twice.

| Sub-theme | Prelims yrs | Mains yrs | Prelims Qs | Mains Qs |
|---|---|---|---|---|
| Freedom Struggle & National Movement | 13 | 14 | 43 | 31 |
| Ancient & Medieval India | 13 | 13 | 72 | 27 |
| Agriculture, MSP & Farmers | 14 | 12 | 37 | 36 |
| Parliament & Legislative Procedure | 14 | 11 | 58 | 20 |
| Physical Geography & Geomorphology | 13 | 12 | 32 | 30 |
| Biotechnology & Health Technology | 14 | 8 | 48 | 9 |
| Fiscal Policy, Budget & Taxation | 13 | 9 | 37 | 15 |
| Space Technology | 13 | 8 | 21 | 8 |

Read it as a priority order: a sub-theme in 13+13 years is worth far more revision
time than one that is frequent in one paper only.

### 7a. One finding from that work worth keeping

While assembling practice sets I found a real defect in the bank: **65 prelims rows are
missing option (d)**, and **15 of them have an answer key that says (d)** — the key points
at an option that does not exist. 2023 is the worst year: 30 of 100 rows.

Those 65 questions cannot be attempted until the options are recovered from the original
papers. Nothing else in this folder depends on them.
