# Workspace conventions

## Default output directory

All files created for the user — documents, PRDs, plans, research, scripts, generated data, assets, and verification screenshots — belong under:

```
/media/saksham/phone data/programming_projects/
```

Put each file inside the project that owns it:

| Project | Path |
|---|---|
| UPSC app / PRDs / strategy | `upsc_app/` |
| Mission 2026 habit tracker | `mission2026/` |
| WhatsApp check-in bot | `whatsapp_bot/` |
| Subliminal video generator | `sub_gen/` |
| YouTube downloader | `yt_downloader/` |
| Other experiments | `side_projects/` |

Rules:

- Never create deliverables in `/home/saksham`, the filesystem root, or a project's `dist/`/`build/` output.
- Prefer the owning project's existing folder (`strategy/`, `docs/`, `notes/`, etc.) over creating a new top-level directory.
- Throwaway runtime files may go to `/tmp/opencode`, but they are not deliverables and must be cleaned up.
- If the right location is genuinely unclear, put the file in `programming_projects/side_projects/` and say so rather than writing outside the tree.
- Only write outside the tree when the user explicitly asks for that exact path or when editing tool configuration (for example `~/.config/opencode/`).

## Current deliverables

- UPSC UI/UX PRD: `upsc_app/strategy/PRD.md`
