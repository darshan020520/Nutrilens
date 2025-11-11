-- =====================================================
-- RECIPE INGREDIENTS MIGRATION SCRIPT
-- =====================================================
-- Purpose: Update recipe_ingredients to point to new enriched items
--
-- INSTRUCTIONS:
-- 1. First, import enriched items: python scripts/ai_assisted_item_seeding.py import --file backend/backend/data/items_to_enrich_final.json
-- 2. Then run this SQL script to update recipe_ingredients
-- 3. Finally, run the delete script to remove old items
-- =====================================================

-- Step 1: Create mapping of new enriched items
-- This will give us the new IDs after import
CREATE TEMPORARY TABLE new_item_mapping AS
SELECT id as new_id, canonical_name
FROM items
WHERE source = 'usda_fdc'
ORDER BY id DESC
LIMIT 95;

-- Step 2: Update recipe_ingredients for each canonical name
-- Replace old item IDs with new enriched item IDs

-- almonds: old IDs [15, 100] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'almonds')
WHERE item_id IN (15, 100);

-- asparagus: old IDs [76] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'asparagus')
WHERE item_id IN (76);

-- avocado: old IDs [126, 89] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'avocado')
WHERE item_id IN (126, 89);

-- banana: old IDs [16, 79] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'banana')
WHERE item_id IN (16, 79);

-- barley: old IDs [57] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'barley')
WHERE item_id IN (57);

-- beef_lean: old IDs [42] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'beef_lean')
WHERE item_id IN (42);

-- bell_pepper: old IDs [28, 65] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'bell_pepper')
WHERE item_id IN (28, 65);

-- black_beans: old IDs [46] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'black_beans')
WHERE item_id IN (46);

-- black_lentils: old IDs [21] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'black_lentils')
WHERE item_id IN (21);

-- black_pepper: old IDs [117] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'black_pepper')
WHERE item_id IN (117);

-- blueberry: old IDs [88] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'blueberry')
WHERE item_id IN (88);

-- bread_whole_wheat: old IDs [54] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'bread_whole_wheat')
WHERE item_id IN (54);

-- broccoli: old IDs [19, 60] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'broccoli')
WHERE item_id IN (19, 60);

-- brown_rice: old IDs [124, 50] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'brown_rice')
WHERE item_id IN (124, 50);

-- buckwheat: old IDs [58] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'buckwheat')
WHERE item_id IN (58);

-- butter: old IDs [97] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'butter')
WHERE item_id IN (97);

-- cardamom: old IDs [122] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'cardamom')
WHERE item_id IN (122);

-- carrot: old IDs [30, 62] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'carrot')
WHERE item_id IN (30, 62);

-- cashews: old IDs [102] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'cashews')
WHERE item_id IN (102);

-- cauliflower: old IDs [27, 61] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'cauliflower')
WHERE item_id IN (27, 61);

-- cheese: old IDs [96] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'cheese')
WHERE item_id IN (96);

-- chia_seeds: old IDs [105] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'chia_seeds')
WHERE item_id IN (105);

-- chicken_breast: old IDs [130, 1, 31] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'chicken_breast')
WHERE item_id IN (130, 1, 31);

-- chicken_thigh: old IDs [32] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'chicken_thigh')
WHERE item_id IN (32);

-- chickpeas: old IDs [18, 45] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'chickpeas')
WHERE item_id IN (18, 45);

-- coconut_oil: old IDs [110] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'coconut_oil')
WHERE item_id IN (110);

-- coriander_seeds: old IDs [119] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'coriander_seeds')
WHERE item_id IN (119);

-- corn: old IDs [72] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'corn')
WHERE item_id IN (72);

-- cream: old IDs [98] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'cream')
WHERE item_id IN (98);

-- cucumber: old IDs [29, 66] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'cucumber')
WHERE item_id IN (29, 66);

-- cumin: old IDs [118] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'cumin')
WHERE item_id IN (118);

-- dal_lentils: old IDs [127] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'dal_lentils')
WHERE item_id IN (127);

-- dates: old IDs [93] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'dates')
WHERE item_id IN (93);

-- eggplant: old IDs [77] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'eggplant')
WHERE item_id IN (77);

-- eggs: old IDs [6, 33] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'eggs')
WHERE item_id IN (6, 33);

-- egg_whites: old IDs [34] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'egg_whites')
WHERE item_id IN (34);

-- fish_salmon: old IDs [39] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'fish_salmon')
WHERE item_id IN (39);

-- garlic: old IDs [25, 114] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'garlic')
WHERE item_id IN (25, 114);

-- ghee: old IDs [112] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'ghee')
WHERE item_id IN (112);

-- ginger: old IDs [24, 115] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'ginger')
WHERE item_id IN (24, 115);

-- grapes: old IDs [83] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'grapes')
WHERE item_id IN (83);

-- greek_yogurt: old IDs [10, 37] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'greek_yogurt')
WHERE item_id IN (10, 37);

-- green_beans: old IDs [70] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'green_beans')
WHERE item_id IN (70);

-- green_chili: old IDs [120] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'green_chili')
WHERE item_id IN (120);

-- green_lentils: old IDs [22] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'green_lentils')
WHERE item_id IN (22);

-- guava: old IDs [92] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'guava')
WHERE item_id IN (92);

-- kale: old IDs [75] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'kale')
WHERE item_id IN (75);

-- kidney_beans: old IDs [47] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'kidney_beans')
WHERE item_id IN (47);

-- kiwi: old IDs [90] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'kiwi')
WHERE item_id IN (90);

-- lentils: old IDs [44] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'lentils')
WHERE item_id IN (44);

-- lettuce: old IDs [74] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'lettuce')
WHERE item_id IN (74);

-- mango: old IDs [82] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'mango')
WHERE item_id IN (82);

-- millet: old IDs [56] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'millet')
WHERE item_id IN (56);

-- mushroom: old IDs [73] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'mushroom')
WHERE item_id IN (73);

-- mustard_oil: old IDs [111] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'mustard_oil')
WHERE item_id IN (111);

-- oats: old IDs [13, 52] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'oats')
WHERE item_id IN (13, 52);

-- okra: old IDs [78] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'okra')
WHERE item_id IN (78);

-- olive_oil: old IDs [12, 109] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'olive_oil')
WHERE item_id IN (12, 109);

-- onion: old IDs [7, 64] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'onion')
WHERE item_id IN (7, 64);

-- NOTE: orange_juice in enriched file but old items have "Orange" (81)
-- This needs manual correction in enriched file to "orange"
-- Skipping for now - user is manually fixing this

-- papaya: old IDs [86] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'papaya')
WHERE item_id IN (86);

-- pasta: old IDs [55] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'pasta')
WHERE item_id IN (55);

-- peanuts: old IDs [103] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'peanuts')
WHERE item_id IN (103);

-- NOTE: green_peas in enriched file but old items have "Peas" (71)
-- This needs manual correction in enriched file to "peas"
-- Skipping for now - user is manually fixing this

-- pineapple: old IDs [85] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'pineapple')
WHERE item_id IN (85);

-- pistachios: old IDs [104] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'pistachios')
WHERE item_id IN (104);

-- pomegranate: old IDs [91] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'pomegranate')
WHERE item_id IN (91);

-- potato: old IDs [26, 69] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'potato')
WHERE item_id IN (26, 69);

-- pumpkin_seeds: old IDs [107] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'pumpkin_seeds')
WHERE item_id IN (107);

-- quinoa: old IDs [11, 51] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'quinoa')
WHERE item_id IN (11, 51);

-- red_lentils: old IDs [4] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'red_lentils')
WHERE item_id IN (4);

-- NOTE: rice_cakes in enriched file but old items have "rice" (131)
-- This needs manual correction in enriched file to "rice"
-- Skipping for now - user is manually fixing this

-- roti: old IDs [128] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'roti')
WHERE item_id IN (128);

-- salmon: old IDs [20] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'salmon')
WHERE item_id IN (20);

-- shrimp: old IDs [41] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'shrimp')
WHERE item_id IN (41);

-- soy_chunks: old IDs [48] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'soy_chunks')
WHERE item_id IN (48);

-- spinach: old IDs [9, 59] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'spinach')
WHERE item_id IN (9, 59);

-- strawberry: old IDs [87] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'strawberry')
WHERE item_id IN (87);

-- sunflower_seeds: old IDs [108] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'sunflower_seeds')
WHERE item_id IN (108);

-- sweet_potato: old IDs [14, 68] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'sweet_potato')
WHERE item_id IN (14, 68);

-- tofu: old IDs [123, 36] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'tofu')
WHERE item_id IN (123, 36);

-- tomato: old IDs [8, 63, 132] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'tomato')
WHERE item_id IN (8, 63, 132);

-- tuna: old IDs [40] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'tuna')
WHERE item_id IN (40);

-- turkey_breast: old IDs [43] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'turkey_breast')
WHERE item_id IN (43);

-- turmeric: old IDs [116] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'turmeric')
WHERE item_id IN (116);

-- turmeric_powder: old IDs [23] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'turmeric_powder')
WHERE item_id IN (23);

-- vegetable_oil: old IDs [113] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'vegetable_oil')
WHERE item_id IN (113);

-- walnuts: old IDs [101] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'walnuts')
WHERE item_id IN (101);

-- watermelon: old IDs [84] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'watermelon')
WHERE item_id IN (84);

-- wheat_flour: old IDs [53] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'wheat_flour')
WHERE item_id IN (53);

-- whey_protein: old IDs [38] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'whey_protein')
WHERE item_id IN (38);

-- white_rice: old IDs [49] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'white_rice')
WHERE item_id IN (49);

-- whole_wheat_bread: old IDs [125] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'whole_wheat_bread')
WHERE item_id IN (125);

-- whole_wheat_flour: old IDs [3] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'whole_wheat_flour')
WHERE item_id IN (3);

-- zucchini: old IDs [67] -> new ID
UPDATE recipe_ingredients
SET item_id = (SELECT new_id FROM new_item_mapping WHERE canonical_name = 'zucchini')
WHERE item_id IN (67);

-- NOTE: Missing old items that don't have enriched equivalents:
-- - apple (old IDs: 129, 80) - NOT in enriched file
-- - basmati_rice (old ID: 2) - NOT in enriched file
-- - cinnamon (old ID: 121) - NOT in enriched file
-- - milk (old ID: 17) - NOT in enriched file
-- - milk_skim (old ID: 95) - NOT in enriched file
-- - milk_whole (old ID: 94) - NOT in enriched file
-- These items are in old database but were not included in the enriched list
-- User needs to decide what to do with these

-- Clean up temporary table
DROP TABLE new_item_mapping;

-- Verification query - run this after migration to check for orphaned recipe_ingredients
SELECT ri.id, ri.recipe_id, ri.item_id, ri.original_ingredient_text
FROM recipe_ingredients ri
LEFT JOIN items i ON ri.item_id = i.id
WHERE i.id IS NULL;
