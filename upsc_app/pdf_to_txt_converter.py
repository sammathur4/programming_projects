#!/usr/bin/env python3
import os
import sys
import subprocess
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

SOURCE_DIR = "/media/saksham/80645C95645C9030/saksham/EXAM/01 upsc sociology 2027"
LOG_DIR = "/media/saksham/phone data/programming_projects/upsc_app/pdf_conversion_logs"
TRACKER = os.path.join(LOG_DIR, "conversion_tracker.json")
PROGRESS = os.path.join(LOG_DIR, "progress.json")

os.makedirs(LOG_DIR, exist_ok=True)

def load_tracker():
    if os.path.exists(TRACKER):
        try:
            with open(TRACKER, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_tracker(tracker):
    with open(TRACKER, 'w') as f:
        json.dump(tracker, f, indent=2)

def load_progress():
    if os.path.exists(PROGRESS):
        try:
            with open(PROGRESS, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"total": 0, "done": 0, "failed": 0, "scanned": 0}

def save_progress(progress):
    with open(PROGRESS, 'w') as f:
        json.dump(progress, f, indent=2)

def convert_pdf(pdf_path, tracker):
    pdf_path = str(pdf_path)
    txt_path = pdf_path.replace('.pdf', '.txt')
    
    if txt_path in tracker:
        return 'skip'
    
    # Check if txt already exists and is non-empty
    if os.path.exists(txt_path) and os.path.getsize(txt_path) > 10:
        tracker[txt_path] = {
            "pdf": pdf_path,
            "status": "DONE_EXISTS",
            "size_kb": os.path.getsize(txt_path) // 1024,
            "converted_at": datetime.now().isoformat()
        }
        return 'exists'
    
    try:
        # Try pdftotext with layout
        result = subprocess.run(
            ['pdftotext', '-layout', pdf_path, txt_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300
        )
        
        if os.path.exists(txt_path) and os.path.getsize(txt_path) > 10:
            tracker[txt_path] = {
                "pdf": pdf_path,
                "status": "DONE",
                "size_kb": os.path.getsize(txt_path) // 1024,
                "converted_at": datetime.now().isoformat(),
                "method": "pdftotext-layout"
            }
            return 'done'
        else:
            # Try without layout
            if os.path.exists(txt_path):
                os.remove(txt_path)
            result = subprocess.run(
                ['pdftotext', pdf_path, txt_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )
            if os.path.exists(txt_path) and os.path.getsize(txt_path) > 10:
                tracker[txt_path] = {
                    "pdf": pdf_path,
                    "status": "DONE",
                    "size_kb": os.path.getsize(txt_path) // 1024,
                    "converted_at": datetime.now().isoformat(),
                    "method": "pdftotext"
                }
                return 'done'
            else:
                if os.path.exists(txt_path):
                    os.remove(txt_path)
                tracker[pdf_path] = {
                    "pdf": pdf_path,
                    "txt": txt_path,
                    "status": "IMPOSSIBLE_SCANNED_OR_ENCRYPTED",
                    "converted_at": datetime.now().isoformat()
                }
                return 'impossible'
    except subprocess.TimeoutExpired:
        tracker[pdf_path] = {
            "pdf": pdf_path,
            "status": "TIMEOUT",
            "converted_at": datetime.now().isoformat()
        }
        return 'timeout'
    except Exception as e:
        tracker[pdf_path] = {
            "pdf": pdf_path,
            "status": "ERROR",
            "error": str(e)[:100],
            "converted_at": datetime.now().isoformat()
        }
        return 'error'

def main():
    tracker = load_tracker()
    progress = load_progress()
    
    print(f"Scanning for PDFs in {SOURCE_DIR}...")
    pdf_files = []
    for root, dirs, files in os.walk(SOURCE_DIR):
        for f in files:
            if f.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, f))
    
    progress['total'] = len(pdf_files)
    save_progress(progress)
    print(f"Found {len(pdf_files)} PDFs")
    
    done = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(convert_pdf, pdf, tracker): pdf for pdf in pdf_files}
        for future in as_completed(futures):
            result = future.result()
            done += 1
            if done % 50 == 0:
                save_tracker(tracker)
                print(f"Progress: {done}/{len(pdf_files)} - Done: {sum(1 for v in tracker.values() if v.get('status','').startswith('DONE'))}, Impossible: {sum(1 for v in tracker.values() if 'IMPOSSIBLE' in v.get('status',''))}")
    
    save_tracker(tracker)
    print(f"\nCompleted! Total processed: {done}")
    print(f"DONE: {sum(1 for v in tracker.values() if v.get('status','').startswith('DONE'))}")
    print(f"IMPOSSIBLE/FAILED: {sum(1 for v in tracker.values() if v.get('status','') in ['IMPOSSIBLE_SCANNED_OR_ENCRYPTED', 'TIMEOUT', 'ERROR'])}")

if __name__ == '__main__':
    main()
