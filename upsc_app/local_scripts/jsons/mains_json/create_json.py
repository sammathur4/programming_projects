import json
from pathlib import Path


# Output directory
OUTPUT_DIR = Path("socio_json")

# Create output directory if it doesn't exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


for year in range(2014, 2027):
    for gs in range(1, 3):
        filename = OUTPUT_DIR / f"socio_{gs}_{year}.json"

        # Create an empty JSON array
        with open(filename, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)

        print(f"Created: {filename}")


print("\nDone! Created 48 empty JSON files.")

