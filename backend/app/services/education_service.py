# backend/app/services/education_service.py
"""
Educational Content Service for NutriLens AI
Provides personalized nutrition education and guidance
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
import logging
import random

from app.models.database import (
    User, UserProfile, UserGoal, MealLog,
    AgentInteraction, GoalType
)

logger = logging.getLogger(__name__)

class NutritionEducationService:
    """Service for providing nutrition education content"""
    
    def __init__(self, db: Session):
        self.db = db
        self.education_library = self._load_education_library()
    
    def _load_education_library(self) -> Dict[str, Any]:
        """Load comprehensive education content library"""
        
        return {
            "basics": {
                "calories": {
                    "title": "Understanding Calories",
                    "content": """
                    Calories are units of energy that fuel your body. Your body needs calories for:
                    • Basic functions (breathing, heartbeat, cell repair) - BMR
                    • Daily activities (walking, working)
                    • Exercise and physical activity
                    • Digestion (TEF - Thermic Effect of Food)
                    
                    Key Points:
                    • 1 gram protein = 4 calories
                    • 1 gram carbohydrate = 4 calories
                    • 1 gram fat = 9 calories
                    • 1 gram alcohol = 7 calories
                    """,
                    "tips": [
                        "Quality matters as much as quantity",
                        "Focus on nutrient-dense foods",
                        "Your needs change daily based on activity"
                    ],
                    "quiz": [
                        {
                            "q": "How many calories in 1 gram of fat?",
                            "a": "9 calories",
                            "options": ["4", "7", "9", "11"]
                        }
                    ]
                },
                "protein": {
                    "title": "Protein: The Building Block",
                    "content": """
                    Protein is essential for:
                    • Building and repairing muscle tissue
                    • Making enzymes and hormones
                    • Supporting immune function
                    • Providing satiety (feeling full)
                    
                    Daily Requirements:
                    • Sedentary: 0.8g per kg body weight
                    • Active: 1.2-1.6g per kg
                    • Athletes: 1.6-2.2g per kg
                    • Fat loss: 1.8-2.4g per kg (preserves muscle)
                    
                    Complete vs Incomplete:
                    • Complete: Contains all 9 essential amino acids (meat, eggs, dairy, soy)
                    • Incomplete: Missing some amino acids (most plant proteins)
                    • Combine incomplete proteins for complete amino acid profile
                    """,
                    "tips": [
                        "Spread protein intake throughout the day",
                        "Aim for 20-30g per meal for optimal synthesis",
                        "Include leucine-rich foods for muscle building"
                    ]
                },
                "carbohydrates": {
                    "title": "Carbohydrates: Your Energy Source",
                    "content": """
                    Carbohydrates are your body's preferred energy source:
                    
                    Types:
                    • Simple carbs: Quick energy (fruits, sugar, honey)
                    • Complex carbs: Sustained energy (whole grains, oats, quinoa)
                    • Fiber: Non-digestible carbs (vegetables, whole grains)
                    
                    Glycemic Index:
                    • Low GI (<55): Slow digestion, stable energy
                    • Medium GI (55-69): Moderate impact
                    • High GI (>70): Quick energy, blood sugar spike
                    
                    Timing Matters:
                    • Morning: Complex carbs for sustained energy
                    • Pre-workout: Simple carbs for quick fuel
                    • Post-workout: Carbs + protein for recovery
                    • Evening: Moderate carbs to avoid energy crashes
                    """,
                    "tips": [
                        "Choose whole grains over refined",
                        "Pair carbs with protein/fat to slow digestion",
                        "Time carbs around activity for best use"
                    ]
                },
                "fats": {
                    "title": "Fats: Essential for Health",
                    "content": """
                    Fats are crucial for:
                    • Hormone production (testosterone, estrogen)
                    • Vitamin absorption (A, D, E, K)
                    • Brain function and mood
                    • Cell membrane health
                    • Inflammation control
                    
                    Types:
                    • Saturated: Limit to <10% of calories (meat, dairy, coconut)
                    • Monounsaturated: Heart-healthy (olive oil, avocados, nuts)
                    • Polyunsaturated: Essential fatty acids (fish, walnuts, seeds)
                    • Trans fats: AVOID (processed foods)
                    
                    Omega Balance:
                    • Omega-3: Anti-inflammatory (fatty fish, flax, chia)
                    • Omega-6: Pro-inflammatory when excessive (vegetable oils)
                    • Aim for 1:1 to 1:4 ratio of omega-3 to omega-6
                    """,
                    "tips": [
                        "Include fatty fish 2-3x per week",
                        "Use olive oil for cooking",
                        "Add nuts/seeds for healthy fats and fiber"
                    ]
                }
            },
            "advanced": {
                "meal_timing": {
                    "title": "Nutrient Timing Strategies",
                    "content": """
                    Strategic meal timing can optimize:
                    • Energy levels
                    • Performance
                    • Recovery
                    • Body composition
                    
                    Pre-Workout (1-3 hours before):
                    • Moderate protein (15-25g)
                    • Complex carbs (30-50g)
                    • Minimal fat and fiber
                    
                    Post-Workout (within 1 hour):
                    • Fast-digesting protein (20-40g)
                    • Simple + complex carbs (0.5-1g per kg body weight)
                    • Minimal fat (slows absorption)
                    
                    Intermittent Fasting Benefits:
                    • Improved insulin sensitivity
                    • Enhanced autophagy
                    • Potential fat loss benefits
                    • Simplified meal planning
                    """,
                    "tips": [
                        "Match eating windows to lifestyle",
                        "Don't force timing if it causes stress",
                        "Total daily intake matters most"
                    ]
                },
                "supplements": {
                    "title": "Smart Supplementation",
                    "content": """
                    Evidence-Based Supplements:
                    
                    Tier 1 (Strong Evidence):
                    • Creatine: 3-5g daily for strength/power
                    • Protein powder: Convenience for hitting targets
                    • Vitamin D: 1000-4000 IU if deficient
                    • Omega-3: 1-3g EPA/DHA daily
                    
                    Tier 2 (Moderate Evidence):
                    • Multivitamin: Insurance policy
                    • Magnesium: 200-400mg for sleep/recovery
                    • Probiotics: Gut health
                    • Caffeine: 3-6mg/kg for performance
                    
                    When to Consider:
                    • Dietary restrictions
                    • Confirmed deficiencies
                    • Performance goals
                    • Convenience needs
                    """,
                    "tips": [
                        "Food first, supplements second",
                        "Get blood work to identify needs",
                        "Buy third-party tested products"
                    ]
                }
            },
            "goal_specific": {
                "muscle_gain": {
                    "title": "Nutrition for Muscle Growth",
                    "content": """
                    Key Principles:
                    1. Caloric Surplus: 300-500 calories above TDEE
                    2. Protein Priority: 1.6-2.2g per kg body weight
                    3. Progressive Overload: Nutrition supports training
                    4. Recovery Focus: 7-9 hours sleep
                    
                    Macro Distribution:
                    • Protein: 25-30% (priority nutrient)
                    • Carbs: 45-50% (fuel for training)
                    • Fat: 20-25% (hormone support)
                    
                    Meal Frequency:
                    • 4-6 meals per day
                    • 20-40g protein per meal
                    • Pre/post workout nutrition critical
                    
                    Common Mistakes:
                    • Excessive surplus (leads to fat gain)
                    • Neglecting vegetables/fiber
                    • Poor meal timing
                    • Inadequate hydration
                    """,
                    "tips": [
                        "Track weekly weight (aim for 0.25-0.5kg/week)",
                        "Take progress photos",
                        "Adjust calories based on progress"
                    ]
                },
                "fat_loss": {
                    "title": "Nutrition for Fat Loss",
                    "content": """
                    Key Principles:
                    1. Caloric Deficit: 300-750 calories below TDEE
                    2. High Protein: 1.8-2.4g per kg (preserve muscle)
                    3. Strength Training: Maintain muscle mass
                    4. Patience: 0.5-1kg per week is optimal
                    
                    Macro Distribution:
                    • Protein: 30-35% (satiety + muscle preservation)
                    • Carbs: 35-40% (performance + adherence)
                    • Fat: 25-30% (hormones + satisfaction)
                    
                    Strategies:
                    • Volume eating (high fiber, low calorie density)
                    • Meal prep for consistency
                    • Track intake accurately
                    • Include refeed days/diet breaks
                    
                    Avoid:
                    • Extreme deficits (muscle loss, metabolic adaptation)
                    • Eliminating food groups
                    • Liquid calories
                    • All-or-nothing mentality
                    """,
                    "tips": [
                        "Focus on trend, not daily fluctuations",
                        "Keep protein high always",
                        "Plan for social events"
                    ]
                },
                "performance": {
                    "title": "Performance Nutrition",
                    "content": """
                    Fueling for Performance:
                    
                    Endurance Athletes:
                    • Carbs: 6-10g per kg body weight
                    • Protein: 1.2-1.6g per kg
                    • Fat: 20-35% of calories
                    • Hydration: Critical with electrolytes
                    
                    Strength/Power Athletes:
                    • Carbs: 4-7g per kg body weight
                    • Protein: 1.6-2.2g per kg
                    • Fat: 25-30% of calories
                    • Creatine: 3-5g daily
                    
                    Competition Day:
                    • 3-4 hours before: Normal meal
                    • 1-2 hours before: Light carbs + caffeine
                    • During: Simple carbs if >60 minutes
                    • After: Recovery nutrition immediately
                    
                    Hydration Protocol:
                    • Daily: 35ml per kg + exercise losses
                    • Pre: 500ml 2 hours before
                    • During: 150-250ml every 15-20 min
                    • Post: 150% of fluid lost
                    """,
                    "tips": [
                        "Practice competition nutrition in training",
                        "Never try new foods on competition day",
                        "Monitor urine color for hydration"
                    ]
                }
            },
            "special_topics": {
                "gut_health": {
                    "title": "Optimizing Gut Health",
                    "content": """
                    Your gut affects:
                    • Nutrient absorption
                    • Immune function
                    • Mental health
                    • Inflammation
                    • Weight management
                    
                    Prebiotics (feed good bacteria):
                    • Fiber-rich foods
                    • Garlic, onions, leeks
                    • Bananas, apples
                    • Oats, barley
                    
                    Probiotics (add good bacteria):
                    • Yogurt, kefir
                    • Sauerkraut, kimchi
                    • Kombucha
                    • Miso, tempeh
                    
                    Gut Health Tips:
                    • Eat 30+ different plants weekly
                    • Limit processed foods
                    • Manage stress
                    • Get adequate sleep
                    • Stay hydrated
                    """,
                    "tips": [
                        "Add fermented foods daily",
                        "Increase fiber gradually",
                        "Consider digestive enzymes if needed"
                    ]
                },
                "inflammation": {
                    "title": "Anti-Inflammatory Nutrition",
                    "content": """
                    Chronic inflammation linked to:
                    • Heart disease
                    • Diabetes
                    • Arthritis
                    • Certain cancers
                    • Mental health issues
                    
                    Anti-Inflammatory Foods:
                    • Fatty fish (salmon, mackerel, sardines)
                    • Berries (blueberries, cherries)
                    • Leafy greens
                    • Nuts and seeds
                    • Olive oil
                    • Turmeric, ginger
                    • Green tea
                    
                    Pro-Inflammatory (limit):
                    • Refined sugar
                    • Processed meats
                    • Trans fats
                    • Excessive omega-6 oils
                    • Refined grains
                    • Excessive alcohol
                    
                    Lifestyle Factors:
                    • Regular exercise
                    • Stress management
                    • Quality sleep
                    • Maintain healthy weight
                    """,
                    "tips": [
                        "Aim for colorful plates",
                        "Cook with herbs and spices",
                        "Choose whole foods over processed"
                    ]
                }
            }
        }
    
    def get_personalized_education(
        self,
        user_id: int,
        topic: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get personalized educational content for user"""
        
        try:
            # Get user context
            user_context = self._get_user_context(user_id)
            
            # Select appropriate topic if not specified
            if not topic:
                topic = self._select_relevant_topic(user_context)
            
            # Get base content
            content = self._get_topic_content(topic)
            
            # Personalize content
            personalized = self._personalize_content(content, user_context)
            
            # Track education delivery
            self._track_education_delivery(user_id, topic)
            
            return {
                "success": True,
                "topic": topic,
                "content": personalized,
                "next_topics": self._suggest_next_topics(user_id, topic),
                "interactive_elements": self._create_interactive_elements(topic)
            }
            
        except Exception as e:
            logger.error(f"Error getting education: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_user_context(self, user_id: int) -> Dict[str, Any]:
        """Get user context for personalization"""
        
        profile = self.db.query(UserProfile).filter(
            UserProfile.user_id == user_id
        ).first()
        
        goal = self.db.query(UserGoal).filter(
            UserGoal.user_id == user_id
        ).first()
        
        # Get recent education history
        recent_education = self.db.query(AgentInteraction).filter(
            and_(
                AgentInteraction.user_id == user_id,
                AgentInteraction.agent_type == "nutrition",
                AgentInteraction.interaction_type == "education",
                AgentInteraction.created_at >= datetime.utcnow() - timedelta(days=30)
            )
        ).all()
        
        recent_topics = [
            interaction.context_data.get("topic") 
            for interaction in recent_education 
            if interaction.context_data
        ]
        
        # Get performance metrics
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_meals = self.db.query(MealLog).filter(
            and_(
                MealLog.user_id == user_id,
                MealLog.planned_datetime >= week_ago
            )
        ).all()
        
        compliance_rate = 0
        if recent_meals:
            consumed = len([m for m in recent_meals if m.consumed_datetime])
            compliance_rate = (consumed / len(recent_meals)) * 100
        
        return {
            "user_id": user_id,
            "goal_type": goal.goal_type.value if goal else "general_health",
            "activity_level": profile.activity_level.value if profile and profile.activity_level else "sedentary",
            "recent_topics": recent_topics,
            "compliance_rate": compliance_rate,
            "experience_level": self._determine_experience_level(recent_topics)
        }
    
    def _select_relevant_topic(self, context: Dict[str, Any]) -> str:
        """Select most relevant topic for user"""
        
        goal_type = context.get("goal_type", "general_health")
        recent_topics = context.get("recent_topics", [])
        compliance_rate = context.get("compliance_rate", 0)
        experience_level = context.get("experience_level", "beginner")
        
        # Priority topics based on context
        if experience_level == "beginner":
            priority = ["basics.calories", "basics.protein", "basics.carbohydrates"]
        elif goal_type == "muscle_gain":
            priority = ["goal_specific.muscle_gain", "advanced.supplements", "basics.protein"]
        elif goal_type == "fat_loss":
            priority = ["goal_specific.fat_loss", "advanced.meal_timing", "special_topics.inflammation"]
        else:
            priority = ["basics.calories", "advanced.meal_timing", "special_topics.gut_health"]
        
        # Filter out recent topics
        available = [t for t in priority if t not in recent_topics[-3:]]
        
        if available:
            return available[0]
        
        # Fallback to random topic
        all_topics = []
        for category in self.education_library:
            for topic in self.education_library[category]:
                all_topics.append(f"{category}.{topic}")
        
        return random.choice(all_topics)
    
    def _get_topic_content(self, topic: str) -> Dict[str, Any]:
        """Get content for specific topic"""
        
        if "." in topic:
            category, subtopic = topic.split(".", 1)
            if category in self.education_library and subtopic in self.education_library[category]:
                return self.education_library[category][subtopic]
        
        # Fallback content
        return {
            "title": "Nutrition Basics",
            "content": "Understanding nutrition is key to achieving your health goals.",
            "tips": ["Focus on whole foods", "Stay consistent", "Track your progress"]
        }
    
    def _personalize_content(self, content: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Personalize content based on user context"""
        
        personalized = content.copy()
        
        # Add goal-specific emphasis
        goal_type = context.get("goal_type", "general_health")
        
        goal_emphasis = {
            "muscle_gain": "For muscle growth, pay special attention to protein timing and total intake.",
            "fat_loss": "For fat loss, focus on maintaining a moderate deficit while preserving muscle.",
            "endurance": "For endurance performance, carbohydrate timing is crucial.",
            "general_health": "For overall health, focus on variety and balance."
        }
        
        personalized["goal_emphasis"] = goal_emphasis.get(goal_type, "")
        
        # Add compliance-based encouragement
        compliance = context.get("compliance_rate", 0)
        
        if compliance > 80:
            personalized["encouragement"] = "You're doing great with consistency! Let's deepen your knowledge."
        elif compliance > 60:
            personalized["encouragement"] = "Good progress! Understanding these concepts will help improve adherence."
        else:
            personalized["encouragement"] = "Knowledge is power! Understanding nutrition will make healthy eating easier."
        
        return personalized
    
    def _suggest_next_topics(self, user_id: int, current_topic: str) -> List[str]:
        """Suggest related topics for continued learning"""
        
        related_topics = {
            "basics.calories": ["basics.protein", "basics.carbohydrates", "basics.fats"],
            "basics.protein": ["goal_specific.muscle_gain", "advanced.supplements"],
            "basics.carbohydrates": ["advanced.meal_timing", "special_topics.inflammation"],
            "basics.fats": ["special_topics.inflammation", "goal_specific.fat_loss"],
            "advanced.meal_timing": ["goal_specific.performance", "advanced.supplements"],
            "goal_specific.muscle_gain": ["advanced.supplements", "basics.protein"],
            "goal_specific.fat_loss": ["advanced.meal_timing", "special_topics.gut_health"]
        }
        
        suggestions = related_topics.get(current_topic, [])
        
        # Add variety
        if not suggestions:
            all_topics = []
            for category in self.education_library:
                for topic in self.education_library[category]:
                    full_topic = f"{category}.{topic}"
                    if full_topic != current_topic:
                        all_topics.append(full_topic)
            
            suggestions = random.sample(all_topics, min(3, len(all_topics)))
        
        return suggestions[:3]
    
    def _create_interactive_elements(self, topic: str) -> Dict[str, Any]:
        """Create interactive elements for engagement"""
        
        elements = {
            "quiz": [],
            "calculator": None,
            "checklist": [],
            "action_items": []
        }
        
        # Topic-specific elements
        if "calories" in topic:
            elements["calculator"] = {
                "type": "tdee_calculator",
                "description": "Calculate your daily calorie needs"
            }
            elements["action_items"] = [
                "Track your intake for 3 days",
                "Calculate your TDEE",
                "Set appropriate calorie target"
            ]
        
        elif "protein" in topic:
            elements["calculator"] = {
                "type": "protein_calculator",
                "description": "Calculate your protein requirements"
            }
            elements["checklist"] = [
                "Include protein in every meal",
                "Aim for 20-30g per meal",
                "Track protein for one week"
            ]
        
        elif "meal_timing" in topic:
            elements["action_items"] = [
                "Plan your meal schedule",
                "Try the suggested timing for one week",
                "Note energy levels at different times"
            ]
        
        return elements
    
    def _track_education_delivery(self, user_id: int, topic: str):
        """Track education content delivery"""
        
        try:
            interaction = AgentInteraction(
                user_id=user_id,
                agent_type="nutrition",
                interaction_type="education",
                input_text=topic,
                response_text=f"Delivered education on {topic}",
                context_data={"topic": topic, "timestamp": datetime.utcnow().isoformat()},
                created_at=datetime.utcnow()
            )
            
            self.db.add(interaction)
            self.db.commit()
            
        except Exception as e:
            logger.error(f"Error tracking education: {str(e)}")
    
    def _determine_experience_level(self, recent_topics: List[str]) -> str:
        """Determine user's experience level"""
        
        if not recent_topics:
            return "beginner"
        
        advanced_topics = sum(1 for t in recent_topics if "advanced" in t or "goal_specific" in t)
        
        if advanced_topics > 3:
            return "advanced"
        elif len(recent_topics) > 5:
            return "intermediate"
        else:
            return "beginner"
    
    def generate_daily_tip(self, user_id: int) -> Dict[str, str]:
        """Generate a daily nutrition tip"""
        
        context = self._get_user_context(user_id)
        goal_type = context.get("goal_type", "general_health")
        
        tips_by_goal = {
            "muscle_gain": [
                "Eat protein within 30 minutes post-workout for optimal recovery",
                "Don't skip carbs - they're essential for muscle growth",
                "Aim for a 300-500 calorie surplus for lean gains",
                "Sleep 7-9 hours for maximum growth hormone release"
            ],
            "fat_loss": [
                "Protein keeps you full longer - prioritize it",
                "Volume eating: Choose high-volume, low-calorie foods",
                "Track everything - small bites add up",
                "Stay patient - sustainable loss is 0.5-1kg per week"
            ],
            "general_health": [
                "Eat the rainbow - colorful foods mean diverse nutrients",
                "Hydrate before you feel thirsty",
                "Fiber is your friend - aim for 25-35g daily",
                "Listen to your hunger and fullness cues"
            ]
        }
        
        tips = tips_by_goal.get(goal_type, tips_by_goal["general_health"])
        daily_tip = random.choice(tips)
        
        return {
            "tip": daily_tip,
            "category": goal_type,
            "timestamp": datetime.utcnow().isoformat()
        }