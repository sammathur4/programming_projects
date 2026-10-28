#!/usr/bin/env python3
"""OCR a scanned UPSC PDF once, cache the text, print it.

    python3 pdf_ocr.py "papers/Prelims GS1 2025.pdf" --pages 1
    python3 pdf_ocr.py "papers/Mains GS1 2024.pdf"            # whole file
    python3 pdf_ocr.py --text-cache /tmp/opencode/ocr

Needs: pdf2image + pytesseract + pillow, and system tesseract + poppler.
The PYQPs folder ships a .venv with them; run this with that interpreter:

    "/media/.../02. PYQPs 2014-25/.venv/bin/python" pdf_ocr.py ...

Cached output is keyed by file content + page range + dpi, so reruns are free.
"""

import argparse
import hashlib
import sys
from pathlib import Path

CACHE = Path("/tmp/opencode/ocr_cache")


def _deps():
    try:
        from pdf2image import convert_from_path
        import pytesseract
        return convert_from_path, pytesseract
    except ImportError:
        sys.exit("need pdf2image + pytesseract (use the PYQPs .venv python)")


def ocr(pdf, pages=None, dpi=250, lang="eng"):
    """Return OCR text for a PDF. pages is a 1-based (first, last) tuple."""
    pdf = Path(pdf)
    convert_from_path, pytesseract = _deps()
    stamp = hashlib.sha1(
        f"{pdf.resolve()}|{pdf.stat().st_size}|{pages}|{dpi}|{lang}".encode()
    ).hexdigest()[:16]
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{pdf.stem[:60]}-{stamp}.txt"
    if cached.exists():
        return cached.read_text(encoding="utf-8")

    kwargs = {"dpi": dpi, "fmt": "jpeg"}
    if pages:
        kwargs["first_page"], kwargs["last_page"] = pages
    images = convert_from_path(str(pdf), **kwargs)
    out = []
    for number, image in enumerate(images, start=pages[0] if pages else 1):
        text = pytesseract.image_to_string(image, lang=lang)
        out.append(f"\n--- PAGE {number} ---\n{text}")
    cached.write_text("\n".join(out), encoding="utf-8")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf")
    ap.add_argument("--pages", help="e.g. 1 or 1-2")
    ap.add_argument("--dpi", type=int, default=250)
    ap.add_argument("--lang", default="eng")
    args = ap.parse_args()

    pages = None
    if args.pages:
        first, _, last = args.pages.partition("-")
        pages = (int(first), int(last or first))
    sys.stdout.write(ocr(args.pdf, pages, args.dpi, args.lang))


if __name__ == "__main__":
    main()
