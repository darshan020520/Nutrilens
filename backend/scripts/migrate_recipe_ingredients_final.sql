-- =====================================================
-- RECIPE INGREDIENTS MIGRATION - FINAL VERSION
-- =====================================================
-- Updates recipe_ingredients to point to new enriched items (IDs 314-405)
-- =====================================================

-- almonds: old [15, 100] -> new 314
UPDATE recipe_ingredients SET item_id = 314 WHERE item_id IN (15, 100);

-- asparagus: old [76] -> new 315
UPDATE recipe_ingredients SET item_id = 315 WHERE item_id IN (76);

-- avocado: old [126, 89] -> new 316
UPDATE recipe_ingredients SET item_id = 316 WHERE item_id IN (126, 89);

-- banana: old [16, 79] -> new 317
UPDATE recipe_ingredients SET item_id = 317 WHERE item_id IN (16, 79);

-- barley: old [57] -> new 318
UPDATE recipe_ingredients SET item_id = 318 WHERE item_id IN (57);

-- beef_lean: old [42] -> new 319
UPDATE recipe_ingredients SET item_id = 319 WHERE item_id IN (42);

-- bell_pepper: old [28, 65] -> new 320
UPDATE recipe_ingredients SET item_id = 320 WHERE item_id IN (28, 65);

-- black_lentils: old [21] -> new 321
UPDATE recipe_ingredients SET item_id = 321 WHERE item_id IN (21);

-- blueberry: old [88] -> new 322
UPDATE recipe_ingredients SET item_id = 322 WHERE item_id IN (88);

-- bread_whole_wheat: old [54] -> new 323
UPDATE recipe_ingredients SET item_id = 323 WHERE item_id IN (54);

-- broccoli: old [19, 60] -> new 324
UPDATE recipe_ingredients SET item_id = 324 WHERE item_id IN (19, 60);

-- brown_rice: old [124, 50] -> new 325
UPDATE recipe_ingredients SET item_id = 325 WHERE item_id IN (124, 50);

-- buckwheat: old [58] -> new 326
UPDATE recipe_ingredients SET item_id = 326 WHERE item_id IN (58);

-- butter: old [97] -> new 327
UPDATE recipe_ingredients SET item_id = 327 WHERE item_id IN (97);

-- cardamom: old [122] -> new 328
UPDATE recipe_ingredients SET item_id = 328 WHERE item_id IN (122);

-- carrot: old [30, 62] -> new 329
UPDATE recipe_ingredients SET item_id = 329 WHERE item_id IN (30, 62);

-- cashews: old [102] -> new 330
UPDATE recipe_ingredients SET item_id = 330 WHERE item_id IN (102);

-- cauliflower: old [27, 61] -> new 331
UPDATE recipe_ingredients SET item_id = 331 WHERE item_id IN (27, 61);

-- cheese: old [96] -> new 332
UPDATE recipe_ingredients SET item_id = 332 WHERE item_id IN (96);

-- chia_seeds: old [105] -> new 333
UPDATE recipe_ingredients SET item_id = 333 WHERE item_id IN (105);

-- chicken_breast: old [130, 1, 31] -> new 334
UPDATE recipe_ingredients SET item_id = 334 WHERE item_id IN (130, 1, 31);

-- chicken_thigh: old [32] -> new 335
UPDATE recipe_ingredients SET item_id = 335 WHERE item_id IN (32);

-- chickpeas: old [18, 45] -> new 336
UPDATE recipe_ingredients SET item_id = 336 WHERE item_id IN (18, 45);

-- coriander_seeds: old [119] -> new 338
UPDATE recipe_ingredients SET item_id = 338 WHERE item_id IN (119);

-- corn: old [72] -> new 339
UPDATE recipe_ingredients SET item_id = 339 WHERE item_id IN (72);

-- cream: old [98] -> new 340
UPDATE recipe_ingredients SET item_id = 340 WHERE item_id IN (98);

-- cucumber: old [29, 66] -> new 341
UPDATE recipe_ingredients SET item_id = 341 WHERE item_id IN (29, 66);

-- cumin: old [118] -> new 342
UPDATE recipe_ingredients SET item_id = 342 WHERE item_id IN (118);

-- dal_lentils: old [127] -> new 343
UPDATE recipe_ingredients SET item_id = 343 WHERE item_id IN (127);

-- dates: old [93] -> new 344
UPDATE recipe_ingredients SET item_id = 344 WHERE item_id IN (93);

-- eggplant: old [77] -> new 345
UPDATE recipe_ingredients SET item_id = 345 WHERE item_id IN (77);

-- eggs: old [6, 33] -> new 346
UPDATE recipe_ingredients SET item_id = 346 WHERE item_id IN (6, 33);

-- egg_whites: old [34] -> new 347
UPDATE recipe_ingredients SET item_id = 347 WHERE item_id IN (34);

-- fish_salmon: old [39] -> new 348
UPDATE recipe_ingredients SET item_id = 348 WHERE item_id IN (39);

-- garlic: old [25, 114] -> new 349
UPDATE recipe_ingredients SET item_id = 349 WHERE item_id IN (25, 114);

-- ghee: old [112] -> new 350
UPDATE recipe_ingredients SET item_id = 350 WHERE item_id IN (112);

-- ginger: old [24, 115] -> new 351
UPDATE recipe_ingredients SET item_id = 351 WHERE item_id IN (24, 115);

-- grapes: old [83] -> new 352
UPDATE recipe_ingredients SET item_id = 352 WHERE item_id IN (83);

-- greek_yogurt: old [10, 37] -> new 353
UPDATE recipe_ingredients SET item_id = 353 WHERE item_id IN (10, 37);

-- green_beans: old [70] -> new 354
UPDATE recipe_ingredients SET item_id = 354 WHERE item_id IN (70);

-- green_chili: old [120] -> new 355
UPDATE recipe_ingredients SET item_id = 355 WHERE item_id IN (120);

-- green_lentils: old [22] -> new 356
UPDATE recipe_ingredients SET item_id = 356 WHERE item_id IN (22);

-- guava: old [92] -> new 357
UPDATE recipe_ingredients SET item_id = 357 WHERE item_id IN (92);

-- kale: old [75] -> new 358
UPDATE recipe_ingredients SET item_id = 358 WHERE item_id IN (75);

-- kidney_beans: old [47] -> new 359
UPDATE recipe_ingredients SET item_id = 359 WHERE item_id IN (47);

-- kiwi: old [90] -> new 360
UPDATE recipe_ingredients SET item_id = 360 WHERE item_id IN (90);

-- lentils: old [44] -> new 361
UPDATE recipe_ingredients SET item_id = 361 WHERE item_id IN (44);

-- lettuce: old [74] -> new 362
UPDATE recipe_ingredients SET item_id = 362 WHERE item_id IN (74);

-- mango: old [82] -> new 363
UPDATE recipe_ingredients SET item_id = 363 WHERE item_id IN (82);

-- millet: old [56] -> new 364
UPDATE recipe_ingredients SET item_id = 364 WHERE item_id IN (56);

-- mushroom: old [73] -> new 365
UPDATE recipe_ingredients SET item_id = 365 WHERE item_id IN (73);

-- mustard_oil: old [111] -> new 366
UPDATE recipe_ingredients SET item_id = 366 WHERE item_id IN (111);

-- oats: old [13, 52] -> new 367
UPDATE recipe_ingredients SET item_id = 367 WHERE item_id IN (13, 52);

-- okra: old [78] -> new 368
UPDATE recipe_ingredients SET item_id = 368 WHERE item_id IN (78);

-- olive_oil: old [12, 109] -> new 369
UPDATE recipe_ingredients SET item_id = 369 WHERE item_id IN (12, 109);

-- onion: old [7, 64] -> new 370
UPDATE recipe_ingredients SET item_id = 370 WHERE item_id IN (7, 64);

-- orange_juice: old [81] -> new 371
UPDATE recipe_ingredients SET item_id = 371 WHERE item_id IN (81);

-- papaya: old [86] -> new 372
UPDATE recipe_ingredients SET item_id = 372 WHERE item_id IN (86);

-- pasta: old [55] -> new 373
UPDATE recipe_ingredients SET item_id = 373 WHERE item_id IN (55);

-- peanuts: old [103] -> new 374
UPDATE recipe_ingredients SET item_id = 374 WHERE item_id IN (103);

-- green_peas: old [71] -> new 375
UPDATE recipe_ingredients SET item_id = 375 WHERE item_id IN (71);

-- pineapple: old [85] -> new 376
UPDATE recipe_ingredients SET item_id = 376 WHERE item_id IN (85);

-- pistachios: old [104] -> new 377
UPDATE recipe_ingredients SET item_id = 377 WHERE item_id IN (104);

-- pomegranate: old [91] -> new 378
UPDATE recipe_ingredients SET item_id = 378 WHERE item_id IN (91);

-- potato: old [26, 69] -> new 379
UPDATE recipe_ingredients SET item_id = 379 WHERE item_id IN (26, 69);

-- quinoa: old [11, 51] -> new 380
UPDATE recipe_ingredients SET item_id = 380 WHERE item_id IN (11, 51);

-- red_lentils: old [4] -> new 381
UPDATE recipe_ingredients SET item_id = 381 WHERE item_id IN (4);

-- rice_cakes: old [131] -> new 382
UPDATE recipe_ingredients SET item_id = 382 WHERE item_id IN (131);

-- roti: old [128] -> new 383
UPDATE recipe_ingredients SET item_id = 383 WHERE item_id IN (128);

-- salmon: old [20] -> new 384
UPDATE recipe_ingredients SET item_id = 384 WHERE item_id IN (20);

-- shrimp: old [41] -> new 385
UPDATE recipe_ingredients SET item_id = 385 WHERE item_id IN (41);

-- soy_chunks: old [48] -> new 386
UPDATE recipe_ingredients SET item_id = 386 WHERE item_id IN (48);

-- spinach: old [9, 59] -> new 387
UPDATE recipe_ingredients SET item_id = 387 WHERE item_id IN (9, 59);

-- strawberry: old [87] -> new 388
UPDATE recipe_ingredients SET item_id = 388 WHERE item_id IN (87);

-- sunflower_seeds: old [108] -> new 389
UPDATE recipe_ingredients SET item_id = 389 WHERE item_id IN (108);

-- sweet_potato: old [14, 68] -> new 390
UPDATE recipe_ingredients SET item_id = 390 WHERE item_id IN (14, 68);

-- tofu: old [123, 36] -> new 391
UPDATE recipe_ingredients SET item_id = 391 WHERE item_id IN (123, 36);

-- tomato: old [8, 63, 132] -> new 392
UPDATE recipe_ingredients SET item_id = 392 WHERE item_id IN (8, 63, 132);

-- tuna: old [40] -> new 393
UPDATE recipe_ingredients SET item_id = 393 WHERE item_id IN (40);

-- turkey_breast: old [43] -> new 394
UPDATE recipe_ingredients SET item_id = 394 WHERE item_id IN (43);

-- turmeric: old [116] -> new 395
UPDATE recipe_ingredients SET item_id = 395 WHERE item_id IN (116);

-- turmeric_powder: old [23] -> new 396
UPDATE recipe_ingredients SET item_id = 396 WHERE item_id IN (23);

-- vegetable_oil: old [113] -> new 397
UPDATE recipe_ingredients SET item_id = 397 WHERE item_id IN (113);

-- walnuts: old [101] -> new 398
UPDATE recipe_ingredients SET item_id = 398 WHERE item_id IN (101);

-- watermelon: old [84] -> new 399
UPDATE recipe_ingredients SET item_id = 399 WHERE item_id IN (84);

-- wheat_flour: old [53] -> new 400
UPDATE recipe_ingredients SET item_id = 400 WHERE item_id IN (53);

-- whey_protein: old [38] -> new 401
UPDATE recipe_ingredients SET item_id = 401 WHERE item_id IN (38);

-- white_rice: old [49] -> new 402
UPDATE recipe_ingredients SET item_id = 402 WHERE item_id IN (49);

-- whole_wheat_bread: old [125] -> new 403
UPDATE recipe_ingredients SET item_id = 403 WHERE item_id IN (125);

-- whole_wheat_flour: old [3] -> new 404
UPDATE recipe_ingredients SET item_id = 404 WHERE item_id IN (3);

-- zucchini: old [67] -> new 405
UPDATE recipe_ingredients SET item_id = 405 WHERE item_id IN (67);

-- Verification query - check for orphaned recipe_ingredients
SELECT
    COUNT(*) as orphaned_count,
    ARRAY_AGG(DISTINCT ri.item_id) as orphaned_item_ids
FROM recipe_ingredients ri
LEFT JOIN items i ON ri.item_id = i.id
WHERE i.id IS NULL;
