# backend/app/agents/planning_agent.py

import logging
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from sqlalchemy import cast, String
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import json
from enum import Enum

from sqlalchemy.orm import Session
from langchain.agents import Tool
from langchain.memory import ConversationBufferMemory
from langchain.schema import BaseMessage

from app.services.final_meal_optimizer import MealPlanOptimizer, OptimizationConstraints
from app.services.meal_plan_service import MealPlanService
from app.models.database import MealPlan, Recipe, Item, UserInventory, UserProfile, UserGoal, UserPath, UserPreference, RecipeIngredient, MealLog
from app.schemas.meal_plan import MealPlanCreate, MealPlanResponse
from app.schemas.nutrition import RecipeResponse
from app.schemas.user import ProfileResponse

logger = logging.getLogger(__name__)


class PlanningState(Enum):
    """States for planning agent"""
    IDLE = "idle"
    ANALYZING = "analyzing"
    GENERATING = "generating"
    OPTIMIZING = "optimizing"
    ADJUSTING = "adjusting"
    COMPLETE = "complete"
    ERROR = "error"

@dataclass
class PlanningContext:
    """Context for planning operations"""
    user_id: int
    user_profile: Optional[Dict] = None
    current_goals: Optional[Dict] = None
    active_meal_plan: Optional[Dict] = None
    current_inventory: Optional[Dict[int, float]] = None
    preferences: Optional[Dict] = None
    optimization_params: Optional[Dict] = None
    generation_history: List[Dict] = field(default_factory=list)
    state: PlanningState = PlanningState.IDLE
    error_message: Optional[str] = None

class PlanningAgent:
    """
    Intelligent planning agent that orchestrates meal plan generation
    Uses the LP optimizer and provides additional planning capabilities
    """
    
    def __init__(self, db: Session, llm=None):
        self.db = db
        self.llm = llm
        self.optimizer = MealPlanOptimizer(db)
        self.meal_plan_service = MealPlanService(db)
        self.memory = ConversationBufferMemory()
        self.context: Optional[PlanningContext] = None
        self.tools = self._initialize_tools()
        
    def _initialize_tools(self) -> List[Tool]:
        """Initialize all planning tools"""
        return [
            Tool(
                name="generate_weekly_meal_plan",
                func=self.generate_weekly_meal_plan,
                description="Generate a complete 7-day meal plan optimized for user goals"
            ),
            Tool(
                name="select_recipes_for_goal",
                func=self.select_recipes_for_goal,
                description="Select recipes that align with specific fitness goals"
            ),
            Tool(
                name="calculate_grocery_list",
                func=self.calculate_grocery_list,
                description="Calculate aggregated grocery list from meal plan"
            ),
            Tool(
                name="suggest_meal_prep",
                func=self.suggest_meal_prep,
                description="Suggest batch cooking and meal prep strategies"
            ),
            Tool(
                name="find_recipe_alternatives",
                func=self.find_recipe_alternatives,
                description="Find alternative recipes with similar macros"
            ),
            Tool(
                name="adjust_plan_for_eating_out",
                func=self.adjust_plan_for_eating_out,
                description="Adjust remaining meals when eating out"
            ),
            Tool(
                name="optimize_inventory_usage",
                func=self.optimize_inventory_usage,
                description="Prioritize recipes using expiring ingredients"
            ),
            Tool(
                name="generate_shopping_reminders",
                func=self.generate_shopping_reminders,
                description="Generate smart shopping reminders"
            ),
            Tool(
                name="create_meal_schedule",
                func=self.create_meal_schedule,
                description="Create time-based meal schedule"
            ),
            Tool(
                name="bulk_cooking_suggestions",
                func=self.bulk_cooking_suggestions,
                description="Suggest efficient bulk cooking strategies"
            )
        ]
    
    async def initialize_context(self, user_id: int) -> PlanningContext:
        """Initialize planning context for user"""
        logger.info(f"Initializing planning context for user {user_id}")
        
        # Fetch user data
        user_profile = self.db.query(UserProfile).filter_by(user_id=user_id).first()

        profile_dict = (
            ProfileResponse.model_validate(user_profile).model_dump()
            if user_profile else None
        )
        
        # Get current inventory
        inventory_items = self.db.query(UserInventory).filter_by(user_id=user_id).all()
        inventory = {item.item_id: item.quantity_grams for item in inventory_items}
        
        # Get active meal plan if exists
        active_plan = self.db.query(MealPlan).filter_by(
            user_id=user_id, 
            is_active=True
        ).first()

        active_plan_dict = (
            MealPlanResponse.model_validate(active_plan).model_dump()
            if active_plan else None
        )

        
        self.context = PlanningContext(
            user_id=user_id,
            user_profile=active_plan_dict if user_profile else None,
            current_inventory=inventory,
            active_meal_plan=active_plan_dict if active_plan else None,
            state=PlanningState.IDLE
        )

        
        return self.context
    
    # Tool 1: Generate Weekly Meal Plan
    def generate_weekly_meal_plan(self, **kwargs) -> Dict:
        """
        Generate a complete 7-day meal plan using LP optimizer
        
        Args:
            user_id: User ID
            start_date: Starting date for the plan
            preferences: Optional preference overrides
            
        Returns:
            Generated meal plan with optimization details
        """
        try:

            self.context.state = PlanningState.GENERATING
            
            user_id = kwargs.get('user_id', self.context.user_id)
            start_date = kwargs.get('start_date', datetime.now())
            
            # Get user constraints
            constraints = self._build_optimization_constraints(user_id)
            
            # Run optimizer
            logger.info(f"Running optimizer for user {user_id}")
            meal_plan = self.optimizer.optimize(
                user_id=user_id,
                days=7,
                constraints=constraints,
                inventory=self.context.current_inventory
            )

            print("MEAL PLAN IN GENERATE WEEKLY API CALL", meal_plan)
            
            if not meal_plan:
                raise Exception("Optimizer failed to generate plan")
            
            # Enhance with metadata
            meal_plan['user_id'] = user_id
            meal_plan['start_date'] = start_date.isoformat()
            meal_plan['generated_at'] = datetime.now().isoformat()
            meal_plan['constraints'] = constraints.__dict__
            
            # Calculate grocery list
            meal_plan['grocery_list'] = self.calculate_grocery_list(meal_plan['week_plan'], self.db, user_id)
            
            # Save to database
            saved_plan = self._save_meal_plan(meal_plan)

            # Create meal logs with meal_plan_id linkage
            self._create_meal_logs(meal_plan, saved_plan.id)

            print("saved_plan", saved_plan)
            
            self.context.state = PlanningState.COMPLETE
            self.context.active_meal_plan = saved_plan
            
            logger.info(f"Successfully generated meal plan for user {user_id}")
            return saved_plan
            
        except Exception as e:
            logger.error(f"Error generating meal plan: {str(e)}")
            self.context.state = PlanningState.ERROR
            self.context.error_message = str(e)
            return {"error": str(e)}
    
    # Tool 2: Select Recipes for Goal
    def select_recipes_for_goal(self, goal: str, count: int = 10) -> List[Dict]:
        """
        Select top recipes that align with a specific fitness goal.
        """
        try:
            # Query recipes by goal
            recipes = self.db.query(Recipe).filter(
                cast(Recipe.goals, String).contains(goal)
            ).all()

            if not recipes:
                # Fallback to a wider set of recipes
                recipes = self.db.query(Recipe).limit(count * 2).all()

            # Score recipes for goal
            scored_recipes = []
            for recipe in recipes:
                score = self._score_recipe_for_goal(recipe, goal)
                scored_recipes.append({
                    "recipe": {
                        "id": recipe.id,
                        "title": recipe.title,
                        "description": recipe.description,
                        "prep_time_min": recipe.prep_time_min,
                        "macros_per_serving": recipe.macros_per_serving or {},
                    },
                    "score": score
                })

            # Sort by score and return top N
            scored_recipes.sort(key=lambda x: x["score"], reverse=True)
            return [r["recipe"] for r in scored_recipes[:count]]

        except Exception as e:
            logger.error(f"Error selecting recipes for goal: {str(e)}")
            return []
    
    # Tool 3: Calculate Grocery List
    def calculate_grocery_list(self, meal_plan: Dict, db_session, user_id: int) -> Dict[str, Any]:
        """
        Build a grocery list from a meal plan.
        """
        try:
            grocery_list: Dict[int, Dict[str, Any]] = {}

            # --- Step 1: collect recipe IDs ---
            recipe_ids = [
                recipe["id"]
                for day_data in meal_plan.values()
                for recipe in (day_data.get("meals", {}) or {}).values()
                if recipe and recipe.get("id")
            ]
            if not recipe_ids:
                # 🔹 Return an EMPTY valid response instead of bare dict
                return {                                                        # 🔹 CHANGED
                    "items": {},
                    "categorized": {},
                    "total_items": 0,
                    "items_to_buy": 0,
                    "estimated_cost": None
                }

            # --- Step 2: fetch recipe ingredients ---
            recipe_ingredients = (
                db_session.query(RecipeIngredient)
                .filter(RecipeIngredient.recipe_id.in_(recipe_ids))
                .all()
            )

            # --- Step 3: map item_id -> Item ---
            item_ids = list({ri.item_id for ri in recipe_ingredients})
            items_map = {
                item.id: item
                for item in db_session.query(Item).filter(Item.id.in_(item_ids)).all()
            }

            # --- Step 4: user inventory ---
            inventory_map = {
                inv.item_id: inv.quantity_grams
                for inv in db_session.query(UserInventory)
                .filter(UserInventory.user_id == user_id, UserInventory.item_id.in_(item_ids))
                .all()
            }

            # --- Step 5: aggregate ---
            for ri in recipe_ingredients:
                if not ri.item_id:
                    continue
                if ri.item_id not in grocery_list:
                    item = items_map.get(ri.item_id)
                    grocery_list[ri.item_id] = {
                        "item_id": ri.item_id,                                  # 🔹 ADDED
                        "item_name": item.canonical_name if item else f"Item {ri.item_id}",
                        "category": self._normalize_category(                   # 🔹 CHANGED
                            item.category if item else "other"
                        ),
                        "unit": item.unit if item else "g",
                        "quantity_needed": 0.0,                                 # 🔹 CHANGED: ensure float
                        "quantity_available": 0.0,                              # 🔹 CHANGED
                        "to_buy": 0.0,                                          # 🔹 CHANGED
                    }
                grocery_list[ri.item_id]["quantity_needed"] += ri.quantity_grams

            # --- Step 6: compute to_buy ---
            for item_id, data in grocery_list.items():
                available = inventory_map.get(item_id, 0)
                data["quantity_available"] = available
                data["to_buy"] = max(0, data["quantity_needed"] - available)

            # --- Step 7: categorize ---
            categorized = self._categorize_grocery_list(grocery_list)

            # --- Step 8: convert keys to strings for Pydantic ---
            items_str_keys = {str(k): v for k, v in grocery_list.items()}

            # 🔹 Placeholder for future cost logic
            estimated_cost = None                                               # 🔹 ADDED

            return {
                "items": items_str_keys,
                "categorized": categorized,
                "total_items": len(items_str_keys),
                "items_to_buy": sum(1 for d in grocery_list.values() if d["to_buy"] > 0),
                "estimated_cost": estimated_cost
            }

        except Exception as e:
            logger.exception("Error calculating grocery list")                  # 🔹 CHANGED: use exception
            # 🔹 Return valid but empty response instead of bare dict
            return {                                                            # 🔹 CHANGED
                "items": {},
                "categorized": {},
                "total_items": 0,
                "items_to_buy": 0,
                "estimated_cost": None
            }


    
    # Tool 4: Suggest Meal Prep
    def suggest_meal_prep(self, meal_plan: Dict) -> Dict:
        """
        Suggest batch cooking and meal prep strategies
        
        Args:
            meal_plan: Weekly meal plan
            
        Returns:
            Meal prep suggestions organized by prep day
        """
        try:
            prep_suggestions = {
                'sunday_prep': [],
                'wednesday_prep': [],
                'daily_prep': [],
                'batch_cooking': []
            }
            
            # Analyze recipes for prep opportunities
            recipe_frequency = {}
            prep_intensive = []
            
            for day_key, day_data in meal_plan.items():
                if not day_key.startswith("day_"):
                    continue
                meals = day_data.get("meals", {})
                for recipe in meals.values():
                    if not recipe:
                        continue

                    rid = recipe.get("id")
                    prep_time = recipe.get("prep_time_min", 0)
                    cook_time = recipe.get("cook_time_min", 0)

                    # Track frequency
                    if rid not in recipe_frequency:
                        recipe_frequency[rid] = {"count": 0, "recipe": recipe}
                    recipe_frequency[rid]["count"] += 1

                    # Identify prep-intensive (>30 min total)
                    if prep_time + cook_time > 30:
                        prep_intensive.append(recipe)
            
            # Suggest batch cooking for repeated recipes
            for rid, data in recipe_frequency.items():
                if data["count"] >= 2:
                    prep_suggestions["batch_cooking"].append({
                        "recipe": data["recipe"]["title"],
                        "quantity": f"{data['count']} servings",
                        "benefit": f"Save {(data['count']-1) * data['recipe'].get('cook_time_min', 0)} minutes"
                    })

            for r in prep_intensive:
                prep_suggestions["daily_prep"].append(
                    f"Pre-chop or marinate for '{r['title']}' "
                    f"(~{r.get('prep_time_min',0)}+{r.get('cook_time_min',0)} min)"
                )
            
            # Sunday prep for the week
            prep_suggestions['sunday_prep'] = [
                "Wash and chop all vegetables",
                "Marinate proteins for Mon-Wed",
                "Cook grains in bulk (rice, quinoa)",
                "Prepare breakfast portions"
            ]
            
            # Wednesday mid-week prep
            prep_suggestions['wednesday_prep'] = [
                "Marinate proteins for Thu-Sat",
                "Refresh vegetable prep",
                "Prepare weekend breakfast items"
            ]
            
            return prep_suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting meal prep: {str(e)}")
            return {}
    
    # Tool 5: Find Recipe Alternatives
    def find_recipe_alternatives(self, recipe_id: int, count: int = 5) -> List[Dict]:
        """
        Find alternative recipes - delegates to MealPlanService

        Args:
            recipe_id: Original recipe ID
            count: Number of alternatives to find (default 5)

        Returns:
            List of alternative recipes with similarity scores
        """
        try:
            # Delegate to meal plan service for consistent logic
            from app.services.meal_plan_service import MealPlanService

            meal_service = MealPlanService(self.db)

            # Use user_id from context
            user_id = self.context.user_id if self.context else None
            if not user_id:
                logger.warning("No user_id in context, cannot filter by dietary preferences")
                return []

            alternatives = meal_service.get_alternatives_for_meal(
                recipe_id=recipe_id,
                user_id=user_id,
                count=count
            )

            logger.info(f"Found {len(alternatives)} alternatives for recipe {recipe_id}")

            return alternatives

        except Exception as e:
            logger.error(f"Error finding alternatives: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    # Tool 6: Adjust Plan for Eating Out
    def adjust_plan_for_eating_out(self, day: int, meal: str, restaurant_calories: int) -> Dict:
        """
        Suggest adjusted meals after logging an eating-out event.
        Does not modify the database—only returns suggestions.

        Args:
            day: Day of the week (0-6)
            meal: Meal being replaced (breakfast/lunch/dinner)
            restaurant_calories: Estimated calories from restaurant meal

        Returns:
            Dict containing suggested adjustments or deficit/surplus info.
        """
        try:
            if not self.context.active_meal_plan:
                return {"error": "No active meal plan"}

            plan = self.context.active_meal_plan
            week_start = plan["week_start_date"]
            day_date = week_start + timedelta(days=day)

            day_key = f"day_{day}"
            if day_key not in plan["plan_data"]:
                return {"error": f"Day {day} not in plan"}

            day_plan = plan["plan_data"][day_key]

            print("day plan", day_plan)
            daily_target = day_plan.get("day_calories") or self.context.user_profile.get("goal_calories", 2000)

            # 1️⃣ Get calories already consumed earlier today from MealLog
            consumed_calories = self._get_consumed_calories(user_id=self.context.user_profile["id"], day=day_date, skip_meal=meal, plan_day_data=day_plan)

            # 2️⃣ Add restaurant calories to consumed
            consumed_with_restaurant = consumed_calories + restaurant_calories

            # 3️⃣ Find remaining meals in today's plan (excluding current meal)
            meal_order = list(day_plan["meals"].keys())
            current_index = meal_order.index(meal) if meal in meal_order else -1
            remaining_meals = meal_order[current_index + 1 :] if current_index >= 0 else []

            print("")

            # 4️⃣ If no meals remain, return surplus/deficit info
            if not remaining_meals:
                surplus_deficit = consumed_with_restaurant - daily_target
                return {
                    "adjusted_day": day,
                    "message": f"No remaining meals today. Net {'surplus' if surplus_deficit > 0 else 'deficit'}: {abs(surplus_deficit)} kcal",
                    "consumed": consumed_with_restaurant,
                    "daily_target": daily_target,
                }

            # 5️⃣ Calculate remaining calories for the rest of the day
            remaining_calories = max(0, daily_target - consumed_with_restaurant)
            calories_per_meal = remaining_calories / len(remaining_meals)

            # 6️⃣ Suggest adjusted recipes for remaining meals
            adjusted_meals = {}
            for meal_name in remaining_meals:
                candidates = self._find_recipes_by_calories(
                    calories_per_meal, tolerance=0.2, meal_type=meal_name
                )
                if candidates:
                    adjusted_meals[meal_name] = candidates[0]

        

            # Include the external meal for clarity in the suggestion payload
            adjusted_meals[meal] = {
                "title": "Eating Out",
                "macros_per_serving": {
                    "calories": restaurant_calories,
                    "protein_g": restaurant_calories * 0.3 / 4,
                    "carbs_g": restaurant_calories * 0.4 / 4,
                    "fat_g": restaurant_calories * 0.3 / 9,
                },
                "is_external": True,
            }

            print("adjusted_meals", adjusted_meals)

            return {
                "adjusted_day": day,
                "meals": adjusted_meals,
                "remaining_calories": remaining_calories,
                "consumed_so_far": consumed_with_restaurant,
                "daily_target": daily_target,
                "message": f"Suggested adjustments for day {day+1} after eating out",
            }

        except Exception as e:
            logger.error(f"Error adjusting for eating out: {str(e)}")
            return {"error": str(e)}
    
    # Tool 7: Optimize Inventory Usage
    def optimize_inventory_usage(self) -> Dict:
        """
        Prioritize recipes using expiring ingredients
        
        Returns:
            Recipes prioritized by expiring inventory
        """
        try:
            # Get expiring items (within 3 days)
            expiry_threshold = datetime.now() + timedelta(days=3)
            
            expiring_items = self.db.query(UserInventory).filter(
                UserInventory.user_id == self.context.user_id,
                UserInventory.expiry_date <= expiry_threshold,
                UserInventory.quantity_grams > 0
            ).all()
            
            if not expiring_items:
                return {
                    'message': 'No expiring items',
                    'recipes': []
                }
            
            # Find recipes using these items
            prioritized_recipes = []
            
            for item in expiring_items:
                recipes = self.db.query(Recipe).join(
                    Recipe.ingredients
                ).filter(
                    Recipe.ingredients.any(item_id=item.item_id)
                ).all()
                
                for recipe in recipes:
                    prioritized_recipes.append({
                        'recipe': recipe.to_dict(),
                        'expiring_ingredient': item.item_id,
                        'days_until_expiry': (item.expiry_date - datetime.now()).days,
                        'quantity_available': item.quantity_grams
                    })
            
            # Sort by expiry urgency
            prioritized_recipes.sort(key=lambda x: x['days_until_expiry'])
            
            return {
                'expiring_items_count': len(expiring_items),
                'recipes': prioritized_recipes[:10],
                'message': f"Found {len(prioritized_recipes)} recipes using expiring ingredients"
            }
            
        except Exception as e:
            logger.error(f"Error optimizing inventory: {str(e)}")
            return {"error": str(e)}
    
    # Tool 8: Generate Shopping Reminders
    def generate_shopping_reminders(self) -> List[Dict]:
        """
        Generate smart shopping reminders based on patterns and inventory
        
        Returns:
            List of shopping reminders with priorities
        """
        try:
            reminders = []
            
            # Check staple items
            staples = self.db.query(UserInventory).filter(
                UserInventory.user_id == self.context.user_id,
                UserInventory.is_staple == True,
                UserInventory.quantity_grams < 100  # Low threshold
            ).all()
            
            for item in staples:
                reminders.append({
                    'type': 'staple_low',
                    'item_id': item.item_id,
                    'message': f"Staple item running low",
                    'priority': 'high',
                    'quantity_remaining': item.quantity_grams
                })
            
            # Check for weekend shopping
            if datetime.now().weekday() == 4:  # Friday
                reminders.append({
                    'type': 'weekend_prep',
                    'message': "Weekend grocery shopping for meal prep",
                    'priority': 'medium',
                    'suggested_day': 'Saturday morning'
                })
            
            # Check meal plan requirements
            if self.context.active_meal_plan:
                grocery_list = self.calculate_grocery_list(self.context.active_meal_plan)
                items_to_buy = grocery_list.get('items_to_buy', 0)
                
                if items_to_buy > 0:
                    reminders.append({
                        'type': 'meal_plan_requirements',
                        'message': f"Need to buy {items_to_buy} items for meal plan",
                        'priority': 'high',
                        'grocery_list': grocery_list
                    })
            
            return reminders
            
        except Exception as e:
            logger.error(f"Error generating reminders: {str(e)}")
            return []
    
    # Tool 9: Create Meal Schedule
    def create_meal_schedule(self, meal_plan: Dict) -> Dict:
        """
        Create time-based meal schedule based on user preferences
        
        Args:
            meal_plan: Weekly meal plan
            
        Returns:
            Time-scheduled meals for each day
        """
        try:
            # Get user's meal timing preferences
            meal_windows = self._get_user_meal_windows()
            
            scheduled_plan = {}
            
            for day_key, day_data in meal_plan.get('week_plan', {}).items():
                day_num = int(day_key.split('_')[1])
                scheduled_day = {
                    'date': (datetime.now() + timedelta(days=day_num)).strftime('%Y-%m-%d'),
                    'meals': []
                }
                
                for meal_name, recipe in day_data.get('meals', {}).items():
                    if recipe:
                        meal_time = meal_windows.get(meal_name, {})
                        scheduled_day['meals'].append({
                            'time': meal_time.get('start', '12:00'),
                            'meal_type': meal_name,
                            'recipe': recipe['title'],
                            'prep_time': recipe.get('prep_time_min', 0),
                            'calories': recipe['macros_per_serving']['calories']
                        })
                
                # Sort by time
                scheduled_day['meals'].sort(key=lambda x: x['time'])
                scheduled_plan[day_key] = scheduled_day
            
            return {
                'schedule': scheduled_plan,
                'meal_windows': meal_windows,
                'total_meals': sum(
                    len(day['meals']) 
                    for day in scheduled_plan.values()
                )
            }
            
        except Exception as e:
            logger.error(f"Error creating schedule: {str(e)}")
            return {}
    
    # Tool 10: Bulk Cooking Suggestions
    def bulk_cooking_suggestions(self, meal_plan: Dict) -> List[Dict]:
        """
        Suggest efficient bulk cooking strategies
        
        Args:
            meal_plan: Weekly meal plan
            
        Returns:
            Bulk cooking suggestions with efficiency metrics
        """
        try:
            suggestions = []
            
            # Analyze common ingredients
            ingredient_usage = {}
            recipe_frequency = {}
            
            for day_data in meal_plan.get('week_plan', {}).values():
                for recipe in day_data.get('meals', {}).values():
                    if recipe:
                        # Track recipe frequency
                        recipe_id = recipe.get('id')
                        if recipe_id not in recipe_frequency:
                            recipe_frequency[recipe_id] = {
                                'recipe': recipe,
                                'count': 0
                            }
                        recipe_frequency[recipe_id]['count'] += 1
                        
                        # Track ingredient usage
                        for ingredient in recipe.get('ingredients', []):
                            item_id = ingredient.get('item_id')
                            if item_id not in ingredient_usage:
                                ingredient_usage[item_id] = {
                                    'total_quantity': 0,
                                    'recipes': []
                                }
                            ingredient_usage[item_id]['total_quantity'] += ingredient.get('quantity_g', 0)
                            ingredient_usage[item_id]['recipes'].append(recipe['title'])
            
            # Suggest bulk prep for frequently used ingredients
            for item_id, usage in ingredient_usage.items():
                if len(usage['recipes']) >= 3:
                    suggestions.append({
                        'type': 'ingredient_prep',
                        'item_id': item_id,
                        'action': f"Prep {usage['total_quantity']}g in bulk",
                        'used_in': usage['recipes'],
                        'time_saved': len(usage['recipes']) * 5  # Estimate 5 min per use
                    })
            
            # Suggest batch cooking for repeated recipes
            for recipe_id, data in recipe_frequency.items():
                if data['count'] >= 2:
                    recipe = data['recipe']
                    time_saved = (data['count'] - 1) * (recipe.get('cook_time_min', 0) + recipe.get('prep_time_min', 0))
                    
                    suggestions.append({
                        'type': 'batch_cooking',
                        'recipe': recipe['title'],
                        'servings': data['count'],
                        'action': f"Cook {data['count']} servings at once",
                        'time_saved': time_saved,
                        'storage_tip': self._get_storage_tip(recipe)
                    })
            
            # Add general bulk cooking tips
            suggestions.append({
                'type': 'general_tip',
                'action': 'Cook grains in bulk',
                'items': ['Rice', 'Quinoa', 'Pasta'],
                'storage_tip': 'Store in portions for 4-5 days'
            })
            
            suggestions.append({
                'type': 'general_tip',
                'action': 'Prep protein in bulk',
                'items': ['Grilled chicken', 'Baked tofu', 'Hard-boiled eggs'],
                'storage_tip': 'Refrigerate for up to 4 days'
            })
            
            # Sort by time saved
            suggestions.sort(
                key=lambda x: x.get('time_saved', 0), 
                reverse=True
            )
            
            return suggestions
            
        except Exception as e:
            logger.error(f"Error generating bulk cooking suggestions: {str(e)}")
            return []
    
    # Helper Methods
    def _build_optimization_constraints(self, user_id: int) -> OptimizationConstraints:
        """Build optimization constraints from user profile"""
        profile = self.db.query(UserProfile).filter_by(user_id=user_id).first()
        goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
        path = self.db.query(UserPath).filter_by(user_id=user_id).first()
        preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
        
        # Default values if no profile
        if not profile or not profile.goal_calories:
            return OptimizationConstraints(
                daily_calories_min=1800,
                daily_calories_max=2200,
                daily_protein_min=120,
                meals_per_day=3,
                max_recipe_repeat_in_days=2
            )
        
        # Get macro ratios from UserGoal.macro_targets JSON field
        if goal and goal.macro_targets:
            protein_ratio = goal.macro_targets.get('protein', 0.30)
            carb_ratio = goal.macro_targets.get('carbs', 0.40)
            fat_ratio = goal.macro_targets.get('fat', 0.30)
        else:
            protein_ratio = 0.30
            carb_ratio = 0.40
            fat_ratio = 0.30
        
        # Calculate gram amounts from ratios
        daily_protein_g = (profile.goal_calories * protein_ratio) / 4
        daily_carbs_g = (profile.goal_calories * carb_ratio) / 4
        daily_fat_g = (profile.goal_calories * fat_ratio) / 9
        
        # Build constraints with actual data
        return OptimizationConstraints(
            daily_calories_min=profile.goal_calories * 0.95,
            daily_calories_max=profile.goal_calories * 1.05,
            daily_protein_min=daily_protein_g * 0.9,
            daily_carbs_min=daily_carbs_g * 0.8,
            daily_carbs_max=daily_carbs_g * 1.2,
            daily_fat_min=daily_fat_g * 0.8,
            daily_fat_max=daily_fat_g * 1.2,
            meals_per_day=path.meals_per_day if path else 3,
            max_recipe_repeat_in_days=2,
            dietary_restrictions=[preferences.dietary_type.value] if preferences and preferences.dietary_type else [],
            allergens=preferences.allergies if preferences and preferences.allergies else []
        )
    
    def _score_recipe_for_goal(self, recipe: Recipe, goal: str) -> float:
        """Score recipe relevance for specific goal"""
        score = 0.0
        
        # Goal match
        if goal in recipe.goals:
            score += 50
        
        # Macro alignment
        if goal == 'muscle_gain':
            score += min(recipe.macros_per_serving['protein_g'] / 2, 25)
            score += min(recipe.macros_per_serving['calories'] / 40, 25)
        elif goal == 'fat_loss':
            score += max(25 - recipe.macros_per_serving['calories'] / 40, 0)
            score += min(recipe.macros_per_serving['protein_g'] / 2, 25)
        
        return score
    
    def _calculate_macro_similarity(self, macros1: Dict, macros2: Dict) -> float:
        """Calculate similarity between two macro profiles"""
        if not macros1 or not macros2:
            return 0.0
        
        differences = []
        for key in ['calories', 'protein_g', 'carbs_g', 'fat_g']:
            if key in macros1 and key in macros2:
                val1 = macros1[key]
                val2 = macros2[key]
                if val1 > 0:
                    diff = abs(val1 - val2) / val1
                    differences.append(min(diff, 1.0))
        
        if not differences:
            return 0.0
        
        avg_diff = sum(differences) / len(differences)
        return max(0, 1 - avg_diff)
    
    def _categorize_grocery_list(self, grocery_list: Dict[int, Dict[str, Any]]) -> Dict[str, List[Dict]]:
        categories = defaultdict(list)
        for item_id, data in grocery_list.items():
            if data["to_buy"] > 0:
                
                cat = self._normalize_category(data.get("category", "other") or "other")  

                categories[cat].append({                                        
                    "item_id": item_id,
                    "item_name": data["item_name"],
                    "category": cat,                                           
                    "unit": data["unit"],
                    "quantity_needed": data["quantity_needed"],                  
                    "quantity_available": data["quantity_available"],            
                    "to_buy": data["to_buy"]                                    
                })
        return categories
    

    def _normalize_category(self, category: str) -> str:
        mapping = {"fats": "fat"}  # Extend as needed
        return mapping.get(category.lower(), category.lower())


    
    def _find_recipes_by_calories(self, target_calories: float, tolerance: float, meal_type: str) -> List[Dict]:
        """Find recipes within calorie range"""
        min_cal = target_calories * (1 - tolerance)
        max_cal = target_calories * (1 + tolerance)
        
        recipes = self.db.query(Recipe).filter(
            cast(Recipe.suitable_meal_times, String).contains(meal_type)
        ).all()
        
        suitable = []
        for recipe in recipes:
            calories = recipe.macros_per_serving.get('calories', 0)
            if min_cal <= calories <= max_cal:
                suitable.append(recipe.to_dict())

        print("suitable meals", suitable)
        
        return suitable
    
    def _get_user_meal_windows(self) -> Dict:
        """Get user's preferred meal timing"""
        # TODO: Get from user preferences
        return {
            'breakfast': {'start': '08:00', 'end': '09:00'},
            'lunch': {'start': '12:30', 'end': '13:30'},
            'dinner': {'start': '19:00', 'end': '20:00'},
            'snack': {'start': '16:00', 'end': '16:30'}
        }
    
    def _get_storage_tip(self, recipe: Dict) -> str:
        """Get storage tip for recipe type"""
        # Simple logic based on recipe type
        if 'salad' in recipe.get('title', '').lower():
            return "Store dressing separately, keeps 3 days"
        elif 'soup' in recipe.get('title', '').lower():
            return "Refrigerate up to 5 days, freeze up to 3 months"
        else:
            return "Store in airtight container for 3-4 days"
    
    def _save_meal_plan(self, meal_plan: Dict) -> Dict:
        """Save meal plan to database"""
        try:
            # Deactivate existing plans
            self.db.query(MealPlan).filter_by(
                user_id=meal_plan['user_id'],
                is_active=True
            ).update({'is_active': False})

            print("during saving grocery list", meal_plan.get('grocery_list', {}))
            
            # Create new plan
            new_plan = MealPlan(
                user_id=meal_plan['user_id'],
                week_start_date=datetime.fromisoformat(meal_plan['start_date']),
                plan_data=meal_plan['week_plan'],
                grocery_list=meal_plan.get('grocery_list', {}),
                total_calories=meal_plan['total_calories'],
                avg_macros=meal_plan['avg_macros'],
                is_active=True
            )

            new_plan.updated_at = datetime.now()

            
            self.db.add(new_plan)
            self.db.commit()
            
            return MealPlanResponse.model_validate(new_plan)
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving meal plan: {str(e)}")
            raise

    def _create_meal_logs(self, meal_plan: Dict, meal_plan_id: int):
        """
        Create MealLog entries for each planned meal in the weekly plan.
        Links logs to meal plan via meal_plan_id and day_index.
        Sets proper meal times based on user's meal windows or defaults.
        """
        try:
            logs_to_add = []
            start_date = datetime.fromisoformat(meal_plan['start_date'])

            # Get user's meal windows for proper timing
            user_path = self.db.query(UserPath).filter_by(user_id=self.context.user_id).first()
            meal_windows = user_path.meal_windows if user_path and user_path.meal_windows else []

            # Create meal time map from windows or use defaults
            default_meal_times = {
                'breakfast': '08:00',
                'lunch': '13:00',
                'dinner': '19:00',
                'snack': '16:00'
            }

            meal_time_map = {}
            for window in meal_windows:
                meal_type = window.get('meal', '').lower()
                start_time = window.get('start', default_meal_times.get(meal_type, '12:00'))
                meal_time_map[meal_type] = start_time

            # Fill in any missing meal types with defaults
            for meal_type, default_time in default_meal_times.items():
                if meal_type not in meal_time_map:
                    meal_time_map[meal_type] = default_time

            print("printing meal plan format inside MealLog save function",meal_plan.get('week_plan', {}))
            for day_key, day_data in meal_plan.get('week_plan', {}).items():
                # Extract the numeric day offset (e.g., 'day_0' → 0)
                day_offset = int(day_key.split('_')[1])
                planned_date = start_date + timedelta(days=day_offset)

                for meal_name, recipe in day_data.get('meals', {}).items():
                    if not recipe:
                        continue  # Skip empty meal slots

                    # Get meal time and create proper datetime
                    meal_time_str = meal_time_map.get(meal_name.lower(), '12:00')
                    hour, minute = map(int, meal_time_str.split(':'))
                    planned_datetime = planned_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    logs_to_add.append(
                        MealLog(
                            user_id=self.context.user_id,
                            recipe_id=recipe['id'],
                            meal_type=meal_name,
                            planned_datetime=planned_datetime,
                            consumed_datetime=None,
                            was_skipped=False,
                            skip_reason=None,
                            portion_multiplier=1.0,
                            notes=None,
                            external_meal=None,
                            meal_plan_id=meal_plan_id,
                            day_index=day_offset
                        )
                    )

            if logs_to_add:
                self.db.bulk_save_objects(logs_to_add)
                self.db.commit()
                logger.info(f"Created {len(logs_to_add)} MealLog entries for user {self.context.user_id}")
            else:
                logger.warning("No MealLog entries to create—meal plan may be empty.")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create MealLog entries: {str(e)}")

    def _get_consumed_calories(self, user_id: int, day: datetime, skip_meal: str, plan_day_data: Dict) -> int:
        """
        Sum calories consumed for a given day using MealLog entries.
        Fallback: if a meal isn't logged, use its planned calories from the meal plan.
        """
        consumed = 0
        # Fetch all MealLog entries for the user/day

        start_dt = datetime.combine(day.date(), datetime.min.time())
        end_dt = datetime.combine(day.date(), datetime.max.time())
        logs = self.db.query(MealLog).filter(
                    MealLog.user_id == user_id,
                    MealLog.consumed_datetime >= start_dt,
                    MealLog.consumed_datetime <= end_dt,
                    MealLog.was_skipped == False
                ).all()

        logged_meals = {log.meal_type: log for log in logs}
        for meal_type, meal_data in plan_day_data.get("meals", {}).items():
            if meal_type == skip_meal:
                continue
            if meal_type in logged_meals:
                log = logged_meals[meal_type]
                if log.external_meal:
                    consumed += log.external_meal.get("calories", 0)
                else:
                    consumed += meal_data.get("macros_per_serving", {}).get("calories", 0)
            else:
                consumed += meal_data.get("macros_per_serving", {}).get("calories", 0)

        return int(consumed)
