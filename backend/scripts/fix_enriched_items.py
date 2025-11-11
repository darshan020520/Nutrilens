"""
Fix Enriched Items
===================

This script fixes the 14 identified issues in the enriched items JSON.
"""

import json

# Load the readable JSON
with open('backend/data/items_to_enrich_readable.json', 'r') as f:
    data = json.load(f)

items = data['items']

# Define corrections based on known good USDA FDC values
CORRECTIONS = {
    # Item 6 - beef_lean: Too low calories
    'beef_lean': {
        'nutrition_per_100g': {
            'calories': 250,
            'protein_g': 26.0,
            'carbs_g': 0.0,
            'fat_g': 15.0,
            'fiber_g': 0.0,
            'sodium_mg': 60.0
        },
        'fdc_id': '174032',
        'fdc_description': 'Beef, ground, 90% lean meat / 10% fat, raw',
        'confidence': 0.9
    },

    # Item 7 - bell_pepper: Low fiber
    'bell_pepper': {
        'nutrition_per_100g': {
            'calories': 20.0,
            'protein_g': 0.86,
            'carbs_g': 4.64,
            'fat_g': 0.17,
            'fiber_g': 1.7,
            'sodium_mg': 3.0
        },
        'fdc_id': '170108',
        'fdc_description': 'Peppers, sweet, red, raw'
    },

    # Item 14 - brown_rice: Should be grain not flour
    'brown_rice': {
        'nutrition_per_100g': {
            'calories': 370,
            'protein_g': 7.9,
            'carbs_g': 77.2,
            'fat_g': 2.9,
            'fiber_g': 3.5,
            'sodium_mg': 7.0
        },
        'fdc_id': '168878',
        'fdc_description': 'Rice, brown, long-grain, raw'
    },

    # Item 21 - cheese: Should be generic cheddar, not blue cheese
    'cheese': {
        'canonical_name': 'cheese',
        'display_name': 'Cheese',
        'category': 'dairy',
        'aliases': ['cheddar cheese', 'cheese block', 'hard cheese'],
        'nutrition_per_100g': {
            'calories': 403,
            'protein_g': 24.9,
            'carbs_g': 1.28,
            'fat_g': 33.1,
            'fiber_g': 0.0,
            'sodium_mg': 621.0
        },
        'fdc_id': '173417',
        'fdc_description': 'Cheese, cheddar',
        'confidence': 0.95
    },

    # Item 56 - oats: Should be raw oats, not oat bread
    'oats': {
        'canonical_name': 'oats',
        'display_name': 'Oats',
        'category': 'grains',
        'aliases': ['rolled oats', 'oat flakes', 'oatmeal'],
        'nutrition_per_100g': {
            'calories': 389,
            'protein_g': 16.9,
            'carbs_g': 66.3,
            'fat_g': 6.9,
            'fiber_g': 10.6,
            'sodium_mg': 2.0
        },
        'fdc_id': '173904',
        'fdc_description': 'Oats',
        'confidence': 0.95
    },

    # Item 58 - olive_oil: All zeros - CRITICAL
    'olive_oil': {
        'nutrition_per_100g': {
            'calories': 884,
            'protein_g': 0.0,
            'carbs_g': 0.0,
            'fat_g': 100.0,
            'fiber_g': 0.0,
            'sodium_mg': 2.0
        },
        'fdc_id': '171413',
        'fdc_description': 'Oil, olive, salad or cooking'
    },

    # Item 60 - orange: Should be fruit, not juice
    'orange': {
        'canonical_name': 'orange',
        'display_name': 'Orange',
        'category': 'fruits',
        'aliases': ['oranges', 'orange fruit', 'sweet orange'],
        'nutrition_per_100g': {
            'calories': 47.0,
            'protein_g': 0.94,
            'carbs_g': 11.8,
            'fat_g': 0.12,
            'fiber_g': 2.4,
            'sodium_mg': 0.0
        },
        'fdc_id': '169097',
        'fdc_description': 'Oranges, raw, all commercial varieties',
        'confidence': 0.95
    },

    # Item 64 - peas: Canonical name fix
    'peas': {
        'canonical_name': 'peas',
        'display_name': 'Peas',
        'aliases': ['green peas', 'garden peas', 'english peas']
    },

    # Item 68 - potato: Should be raw potato, not flour
    'potato': {
        'canonical_name': 'potato',
        'display_name': 'Potato',
        'category': 'vegetables',
        'aliases': ['potatoes', 'white potato', 'irish potato'],
        'nutrition_per_100g': {
            'calories': 77.0,
            'protein_g': 2.05,
            'carbs_g': 17.5,
            'fat_g': 0.09,
            'fiber_g': 2.1,
            'sodium_mg': 6.0
        },
        'fdc_id': '170026',
        'fdc_description': 'Potatoes, raw, skin',
        'confidence': 0.95
    },

    # Item 72 - rice: Should be white rice, not rice cakes
    'rice': {
        'canonical_name': 'rice',
        'display_name': 'Rice',
        'category': 'grains',
        'aliases': ['white rice', 'polished rice', 'rice grain'],
        'nutrition_per_100g': {
            'calories': 365,
            'protein_g': 7.13,
            'carbs_g': 79.9,
            'fat_g': 0.66,
            'fiber_g': 1.3,
            'sodium_mg': 5.0
        },
        'fdc_id': '169756',
        'fdc_description': 'Rice, white, long-grain, regular, raw, unenriched',
        'confidence': 0.95
    },

    # Item 80 - sweet_potato: Should be raw, not canned
    'sweet_potato': {
        'nutrition_per_100g': {
            'calories': 86.0,
            'protein_g': 1.57,
            'carbs_g': 20.1,
            'fat_g': 0.05,
            'fiber_g': 3.0,
            'sodium_mg': 55.0
        },
        'fdc_id': '168487',
        'fdc_description': 'Sweet potato, raw, unprepared'
    },

    # Item 81 - tofu: Should be regular, not fried
    'tofu': {
        'nutrition_per_100g': {
            'calories': 76.0,
            'protein_g': 8.08,
            'carbs_g': 1.88,
            'fat_g': 4.78,
            'fiber_g': 0.3,
            'sodium_mg': 7.0
        },
        'fdc_id': '172444',
        'fdc_description': 'Tofu, raw, firm, prepared with calcium sulfate'
    },

    # Item 92 - white_rice: Use dry values for consistency
    'white_rice': {
        'nutrition_per_100g': {
            'calories': 365,
            'protein_g': 7.13,
            'carbs_g': 79.9,
            'fat_g': 0.66,
            'fiber_g': 1.3,
            'sodium_mg': 5.0
        },
        'fdc_id': '169756',
        'fdc_description': 'Rice, white, long-grain, regular, raw, unenriched'
    },

    # Item 53 - millet: Use raw values for consistency
    'millet': {
        'nutrition_per_100g': {
            'calories': 378,
            'protein_g': 11.0,
            'carbs_g': 73.0,
            'fat_g': 4.22,
            'fiber_g': 8.5,
            'sodium_mg': 5.0
        },
        'fdc_id': '169708',
        'fdc_description': 'Millet, raw'
    }
}

# Apply corrections
fixed_count = 0
for item in items:
    canonical_name = item['canonical_name']

    if canonical_name in CORRECTIONS:
        correction = CORRECTIONS[canonical_name]

        # Update fields
        for key, value in correction.items():
            if key == 'nutrition_per_100g':
                # Update nutrition values
                item['nutrition_per_100g'].update(value)
            else:
                # Update other fields
                item[key] = value

        fixed_count += 1
        print(f"✓ Fixed: {canonical_name}")

# Save corrected JSON
data['items'] = items
data['metadata']['corrected_items'] = fixed_count

with open('backend/data/items_to_enrich_corrected.json', 'w') as f:
    json.dump(data, f, indent=2)

print(f"\n✅ Fixed {fixed_count} items")
print(f"Saved to: backend/data/items_to_enrich_corrected.json")
print("\nPlease review and then copy this to items_to_enrich_readable.json if satisfied.")
