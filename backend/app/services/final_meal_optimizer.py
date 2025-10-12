# backend/app/services/meal_optimizer_fixed.py
# COMPLETE FIXED VERSION - Addresses all issues from testing

import pulp
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
from collections import defaultdict
from sqlalchemy.orm import Session
import random
from app.models.database import UserProfile, UserGoal, UserPath, UserPreference, Recipe
from app.models.database import UserGoal, UserInventory, RecipeIngredient
from sqlalchemy import cast, String, func


logger = logging.getLogger(__name__)

@dataclass
class OptimizationConstraints:
    """Constraints for meal plan optimization"""
    daily_calories_min: float
    daily_calories_max: float
    daily_protein_min: float
    daily_carbs_min: float = 0
    daily_carbs_max: float = float('inf')
    daily_fat_min: float = 0
    daily_fat_max: float = float('inf')
    daily_fiber_min: float = 20
    meals_per_day: int = 3
    max_recipe_repeat_in_days: int = 2
    max_prep_time_minutes: int = 60
    dietary_restrictions: List[str] = field(default_factory=list)
    allergens: List[str] = field(default_factory=list)

@dataclass
class OptimizationObjective:
    """Weights for different optimization objectives"""
    macro_deviation_weight: float = 0.4
    inventory_usage_weight: float = 0.3
    recipe_variety_weight: float = 0.2
    goal_alignment_weight: float = 0.1

@dataclass
class RecipeScore:
    """Scoring metrics for a recipe"""
    recipe_id: int
    goal_alignment: float = 0.0
    macro_fit: float = 0.0
    timing_appropriateness: float = 0.0
    complexity_score: float = 0.0
    inventory_coverage: float = 0.0
    composite_score: float = 0.0
    
    def calculate_composite(self, weights: Dict[str, float]) -> float:
        """Calculate weighted composite score"""
        self.composite_score = (
            weights.get('goal', 0.3) * self.goal_alignment +
            weights.get('macro', 0.25) * self.macro_fit +
            weights.get('timing', 0.15) * self.timing_appropriateness +
            weights.get('complexity', 0.1) * (100 - self.complexity_score) +
            weights.get('inventory', 0.2) * self.inventory_coverage
        )
        return self.composite_score

class MealPlanOptimizer:
    """Fixed Linear Programming based meal plan optimizer"""
    
    def __init__(self, db_session: Session = None):
        self.db = db_session
        self.problem = None
        self.x = {}  # Decision variables
        self.recipes = []
        self.days = 0
        self.meals_per_day = 0
        
    def optimize(
        self,
        user_id: int,
        days: int = 7,
        constraints: OptimizationConstraints = None,
        objective: OptimizationObjective = None,
        available_recipes: List[Dict] = None,
        inventory: Dict[int, float] = None
    ) -> Optional[Dict]:
        """Main optimization with proper constraint handling"""
        
        try:
            self.days = days
            self.meals_per_day = constraints.meals_per_day if constraints else 3
            
            if not constraints:
                constraints = self._get_user_constraints(user_id)
            
            # Get recipes - FIXED to have appropriate calorie ranges
            if available_recipes:
                self.recipes = available_recipes
            else:
                print("user_id", user_id)
                print("constraints", constraints)
                self.recipes = self._get_filtered_recipes_fixed(user_id, constraints)
            
            # Filter recipes to those that can help meet constraints
            self.recipes = self._filter_recipes_by_calories(self.recipes, constraints)
            
            if len(self.recipes) < self.meals_per_day * 3:  # Need variety
                logger.error(f"Not enough suitable recipes: {len(self.recipes)}")
                return self._generate_simple_plan(days, constraints)
            
            # Score recipes
            scored_recipes = self._score_recipes(
                self.recipes, constraints, inventory or {}, user_id
            )
            
            # Try LP optimization with proper constraints
            result = self._solve_lp_problem_fixed(constraints, objective, scored_recipes)
            
            if result and self._validate_solution(result, constraints):
                logger.info("LP optimization successful with valid solution")
                return result
            
            # Try with relaxed constraints
            logger.info("Trying relaxed constraints...")
            result = self._solve_with_relaxed_constraints_fixed(constraints, scored_recipes, inventory)
            
            if result:
                logger.info("Relaxed LP successful")
                return result
            
            # Fallback to greedy
            logger.warning("Using greedy fallback")
            return self._fallback_greedy_algorithm_fixed(days, constraints, scored_recipes, inventory or {})
                
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}", exc_info=True)
            return self._generate_simple_plan(days, constraints)
    
    def _filter_recipes_by_calories(self, recipes: List[Dict], constraints: OptimizationConstraints) -> List[Dict]:
        """Filter out recipes that make it impossible to meet calorie constraints"""
        min_cal_per_meal = constraints.daily_calories_min / constraints.meals_per_day * 0.5  # Allow flexibility
        max_cal_per_meal = constraints.daily_calories_max / constraints.meals_per_day * 1.5
        
        filtered = []
        for recipe in recipes:
            calories = recipe.get('macros_per_serving', {}).get('calories', 0)
            if min_cal_per_meal <= calories <= max_cal_per_meal:
                filtered.append(recipe)
        
        # If too restrictive, include more
        if len(filtered) < constraints.meals_per_day * 3:
            return recipes  # Return all
        
        return filtered
    
    def _solve_lp_problem_fixed(
        self, 
        constraints: OptimizationConstraints,
        objective: OptimizationObjective,
        scored_recipes: Dict[int, RecipeScore]
    ) -> Optional[Dict]:
        """Solve LP with properly implemented constraints"""
        
        # Create problem
        self.problem = pulp.LpProblem("MealPlan", pulp.LpMinimize)
        
        # Create decision variables
        self._create_lp_variables()
        
        # Set objective with calorie awareness
        self._set_lp_objective_fixed(scored_recipes, objective, constraints)
        
        # Add constraints
        self._add_assignment_constraints()
        self._add_nutrition_constraints_fixed(constraints)
        self._add_variety_constraints_fixed(constraints)
        
        # Solve
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=30)  # More time for complex problems
        status = self.problem.solve(solver)
        
        if status == pulp.LpStatusOptimal:
            solution = self._extract_lp_solution()
            return solution
        
        logger.warning(f"LP status: {pulp.LpStatus[status]}")
        return None
    
    def _create_lp_variables(self):
        """Create binary decision variables"""
        self.x = {}
        
        for r_idx, recipe in enumerate(self.recipes):
            self.x[r_idx] = {}
            for d in range(self.days):
                self.x[r_idx][d] = {}
                for m in range(self.meals_per_day):
                    if self._is_recipe_suitable_for_meal(recipe, m):
                        var_name = f"x_{r_idx}_{d}_{m}"
                        self.x[r_idx][d][m] = pulp.LpVariable(var_name, cat='Binary')
    
    def _set_lp_objective_fixed(self, scored_recipes: Dict, objective: OptimizationObjective, constraints):
        """Objective function that considers calorie requirements"""
        if not objective:
            objective = OptimizationObjective()
        
        obj_terms = []
        target_cal_per_meal = ((constraints.daily_calories_min + constraints.daily_calories_max) / 2) / constraints.meals_per_day
        
        for r_idx, recipe in enumerate(self.recipes):
            if r_idx in self.x:
                # Get recipe score
                score = scored_recipes.get(recipe['id'], RecipeScore(recipe_id=recipe['id']))
                
                # Base cost from composite score
                base_cost = max(0, 100 - score.composite_score)
                
                # Penalize deviation from target calories
                recipe_cal = recipe.get('macros_per_serving', {}).get('calories', 0)
                cal_deviation = abs(recipe_cal - target_cal_per_meal) / target_cal_per_meal if target_cal_per_meal > 0 else 0
                cal_penalty = cal_deviation * 30  # Strong weight for calorie matching
                
                total_cost = base_cost * 0.7 + cal_penalty * 0.3  # Balance scores
                
                for d in self.x[r_idx]:
                    for m in self.x[r_idx][d]:
                        obj_terms.append(total_cost * self.x[r_idx][d][m])
        
        if obj_terms:
            self.problem += pulp.lpSum(obj_terms), "Objective"
    
    def _add_assignment_constraints(self):
        """Each meal slot gets exactly one recipe"""
        for d in range(self.days):
            for m in range(self.meals_per_day):
                meal_vars = []
                for r_idx in self.x:
                    if d in self.x[r_idx] and m in self.x[r_idx][d]:
                        meal_vars.append(self.x[r_idx][d][m])
                
                if meal_vars:
                    self.problem += pulp.lpSum(meal_vars) == 1, f"assign_d{d}_m{m}"
    
    def _add_nutrition_constraints_fixed(self, constraints: OptimizationConstraints):
        """Nutrition constraints with appropriate relaxation"""
        
        for d in range(self.days):
            daily_calories = []
            daily_protein = []
            daily_carbs = []
            daily_fat = []
            
            for r_idx, recipe in enumerate(self.recipes):
                if r_idx in self.x and d in self.x[r_idx]:
                    for m in self.x[r_idx][d]:
                        var = self.x[r_idx][d][m]
                        macros = recipe.get('macros_per_serving', {})
                        
                        daily_calories.append(macros.get('calories', 0) * var)
                        daily_protein.append(macros.get('protein_g', 0) * var)
                        daily_carbs.append(macros.get('carbs_g', 0) * var)
                        daily_fat.append(macros.get('fat_g', 0) * var)
            
            # Calorie constraints - RELAXED for feasibility
            if daily_calories:
                # Use 20% tolerance for better feasibility
                min_cal = constraints.daily_calories_min * 0.8
                max_cal = constraints.daily_calories_max * 1.2
                
                self.problem += pulp.lpSum(daily_calories) >= min_cal, f"min_cal_d{d}"
                self.problem += pulp.lpSum(daily_calories) <= max_cal, f"max_cal_d{d}"
            
            # Protein - slightly relaxed
            if daily_protein:
                min_protein = constraints.daily_protein_min * 0.85
                self.problem += pulp.lpSum(daily_protein) >= min_protein, f"min_protein_d{d}"
            
            # Optional constraints
            if daily_carbs and constraints.daily_carbs_max < float('inf'):
                self.problem += pulp.lpSum(daily_carbs) <= constraints.daily_carbs_max * 1.2, f"max_carbs_d{d}"
            
            if daily_fat and constraints.daily_fat_max < float('inf'):
                self.problem += pulp.lpSum(daily_fat) <= constraints.daily_fat_max * 1.2, f"max_fat_d{d}"
    
    # Replace the _add_variety_constraints_fixed method with this:

    def _add_variety_constraints_fixed(self, constraints: OptimizationConstraints):
        """
        FINAL FIX: Properly implement variety constraints
        
        If max_recipe_repeat_in_days = 2, it means:
        - A recipe can appear again only after 2 days gap
        - In a 7-day plan, a recipe can be used at most on days like: 1, 4, 7 (3 times)
        - But we want stricter: max 2 times in 7 days for better variety
        """
        
        # For a 7-day plan with max_repeat=2, we want each recipe used at most 2 times
        # Not 3 times as currently happening
        
        if self.days <= 3:
            # For short plans, each recipe used at most once
            max_uses_per_recipe = 1
        elif self.days <= 5:
            # For 4-5 day plans, allow 2 uses
            max_uses_per_recipe = 2
        else:
            # For 6-7 day plans, strictly limit to 2 uses
            # This ensures more variety
            max_uses_per_recipe = 2
        
        # Global constraint: limit total uses of each recipe
        for r_idx in self.x:
            all_uses = []
            for d in self.x[r_idx]:
                for m in self.x[r_idx][d]:
                    all_uses.append(self.x[r_idx][d][m])
            
            if all_uses:
                # Each recipe used at most 'max_uses_per_recipe' times
                self.problem += pulp.lpSum(all_uses) <= max_uses_per_recipe, f"max_uses_r{r_idx}"
        
        # Spacing constraint: ensure minimum gap between uses
        if constraints.max_recipe_repeat_in_days > 1:
            for r_idx in self.x:
                for d in range(self.days):
                    # Check if recipe is used on day d
                    # If yes, it cannot be used in the next (max_repeat-1) days
                    
                    window_end = min(d + constraints.max_recipe_repeat_in_days, self.days)
                    window_uses = []
                    
                    for day in range(d, window_end):
                        if day in self.x[r_idx]:
                            for m in self.x[r_idx][day]:
                                window_uses.append(self.x[r_idx][day][m])
                    
                    if len(window_uses) >= 2:
                        # In any window of 'max_repeat' days, use recipe at most once
                        self.problem += pulp.lpSum(window_uses) <= 1, f"spacing_r{r_idx}_d{d}_window"


    # Alternative simpler approach if the above is too restrictive:
    def _add_variety_constraints_simple(self, constraints: OptimizationConstraints):
        """
        Simpler version: Just limit total uses based on plan length
        """
        
        # Calculate reasonable max uses
        if self.days <= 3:
            max_uses = 1
        elif self.days <= 5:
            max_uses = 2  
        elif self.days == 7:
            max_uses = 2  # Force only 2 uses in a week for variety
        else:
            max_uses = 3  # For longer plans
        
        # Apply global limit
        for r_idx in self.x:
            all_uses = []
            for d in self.x[r_idx]:
                for m in self.x[r_idx][d]:
                    all_uses.append(self.x[r_idx][d][m])
            
            if all_uses:
                self.problem += pulp.lpSum(all_uses) <= max_uses, f"variety_limit_r{r_idx}"
        
        # No consecutive days constraint
        for r_idx in self.x:
            for d in range(self.days - 1):
                consecutive = []
                for day in [d, d + 1]:
                    if day in self.x[r_idx]:
                        for m in self.x[r_idx][day]:
                            consecutive.append(self.x[r_idx][day][m])
                
                if consecutive:
                    self.problem += pulp.lpSum(consecutive) <= 1, f"no_consecutive_r{r_idx}_d{d}"
    
    def _validate_solution(self, solution: Dict, constraints: OptimizationConstraints) -> bool:
        """Validate that solution meets minimum requirements"""
        if not solution or 'week_plan' not in solution:
            return False
        
        avg_cal = solution.get('avg_daily_calories', 0)
        avg_protein = solution['avg_macros'].get('protein_g', 0)
        
        # Check if within reasonable bounds (25% tolerance)
        cal_ok = constraints.daily_calories_min * 0.75 <= avg_cal <= constraints.daily_calories_max * 1.25
        protein_ok = avg_protein >= constraints.daily_protein_min * 0.75
        
        return cal_ok and protein_ok
    
    def _solve_with_relaxed_constraints_fixed(self, constraints, scored_recipes, inventory):
        """Progressively relax constraints"""
        
        # Very relaxed constraints
        relaxed = OptimizationConstraints(
            daily_calories_min=constraints.daily_calories_min * 0.7,
            daily_calories_max=constraints.daily_calories_max * 1.3,
            daily_protein_min=constraints.daily_protein_min * 0.7,
            daily_carbs_min=0,
            daily_carbs_max=float('inf'),
            daily_fat_min=0,
            daily_fat_max=float('inf'),
            meals_per_day=constraints.meals_per_day,
            max_recipe_repeat_in_days=max(1, constraints.max_recipe_repeat_in_days),
            dietary_restrictions=constraints.dietary_restrictions,
            allergens=constraints.allergens
        )
        
        result = self._solve_lp_problem_fixed(relaxed, None, scored_recipes)
        
        if result:
            result['optimization_method'] = 'linear_programming_relaxed'
            return result
        
        return None
    
    def _fallback_greedy_algorithm_fixed(self, days, constraints, scored_recipes, inventory):
        """Improved greedy algorithm that respects constraints better"""
        logger.info("Using improved greedy algorithm")
        
        meal_plan = {
            'week_plan': {},
            'total_calories': 0,
            'avg_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0, 'fiber_g': 0},
            'optimization_method': 'greedy_improved',
            'success': True
        }
        
        meal_names = ['breakfast', 'lunch', 'dinner', 'snack', 'meal_4', 'meal_5']
        
        # Group recipes by meal type
        recipes_by_meal = defaultdict(list)
        for recipe in self.recipes:
            for meal_time in recipe.get('suitable_meal_times', []):
                recipes_by_meal[meal_time].append(recipe)
        
        # Add flexible recipes to all meal types
        for recipe in self.recipes:
            if len(recipe.get('suitable_meal_times', [])) >= 3:
                for meal_type in meal_names[:constraints.meals_per_day]:
                    if recipe not in recipes_by_meal[meal_type]:
                        recipes_by_meal[meal_type].append(recipe)
        
        # Sort by score
        for meal_type in recipes_by_meal:
            recipes_by_meal[meal_type].sort(
                key=lambda r: scored_recipes.get(r['id'], RecipeScore(recipe_id=r['id'])).composite_score,
                reverse=True
            )
        
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        total_fiber = 0
        
        # Track recent usage
        recent_recipes = []
        
        for d in range(days):
            day_plan = {
                'meals': {},
                'day_calories': 0,
                'day_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0}
            }
            
            # Target calories for the day
            target_cal = (constraints.daily_calories_min + constraints.daily_calories_max) / 2
            remaining_cal = target_cal
            
            for m in range(constraints.meals_per_day):
                meal_name = meal_names[m] if m < len(meal_names) else f'meal_{m}'
                
                # Get candidates for this meal type
                candidates = recipes_by_meal.get(meal_name, self.recipes)
                
                # Filter out recently used
                available = [r for r in candidates if r['id'] not in [x['id'] for x in recent_recipes[-constraints.meals_per_day:]]]
                
                if not available:
                    available = candidates  # Use all if necessary
                
                # Pick best recipe considering remaining calories
                best_recipe = None
                best_score = -1
                target_meal_cal = remaining_cal / (constraints.meals_per_day - m)
                
                for recipe in available[:10]:  # Check top 10
                    recipe_cal = recipe.get('macros_per_serving', {}).get('calories', 0)
                    cal_fit = 1 - abs(recipe_cal - target_meal_cal) / target_meal_cal if target_meal_cal > 0 else 0
                    
                    score = scored_recipes.get(recipe['id'], RecipeScore(recipe_id=recipe['id'])).composite_score
                    combined_score = score * 0.6 + cal_fit * 100 * 0.4
                    
                    if combined_score > best_score:
                        best_score = combined_score
                        best_recipe = recipe
                
                if best_recipe:
                    day_plan['meals'][meal_name] = best_recipe
                    recent_recipes.append(best_recipe)
                    
                    macros = best_recipe.get('macros_per_serving', {})
                    day_plan['day_calories'] += macros.get('calories', 0)
                    remaining_cal -= macros.get('calories', 0)
                    
                    day_plan['day_macros']['protein_g'] += macros.get('protein_g', 0)
                    day_plan['day_macros']['carbs_g'] += macros.get('carbs_g', 0)
                    day_plan['day_macros']['fat_g'] += macros.get('fat_g', 0)
                    
                    total_protein += macros.get('protein_g', 0)
                    total_carbs += macros.get('carbs_g', 0)
                    total_fat += macros.get('fat_g', 0)
                    total_fiber += macros.get('fiber_g', 0)
            
            # Keep recent list manageable
            if len(recent_recipes) > constraints.meals_per_day * 2:
                recent_recipes = recent_recipes[-(constraints.meals_per_day * 2):]
            
            meal_plan['week_plan'][f'day_{d}'] = day_plan
            meal_plan['total_calories'] += day_plan['day_calories']
        
        # Calculate averages
        if days > 0:
            meal_plan['avg_macros']['protein_g'] = round(total_protein / days, 1)
            meal_plan['avg_macros']['carbs_g'] = round(total_carbs / days, 1)
            meal_plan['avg_macros']['fat_g'] = round(total_fat / days, 1)
            meal_plan['avg_macros']['fiber_g'] = round(total_fiber / days, 1)
            meal_plan['avg_daily_calories'] = round(meal_plan['total_calories'] / days, 0)
        
        return meal_plan
    
    def _get_filtered_recipes_fixed(self, user_id: int, constraints: OptimizationConstraints) -> List[Dict]:
        """Get actual recipes from database"""

        print("goal")
        
        # Get user's goal to filter recipes
        goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()

        print("goal", goal)

        

        goal_str = goal.goal_type.value.lower()

        print("goal_str", goal_str)
        
        # Start with all recipes
        query = self.db.query(Recipe)
        
        # Filter by goal if user has one
        if goal:
            # Recipe.goals is JSON array like ["muscle_gain", "fat_loss"]
            # We need recipes that contain the user's goal
            query = query.filter(cast(Recipe.goals, String).contains(goal_str))

        # Filter by dietary restrictions
        if constraints.dietary_restrictions:
            for restriction in constraints.dietary_restrictions:
                if restriction == 'vegetarian':
                    query = query.filter(cast(Recipe.dietary_tags, String).contains('vegetarian'))
                elif restriction == 'vegan':
                    query = query.filter(cast(Recipe.dietary_tags, String).contains('vegan'))
                # non_vegetarian recipes don't need filtering - they can eat everything
        
        # Filter by prep time
        if constraints.max_prep_time_minutes:
            query = query.filter(
                (Recipe.prep_time_min + Recipe.cook_time_min) <= constraints.max_prep_time_minutes
            )
        
        # Execute query
        recipes_from_db = query.all()
        
        # Convert to dict format expected by optimizer
        recipes = []
        for recipe in recipes_from_db:
            # Calculate if recipe fits calorie constraints
            calories = recipe.macros_per_serving.get('calories', 0)
            min_cal_per_meal = constraints.daily_calories_min / constraints.meals_per_day * 0.5
            max_cal_per_meal = constraints.daily_calories_max / constraints.meals_per_day * 1.5
            
            # Only include recipes that could fit in the meal plan
            if min_cal_per_meal <= calories <= max_cal_per_meal:
                recipes.append({
                    'id': recipe.id,
                    'title': recipe.title,
                    'suitable_meal_times': recipe.suitable_meal_times or [],
                    'goals': recipe.goals or [],
                    'dietary_tags': recipe.dietary_tags or [],
                    'macros_per_serving': recipe.macros_per_serving,
                    'prep_time_min': recipe.prep_time_min or 0,
                    'cook_time_min': recipe.cook_time_min or 0,
                    'ingredients': []  # Would need to join with RecipeIngredient if needed
                })
        
        # If we don't have enough recipes, relax the calorie constraints
        if len(recipes) < constraints.meals_per_day * 3:
            recipes = []
            for recipe in recipes_from_db:
                recipes.append({
                    'id': recipe.id,
                    'title': recipe.title,
                    'suitable_meal_times': recipe.suitable_meal_times or [],
                    'goals': recipe.goals or [],
                    'dietary_tags': recipe.dietary_tags or [],
                    'macros_per_serving': recipe.macros_per_serving,
                    'prep_time_min': recipe.prep_time_min or 0,
                    'cook_time_min': recipe.cook_time_min or 0,
                    'ingredients': []
                })
        
        return recipes
    
    # Keep all other methods unchanged...
    def _is_recipe_suitable_for_meal(self, recipe: Dict, meal_slot: int) -> bool:
        """Check if recipe suitable for meal slot"""
        meal_map = {0: 'breakfast', 1: 'lunch', 2: 'dinner', 3: 'snack', 4: 'meal_4', 5: 'meal_5'}
        
        if meal_slot >= len(meal_map):
            return True
        
        meal_type = meal_map[meal_slot]
        suitable_times = recipe.get('suitable_meal_times', [])
        
        if not suitable_times or len(suitable_times) >= 3:
            return True
            
        return meal_type in suitable_times or 'snack' in suitable_times
    
    def _extract_lp_solution(self) -> Dict:
        """Extract meal plan from solved LP"""
        meal_plan = {
            'week_plan': {},
            'total_calories': 0,
            'avg_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0, 'fiber_g': 0},
            'optimization_method': 'linear_programming',
            'success': True
        }
        
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        total_fiber = 0
        
        meal_names = ['breakfast', 'lunch', 'dinner', 'snack', 'meal_4', 'meal_5']
        
        for d in range(self.days):
            day_plan = {
                'meals': {},
                'day_calories': 0,
                'day_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0}
            }
            
            for m in range(self.meals_per_day):
                meal_name = meal_names[m] if m < len(meal_names) else f'meal_{m}'
                
                for r_idx, recipe in enumerate(self.recipes):
                    if r_idx in self.x and d in self.x[r_idx] and m in self.x[r_idx][d]:
                        if self.x[r_idx][d][m].varValue == 1:
                            day_plan['meals'][meal_name] = recipe
                            macros = recipe.get('macros_per_serving', {})
                            
                            day_plan['day_calories'] += macros.get('calories', 0)
                            day_plan['day_macros']['protein_g'] += macros.get('protein_g', 0)
                            day_plan['day_macros']['carbs_g'] += macros.get('carbs_g', 0)
                            day_plan['day_macros']['fat_g'] += macros.get('fat_g', 0)
                            
                            total_protein += macros.get('protein_g', 0)
                            total_carbs += macros.get('carbs_g', 0)
                            total_fat += macros.get('fat_g', 0)
                            total_fiber += macros.get('fiber_g', 0)
                            break
            
            meal_plan['week_plan'][f'day_{d}'] = day_plan
            meal_plan['total_calories'] += day_plan['day_calories']
        
        # Calculate averages
        if self.days > 0:
            meal_plan['avg_macros']['protein_g'] = round(total_protein / self.days, 1)
            meal_plan['avg_macros']['carbs_g'] = round(total_carbs / self.days, 1)
            meal_plan['avg_macros']['fat_g'] = round(total_fat / self.days, 1)
            meal_plan['avg_macros']['fiber_g'] = round(total_fiber / self.days, 1)
            meal_plan['avg_daily_calories'] = round(meal_plan['total_calories'] / self.days, 0)
        
        return meal_plan
    
    def _generate_simple_plan(self, days: int, constraints: OptimizationConstraints) -> Dict:
        """Emergency fallback"""
        return {
            'week_plan': {f'day_{d}': {'meals': {}, 'day_calories': 0} for d in range(days)},
            'total_calories': 0,
            'avg_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0},
            'optimization_method': 'emergency_fallback',
            'success': False,
            'error': 'Could not generate valid meal plan'
        }
    
    # Include all other helper methods from original...
    def _score_recipes(self, recipes, constraints, inventory, user_id):
        """Score recipes based on actual user data and inventory"""
        
        
        # Get user's goal
        goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
        user_goal_type = goal.goal_type.value if goal else 'general_health'
        
        # Get user's current inventory as a dict {item_id: quantity}
        user_inventory = {}
        if inventory:
            user_inventory = inventory
        else:
            inventory_items = self.db.query(UserInventory).filter_by(user_id=user_id).all()
            for item in inventory_items:
                user_inventory[item.item_id] = item.quantity_grams
        
        scored = {}
        
        # Target macros per meal
        target_cal_per_meal = ((constraints.daily_calories_min + constraints.daily_calories_max) / 2) / constraints.meals_per_day
        target_protein_per_meal = constraints.daily_protein_min / constraints.meals_per_day
        target_carbs_per_meal = (constraints.daily_carbs_min + constraints.daily_carbs_max) / 2 / constraints.meals_per_day
        target_fat_per_meal = (constraints.daily_fat_min + constraints.daily_fat_max) / 2 / constraints.meals_per_day
        
        for recipe in recipes:
            score = RecipeScore(recipe_id=recipe['id'])
            
            # 1. Goal alignment (0-100)
            recipe_goals = recipe.get('goals', [])
            if user_goal_type in recipe_goals:
                score.goal_alignment = 100
            elif any(g in recipe_goals for g in ['maintenance', 'general_health']):
                score.goal_alignment = 60
            else:
                score.goal_alignment = 30
            
            # 2. Macro fit (0-100) - how close to target macros
            macros = recipe.get('macros_per_serving', {})
            cal_diff = abs(macros.get('calories', 0) - target_cal_per_meal) / target_cal_per_meal if target_cal_per_meal > 0 else 1
            protein_diff = abs(macros.get('protein_g', 0) - target_protein_per_meal) / target_protein_per_meal if target_protein_per_meal > 0 else 1
            carbs_diff = abs(macros.get('carbs_g', 0) - target_carbs_per_meal) / target_carbs_per_meal if target_carbs_per_meal > 0 else 1
            fat_diff = abs(macros.get('fat_g', 0) - target_fat_per_meal) / target_fat_per_meal if target_fat_per_meal > 0 else 1
            
            # Average difference (lower is better)
            avg_diff = (cal_diff * 0.4 + protein_diff * 0.3 + carbs_diff * 0.2 + fat_diff * 0.1)
            score.macro_fit = max(0, 100 - (avg_diff * 50))  # Convert to 0-100 scale
            
            # 3. Timing appropriateness (0-100)
            # This stays relatively simple as meal timing is handled elsewhere
            suitable_times = recipe.get('suitable_meal_times', [])
            if len(suitable_times) >= 3:  # Very flexible
                score.timing_appropriateness = 100
            elif len(suitable_times) == 2:
                score.timing_appropriateness = 75
            elif len(suitable_times) == 1:
                score.timing_appropriateness = 50
            else:
                score.timing_appropriateness = 100  # If no restriction, it's flexible
            
            # 4. Complexity score (0-100, lower is better)
            prep_time = recipe.get('prep_time_min', 0)
            cook_time = recipe.get('cook_time_min', 0)
            total_time = prep_time + cook_time
            
            if total_time <= 15:
                score.complexity_score = 0  # Very quick
            elif total_time <= 30:
                score.complexity_score = 30
            elif total_time <= 45:
                score.complexity_score = 60
            else:
                score.complexity_score = 90  # Complex
            
            # 5. Inventory coverage (0-100) - what % of ingredients are available
            if user_inventory:
                # Get recipe ingredients
                recipe_ingredients = self.db.query(RecipeIngredient).filter_by(recipe_id=recipe['id']).all()
                
                if recipe_ingredients:
                    total_ingredients = len(recipe_ingredients)
                    available_ingredients = 0
                    
                    for ingredient in recipe_ingredients:
                        if ingredient.item_id in user_inventory:
                            if user_inventory[ingredient.item_id] >= ingredient.quantity_grams:
                                available_ingredients += 1
                            elif user_inventory[ingredient.item_id] > 0:
                                available_ingredients += 0.5  # Partial credit
                    
                    score.inventory_coverage = (available_ingredients / total_ingredients) * 100 if total_ingredients > 0 else 0
                else:
                    score.inventory_coverage = 50  # No ingredient data, neutral score
            else:
                score.inventory_coverage = 50  # No inventory data, neutral score
            
            # Calculate composite score
            score.calculate_composite({
                'goal': 0.3,
                'macro': 0.25,
                'timing': 0.15,
                'complexity': 0.1,
                'inventory': 0.2
            })
            
            scored[recipe['id']] = score
        
        return scored
    
    
    def _get_user_constraints(self, user_id):
        """Get user constraints from database"""
        
        
        # Fetch all user data
        profile = self.db.query(UserProfile).filter_by(user_id=user_id).first()
        goal = self.db.query(UserGoal).filter_by(user_id=user_id, is_active=True).first()
        path = self.db.query(UserPath).filter_by(user_id=user_id).first()
        preferences = self.db.query(UserPreference).filter_by(user_id=user_id).first()
        
        # If no profile, return defaults
        if not profile or not profile.goal_calories:
            return OptimizationConstraints(
                daily_calories_min=1800,
                daily_calories_max=2200,
                daily_protein_min=120,
                meals_per_day=3,
                max_recipe_repeat_in_days=2
            )
        
        # Get macro ratios from UserGoal.macro_targets JSON
        # Format: {"protein": 0.35, "carbs": 0.45, "fat": 0.20}
        protein_ratio = 0.30  # defaults
        carb_ratio = 0.40
        fat_ratio = 0.30
        
        if goal and goal.macro_targets:
            protein_ratio = goal.macro_targets.get('protein', 0.30)
            carb_ratio = goal.macro_targets.get('carbs', 0.40)
            fat_ratio = goal.macro_targets.get('fat', 0.30)
        
        # Convert ratios to grams using goal_calories
        daily_protein_g = (profile.goal_calories * protein_ratio) / 4  # 4 cal per g protein
        daily_carbs_g = (profile.goal_calories * carb_ratio) / 4      # 4 cal per g carbs
        daily_fat_g = (profile.goal_calories * fat_ratio) / 9         # 9 cal per g fat
        
        # Get dietary restrictions - convert enum to string if needed
        dietary_restrictions = []
        if preferences and preferences.dietary_type:
            dietary_restrictions = [preferences.dietary_type.value if hasattr(preferences.dietary_type, 'value') else preferences.dietary_type]
        
        return OptimizationConstraints(
            daily_calories_min=profile.goal_calories * 0.95,
            daily_calories_max=profile.goal_calories * 1.05,
            daily_protein_min=daily_protein_g * 0.9,  # Allow 10% flexibility
            daily_carbs_min=daily_carbs_g * 0.8,
            daily_carbs_max=daily_carbs_g * 1.2,
            daily_fat_min=daily_fat_g * 0.8,
            daily_fat_max=daily_fat_g * 1.2,
            daily_fiber_min=20,  # Standard recommendation
            meals_per_day=path.meals_per_day if path else 3,
            max_recipe_repeat_in_days=2,
            max_prep_time_minutes=preferences.max_prep_time_weekday if preferences else 60,
            dietary_restrictions=dietary_restrictions,
            allergens=preferences.allergies if preferences and preferences.allergies else []
        )