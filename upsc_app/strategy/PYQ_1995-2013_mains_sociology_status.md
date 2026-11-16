# PYQ 1995–2013 Mains + Sociology — Completion Status

**Target:** `/media/saksham/phone data/downloads/Opencode_upsc_plan - Mains + Sociology.csv`  
**Schema:** `id,question_id,year,paper,subject,question,section,marks,max_word_limit,source_question_ids,source_file,difficulty,nature,master_theme,syllabus_tags`  
**Scope:** Mains GS + Sociology optional, 1995–2013 only (Prelims out of scope).  
**Snapshot:** 2026-11-16 (latest). CSV total rows: **2790**. 1995–2013 Sociology rows: **624**. `duplicate question_id = 0`, `duplicate id = 0`. `id` range 1–3876 with gaps (includes missing original **`id 1570`**, unrecovered — no backup/source found in workspace). No commits/pushes made.

## Milestone 1 — Sociology QA & fix (1995–2013): COMPLETE (source-checked)
- Re-extracted/corrected all Sociology P1/P2 for 1995–2013 from source PDFs in `.../02. PYQPs 2014-25/PYQPs 1995–2013/`.
  - 1995–2012: `pdftotext` of `Sociology Optional Paper I|II <year>.pdf` (and manual structured fixes).
  - 2013: reconstructed from OCR texts `/tmp/Sociology_Optional_Paper_I_2013.pdf.txt`, `/tmp/Sociology_Optional_Paper_II_2013.pdf.txt`.
- Section/marks/max_word_limit/question_id set per paper; spot-verified against source structure/content (incl. 1995 main 60-mark questions, 2009–2012 corrected structures, 2013 P1/P2 reconstructed).
- Counts (P1, P2): 1995–2008 (14,14); 2009 (17,18); 2010 (24,19); 2011 (25,22); 2012 (26,25); 2013 (28,28) = **624 rows**.

## Milestone 2 — Mains GS 2013 completion (gs2/gs3/gs4): PARTIAL (best-effort, not fully spot-verified)
- `gs1`: 25 rows kept unchanged.
- `gs2`: **25** rows rebuilt/cleaned from `/tmp/GS2_mains_2013.pdf.txt` (OCR-derived, marker-based). Q1–20 set 10 marks/200 words, Q21–25 set 15/250 (heuristic). Not fully spot-verified vs `PYQPs 2013/GS2 mains 2013.pdf`.
- `gs3`: **28** rows rebuilt/cleaned/deduped from `/tmp/GS3_mains_2013.pdf.txt` (OCR-derived). Marks/limits derived from word markers (100→5, 200→10). Count/boundaries not fully verified vs `PYQPs 2013/GS3 mains 2013.pdf`.
- `gs4`: **14** rows rebuilt from `/tmp/GS4_mains_2013.pdf.txt` (Q1–8 theory/quotes + Q9–14 case studies; Q14 case text filled). Q9–Q13 case texts contain OCR noise/truncation; not fully spot-verified vs `PYQPs 2013/GS4 mains 2013.pdf`.
- **Gap:** gs2/gs3/gs4 require full spot-verification and completion (correct counts, subparts, question text, section, marks, max_word_limit) against source PDFs.

## Milestone 3 — Mains GS 2008–2012 extraction: INCOMPLETE / BLOCKED
- **2008:** No Mains GS PDFs present in `.../PYQPs 2008/` (directory contains only `Prelims GS Paper I 2008*.pdf` and `Sociology Optional Paper I|II 2008.pdf`). **Source gap — cannot extract without files.**
- **2009–2012:** Scanned Mains GS Paper I/II PDFs exist in `PYQPs 2009–2012/`. OCR attempted:
  - Eng-only OCR texts: `/tmp/Mains_GS_Paper_{I,II}_{2009,2010,2011,2012}.pdf.txt` (bilingual/garbled for reliable parsing).
  - Eng+Hin OCR (running during snapshot): `/tmp/ocr_mains_09_12_hin.py`, log `/tmp/ocr_mains_09_12_hin.log`. Ready: 2009 I/II, 2010 I/II enghin texts; 2011 I/II, 2012 I/II pending/incomplete at this snapshot.
- CSV state (reparsed from enghin OCR texts, **best-effort, not fully spot-verified**): **2009 gs1_paper1 = 18**, **2009 gs2_paper2 = 16**; **2010 gs1_paper1 = 20**, **2010 gs2_paper2 = 11**; **2011 gs1_paper1 = 17**, **2011 gs2_paper2 = 35**; **2012 gs1_paper1 = 22**, **2012 gs2_paper2 = 28** (167 rows total). Eng+hin OCR texts: `/tmp/Mains_GS_Paper_{I,II}_{2009-2012}.pdf.enghin.txt`. Question boundaries/subparts, marks, word limits, and completeness require manual spot-check/correction against `PYQPs 2009–2012/` source PDFs.
- **Gap:** Complete quality OCR (eng+hin) + careful parse + append + spot-check for all 2009–2012 Mains GS I/II against `PYQPs 2009–2012/` PDFs.

## Milestone 4 — Mains GS 1995–2007 refinement: PARTIAL
- Rows present in CSV (re-extracted from `pdftotext` of `PYQPs 1995–2007/Mains GS <year> (Paper I & II).pdf`): 1995 12/8; 1996 12/8; 1997 12/8; 1998 12/8; 1999 16/10; 2000 28 (gs1_paper1); 2001 13/16; 2002 28 (gs_mains); 2003 12/15; 2004 13/19; 2005 13/15; 2006 13/17; 2007 13/15 (gs1/gs2 or as noted).
- Fixes applied: 1995 manually restructured with sections; 1996–2007 systematically re-extracted; deduped `question_id`s (0 dupes remain); cleaned Examrace artifacts.
- **Gaps:** question boundaries/splits, marks/limits, and paper mapping (`gs1_paper1`/`gs2_paper2`/`gs_mains`) still need full refinement and **spot-check** against source PDFs (re-extraction is text-based/heuristic; some years may have subparts/boundaries needing correction).

## Milestone 5 — Integrity & hygiene: PARTIAL
- Duplicates: `question_id` duplicates = **0**, `id` duplicates = **0** (after dedupe).
- `id 1570`: **unresolved/unrecovered**. Investigated: not present in target CSV or `Opencode_upsc_plan - Prelims.csv`; no `*Mains*Sociology*` backup found in `/media/saksham/phone data/downloads` (top-level scan). No recoverable source/backup identified in available workspace.
- Global `id` sequence not normalized (gaps remain by design of current edits; `HAS_1570 False`).
- `/tmp` artifacts: removed `parse_*`, `fix_*`, `ocr*` scripts/logs/dirs (incl. `/tmp/ocr2008`), `*2013*.pdf.txt`, `Sociology_Optional_Paper_*2013*.pdf.txt`, and `Mains_GS_Paper_{I,II}_{2009-2012}*.txt/.enghin.txt` after extraction into CSV. No matching `*2013*.pdf.txt`, `parse_*`, `fix_*`, `ocr2013*`, `ocr_mains_09_12*`, or `Mains_GS_Paper_*` artifacts remain in `/tmp`.

## Definition of done — NOT MET
- **Met:** Sociology (1995–2013) present, structured, and spot-checked against source PDFs.
- **Not met:** Mains GS (1995–2013) not fully present, structured, and spot-checked.
  - Missing/unverified: GS 2008 (source absent), GS 2009–2012 I/II (mostly absent/unverified), 2012 gs2 partial, 2009 gs1 partial/unverified.
  - Unverified/incomplete: GS 2013 gs2/gs3/gs4.
  - Rough/unrefined: GS 1995–2007 (most years).
- **Blockers requiring user/external/manual action:** provision of 2008 Mains GS source PDFs; completion of reliable (eng+hin) OCR + careful parsing and manual spot-verification for scanned GS papers (2009–2013, and any 1995–2007 issues) to reach “spot-checked”.

## Evidence (key paths)
- CSV: `/media/saksham/phone data/downloads/Opencode_upsc_plan - Mains + Sociology.csv`
- Sources: `.../02. PYQPs 2014-25/PYQPs 1995–2013/` (note `PYQPs 2008/` has no Mains GS PDFs)
- OCR/text artifacts (in `/tmp`, see above): `GS2|GS3|GS4_mains_2013.pdf.txt`, `Sociology_Optional_Paper_I|II_2013.pdf.txt`, `Mains_GS_Paper_*2009-2012*`
