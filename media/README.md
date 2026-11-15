# media — generated and downloaded media

Large files that are produced or pulled by the projects, kept out of the code
folders so that `du` on a project means something.

```
media/
└── YouTube/    12 GB of downloaded MKVs (music videos, lectures)
```

## Notes

- `YouTube/` is a **stale cache**. `yt_downloader` writes to
  `~/Videos/YouTube`, not here, and no code in this tree reads this path.
  Everything in it can be deleted or merged into `~/Videos/YouTube` — check for
  duplicates first, several files exist in both places.
- Git-ignored (`.gitignore`: `media/YouTube/`).
- New generated media belongs inside the project that makes it
  (`sub_gen/output/`, `upsc_app/data/ingest/`), not here. This folder is only
  for orphaned bulk media.
