# data — UPSC datasets

Shared input for `upsc_app` and the note-building work. Read-only in practice:
the importers read these, nothing writes back here.

```
data/
├── final_pyq_data/       cleaned PYQ question banks (CSV)
│   ├── UPSC IAS PYQs - prelims_2013_2026.csv
│   ├── UPSC IAS PYQs - mains_2013_2026_corrected.csv
│   ├── UPSC IAS PYQs - csat_2013_2026.csv
│   ├── UPSC IAS PYQs - prelims_questions_complete_testbook.csv
│   ├── UPSC IAS PYQs - upsc_mains_pyqs_cleaned_clubbed.csv
│   ├── suspected_wrong_subjects.json
│   └── views.py                     importer helper
├── upsc_mains_json/      one JSON per paper per year, 2014–2025
└── upsc_pyq_extracted/   raw OCR/text of every paper + parsed questions.json
    ├── raw_text/
    ├── questions/
    └── review/
```

## Who reads what

| Consumer | Path |
|---|---|
| `upsc_app/tools/ingest_ppts.py` | `data/final_pyq_data/*.csv` (run from the tree root) |
| `upsc_app/local_scripts/setup_pyq_db.py` | `~/upsc_pyq_extracted` — **stale**, update to `data/upsc_pyq_extracted` before using |
| `scripts/extract_ca_from_ppt.py` | writes a CSV, drop it wherever you need it |

## Notes

- The `corrected` and `cleaned_clubbed` mains files are the ones to trust; the
  uncorrected exports are kept for diffing.
- Nothing here is generated at runtime, so there is no rebuild step. If you
  regenerate a CSV, keep the old one beside it with a date suffix.
