from pathlib import Path
from datetime import datetime, timedelta
import time
import yt_dlp

# ==================================================
# CONFIGURATION
# ==================================================

DOWNLOAD_DIR = Path.home() / "Videos" / "YouTube"
ARCHIVE_FILE = DOWNLOAD_DIR / "downloaded.txt"
SLEEP_SECONDS = 5

# Date filter: last week to last 3 years (2024, 2025, 2026)
NOW = datetime.now()
ONE_WEEK_AGO = NOW - timedelta(days=7)
START_YEAR = 2024  # Include from 2024 onwards + last week

# Runtime counters
stats = {
    "downloaded": 0,
    "skipped": 0,
    "failed": 0,
    "filtered": 0,
}


# ==================================================
# LOGGING
# ==================================================


class DownloadLogger:
    def __init__(self):
        self.errors = []

    def debug(self, message):
        pass

    def info(self, message):
        pass

    def warning(self, message):
        print(f"WARNING: {message}")

    def error(self, message):
        self.errors.append(message)
        print(f"ERROR: {message}")


# ==================================================
# COMMON OPTIONS
# ==================================================


def base_options():
    return {
        "format": "bestvideo*+bestaudio/best",
        # YouTube JavaScript runtime
        "js_runtimes": {"deno": {}},
        # Resume partial downloads
        "continuedl": True,
        "nopart": False,
        # Retry temporary failures
        "retries": 3,
        "fragment_retries": 5,
        "file_access_retries": 3,
        # Preserve archive tracking
        "download_archive": str(ARCHIVE_FILE),
        # Merge separate audio and video
        "merge_output_format": "mkv",
        # Show normal download progress
        "quiet": False,
        "noprogress": False,
        "ignoreerrors": True,
    }


# ==================================================
# ARCHIVE HELPERS
# ==================================================


def load_archive():
    """Load IDs of successfully downloaded videos."""
    if not ARCHIVE_FILE.exists():
        return set()

    downloaded_ids = set()

    with ARCHIVE_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            parts = line.strip().split()

            if len(parts) >= 2:
                downloaded_ids.add(parts[-1])

    return downloaded_ids


# ==================================================
# DATE FILTERING
# ==================================================


def should_download(entry):
    """Filter videos to last week or years 2024, 2025, 2026."""
    if not entry:
        return False
    
    # Check upload date
    upload_date = entry.get("upload_date")
    timestamp = entry.get("timestamp") or entry.get("release_timestamp")
    
    # If we have upload_date as YYYYMMDD
    if upload_date:
        try:
            upload_dt = datetime.strptime(str(upload_date), "%Y%m%d")
            # Include if in last week OR year >= 2024
            if upload_dt >= ONE_WEEK_AGO or upload_dt.year >= START_YEAR:
                return True
            else:
                return False
        except (ValueError, TypeError):
            pass
    
    # If we have timestamp
    if timestamp:
        try:
            upload_dt = datetime.fromtimestamp(int(timestamp))
            if upload_dt >= ONE_WEEK_AGO or upload_dt.year >= START_YEAR:
                return True
            else:
                return False
        except (ValueError, TypeError, OSError):
            pass
    
    # If no date info available, skip to be safe
    return False


# ==================================================
# STATUS DISPLAY
# ==================================================


def show_status(index, total, title, status):
    print("\n" + "=" * 65)
    print(f"VIDEO: {index}/{total}")
    print(f"TITLE: {title}")
    print(f"STATUS: {status}")
    print("-" * 65)


def show_summary(total, processed, filtered_count):
    remaining = total - processed

    print("\n" + "=" * 65)
    print("PLAYLIST PROGRESS")
    print("=" * 65)
    print(f"Total videos       : {total}")
    print(f"Filtered out       : {filtered_count} (older than range)")
    print(f"Downloaded this run: {stats['downloaded']}")
    print(f"Already downloaded : {stats['skipped']}")
    print(f"Failed             : {stats['failed']}")
    print(f"Processed          : {processed}/{total}")
    print(f"Remaining          : {remaining}")
    print("=" * 65)


# ==================================================
# DOWNLOAD PLAYLIST
# ==================================================


def download_playlist(playlist_url):
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    print("\nReading playlist information...")

    # Extract playlist metadata first.
    try:
        extract_opts = base_options()
        extract_opts["ignoreerrors"] = True
        with yt_dlp.YoutubeDL(extract_opts) as ydl:
            playlist = ydl.extract_info(
                playlist_url,
                download=False,
            )

    except Exception as error:
        print(f"\nPLAYLIST ERROR: {error}")
        print("Attempting to continue with available entries...")
        try:
            extract_opts = base_options()
            extract_opts["ignoreerrors"] = True
            extract_opts["extract_flat"] = "in_playlist"
            with yt_dlp.YoutubeDL(extract_opts) as ydl:
                playlist = ydl.extract_info(
                    playlist_url,
                    download=False,
                )
        except Exception as error2:
            print(f"\nPLAYLIST ERROR: {error2}")
            print("No videos were processed.")
            return

    if not playlist:
        print("ERROR: YouTube returned no playlist information.")
        return

    entries = playlist.get("entries")

    if entries is None:
        print("ERROR: The supplied URL did not return a playlist.")
        return

    entries = list(entries)
    total = len(entries)
    playlist_title = playlist.get("title") or "Unknown Playlist"

    if total == 0:
        print("The playlist contains no accessible videos.")
        return

    playlist_dir = DOWNLOAD_DIR / playlist_title
    playlist_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nPlaylist: {playlist_title}")
    print(f"Total videos: {total}")
    print(f"Output folder: {playlist_dir}")
    print(f"Filter: Last week ({ONE_WEEK_AGO.strftime('%Y-%m-%d')}) or {START_YEAR}+ (2024,2025,2026)")
    print(f"Delay between videos: {SLEEP_SECONDS} seconds")

    downloaded_ids = load_archive()
    processed = 0
    filtered_count = 0

    # Process each playlist entry individually.
    for position, entry in enumerate(entries, start=1):
        try:
            if entry is None:
                stats["failed"] += 1
                processed += 1

                show_status(
                    position,
                    total,
                    "Unavailable video",
                    "FAILED - YouTube returned no video information",
                )
                show_summary(total, processed, filtered_count)
                continue

            video_id = entry.get("id")
            title = entry.get("title") or "Unknown title"

            if not video_id:
                stats["failed"] += 1
                processed += 1

                show_status(
                    position,
                    total,
                    title,
                    "FAILED - Video ID is missing",
                )
                show_summary(total, processed, filtered_count)
                continue

            # Apply date filter
            if not should_download(entry):
                filtered_count += 1
                processed += 1
                upload_date = entry.get("upload_date")
                date_str = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}" if upload_date and len(upload_date) == 8 else "unknown"
                show_status(
                    position,
                    total,
                    title,
                    f"FILTERED - Too old ({date_str}), outside range",
                )
                show_summary(total, processed, filtered_count)
                continue

            # Print title and index even when the video is skipped.
            if video_id in downloaded_ids:
                stats["skipped"] += 1
                processed += 1

                show_status(
                    position,
                    total,
                    title,
                    "SKIPPED - Already present in download archive",
                )
                show_summary(total, processed, filtered_count)
                continue

            video_url = f"https://www.youtube.com/watch?v={video_id}"

            show_status(
                position,
                total,
                title,
                "DOWNLOADING",
            )

            # Include the playlist position in the filename.
            options = base_options()
            options["outtmpl"] = str(
                playlist_dir / f"{position:03d} - %(title)s.%(ext)s"
            )

            logger = DownloadLogger()
            options["logger"] = logger
            options["ignoreerrors"] = True

            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    result = ydl.download([video_url])

                # yt-dlp returns a nonzero code for download failures.
                if result != 0:
                    reason = (
                        logger.errors[-1]
                        if logger.errors
                        else f"yt-dlp returned exit code {result}"
                    )
                    # Treat upcoming/premiere live events as skipped, not failed
                    reason_str = str(reason).lower()
                    if "live event will begin" in reason_str or ("premiere" in reason_str and "begin" in reason_str):
                        stats["skipped"] += 1
                        print(f"\nSKIPPED: {title}")
                        print(f"Reason: {reason}")
                    else:
                        stats["failed"] += 1
                        print(f"\nFAILED: {title}")
                        print(f"Reason: {reason}")

                else:
                    stats["downloaded"] += 1
                    print(f"\nSUCCESS: {title}")

                    # Update the local set for subsequent entries.
                    downloaded_ids.add(video_id)

            except Exception as error:
                error_str = str(error).lower()
                if "live event will begin" in error_str or ("premiere" in error_str and "begin" in error_str):
                    stats["skipped"] += 1
                    print(f"\nSKIPPED: {title}")
                    print(f"Reason: {error}")
                else:
                    stats["failed"] += 1
                    print(f"\nFAILED: {title}")
                    print(f"Reason: {type(error).__name__}: {error}")

            processed += 1
            show_summary(total, processed, filtered_count)

            # Wait between videos, but not after the last one.
            if position < total:
                print(f"\nWaiting {SLEEP_SECONDS} seconds before the next video...")
                time.sleep(SLEEP_SECONDS)

        except KeyboardInterrupt:
            print("\n\nInterrupted by user.")
            show_summary(total, processed, filtered_count)
            print("Run the script again to resume.")
            return

    print("\nAll playlist entries have been processed.")
    show_summary(total, processed, filtered_count)


# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    playlists = [
        {
            "name": "The Hindu Newspaper Editorial Analysis",
            "url": (
                "https://www.youtube.com/playlist?"
                "list=PLhNxZA1Rs2iQ7Wwv6JFEC3Nk5aJQzBh1x"
            ),
        },
        {
            "name": "Indian Express Editorial Analysis",
            "url": (
                "https://www.youtube.com/playlist?"
                "list=PLpuxPG4TUOR5NV73zely8EP9W9uper"
            ),
        },
    ]

    try:
        for index, playlist in enumerate(playlists, start=1):
            print("\n" + "#" * 75)
            print(f"PLAYLIST {index}/{len(playlists)}")
            print(f"NAME: {playlist['name']}")
            print("#" * 75)

            download_playlist(playlist["url"])

        print("\nAll playlists have been processed.")

    except KeyboardInterrupt:
        print("\nInterrupted by user. Run the script again to resume.")