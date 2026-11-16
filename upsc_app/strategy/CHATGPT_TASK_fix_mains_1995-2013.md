# Task: Complete UPSC Mains + Sociology PYQ CSV (1995–2013)

## Goal
Make `/media/saksham/phone data/downloads/Opencode_upsc_plan - Mains + Sociology.csv` complete, structured, and **spot-checked** for **Mains GS + Sociology optional (1995–2013 only)**. Prelims CSV is out of scope.

## Files / paths
- **Target CSV (edit this):** `/media/saksham/phone data/downloads/Opencode_upsc_plan - Mains + Sociology.csv`
- **Gaps list (use as checklist):** `upsc_app/strategy/PYQ_1995-2013_mains_gaps.csv` (38 items: missing sources, unverified/partial OCR rows, refinement needed, integrity gap)
- **Status/gap notes:** `upsc_app/strategy/PYQ_1995-2013_mains_sociology_status.md`
- **Source PDFs:** `/media/saksham/80645C95645C9030/saksham/EXAM/01 upsc sociology 2027/02. PYQPs 2014-25/PYQPs 1995–2013/`
  - GS 2009–2012: `PYQPs 2009–2012/Mains GS Paper I|II <year>.pdf` (scanned)
  - GS 2013: `PYQPs 2013/GS1|GS2|GS3|GS4 mains 2013.pdf`
  - GS 1995–2007: `PYQPs 1995–2007/Mains GS <year> (Paper I & II).pdf` (text-extractable, Examrace-compiled)
  - Sociology: `PYQPs 1995–2013/Sociology Optional Paper I|II <year>.pdf`

## CSV schema (keep exact columns/order)
`id,question_id,year,paper,subject,question,section,marks,max_word_limit,source_question_ids,source_file,difficulty,nature,master_theme,syllabus_tags`

## Current state (evidence)
- Total rows: **2790**. `DUP_QID=0`, `DUP_ID=0`. `id` gaps exist; **original `id 1570` missing/unrecovered** (no backup found).
- **Sociology 1995–2013: complete/spot-checked (624 rows)** — do not regress; only fix if you find a verified error against source.
- **Mains GS 1995–2013: NOT fully present/structured/spot-checked.**
  - **2008 GS:** Mains GS Paper I/II PDFs absent in `PYQPs 2008/` (source unavailable) — cannot add without source; document as explicit gap.
  - **2009–2012 GS:** OCR-extracted rows present but **unverified/partial** (2009 gs1 18/gs2 16, 2010 20/11, 2011 17/35, 2012 22/28). Boundaries/subparts, marks, word limits, text, and counts need spot-check/correction against source PDFs.
  - **2013 GS:** `gs1` 25 kept (verify only if errors found). `gs2` 25, `gs3` 28, `gs4` 14 are OCR-derived and **unverified** (possible count/boundary/text/marks issues; gs4 case studies noisy) — verify/correct against `GS2|GS3|GS4 mains 2013.pdf`.
  - **1995–2007 GS:** re-extracted/restructured but **needs refinement/spot-check** (question boundaries/splits, marks, max_word_limit, section, paper mapping `gs1_paper1`/`gs2_paper2`/`gs_mains`, question_id sequencing) against `Mains GS <year> (Paper I & II).pdf`.

## What to do (work through `PYQ_1995-2013_mains_gaps.csv`)

### 1) Mains GS 2008–2012
- **2008:** Document clearly as source gap (Mains GS PDFs missing in `PYQPs 2008/`). Add rows only if source files are provided/found.
- **2009–2012:** For each paper in gaps CSV (`unverified_partial`), open the source PDF and **spot-check every row**:
  - Ensure **all questions/subparts** present (split/merge/add missing as needed).
  - Fix `question` text (complete, clean OCR noise/Hindi artifacts), `section`, `marks`, `max_word_limit`.
  - Ensure correct `paper`, `year`, `subject`, `source_file`, `question_id` sequencing (`{year}-{paper}-qN` or consistent scheme).
  - Verify counts/structure against the actual paper.
- If you OCR again, use reliable OCR (e.g. eng+hin for bilingual scans) and parse carefully; final CSV must reflect verified content.

### 2) Mains GS 2013 (gs2/gs3/gs4)
- Spot-check against `PYQPs 2013/GS2 mains 2013.pdf`, `GS3 mains 2013.pdf`, `GS4 mains 2013.pdf`.
- Correct counts, subparts, question text, section, marks, max_word_limit; remove fragments/noise.
- Keep `gs1` unchanged unless a verified error is found.

### 3) Mains GS 1995–2007 refinement
- For each paper in gaps CSV (`refinement_needed`), spot-check against `PYQPs 1995–2007/Mains GS <year> (Paper I & II).pdf`.
- Clean artifacts, fix question boundaries/subparts, marks, max_word_limit, section.
- Fix paper mapping (`gs1_paper1` / `gs2_paper2` / `gs_mains`) and `question_id` sequencing to match the source.

### 4) Integrity & hygiene
- `id 1570` is missing/unrecovered: keep documented as unrecoverable unless a backup/source is found to restore it.
- Ensure **no unintended duplicate `id` or `question_id`** and consistent ids/question_ids (global renumbering acceptable if consistent; document if you change scheme).
- Remove unneeded temp/OCR artifacts in `/tmp` (`*2013*.pdf.txt`, `parse_*`, `ocr*`, `Mains_GS_Paper_*`, etc.) once no longer needed.

## Definition of done (must satisfy)
- **All Sociology (1995–2013)** and **all Mains GS (1995–2013)** questions are present in the CSV, correctly structured, and **spot-checked against source PDFs**.
- **All known/irrecoverable gaps explicitly documented** with evidence (e.g. 2008 Mains GS source PDFs absent; id 1570 unrecovered), in a short note/update to `PYQ_1995-2013_mains_sociology_status.md` or a gaps-resolved section.
- CSV consistent (no unintended duplicate ids/question_ids). `/tmp` temp artifacts cleaned.

## Deliverables / evidence
- Updated target CSV.
- Updated `PYQ_1995-2013_mains_gaps.csv` (mark resolved items or add resolution notes) and/or updated status doc listing what was verified/fixed and any remaining gaps with evidence.
- Brief summary: counts by year/paper for 1995–2013 (GS + Sociology) and confirmation of spot-check against sources.
