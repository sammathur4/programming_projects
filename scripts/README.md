# scripts — shared one-off generators

Loose helpers used by the UPSC work that did not belong to a single app.

```
scripts/
├── extract_ca_from_ppt.py        read a current-affairs PPTX, emit a categorised CSV
└── generate_laxmikanth_notes.py  append chapter-wise Laxmikanth notes to a master MD
```

## Run

```bash
python3 scripts/extract_ca_from_ppt.py <input.pptx> [output.csv]
python3 scripts/generate_laxmikanth_notes.py
```

## Notes

- `generate_laxmikanth_notes.py` still hard-codes its output path
  (`/media/saksham/80645C95645C9030/.../GS2_Laxmikanth_Chapterwise_Ultimate_Notes.md`).
  Fix that to a relative path before re-running it, or it writes to the other
  drive.
- `extract_ca_from_ppt.py` needs `python-pptx`; the root `.venv` has it.
