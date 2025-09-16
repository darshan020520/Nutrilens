# backend/app/agents/planning_agent.py

import logging
from typing import Dict, List, Optional, Any, Tuple
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
from app.models.database import MealPlan, Recipe, UserInventory, UserProfile, UserGoal, UserPath, UserPreference
from app.schemas.meal_plan import MealPlanCreate, MealPlanResponse
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

            print("MEAL PLAN", meal_plan)
            
            if not meal_plan:
                raise Exception("Optimizer failed to generate plan")
            
            # Enhance with metadata
            meal_plan['user_id'] = user_id
            meal_plan['start_date'] = start_date.isoformat()
            meal_plan['generated_at'] = datetime.now().isoformat()
            meal_plan['constraints'] = constraints.__dict__
            
            # Calculate grocery list
            meal_plan['grocery_list'] = self.calculate_grocery_list(meal_plan)
            
            # Save to database
            saved_plan = self._save_meal_plan(meal_plan)

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
    def calculate_grocery_list(self, meal_plan: Dict) -> Dict:
        """
        Calculate aggregated grocery list from meal plan
        
        Args:
            meal_plan: Meal plan dictionary
            
        Returns:
            Aggregated grocery list with quantities
        """
        try:
            grocery_list = {}
            
            # Iterate through all meals in the plan
            for day_key, day_data in meal_plan.get('week_plan', {}).items():
                for meal_name, recipe in day_data.get('meals', {}).items():
                    if recipe and 'ingredients' in recipe:
                        for ingredient in recipe['ingredients']:
                            item_id = ingredient.get('item_id')
                            quantity = ingredient.get('quantity_g', 0)
                            
                            if item_id:
                                if item_id not in grocery_list:
                                    grocery_list[item_id] = {
                                        'quantity_needed': 0,
                                        'quantity_available': 0,
                                        'to_buy': 0
                                    }
                                
                                grocery_list[item_id]['quantity_needed'] += quantity
            
            # Check against inventory
            if self.context.current_inventory:
                for item_id, item_data in grocery_list.items():
                    available = self.context.current_inventory.get(item_id, 0)
                    item_data['quantity_available'] = available
                    item_data['to_buy'] = max(0, item_data['quantity_needed'] - available)
            
            # Group by category and add item names
            categorized = self._categorize_grocery_list(grocery_list)
            
            return {
                'items': grocery_list,
                'categorized': categorized,
                'total_items': len(grocery_list),
                'items_to_buy': sum(1 for item in grocery_list.values() if item['to_buy'] > 0)
            }
            
        except Exception as e:
            logger.error(f"Error calculating grocery list: {str(e)}")
            return {}
    
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
            
            for day_data in meal_plan.get('week_plan', {}).values():
                for recipe in day_data.get('meals', {}).values():
                    if recipe:
                        recipe_id = recipe.get('id')
                        prep_time = recipe.get('prep_time_min', 0)
                        cook_time = recipe.get('cook_time_min', 0)
                        
                        # Track frequency
                        if recipe_id not in recipe_frequency:
                            recipe_frequency[recipe_id] = {
                                'count': 0,
                                'recipe': recipe
                            }
                        recipe_frequency[recipe_id]['count'] += 1
                        
                        # Identify prep-intensive recipes
                        if prep_time + cook_time > 30:
                            prep_intensive.append(recipe)
            
            # Suggest batch cooking for repeated recipes
            for recipe_id, data in recipe_frequency.items():
                if data['count'] >= 2:
                    prep_suggestions['batch_cooking'].append({
                        'recipe': data['recipe']['title'],
                        'quantity': f"{data['count']} servings",
                        'benefit': f"Save {(data['count']-1) * data['recipe'].get('cook_time_min', 0)} minutes"
                    })
            
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
    def find_recipe_alternatives(self, recipe_id: int, count: int = 3) -> List[Dict]:
        """
        Find alternative recipes with similar macros
        
        Args:
            recipe_id: Original recipe ID
            count: Number of alternatives to find
            
        Returns:
            List of alternative recipes with similarity scores
        """
        try:
            # Get original recipe
            original = self.db.query(Recipe).filter_by(id=recipe_id).first()
            if not original:
                return []
            
            original_macros = original.macros_per_serving
            
            # Find recipes with similar macros
            all_recipes = self.db.query(Recipe).filter(
                Recipe.id != recipe_id
            ).all()
            
            alternatives = []
            for recipe in all_recipes:
                # Calculate macro similarity
                similarity = self._calculate_macro_similarity(
                    original_macros, 
                    recipe.macros_per_serving
                )
                
                # Check meal time compatibility
                time_compatible = any(
                    time in recipe.suitable_meal_times 
                    for time in original.suitable_meal_times
                )
                
                if similarity > 0.7 and time_compatible:
                    alternatives.append({
                        'recipe': recipe.to_dict(),
                        'similarity_score': similarity,
                        'macro_difference': {
                            'calories': recipe.macros_per_serving['calories'] - original_macros['calories'],
                            'protein_g': recipe.macros_per_serving['protein_g'] - original_macros['protein_g'],
                            'carbs_g': recipe.macros_per_serving['carbs_g'] - original_macros['carbs_g'],
                            'fat_g': recipe.macros_per_serving['fat_g'] - original_macros['fat_g']
                        }
                    })
            
            # Sort by similarity and return top N
            alternatives.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return alternatives[:count]
            
        except Exception as e:
            logger.error(f"Error finding alternatives: {str(e)}")
            return []
    
    # Tool 6: Adjust Plan for Eating Out
    def adjust_plan_for_eating_out(self, day: int, meal: str, restaurant_calories: int) -> Dict:
        """
        Adjust remaining meals when eating out
        
        Args:
            day: Day of the week (0-6)
            meal: Meal being replaced (breakfast/lunch/dinner)
            restaurant_calories: Estimated calories from restaurant meal
            
        Returns:
            Adjusted meal plan for the day
        """
        try:
            if not self.context.active_meal_plan:
                return {"error": "No active meal plan"}
            
            plan = self.context.active_meal_plan
            day_key = f"day_{day}"
            
            if day_key not in plan['week_plan']:
                return {"error": f"Day {day} not in plan"}
            
            day_plan = plan['week_plan'][day_key]
            
            # Calculate remaining calorie budget
            daily_target = self.context.user_profile.get('goal_calories', 2000)
            remaining_calories = daily_target - restaurant_calories
            
            # Adjust other meals for the day
            meals_to_adjust = [m for m in day_plan['meals'] if m != meal]
            calories_per_meal = remaining_calories / len(meals_to_adjust) if meals_to_adjust else 0
            
            adjusted_meals = {}
            
            for meal_name in meals_to_adjust:
                # Find a recipe close to target calories
                suitable_recipes = self._find_recipes_by_calories(
                    calories_per_meal,
                    tolerance=0.2,
                    meal_type=meal_name
                )
                
                if suitable_recipes:
                    adjusted_meals[meal_name] = suitable_recipes[0]
            
            # Update the plan
            adjusted_meals[meal] = {
                'title': 'Eating Out',
                'macros_per_serving': {
                    'calories': restaurant_calories,
                    'protein_g': restaurant_calories * 0.3 / 4,  # Estimate
                    'carbs_g': restaurant_calories * 0.4 / 4,
                    'fat_g': restaurant_calories * 0.3 / 9
                },
                'is_external': True
            }
            
            return {
                'adjusted_day': day,
                'meals': adjusted_meals,
                'total_calories': sum(
                    m['macros_per_serving']['calories'] 
                    for m in adjusted_meals.values()
                ),
                'message': f"Adjusted meals for day {day+1} to accommodate eating out"
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
    
    def _categorize_grocery_list(self, grocery_list: Dict) -> Dict:
        """Categorize grocery items by type"""
        categories = {
            'proteins': [],
            'grains': [],
            'vegetables': [],
            'fruits': [],
            'dairy': [],
            'pantry': [],
            'other': []
        }
        
        # TODO: Implement categorization logic based on item database
        # For now, return a simple structure
        for item_id, data in grocery_list.items():
            if data['to_buy'] > 0:
                categories['other'].append({
                    'item_id': item_id,
                    'quantity': data['to_buy']
                })
        
        return categories
    
    def _find_recipes_by_calories(self, target_calories: float, tolerance: float, meal_type: str) -> List[Dict]:
        """Find recipes within calorie range"""
        min_cal = target_calories * (1 - tolerance)
        max_cal = target_calories * (1 + tolerance)
        
        recipes = self.db.query(Recipe).filter(
            Recipe.suitable_meal_times.contains([meal_type])
        ).all()
        
        suitable = []
        for recipe in recipes:
            calories = recipe.macros_per_serving.get('calories', 0)
            if min_cal <= calories <= max_cal:
                suitable.append(recipe.to_dict())
        
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