#!/usr/bin/env python3
import re
import sys
from pathlib import Path


def natural_sort_key(path: Path):
    parts = re.split(r'(\d+)', path.name)
    normalized = []
    for part in parts:
        if part.isdigit():
            normalized.append((0, int(part)))
        else:
            normalized.append((1, part.lower()))
    return normalized


def main():
    base_dir = Path(__file__).resolve().parent
    output_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else base_dir / "merged_all.md"

    markdown_files = sorted(
        [p for p in base_dir.glob("*.md") if p.is_file() and p.name != output_path.name],
        key=natural_sort_key,
    )

    if not markdown_files:
        print(f"No .md files found in {base_dir}")
        return 1

    with output_path.open("w", encoding="utf-8") as merged_file:
        for path in markdown_files:
            content = path.read_text(encoding="utf-8").rstrip()
            if not content:
                continue
            merged_file.write(f"\n\n# --- {path.name} ---\n\n")
            merged_file.write(content)
            merged_file.write("\n\n")

    print(f"Merged {len(markdown_files)} Markdown files into {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
