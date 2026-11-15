# yt_downloader

Standalone downloaders and helpers. Everything writes into
`~/Videos/YouTube/` (music and lecture MKVs that `sub_gen` and the study work
consume), so it does not care where this folder sits.

```
yt_downloader/
├── yt_downloader.py          playlist downloader: picks the next N undownloaded
│                             videos, tracks them in downloaded.txt
├── yt_video_downloader.py    single-video downloader (prompts for a URL)
├── wake_up_video.py          opens the morning video in the browser (cron 05:00)
├── videos_to_download.md     the working queue of URLs
├── pinterest_dl/             Pinterest puller (download_pins.py, pull_pins.js,
│                             pins.json, run_brave.sh)
└── .venv/                    yt-dlp + Telethon
```

## Run

```bash
cd yt_downloader
.venv/bin/python yt_downloader.py          # batch from the queue
.venv/bin/python yt_video_downloader.py    # one URL, interactive
.venv/bin/python wake_up_video.py          # also runs from system cron at 05:00
```

## Notes

- `DOWNLOAD_DIR` is hard-coded to `Path.home() / "Videos" / "YouTube"` in both
  downloaders. Change it there, not per-run.
- `downloaded.txt` in the download dir is the ledger — deleting it re-downloads
  everything.
- Interrupted downloads leave `.part`, `.ytdl` and `*-Frag*.part` files behind.
  They are safe to delete; clear them before blaming the space budget.
- Telethon credentials (if used) come from the environment, never from this
  folder.

## Check

```bash
.venv/bin/python -m py_compile yt_downloader.py yt_video_downloader.py
```
