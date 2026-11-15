#!/usr/bin/env python3
import csv
import os
import re
from pathlib import Path

# Read existing inventory
inventory_path = '/media/saksham/phone data/programming_projects/upsc_app/notes/UPSC_CSE_2027/00_MASTER_INDEX/Resource_Inventory.md'
output_csv = '/media/saksham/phone data/programming_projects/upsc_app/notes/UPSC_CSE_2027/00_MASTER_INDEX/Resource_Inventory_Classified.csv'

# Classification rules
def classify_file(filename, filepath):
    filename_lower = filename.lower()
    filepath_lower = filepath.lower()
    
    subject = 'TBD'
    syllabus_mapping = 'TBD'
    content_type = 'TBD'
    quality = 'TBD'
    relevance = 'High'
    
    # Prelims GS1
    if 'prelim' in filepath_lower or 'gs1' in filepath_lower and 'mains' not in filepath_lower:
        if 'csat' in filepath_lower or 'comprehension' in filename_lower or 'reasoning' in filename_lower:
            subject = 'CSAT'
            syllabus_mapping = 'Prelims Paper II'
        else:
            subject = 'Prelims GS I'
            syllabus_mapping = 'Prelims Paper I'
    
    # Mains
    if 'mains' in filepath_lower or 'gs paper' in filepath_lower or 'paper' in filepath_lower and '02_mains' in filepath_lower:
        if 'gs1' in filepath_lower or 'heritage' in filepath_lower or 'culture' in filepath_lower or 'history' in filepath_lower and 'geography' in filepath_lower and 'society' in filepath_lower:
            subject = 'GS I Mains'
            syllabus_mapping = 'Mains GS Paper I'
        elif 'gs2' in filepath_lower or 'polity' in filepath_lower or 'governance' in filepath_lower or 'constitution' in filepath_lower or 'international' in filepath_lower:
            subject = 'GS II Mains'
            syllabus_mapping = 'Mains GS Paper II'
        elif 'gs3' in filepath_lower or 'economy' in filepath_lower or 'agriculture' in filepath_lower or 'environment' in filepath_lower or 'security' in filepath_lower or 'science' in filepath_lower:
            subject = 'GS III Mains'
            syllabus_mapping = 'Mains GS Paper III'
        elif 'gs4' in filepath_lower or 'ethic' in filepath_lower or 'integrity' in filepath_lower:
            subject = 'GS IV Mains'
            syllabus_mapping = 'Mains GS Paper IV'
    
    # Sociology
    if 'sociology' in filepath_lower or 'optional' in filepath_lower:
        subject = 'Sociology Optional'
        if 'paper1' in filepath_lower or 'fundamental' in filepath_lower:
            syllabus_mapping = 'Sociology Paper I'
        elif 'paper2' in filepath_lower or 'indian society' in filepath_lower:
            syllabus_mapping = 'Sociology Paper II'
        else:
            syllabus_mapping = 'Sociology Optional'
    
    # Essay
    if 'essay' in filepath_lower:
        subject = 'Essay'
        syllabus_mapping = 'Essay Paper'
    
    # Current Affairs
    if 'ca ' in filepath_lower or 'current' in filepath_lower:
        content_type = 'Current Affairs'
        if subject == 'TBD':
            subject = 'Current Affairs (General)'
    
    # PYQ
    if 'pyq' in filepath_lower or 'previous year' in filepath_lower or 'question' in filepath_lower:
        content_type = 'PYQ'
    
    # Books/Notes
    if content_type == 'TBD':
        if filename_lower.endswith('.pdf'):
            if 'notes' in filename_lower or 'complete' in filename_lower:
                content_type = 'Notes'
            elif 'book' in filename_lower:
                content_type = 'Book'
            else:
                content_type = 'Reference Material'
    
    # International/National institutions
    if 'institution' in filepath_lower:
        if subject == 'TBD':
            subject = 'Prelims GS I - Polity/IR'
    
    return subject, syllabus_mapping, content_type, quality, relevance

# Parse markdown table
files_data = []
with open(inventory_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find table rows
lines = content.split('\n')
for line in lines:
    if line.strip().startswith('|') and not line.strip().startswith('| ---') and not line.strip().startswith('| File ID'):
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 12:
            file_id = parts[1]
            filename = parts[2]
            filepath = parts[3]
            file_format = parts[4]
            if filename and filename != 'File name':
                subject, syllabus_mapping, content_type, quality, relevance = classify_file(filename, filepath)
                files_data.append({
                    'File ID': file_id,
                    'File name': filename,
                    'File path': filepath,
                    'Format': file_format,
                    'Subject': subject,
                    'Syllabus mapping': syllabus_mapping,
                    'Content type': content_type,
                    'Processing status': 'Pending',
                    'Quality': quality,
                    'Relevance': relevance,
                    'Remarks': parts[11] if len(parts) > 11 else ''
                })

# Write CSV
with open(output_csv, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['File ID', 'File name', 'File path', 'Format', 'Subject', 'Syllabus mapping', 'Content type', 'Processing status', 'Quality', 'Relevance', 'Remarks'])
    writer.writeheader()
    for row in files_data:
        writer.writerow(row)

print(f'Classified {len(files_data)} files. Output: {output_csv}')
