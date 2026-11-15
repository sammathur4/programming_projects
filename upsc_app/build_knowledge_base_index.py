#!/usr/bin/env python3
import os
from pathlib import Path

base = '/media/saksham/phone data/programming_projects/upsc_app/notes/UPSC_CSE_2027'
index_path = os.path.join(base, '00_MASTER_INDEX', 'Master_Index_Auto_Generated.md')

with open(index_path, 'w', encoding='utf-8') as f:
    f.write('# Auto Generated Master Index\n\n')
    f.write(f'Generated from: {base}\n\n')
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in ['.git']]
        md_files = [f for f in files if f.endswith('.md')]
        if md_files:
            rel = os.path.relpath(root, base)
            f.write(f'## {rel}\n\n')
            for mf in sorted(md_files):
                full = os.path.join(root, mf)
                f.write(f'- [{mf}]({os.path.relpath(full, base)})\n')
            f.write('\n')

print('Done')
