# Task: Complete UPSC Prelims 1995–2012 (fill pending gaps)

## Objective
Produce a **complete, corrected dataset** for UPSC Civil Services Prelims (General Studies Paper I), years **1995–2012**, by filling every pending gap listed in the gap file. Output must be ready to merge back into the main CSV.

## Files / context
- **Main CSV (to be completed):** `/media/saksham/phone data/downloads/Opencode_upsc_plan - Prelims.csv`
  - Backup: `/media/saksham/phone data/downloads/Opencode_upsc_plan - Prelims.csv.bak`
  - Header (row 2; row 1 is empty): `id,question_id,year,paper,section,question,option_a,option_b,option_c,option_d,correct_answer,explanation,motivation,difficulty,nature,source,source_type,tags,relevance,current_affairs_linkage,why_correct,marks,negative_marks`
- **Gap/pending pointers CSV (source of truth for what to fix):** `/media/saksham/phone data/programming_projects/upsc_app/prelims_1995_2012_pending.csv`
  - Columns: `year,question_id,row_id,issues,reason,question,option_a,option_b,option_c,option_d,correct_answer,source_pointer`
  - **351 pending rows** (1995–2007: 32, 2008: 72, 2009: 71, 2010: 76, 2011: 100)

## What is pending (must be resolved)
1. **2011 — 100 rows:** `correct_answer` missing for all; many `question`/`option_a–d` incomplete or noisy (scanned bilingual OCR). Provide verified Q, options A–D, and correct answer for each 2011 question (Prelims GS Paper I, 2011).
2. **2008–2010 — 219 rows total with option gaps/noise:** `correct_answer` and `question` are present, but one or more of `option_a–d` is missing or unreliable due to OCR. Fill/replace with accurate option text (keep existing verified correct answers unless you can cite an official correction).
3. **1995–2007 — 32 rows:** specific `option_a–d` missing, largely figure/diagram/graph/map-based items where text was not extractable locally. Provide the correct option texts as per the official/standard question; if an option is inherently graphical, give the standard textual description used in authentic papers/keys (and note if not textually representable).

## Requirements
- **Accuracy first:** Use authentic UPSC Prelims question papers and official/authoritative answer keys for the respective years. Do not guess answers.
- **Match by key:** For each fix, match on `(year, question_id)` (and `row_id` where provided) so rows align exactly with the main CSV.
- **Complete fields:** For every pending row deliver non-empty `question`, `option_a`, `option_b`, `option_c`, `option_d`, `correct_answer`.
  - `correct_answer` format: a single lowercase letter `a`, `b`, `c`, or `d` (or `x` only if the official key explicitly marks cancelled/withdrawn for that question; include a brief note in a `notes` field if so).
- **Preserve existing data:** Do not alter rows/years outside the pending set except to correct an objectively wrong value in a pending row (if corrected, state the source).
- **Encoding/format:** UTF-8 CSV-safe text. No line breaks inside fields unless properly quoted. Keep punctuation/symbols faithful to the question (use plain text equivalents where needed).

## Deliverables (provide all)
1. **`prelims_1995_2012_fixes.csv`** — one row per pending item fixed, columns:
   `year,question_id,row_id,question,option_a,option_b,option_c,option_d,correct_answer,source,notes`
   - `source`: cite the paper/key source used (e.g. “UPSC Prelims 2011 GS Paper I official question paper & answer key”).
   - `notes`: mention if answer differs from main CSV, if question was cancelled, or if an option is a textual rendering of a figure.
2. **`prelims_1995_2012_completed_merge.csv`** (optional but preferred) — the 351 pending rows in the **main CSV schema** with all gaps filled, ready to replace those rows by `(year,question_id)`.
3. **`verification_report.md`** — brief report including:
   - counts by year: total pending, fixed, and any unresolved (with reason),
   - confirmation that every delivered row has non-empty `question, option_a, option_b, option_c, option_d, correct_answer`,
   - list of any questions with ambiguous/cancelled official answers or figure-only options.

## Acceptance criteria
- 0 unresolved pending rows, **or** every unresolved row explicitly listed with reason and the best authoritative source checked.
- 2008–2010: all 150/150 questions per year have complete, clean `option_a–d` and retain verified `correct_answer`.
- 2011: 100/100 rows have complete `question, option_a–d, correct_answer`.
- 1995–2007: all listed gap rows have complete `option_a–d` (text or faithful textual description) and verified `correct_answer`.

## Working approach (suggested)
1. Load `prelims_1995_2012_pending.csv` and group by `year`.
2. For each year, retrieve the authentic GS Paper I question paper and official answer key; fix all rows for that year in one pass.
3. Validate: no empty required fields, `correct_answer` in {a,b,c,d,x}, `(year,question_id)` unique.
4. Emit the deliverables above. Keep a changelog of any corrected answers vs current CSV values.