# programming_projects

One folder per project. Each project is self-contained: its own code, data,
dependencies, and README. Nothing shared between projects except the machine.

```
programming_projects/
├── mission2026/        habit / study / fitness tracker (Flutter + Django + MySQL)
├── whatsapp_bot/       WhatsApp check-in + laptop-control bot (Node)
├── upsc_app/           UPSC question bank (Django + Vite)
├── sub_gen/            subliminal / affirmation video generator (Python + ffmpeg)
├── yt_downloader/      YouTube + Pinterest + Telegram downloaders, voice assistant
├── optimize_mint/      laptop tuning script (Python, stdlib only)
├── side_projects/      older experiments, kept for reference
│   ├── ourtube/
│   └── youtube_catalog/
└── .reorg-backup/      source snapshot taken before the 2026-10-22 reorg
```

## Projects

| Project | Stack | Entry point | Runs on |
|---|---|---|---|
| [mission2026](mission2026/README.md) | Flutter, Django REST, MySQL | `mission2026/run_server.sh` | :8000 |
| [whatsapp_bot](whatsapp_bot/README.md) | Node, whatsapp-web.js | `whatsapp_bot/run.sh bg` | :3000 |
| [upsc_app](upsc_app/) | Django + Vite/React | `upsc_app/backend/manage.py`, `upsc_app/frontend` | compose |
| [sub_gen](sub_gen/README.md) | Python, ffmpeg, espeak-ng | `sub_gen/sub_video_gen.py` | CLI |
| [yt_downloader](yt_downloader/) | Python, yt-dlp, Telethon | `yt_downloader/yt_downloader.py` | CLI |
| [optimize_mint](optimize_mint/README.md) | Python (stdlib only) | `optimize_mint/optimize_mint.py` | CLI |

### mission2026

The main project. Django serves both the REST API and the compiled Flutter web
app on one port, so there is no CORS or second server.

```bash
cd mission2026
./run_server.sh                    # http://localhost:8000/
```

- `mission2026/server/` — Django app (`api`, `vision_board`, `checkin_board`, `data/`)
- `mission2026/mission_app/` — Flutter app (`lib`, `android`, `ios`, `web`, `build/`)
- `mission2026/docs/ui_mockup/` — HTML design mockup + screenshots
- `mission2026/.venv/` — Python virtualenv (Django, DRF, PyMySQL, CORS)
- `mission2026/server/data/` — the six sheet exports + `Daily Subjects.csv`

Rebuild the web app with `cd mission2026/mission_app && flutter build web --release`.

### whatsapp_bot

Node bot that posts habit polls, collects check-ins, and accepts owner-only
`!` commands (screen control, `!task`, `!open`, `!mission`). It talks to
mission2026 over HTTP (`MISSION_API_URL` in `.env`), so it is independent of the
Django process.

```bash
cd whatsapp_bot
./run.sh bg        # start in background
./run.sh status    # is it alive? what does /status say?
./run.sh logs      # follow bot.log
```

### sub_gen

Turns a markdown/text script into a chaptered MP4: images → Ken Burns motion,
`espeak-ng` affirmations → layered/accelerated audio, ambience bed, ffmpeg
concat. Manifests live at the top level, generated media in `cache/` and
`output/`, the music bed in `assets/girlfriends/`.

```bash
cd sub_gen
python3 sub_video_gen.py --dry-run
python3 sub_video_gen.py --script gf_manifest_10k.txt --out output/gf_manifest_10k.mp4
```

### yt_downloader

Standalone downloaders and helpers that `sub_gen` consumes media from:

```bash
cd yt_downloader
.venv/bin/python yt_downloader.py
.venv/bin/python yt_video_downloader.py
.venv/bin/python wake_up_video.py      # opens the morning video (also run by cron at 05:00)
```

`pinterest_dl/` pulls pins, `voice-assistant/` holds the local speech model.

### optimize_mint

Tuning script for this laptop. Reclaims stale swap, adds zram, trims boot
services and autostart entries, clears caches. Never touches `whatsapp_bot/`
or the Telegram downloads.

```bash
cd optimize_mint
python3 optimize_mint.py --dry-run
python3 optimize_mint.py --only swap,boot
```

### side_projects

Older experiments (`ourtube/video-finder-algorithm`, `youtube_catalog`). They
have their own `side_projects/.venv`; the ourtube DB path is now resolved
relative to its own script instead of the old `~/Desktop/...` location.

## Conventions

- **One project, one folder, one README.** No project reaches into another's
  files; they talk over HTTP or via files you pass explicitly.
- **Dependencies stay inside the project** (`.venv/`, `node_modules/`), never at
  this root.
- **Generated data stays inside the project** (`build/`, `cache/`, `output/`,
  `node_modules/`) and is git-ignored.
- **No absolute `/home/...` or `/media/...` paths in code** — resolve relative to
  `__file__` or the project root.

## Services

```bash
# Mission 2026 backend + web app
cd mission2026 && ./run_server.sh

# WhatsApp bot
cd whatsapp_bot && ./run.sh bg
```

Both are plain processes (no systemd unit), so they need starting after a
reboot. The bot's 4 AM wake-up and 7 AM mission poll are cron jobs inside the
Node process (`node-cron`), not system cron.

## Reorg backup

`.reorg-backup/sources-YYYYMMDD-HHMM/` contains a source-only copy (no venvs,
node_modules, caches, media) taken before the 2026-10-22 reorganization. Once
everything is verified, delete it with `rm -rf .reorg-backup`.
