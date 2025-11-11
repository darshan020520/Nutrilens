"""
Test FDC parsing to debug why calories = 0
"""
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.fdc_service import FDCService

# Load raspberry FDC data
with open('backend/backend/data/debug_fdc_raspberry.json', 'r') as f:
    raspberry_data = json.load(f)

# Get first match
first_match = raspberry_data[0]

print("="*80)
print("TESTING FDC NUTRIENT PARSING")
print("="*80)
print(f"\nFood: {first_match.get('description')}")
print(f"Total nutrients in FDC data: {len(first_match.get('foodNutrients', []))}")

# Find calories specifically
print("\nSearching for calories (nutrientId: 1008)...")
found_calories = False
for nutrient in first_match.get('foodNutrients', []):
    if nutrient.get('nutrientId') == 1008:
        print(f"✓ FOUND calories in raw data:")
        print(f"  nutrientId: {nutrient.get('nutrientId')}")
        print(f"  nutrientName: {nutrient.get('nutrientName')}")
        print(f"  value: {nutrient.get('value')}")
        found_calories = True
        break

if not found_calories:
    print("✗ Calories NOT found in FDC data!")

# Test our parsing function
print("\n" + "="*80)
print("TESTING OUR PARSING FUNCTION")
print("="*80)

fdc_service = FDCService()
parsed_nutrients = fdc_service._parse_fdc_nutrients(first_match)

print(f"\nParsed result:")
for key, value in parsed_nutrients.items():
    status = "✓" if value > 0 else "✗"
    print(f"  {status} {key}: {value}")

print("\n" + "="*80)
if parsed_nutrients['calories'] == 0:
    print("❌ BUG CONFIRMED: Calories parsed as 0 despite being in FDC data!")
else:
    print(f"✅ SUCCESS: Calories correctly parsed as {parsed_nutrients['calories']}")
print("="*80)
