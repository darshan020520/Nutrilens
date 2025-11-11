"""
Spoonacular API Client for Recipe Fetching
==========================================

Minimal client for:
1. Constraint-based recipe search (calories, macros, diet, cuisine)
2. Recipe details (title, instructions, image, raw ingredients)

Does NOT use Spoonacular for:
- Ingredient parsing (we use LLM)
- Unit conversion (we use LLM)
- Ingredient database (we use FDC + RAG)
"""

import httpx
import json
import redis
import logging
from typing import List, Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class SpoonacularClient:
    """
    Minimal Spoonacular client - ONLY for recipe data source

    Cost: 1 point per search + 0.01 per result
          1 point per recipe detail fetch
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, 'spoonacular_api_key', None)
        self.base_url = "https://api.spoonacular.com"
        self.redis_client = redis.from_url(settings.redis_url)
        self.cache_ttl = 604800  # 7 days

        if not self.api_key:
            logger.warning("No Spoonacular API key provided. Some features will be unavailable.")

    async def search_recipes_by_constraints(
        self,
        min_calories: Optional[int] = None,
        max_calories: Optional[int] = None,
        min_protein: Optional[int] = None,
        max_protein: Optional[int] = None,
        min_carbs: Optional[int] = None,
        max_carbs: Optional[int] = None,
        min_fat: Optional[int] = None,
        max_fat: Optional[int] = None,
        diet: Optional[str] = None,
        intolerances: Optional[str] = None,
        cuisine: Optional[str] = None,
        max_ready_time: Optional[int] = None,
        number: int = 50,
        offset: int = 0,
        sort: str = "max-used-ingredients"
    ) -> List[Dict]:
        """
        Search recipes with nutritional and dietary constraints

        Args:
            min_calories/max_calories: Calorie range per serving
            min_protein/max_protein: Protein in grams
            min_carbs/max_carbs: Carbs in grams
            min_fat/max_fat: Fat in grams
            diet: vegetarian, vegan, paleo, keto, etc.
            intolerances: gluten, dairy, etc. (comma-separated)
            cuisine: mediterranean, italian, etc.
            max_ready_time: Max prep time in minutes
            number: Number of results (max 100)
            offset: Pagination offset
            sort: "max-used-ingredients", "healthiness", "time", etc.

        Returns:
            List of recipe summaries with basic info
        """
        if not self.api_key:
            raise ValueError("Spoonacular API key required for recipe search")

        # Build cache key
        cache_key = f"spoonacular:search:{min_calories}:{max_calories}:{min_protein}:{diet}:{cuisine}:{number}:{offset}"
        cached = self.redis_client.get(cache_key)
        if cached:
            logger.info(f"Cache hit for recipe search")
            return json.loads(cached)

        # Build params
        params = {
            'apiKey': self.api_key,
            'number': number,
            'offset': offset,
            'sort': sort,
            'addRecipeInformation': False,  # We'll fetch details separately
            'fillIngredients': False,  # Not needed for search
        }

        # Add nutritional constraints
        if min_calories is not None:
            params['minCalories'] = min_calories
        if max_calories is not None:
            params['maxCalories'] = max_calories
        if min_protein is not None:
            params['minProtein'] = min_protein
        if max_protein is not None:
            params['maxProtein'] = max_protein
        if min_carbs is not None:
            params['minCarbs'] = min_carbs
        if max_carbs is not None:
            params['maxCarbs'] = max_carbs
        if min_fat is not None:
            params['minFat'] = min_fat
        if max_fat is not None:
            params['maxFat'] = max_fat

        # Add dietary constraints
        if diet:
            params['diet'] = diet
        if intolerances:
            params['intolerances'] = intolerances
        if cuisine:
            params['cuisine'] = cuisine
        if max_ready_time:
            params['maxReadyTime'] = max_ready_time

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/recipes/complexSearch"

                # Log to both logger and console
                print(f"\n{'='*80}")
                print(f"SPOONACULAR API REQUEST")
                print(f"{'='*80}")
                print(f"URL: {url}")
                print(f"Parameters:")
                for key, value in params.items():
                    if key == 'apiKey':
                        print(f"  {key}: {value[:10]}...")
                    else:
                        print(f"  {key}: {value}")
                print(f"{'='*80}\n")

                logger.info(f"Searching Spoonacular recipes with constraints")

                response = await client.get(
                    url,
                    params=params,
                    timeout=30.0
                )

                print(f"Response Status: {response.status_code}")

                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', [])

                    print(f"✅ Success! Found {len(results)} recipes")
                    logger.info(f"Found {len(results)} recipes matching constraints")

                    # Cache the result
                    self.redis_client.setex(
                        cache_key,
                        self.cache_ttl,
                        json.dumps(results)
                    )

                    return results

                elif response.status_code == 402:
                    print(f"❌ ERROR: Spoonacular API quota exceeded (402)")
                    print(f"Response: {response.text}")
                    logger.error("Spoonacular API quota exceeded (402)")
                    raise Exception("Spoonacular API quota exceeded. Please upgrade plan.")

                else:
                    print(f"❌ ERROR: Status {response.status_code}")
                    print(f"Response: {response.text}")
                    logger.error(f"Spoonacular API error: {response.status_code} - {response.text}")
                    return []

        except httpx.TimeoutException:
            logger.error("Spoonacular API timeout")
            return []
        except Exception as e:
            logger.error(f"Spoonacular search error: {e}")
            return []

    async def get_recipe_details(self, recipe_id: int) -> Optional[Dict]:
        """
        Get detailed recipe information

        Args:
            recipe_id: Spoonacular recipe ID

        Returns:
            {
                'id': 716429,
                'title': 'Pasta with Garlic...',
                'image': 'https://...',
                'servings': 2,
                'ready_in_minutes': 45,
                'instructions': '1. Boil water...',
                'cuisines': ['italian'],
                'diets': ['vegetarian'],
                'raw_ingredients': [
                    '2 cups diced cucumber',
                    '1 lb chicken breast',
                    ...
                ]
            }
        """
        if not self.api_key:
            raise ValueError("Spoonacular API key required")

        # Check cache
        cache_key = f"spoonacular:recipe:{recipe_id}"
        cached = self.redis_client.get(cache_key)
        if cached:
            logger.info(f"Cache hit for recipe {recipe_id}")
            return json.loads(cached)

        try:
            async with httpx.AsyncClient() as client:
                logger.info(f"Fetching recipe details for ID {recipe_id}")
                response = await client.get(
                    f"{self.base_url}/recipes/{recipe_id}/information",
                    params={'apiKey': self.api_key},
                    timeout=15.0
                )

                if response.status_code == 200:
                    data = response.json()

                    # Extract ONLY what we need
                    recipe_data = {
                        'id': data['id'],
                        'title': data['title'],
                        'image': data.get('image'),
                        'servings': data['servings'],
                        'ready_in_minutes': data['readyInMinutes'],
                        'instructions': self._format_instructions(data.get('analyzedInstructions', [])),
                        'cuisines': data.get('cuisines', []),
                        'diets': data.get('diets', []),

                        # RAW ingredient text - we'll parse with LLM
                        'raw_ingredients': [
                            ing.get('original', ing.get('name', ''))
                            for ing in data.get('extendedIngredients', [])
                        ]
                    }

                    # Cache the result
                    self.redis_client.setex(
                        cache_key,
                        self.cache_ttl,
                        json.dumps(recipe_data)
                    )

                    logger.info(f"Successfully fetched recipe '{recipe_data['title']}' with {len(recipe_data['raw_ingredients'])} ingredients")

                    return recipe_data

                elif response.status_code == 402:
                    logger.error("Spoonacular API quota exceeded (402)")
                    raise Exception("Spoonacular API quota exceeded")

                else:
                    logger.error(f"Spoonacular API error: {response.status_code}")
                    return None

        except httpx.TimeoutException:
            logger.error(f"Spoonacular API timeout for recipe {recipe_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching recipe {recipe_id}: {e}")
            return None

    def _format_instructions(self, analyzed_instructions: List[Dict]) -> str:
        """
        Convert Spoonacular's analyzedInstructions to simple text

        Input:
            [
                {
                    "name": "",
                    "steps": [
                        {"number": 1, "step": "Boil water..."},
                        {"number": 2, "step": "Add pasta..."}
                    ]
                }
            ]

        Output:
            "1. Boil water...\n2. Add pasta..."
        """
        if not analyzed_instructions:
            return ""

        steps = []
        for instruction_set in analyzed_instructions:
            for step in instruction_set.get('steps', []):
                steps.append(f"{step['number']}. {step['step']}")

        return "\n".join(steps)

    async def search_recipes_by_goal(
        self,
        goal_calories_per_meal: float,
        protein_target: float,
        carbs_target: float,
        fat_target: float,
        dietary_tags: Optional[List[str]] = None,
        cuisine: Optional[str] = None,
        max_prep_time: Optional[int] = None,
        number: int = 50
    ) -> List[Dict]:
        """
        Helper method: Search recipes for specific goal type

        Automatically applies ±50% calorie flexibility and ±20% macro flexibility
        (matching optimizer behavior)

        Args:
            goal_calories_per_meal: Target calories per meal
            protein_target: Target protein in grams
            carbs_target: Target carbs in grams
            fat_target: Target fat in grams
            dietary_tags: List of dietary preferences (vegan, keto, etc.)
            cuisine: Cuisine filter
            max_prep_time: Max prep time in minutes
            number: Number of recipes to fetch

        Returns:
            List of recipe summaries
        """
        # Apply optimizer's flexibility ranges
        min_cal = int(goal_calories_per_meal * 0.5)
        max_cal = int(goal_calories_per_meal * 1.5)

        min_protein = int(protein_target * 0.8)
        max_protein = int(protein_target * 1.2)

        min_carbs = int(carbs_target * 0.8)
        max_carbs = int(carbs_target * 1.2)

        min_fat = int(fat_target * 0.8)
        max_fat = int(fat_target * 1.2)

        # Convert dietary_tags list to comma-separated string
        diet = dietary_tags[0] if dietary_tags else None

        logger.info(
            f"Searching recipes for goal: "
            f"{min_cal}-{max_cal} cal, "
            f"{min_protein}-{max_protein}g protein, "
            f"{min_carbs}-{max_carbs}g carbs, "
            f"{min_fat}-{max_fat}g fat"
        )

        return await self.search_recipes_by_constraints(
            min_calories=min_cal,
            max_calories=max_cal,
            min_protein=min_protein,
            max_protein=max_protein,
            min_carbs=min_carbs,
            max_carbs=max_carbs,
            min_fat=min_fat,
            max_fat=max_fat,
            diet=diet,
            cuisine=cuisine,
            max_ready_time=max_prep_time,
            number=number
        )
