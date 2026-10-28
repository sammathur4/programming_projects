#!/usr/bin/env python3
import json
from pathlib import Path
from django.core.management.base import BaseCommand
from syllabus.models import PrelimsQuestion


class Command(BaseCommand):
    help = 'Import questions from prelims-arena into PrelimsQuestion'

    def add_arguments(self, parser):
        parser.add_argument('--data-dir', type=str, default='/media/saksham/phone data/programming_projects/side_projects/prelims-arena/data')

    def handle(self, *args, **options):
        data_dir = Path(options['data_dir'])
        sets_dir = data_dir / 'sets'
        
        imported = 0
        for json_file in sorted(sets_dir.glob('PYQ-*.json')):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                questions = data.get('questions', []) if isinstance(data, dict) else []
                for q in questions:
                    qtext = q.get('q', '')
                    opts = q.get('o', [])
                    ans_idx = q.get('a')
                    year = q.get('y')
                    if not qtext or not year:
                        continue
                    pq = PrelimsQuestion(
                        question_id=PrelimsQuestion.objects.filter(year=year).count() + 50000,
                        year=year,
                        section=q.get('u') or q.get('sub') or '',
                        question=qtext,
                        option_a=opts[0] if len(opts) > 0 else '',
                        option_b=opts[1] if len(opts) > 1 else '',
                        option_c=opts[2] if len(opts) > 2 else '',
                        option_d=opts[3] if len(opts) > 3 else '',
                        correct_answer=chr(65 + ans_idx) if isinstance(ans_idx, int) and 0 <= ans_idx < 4 else '',
                        explanation=q.get('e', ''),
                        source='prelims-arena',
                        source_type='Previous Year Question',
                    )
                    pq.save()
                    imported += 1
                self.stdout.write(f'{json_file.name}: {len(questions)}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'{json_file.name}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'Total imported: {imported}'))
