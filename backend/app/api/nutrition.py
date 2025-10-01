# backend/app/api/nutrition.py
"""
API endpoints for nutrition guidance and education
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.models.database import get_db, User
from app.agents.nutrition_agent import NutritionAgent
from app.services.auth import get_current_user

router = APIRouter(prefix="/nutrition", tags=["Nutrition"])

# Pydantic models for requests and responses

class BMRCalculationRequest(BaseModel):
    """Request model for BMR/TDEE calculation"""
    weight_kg: Optional[float] = Field(None, ge=30, le=300, description="Weight in kg")
    height_cm: Optional[float] = Field(None, ge=100, le=250, description="Height in cm")
    age: Optional[int] = Field(None, ge=10, le=120, description="Age in years")
    sex: Optional[str] = Field(None, description="Biological sex (male/female)")
    activity_level: Optional[str] = Field(None, description="Activity level")
    
    @validator('sex')
    def validate_sex(cls, v):
        if v and v.lower() not in ['male', 'female', 'm', 'f']:
            raise ValueError("Sex must be 'male' or 'female'")
        return v
    
    @validator('activity_level')
    def validate_activity(cls, v):
        valid_levels = ['sedentary', 'lightly_active', 'moderately_active', 
                       'very_active', 'extra_active']
        if v and v not in valid_levels:
            raise ValueError(f"Activity level must be one of {valid_levels}")
        return v

class GoalAdjustmentRequest(BaseModel):
    """Request model for goal-based calorie adjustment"""
    goal_type: Optional[str] = Field(None, description="Goal type")
    target_weight: Optional[float] = Field(None, ge=30, le=300, description="Target weight in kg")
    timeline_weeks: Optional[int] = Field(None, ge=1, le=52, description="Timeline in weeks")
    
    @validator('goal_type')
    def validate_goal(cls, v):
        valid_goals = ['muscle_gain', 'fat_loss', 'body_recomp', 
                      'weight_training', 'endurance', 'general_health']
        if v and v not in valid_goals:
            raise ValueError(f"Goal type must be one of {valid_goals}")
        return v

class MacroAnalysisRequest(BaseModel):
    """Request model for macro analysis"""
    recipe_id: Optional[int] = Field(None, description="Recipe ID to analyze")
    meal_log_id: Optional[int] = Field(None, description="Meal log ID to analyze")
    include_micros: bool = Field(False, description="Include micronutrient analysis")

class MealSuggestionRequest(BaseModel):
    """Request model for meal suggestions"""
    meal_type: Optional[str] = Field(None, description="Type of meal")
    time_until_meal: Optional[int] = Field(None, description="Minutes until meal")
    
    @validator('meal_type')
    def validate_meal_type(cls, v):
        if v and v not in ['breakfast', 'lunch', 'dinner', 'snack']:
            raise ValueError("Invalid meal type")
        return v

class EducationRequest(BaseModel):
    """Request model for nutrition education"""
    topic: Optional[str] = Field(None, description="Education topic")
    
    @validator('topic')
    def validate_topic(cls, v):
        valid_topics = ['macros', 'meal_timing', 'hydration', 'goal_specific', 
                       'supplements', 'recovery', 'performance']
        if v and v not in valid_topics:
            raise ValueError(f"Topic must be one of {valid_topics}")
        return v

class PortionAdjustmentRequest(BaseModel):
    """Request model for portion adjustment"""
    recipe_id: int = Field(..., description="Recipe ID")
    user_preference: Optional[float] = Field(None, ge=0.5, le=3.0, 
                                            description="User's preferred portion size")

class ProgressReportRequest(BaseModel):
    """Request model for progress report"""
    period_days: int = Field(7, ge=1, le=90, description="Report period in days")

# Response models

class BMRResponse(BaseModel):
    """Response model for BMR/TDEE calculation"""
    success: bool
    calculations: Optional[Dict[str, float]]
    explanation: Optional[str]
    recommendations: Optional[List[str]]
    error: Optional[str]

class GoalAdjustmentResponse(BaseModel):
    """Response model for goal adjustment"""
    success: bool
    goal_type: Optional[str]
    current_tdee: Optional[float]
    adjusted_calories: Optional[float]
    calorie_adjustment: Optional[float]
    macros: Optional[Dict[str, float]]
    description: Optional[str]
    recommendations: Optional[List[str]]
    error: Optional[str]

class MacroAnalysisResponse(BaseModel):
    """Response model for macro analysis"""
    success: bool
    recipe: Optional[str]
    total_calories: Optional[float]
    calculated_calories: Optional[float]
    macros: Optional[Dict[str, Any]]
    quality_scores: Optional[Dict[str, float]]
    micronutrients: Optional[Dict[str, Any]]
    recommendations: Optional[List[str]]
    error: Optional[str]

class DailyTargetsResponse(BaseModel):
    """Response model for daily targets check"""
    success: bool
    date: Optional[str]
    consumed: Optional[Dict[str, float]]
    progress: Optional[Dict[str, Dict]]
    remaining: Optional[Dict[str, float]]
    status: Optional[str]
    expected_progress: Optional[str]
    remaining_meals: Optional[int]
    recommendations: Optional[List[str]]
    meal_suggestions: Optional[List[Dict]]
    error: Optional[str]

class MealSuggestionResponse(BaseModel):
    """Response model for meal suggestions"""
    success: bool
    meal_type: Optional[str]
    time_until_meal: Optional[int]
    meal_targets: Optional[Dict[str, float]]
    suggestions: Optional[List[Dict]]
    primary_recommendation: Optional[Dict]
    timing_advice: Optional[str]
    preparation_tips: Optional[List[str]]
    error: Optional[str]
    message: Optional[str]

class MealTimingResponse(BaseModel):
    """Response model for meal timing"""
    success: bool
    path_type: Optional[str]
    recommended_schedule: Optional[Dict]
    goal_adjustments: Optional[Dict]
    actual_patterns: Optional[Dict]
    optimization_tips: Optional[List[str]]
    circadian_alignment: Optional[Dict]
    error: Optional[str]

class EducationResponse(BaseModel):
    """Response model for nutrition education"""
    success: bool
    education: Optional[Dict]
    personalized_tips: Optional[List[str]]
    related_topics: Optional[List[str]]
    quiz: Optional[List[Dict]]
    error: Optional[str]

class WeeklyProgressResponse(BaseModel):
    """Response model for weekly progress"""
    success: bool
    week_summary: Optional[Dict]
    totals: Optional[Dict]
    averages: Optional[Dict]
    target_achievement: Optional[Dict]
    daily_breakdown: Optional[Dict]
    weight_change: Optional[Dict]
    insights: Optional[List[str]]
    recommendations: Optional[List[str]]
    error: Optional[str]

class ProgressReportResponse(BaseModel):
    """Response model for progress report"""
    success: bool
    report_period: Optional[str]
    generated_at: Optional[str]
    summary: Optional[Dict]
    achievements: Optional[List[Dict]]
    areas_for_improvement: Optional[List[Dict]]
    insights: Optional[List[str]]
    action_items: Optional[List[Dict]]
    detailed_metrics: Optional[Dict]
    next_review_date: Optional[str]
    error: Optional[str]

# API Endpoints

@router.post("/calculate-bmr", response_model=BMRResponse)
async def calculate_bmr_tdee(
    request: BMRCalculationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calculate Basal Metabolic Rate (BMR) and Total Daily Energy Expenditure (TDEE)
    
    - Uses Mifflin-St Jeor formula for BMR
    - Applies activity multiplier for TDEE
    - Provides protein and hydration requirements
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.calculate_bmr_tdee(
        weight_kg=request.weight_kg,
        height_cm=request.height_cm,
        age=request.age,
        sex=request.sex,
        activity_level=request.activity_level
    )
    
    return BMRResponse(**result)

@router.post("/adjust-calories", response_model=GoalAdjustmentResponse)
async def adjust_calories_for_goal(
    request: GoalAdjustmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Adjust calorie and macro targets based on specific goals
    
    - Calculates appropriate surplus/deficit
    - Sets macro distribution for goal
    - Provides goal-specific recommendations
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.adjust_calories_for_goal(
        goal_type=request.goal_type,
        target_weight=request.target_weight,
        timeline_weeks=request.timeline_weeks
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to adjust calories")
        )
    
    return GoalAdjustmentResponse(**result)

@router.post("/analyze-macros", response_model=MacroAnalysisResponse)
async def analyze_meal_macros(
    request: MacroAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze macronutrient breakdown of a meal
    
    - Calculates macro distribution
    - Provides quality scores
    - Optional micronutrient analysis
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.analyze_meal_macros(
        recipe_id=request.recipe_id,
        meal_log_id=request.meal_log_id,
        include_micros=request.include_micros
    )
    
    return MacroAnalysisResponse(**result)

@router.get("/daily-targets", response_model=DailyTargetsResponse)
async def check_daily_targets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check progress against daily nutritional targets
    
    - Shows consumed vs target nutrients
    - Calculates remaining allowance
    - Provides meal suggestions for remaining targets
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.check_daily_targets()
    
    return DailyTargetsResponse(**result)

@router.post("/suggest-meal", response_model=MealSuggestionResponse)
async def suggest_next_meal(
    request: MealSuggestionRequest = MealSuggestionRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get intelligent meal suggestions based on remaining targets
    
    - Considers remaining macros for the day
    - Checks inventory availability
    - Accounts for preparation time
    - Aligns with user goals
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.suggest_next_meal(
        meal_type=request.meal_type,
        time_until_meal=request.time_until_meal
    )
    
    return MealSuggestionResponse(**result)

@router.get("/meal-timing", response_model=MealTimingResponse)
async def get_optimal_meal_timing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calculate optimal meal timing windows
    
    - Based on eating pattern (IF, traditional, etc.)
    - Goal-specific adjustments
    - Circadian rhythm optimization
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.calculate_meal_timing()
    
    return MealTimingResponse(**result)

@router.post("/education", response_model=EducationResponse)
async def get_nutrition_education(
    request: EducationRequest = EducationRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get educational content about nutrition
    
    - Topic-based education
    - Personalized tips
    - Interactive quizzes
    - Related topics for further learning
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.provide_nutrition_education(topic=request.topic)
    
    return EducationResponse(**result)

@router.get("/weekly-progress", response_model=WeeklyProgressResponse)
async def track_weekly_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Track and analyze weekly nutritional progress
    
    - Weekly totals and averages
    - Compliance rate tracking
    - Trend analysis
    - Weight change estimation
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.track_weekly_progress()
    
    return WeeklyProgressResponse(**result)

@router.post("/adjust-portion", response_model=Dict[str, Any])
async def adjust_portion_size(
    request: PortionAdjustmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized portion size recommendations
    
    - Based on historical consumption
    - Goal-adjusted portions
    - Target fit scoring
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.adjust_portions(
        recipe_id=request.recipe_id,
        user_preference=request.user_preference
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to adjust portion")
        )
    
    return result

@router.post("/progress-report", response_model=ProgressReportResponse)
async def generate_progress_report(
    request: ProgressReportRequest = ProgressReportRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate comprehensive nutritional progress report
    
    - Achievements and areas for improvement
    - Actionable insights
    - Detailed metrics
    - Next steps
    """
    agent = NutritionAgent(db, current_user.id)
    
    result = agent.generate_progress_report(period_days=request.period_days)
    
    return ProgressReportResponse(**result)

# Real-time nutrition guidance endpoints

@router.get("/recommendations/next-meal")
async def get_next_meal_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recommendations for the next scheduled meal
    
    - Time-aware suggestions
    - Macro-optimized options
    - Prep time consideration
    """
    agent = NutritionAgent(db, current_user.id)
    
    # Get next meal timing
    from app.models.database import MealLog
    
    today = date.today()
    next_meal = db.query(MealLog).filter(
        and_(
            MealLog.user_id == current_user.id,
            func.date(MealLog.planned_datetime) == today,
            MealLog.consumed_datetime.is_(None),
            MealLog.was_skipped.is_(False)
        )
    ).order_by(MealLog.planned_datetime).first()
    
    if not next_meal:
        return {
            "success": False,
            "message": "No upcoming meals scheduled today"
        }
    
    time_until = int((next_meal.planned_datetime - datetime.utcnow()).total_seconds() / 60)
    
    result = agent.suggest_next_meal(
        meal_type=next_meal.meal_type,
        time_until_meal=time_until
    )
    
    return result

@router.get("/recommendations/pre-workout")
async def get_pre_workout_nutrition(
    workout_in_minutes: int = Query(60, description="Time until workout in minutes"),
    workout_type: str = Query("strength", description="Type of workout"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get pre-workout nutrition recommendations
    
    - Timing-specific advice
    - Workout type optimization
    - Macro recommendations
    """
    agent = NutritionAgent(db, current_user.id)
    
    recommendations = {
        "success": True,
        "workout_type": workout_type,
        "time_until_workout": workout_in_minutes,
        "nutrition_timing": {}
    }
    
    if workout_in_minutes < 30:
        recommendations["nutrition_timing"] = {
            "eat_now": False,
            "recommendation": "Too close to workout - have only water or BCAAs",
            "if_needed": "Small banana or dates for quick energy"
        }
    elif workout_in_minutes < 60:
        recommendations["nutrition_timing"] = {
            "eat_now": True,
            "recommendation": "Light snack with simple carbs",
            "suggestions": ["Banana with almond butter", "Rice cakes with honey", "Apple slices"],
            "avoid": ["High fat", "High fiber", "Large portions"]
        }
    elif workout_in_minutes < 120:
        recommendations["nutrition_timing"] = {
            "eat_now": True,
            "recommendation": "Balanced meal with carbs and moderate protein",
            "suggestions": ["Oatmeal with protein powder", "Toast with eggs", "Smoothie bowl"],
            "macros": {"carbs_g": 30-50, "protein_g": 15-25, "fat_g": 5-10}
        }
    else:
        recommendations["nutrition_timing"] = {
            "eat_now": True,
            "recommendation": "Full meal with complex carbs and protein",
            "suggestions": ["Chicken with rice", "Pasta with lean meat", "Quinoa bowl"],
            "macros": {"carbs_g": 40-60, "protein_g": 25-35, "fat_g": 10-15}
        }
    
    # Add workout-specific advice
    if workout_type == "endurance":
        recommendations["special_considerations"] = [
            "Increase carb intake for sustained energy",
            "Consider electrolyte supplementation",
            "Hydrate well 2 hours before"
        ]
    elif workout_type == "strength":
        recommendations["special_considerations"] = [
            "Ensure adequate protein for muscle synthesis",
            "Moderate carbs for explosive energy",
            "Consider creatine supplementation"
        ]
    
    return recommendations

@router.get("/recommendations/post-workout")
async def get_post_workout_nutrition(
    workout_completed_minutes_ago: int = Query(0, description="Minutes since workout ended"),
    workout_intensity: str = Query("moderate", description="Workout intensity level"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get post-workout nutrition recommendations
    
    - Recovery optimization
    - Anabolic window guidance
    - Macro ratios for recovery
    """
    recommendations = {
        "success": True,
        "time_since_workout": workout_completed_minutes_ago,
        "intensity": workout_intensity,
        "recovery_nutrition": {}
    }
    
    if workout_completed_minutes_ago < 30:
        recommendations["recovery_nutrition"] = {
            "priority": "high",
            "recommendation": "Consume protein and carbs immediately",
            "optimal_window": "Within 30 minutes",
            "suggestions": [
                "Protein shake with banana",
                "Greek yogurt with berries",
                "Chocolate milk"
            ],
            "macro_ratio": "3:1 or 4:1 carbs to protein",
            "target": {"carbs_g": 30-45, "protein_g": 20-25}
        }
    elif workout_completed_minutes_ago < 60:
        recommendations["recovery_nutrition"] = {
            "priority": "moderate",
            "recommendation": "Have a balanced meal soon",
            "optimal_window": "Within next 30 minutes",
            "suggestions": [
                "Chicken and rice bowl",
                "Tuna sandwich",
                "Protein smoothie bowl"
            ],
            "target": {"carbs_g": 40-60, "protein_g": 25-35}
        }
    else:
        recommendations["recovery_nutrition"] = {
            "priority": "low",
            "recommendation": "Anabolic window passed - eat normally",
            "note": "Focus on meeting daily protein targets",
            "suggestions": ["Regular balanced meal"],
            "target": {"protein_g": 25-35}
        }
    
    # Intensity-based adjustments
    if workout_intensity == "high":
        recommendations["additional_needs"] = [
            "Increase carb intake for glycogen replenishment",
            "Consider anti-inflammatory foods",
            "Ensure adequate hydration with electrolytes"
        ]
    
    return recommendations

@router.get("/insights/daily")
async def get_daily_nutrition_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get personalized daily nutrition insights
    
    - Current progress analysis
    - Contextual recommendations
    - Educational tips
    """
    agent = NutritionAgent(db, current_user.id)
    
    # Get current progress
    daily_targets = agent.check_daily_targets()
    
    if not daily_targets["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to generate insights"
        )
    
    insights = {
        "success": True,
        "date": date.today().isoformat(),
        "insights": []
    }
    
    # Generate contextual insights
    progress = daily_targets.get("progress", {})
    status = daily_targets.get("status", "unknown")
    
    # Calorie insight
    calorie_progress = progress.get("calories", {}).get("percentage", 0)
    if calorie_progress < 40 and datetime.now().hour > 14:
        insights["insights"].append({
            "type": "warning",
            "message": "You're significantly behind on calories - prioritize nutrient-dense meals",
            "action": "Consider adding a protein shake or nuts"
        })
    elif calorie_progress > 90 and datetime.now().hour < 18:
        insights["insights"].append({
            "type": "info",
            "message": "Close to calorie target with meals remaining - opt for lighter options",
            "action": "Focus on vegetables and lean proteins"
        })
    
    # Protein insight
    protein_progress = progress.get("protein_g", {}).get("percentage", 0)
    if protein_progress < 60:
        insights["insights"].append({
            "type": "tip",
            "message": "Protein intake is low - essential for muscle preservation",
            "action": "Add Greek yogurt, protein powder, or lean meat to next meal"
        })
    
    # Hydration reminder
    current_hour = datetime.now().hour
    if current_hour in [10, 14, 17]:
        insights["insights"].append({
            "type": "reminder",
            "message": "Hydration check - aim for a glass of water now",
            "action": "Drink 250-500ml of water"
        })
    
    # Educational tip
    import random
    tips = [
        "Protein helps with satiety - spread intake throughout the day",
        "Fiber slows digestion and improves fullness - aim for 25-35g daily",
        "Healthy fats are essential for hormone production",
        "Complex carbs provide sustained energy compared to simple sugars",
        "Meal timing matters less than total daily intake for weight management"
    ]
    
    insights["insights"].append({
        "type": "education",
        "message": random.choice(tips)
    })
    
    return insights

@router.get("/analysis/meal-quality/{meal_log_id}")
async def analyze_meal_quality(
    meal_log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze the nutritional quality of a specific meal
    
    - Macro balance assessment
    - Micronutrient coverage
    - Goal alignment score
    """
    agent = NutritionAgent(db, current_user.id)
    
    # Analyze the meal
    analysis = agent.analyze_meal_macros(
        meal_log_id=meal_log_id,
        include_micros=True
    )
    
    if not analysis["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=analysis.get("error", "Failed to analyze meal")
        )
    
    # Add goal alignment
    from app.models.database import UserGoal, MealLog
    
    user_goal = db.query(UserGoal).filter(
        UserGoal.user_id == current_user.id
    ).first()
    
    meal_log = db.query(MealLog).filter(
        MealLog.id == meal_log_id
    ).first()
    
    if user_goal and meal_log and meal_log.recipe:
        goal_alignment = 100
        
        if user_goal.goal_type.value in meal_log.recipe.goals:
            analysis["goal_alignment"] = {
                "score": 100,
                "message": f"Perfectly aligned with {user_goal.goal_type.value} goal"
            }
        else:
            analysis["goal_alignment"] = {
                "score": 50,
                "message": "Moderately aligned with your goals"
            }
    
    return analysis

@router.get("/trends/weekly")
async def get_weekly_nutrition_trends(
    weeks: int = Query(4, ge=1, le=12, description="Number of weeks to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze nutrition trends over multiple weeks
    
    - Compliance trends
    - Macro distribution changes
    - Progress towards goals
    """
    agent = NutritionAgent(db, current_user.id)
    
    trends = {
        "success": True,
        "period": f"Last {weeks} weeks",
        "weekly_data": []
    }
    
    # Get data for each week
    for week_offset in range(weeks):
        week_start = datetime.utcnow() - timedelta(weeks=week_offset+1)
        week_end = week_start + timedelta(days=7)
        
        # Get meal logs for this week
        from app.models.database import MealLog
        
        meal_logs = db.query(MealLog).filter(
            and_(
                MealLog.user_id == current_user.id,
                MealLog.planned_datetime >= week_start,
                MealLog.planned_datetime < week_end
            )
        ).all()
        
        if meal_logs:
            consumed = [log for log in meal_logs if log.consumed_datetime]
            
            week_data = {
                "week_start": week_start.date().isoformat(),
                "compliance_rate": (len(consumed) / len(meal_logs) * 100) if meal_logs else 0,
                "total_meals": len(meal_logs),
                "consumed_meals": len(consumed)
            }
            
            trends["weekly_data"].append(week_data)
    
    # Calculate trend direction
    if len(trends["weekly_data"]) >= 2:
        recent_compliance = trends["weekly_data"][0]["compliance_rate"]
        older_compliance = trends["weekly_data"][-1]["compliance_rate"]
        
        if recent_compliance > older_compliance + 5:
            trends["trend"] = "improving"
            trends["message"] = "Great job! Your consistency is improving"
        elif recent_compliance < older_compliance - 5:
            trends["trend"] = "declining"
            trends["message"] = "Focus on meal planning to improve consistency"
        else:
            trends["trend"] = "stable"
            trends["message"] = "Maintaining consistent nutrition habits"
    
    return trends

@router.post("/feedback/meal-rating")
async def submit_meal_rating(
    meal_log_id: int = Body(..., description="Meal log ID"),
    rating: int = Body(..., ge=1, le=5, description="Rating from 1-5"),
    feedback: Optional[str] = Body(None, description="Optional feedback"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit feedback and rating for a consumed meal
    
    - Helps improve future recommendations
    - Tracks meal satisfaction
    """
    from app.models.database import MealLog, AgentInteraction
    
    # Verify meal belongs to user
    meal_log = db.query(MealLog).filter(
        and_(
            MealLog.id == meal_log_id,
            MealLog.user_id == current_user.id,
            MealLog.consumed_datetime.isnot(None)
        )
    ).first()
    
    if not meal_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal not found or not consumed"
        )
    
    # Store feedback
    interaction = AgentInteraction(
        user_id=current_user.id,
        agent_type="nutrition",
        interaction_type="meal_feedback",
        input_text=feedback,
        context_data={
            "meal_log_id": meal_log_id,
            "recipe_id": meal_log.recipe_id,
            "rating": rating,
            "meal_type": meal_log.meal_type
        },
        created_at=datetime.utcnow()
    )
    
    db.add(interaction)
    db.commit()
    
    return {
        "success": True,
        "message": "Thank you for your feedback!",
        "rating": rating,
        "meal": meal_log.recipe.title if meal_log.recipe else "External meal"
    }