# Final_Notes — UPSC Sociology Optional 2027

This is a **content build**, not an application: chapter-wise sociology notes
for Paper 1 and Paper 2, each chapter tied to exact-wording PYQs (2013–2025)
and current-affairs examples. The plan and the definition of done live in
[`WORK_PLAN.md`](WORK_PLAN.md).

```
Final_Notes/
├── WORK_PLAN.md    deliverables, source priorities, build stages
└── _work/          build artefacts, all generated
    ├── pdf_inventory.tsv       every source PDF with page counts
    ├── pdf_text/               extracted text per PDF
    ├── lecture_durations.tsv   lecture runtimes
    └── transcribe_venv/        whisper transcription environment
```

## Run

Nothing to start. Read `WORK_PLAN.md`, then follow its build stages in order.
Source PDFs stay outside this folder — the inventory records their paths.

```bash
# re-build the PDF inventory
cd Final_Notes
ls _work/pdf_text | wc -l
```

## Notes

- `_work/` is disposable; regenerating it costs time, not data.
- The notes themselves are the deliverable. Nothing here is imported by another
  project, so breaking `_work/` cannot break the apps.
