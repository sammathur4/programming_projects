"""Seed the Food DB, workout modules and notes feed.

Values are the ones the approved mockup uses, so the live app matches the
design that was signed off. Idempotent — safe to re-run: it updates by name
rather than inserting duplicates.

    python manage.py seed_food_notes_modules
    python manage.py seed_food_notes_modules --reset   # wipe and re-seed
"""
import datetime as dt

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import (
    DiaryEntry,
    Food,
    Note,
    NutritionTarget,
    WorkoutModule,
)

# name, serving, kcal, protein, carbs, fat, category
FOODS = [
    ("Roti / Chapati", "1 medium (40g)", 104, 3, 22, 1.2, "Indian"),
    ("Paratha (plain)", "1 piece (70g)", 210, 4.5, 28, 9, "Indian"),
    ("Jeera Rice", "1 katori (150g)", 245, 4, 45, 6, "Indian"),
    ("White Rice (cooked)", "1 katori (150g)", 205, 4.3, 45, 0.4, "Indian"),
    ("Dal Tadka", "1 katori (150g)", 180, 9, 22, 6, "Indian"),
    ("Rajma Curry", "1 katori (150g)", 215, 11, 30, 6, "Indian"),
    ("Chole", "1 katori (150g)", 230, 10, 32, 7, "Indian"),
    ("Paneer Butter Masala", "1 katori (150g)", 340, 14, 12, 27, "Indian"),
    ("Palak Paneer", "1 katori (150g)", 265, 13, 11, 19, "Indian"),
    ("Paneer Tikka", "6 pieces (150g)", 320, 20, 9, 23, "Indian"),
    ("Chicken Curry", "1 katori (150g)", 245, 22, 8, 14, "Indian"),
    ("Tandoori Chicken", "2 pieces (200g)", 330, 38, 4, 18, "Indian"),
    ("Butter Chicken", "1 katori (150g)", 390, 24, 11, 28, "Indian"),
    ("Egg (boiled)", "1 large", 78, 6.3, 0.6, 5.3, "Common"),
    ("Egg Bhurji", "2 eggs", 220, 13, 4, 17, "Indian"),
    ("Omelette (2 egg)", "1 serving", 230, 13, 3, 18, "Common"),
    ("Idli", "2 pieces", 116, 4, 24, 0.6, "Indian"),
    ("Masala Dosa", "1 piece", 310, 6, 44, 12, "Indian"),
    ("Plain Dosa", "1 piece", 168, 3.9, 28, 5, "Indian"),
    ("Upma", "1 katori (150g)", 190, 5, 30, 6, "Indian"),
    ("Poha", "1 katori (150g)", 250, 4.5, 42, 8, "Indian"),
    ("Sambar", "1 katori (150g)", 105, 5, 15, 3, "Indian"),
    ("Curd / Dahi", "1 katori (150g)", 90, 5, 7, 5, "Indian"),
    ("Raita", "1 katori (150g)", 110, 5, 8, 6, "Indian"),
    ("Oats (dry)", "40g", 150, 5, 27, 2.5, "Common"),
    ("Muesli with milk", "1 bowl (60g+200ml)", 330, 12, 52, 8, "Common"),
    ("Banana", "1 medium", 105, 1.3, 27, 0.4, "Fruit"),
    ("Apple", "1 medium", 95, 0.5, 25, 0.3, "Fruit"),
    ("Mango", "1 medium", 150, 1.4, 38, 0.6, "Fruit"),
    ("Almonds", "10 pieces", 70, 2.5, 2.5, 6, "Snack"),
    ("Peanut Butter", "1 tbsp (16g)", 95, 4, 3, 8, "Snack"),
    ("Whey Protein", "1 scoop (30g)", 120, 24, 3, 1.5, "Supplement"),
    ("Samosa", "1 piece", 260, 4, 30, 14, "Snack"),
    ("Pakora / Bhajji", "4 pieces", 290, 6, 26, 18, "Snack"),
    ("Gulab Jamun", "1 piece", 150, 2, 22, 6, "Dessert"),
    ("Pav Bhaji", "1 plate", 400, 9, 52, 17, "Indian"),
    ("Chicken Biryani", "1 plate (300g)", 520, 26, 62, 18, "Indian"),
    ("Veg Biryani", "1 plate (300g)", 420, 9, 66, 13, "Indian"),
    ("Pasta (cooked)", "1 cup (140g)", 220, 8, 43, 1.3, "Western"),
    ("Brown Bread", "2 slices", 140, 6, 26, 2, "Common"),
    ("Maggi Noodles", "1 pack (70g)", 310, 7, 42, 12, "Snack"),
    ("Sweet Potato", "1 medium (150g)", 130, 2.4, 30, 0.2, "Common"),
    ("Boiled Potato", "1 medium (150g)", 130, 3, 30, 0.2, "Common"),
    ("Mixed Salad", "1 bowl (150g)", 45, 2, 8, 0.5, "Common"),
    ("Tea with milk", "1 cup (150ml)", 60, 2, 8, 2, "Beverage"),
    ("Black Coffee", "1 cup", 5, 0.3, 0, 0, "Beverage"),
]

# What is logged for "today" in the mockup: meal, dish, quantity
DIARY_TODAY = [
    ("Breakfast", "Oats (dry)", 1),
    ("Breakfast", "Egg (boiled)", 3),
    ("Breakfast", "Black Coffee", 1),
    ("Lunch", "Roti / Chapati", 3),
    ("Lunch", "Dal Tadka", 1),
    ("Lunch", "Curd / Dahi", 1),
    ("Lunch", "Mixed Salad", 1),
    ("Snack", "Whey Protein", 1),
    ("Snack", "Banana", 1),
    ("Dinner", "Paneer Tikka", 1),
    ("Dinner", "Jeera Rice", 1),
]

# name, color, emoji, days, exercises
MODULES = [
    ("Push", "#3b82f6", "💪", ["Mon", "Thu"], [
        {"name": "Bench Press", "sets": 4, "reps": 8, "weight_kg": 70, "muscle": "Chest"},
        {"name": "Incline DB Press", "sets": 3, "reps": 10, "weight_kg": 26, "muscle": "Chest"},
        {"name": "Overhead Press", "sets": 3, "reps": 10, "weight_kg": 40, "muscle": "Shoulders"},
        {"name": "Lateral Raise", "sets": 3, "reps": 15, "weight_kg": 10, "muscle": "Shoulders"},
        {"name": "Triceps Pushdown", "sets": 3, "reps": 12, "weight_kg": 25, "muscle": "Triceps"},
    ]),
    ("Pull", "#22c55e", "🪢", ["Tue", "Fri"], [
        {"name": "Deadlift", "sets": 3, "reps": 5, "weight_kg": 110, "muscle": "Back"},
        {"name": "Barbell Row", "sets": 4, "reps": 10, "weight_kg": 55, "muscle": "Back"},
        {"name": "Lat Pulldown", "sets": 3, "reps": 12, "weight_kg": 50, "muscle": "Back"},
        {"name": "Face Pull", "sets": 3, "reps": 15, "weight_kg": 20, "muscle": "Rear Delts"},
        {"name": "Barbell Curl", "sets": 3, "reps": 12, "weight_kg": 25, "muscle": "Biceps"},
    ]),
    ("Legs", "#f59e0b", "🦵", ["Wed", "Sat"], [
        {"name": "Squat", "sets": 4, "reps": 6, "weight_kg": 90, "muscle": "Quads"},
        {"name": "Romanian Deadlift", "sets": 3, "reps": 10, "weight_kg": 70, "muscle": "Hamstrings"},
        {"name": "Leg Press", "sets": 3, "reps": 12, "weight_kg": 120, "muscle": "Quads"},
        {"name": "Leg Curl", "sets": 3, "reps": 12, "weight_kg": 40, "muscle": "Hamstrings"},
        {"name": "Standing Calf Raise", "sets": 4, "reps": 15, "weight_kg": 60, "muscle": "Calves"},
    ]),
    ("Cardio", "#38bdf8", "🏃", ["Sun"], [
        {"name": "Treadmill", "sets": 1, "reps": 1, "weight_kg": 0, "muscle": "Cardio",
         "cardio": True, "quantity": 5, "unit": "km", "minutes": 35},
        {"name": "Cycling", "sets": 1, "reps": 1, "weight_kg": 0, "muscle": "Cardio",
         "cardio": True, "quantity": 12, "unit": "km", "minutes": 28},
    ]),
]

# date offset from today, tag, ref, text, pinned
NOTES = [
    (0, "day", "Today", "Woke at 4:10, felt sharp. Gym was heavy but got all sets. Diet clean — no sugar. Need to start Economy revision tomorrow.", True),
    (0, "habit", "Diet", "Ate clean, no sugar. Felt lighter after gym.", False),
    (0, "fitness", "Push · Bench Press", "70 kg × 8 felt solid. Try 72.5 next week.", False),
    (0, "food", "Lunch", "3 roti + dal was perfect portioning. Curd helps digestion.", False),
    (1, "day", "Yesterday", "Missed Wake 4 AM — slept at 1:30 because of the Guitar practice. Fix the night routine.", False),
    (1, "habit", "Sleep 8H", "Only 6h. This is the root cause of the 4 AM misses.", False),
    (1, "goal", "UPSC CSE 2027", "Polity is at 62%. At this pace I finish before Nov 15 — ahead of schedule.", False),
    (2, "idea", "App idea", "Vision board should open as the first screen in the morning, before the habit list.", False),
    (2, "fitness", "Legs · Squat", "90 kg for 6. Depth good. Knee felt fine.", False),
    (3, "day", "Friday", "Deloitte work ran till 9pm. Still hit 4 habits. Small wins compound.", False),
    (3, "habit", "No Smoke + NoFap", "Day 14. Cravings passed faster than last week.", False),
    (4, "goal", "Fitness", "99.4 kg now. 24.4 kg down. Visible change in the mirror.", False),
    (4, "food", "Dinner", "Skipped rice at dinner — kept calories low since it was a rest day.", False),
    (5, "idea", "Study system", "Do MCQ tests in the morning, theory at night. Mornings are for output.", False),
    (6, "day", "Tuesday", "First perfect week. 7/7 days all habits. Momentum is real.", False),
]


class Command(BaseCommand):
    help = "Seed the food database, workout modules and notes feed."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="hard-delete existing seeded rows first")

    def handle(self, *args, **opts):
        if opts["reset"]:
            DiaryEntry.all_objects.all().hard_delete()
            Note.all_objects.all().hard_delete()
            WorkoutModule.all_objects.all().hard_delete()
            Food.all_objects.all().hard_delete()
            self.stdout.write("  reset: cleared diary, notes, modules, foods")

        self._foods()
        self._targets()
        self._modules()
        self._diary()
        self._notes()

    def _foods(self):
        created = updated = 0
        for name, serving, kcal, p, c, f, cat in FOODS:
            _, made = Food.objects.update_or_create(
                name=name,
                defaults=dict(serving=serving, kcal=kcal, protein_g=p, carbs_g=c,
                              fat_g=f, category=cat, deleted_at=None),
            )
            created += made
            updated += (not made)
        self.stdout.write(self.style.SUCCESS(
            f"  food: {created} created, {updated} updated ({Food.objects.count()} total)"))

    def _targets(self):
        obj = NutritionTarget.objects.first()
        if not obj:
            NutritionTarget.objects.create(calorie_goal=2100, protein_goal=140, carbs_goal=210, fat_goal=60)
            self.stdout.write(self.style.SUCCESS("  targets: 2100 kcal / 140P 210C 60F"))
        else:
            self.stdout.write(f"  targets: existing kept ({obj})")

    def _modules(self):
        for i, (name, color, emoji, days, exercises) in enumerate(MODULES):
            WorkoutModule.objects.update_or_create(
                name=name,
                defaults=dict(color=color, emoji=emoji, days=days, exercises=exercises,
                              order=i, deleted_at=None),
            )
        total_sets = sum(
            0 if e.get("cardio") else int(e.get("sets") or 0)
            for _, _, _, _, ex in MODULES for e in ex
        )
        self.stdout.write(self.style.SUCCESS(
            f"  modules: {len(MODULES)} upserted, {total_sets} working sets across the split"))

    def _diary(self):
        today = dt.date.today()
        if DiaryEntry.objects.filter(date=today).exists():
            self.stdout.write(f"  diary: {today} already has entries, skipped")
            return
        made = 0
        for meal, dish_name, qty in DIARY_TODAY:
            dish = Food.objects.filter(name=dish_name).first()
            if not dish:
                self.stderr.write(f"    ! missing dish {dish_name}")
                continue
            DiaryEntry.objects.create(
                date=today, meal=meal, food=dish, food_name=dish.name, quantity=qty,
                kcal=round(float(dish.kcal) * qty),
                protein_g=round(float(dish.protein_g) * qty, 1),
                carbs_g=round(float(dish.carbs_g) * qty, 1),
                fat_g=round(float(dish.fat_g) * qty, 1),
            )
            made += 1
        kcal = sum(e.kcal for e in DiaryEntry.objects.filter(date=today))
        self.stdout.write(self.style.SUCCESS(
            f"  diary: {made} entries for {today} ({kcal} kcal)"))

    def _notes(self):
        today = dt.date.today()
        made = skipped = 0
        for offset, tag, ref, text, pinned in NOTES:
            date = today - dt.timedelta(days=offset)
            exists = Note.all_objects.filter(date=date, tag=tag, ref=ref).exists()
            if exists:
                skipped += 1
                continue
            Note.objects.create(date=date, tag=tag, ref=ref, text=text, pinned=pinned)
            made += 1
        self.stdout.write(self.style.SUCCESS(
            f"  notes: {made} created, {skipped} already present ({Note.objects.count()} total)"))
        self.stdout.write(f"  seeded at {timezone.now():%Y-%m-%d %H:%M}")
