"""Seed the jaap (mantra counter) library.

Idempotent: running it again only fills in blanks, so it never overwrites a
mala size or daily goal you have since changed in the app.

    python manage.py seed_jaap
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import JaapMantra

# The starter library. `mala_size` is the number of beads in one round —
# 108 is the tradition, but the user decides and can change it per mantra.
MANTRAS = [
    {
        "name": "Hanuman Chalisa",
        "emoji": "🙏",
        "devanagari": "श्रीगुरु चरन सरोज रज निज मनु मलु धुरि स्वयं",
        "transliteration": "Shri Guru charan saroj raj nij manu malu dhuri svayam",
        "category": JaapMantra.CATEGORY_CHALISA,
        "deity": "Hanuman",
        "mala_size": 108,
        "daily_goal": 1188,  # 11 x 108 — the "11x" in the habit name
        "color": "#F5A623",
        "sort_order": 1,
    },
    {
        "name": "Ram Tarak",
        "emoji": "🙏",
        "devanagari": "जय राम जय जय जय राम",
        "transliteration": "Jai Ram Jai Jai Jai Ram",
        "category": JaapMantra.CATEGORY_NAAM,
        "deity": "Ram",
        "mala_size": 108,
        "daily_goal": 108,
        "color": "#F5C96E",
        "sort_order": 2,
    },
]


class Command(BaseCommand):
    help = "Seed the jaap mantra library (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Also update existing rows to the values below.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        reset = options.get("reset")
        created = updated = restored = 0
        for spec in MANTRAS:
            # Look through soft-deleted rows too: the name is unique, so a
            # retired mantra must be revived rather than duplicated.
            obj = JaapMantra.all_objects.filter(name=spec["name"]).first()
            if obj is None:
                JaapMantra.objects.create(**spec)
                created += 1
                continue
            if obj.deleted_at:
                obj.deleted_at = None
                obj.save(update_fields=["deleted_at", "updated_at"])
                restored += 1
            if reset:
                changed = False
                for k, v in spec.items():
                    if getattr(obj, k) != v:
                        setattr(obj, k, v)
                        changed = True
                if changed:
                    obj.save()
                    updated += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Jaap library: {created} created, {restored} restored, "
                f"{updated} updated ({len(MANTRAS)} in the seed set)"
            )
        )
