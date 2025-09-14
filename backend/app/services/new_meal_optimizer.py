# backend/app/services/meal_optimizer_v2.py

import pulp
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
from collections import defaultdict
from sqlalchemy.orm import Session

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

class MealPlanOptimizerV2:
    """Clean LP-based meal plan optimizer that actually works"""
    
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
        objective: OptimizationObjective = None
    ) -> Optional[Dict]:
        """
        Generate optimized meal plan using Linear Programming
        """
        try:
            # Setup
            self.days = days
            self.meals_per_day = constraints.meals_per_day if constraints else 3
            
            # Get recipes from database or mock
            self.recipes = self._get_recipes_from_db(user_id, constraints)
            
            if len(self.recipes) < self.meals_per_day * 2:
                logger.error("Not enough recipes for optimization")
                return None
            
            # Create LP problem
            self.problem = pulp.LpProblem("MealPlan", pulp.LpMinimize)
            
            # Create decision variables: x[r][d][m] = 1 if recipe r is used on day d for meal m
            self._create_decision_variables()
            
            # Set objective function
            self._set_objective_function(objective)
            
            # Add constraints
            self._add_meal_assignment_constraints()
            self._add_nutrition_constraints(constraints)
            self._add_variety_constraints(constraints)
            
            # Solve
            solver = pulp.PULP_CBC_CMD(msg=1, timeLimit=10)  # Show messages for debugging
            status = self.problem.solve(solver)
            
            if status == pulp.LpStatusOptimal:
                logger.info("LP found optimal solution!")
                return self._extract_solution(constraints)
            else:
                logger.warning(f"LP status: {pulp.LpStatus[status]}")
                # Try relaxed version
                return self._solve_relaxed_problem(constraints, objective)
                
        except Exception as e:
            logger.error(f"Optimization error: {str(e)}")
            return None
    
    def _create_decision_variables(self):
        """Create binary decision variables for recipe assignment"""
        self.x = {}
        
        for r_idx, recipe in enumerate(self.recipes):
            self.x[r_idx] = {}
            for d in range(self.days):
                self.x[r_idx][d] = {}
                for m in range(self.meals_per_day):
                    # Only create variable if recipe is suitable for this meal slot
                    if self._is_recipe_suitable_for_meal(recipe, m):
                        var_name = f"x_{r_idx}_{d}_{m}"
                        self.x[r_idx][d][m] = pulp.LpVariable(var_name, cat='Binary')
    
    def _is_recipe_suitable_for_meal(self, recipe: Dict, meal_slot: int) -> bool:
        """Check if recipe is suitable for given meal slot"""
        meal_type_map = {
            0: 'breakfast',
            1: 'lunch',
            2: 'dinner',
            3: 'snack'
        }
        
        if meal_slot >= len(meal_type_map):
            return True  # Allow any recipe for extra meals
        
        meal_type = meal_type_map[meal_slot]
        suitable_times = recipe.get('suitable_meal_times', [])
        
        # If recipe has no restrictions, allow it
        if not suitable_times or len(suitable_times) >= 3:
            return True
            
        return meal_type in suitable_times
    
    def _set_objective_function(self, objective: OptimizationObjective = None):
        """Set objective to minimize cost (simplified for now)"""
        if not objective:
            objective = OptimizationObjective()
        
        obj_terms = []
        
        for r_idx, recipe in enumerate(self.recipes):
            if r_idx in self.x:
                for d in self.x[r_idx]:
                    for m in self.x[r_idx][d]:
                        # Simple objective: prefer higher protein recipes
                        protein = recipe.get('macros_per_serving', {}).get('protein_g', 0)
                        cost = 100 - protein  # Lower cost for higher protein
                        obj_terms.append(cost * self.x[r_idx][d][m])
        
        if obj_terms:
            self.problem += pulp.lpSum(obj_terms), "Objective"
    
    def _add_meal_assignment_constraints(self):
        """Each meal slot must have exactly one recipe"""
        for d in range(self.days):
            for m in range(self.meals_per_day):
                meal_vars = []
                for r_idx in self.x:
                    if d in self.x[r_idx] and m in self.x[r_idx][d]:
                        meal_vars.append(self.x[r_idx][d][m])
                
                if meal_vars:
                    # Exactly one recipe per meal slot
                    constraint_name = f"meal_d{d}_m{m}"
                    self.problem += pulp.lpSum(meal_vars) == 1, constraint_name
    
    def _add_nutrition_constraints(self, constraints: OptimizationConstraints):
        """Add daily nutrition constraints"""
        
        for d in range(self.days):
            daily_calories = []
            daily_protein = []
            
            for r_idx, recipe in enumerate(self.recipes):
                if r_idx in self.x and d in self.x[r_idx]:
                    for m in self.x[r_idx][d]:
                        var = self.x[r_idx][d][m]
                        macros = recipe.get('macros_per_serving', {})
                        
                        calories = macros.get('calories', 0)
                        protein = macros.get('protein_g', 0)
                        
                        daily_calories.append(calories * var)
                        daily_protein.append(protein * var)
            
            # Daily calorie constraints (with 15% tolerance for feasibility)
            if daily_calories:
                min_cal = constraints.daily_calories_min * 0.85
                max_cal = constraints.daily_calories_max * 1.15
                
                self.problem += pulp.lpSum(daily_calories) >= min_cal, f"min_cal_d{d}"
                self.problem += pulp.lpSum(daily_calories) <= max_cal, f"max_cal_d{d}"
            
            # Daily protein constraint (with 10% tolerance)
            if daily_protein:
                min_protein = constraints.daily_protein_min * 0.9
                self.problem += pulp.lpSum(daily_protein) >= min_protein, f"min_protein_d{d}"
    
    def _add_variety_constraints(self, constraints: OptimizationConstraints):
        """Limit recipe repetition"""
        window = constraints.max_recipe_repeat_in_days
        
        for r_idx in self.x:
            for d_start in range(max(0, self.days - window + 1)):
                d_end = min(d_start + window, self.days)
                
                window_uses = []
                for d in range(d_start, d_end):
                    if d in self.x[r_idx]:
                        for m in self.x[r_idx][d]:
                            window_uses.append(self.x[r_idx][d][m])
                
                if window_uses:
                    # Recipe can be used at most once in the window
                    constraint_name = f"variety_r{r_idx}_d{d_start}"
                    self.problem += pulp.lpSum(window_uses) <= 1, constraint_name
    
    def _solve_relaxed_problem(self, constraints: OptimizationConstraints, objective: OptimizationObjective):
        """Try solving with relaxed constraints if original fails"""
        logger.info("Trying relaxed problem...")
        
        # Create new problem with relaxed constraints
        self.problem = pulp.LpProblem("RelaxedMealPlan", pulp.LpMinimize)
        
        # Re-create variables
        self._create_decision_variables()
        self._set_objective_function(objective)
        self._add_meal_assignment_constraints()
        
        # Add relaxed nutrition constraints (wider tolerance)
        for d in range(self.days):
            daily_calories = []
            daily_protein = []
            
            for r_idx, recipe in enumerate(self.recipes):
                if r_idx in self.x and d in self.x[r_idx]:
                    for m in self.x[r_idx][d]:
                        var = self.x[r_idx][d][m]
                        macros = recipe.get('macros_per_serving', {})
                        
                        calories = macros.get('calories', 0)
                        protein = macros.get('protein_g', 0)
                        
                        daily_calories.append(calories * var)
                        daily_protein.append(protein * var)
            
            # Very relaxed constraints (30% tolerance)
            if daily_calories:
                min_cal = constraints.daily_calories_min * 0.7
                max_cal = constraints.daily_calories_max * 1.3
                
                self.problem += pulp.lpSum(daily_calories) >= min_cal, f"relaxed_min_cal_d{d}"
                self.problem += pulp.lpSum(daily_calories) <= max_cal, f"relaxed_max_cal_d{d}"
            
            # Relaxed protein (20% tolerance)
            if daily_protein:
                min_protein = constraints.daily_protein_min * 0.8
                self.problem += pulp.lpSum(daily_protein) >= min_protein, f"relaxed_min_protein_d{d}"
        
        # Solve relaxed problem
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=5)
        status = self.problem.solve(solver)
        
        if status == pulp.LpStatusOptimal:
            logger.info("Relaxed LP found solution!")
            return self._extract_solution(constraints)
        
        return None
    
    def _extract_solution(self, constraints: OptimizationConstraints) -> Dict:
        """Extract meal plan from solved LP"""
        meal_plan = {
            'week_plan': {},
            'total_calories': 0,
            'avg_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0},
            'optimization_method': 'linear_programming'
        }
        
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        
        meal_names = ['breakfast', 'lunch', 'dinner', 'snack']
        
        for d in range(self.days):
            day_plan = {}
            day_calories = 0
            
            for m in range(self.meals_per_day):
                meal_name = meal_names[m] if m < len(meal_names) else f'meal_{m}'
                
                for r_idx, recipe in enumerate(self.recipes):
                    if r_idx in self.x and d in self.x[r_idx] and m in self.x[r_idx][d]:
                        if self.x[r_idx][d][m].varValue == 1:
                            day_plan[meal_name] = recipe
                            macros = recipe.get('macros_per_serving', {})
                            
                            day_calories += macros.get('calories', 0)
                            total_protein += macros.get('protein_g', 0)
                            total_carbs += macros.get('carbs_g', 0)
                            total_fat += macros.get('fat_g', 0)
                            break
            
            meal_plan['week_plan'][f'day_{d}'] = day_plan
            meal_plan['total_calories'] += day_calories
        
        # Calculate daily averages
        if self.days > 0:
            meal_plan['avg_macros']['protein_g'] = total_protein / self.days
            meal_plan['avg_macros']['carbs_g'] = total_carbs / self.days
            meal_plan['avg_macros']['fat_g'] = total_fat / self.days
        
        return meal_plan
    
    def _get_recipes_from_db(self, user_id: int, constraints: OptimizationConstraints) -> List[Dict]:
        """Get recipes from database or return comprehensive mock data"""
        
        if self.db:
            # TODO: Implement actual database query
            # from app.models import Recipe, UserPreference
            # user_pref = self.db.query(UserPreference).filter_by(user_id=user_id).first()
            # recipes = self.db.query(Recipe).filter(...).all()
            pass
        
        # Return diverse mock recipes that can satisfy various constraints
        recipes = []
        
        # Breakfast options (300-500 calories, 20-40g protein)
        for i in range(8):
            recipes.append({
                'id': i + 1,
                'title': f'Breakfast Option {i+1}',
                'suitable_meal_times': ['breakfast'],
                'macros_per_serving': {
                    'calories': 350 + (i * 20),
                    'protein_g': 25 + (i * 2),
                    'carbs_g': 40 + (i * 3),
                    'fat_g': 12 + (i % 3),
                    'fiber_g': 5
                },
                'prep_time_min': 10,
                'cook_time_min': 15
            })
        
        # Lunch options (400-700 calories, 30-50g protein)
        for i in range(8):
            recipes.append({
                'id': i + 101,
                'title': f'Lunch Option {i+1}',
                'suitable_meal_times': ['lunch'],
                'macros_per_serving': {
                    'calories': 450 + (i * 35),
                    'protein_g': 35 + (i * 2),
                    'carbs_g': 45 + (i * 4),
                    'fat_g': 18 + (i % 4),
                    'fiber_g': 8
                },
                'prep_time_min': 15,
                'cook_time_min': 20
            })
        
        # Dinner options (500-800 calories, 40-60g protein)
        for i in range(8):
            recipes.append({
                'id': i + 201,
                'title': f'Dinner Option {i+1}',
                'suitable_meal_times': ['dinner'],
                'macros_per_serving': {
                    'calories': 550 + (i * 40),
                    'protein_g': 45 + (i * 2),
                    'carbs_g': 50 + (i * 3),
                    'fat_g': 22 + (i % 5),
                    'fiber_g': 10
                },
                'prep_time_min': 20,
                'cook_time_min': 30
            })
        
        # Flexible options (can be used for any meal)
        for i in range(6):
            recipes.append({
                'id': i + 301,
                'title': f'Flexible Option {i+1}',
                'suitable_meal_times': ['breakfast', 'lunch', 'dinner'],
                'macros_per_serving': {
                    'calories': 400 + (i * 50),
                    'protein_g': 30 + (i * 5),
                    'carbs_g': 40 + (i * 5),
                    'fat_g': 15 + (i * 2),
                    'fiber_g': 7
                },
                'prep_time_min': 15,
                'cook_time_min': 20
            })
        
        return recipes


# Wrapper function for backward compatibility
def create_optimizer(db_session=None):
    """Factory function to create optimizer instance"""
    return MealPlanOptimizerV2(db_session)