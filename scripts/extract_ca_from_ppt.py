#!/usr/bin/env python3
import sys
import csv
import re
from pathlib import Path
from collections import defaultdict
from pptx import Presentation

CATEGORIES = {
    'polity': ['constitution', 'parliament', 'minister', 'bill', 'act', 'judiciary', 'court', 'supreme', 'governor', 'president', 'election', 'assembly', 'panchayat'],
    'economy': ['gdp', 'budget', 'rbi', 'bank', 'market', 'trade', 'export', 'import', 'tax', 'inflation', 'investment', 'economy', 'gst', 'fiscal'],
    'environment': ['climate', 'forest', 'wildlife', 'tiger', 'carbon', 'emission', 'pollution', 'water', 'river', 'biodiversity', 'conservation'],
    'science': ['ai', 'drone', 'satellite', 'missile', 'technology', 'nuclear', 'submarine', 'space', 'isro', 'artificial'],
    'international': ['china', 'pakistan', 'russia', 'usa', 'un', 'treaty', 'bilateral', 'cooperation', 'summit', 'brics', 'g20'],
    'defense': ['army', 'navy', 'air', 'missile', 'defense', 'security', 'border', 'military'],
    'health': ['health', 'disease', 'vaccine', 'hospital', 'mortality', 'who'],
    'social': ['women', 'child', 'education', 'poverty', 'scheme', 'welfare'],
}

def categorize(text):
    text_lower = text.lower()
    scores = defaultdict(int)
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw in text_lower:
                scores[cat] += 1
    if not scores:
        return 'other'
    return max(scores.items(), key=lambda x: x[1])[0]

def extract_date_from_filename(filename):
    m = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', filename)
    if not m:
        return None, None, None, None
    day, mon, year = m.group(1).zfill(2), m.group(2).lower(), m.group(3)
    months = {'january':'01','february':'02','march':'03','april':'04','may':'05','june':'06',
             'july':'07','august':'08','september':'09','october':'10','november':'11','december':'12',
             'jan':'01','feb':'02','mar':'03','apr':'04','jun':'06','jul':'07','aug':'08','sep':'09','sept':'09','oct':'10','nov':'11','dec':'12'}
    month = months.get(mon)
    if not month:
        return None, None, None, None
    return f"{year}-{month}-{day}", year, month, day

def extract_from_ppt(ppt_path, output_csv=None):
    ppt_path = Path(ppt_path)
    if not ppt_path.exists():
        print(f"Error: {ppt_path} not found")
        sys.exit(1)
    
    date_str, year, month, day = extract_date_from_filename(ppt_path.name)
    if not date_str:
        # Try to get from parent dirs or use current
        date_str = year = month = day = ''
    
    prs = Presentation(str(ppt_path))
    results = []
    
    for slide_num, slide in enumerate(prs.slides):
        # Get all text from slide
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append(shape.text.strip())
        
        full_slide_text = '\n'.join(slide_text)
        if not full_slide_text.strip():
            continue
        
        # Check if it's a current affairs slide
        if not re.search(r'current affairs|समसाम|short.*affairs', full_slide_text, re.I):
            # Also check for common patterns
            pass
        
        # Try to extract items from slide
        # Look for bullet points or structured content
        for shape in slide.shapes:
            if hasattr(shape, "text_frame"):
                text = shape.text_frame
                # Process paragraphs
                for para in text.paragraphs:
                    para_text = para.text.strip()
                    if not para_text:
                        continue
                    # Skip headers/boilerplate
                    if any(x in para_text.lower() for x in ['studylove', 'telegram', 'download', 'contact', 'website']):
                        continue
                    if re.match(r'^[\u0900-\u097F\s]+$', para_text):
                        continue
                    if para_text.lower().startswith('imp. short') or para_text.lower().startswith('score booster'):
                        continue
                    # Check if it's a bullet point (level > 0) or main point
                    if para.level > 0 or para_text.startswith(('•', '❖', '-', '*')):
                        content = re.sub(r'^[•❖\-\*\s]+', '', para_text).strip()
                        if len(content) > 10:
                            # Look for topic-like content
                            headline = content
                            if ':' in headline and len(headline.split(':')[0]) < 60:
                                headline = headline.split(':')[0].strip()
                            full_text = content
                            cat = categorize(full_text)
                            results.append({
                                'date': date_str,
                                'year': year,
                                'month': month,
                                'category': cat,
                                'headline': headline[:200],
                                'details': content[:300],
                                'source_file': ppt_path.name
                            })
                    elif len(para_text) > 20 and re.match(r'^[A-Z]', para_text):
                        # Maybe a heading
                        if ':' not in para_text[:40] or len(para_text) < 100:
                            headline = para_text
                            if len(headline) > 200:
                                headline = headline[:200]
                            full_text = headline
                            cat = categorize(full_text)
                            results.append({
                                'date': date_str,
                                'year': year,
                                'month': month,
                                'category': cat,
                                'headline': headline,
                                'details': '',
                                'source_file': ppt_path.name
                            })
    
    # Remove duplicates
    seen = set()
    unique_results = []
    for r in results:
        key = r['headline'].lower()
        if key not in seen and len(key) > 10:
            seen.add(key)
            unique_results.append(r)
    
    if output_csv is None:
        output_csv = ppt_path.stem + '_ca_pointers.csv'
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['date', 'year', 'month', 'category', 'headline', 'details', 'source_file'])
        writer.writeheader()
        for r in unique_results:
            writer.writerow(r)
    
    print(f'Extracted {len(unique_results)} items to {output_csv}')
    return output_csv

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python extract_ca_from_ppt.py <input.pptx> [output.csv]")
        sys.exit(1)
    extract_from_ppt(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
