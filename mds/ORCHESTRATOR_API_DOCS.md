# NutriLens Orchestrator API Documentation

**Version:** 1.0
**Base URL:** `https://your-domain.com/api/orchestrator`

## Overview

These endpoints provide simplified access to NutriLens features specifically designed for WhatsApp agent integration. All endpoints accept `user_id` directly (no JWT authentication required).

---

## Endpoints

### 1. Get Planned Meal

**Endpoint:** `GET /api/orchestrator/planned-meal`

**Description:** Retrieve a specific planned meal for user confirmation before logging.

**Query Parameters:**
- `user_id` (integer, required) - NutriLens user ID
- `meal_type` (string, required) - One of: `breakfast`, `lunch`, `dinner`, `snack`

**Success Response (200):**
```json
{
    "success": true,
    "meal_log_id": 125,
    "meal_type": "lunch",
    "meal_name": "Grilled Chicken Salad",
    "calories": 500.0,
    "protein": 48.0,
    "carbs": 12.0,
    "fat": 23.0
}
```

**Error Responses:**
- `no_active_plan` - User has no active meal plan
- `meal_not_found` - No meal planned for this type today
- `already_logged` - Meal already logged
- `already_skipped` - Meal was skipped

---

### 2. Log Planned Meal

**Endpoint:** `POST /api/orchestrator/log-meal`

**Description:** Log a planned meal as consumed after user confirmation.

**Request Body:**
```json
{
    "user_id": 123,
    "meal_log_id": 125,
    "portion_multiplier": 1.0
}
```

**Parameters:**
- `user_id` (integer, required) - NutriLens user ID
- `meal_log_id` (integer, required) - ID from get-planned-meal response
- `portion_multiplier` (float, optional, default: 1.0) - Portion adjustment

**Success Response (200):**
```json
{
    "success": true,
    "meal_log_id": 125,
    "calories_remaining": 1500.0,
    "message": "Meal logged successfully"
}
```

---

### 3. Estimate External Meal

**Endpoint:** `POST /api/orchestrator/estimate-external-meal`

**Description:** Get LLM-based nutrition estimation for an external meal (for user confirmation).

**Request Body:**
```json
{
    "user_id": 123,
    "meal_type": "lunch",
    "dish_name": "Margherita Pizza",
    "portion_size": "2 large slices",
    "restaurant_name": "Dominos",
    "cuisine_type": "Italian"
}
```

**Parameters:**
- `user_id` (integer, required) - NutriLens user ID
- `meal_type` (string, required) - `breakfast`, `lunch`, `dinner`, or `snack`
- `dish_name` (string, required) - Name of the dish
- `portion_size` (string, required) - Description like "1 large plate", "300g"
- `restaurant_name` (string, optional) - Restaurant name for better estimation
- `cuisine_type` (string, optional) - Cuisine type (e.g., "Italian", "Indian")

**Success Response (200):**
```json
{
    "success": true,
    "dish_name": "Margherita Pizza",
    "portion_size": "2 large slices",
    "estimated_macros": {
        "calories": 580.0,
        "protein": 24.0,
        "carbs": 72.0,
        "fat": 22.0,
        "fiber": 4.0
    },
    "confidence": 0.85,
    "reasoning": "Based on typical Dominos Margherita pizza nutritional values"
}
```

---

### 4. Log External Meal

**Endpoint:** `POST /api/orchestrator/log-external-meal`

**Description:** Log confirmed external meal after user approves the estimation.

**Request Body:**
```json
{
    "user_id": 123,
    "meal_type": "lunch",
    "dish_name": "Margherita Pizza",
    "portion_size": "2 large slices",
    "calories": 580.0,
    "protein_g": 24.0,
    "carbs_g": 72.0,
    "fat_g": 22.0,
    "fiber_g": 4.0,
    "restaurant_name": "Dominos",
    "cuisine_type": "Italian"
}
```

**Parameters:**
- `user_id` (integer, required) - NutriLens user ID
- `meal_type` (string, required) - Meal type
- `dish_name` (string, required) - Dish name
- `portion_size` (string, required) - Portion description
- `calories` (float, required) - Confirmed calories
- `protein_g` (float, required) - Confirmed protein in grams
- `carbs_g` (float, required) - Confirmed carbs in grams
- `fat_g` (float, required) - Confirmed fat in grams
- `fiber_g` (float, optional) - Confirmed fiber in grams
- `restaurant_name` (string, optional) - Restaurant name
- `cuisine_type` (string, optional) - Cuisine type

**Success Response (200):**
```json
{
    "success": true,
    "meal_log_id": 456,
    "calories_remaining": 1420.0,
    "message": "External meal logged successfully"
}
```

---

## Complete Workflows

### Workflow 1: Log Planned Meal

```
User: "I ate lunch"
    ↓
1. GET /orchestrator/planned-meal?user_id=123&meal_type=lunch
    ↓
   Response: {meal_name: "Grilled Chicken Salad", calories: 500, meal_log_id: 125}
    ↓
WhatsApp: "You planned: Grilled Chicken Salad (500 cal). Confirm?"
    ↓
User: "yes"
    ↓
2. POST /orchestrator/log-meal
   Body: {user_id: 123, meal_log_id: 125}
    ↓
WhatsApp: "✅ Meal logged! 1500 calories remaining"
```

### Workflow 2: Log External Meal

```
User: "I ate pizza at Dominos"
    ↓
1. POST /orchestrator/estimate-external-meal
   Body: {user_id: 123, dish_name: "pizza", portion_size: "2 slices",
          restaurant_name: "Dominos"}
    ↓
   Response: {estimated_macros: {calories: 580, ...}, confidence: 0.85}
    ↓
WhatsApp: "Pizza (2 slices) - ~580 cal. Confirm?"
    ↓
User: "yes"
    ↓
2. POST /orchestrator/log-external-meal
   Body: {user_id: 123, dish_name: "pizza", calories: 580,
          protein_g: 24, carbs_g: 72, fat_g: 22}
    ↓
WhatsApp: "✅ External meal logged! 1420 calories remaining"
```

---

## Error Handling

All endpoints return errors in this format:
```json
{
    "success": false,
    "error": "error_code",
    "message": "Human-readable error message"
}
```

**Common Error Codes:**
- `no_active_plan` - User has no active meal plan
- `meal_not_found` - Requested meal doesn't exist
- `already_logged` - Meal was already logged
- `already_skipped` - Meal was marked as skipped
- `internal_error` - Server error

---

## Implementation Notes

1. **No JWT Required:** These endpoints accept `user_id` directly
2. **Minimal Duplication:** All endpoints reuse existing NutriLens services
3. **LLM Integration:** External meal estimation uses GPT-4o for accuracy
4. **Daily Summary:** Calories remaining is calculated using existing ConsumptionService
5. **Meal Logging:** Uses TrackingAgent for proper inventory deduction and achievements

---

## Testing

**Test Planned Meal Flow:**
```bash
# 1. Get planned meal
curl "http://localhost:8000/api/orchestrator/planned-meal?user_id=1&meal_type=lunch"

# 2. Log the meal (use meal_log_id from step 1)
curl -X POST "http://localhost:8000/api/orchestrator/log-meal" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 1, "meal_log_id": 125, "portion_multiplier": 1.0}'
```

**Test External Meal Flow:**
```bash
# 1. Estimate external meal
curl -X POST "http://localhost:8000/api/orchestrator/estimate-external-meal" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "meal_type": "lunch",
    "dish_name": "pizza",
    "portion_size": "2 slices",
    "restaurant_name": "Dominos"
  }'

# 2. Log external meal (use estimated values from step 1)
curl -X POST "http://localhost:8000/api/orchestrator/log-external-meal" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "meal_type": "lunch",
    "dish_name": "pizza",
    "portion_size": "2 slices",
    "calories": 580,
    "protein_g": 24,
    "carbs_g": 72,
    "fat_g": 22,
    "fiber_g": 4
  }'
```

---

**Last Updated:** 2025-11-05
**Maintained By:** NutriLens Backend Team
