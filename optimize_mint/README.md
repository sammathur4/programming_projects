# optimize_mint

One-shot tuning for this laptop (Linux Mint 22.3, i5-6200U, 16 GB).

Reclaims stale swap, adds zram, trims boot services and autostart entries,
clears regenerable caches, caps the journal, and reports what still needs a
human decision.

## Usage

```bash
cd optimize_mint

python3 optimize_mint.py --list            # see the tasks
python3 optimize_mint.py --dry-run         # print every command, change nothing
python3 optimize_mint.py                   # interactive: y/n/a/q per task
python3 optimize_mint.py --yes             # run everything
python3 optimize_mint.py --only swap,boot  # subset
python3 optimize_mint.py --skip docker     # everything except some
python3 optimize_mint.py --include-risky   # also prune tagged docker images,
                                           # stopped containers, kill a duplicate
                                           # opencode pairing server
```

Run as your normal user, not root. It calls `sudo` itself and asks for the
password once. Every run logs to `~/.local/state/optimize-mint/`.

## Protections

Hard-coded; no flag overrides them:

- `whatsapp_bot/` — never copied, deleted, or cached out, and none of its
  processes (node, headless Chrome) are ever killed
- `~/Downloads/Telegram`
- `~/Desktop/listen`, `~/Desktop/wallpapers`
- the opencode server running the current session
- running dev servers (detected via `/proc` cwd/open files)
- system cron jobs, MySQL, Redis, printer/Bluetooth services

This script never moves code out of `programming_projects/`. The workspace is
resolved from `__file__`, so it works wherever the folder is mounted.

## Notes

- Boot-time unit changes and the GRUB timeout (10s → 2s) need a reboot.
- Autostart changes apply at next login; they are per-user files in
  `~/.config/autostart/` and revert by deleting them.
- Swap is only reclaimed when free RAM is at least 1.2× the swap size.
- The NTFS partition holding this workspace has no `fstab` entry; it is mounted
  by udisks. If it is now the only coding location, add a permanent mount
  (see the parent README's note) so a failed automount cannot hide the folder.
