"""
Simple test of FDC parsing logic
"""

# Simulate the parsing function
def parse_fdc_nutrients(food_data):
    nutrients = {
        "calories": 0,
        "protein_g": 0,
        "carbs_g": 0,
        "fat_g": 0,
        "fiber_g": 0,
        "sodium_mg": 0
    }

    nutrient_map = {
        1008: 'calories',
        1003: 'protein_g',
        1004: 'fat_g',
        1005: 'carbs_g',
        1079: 'fiber_g',
        1093: 'sodium_mg'
    }

    print(f"Processing: {food_data.get('description')}")
    print(f"Total nutrients: {len(food_data.get('foodNutrients', []))}")

    for nutrient in food_data.get('foodNutrients', []):
        nutrient_id = nutrient.get('nutrientId') or nutrient.get('nutrient', {}).get('id')
        if nutrient_id in nutrient_map:
            value = nutrient.get('value', 0)
            name = nutrient_map[nutrient_id]
            nutrients[name] = round(value, 2)
            print(f"  OK {name}: {value} -> {nutrients[name]}")

    return nutrients


# Test with sample raspberry data
raspberry = {
    "description": "Raspberries, raw",
    "foodNutrients": [
        {"nutrientId": 1008, "nutrientName": "Energy", "value": 52.0},
        {"nutrientId": 1003, "nutrientName": "Protein", "value": 1.01},
        {"nutrientId": 1005, "nutrientName": "Carbs", "value": 12.9},
        {"nutrientId": 1004, "nutrientName": "Fat", "value": 0.19},
    ]
}

print("="*80)
print("TESTING FDC PARSING")
print("="*80)
result = parse_fdc_nutrients(raspberry)
print("\nResult:")
print(result)

if result['calories'] == 52.0:
    print("\n✅ SUCCESS: Parsing works correctly!")
else:
    print(f"\n❌ FAILED: Calories = {result['calories']}, expected 52.0")
