# backend/app/services/meal_optimizer_phase4.py

import pulp
from dataclasses import dataclass
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

@dataclass
class OptimizationConstraintsPhase4:
    daily_calories_min: float
    daily_calories_max: float
    daily_protein_min: float
    daily_protein_max: float
    max_recipe_repeats_per_week: int = 2
    meals_per_day: int = 3
    consecutive_day_penalty_weight: float = 1.0  # weight for consecutive repeat penalty

class MealPlanOptimizerPhase4:
    """Phase 4 Meal Planner: Handles all constraints including repeats and consecutive-day penalties"""

    def __init__(self):
        self.problem = None
        self.decision_vars = {}

    def optimize(self, days: int, constraints: OptimizationConstraintsPhase4, recipes: List[Dict]):
        self.problem = pulp.LpProblem("MealPlanOptimizationPhase4", pulp.LpMinimize)
        self.decision_vars = {}

        meal_types = ['breakfast', 'lunch', 'dinner'][:constraints.meals_per_day]

        # --- Create binary decision variables ---
        for day in range(days):
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                        self.decision_vars[var_name] = pulp.LpVariable(var_name, cat='Binary')

        # --- Objective: minimize consecutive-day repeats ---
        objective_terms = []
        for day in range(1, days):
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    var_prev = self.decision_vars.get(f"recipe_{recipe['id']}_day_{day-1}_meal_{meal_idx}")
                    var_curr = self.decision_vars.get(f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}")
                    if var_prev is not None and var_curr is not None:
                        repeat_var = pulp.LpVariable(
                            f"repeat_{recipe['id']}_day_{day}_meal_{meal_idx}", cat='Binary'
                        )
                        # Linearization: repeat_var = var_prev AND var_curr
                        self.problem += repeat_var >= var_prev + var_curr - 1
                        self.problem += repeat_var <= var_prev
                        self.problem += repeat_var <= var_curr
                        objective_terms.append(repeat_var * constraints.consecutive_day_penalty_weight)

        self.problem += pulp.lpSum(objective_terms), "MinimizeConsecutiveRepeats"

        # --- Hard constraints: one recipe per meal per day ---
        for day in range(days):
            for meal_idx, meal_type in enumerate(meal_types):
                vars_for_meal = [
                    self.decision_vars[f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"]
                    for recipe in recipes if meal_type in recipe.get('suitable_meal_times', [])
                ]
                if vars_for_meal:
                    self.problem += pulp.lpSum(vars_for_meal) == 1, f"one_recipe_day_{day}_meal_{meal_idx}"

        # --- Daily calories and protein constraints ---
        for day in range(days):
            day_calories = []
            day_protein = []
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    if meal_type in recipe.get('suitable_meal_times', []):
                        var = self.decision_vars[f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"]
                        day_calories.append(recipe['macros_per_serving']['calories'] * var)
                        day_protein.append(recipe['macros_per_serving']['protein_g'] * var)
            if day_calories:
                self.problem += pulp.lpSum(day_calories) >= constraints.daily_calories_min, f"cal_min_day_{day}"
                self.problem += pulp.lpSum(day_calories) <= constraints.daily_calories_max, f"cal_max_day_{day}"
            if day_protein:
                self.problem += pulp.lpSum(day_protein) >= constraints.daily_protein_min, f"protein_min_day_{day}"
                self.problem += pulp.lpSum(day_protein) <= constraints.daily_protein_max, f"protein_max_day_{day}"

        # --- Max recipe repeats per week ---
        for recipe in recipes:
            vars_for_recipe = [
                self.decision_vars[f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"]
                for day in range(days)
                for meal_idx, meal_type in enumerate(meal_types)
                if meal_type in recipe.get('suitable_meal_times', [])
            ]
            if vars_for_recipe:
                self.problem += pulp.lpSum(vars_for_recipe) <= constraints.max_recipe_repeats_per_week, \
                                f"max_repeat_recipe_{recipe['id']}"

        # --- Solve the problem ---
        status = self.problem.solve(pulp.PULP_CBC_CMD(msg=1, timeLimit=30))
        logger.info(f"LP solver status: {pulp.LpStatus[status]}")

        # --- Extract solution ---
        if pulp.LpStatus[status] not in ['Optimal', 'Feasible']:
            logger.warning("No feasible solution found. Returning empty plan.")
            return {}

        meal_plan = {}
        weekly_recipe_counts = {recipe['id']: 0 for recipe in recipes}

        for day in range(days):
            day_plan = {}
            for meal_idx, meal_type in enumerate(meal_types):
                for recipe in recipes:
                    var_name = f"recipe_{recipe['id']}_day_{day}_meal_{meal_idx}"
                    if var_name in self.decision_vars and self.decision_vars[var_name].varValue == 1:
                        day_plan[meal_type] = recipe
                        weekly_recipe_counts[recipe['id']] += 1
            meal_plan[f"day_{day}"] = day_plan

        logger.info(f"Weekly Recipe Counts: {weekly_recipe_counts}")
        return meal_plan
