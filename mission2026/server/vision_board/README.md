# Vision Board | 2025 | 2026 | 2027

An offline, dependency-free HTML vision board rebuilt from the Notion export
`4f9d701e-…-b78e5dc1-…` (page "Vision Board 2025 2026 2027").

## Open it

Double-click **`index.html`**, or:

```bash
xdg-open index.html
```

No server, no internet, no CDN — everything is local.

## What's in here

| Path | What |
|---|---|
| `index.html` | The board (single page) |
| `assets/` | 130 optimised images (max 1000 px, JPEG q82) |
| `preview-light.png` / `preview-dark.png` | Top-of-page previews in both themes |
| `preview-full.png` | Whole page in one image |

## Features

- **Light & dark mode** — follows your OS by default, with a toggle in the nav
  (top-right). Your choice is saved in `localStorage`. Force one with
  `index.html?theme=dark` or `?theme=light`.
- Sticky category nav with jump links, **scroll-spy** highlighting
- Hero with gradient title, opening quote, and the "Main Manifestation Mantra" card
- "Manifesting" chips list and the "Top Goals" checklist
- One callout card per Notion `<aside>` (25 cards), each with bullet goals and its images
- Masonry galleries for the loose image dumps
- **Lightbox** with prev/next, image counter, and arrow-key / Esc support
- Scroll-reveal animations, back-to-top button, reduced-motion support
- Fully responsive (5 → 3 → 2 columns)

## Notes on the rebuild

- Sections originally titled **"Women"** are retitled **"Confidence & Charm"** (images kept).
- The line *"Hit 100 body count"* was dropped.
- The empty *"Duplicate This"* template placeholder was removed.
- Repeated pin references (the `… 1.jpg` duplicates in Notion) are preserved.

## Rebuild / edit

Regenerate from the export with:

```bash
python3 ../build_vision_board.py
```

The script re-tokenises the markdown export, re-optimises every image, and
rewrites `index.html`. Tweak `MAX_DIM` / `QUALITY` / `RETITLE` / `DROP_LINES`
at the top of that script, or restyle via the `CSS` / `JS` blocks.

To refresh the preview images:

```bash
python3 ../render_vision_board_previews.py index.html
```
