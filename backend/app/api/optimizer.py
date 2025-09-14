# backend/app/api/optimizer.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, Dict, List
from datetime import datetime

from app.models.database import get_db
from app.services.meal_optimizer import MealPlanOptimizer, OptimizationConstraints, OptimizationObjective
from app.services.meal_optimizer import GeneticMealOptimizer
from app.schemas.optimizer import (
    OptimizationRequest,
    OptimizationResponse,
    ConstraintsSchema,
    ObjectiveSchema
)
from ..auth import get_current_user
from ..models import User

router = APIRouter(prefix="/optimizer", tags=["optimizer"])

@router.post("/generate-plan", response_model=OptimizationResponse)
async def generate_meal_plan(
    request: OptimizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate optimized meal plan using Linear Programming"""
    
    optimizer = MealPlanOptimizer(db_session=db)
    
    # Create constraints from request
    constraints = OptimizationConstraints(
        daily_calories_min=request.constraints.daily_calories_min,
        daily_calories_max=request.constraints.daily_calories_max,
        daily_protein_min=request.constraints.daily_protein_min,
        daily_carbs_min=request.constraints.daily_carbs_min,
        daily_carbs_max=request.constraints.daily_carbs_max,
        daily_fat_min=request.constraints.daily_fat_min,
        daily_fat_max=request.constraints.daily_fat_max,
        daily_fiber_min=request.constraints.daily_fiber_min,
        meals_per_day=request.constraints.meals_per_day,
        max_recipe_repeat_in_days=request.constraints.max_recipe_repeat_in_days,
        max_prep_time_minutes=request.constraints.max_prep_time_minutes,
        dietary_restrictions=request.constraints.dietary_restrictions,
        allergens=request.constraints.allergens
    )
    
    # Create objective weights from request
    objective = OptimizationObjective(
        macro_deviation_weight=request.objective.macro_deviation_weight,
        inventory_usage_weight=request.objective.inventory_usage_weight,
        recipe_variety_weight=request.objective.recipe_variety_weight,
        goal_alignment_weight=request.objective.goal_alignment_weight
    )
    
    # Run optimization
    result = optimizer.optimize(
        user_id=current_user.id,
        days=request.days,
        constraints=constraints,
        objective=objective
    )
    
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not generate feasible meal plan with given constraints"
        )
        
    return OptimizationResponse(
        success=True,
        meal_plan=result,
        optimization_method="linear_programming",
        generation_time_seconds=0.0  # Will be calculated
    )
    
@router.post("/generate-plan-genetic", response_model=OptimizationResponse)
async def generate_meal_plan_genetic(
    request: OptimizationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generate meal plan using Genetic Algorithm (fallback method)"""
    
    genetic_optimizer = GeneticMealOptimizer(
        population_size=50,
        generations=100,
        mutation_rate=0.1,
        crossover_rate=0.7
    )
    
    # Fetch recipes and inventory
    recipes = []  # Fetch from database
    inventory = {}  # Fetch from database
    
    constraints = {
        'daily_calories_min': request.constraints.daily_calories_min,
        'daily_calories_max': request.constraints.daily_calories_max,
        'daily_protein_min': request.constraints.daily_protein_min
    }
    
    result = genetic_optimizer.optimize(
        days=request.days,
        meals_per_day=request.constraints.meals_per_day,
        recipes=recipes,
        constraints=constraints,
        inventory=inventory
    )
    
    if not result:
        raise HTTPException(
            status_code=400,
            detail="Genetic algorithm failed to find solution"
        )
        
    return OptimizationResponse(
        success=True,
        meal_plan=result,
        optimization_method="genetic_algorithm",
        generation_time_seconds=0.0
    )
    
@router.get("/test-optimizer")
async def test_optimizer(
    days: int = Query(7, ge=1, le=14),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test endpoint for optimizer with default parameters"""
    
    optimizer = MealPlanOptimizer(db_session=db)
    
    # Use default constraints for testing
    constraints = OptimizationConstraints(
        daily_calories_min=1800,
        daily_calories_max=2200,
        daily_protein_min=120,
        meals_per_day=3
    )
    
    result = optimizer.optimize(
        user_id=current_user.id,
        days=days,
        constraints=constraints
    )
    
    return {
        "success": result is not None,
        "meal_plan": result,
        "test_mode": True
    }