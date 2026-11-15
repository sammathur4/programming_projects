#!/usr/bin/env python3
import os
import re

BASE_PATH = "/media/saksham/80645C95645C9030/saksham/EXAM/01 upsc sociology 2027/GS Paper 2 — Governance & Polity/Polity/Handbook"
NOTES_FILE = os.path.join(BASE_PATH, "GS2_Laxmikanth_Chapterwise_Ultimate_Notes.md")

def append_chapter(content):
    with open(NOTES_FILE, 'a', encoding='utf-8') as f:
        f.write('\n\n' + content + '\n\n---\n')

def get_last_chapter():
    if not os.path.exists(NOTES_FILE):
        return 0
    with open(NOTES_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    # Find all chapter numbers like "## N." or "## N "
    matches = re.findall(r'##\s*(\d+)\.', content)
    if matches:
        return int(matches[-1])
    return 0

def main():
    last = get_last_chapter()
    print(f"Last chapter found: {last}")
    # This script is now designed to be used by the automation system
    # The actual content generation is handled by opencode agents
    # via auto_runner_laxmikanth.sh
    print("Use auto_runner_laxmikanth.sh for automated chapter-by-chapter generation")

if __name__ == '__main__':
    main()
