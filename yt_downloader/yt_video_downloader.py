
#!/usr/bin/env python3

from pathlib import Path
import yt_dlp

# ==================================================
# CONFIGURATION
# ==================================================

DOWNLOAD_DIR = Path.home() / "Videos" / "YouTube"
ARCHIVE_FILE = DOWNLOAD_DIR / "downloaded.txt"

stats = {
    "downloaded": 0,
    "skipped": 0,
    "failed": 0,
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
        "js_runtimes": {"deno": {}},

        # Download and metadata options
        "writedescription": True,
        "writeinfojson": True,

        # Resume partial downloads
        "continuedl": True,
        "nopart": False,

        # Retry temporary failures
        "retries": 3,
        "fragment_retries": 5,
        "file_access_retries": 3,

        # Archive tracking
        "download_archive": str(ARCHIVE_FILE),

        # Merge video and audio
        "merge_output_format": "mkv",

        # Progress display
        "quiet": False,
        "noprogress": False,
        "ignoreerrors": False,
    }


# ==================================================
# DISPLAY
# ==================================================

def show_status(index, total, title, status):
    print("\n" + "=" * 65)
    print(f"VIDEO:  {index}/{total}")
    print(f"TITLE:  {title}")
    print(f"STATUS: {status}")
    print("-" * 65)


def show_summary(total, processed):
    print("\n" + "=" * 65)
    print("DOWNLOAD PROGRESS")
    print("=" * 65)
    print(f"Total videos        : {total}")
    print(f"Downloaded this run : {stats['downloaded']}")
    print(f"Already downloaded  : {stats['skipped']}")
    print(f"Failed              : {stats['failed']}")
    print(f"Processed           : {processed}/{total}")
    print(f"Remaining           : {max(0, total - processed)}")
    print("=" * 65)


# ==================================================
# DOWNLOAD ONE VIDEO
# ==================================================

def download_one(video_url, index=1, total=1, output_dir=None):
    output_dir = output_dir or DOWNLOAD_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    options = base_options()
    options["outtmpl"] = str(
        output_dir / f"{index:03d} - %(title)s.%(ext)s"
    )

    logger = DownloadLogger()
    options["logger"] = logger

    try:
        # Extract metadata first so the title is always displayed.
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(video_url, download=False)

            if not info:
                raise RuntimeError("YouTube returned no video information.")

            # A normal video URL should resolve to a single video.
            if info.get("_type") in ("playlist", "multi_video"):
                raise RuntimeError(
                    "This URL contains multiple videos. "
                    "Use the playlist URL mode instead."
                )

            title = info.get("title") or "Unknown title"
            video_id = info.get("id")

            show_status(index, total, title, "DOWNLOADING")

            # Archive entries are managed by yt-dlp.
            # download() returns a nonzero code on failure.
            result = ydl.download([video_url])

        if result != 0:
            stats["failed"] += 1
            reason = (
                logger.errors[-1]
                if logger.errors
                else f"yt-dlp returned exit code {result}"
            )
            print(f"\nFAILED: {title}")
            print(f"Reason: {reason}")
        else:
            stats["downloaded"] += 1
            print(f"\nSUCCESS: {title}")

    except Exception as error:
        stats["failed"] += 1
        print(f"\nFAILED: {video_url}")
        print(f"Reason: {type(error).__name__}: {error}")

    show_summary(total, 1)


# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        print("=" * 65)
        print("YOUTUBE SINGLE-VIDEO DOWNLOADER")
        print("=" * 65)
        url = [
            "https://www.youtube.com/watch?v=57J5UYoaXrc",
            "https://www.youtube.com/watch?v=y-AjqG4Lepc",
            "https://www.youtube.com/watch?v=lQsH8kVKoxs"
        ]

        if not url:
            print("ERROR: URL cannot be empty.")
        else:
            for index, video_url in enumerate(url, start=1):
                download_one(video_url, index=index, total=len(url))

    except KeyboardInterrupt:
        print("\nExiting.")


"""
"""