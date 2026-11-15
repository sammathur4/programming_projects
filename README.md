# programming_projects

All work in one tree. Code projects are self-contained (own deps, own README);
generated data, media and old work live in the group folders at the bottom.

```
programming_projects/
├── start_all.py          start / stop / status the whole local stack
│
├── mission2026/          habit + study + fitness tracker … Django API + Flutter web   :8001
├── whatsapp_bot/         WhatsApp check-in & laptop-control bot (Node)                :3000
├── upsc_app/             UPSC question bank … Django + Vite/React (Docker)            :8000 / :5173
├── Store_Front/          Django e-commerce demo storefront                            :8000
├── Final_Notes/          UPSC Sociology 2027 notes build (content, not an app)
├── sub_gen/              subliminal / affirmation video generator (Python + ffmpeg)
├── yt_downloader/        YouTube, Pinterest and Telegram downloaders, wake-up video
├── optimize_mint/        laptop tuning script (Python, stdlib only)
│
├── data/                 UPSC datasets: PYQ csVs, per-year Mains JSON, extracted text
├── media/                large generated media (downloaded video cache)
├── scripts/              one-off generator scripts shared by the UPSC work
├── archive/              old personal files kept but not worked on
├── old_projects/         58 archived side projects (2019–2024, reference only)
├── side_projects/        newer experiments (iHatePDF, prelims-arena, ourtube, …)
├── upsc/                 Obsidian study vault — syllabus, notes, newspapers (13 GB)
└── .reorg-backup/        source snapshot from before the 2026-10-22 reorg
```

## Start everything

```bash
python3 start_all.py              # docker compose + bot + Mission 2026 + public tunnel
python3 start_all.py status       # what is up, and the public Mission 2026 URL
python3 start_all.py stop         # stop everything
python3 start_all.py --dry-run    # print the commands, run nothing
```

| Port | Service | Started by |
|---|---|---|
| 8000 | upsc_app backend | `docker compose` in `upsc_app/` |
| 5173 | upsc_app frontend (Vite) | `docker compose` in `upsc_app/` |
| 3000 | WhatsApp bot | `whatsapp_bot/run.sh bg` |
| 8001 | Mission 2026 | `mission2026/run_server.sh 8001` |

Mission 2026 is published through a free `localhost.run` ssh tunnel, so
`start_all.py status` prints a random `https://<id>.lhr.life` URL that changes
every start.

## Projects

| Project | Stack | Entry point |
|---|---|---|
| [mission2026](mission2026/README.md) | Flutter, Django REST, MySQL | `mission2026/run_server.sh` |
| [whatsapp_bot](whatsapp_bot/README.md) | Node, whatsapp-web.js | `whatsapp_bot/run.sh bg` |
| [upsc_app](upsc_app/README.md) | Django, Vite/React, Docker | `docker compose up -d` |
| [Store_Front](Store_Front/README.md) | Django, SQLite | `python manage.py runserver` |
| [Final_Notes](Final_Notes/README.md) | Markdown build | `Final_Notes/WORK_PLAN.md` |
| [sub_gen](sub_gen/README.md) | Python, ffmpeg, espeak-ng | `sub_gen/sub_video_gen.py` |
| [yt_downloader](yt_downloader/README.md) | Python, yt-dlp, Telethon | `yt_downloader/yt_downloader.py` |
| [optimize_mint](optimize_mint/README.md) | Python, stdlib | `optimize_mint/optimize_mint.py` |
| [side_projects](side_projects/README.md) | mixed | per sub-project |
| [old_projects](old_projects/README.md) | mixed | archive only |

## Conventions

- **One project, one folder, one README.** No project reaches into another's
  files; they talk over HTTP or via paths you pass explicitly.
- **Dependencies stay inside the project** (`.venv/`, `node_modules/`), never at
  this root. The root `requirements.txt` is a historical aggregate.
- **Generated data stays inside the project** (`build/`, `cache/`, `output/`,
  `node_modules/`) and is git-ignored.
- **Resolve paths from `__file__`**, not from `Path.home()` or a `/media/...`
  literal. A few older scripts still hard-code absolute paths; that is a known
  defect, not a pattern to copy.
- **This drive is NTFS (`fuseblk`).** Executable bits do not survive a copy, so
  invoke scripts as `bash run.sh`, not `./run.sh`, when in doubt. File watchers
  often miss changes — re-run checks explicitly.

## Services are plain processes

No systemd units. After a reboot `:8000`, `:3000` and `:8001` are all down. The
bot's 04:00 wake-up and 07:00 mission poll are `node-cron` jobs inside the Node
process, not system cron. `yt_downloader/wake_up_video.py` is the only real cron
job (05:00).

## Reorg backup

`.reorg-backup/sources-YYYYMMDD-HHMM/` is a source-only copy (no venvs,
node_modules, caches, media) taken before the 2026-10-22 reorganisation. The git
history now covers everything in it, so it can be deleted with
`rm -rf .reorg-backup` once you are satisfied nothing was lost.
