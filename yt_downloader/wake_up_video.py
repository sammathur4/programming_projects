#!/usr/bin/env python3

import webbrowser
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# ===== CONFIGURATION =====
VIDEO_URL = "https://www.youtube.com/watch?v=aLX6I-e5nrk"
START_AT_SECONDS = 0
# =========================


def main():
    parsed = urlparse(VIDEO_URL)
    params = parse_qs(parsed.query)

    # Add the starting timestamp to the YouTube URL
    params["t"] = [str(START_AT_SECONDS)]

    video_url = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))

    print(f"Opening YouTube: {video_url}")
    webbrowser.open(video_url)


if __name__ == "__main__":
    main()
