# backend/app/services/genetic_optimizer.py

import random
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Individual:
    """Represents a meal plan individual in genetic algorithm"""
    genes: List[int]  # Recipe IDs for each meal slot
    fitness: float = 0.0
    
class GeneticMealOptimizer:
    """Genetic Algorithm for meal plan optimization"""
    
    def __init__(
        self,
        population_size: int = 50,
        generations: int = 100,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        elitism_rate: float = 0.1
    ):
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism_rate = elitism_rate
        self.population = []
        
    def optimize(
        self,
        days: int,
        meals_per_day: int,
        recipes: List[Dict],
        constraints: Dict,
        inventory: Dict[int, float]
    ) -> Optional[Dict]:
        """Run genetic algorithm optimization"""
        
        # Initialize population
        self.population = self._initialize_population(
            days, meals_per_day, recipes
        )
        
        # Evolution loop
        for generation in range(self.generations):
            # Evaluate fitness
            for individual in self.population:
                individual.fitness = self._evaluate_fitness(
                    individual, days, meals_per_day, recipes,
                    constraints, inventory
                )
                
            # Sort by fitness
            self.population.sort(key=lambda x: x.fitness, reverse=True)
            
            # Check convergence
            if self._has_converged():
                break
                
            # Create next generation
            next_generation = []
            
            # Elitism - keep best individuals
            elite_count = int(self.population_size * self.elitism_rate)
            next_generation.extend(self.population[:elite_count])
            
            # Crossover and mutation
            while len(next_generation) < self.population_size:
                # Select parents
                parent1 = self._tournament_selection()
                parent2 = self._tournament_selection()
                
                # Crossover
                if random.random() < self.crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2)
                else:
                    child1, child2 = parent1, parent2
                
                # Mutation
                if random.random() < self.mutation_rate:
                    child1 = self._mutate(child1, recipes)
                if random.random() < self.mutation_rate:
                    child2 = self._mutate(child2, recipes)
                    
                next_generation.append(child1)
                if len(next_generation) < self.population_size:
                    next_generation.append(child2)
                    
            self.population = next_generation
            
        # Return best solution
        best_individual = max(self.population, key=lambda x: x.fitness)
        return self._individual_to_meal_plan(
            best_individual, days, meals_per_day, recipes
        )
        
    def _initialize_population(
        self, days: int, meals_per_day: int, recipes: List[Dict]
    ) -> List[Individual]:
        """Create initial random population"""
        population = []
        total_slots = days * meals_per_day
        
        for _ in range(self.population_size):
            genes = []
            for slot in range(total_slots):
                # Random recipe selection
                suitable_recipes = [
                    r for r in recipes
                    if self._is_suitable_for_slot(r, slot, meals_per_day)
                ]
                if suitable_recipes:
                    genes.append(random.choice(suitable_recipes)['id'])
                else:
                    genes.append(recipes[0]['id'])  # Fallback
                    
            population.append(Individual(genes=genes))
            
        return population
        
    def _evaluate_fitness(
        self, individual: Individual, days: int, meals_per_day: int,
        recipes: List[Dict], constraints: Dict, inventory: Dict[int, float]
    ) -> float:
        """Calculate fitness score for an individual"""
        fitness = 100.0
        recipe_map = {r['id']: r for r in recipes}
        
        # Check constraints
        for day in range(days):
            day_calories = 0
            day_protein = 0
            
            for meal in range(meals_per_day):
                slot = day * meals_per_day + meal
                recipe = recipe_map.get(individual.genes[slot])
                
                if recipe:
                    day_calories += recipe['macros_per_serving']['calories']
                    day_protein += recipe['macros_per_serving']['protein_g']
                    
            # Calorie constraint penalty
            if day_calories < constraints['daily_calories_min']:
                fitness -= (constraints['daily_calories_min'] - day_calories) * 0.1
            elif day_calories > constraints['daily_calories_max']:
                fitness -= (day_calories - constraints['daily_calories_max']) * 0.1
                
            # Protein constraint penalty
            if day_protein < constraints['daily_protein_min']:
                fitness -= (constraints['daily_protein_min'] - day_protein) * 0.2
                
        # Variety bonus
        unique_recipes = len(set(individual.genes))
        fitness += unique_recipes * 0.5
        
        # Inventory usage bonus
        inventory_score = self._calculate_inventory_score(
            individual, recipe_map, inventory
        )
        fitness += inventory_score * 10
        
        return max(0, fitness)
        
    def _tournament_selection(self, tournament_size: int = 3) -> Individual:
        """Select individual using tournament selection"""
        tournament = random.sample(self.population, tournament_size)
        return max(tournament, key=lambda x: x.fitness)
        
    def _crossover(
        self, parent1: Individual, parent2: Individual
    ) -> Tuple[Individual, Individual]:
        """Perform crossover between two parents"""
        crossover_point = random.randint(1, len(parent1.genes) - 1)
        
        child1_genes = parent1.genes[:crossover_point] + parent2.genes[crossover_point:]
        child2_genes = parent2.genes[:crossover_point] + parent1.genes[crossover_point:]
        
        return Individual(genes=child1_genes), Individual(genes=child2_genes)
        
    def _mutate(self, individual: Individual, recipes: List[Dict]) -> Individual:
        """Mutate an individual"""
        mutated_genes = individual.genes.copy()
        mutation_point = random.randint(0, len(mutated_genes) - 1)
        
        # Replace with random suitable recipe
        suitable_recipes = [r['id'] for r in recipes]
        mutated_genes[mutation_point] = random.choice(suitable_recipes)
        
        return Individual(genes=mutated_genes)
        
    def _has_converged(self, threshold: float = 0.95) -> bool:
        """Check if population has converged"""
        if len(self.population) < 2:
            return True
            
        best_fitness = self.population[0].fitness
        avg_fitness = sum(ind.fitness for ind in self.population) / len(self.population)
        
        return avg_fitness / best_fitness > threshold if best_fitness > 0 else False
        
    def _is_suitable_for_slot(
        self, recipe: Dict, slot: int, meals_per_day: int
    ) -> bool:
        """Check if recipe is suitable for meal slot"""
        meal_type_idx = slot % meals_per_day
        meal_types = ['breakfast', 'lunch', 'dinner', 'snack'][:meals_per_day]
        meal_type = meal_types[meal_type_idx]
        
        return meal_type in recipe.get('suitable_meal_times', [])
        
    def _calculate_inventory_score(
        self, individual: Individual, recipe_map: Dict,
        inventory: Dict[int, float]
    ) -> float:
        """Calculate inventory usage score"""
        used_items = set()
        
        for recipe_id in individual.genes:
            recipe = recipe_map.get(recipe_id)
            if recipe:
                for ingredient in recipe.get('ingredients', []):
                    if ingredient['item_id'] in inventory:
                        used_items.add(ingredient['item_id'])
                        
        return len(used_items) / max(len(inventory), 1)
        
    def _individual_to_meal_plan(
        self, individual: Individual, days: int, meals_per_day: int,
        recipes: List[Dict]
    ) -> Dict:
        """Convert individual to meal plan format"""
        recipe_map = {r['id']: r for r in recipes}
        meal_plan = {
            'week_plan': {},
            'total_calories': 0,
            'avg_macros': {'protein_g': 0, 'carbs_g': 0, 'fat_g': 0}
        }
        
        meal_types = ['breakfast', 'lunch', 'dinner', 'snack'][:meals_per_day]
        
        for day in range(days):
            day_plan = {}
            
            for meal_idx, meal_type in enumerate(meal_types):
                slot = day * meals_per_day + meal_idx
                recipe = recipe_map.get(individual.genes[slot])
                
                if recipe:
                    day_plan[meal_type] = recipe
                    meal_plan['total_calories'] += recipe['macros_per_serving']['calories']
                    
                    for macro in ['protein_g', 'carbs_g', 'fat_g']:
                        meal_plan['avg_macros'][macro] += recipe['macros_per_serving'][macro]
                        
            meal_plan['week_plan'][f'day_{day}'] = day_plan
            
        # Calculate averages
        total_meals = days * meals_per_day
        for macro in meal_plan['avg_macros']:
            meal_plan['avg_macros'][macro] /= total_meals if total_meals > 0 else 1
            
        return meal_plan