# backend/app/services/meal_optimizer.py

import pulp
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
from collections import defaultdict
import random

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
    goal_alignment: float = 0.0  # Add defaults
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
    """Linear Programming based meal plan optimizer"""
    
    def __init__(self, db_session=None):
        self.db_session = db_session
        self.problem = None
        self.decision_vars = {}
        self.solution = None
        
    def optimize(self, user_id: int, days: int = 7, 
            constraints: OptimizationConstraints = None,
            objective: OptimizationObjective = None,
            available_recipes: List[Dict] = None,
            inventory: Dict[int, float] = None) -> Optional[Dict]:
    
        scored_recipes = {}
        """
        Main optimization function to generate meal plan
        
        Returns:
            Dict with weekly meal plan or None if infeasible
        """
        try:
            if not constraints:
                constraints = self._get_user_constraints(user_id)
            if not objective:
                objective = OptimizationObjective()
            if not available_recipes:
                available_recipes = self._get_filtered_recipes(user_id, constraints)
            if not inventory:
                inventory = self._get_user_inventory(user_id)
                
            # Pre-filter and score recipes
            scored_recipes = self._score_recipes(
                available_recipes, constraints, inventory, user_id
            )
            
            # Select top candidates to reduce problem size
            top_recipes = self._select_top_recipes(scored_recipes, days * constraints.meals_per_day * 3)
            
            # Setup LP problem
            self._setup_problem(days, constraints.meals_per_day, top_recipes)
            
            # Add decision variables
            self._add_decision_variables(days, constraints.meals_per_day, top_recipes)
            
            # Set objective function
            self._set_objective_function(
                days, constraints.meals_per_day, top_recipes, 
                scored_recipes, inventory, objective
            )
            
            # Add constraints
            self._add_hard_constraints(
                days, constraints, top_recipes, inventory
            )
            self._add_soft_constraints(
                days, constraints, top_recipes
            )
            
            # Solve
            status = self.problem.solve(pulp.PULP_CBC_CMD(msg=0, timeLimit=5))
            
            if status != pulp.LpStatusOptimal:
                logger.warning(f"LP solver status: {pulp.LpStatus[status]}")
                # Try fallback algorithm
                return self._fallback_greedy_algorithm(
                    days, constraints, scored_recipes, inventory
                )
                
            # Extract solution
            meal_plan = self._extract_solution(days, constraints.meals_per_day, top_recipes)
            
            # Validate solution
            if not self._validate_solution(meal_plan, constraints):
                return self._fallback_greedy_algorithm(
                    days, constraints, scored_recipes, inventory
                )
                
            return meal_plan
            
        except Exception as e:
            logger.error(f"Optimization failed: {str(e)}")
            return self._fallback_greedy_algorithm(
                days, constraints, scored_recipes, inventory
            )
            
    def _setup_problem(self, days: int, meals_per_day: int, recipes: List[Dict]):
        """Initialize PuLP problem"""
        self.problem = pulp.LpProblem("MealPlanOptimization", pulp.LpMinimize)
        
    def _add_decision_variables(self, days: int, meals_per_day: int, recipes: List[Dict]):
        """Create binary decision variables for recipe selection"""
        self.decision_vars = {}
        
        meal_types = ['breakfast', 'lunch', 'dinner', 'snack'][:meals_per_day]
        
        for day in range(days):
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    # Check if recipe is suitable for this meal type
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                        self.decision_vars[var_name] = pulp.LpVariable(
                            var_name, cat='Binary'
                        )
                        
    def _set_objective_function(
        self, days: int, meals_per_day: int, recipes: List[Dict],
        scored_recipes: Dict[int, RecipeScore], inventory: Dict[int, float],
        objective: OptimizationObjective
    ):
        """Define the objective function to minimize"""
        obj_terms = []
        
        meal_types = ['breakfast', 'lunch', 'dinner', 'snack'][:meals_per_day]
        
        for day in range(days):
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                        if var_name in self.decision_vars:
                            var = self.decision_vars[var_name]
                            score = scored_recipes[recipe['id']]
                            
                            # Macro deviation penalty
                            macro_penalty = (100 - score.macro_fit) * objective.macro_deviation_weight
                            
                            # Inventory usage bonus (negative penalty)
                            inventory_bonus = -score.inventory_coverage * objective.inventory_usage_weight
                            
                            # Recipe variety penalty for repetition
                            repetition_penalty = self._calculate_repetition_penalty(
                                recipe['id'], day, days
                            ) * objective.recipe_variety_weight
                            
                            # Goal misalignment penalty
                            goal_penalty = (100 - score.goal_alignment) * objective.goal_alignment_weight
                            
                            # Combined coefficient
                            coefficient = macro_penalty + inventory_bonus + repetition_penalty + goal_penalty
                            obj_terms.append(coefficient * var)
                            
        self.problem += pulp.lpSum(obj_terms)
        
    def _add_hard_constraints(
        self, days: int, constraints: OptimizationConstraints,
        recipes: List[Dict], inventory: Dict[int, float]
    ):
        """Add hard constraints that must be satisfied"""
        meal_types = ['breakfast', 'lunch', 'dinner', 'snack'][:constraints.meals_per_day]
        
        # 1. Exactly one recipe per meal slot
        for day in range(days):
            for meal_idx, meal_type in enumerate(meal_types):
                meal_vars = []
                for recipe in recipes:
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                        if var_name in self.decision_vars:
                            meal_vars.append(self.decision_vars[var_name])
                            
                if meal_vars:
                    self.problem += pulp.lpSum(meal_vars) == 1, f"one_recipe_day_{day}_meal_{meal_idx}"
                    
        # 2. Daily calorie constraints
        for day in range(days):
            day_calories = []
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                        if var_name in self.decision_vars:
                            calories = recipe['macros_per_serving']['calories']
                            day_calories.append(calories * self.decision_vars[var_name])
                            
            if day_calories:
                self.problem += pulp.lpSum(day_calories) >= constraints.daily_calories_min
                self.problem += pulp.lpSum(day_calories) <= constraints.daily_calories_max
                
        # 3. Daily protein minimum
        for day in range(days):
            day_protein = []
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                        if var_name in self.decision_vars:
                            protein = recipe['macros_per_serving']['protein_g']
                            day_protein.append(protein * self.decision_vars[var_name])
                            
            if day_protein:
                self.problem += pulp.lpSum(day_protein) >= constraints.daily_protein_min
                
        # 4. Inventory constraints
        ingredient_usage = defaultdict(float)
        for day in range(days):
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                        if var_name in self.decision_vars:
                            for ingredient in recipe.get('ingredients', []):
                                item_id = ingredient['item_id']
                                quantity = ingredient['quantity_g']
                                ingredient_usage[item_id] += quantity * self.decision_vars[var_name]
                                
        for item_id, total_usage in ingredient_usage.items():
            if item_id in inventory:
                self.problem += total_usage <= inventory[item_id]
                
    def _add_soft_constraints(
        self, days: int, constraints: OptimizationConstraints,
        recipes: List[Dict]
    ):
        """Add soft constraints as penalties in objective"""
        meal_types = ['breakfast', 'lunch', 'dinner', 'snack'][:constraints.meals_per_day]
        
        # Recipe variety - limit repetitions within time window
        for recipe in recipes:
            for day_window_start in range(days - constraints.max_recipe_repeat_in_days + 1):
                window_vars = []
                for day in range(day_window_start, min(day_window_start + constraints.max_recipe_repeat_in_days, days)):
                    for meal_idx, meal_type in enumerate(meal_types):
                        if meal_type in recipe.get('suitable_meal_times', []):
                            var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                            if var_name in self.decision_vars:
                                window_vars.append(self.decision_vars[var_name])
                                
                if window_vars:
                    self.problem += pulp.lpSum(window_vars) <= 1
                    
    def _score_recipes(
        self, recipes: List[Dict], constraints: OptimizationConstraints,
        inventory: Dict[int, float], user_id: int
    ) -> Dict[int, RecipeScore]:
        """Score all recipes based on multiple criteria"""
        scored_recipes = {}
        
        # Get user goals and preferences
        user_goals = self._get_user_goals(user_id)
        target_macros = self._get_target_macros(user_id)
        
        for recipe in recipes:
            score = RecipeScore(recipe_id=recipe['id'])
            
            # Goal alignment scoring
            recipe_goals = set(recipe.get('goals', []))
            user_goal_set = set(user_goals)
            if recipe_goals and user_goal_set:
                score.goal_alignment = len(recipe_goals.intersection(user_goal_set)) / len(user_goal_set) * 100
            else:
                score.goal_alignment = 50  # Neutral score
                
            # Macro fit scoring
            score.macro_fit = self._calculate_macro_fit(
                recipe['macros_per_serving'], target_macros
            )
            
            # Timing appropriateness (simplified)
            score.timing_appropriateness = 80  # Can be enhanced with time-based logic
            
            # Complexity scoring
            total_time = recipe.get('prep_time_min', 0) + recipe.get('cook_time_min', 0)
            score.complexity_score = min(total_time, 100)
            
            # Inventory coverage scoring
            score.inventory_coverage = self._calculate_inventory_coverage(
                recipe.get('ingredients', []), inventory
            )
            
            # Calculate composite score
            score.calculate_composite({
                'goal': 0.3,
                'macro': 0.25,
                'timing': 0.15,
                'complexity': 0.1,
                'inventory': 0.2
            })
            
            scored_recipes[recipe['id']] = score
            
        return scored_recipes
        
    def _calculate_macro_fit(self, recipe_macros: Dict, target_macros: Dict) -> float:
        """Calculate how well recipe macros fit daily targets"""
        if not target_macros:
            return 50
            
        # Assuming 3 meals per day for calculation
        meal_targets = {
            'calories': target_macros.get('calories', 2000) / 3,
            'protein_g': target_macros.get('protein_g', 60) / 3,
            'carbs_g': target_macros.get('carbs_g', 250) / 3,
            'fat_g': target_macros.get('fat_g', 65) / 3
        }
        
        deviations = []
        for macro in ['calories', 'protein_g', 'carbs_g', 'fat_g']:
            if macro in recipe_macros and macro in meal_targets:
                target = meal_targets[macro]
                actual = recipe_macros[macro]
                if target > 0:
                    deviation = abs(actual - target) / target
                    deviations.append(min(deviation, 1))  # Cap at 100% deviation
                    
        if deviations:
            avg_deviation = sum(deviations) / len(deviations)
            return max(0, (1 - avg_deviation) * 100)
        return 50
        
    def _calculate_inventory_coverage(
        self, ingredients: List[Dict], inventory: Dict[int, float]
    ) -> float:
        """Calculate what percentage of recipe ingredients are in inventory"""
        if not ingredients:
            return 0
            
        covered = 0
        total = 0
        
        for ingredient in ingredients:
            item_id = ingredient['item_id']
            quantity_needed = ingredient['quantity_g']
            total += 1
            
            if item_id in inventory and inventory[item_id] >= quantity_needed:
                covered += 1
            elif item_id in inventory and inventory[item_id] > 0:
                covered += inventory[item_id] / quantity_needed
                
        return (covered / total * 100) if total > 0 else 0
        
    def _calculate_repetition_penalty(self, recipe_id: int, day: int, total_days: int) -> float:
        """Calculate penalty for recipe repetition"""
        # This is simplified - in production, would check actual assignments
        return 0
        
    def _select_top_recipes(
        self, scored_recipes: Dict[int, RecipeScore], count: int
    ) -> List[Dict]:
        """Select top N recipes based on composite scores"""
        # Get recipes from database or cache
        sorted_recipes = sorted(
            scored_recipes.items(),
            key=lambda x: x[1].composite_score,
            reverse=True
        )
        
        top_recipe_ids = [recipe_id for recipe_id, _ in sorted_recipes[:count]]
        
        # In production, fetch from database
        # For now, returning mock data
        return self._fetch_recipes_by_ids(top_recipe_ids)
        
    def _extract_solution(self, days: int, meals_per_day: int, recipes: List[Dict]) -> Dict:
        """Extract meal plan from solved LP problem"""
        meal_plan = {
            'week_plan': {},
            'total_calories': 0,
            'avg_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0},
            'recipe_ids': set()
        }
        
        meal_types = ['breakfast', 'lunch', 'dinner', 'snack'][:meals_per_day]
        
        for day in range(days):
            day_plan = {}
            day_calories = 0
            
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                        if var_name in self.decision_vars:
                            if self.decision_vars[var_name].varValue == 1:
                                day_plan[meal_type] = recipe
                                day_calories += recipe['macros_per_serving']['calories']
                                meal_plan['recipe_ids'].add(recipe['id'])
                                
                                # Accumulate macros
                                for macro in ['protein_g', 'carbs_g', 'fat_g']:
                                    meal_plan['avg_macros'][macro] += recipe['macros_per_serving'][macro]
                                    
            meal_plan['week_plan'][f'day_{day}'] = day_plan
            meal_plan['total_calories'] += day_calories
            
        # Calculate averages
        total_meals = days * meals_per_day
        for macro in meal_plan['avg_macros']:
            meal_plan['avg_macros'][macro] /= total_meals
            
        return meal_plan
        
    def _validate_solution(self, meal_plan: Dict, constraints: OptimizationConstraints) -> bool:
        """Validate that solution meets all hard constraints"""
        if not meal_plan or 'week_plan' not in meal_plan:
            return False
        
        for day_key, day_plan in meal_plan['week_plan'].items():
            if not day_plan:
                return False
            
            day_calories = sum(
                meal['macros_per_serving']['calories'] 
                for meal in day_plan.values() if meal
            )
            
            day_protein = sum(
                meal['macros_per_serving']['protein_g'] 
                for meal in day_plan.values() if meal
            )
            
            # Allow 5% tolerance on calories
            min_cal = constraints.daily_calories_min * 0.95
            max_cal = constraints.daily_calories_max * 1.05
            
            if day_calories < min_cal or day_calories > max_cal:
                logger.warning(f"{day_key}: Calories {day_calories} outside range [{min_cal}, {max_cal}]")
                return False
            
            # Allow 10% tolerance on protein
            if day_protein < constraints.daily_protein_min * 0.9:
                logger.warning(f"{day_key}: Protein {day_protein}g below minimum {constraints.daily_protein_min}g")
                return False
        
        return True
        
    def _fallback_greedy_algorithm(
        self, days: int, constraints: OptimizationConstraints,
        scored_recipes: Dict[int, RecipeScore], inventory: Dict[int, float]
    ) -> Dict:
        """IMPROVED greedy algorithm that respects constraints"""
        logger.info("Using fallback greedy algorithm")
        
        meal_plan = {
            'week_plan': {},
            'total_calories': 0,
            'avg_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0},
            'recipe_ids': set()
        }
        
        # Sort recipes by composite score
        sorted_recipes = sorted(
            scored_recipes.items(),
            key=lambda x: x[1].composite_score,
            reverse=True
        )
        
        # Get actual recipe data
        all_recipes = self._get_filtered_recipes(1, constraints)
        recipe_data = {r['id']: r for r in all_recipes}
        
        meal_types = ['breakfast', 'lunch', 'dinner', 'snack'][:constraints.meals_per_day]
        used_recently = defaultdict(int)
        
        # Calculate per-meal targets
        calories_per_meal = constraints.daily_calories_min / constraints.meals_per_day
        protein_per_meal = constraints.daily_protein_min / constraints.meals_per_day
        
        for day in range(days):
            day_plan = {}
            day_calories = 0
            day_protein = 0
            day_carbs = 0
            day_fat = 0
            
            for meal_type in meal_types:
                # Calculate remaining needs for the day
                remaining_meals = constraints.meals_per_day - len(day_plan)
                if remaining_meals > 0:
                    needed_calories = constraints.daily_calories_min - day_calories
                    needed_protein = constraints.daily_protein_min - day_protein
                    
                    target_calories = needed_calories / remaining_meals
                    target_protein = needed_protein / remaining_meals
                    
                    # Find best recipe for this meal slot
                    best_recipe = None
                    best_fit_score = -1
                    
                    for recipe_id, score in sorted_recipes:
                        recipe = recipe_data.get(recipe_id)
                        if not recipe:
                            continue
                        
                        # Check if suitable for meal time
                        if meal_type not in recipe.get('suitable_meal_times', []):
                            continue
                        
                        # Check if used too recently
                        if used_recently[recipe_id] > 0:
                            continue
                        
                        # Calculate fit score based on nutritional needs
                        recipe_calories = recipe['macros_per_serving']['calories']
                        recipe_protein = recipe['macros_per_serving']['protein_g']
                        
                        # Skip if way over calorie budget
                        if day_calories + recipe_calories > constraints.daily_calories_max:
                            continue
                        
                        # Calculate how well this recipe fits our needs
                        calorie_fit = 1 - abs(recipe_calories - target_calories) / target_calories
                        protein_fit = 1 - abs(recipe_protein - target_protein) / target_protein
                        
                        # Combine with recipe's composite score
                        fit_score = (calorie_fit * 0.3 + protein_fit * 0.3 + score.composite_score/100 * 0.4)
                        
                        if fit_score > best_fit_score:
                            best_fit_score = fit_score
                            best_recipe = recipe
                    
                    if best_recipe:
                        day_plan[meal_type] = best_recipe
                        day_calories += best_recipe['macros_per_serving']['calories']
                        day_protein += best_recipe['macros_per_serving']['protein_g']
                        day_carbs += best_recipe['macros_per_serving'].get('carbs_g', 0)
                        day_fat += best_recipe['macros_per_serving'].get('fat_g', 0)
                        
                        # Update recent usage
                        used_recently[best_recipe['id']] = constraints.max_recipe_repeat_in_days
                        meal_plan['recipe_ids'].add(best_recipe['id'])
            
            # Decrease recent usage counters
            for recipe_id in list(used_recently.keys()):
                used_recently[recipe_id] = max(0, used_recently[recipe_id] - 1)
            
            meal_plan['week_plan'][f'day_{day}'] = day_plan
            meal_plan['total_calories'] += day_calories
            
            # Accumulate macros
            meal_plan['avg_macros']['protein_g'] += day_protein
            meal_plan['avg_macros']['carbs_g'] += day_carbs
            meal_plan['avg_macros']['fat_g'] += day_fat
        
        # Calculate averages
        total_days = days
        if total_days > 0:
            meal_plan['avg_macros']['protein_g'] /= total_days
            meal_plan['avg_macros']['carbs_g'] /= total_days
            meal_plan['avg_macros']['fat_g'] /= total_days
        
        return meal_plan
        
    # Database interaction methods (to be implemented with actual DB)
    def _get_user_constraints(self, user_id: int) -> OptimizationConstraints:
        """Fetch user constraints from database"""
        # Mock implementation
        return OptimizationConstraints(
            daily_calories_min=1800,
            daily_calories_max=2200,
            daily_protein_min=120,
            daily_carbs_min=150,
            daily_carbs_max=250,
            daily_fat_min=50,
            daily_fat_max=80,
            meals_per_day=3,
            dietary_restrictions=['vegetarian'],
            allergens=[]
        )
        
    def _get_filtered_recipes(self, user_id: int, constraints: OptimizationConstraints) -> List[Dict]:
        """Get REALISTIC recipes filtered by user preferences and constraints"""
        recipes = []
        
        # Create breakfast recipes (350-500 cal, 15-25g protein)
        breakfast_bases = [
            "Oatmeal Bowl", "Egg Scramble", "Protein Pancakes", 
            "Greek Yogurt Parfait", "Avocado Toast", "Smoothie Bowl",
            "Breakfast Burrito", "French Toast", "Chia Pudding", "Egg Muffins"
        ]
        
        for i in range(10):
            recipes.append({
                'id': i + 1,
                'title': f'{breakfast_bases[i % len(breakfast_bases)]} Variation {i+1}',
                'goals': ['balanced', 'energy'],
                'suitable_meal_times': ['breakfast'],
                'macros_per_serving': {
                    'calories': 350 + (i * 15),
                    'protein_g': 15 + (i * 1.5),
                    'carbs_g': 45 + (i * 2),
                    'fat_g': 12 + (i % 3),
                    'fiber_g': 5
                },
                'ingredients': [
                    {'item_id': i+1, 'quantity_g': 100},
                    {'item_id': i+51, 'quantity_g': 50}
                ],
                'prep_time_min': 10 + (i % 5),
                'cook_time_min': 10 + (i % 10)
            })
        
        # Create lunch recipes (500-700 cal, 30-45g protein)
        lunch_bases = [
            "Grilled Chicken Salad", "Turkey Sandwich", "Buddha Bowl",
            "Pasta Primavera", "Tuna Wrap", "Quinoa Bowl",
            "Chicken Stir-fry", "Mexican Bowl", "Power Salad", "Protein Wrap"
        ]
        
        for i in range(10):
            recipes.append({
                'id': i + 11,
                'title': f'{lunch_bases[i % len(lunch_bases)]} Variation {i+1}',
                'goals': ['balanced', 'muscle_gain'],
                'suitable_meal_times': ['lunch'],
                'macros_per_serving': {
                    'calories': 500 + (i * 20),
                    'protein_g': 30 + (i * 1.5),
                    'carbs_g': 50 + (i * 3),
                    'fat_g': 18 + (i % 5),
                    'fiber_g': 8
                },
                'ingredients': [
                    {'item_id': i+11, 'quantity_g': 150},
                    {'item_id': i+61, 'quantity_g': 75}
                ],
                'prep_time_min': 15 + (i % 10),
                'cook_time_min': 20 + (i % 15)
            })
        
        # Create dinner recipes (600-800 cal, 40-60g protein)
        dinner_bases = [
            "Grilled Salmon", "Beef Stir-fry", "Chicken Breast",
            "Lean Steak", "Turkey Meatballs", "Baked Cod",
            "Pork Tenderloin", "Shrimp Curry", "Tofu Steak", "Lamb Chops"
        ]
        
        for i in range(10):
            recipes.append({
                'id': i + 21,
                'title': f'{dinner_bases[i % len(dinner_bases)]} with Vegetables',
                'goals': ['muscle_gain', 'high_protein'],
                'suitable_meal_times': ['dinner'],
                'macros_per_serving': {
                    'calories': 600 + (i * 20),
                    'protein_g': 40 + (i * 2),
                    'carbs_g': 45 + (i * 2),
                    'fat_g': 20 + (i % 6),
                    'fiber_g': 10
                },
                'ingredients': [
                    {'item_id': i+21, 'quantity_g': 200},
                    {'item_id': i+71, 'quantity_g': 100}
                ],
                'prep_time_min': 20 + (i % 10),
                'cook_time_min': 25 + (i % 15)
            })
        
        # Create flexible snack recipes
        snack_bases = [
            "Protein Bar", "Mixed Nuts", "Fruit & Yogurt",
            "Hummus & Veggies", "Protein Shake"
        ]
        
        for i in range(5):
            recipes.append({
                'id': i + 31,
                'title': snack_bases[i % len(snack_bases)],
                'goals': ['balanced'],
                'suitable_meal_times': ['breakfast', 'lunch', 'dinner', 'snack'],
                'macros_per_serving': {
                    'calories': 150 + (i * 10),
                    'protein_g': 8 + i,
                    'carbs_g': 15 + (i * 2),
                    'fat_g': 6 + (i % 3),
                    'fiber_g': 3
                },
                'ingredients': [
                    {'item_id': i+31, 'quantity_g': 50}
                ],
                'prep_time_min': 5,
                'cook_time_min': 0
            })
        
        return recipes
        
    def _get_user_inventory(self, user_id: int) -> Dict[int, float]:
        """Get user's current inventory"""
        # Mock implementation
        return {i: 1000.0 for i in range(1, 100)}
        
    def _get_user_goals(self, user_id: int) -> List[str]:
        """Get user's fitness goals"""
        # Mock implementation
        return ['muscle_gain', 'balanced']
        
    def _get_target_macros(self, user_id: int) -> Dict[str, float]:
        """Get user's target macros"""
        # Mock implementation
        return {
            'calories': 2000,
            'protein_g': 150,
            'carbs_g': 200,
            'fat_g': 65
        }
        
    def _fetch_recipes_by_ids(self, recipe_ids: List[int]) -> List[Dict]:
        """Fetch recipes by IDs from database"""
        # Mock implementation
        return [
            {
                'id': rid,
                'title': f'Recipe {rid}',
                'goals': ['muscle_gain', 'balanced'],
                'suitable_meal_times': ['breakfast', 'lunch', 'dinner'],
                'macros_per_serving': {
                    'calories': 400 + (rid * 10),
                    'protein_g': 25 + (rid % 10),
                    'carbs_g': 40 + (rid % 15),
                    'fat_g': 15 + (rid % 5),
                    'fiber_g': 5
                },
                'ingredients': [
                    {'item_id': 1, 'quantity_g': 100},
                    {'item_id': 2, 'quantity_g': 50}
                ],
                'prep_time_min': 15,
                'cook_time_min': 20
            }
            for rid in recipe_ids
        ]