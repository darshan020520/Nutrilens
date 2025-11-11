"""
Analyze all debug_fdc_*.json files to understand nutrient ID mappings across different FDC data types

This will help us identify:
1. Which nutrient IDs correspond to which nutrients (calories, protein, carbs, etc.)
2. Inconsistencies across different FDC data types (Foundation vs SR Legacy)
3. Complete mapping needed for robust parsing
"""

import json
import os
from collections import defaultdict
from pathlib import Path

# Our target nutrients
TARGET_NUTRIENTS = {
    'calories': ['energy', 'kcal'],
    'protein': ['protein'],
    'carbs': ['carbohydrate', 'carbs'],
    'fat': ['fat', 'lipid'],
    'fiber': ['fiber', 'fibre'],
    'sodium': ['sodium']
}

def analyze_fdc_files():
    """Analyze all debug_fdc_*.json files"""

    # Dictionary to store: nutrient_name -> {nutrient_id: count}
    nutrient_mappings = defaultdict(lambda: defaultdict(int))

    # Dictionary to store: our_field -> {nutrient_id: [examples]}
    field_to_ids = defaultdict(lambda: defaultdict(list))

    # Get all debug_fdc files
    data_dir = Path("backend/data")
    if not data_dir.exists():
        data_dir = Path("backend/backend/data")
    fdc_files = list(data_dir.glob("debug_fdc_*.json"))

    print("="*80)
    print(f"ANALYZING {len(fdc_files)} FDC DEBUG FILES")
    print("="*80)
    print()

    total_matches = 0

    for fdc_file in fdc_files:
        item_name = fdc_file.stem.replace('debug_fdc_', '')

        with open(fdc_file, 'r') as f:
            data = json.load(f)

        print(f"\n{'='*80}")
        print(f"Item: {item_name}")
        print(f"{'='*80}")

        for match_idx, match in enumerate(data):
            total_matches += 1
            description = match.get('description', 'N/A')
            data_type = match.get('dataType', 'N/A')

            print(f"\n  Match {match_idx}: {description} ({data_type})")
            print(f"  Total nutrients: {len(match.get('foodNutrients', []))}")

            # Analyze nutrients
            for nutrient in match.get('foodNutrients', []):
                nutrient_id = nutrient.get('nutrientId')
                nutrient_name = nutrient.get('nutrientName', '').lower()
                nutrient_value = nutrient.get('value', 0)
                unit = nutrient.get('unitName', '')

                # Track this mapping
                nutrient_mappings[nutrient_name][nutrient_id] += 1

                # Check if this matches our target nutrients
                for field, keywords in TARGET_NUTRIENTS.items():
                    if any(keyword in nutrient_name for keyword in keywords):
                        field_to_ids[field][nutrient_id].append({
                            'item': item_name,
                            'match': match_idx,
                            'name': nutrient.get('nutrientName'),
                            'value': nutrient_value,
                            'unit': unit,
                            'dataType': data_type
                        })
                        print(f"    [OK] {field.upper()}: ID {nutrient_id} = {nutrient_value} {unit} ({nutrient.get('nutrientName')})")

    print("\n\n")
    print("="*80)
    print("SUMMARY: NUTRIENT ID MAPPINGS FOR TARGET FIELDS")
    print("="*80)

    for field in ['calories', 'protein', 'carbs', 'fat', 'fiber', 'sodium']:
        print(f"\n{field.upper()}:")
        print("-" * 40)

        if field not in field_to_ids:
            print("  [X] NOT FOUND in any match!")
            continue

        # Group by nutrient ID
        ids = field_to_ids[field]
        for nutrient_id in sorted(ids.keys()):
            examples = ids[nutrient_id]
            print(f"\n  Nutrient ID {nutrient_id}:")

            # Get unique names for this ID
            unique_names = set(ex['name'] for ex in examples)
            for name in unique_names:
                print(f"    Name: {name}")

            # Show data type distribution
            data_types = defaultdict(int)
            for ex in examples:
                data_types[ex['dataType']] += 1

            print(f"    Data types: {dict(data_types)}")
            print(f"    Total occurrences: {len(examples)}")

            # Show example values
            print(f"    Example values:")
            for ex in examples[:3]:  # Show first 3
                print(f"      {ex['item']} (match {ex['match']}): {ex['value']} {ex['unit']}")

    print("\n\n")
    print("="*80)
    print("RECOMMENDED NUTRIENT MAP")
    print("="*80)
    print("\nnutrient_map = {")

    for field in ['calories', 'protein', 'carbs', 'fat', 'fiber', 'sodium']:
        if field in field_to_ids:
            ids = sorted(field_to_ids[field].keys())
            print(f"    # {field}")
            for nutrient_id in ids:
                examples = field_to_ids[field][nutrient_id]
                name = examples[0]['name']
                print(f"    {nutrient_id}: '{field}_g' if '{field}' != 'calories' else 'calories',  # {name}")

    print("}")

    print("\n\n")
    print("="*80)
    print("STATISTICS")
    print("="*80)
    print(f"Total FDC files analyzed: {len(fdc_files)}")
    print(f"Total matches analyzed: {total_matches}")
    print(f"Unique nutrient IDs found: {len(nutrient_mappings)}")


if __name__ == "__main__":
    analyze_fdc_files()
