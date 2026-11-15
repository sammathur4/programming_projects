#!/usr/bin/env python3
"""
ingest_ppts.py — image-heavy UPSC deck PDFs/PPTX -> complete text + figures + PYQ map.

Not a summariser: every page's full text is kept, in reading order, plus every
non-decorative figure and a link to the prelims/mains PYQs it relates to.

Stages
  1. extract  : per page, use the PDF text layer; OCR only pages that have none.
                Pull embedded figures (maps/diagrams), dedupe them by hash.
  2. map      : BM25 over your PYQ CSVs -> top-k related questions per page.
  3. render   : per-deck .md, one combined book.md + book.html (print to PDF).

Bulk-safe: SQLite manifest keyed on (path, size, mtime) => rerun resumes, never
re-does a finished deck. Parallel across decks, one PDF per worker.

  .venv/bin/python upsc_app/tools/ingest_ppts.py ~/Desktop/decks --out upsc_app/data/ingest
  .venv/bin/python upsc_app/tools/ingest_ppts.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# Tesseract spawns OpenMP threads that fight each other on 4-core laptops:
# 30 s/page at 200 dpi with default threading, 7.4 s with one thread. We get
# parallelism from running several decks at once instead.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

MIN_TEXT = 60          # chars below which a page counts as image-only -> OCR
MIN_IMG_W, MIN_IMG_H = 200, 150
BG_FRAC = 0.95         # image covering >95% of the page is the slide background
FIG_FRAC = 0.05        # ...unless the page has no text layer, then it IS the page
DRAWINGS_FOR_FIGURE = 25   # vector-only pages (charts drawn as shapes) -> render
DEV = re.compile(r"[\u0900-\u097F]")
FOOTER_SHARE = 0.5     # a line repeated on >50% of pages is a footer, not content

STOP = set("""a an the of and or in on for to from with by as at is are was were be been
this that these those it its which who whom whose what when where how why not no nor
all any both each few more most other some such only own same so than too very can will
just should now also into over under about after before between during through against
while if then there their them they we you your our he she his her has have had do does
did but i ii iii iv v vi up out per via vs etc
consider following statements statement correct given above answer select code options pairs
regard reference context marks words""".split())


# ---------------------------------------------------------------- extraction

def _lang(text: str) -> str:
    alpha = sum(c.isalpha() for c in text)
    dev = len(DEV.findall(text))
    return "hi" if alpha and dev / alpha > 0.15 else "en"


def _strip_ocr_noise(text: str) -> str:
    """eng+hin OCR hallucinates the other script on single-language pages.

    A page is one language, so lines written mostly in the losing script are
    noise. ponytail: a genuinely bilingual page would lose its minority lines;
    these decks are one language per slide, so that trade is free.
    """
    lines = text.splitlines()
    dev = sum(len(DEV.findall(l)) for l in lines)
    lat = sum(len(re.findall(r"[A-Za-z]", l)) for l in lines)
    if dev + lat < 20:
        return text
    latin_page = lat >= dev
    keep = []
    for line in lines:
        d, a = len(DEV.findall(line)), len(re.findall(r"[A-Za-z]", line))
        if latin_page and d > a:
            continue
        if not latin_page and a > d:
            continue
        keep.append(line)
    return "\n".join(keep)


def _figure_refs(doc, page, page_no, img_dir, seen, has_text):
    """Embedded images that are content, not background or bullet icons."""
    refs = []
    area = page.rect.get_area()
    for xref, _smask, w, h, *_rest in page.get_images(full=True):
        if w < MIN_IMG_W or h < MIN_IMG_H:
            continue
        rects = page.get_image_rects(xref)
        frac = max((((r & page.rect).get_area() / area) for r in rects), default=0.0)
        if frac >= BG_FRAC and has_text:
            continue                      # slide background
        if frac < FIG_FRAC and frac < BG_FRAC:
            continue                      # bullet icon / logo
        try:
            info = doc.extract_image(xref)
        except Exception:
            continue
        data = info["image"]
        key = hashlib.md5(data).hexdigest()
        if key in seen:
            refs.append(seen[key])
            continue
        name = f"p{page_no:03d}_{len(seen) + 1}.{info.get('ext', 'png')}"
        (img_dir / name).write_bytes(data)
        rel = f"images/{name}"
        seen[key] = rel
        refs.append(rel)
    return refs


def _render_page(page, page_no, img_dir, seen):
    """Fallback for pages whose figure is vector shapes, not a raster image."""
    data = page.get_pixmap(dpi=150).tobytes("png")
    key = hashlib.md5(data).hexdigest()
    if key in seen:
        return seen[key]
    name = f"p{page_no:03d}_render.png"
    (img_dir / name).write_bytes(data)
    seen[key] = f"images/{name}"
    return seen[key]


def extract_deck(job):
    """Worker: one deck in, one pages.jsonl out. A bad file must not kill the batch."""
    pdf_path, deck_dir, dpi, ocr_lang, do_ocr, cache_dir = job
    try:
        return _extract_deck(pdf_path, deck_dir, dpi, ocr_lang, do_ocr, cache_dir)
    except Exception as exc:  # noqa: BLE001 - one corrupt deck out of 1000
        return {"path": str(pdf_path), "deck_dir": str(deck_dir), "status": "failed",
                "pages": 0, "ocr_pages": 0, "figures": 0, "chars": 0,
                "seconds": 0.0, "error": f"{type(exc).__name__}: {exc}"[:300]}


def _extract_deck(pdf_path, deck_dir, dpi, ocr_lang, do_ocr, cache_dir):
    import pymupdf

    pdf_path, deck_dir, cache_dir = Path(pdf_path), Path(deck_dir), Path(cache_dir)
    img_dir = deck_dir / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    doc = pymupdf.open(pdf_path)
    seen: dict[str, str] = {}
    records = []

    for i, page in enumerate(doc, 1):
        text = page.get_text("text").strip()
        has_text = len(text) >= MIN_TEXT
        ocr_used = False
        if not has_text and do_ocr:
            png = page.get_pixmap(dpi=dpi).tobytes("png")
            # Same page showing up in several decks (maps, ads, repeats) is
            # OCR'd once ever. Cache is a plain file tree, no locking needed.
            key = hashlib.md5(png).hexdigest()
            cached = cache_dir / f"{key}.txt"
            if cached.exists():
                text = cached.read_text(encoding="utf-8").strip()
            else:
                from PIL import Image
                import pytesseract
                img = Image.open(io.BytesIO(png))
                text = pytesseract.image_to_string(img, lang=ocr_lang).strip()
                cached.write_text(text, encoding="utf-8")
            text = _strip_ocr_noise(text)
            ocr_used = True

        figures = _figure_refs(doc, page, i, img_dir, seen, has_text)
        if not figures and len(page.get_drawings()) >= DRAWINGS_FOR_FIGURE:
            figures.append(_render_page(page, i, img_dir, seen))
        figures = list(dict.fromkeys(figures))

        records.append({
            "deck": pdf_path.stem, "page": i, "lang": _lang(text),
            "ocr": ocr_used, "chars": len(text), "text": text, "figures": figures,
        })

    _drop_repeated_lines(records)

    with (deck_dir / "pages.jsonl").open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return {
        "path": str(pdf_path), "deck_dir": str(deck_dir), "status": "ok",
        "pages": len(records), "ocr_pages": sum(r["ocr"] for r in records),
        "figures": len(seen), "chars": sum(r["chars"] for r in records),
        "seconds": round(time.time() - t0, 1), "error": "",
    }


def _drop_repeated_lines(records):
    """Kill the 'Website > ... Telegram ...' footer that sits on every slide."""
    if len(records) < 4:
        return
    counts = Counter()
    for rec in records:
        for line in set(rec["text"].splitlines()):
            if line.strip() and len(line) < 120:
                counts[line] += 1
    limit = max(3, int(len(records) * FOOTER_SHARE))
    junk = {line for line, n in counts.items() if n >= limit}
    for rec in records:
        rec["text"] = "\n".join(l for l in rec["text"].splitlines() if l not in junk).strip()


# ---------------------------------------------------------------- PYQ mapping

def toks(s: str):
    s = re.sub(r"<[^>]+>", " ", s.lower())
    return [t for t in re.findall(r"[a-z][a-z\-]{2,}", s) if t not in STOP]


class BM25:
    """Sparse BM25. Questions are documents, a deck page is the query."""

    def __init__(self, docs):
        self.tf = [Counter(d) for d in docs]
        self.ln = [len(d) or 1 for d in docs]
        self.avg = sum(self.ln) / max(len(docs), 1)
        self.post = defaultdict(list)
        df = Counter()
        for i, c in enumerate(self.tf):
            df.update(c.keys())
            for t, f in c.items():
                self.post[t].append((i, f))
        n = len(docs)
        self.idf = {t: math.log(1 + (n - k + 0.5) / (k + 0.5)) for t, k in df.items()}

    def scores(self, query, k1=1.2, b=0.75):
        out = defaultdict(float)
        for t in set(query):
            idf = self.idf.get(t)
            if not idf:
                continue
            for i, f in self.post[t]:
                out[i] += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * self.ln[i] / self.avg))
        return out


def load_pyqs(path, exam, paper_col):
    rows = []
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            q = (row.get("question") or "").strip()
            if len(q) < 15:
                continue
            rows.append({
                "exam": exam, "year": row.get("year", ""),
                "paper": row.get(paper_col, "") or row.get("section", ""),
                "subject": row.get("subject", ""), "tags": row.get("tags", ""),
                "question": q,
            })
    return rows


def build_pyq_index(prelims_csv, mains_csv):
    rows = []
    if prelims_csv and Path(prelims_csv).exists():
        rows += load_pyqs(prelims_csv, "Prelims", "section")
    if mains_csv and Path(mains_csv).exists():
        rows += load_pyqs(mains_csv, "Mains", "paper")
    if not rows:
        return None, []
    docs = [toks(f"{r['question']} {r['tags']} {r['subject']} {r['paper']}") for r in rows]
    return BM25(docs), rows


def map_page(model, rows, text, top_k, min_score):
    """Page -> related PYQs. Short pages (covers, ads) are not mapped."""
    if model is None or len(text) < 250:
        return []
    s = model.scores(toks(text)[:400])
    best = sorted(s.items(), key=lambda kv: -kv[1])[:top_k]
    out = []
    for idx, score in best:
        if score < min_score:
            continue
        r = rows[idx]
        out.append({"exam": r["exam"], "year": r["year"], "paper": r["paper"],
                    "question": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", r["question"])).strip(),
                    "score": round(score, 1)})
    return out


# ---------------------------------------------------------------- rendering

def render_md(deck, recs, links, out_path, top=()):
    parts = [f"# {deck}\n"]
    if top:
        parts.append("\n## Most relevant PYQs for this deck\n")
        for q in top:
            parts.append(f"- **{q['exam']} {q['year']}** — {q['question'][:300]} "
                         f"*(score {q['score']})*\n")
    for rec in recs:
        parts.append(f"\n## Page {rec['page']}\n")
        if rec["text"]:
            parts.append(rec["text"] + "\n")
        for fig in rec["figures"]:
            parts.append(f"\n![figure p{rec['page']}]({fig})\n")
        rel = links.get(rec["page"]) or []
        if rel:
            parts.append("\n**Related PYQs**\n")
            for q in rel:
                parts.append(f"- **{q['exam']} {q['year']} {q['paper']}** — "
                             f"{q['question'][:300]} *(score {q['score']})*\n")
    out_path.write_text("".join(parts), encoding="utf-8")


CSS = """body{font:16px/1.55 system-ui,sans-serif;max-width:60em;margin:2em auto;padding:0 1em;color:#111}
h1{border-bottom:2px solid #333;padding-bottom:.3em}h2{margin-top:2em;color:#003}
img{max-width:100%;border:1px solid #ddd;margin:.6em 0}
.pyq{background:#f6f7f9;border-left:4px solid #4a6fa5;padding:.5em .8em;margin:.8em 0;font-size:.92em}
.pyq b{color:#204a87}.toc a{text-decoration:none}@media print{h2{page-break-before:always}}"""


def render_html(deck, recs, links, img_prefix, fh, top=()):
    esc = html.escape
    anchor = re.sub(r"\W+", "-", deck)
    fh.write(f'<section id="d-{esc(anchor)}"><h1>{esc(deck)}</h1>\n')
    if top:
        fh.write('<div class="pyq"><b>Most relevant PYQs for this deck</b><ul>')
        for q in top:
            fh.write(f'<li>{esc(q["exam"])} {esc(q["year"])} — '
                     f'{esc(q["question"][:300])} <i>({q["score"]})</i></li>')
        fh.write("</ul></div>\n")
    for rec in recs:
        fh.write(f'<h2 id="p{rec["page"]}">Page {rec["page"]}</h2>\n')
        if rec["text"]:
            body = esc(rec["text"]).replace("\n\n", "</p><p>").replace("\n", "<br>")
            fh.write(f"<p>{body}</p>\n")
        for fig in rec["figures"]:
            fh.write(f'<img src="{esc(img_prefix + fig)}" alt="page {rec["page"]} figure">\n')
        for q in links.get(rec["page"]) or []:
            fh.write(f'<div class="pyq"><b>{esc(q["exam"])} {esc(q["year"])} '
                     f'{esc(q["paper"])}</b> — {esc(q["question"][:400])} '
                     f'<i>({q["score"]})</i></div>\n')
    fh.write("</section>\n")


# ---------------------------------------------------------------- driver

def discover(srcs, out_dir):
    decks = []
    for src in srcs:
        p = Path(src).expanduser()
        if p.is_file() and p.suffix.lower() in (".pdf", ".pptx"):
            decks.append(p)
        elif p.is_dir():
            decks += [f for f in p.rglob("*")
                      if f.suffix.lower() in (".pdf", ".pptx") and not f.name.startswith(".")]
    out = []
    for deck in decks:
        if deck.suffix.lower() == ".pptx":
            pdf = out_dir / "_converted" / (deck.stem + ".pdf")
            if not pdf.exists():
                if not shutil.which("soffice"):
                    print(f"skip (no soffice to convert pptx): {deck}")
                    continue
                pdf.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                                "--outdir", str(pdf.parent), str(deck)],
                               check=False, capture_output=True)
            if pdf.exists():
                out.append(pdf)
        else:
            out.append(deck)
    return sorted(set(out), key=lambda f: f.stat().st_size, reverse=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sources", nargs="*", help="PDFs/PPTX or folders to walk")
    ap.add_argument("--out", default="upsc_app/data/ingest")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    ap.add_argument("--dpi", type=int, default=200, help="OCR render dpi (150 loses newspaper columns)")
    ap.add_argument("--ocr-lang", default="eng+hin")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--pyq-prelims", default="data/final_pyq_data/UPSC IAS PYQs - prelims_questions_complete_testbook.csv")
    ap.add_argument("--pyq-mains", default="data/final_pyq_data/UPSC IAS PYQs - upsc_mains_pyqs_cleaned_clubbed.csv")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--min-score", type=float, default=8.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not args.sources:
        ap.error("give at least one PDF/folder (or --selftest)")

    out = Path(args.out).expanduser()
    (out / "decks").mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(out / "manifest.db")
    db.execute("""CREATE TABLE IF NOT EXISTS decks(
        path TEXT PRIMARY KEY, size INT, mtime REAL, status TEXT, pages INT,
        ocr_pages INT, figures INT, chars INT, error TEXT, updated REAL)""")

    decks = discover(args.sources, out)
    if args.limit:
        decks = decks[:args.limit]
    print(f"{len(decks)} deck(s) -> {out}")

    def done(deck):
        if args.redo:
            return False
        row = db.execute("SELECT size, mtime, status FROM decks WHERE path=?",
                         (str(deck),)).fetchone()
        return bool(row and row[2] == "ok" and row[0] == deck.stat().st_size
                    and abs(row[1] - deck.stat().st_mtime) < 1)

    todo = [d for d in decks if not done(d)]
    print(f"{len(decks) - len(todo)} already done, {len(todo)} to extract")

    if todo:
        jobs = [(str(d), str(out / "decks" / d.stem), args.dpi, args.ocr_lang,
                 not args.no_ocr, str(out / "ocr_cache")) for d in todo]
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            for n, res in enumerate(pool.map(extract_deck, jobs), 1):
                db.execute("INSERT OR REPLACE INTO decks VALUES(?,?,?,?,?,?,?,?,?,?)",
                           (res["path"], Path(res["path"]).stat().st_size,
                            Path(res["path"]).stat().st_mtime, res["status"], res["pages"],
                            res["ocr_pages"], res["figures"], res["chars"],
                            res["error"], time.time()))
                db.commit()
                print(f"[{n}/{len(jobs)}] {Path(res['path']).name}: {res['pages']}p "
                      f"({res['ocr_pages']} OCR, {res['figures']} fig, {res['chars']} ch) "
                      f"{res['seconds']}s")

    model, rows = build_pyq_index(args.pyq_prelims, args.pyq_mains)
    print(f"PYQ index: {len(rows)} questions" if rows else "PYQ index: none (check --pyq-* paths)")

    book_md, book_html = out / "book.md", out / "book.html"
    links_fh = (out / "pyq_links.jsonl").open("w", encoding="utf-8")
    total_pages = total_links = 0
    with book_md.open("w", encoding="utf-8") as md, \
         book_html.open("w", encoding="utf-8") as ht:
        ht.write(f'<!doctype html><meta charset="utf-8"><title>Deck book</title>'
                 f"<style>{CSS}</style><nav class=toc><h1>Contents</h1><ul>")
        for deck in decks:
            ht.write(f'<li><a href="#d-{html.escape(re.sub(r"\\W+", "-", deck.stem))}">'
                     f'{html.escape(deck.stem)}</a></li>')
        ht.write("</ul></nav>\n")

        for deck in decks:
            pj = out / "decks" / deck.stem / "pages.jsonl"
            if not pj.exists():
                continue
            recs = [json.loads(line) for line in pj.open(encoding="utf-8")]
            links = {}
            for rec in recs:
                if rec["lang"] != "en":
                    continue      # questions are in English; Hindi is the same slide
                rel = map_page(model, rows, rec["text"], args.top_k, args.min_score)
                if rel:
                    links[rec["page"]] = rel
                    links_fh.write(json.dumps({"deck": deck.stem, "page": rec["page"],
                                               "pyqs": rel}, ensure_ascii=False) + "\n")
            # Rank by best single-page score: a deck that mentions a topic once
            # properly beats one that grazes it on fifty map pages.
            best, total = defaultdict(float), defaultdict(float)
            for rel in links.values():
                for q in rel:
                    k = (q["exam"], q["year"], q["question"])
                    best[k] = max(best[k], q["score"])
                    total[k] += q["score"]
            top = [{"exam": k[0], "year": k[1], "question": k[2], "score": round(v, 1)}
                   for k, v in sorted(best.items(), key=lambda kv: (-kv[1], -total[kv[0]]))[:10]]
            render_md(deck.stem, recs, links,
                      out / "decks" / deck.stem / f"{deck.stem}.md", top)
            render_html(deck.stem, recs, links, f"decks/{deck.stem}/", ht, top)
            md.write(f"\n\n---\n\n")
            md.write((out / "decks" / deck.stem / f"{deck.stem}.md").read_text(encoding="utf-8"))
            total_pages += len(recs)
            total_links += sum(len(v) for v in links.values())

        ht.write("</body>")
    links_fh.close()

    (out / "report.txt").write_text(
        f"decks: {len(decks)}\npages: {total_pages}\npyq links: {total_links}\n"
        f"book: {book_md}\nhtml: {book_html}\n", encoding="utf-8")
    print(f"\n{total_pages} pages, {total_links} PYQ links")
    print(f"book: {book_md}\nhtml: {book_html}  (open in a browser -> Print -> Save as PDF)")


# ---------------------------------------------------------------- self-check

def selftest():
    """Build a 3-page PDF in /tmp and assert the whole pipeline on it."""
    import pymupdf

    tmp = Path(tempfile.mkdtemp(prefix="ingest-selftest-"))
    src = pymupdf.open()
    p = src.new_page()
    p.insert_text((72, 120), "HELLO OCR SELF TEST", fontsize=30)
    png = p.get_pixmap(dpi=200).tobytes("png")

    doc = pymupdf.open()
    a = doc.new_page()
    a.insert_text((72, 72), "Plain text page about the Election Commission of India, "
                            "Article 324 and removal of the Chief Election Commissioner.")
    b = doc.new_page()
    b.insert_text((72, 72), "Figure page")
    for k in range(40):
        b.draw_line((72, 100 + k * 5), (400, 100 + k * 5))
    c = doc.new_page()
    c.insert_image(c.rect, stream=png)
    pdf = tmp / "deck.pdf"
    doc.save(pdf)
    doc.close()

    out = tmp / "out"
    (out / "decks").mkdir(parents=True)
    res = extract_deck((str(pdf), str(out / "decks" / "deck"), 200, "eng", True,
                        str(out / "ocr_cache")))
    assert res["status"] == "ok" and res["pages"] == 3, res

    recs = [json.loads(l) for l in (out / "decks" / "deck" / "pages.jsonl").open()]
    assert recs[0]["text"].startswith("Plain text") and not recs[0]["ocr"]
    assert recs[1]["figures"], "vector figure page produced no image"
    assert recs[2]["ocr"] and "HELLO" in recs[2]["text"].upper(), recs[2]["text"][:200]
    assert all(r["lang"] == "en" for r in recs)

    model, rows = build_pyq_index("data/final_pyq_data/UPSC IAS PYQs - prelims_questions_complete_testbook.csv",
                                  "data/final_pyq_data/UPSC IAS PYQs - upsc_mains_pyqs_cleaned_clubbed.csv")
    if rows:
        hit = map_page(model, rows, "The Opposition has moved a motion for the removal of the "
                                    "Chief Election Commissioner under Article 324(5). Removal "
                                    "requires a special majority in both Houses of Parliament on "
                                    "grounds of proved misbehaviour or incapacity, in the same "
                                    "manner as a judge of the Supreme Court. The Election "
                                    "Commission's independence and the conduct of free and fair "
                                    "elections are at stake.", 3, 1.0)
        assert hit, "PYQ mapping returned nothing for an obvious CEC question"

    links = {1: [{"exam": "Prelims", "year": "2019", "paper": "Polity",
                  "question": "CEC removal?", "score": 9.9}]}
    render_md("deck", recs, links, out / "deck.md")
    with (out / "deck.html").open("w", encoding="utf-8") as fh:
        render_html("deck", recs, links, "decks/deck/", fh)
    assert "Page 3" in (out / "deck.md").read_text() and "Related PYQs" in (out / "deck.md").read_text()
    assert (out / "decks" / "deck" / "images").is_dir()
    print(f"SELFTEST PASS ({res['pages']} pages, {res['figures']} figures) -> {tmp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
