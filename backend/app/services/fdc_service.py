import httpx
import asyncio
from typing import Dict, Optional, List
import json
from app.core.config import settings
import redis
import logging

logger = logging.getLogger(__name__)

class FDCService:
    """
    FoodData Central API Service
    Falls back to local data if API is unavailable
    """
    
    def __init__(self):
        self.api_key = settings.fdc_api_key if hasattr(settings, 'fdc_api_key') else None
        self.base_url = "https://api.nal.usda.gov/fdc/v1"
        self.redis_client = redis.from_url(settings.redis_url)
        self.cache_ttl = 604800  # 7 days in seconds
        
    async def search_food(self, query: str) -> List[Dict]:
        """Search for food items"""
        # Check cache first
        cache_key = f"fdc:search:{query.lower()}"
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # If no API key, use local search
        if not self.api_key:
            return self._local_search(query)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/foods/search",
                    params={
                        "query": query,
                        "api_key": self.api_key,
                        "limit": 10,
                        "dataType": "Foundation,SR Legacy"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    foods = data.get('foods', [])
                    
                    # Cache the result
                    self.redis_client.setex(
                        cache_key,
                        self.cache_ttl,
                        json.dumps(foods)
                    )
                    
                    return foods
                else:
                    logger.warning(f"FDC API returned status {response.status_code}")
                    return self._local_search(query)
                    
        except Exception as e:
            logger.error(f"FDC API error: {e}")
            return self._local_search(query)
    
    async def get_nutrition(self, food_name: str) -> Optional[Dict]:
        """Get nutrition information for a food item"""
        # Check cache
        cache_key = f"fdc:nutrition:{food_name.lower()}"
        cached = self.redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Search for the food
        foods = await self.search_food(food_name)
        if not foods:
            return None
        
        # Get the first result
        food = foods[0]
        nutrition = self._parse_fdc_nutrients(food)
        
        # Cache the result
        if nutrition:
            self.redis_client.setex(
                cache_key,
                self.cache_ttl,
                json.dumps(nutrition)
            )
        
        return nutrition
    
    def _parse_fdc_nutrients(self, food_data: Dict) -> Dict:
        """Parse FDC food data into our nutrition format

        Complete nutrient ID mapping verified from 21 items, 60 FDC matches:
        - Calories: 4 different IDs (1008 SR Legacy kcal, 2047/2048 Foundation Atwater, 1062 kJ)
        - Other nutrients: Universal IDs across data types
        - Fiber: Often missing in Foundation data (only 49/60 matches have it)
        """
        nutrients = {
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "fiber_g": 0,
            "sodium_mg": 0
        }

        # Complete nutrient ID mapping - verified from all debug files
        # Multiple IDs can map to same field (especially calories)
        nutrient_map = {
            # CALORIES - 4 different IDs across data types
            1008: 'calories',  # Energy (kcal) - SR Legacy
            2047: 'calories',  # Energy (Atwater General) - Foundation
            2048: 'calories',  # Energy (Atwater Specific) - Foundation
            1062: 'calories_kj',  # Energy (kJ) - needs conversion

            # PROTEIN - Universal ID
            1003: 'protein_g',

            # CARBS - Universal ID
            1005: 'carbs_g',

            # FAT - Universal ID
            1004: 'fat_g',

            # FIBER - Universal ID but often missing (only 49/60 matches)
            1079: 'fiber_g',

            # SODIUM - Universal ID
            1093: 'sodium_mg',
        }

        # Track kJ for conversion if kcal not available
        calories_kj = 0

        # Parse all nutrients
        for nutrient in food_data.get('foodNutrients', []):
            nutrient_id = nutrient.get('nutrientId') or nutrient.get('nutrient', {}).get('id')

            if nutrient_id not in nutrient_map:
                continue

            value = nutrient.get('value', 0)
            if value == 0:
                continue

            field_name = nutrient_map[nutrient_id]

            # Handle kJ separately for conversion
            if field_name == 'calories_kj':
                calories_kj = value
                continue

            # For all other fields, use first non-zero value found
            if nutrients[field_name] == 0:
                nutrients[field_name] = round(value, 2)

        # Fallback: Convert kJ to kcal if no kcal value found (1 kcal = 4.184 kJ)
        if nutrients['calories'] == 0 and calories_kj > 0:
            nutrients['calories'] = round(calories_kj / 4.184, 2)
            logger.debug(f"Converted {calories_kj} kJ to {nutrients['calories']} kcal")

        return nutrients
    
    def _local_search(self, query: str) -> List[Dict]:
        """Fallback to local database search"""
        from app.models.database import Item, get_db
        
        db = next(get_db())
        items = db.query(Item).filter(
            Item.canonical_name.ilike(f"%{query}%")
        ).limit(10).all()
        
        results = []
        for item in items:
            results.append({
                "description": item.canonical_name,
                "foodNutrients": self._convert_to_fdc_format(item.nutrition_per_100g)
            })
        
        return results
    
    def _convert_to_fdc_format(self, nutrition: Dict) -> List[Dict]:
        """Convert our nutrition format to FDC format for consistency"""
        nutrient_map = {
            'calories': {'nutrientId': 1008, 'nutrientName': 'Energy'},
            'protein_g': {'nutrientId': 1003, 'nutrientName': 'Protein'},
            'fat_g': {'nutrientId': 1004, 'nutrientName': 'Total lipid (fat)'},
            'carbs_g': {'nutrientId': 1005, 'nutrientName': 'Carbohydrate'},
            'fiber_g': {'nutrientId': 1079, 'nutrientName': 'Fiber'},
            'sodium_mg': {'nutrientId': 1093, 'nutrientName': 'Sodium'}
        }
        
        nutrients = []
        for key, value in nutrition.items():
            if key in nutrient_map:
                nutrients.append({
                    'nutrientId': nutrient_map[key]['nutrientId'],
                    'nutrientName': nutrient_map[key]['nutrientName'],
                    'value': value
                })
        
        return nutrients