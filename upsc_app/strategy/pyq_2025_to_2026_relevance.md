# PYQ 2025 → 2026 Relevance Map

Method: Jaccard keyword-overlap (words ≥4 chars) between each 2026 question and the best-matching 2025 question. Threshold for a "match" = 0.20 (prelims/GS) or 0.15 (sociology).

## Summary

| Segment | 2025 questions | 2026 questions | 2026 with a 2025 match | Relevance |
|---|---|---|---|---|
| Prelims GS | 100 | 99 | 33 (33%) | Moderate — about one-third of 2026 GS prelims recycled 2025 themes |
| Prelims CSAT | 80 | 80 | 18 (22.5%) | Low-moderate |
| Mains GS1 | 20 | 20 | 0 (0%) | Low — 2026 GS1 topics largely fresh vs 2025 |
| Mains Sociology Paper I | 28 | 28 | 13 (46%) | High — nearly half the themes carried over |
| Mains Sociology Paper II | 28 | 28 | 7 (25%) | Moderate |

## Reading

- Sociology Paper I shows the strongest year-on-year theme continuity (≈46%), so 2025 Paper I PYQs are the most useful predictor for 2026 Paper I.
- Sociology Paper II dropped to ≈25% overlap — 2026 Paper II questions are more novel.
- Prelims GS recycled ~33% of themes; CSAT ~22%.
- Mains GS1 2026 (as extracted) shows no strong keyword overlap with 2025 GS1 — topics shifted.

## Per-question mapping

See `upsc_app/data/pyq_2025_to_2026_map.csv` (255 rows: 99 prelims GS + 80 CSAT + 20 GS1 + 28 + 28 sociology), each 2026 question mapped to its closest 2025 counterpart with a similarity score.

## Caveats

- 2026 mains data is partial (GS1 + sociology only; GS2–GS4 and Essay not yet extracted).
- Keyword overlap ≠ true thematic equivalence; manual review recommended for high-stakes use.
- 2025 prelims section labels differ in naming from 2026, so section-based comparison was not used.