#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from pdf2image import convert_from_path
import pytesseract

def ocr_pdf(pdf_path, dpi=300):
    pages = convert_from_path(str(pdf_path), dpi=dpi)
    texts = []
    for img in pages:
        texts.append(pytesseract.image_to_string(img, lang='eng'))
    return '\n\n===PAGE_BREAK===\n\n'.join(texts)

def extract_csat_questions(text):
    questions = []
    pattern = re.compile(r'(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,3})[\.\)]\s+(.+?)(?=\n\s*(?:Q\.?\s*)?\d{1,3}[\.\)]|\Z)', re.DOTALL)
    for i, (num, block) in enumerate(pattern.findall(text), 1):
        options = []
        qtext = block
        opt_pattern = re.compile(r'\b([A-D])[\.\)]\s+(.+?)(?=\b[A-D][\.\)]|\Z)', re.DOTALL | re.IGNORECASE)
        opt_matches = opt_pattern.findall(block)
        if opt_matches:
            for letter, opt_text in opt_matches:
                opt_text = re.sub(r'\n+', ' ', opt_text)
                opt_text = re.sub(r'\s+', ' ', opt_text).strip()
                options.append({'option': letter.upper(), 'text': opt_text})
            first_opt = re.search(r'\b[A-D][\.\)]', block)
            if first_opt:
                qtext = block[:first_opt.start()]
        qtext = re.sub(r'\n+', ' ', qtext)
        qtext = re.sub(r'\s+', ' ', qtext).strip()
        if len(qtext) < 10:
            continue
        questions.append({
            "question_number": int(num),
            "question": qtext,
            "options": options,
            "type": "mcq"
        })
    return questions

def extract_mains_questions(text):
    questions = []
    pattern = re.compile(r'(?:^|\n)\s*(?:Q\.?\s*)?(\d{1,2})[\.\)]\s+(.+?)(?=\n\s*(?:Q\.?\s*)?\d{1,2}[\.\)]|\Z)', re.DOTALL)
    for i, (num, block) in enumerate(pattern.findall(text), 1):
        qtext = re.sub(r'\n+', ' ', block)
        qtext = re.sub(r'\s+', ' ', qtext).strip()
        qtext = re.sub(r'\(Answer.*?\d+.*?\)', '', qtext, flags=re.I).strip()
        if len(qtext) < 40:
            continue
        questions.append({
            "question_number": int(num),
            "question": qtext,
            "type": "mains"
        })
    return questions

def main():
    if len(sys.argv) < 2:
        print("Usage: pdf_to_json.py <pdf_path> [output_dir]")
        sys.exit(1)
    pdf_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else pdf_path.parent / "json_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"OCRing {pdf_path}...")
    text = ocr_pdf(pdf_path)
    (out_dir / f"{pdf_path.stem}_raw.txt").write_text(text, encoding='utf-8')
    
    name = pdf_path.name.lower()
    if 'csat' in name or 'prelim' in name:
        questions = extract_csat_questions(text)
        paper = "GS Paper 2 (CSAT)"
    else:
        questions = extract_mains_questions(text)
        paper = "Mains"
    
    year = re.search(r'20\d{2}', pdf_path.name)
    year = year.group(0) if year else ""
    
    result = {
        "exam": "UPSC",
        "paper": paper,
        "year": year,
        "source_file": pdf_path.name,
        "total_questions": len(questions),
        "questions": questions
    }
    out_file = out_dir / f"{pdf_path.stem}.json"
    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Saved {out_file} ({len(questions)} questions)")

if __name__ == '__main__':
    main()
