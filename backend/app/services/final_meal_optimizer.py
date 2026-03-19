import pulp
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import logging
from collections import defaultdict
from app.repositories.interfaces.recipe_repository import IRecipeRepository
from app.repositories.interfaces.inventory_repository import IInventoryRepository
from app.repositories.interfaces.user_profile_repository import IUserProfileRepository


logger = logging.getLogger(__name__)

@dataclass
class OptimizationConstraints:

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

    macro_deviation_weight: float = 0.4
    inventory_usage_weight: float = 0.3
    recipe_variety_weight: float = 0.2
    goal_alignment_weight: float = 0.1

@dataclass
class RecipeScore:

    recipe_id: int
    goal_alignment: float = 0.0
    macro_fit: float = 0.0
    timing_appropriateness: float = 0.0
    complexity_score: float = 0.0
    inventory_coverage: float = 0.0
    composite_score: float = 0.0
    
    def calculate_composite(self, weights: Dict[str, float]) -> float:

        self.composite_score = (
            weights.get('goal', 0.3) * self.goal_alignment +
            weights.get('macro', 0.25) * self.macro_fit +
            weights.get('timing', 0.15) * self.timing_appropriateness +
            weights.get('complexity', 0.1) * (100 - self.complexity_score) +
            weights.get('inventory', 0.2) * self.inventory_coverage
        )
        return self.composite_score

class MealPlanOptimizer:


    def __init__(
        self,
        recipe_repo: IRecipeRepository,
        inventory_repo: IInventoryRepository,
        user_profile_repo: IUserProfileRepository
    ):

        self.recipe_repo = recipe_repo
        self.inventory_repo = inventory_repo
        self.user_profile_repo = user_profile_repo
        self.problem = None
        self.x = {}  # Decision variables
        self.recipes = []
        self.days = 0
        self.meals_per_day = 0
        
    async def optimize(
        self,
        user_id: int,
        days: int = 7,
        constraints: OptimizationConstraints = None,
        objective: OptimizationObjective = None,
        available_recipes: List[Dict] = None,
        inventory: Dict[int, float] = None
    ) -> Optional[Dict]:

        try:
            self.days = days
            self.meals_per_day = constraints.meals_per_day if constraints else 3

            # Minimum unique recipes LP needs: ceil(total_slots / max_uses_per_recipe)
            # For 7d × 3 meals = 21 slots, max_uses=2 → need at least 11 unique recipes
            max_uses_per_recipe = 2
            lp_min_recipes = math.ceil((days * self.meals_per_day) / max_uses_per_recipe)

            if available_recipes:
                self.recipes = available_recipes
            else:
                self.recipes = await self._get_filtered_recipes_fixed(user_id, constraints, lp_min_recipes)

            # Filter recipes to those that can help meet constraints
            self.recipes = self._filter_recipes_by_calories(self.recipes, constraints)

            print(
                f"[LP] user={user_id} days={days} meals/day={self.meals_per_day} "
                f"recipe_count={len(self.recipes)} lp_min_needed={lp_min_recipes} "
                f"cal_range=[{constraints.daily_calories_min:.0f},{constraints.daily_calories_max:.0f}] "
                f"protein_min={constraints.daily_protein_min:.0f}g"
            )

            if len(self.recipes) < lp_min_recipes:
                print(
                    f"[LP] EMERGENCY FALLBACK — only {len(self.recipes)} recipes available, "
                    f"need {lp_min_recipes} for LP feasibility"
                )
                return self._generate_simple_plan(days, constraints)

            # Score recipes
            scored_recipes = await self._score_recipes(
                self.recipes, constraints, inventory or {}, user_id
            )

            # Try LP optimization with proper constraints
            print(f"[LP] Attempting standard LP with {len(self.recipes)} recipes...")
            result = self._solve_lp_problem_fixed(constraints, objective, scored_recipes)

            if result:
                valid = self._validate_solution(result, constraints)
                print(
                    f"[LP] Standard LP status=Optimal  validate={valid}  "
                    f"avg_cal={result.get('avg_daily_calories', 0):.0f}  "
                    f"avg_protein={result.get('avg_macros', {}).get('protein_g', 0):.0f}g"
                )
                if valid:
                    print("[LP] SUCCESS — using linear_programming result")
                    return result
                print("[LP] LP result failed validation — trying relaxed LP")
            else:
                print("[LP] Standard LP returned no solution (Infeasible/Undefined) — trying relaxed LP")

            # Try with relaxed constraints
            result = self._solve_with_relaxed_constraints_fixed(constraints, scored_recipes, inventory)

            if result:
                print(
                    f"[LP] Relaxed LP succeeded  "
                    f"avg_cal={result.get('avg_daily_calories', 0):.0f}  "
                    f"avg_protein={result.get('avg_macros', {}).get('protein_g', 0):.0f}g"
                )
                return result

            print("[LP] Relaxed LP also failed — falling back to greedy algorithm")
            result = self._fallback_greedy_algorithm_fixed(days, constraints, scored_recipes, inventory or {})
            print(
                f"[LP] GREEDY FALLBACK used  "
                f"avg_cal={result.get('avg_daily_calories', 0):.0f}  "
                f"avg_protein={result.get('avg_macros', {}).get('protein_g', 0):.0f}g"
            )
            return result

        except Exception as e:
            import traceback
            print(f"[LP] Optimization crashed: {str(e)}")
            print(traceback.format_exc())
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
        solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=30)
        status = self.problem.solve(solver)

        print(
            f"[LP] CBC solver status={pulp.LpStatus[status]} ({status})  "
            f"vars={len(self.problem.variables())}  constraints={len(self.problem.constraints)}"
        )

        if status == pulp.LpStatusOptimal:
            solution = self._extract_lp_solution()
            return solution

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
            
            if daily_calories:
                min_cal = constraints.daily_calories_min * 0.8
                max_cal = constraints.daily_calories_max * 1.2
                
                self.problem += pulp.lpSum(daily_calories) >= min_cal, f"min_cal_d{d}"
                self.problem += pulp.lpSum(daily_calories) <= max_cal, f"max_cal_d{d}"
            
            if daily_protein:
                min_protein = constraints.daily_protein_min * 0.85
                self.problem += pulp.lpSum(daily_protein) >= min_protein, f"min_protein_d{d}"
            
            if daily_carbs and constraints.daily_carbs_max < float('inf'):
                self.problem += pulp.lpSum(daily_carbs) <= constraints.daily_carbs_max * 1.2, f"max_carbs_d{d}"
            
            if daily_fat and constraints.daily_fat_max < float('inf'):
                self.problem += pulp.lpSum(daily_fat) <= constraints.daily_fat_max * 1.2, f"max_fat_d{d}"
    

    def _add_variety_constraints_fixed(self, constraints: OptimizationConstraints):

        
        if self.days <= 3:
            max_uses_per_recipe = 1
        elif self.days <= 5:
            max_uses_per_recipe = 2
        else:
            max_uses_per_recipe = 2
        
        for r_idx in self.x:
            all_uses = []
            for d in self.x[r_idx]:
                for m in self.x[r_idx][d]:
                    all_uses.append(self.x[r_idx][d][m])
            
            if all_uses:
                self.problem += pulp.lpSum(all_uses) <= max_uses_per_recipe, f"max_uses_r{r_idx}"
        

        if constraints.max_recipe_repeat_in_days > 1:
            for r_idx in self.x:
                for d in range(self.days):

                    window_end = min(d + constraints.max_recipe_repeat_in_days, self.days)
                    window_uses = []
                    
                    for day in range(d, window_end):
                        if day in self.x[r_idx]:
                            for m in self.x[r_idx][day]:
                                window_uses.append(self.x[r_idx][day][m])
                    
                    if len(window_uses) >= 2:
                        self.problem += pulp.lpSum(window_uses) <= 1, f"spacing_r{r_idx}_d{d}_window"


    def _add_variety_constraints_simple(self, constraints: OptimizationConstraints):

        if self.days <= 3:
            max_uses = 1
        elif self.days <= 5:
            max_uses = 2  
        elif self.days == 7:
            max_uses = 2 
        else:
            max_uses = 3 
        

        for r_idx in self.x:
            all_uses = []
            for d in self.x[r_idx]:
                for m in self.x[r_idx][d]:
                    all_uses.append(self.x[r_idx][d][m])
            
            if all_uses:
                self.problem += pulp.lpSum(all_uses) <= max_uses, f"variety_limit_r{r_idx}"
        

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

        if not solution or 'week_plan' not in solution:
            return False
        
        avg_cal = solution.get('avg_daily_calories', 0)
        avg_protein = solution['avg_macros'].get('protein_g', 0)
        

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

        recipes_by_meal = defaultdict(list)
        for recipe in self.recipes:
            for meal_time in recipe.get('suitable_meal_times', []):
                recipes_by_meal[meal_time].append(recipe)
        

        for recipe in self.recipes:
            if len(recipe.get('suitable_meal_times', [])) >= 3:
                for meal_type in meal_names[:constraints.meals_per_day]:
                    if recipe not in recipes_by_meal[meal_type]:
                        recipes_by_meal[meal_type].append(recipe)
        

        for meal_type in recipes_by_meal:
            recipes_by_meal[meal_type].sort(
                key=lambda r: scored_recipes.get(r['id'], RecipeScore(recipe_id=r['id'])).composite_score,
                reverse=True
            )
        
        total_protein = 0
        total_carbs = 0
        total_fat = 0
        total_fiber = 0
        
        recent_recipes = []
        
        for d in range(days):
            day_plan = {
                'meals': {},
                'day_calories': 0,
                'day_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0}
            }
            

            target_cal = (constraints.daily_calories_min + constraints.daily_calories_max) / 2
            remaining_cal = target_cal
            
            for m in range(constraints.meals_per_day):
                meal_name = meal_names[m] if m < len(meal_names) else f'meal_{m}'
                

                candidates = recipes_by_meal.get(meal_name, self.recipes)
                

                available = [r for r in candidates if r['id'] not in [x['id'] for x in recent_recipes[-constraints.meals_per_day:]]]
                
                if not available:
                    available = candidates
                

                best_recipe = None
                best_score = -1
                target_meal_cal = remaining_cal / (constraints.meals_per_day - m)
                
                for recipe in available[:10]:
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
            

            if len(recent_recipes) > constraints.meals_per_day * 2:
                recent_recipes = recent_recipes[-(constraints.meals_per_day * 2):]
            
            meal_plan['week_plan'][f'day_{d}'] = day_plan
            meal_plan['total_calories'] += day_plan['day_calories']
        

        if days > 0:
            meal_plan['avg_macros']['protein_g'] = round(total_protein / days, 1)
            meal_plan['avg_macros']['carbs_g'] = round(total_carbs / days, 1)
            meal_plan['avg_macros']['fat_g'] = round(total_fat / days, 1)
            meal_plan['avg_macros']['fiber_g'] = round(total_fiber / days, 1)
            meal_plan['avg_daily_calories'] = round(meal_plan['total_calories'] / days, 0)
        
        return meal_plan
    
    async def _get_filtered_recipes_fixed(
        self, user_id: int, constraints: OptimizationConstraints, min_needed: int = 9
    ) -> List[Dict]:

        goal = await self.user_profile_repo.get_active_goal(user_id)
        goal_str = goal.goal_type.value.lower() if goal else None

        dietary_type = constraints.dietary_restrictions[0] if constraints.dietary_restrictions else None

        # First try: filter by goal + dietary + prep-time
        recipes_from_db = await self.recipe_repo.get_filtered_recipes(
            goal_type=goal_str,
            dietary_type=dietary_type,
            exclude_allergens=constraints.allergens if constraints.allergens else None,
            max_prep_time=constraints.max_prep_time_minutes
        )

        print(
            f"[LP] DB query: goal={goal_str} dietary={dietary_type} "
            f"prep_max={constraints.max_prep_time_minutes}min → {len(recipes_from_db)} recipes"
        )

        # If goal filter + other filters leave too few recipes, retry without goal filter
        # Goal alignment is already handled in recipe scoring (not hard filtering)
        if len(recipes_from_db) < min_needed:
            print(
                f"[LP] Only {len(recipes_from_db)} recipes after goal filter (need {min_needed}). "
                f"Retrying without goal filter — scoring will still prefer goal={goal_str} recipes."
            )
            recipes_from_db = await self.recipe_repo.get_filtered_recipes(
                goal_type=None,
                dietary_type=dietary_type,
                exclude_allergens=constraints.allergens if constraints.allergens else None,
                max_prep_time=constraints.max_prep_time_minutes
            )
            print(f"[LP] Without goal filter: {len(recipes_from_db)} recipes")

        # If still too few, drop prep-time filter too
        if len(recipes_from_db) < min_needed:
            print(f"[LP] Still only {len(recipes_from_db)} recipes. Dropping prep-time filter.")
            recipes_from_db = await self.recipe_repo.get_filtered_recipes(
                goal_type=None,
                dietary_type=dietary_type,
                exclude_allergens=None,
                max_prep_time=None
            )
            print(f"[LP] Without prep-time filter: {len(recipes_from_db)} recipes")

        def to_dict(recipe) -> Dict:
            return {
                'id': recipe.id,
                'title': recipe.title,
                'source': recipe.source,
                'suitable_meal_times': recipe.suitable_meal_times or [],
                'goals': recipe.goals or [],
                'dietary_tags': recipe.dietary_tags or [],
                'macros_per_serving': recipe.macros_per_serving,
                'prep_time_min': recipe.prep_time_min or 0,
                'cook_time_min': recipe.cook_time_min or 0,
                'ingredients': []
            }

        min_cal_per_meal = constraints.daily_calories_min / constraints.meals_per_day * 0.5
        max_cal_per_meal = constraints.daily_calories_max / constraints.meals_per_day * 1.5

        calorie_filtered = [
            to_dict(r) for r in recipes_from_db
            if min_cal_per_meal <= r.macros_per_serving.get('calories', 0) <= max_cal_per_meal
        ]

        if len(calorie_filtered) >= min_needed:
            print(f"[LP] After calorie filter: {len(calorie_filtered)} recipes")
            return calorie_filtered

        # If calorie filter also cuts too deep, use all
        print(f"[LP] Calorie filter left only {len(calorie_filtered)} recipes — using all {len(recipes_from_db)}")
        return [to_dict(r) for r in recipes_from_db]
    
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
    

    async def _score_recipes(self, recipes, constraints, inventory, user_id):


        goal = await self.user_profile_repo.get_active_goal(user_id)
        user_goal_type = goal.goal_type.value if goal else 'general_health'

        user_inventory = {}
        if inventory:
            user_inventory = inventory
        else:
            inventory_items = await self.inventory_repo.get_all_for_user(user_id)
            for item in inventory_items:
                user_inventory[item.item_id] = item.quantity_grams
        
        scored = {}

        recipe_ids = [r['id'] for r in recipes]
        all_ingredients_map = await self.recipe_repo.get_ingredients_for_recipes(recipe_ids) if recipe_ids else {}

        target_cal_per_meal = ((constraints.daily_calories_min + constraints.daily_calories_max) / 2) / constraints.meals_per_day
        target_protein_per_meal = constraints.daily_protein_min / constraints.meals_per_day
        target_carbs_per_meal = (constraints.daily_carbs_min + constraints.daily_carbs_max) / 2 / constraints.meals_per_day
        target_fat_per_meal = (constraints.daily_fat_min + constraints.daily_fat_max) / 2 / constraints.meals_per_day

        for recipe in recipes:
            score = RecipeScore(recipe_id=recipe['id'])
            
            recipe_goals = recipe.get('goals', [])
            if user_goal_type in recipe_goals:
                score.goal_alignment = 100
            elif any(g in recipe_goals for g in ['maintenance', 'general_health']):
                score.goal_alignment = 60
            else:
                score.goal_alignment = 30
            

            macros = recipe.get('macros_per_serving', {})
            cal_diff = abs(macros.get('calories', 0) - target_cal_per_meal) / target_cal_per_meal if target_cal_per_meal > 0 else 1
            protein_diff = abs(macros.get('protein_g', 0) - target_protein_per_meal) / target_protein_per_meal if target_protein_per_meal > 0 else 1
            carbs_diff = abs(macros.get('carbs_g', 0) - target_carbs_per_meal) / target_carbs_per_meal if target_carbs_per_meal > 0 else 1
            fat_diff = abs(macros.get('fat_g', 0) - target_fat_per_meal) / target_fat_per_meal if target_fat_per_meal > 0 else 1
            

            avg_diff = (cal_diff * 0.4 + protein_diff * 0.3 + carbs_diff * 0.2 + fat_diff * 0.1)
            score.macro_fit = max(0, 100 - (avg_diff * 50))  
            
            suitable_times = recipe.get('suitable_meal_times', [])
            if len(suitable_times) >= 3:  
                score.timing_appropriateness = 100
            elif len(suitable_times) == 2:
                score.timing_appropriateness = 75
            elif len(suitable_times) == 1:
                score.timing_appropriateness = 50
            else:
                score.timing_appropriateness = 100  
            
            prep_time = recipe.get('prep_time_min', 0)
            cook_time = recipe.get('cook_time_min', 0)
            total_time = prep_time + cook_time
            
            if total_time <= 15:
                score.complexity_score = 0  
            elif total_time <= 30:
                score.complexity_score = 30
            elif total_time <= 45:
                score.complexity_score = 60
            else:
                score.complexity_score = 90  
            
            if user_inventory:

                recipe_ingredients = all_ingredients_map.get(recipe['id'], [])
                
                if recipe_ingredients:
                    total_ingredients = len(recipe_ingredients)
                    available_ingredients = 0
                    
                    for ingredient in recipe_ingredients:
                        if ingredient.item_id in user_inventory:
                            if user_inventory[ingredient.item_id] >= ingredient.quantity_grams:
                                available_ingredients += 1
                            elif user_inventory[ingredient.item_id] > 0:
                                available_ingredients += 0.5
                    
                    score.inventory_coverage = (available_ingredients / total_ingredients) * 100 if total_ingredients > 0 else 0
                else:
                    score.inventory_coverage = 50
            else:
                score.inventory_coverage = 50
            

            score.calculate_composite({
                'goal': 0.3,
                'macro': 0.25,
                'timing': 0.15,
                'complexity': 0.1,
                'inventory': 0.2
            })
            
            scored[recipe['id']] = score
        
        return scored