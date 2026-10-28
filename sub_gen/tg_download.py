#!/usr/bin/env python3
"""Telegram channel/group video downloader.

Setup:
  1. Create an app at https://my.telegram.org -> get api_id + api_hash
  2. Put them in .env next to this script (copy .env.example)
  3. .venv/bin/python tg_download.py login
  4. .venv/bin/python tg_download.py <channel-or-group> [options]

Files are saved as:  <out>/<channel_name>/<YYYY-MM-DD>_<title>.mp4
Already-downloaded files are skipped, so runs are resume-friendly.

Examples:
  .venv/bin/python tg_download.py durov
  .venv/bin/python tg_download.py https://t.me/s/somechannel --since 2026-10-01 --limit 20
  .venv/bin/python tg_download.py -1001234567890 --max-size 500M --dry-run
"""

import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_FILE = SCRIPT_DIR / ".env"
SESSION_PATH = SCRIPT_DIR / "tg_session"
DEFAULT_OUT = SCRIPT_DIR / "output" / "telegram"

UNSAFE_CHARS = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]+')
TME_LINK = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]+)(?:/\d+)?/?$"
)


# ---------------------------------------------------------------- credentials

def load_env() -> None:
    """Read KEY=VALUE lines from .env without overriding real env vars."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def get_credentials() -> tuple[int, str]:
    api_id = os.environ.get("TG_API_ID", "").strip()
    api_hash = os.environ.get("TG_API_HASH", "").strip()
    if not api_id or not api_hash:
        sys.exit(
            "Missing TG_API_ID / TG_API_HASH.\n"
            f"Create them at https://my.telegram.org and put them in {ENV_FILE}\n"
            "(copy .env.example to .env and fill it in)."
        )
    if not api_id.isdigit():
        sys.exit("TG_API_ID must be a numeric value.")
    return int(api_id), api_hash


# --------------------------------------------------------------------- naming

def sanitize(text: str, max_len: int = 120) -> str:
    text = " ".join(text.split())                 # collapse whitespace
    text = UNSAFE_CHARS.sub("_", text)            # filesystem-unsafe chars
    text = re.sub(r"\s*(?:_\s*)+", "_", text)     # tidy up "_ _" patterns
    text = text.strip(" ._-")                     # leading/trailing junk
    if len(text) > max_len:
        text = text[:max_len].rstrip(" ._-")
    return text


def local_date(dt: datetime) -> str:
    return dt.astimezone().strftime("%Y-%m-%d")


def video_title(message) -> str:
    caption = (message.message or "").strip()
    if caption:
        # first non-empty line, kept short
        first_line = next((l for l in caption.splitlines() if l.strip()), "")
        return sanitize(first_line) or f"video_{message.id}"
    return f"video_{message.id}"


def parse_size(text: str) -> int | None:
    if not text:
        return None
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([KMG]?)B?", text.strip(), re.I)
    if not m:
        raise argparse.ArgumentTypeError(f"bad size: {text!r} (use e.g. 200M, 2G)")
    num = float(m.group(1))
    unit = m.group(2).upper()
    factor = {"": 1024**2, "K": 1024, "M": 1024**2, "G": 1024**3}[unit]  # default MB
    return int(num * factor)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Download videos from a Telegram channel or group."
    )
    p.add_argument(
        "target",
        nargs="?",
        help="Channel/group: @name, username, t.me link, or numeric ID "
             "(or the word 'login' to authorize)",
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT,
                   help=f"output root (default: {DEFAULT_OUT})")
    p.add_argument("--limit", type=int, default=None,
                   help="max number of videos to download")
    p.add_argument("--since", type=str, default=None,
                   help="only videos sent on/after this date (YYYY-MM-DD)")
    p.add_argument("--until", type=str, default=None,
                   help="only videos sent on/before this date (YYYY-MM-DD)")
    p.add_argument("--max-size", type=parse_size, default=None,
                   help="skip videos larger than this (e.g. 200M, 2G)")
    p.add_argument("--dry-run", action="store_true",
                   help="list what would be downloaded, don't download")
    return p.parse_args()


def parse_day(text: str, end: bool = False) -> datetime:
    try:
        dt = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        sys.exit(f"bad date: {text!r} (expected YYYY-MM-DD)")
    if end:
        dt += timedelta(days=1) - timedelta(seconds=1)
    return dt.replace(tzinfo=timezone.utc)


# ----------------------------------------------------------------- telethon

def normalize_target(raw: str) -> str:
    raw = raw.strip()
    if re.match(r"^(?:https?://)?(?:t\.me|telegram\.me)/c/", raw):
        sys.exit(
            "Private invite-style links (t.me/c/...) can't be resolved directly.\n"
            "Open the chat in Telegram, use 'Copy Profile/Invite Link', or pass "
            "the channel username/ID instead."
        )
    m = TME_LINK.match(raw)
    return m.group(1) if m else raw


def make_progress(label: str):
    is_tty = sys.stdout.isatty()
    state = {"last": -10}

    def callback(cur, total):
        if not is_tty or not total:
            return
        pct = int(cur * 100 / total)
        if pct >= state["last"] + 10 or pct == 100:
            state["last"] = pct
            mb, tot = cur / 1048576, total / 1048576
            sys.stdout.write(f"\r    {label}: {pct:3d}%  ({mb:.1f}/{tot:.1f} MB)")
            sys.stdout.flush()

    return callback


async def run_login(args: argparse.Namespace) -> None:
    api_id, api_hash = get_credentials()
    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await client.start()  # prompts for phone / code / 2FA in the terminal
    me = await client.get_me()
    print(f"\nLogged in as {me.first_name} (@{me.username or 'n/a'}). "
          f"Session saved to {SESSION_PATH}.session")
    await client.disconnect()


async def run_download(args: argparse.Namespace) -> None:
    api_id, api_hash = get_credentials()
    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        sys.exit(f"Not logged in yet. Run:  {Path(sys.argv[0]).name} login")

    target = normalize_target(args.target)
    try:
        entity = await client.get_entity(
            int(target) if re.fullmatch(r"-?\d+", target) else target
        )
    except Exception as exc:
        await client.disconnect()
        sys.exit(f"Could not open {args.target!r}: {exc}")

    folder_name = sanitize(
        getattr(entity, "username", None)
        or getattr(entity, "title", None)
        or f"chat_{entity.id}"
    )
    folder = args.out / folder_name
    since = parse_day(args.since) if args.since else None
    until = parse_day(args.until, end=True) if args.until else None

    print(f"Channel: {getattr(entity, 'title', None) or folder_name}")
    print(f"Saving to: {folder}")
    filters = []
    if since:
        filters.append(f"since {args.since}")
    if until:
        filters.append(f"until {args.until}")
    if args.max_size:
        filters.append(f"max {args.max_size // 1048576}MB")
    if args.limit:
        filters.append(f"limit {args.limit}")
    if filters:
        print("Filters: " + ", ".join(filters))
    if not args.dry_run:
        folder.mkdir(parents=True, exist_ok=True)

    downloaded = skipped = no_video = oversized = 0
    seen = 0

    async for msg in client.iter_messages(entity):
        if until and msg.date > until:
            continue          # newer than --until; older ones come next
        if since and msg.date < since:
            break             # we're past the window now
        if not msg.video:
            no_video += 1
            continue

        seen += 1
        size = getattr(msg.file, "size", None) if msg.file else None
        if args.max_size and size and size > args.max_size:
            oversized += 1
            print(f"  skip (too big, {size // 1048576}MB): "
                  f"{local_date(msg.date)} {video_title(msg)}")
            continue

        fname = f"{local_date(msg.date)}_{video_title(msg)}.mp4"
        path = folder / fname
        if path.exists() and path.stat().st_size > 0:
            skipped += 1
            continue

        if args.dry_run:
            print(f"  would download: {folder_name}/{fname}"
                  + (f"  ({size // 1048576}MB)" if size else ""))
            downloaded += 1
        else:
            label = fname[:60]
            print(f"  downloading: {fname}" + (f"  ({size // 1048576}MB)" if size else ""))
            part = path.with_suffix(path.suffix + ".part")
            try:
                await client.download_media(
                    msg, file=str(part), progress_callback=make_progress(label)
                )
                if sys.stdout.isatty():
                    sys.stdout.write("\r" + " " * 80 + "\r")
                part.replace(path)
                downloaded += 1
            except Exception as exc:
                print(f"\n    FAILED: {exc}")
                if part.exists():
                    part.unlink()

        if args.limit and (downloaded + skipped) >= args.limit and not args.dry_run:
            break
        if args.limit and downloaded >= args.limit and args.dry_run:
            break

    await client.disconnect()

    print(f"\nDone. {downloaded} {'listed' if args.dry_run else 'downloaded'}, "
          f"{skipped} already present, {oversized} oversized, "
          f"{no_video} messages without video scanned.")


def main() -> None:
    args = parse_args()
    load_env()
    import asyncio
    if not args.target:
        sys.exit("Usage: tg_download.py <channel|group|t.me-link> [options] "
                 "or: tg_download.py login")
    if args.target.lower() == "login":
        asyncio.run(run_login(args))
        return
    asyncio.run(run_download(args))


if __name__ == "__main__":
    main()
