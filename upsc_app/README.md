# upsc_app — UPSC question bank

Django REST backend + Vite/React frontend, run together with Docker Compose.
It holds the syllabus tree, PYQ questions, attempts and notes for the UPSC
2027 preparation, and feeds the paper-level analytics.

```
upsc_app/
├── backend/            Django + DRF
│   ├── config/         settings, urls, wsgi
│   ├── syllabus/       models, views, admin, middleware, migrations
│   ├── media/          uploaded attachments
│   └── db.sqlite3      local database (backups: db.sqlite3.bak-*)
├── frontend/           Vite + React (src/, public/, dist/ = built bundle)
├── data/               curated CSVs (CA pointers, PYQ topic maps)
├── strategy/           PRD, tech plan, build tracker, study plans
├── local_scripts/      one-off importers and scrapers (not run by the app)
├── tools/              pptx/pdf ingestion pipeline (ingest_ppts.py, pdf_to_json.py)
├── notes/              generated study notes + master resource inventory
└── logs/               ingestion and conversion logs
```

## Run

```bash
cd upsc_app
docker compose up -d          # backend :8000, frontend :5173
docker compose down
```

Local Python without Docker:

```bash
cd upsc_app/backend
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py runserver 8000
```

## Ingest new material

Run from the tree root — the defaults are root-relative.

```bash
python3 upsc_app/tools/ingest_ppts.py <pdf-or-pptx-or-folder> \
    --out upsc_app/data/ingest --ocr-lang eng+hin
```

PYQ CSVs come from `data/final_pyq_data/`. Extracted per-year JSON lives in
`data/upsc_mains_json/`.

## Checks

```bash
cd upsc_app && docker compose config -q        # compose file is valid
cd upsc_app/backend && ../.venv/bin/python manage.py check
```

No test suite. The `local_scripts/` importers are run by hand and are not
covered by anything.
