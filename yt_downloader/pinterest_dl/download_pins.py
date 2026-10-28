#!/usr/bin/env python3
"""Download all pins from a scraped pins.json into a target directory.

Usage:
    python3 download_pins.py [destination_dir]

Defaults to ./pins_dl next to this script and reads pins.json from the
same directory, so it works no matter where you call it from.
"""
import json
import sys
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PINS = SCRIPT_DIR / "pins.json"
DEST = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else SCRIPT_DIR / "pins_dl"
DEST.mkdir(parents=True, exist_ok=True)

if not PINS.exists():
    sys.exit(f"ERROR: {PINS} not found. Run pull_pins.js first (see run_brave.sh).")

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

pins = json.loads(PINS.read_text())["pins"]
ok, fail = 0, 0
manifest = []

for p in pins:
    url = p["image"]
    if not url:
        fail += 1
        continue
    ext = Path(url.split("?")[0]).suffix or ".jpg"
    name = f"{p['order']:03d}_{p['id']}{ext}"
    out = DEST / name
    if out.exists() and out.stat().st_size > 8000:
        ok += 1
    else:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.pinterest.com/"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) < 5000:
                raise ValueError(f"too small ({len(data)} bytes)")
            out.write_bytes(data)
            ok += 1
            print(f"[OK]   {name:<32} {len(data)//1024:>5} KB  {p['width']}x{p['height']}")
        except Exception as e:
            fail += 1
            print(f"[FAIL] {name:<32} {e}")
            continue
    manifest.append({**p, "file": name, "local": str(out)})

(DEST / "manifest.json").write_text(json.dumps(manifest, indent=1))
print(f"\nDownloaded: {ok}  Failed: {fail}  ->  {DEST}")
