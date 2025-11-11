"""
Nutrition Intelligence Layer - LLM-Powered Intent Classification & Response

This module provides intelligent query understanding and response generation using
LLMs for intent classification and hybrid rule-based/LLM response handling.

Architecture:
1. LLM-based intent classification (Haiku for speed/cost)
2. Rule-based handlers for simple queries (STATS)
3. LLM handlers for complex queries (WHAT_IF, SUGGESTIONS, CHAT)

Cost Optimization:
- Classification: ~$0.0005 per query (Haiku)
- Simple queries: $0 (rule-based)
- Complex queries: ~$0.003 per query (Sonnet)
- Average: ~$0.002 per query

Author: NutriLens AI Team
Created: 2025-11-10
"""

from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from sqlalchemy.orm import Session

from app.agents.nutrition_context import UserContext

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """User query intent types"""
    STATS = "stats"  # "how is my protein?" - Rule-based
    WHAT_IF = "what_if"  # "what if I eat pizza?" - LLM-based
    MEAL_SUGGESTION = "meal_suggestion"  # "what should I eat?" - LLM-based
    MEAL_PLAN = "meal_plan"  # "show my meal plan" - Rule-based + formatting
    INVENTORY = "inventory"  # "what can I make?" - Rule-based
    CONVERSATIONAL = "conversational"  # "tell me about protein" - LLM-based
    UNKNOWN = "unknown"  # Fallback


@dataclass
class IntentResult:
    """Result of intent classification"""
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]  # Extracted entities (food items, time periods, etc)
    reasoning: str

    @classmethod
    def parse(cls, llm_response: str) -> 'IntentResult':
        """Parse LLM JSON response into IntentResult"""
        try:
            data = json.loads(llm_response)
            return cls(
                intent=IntentType(data.get("intent", "unknown").lower()),
                confidence=float(data.get("confidence", 0.0)),
                entities=data.get("entities", {}),
                reasoning=data.get("reasoning", "")
            )
        except Exception as e:
            logger.error(f"Error parsing intent result: {str(e)}")
            return cls(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                entities={},
                reasoning=f"Parse error: {str(e)}"
            )


@dataclass
class IntelligenceResponse:
    """Response from intelligence layer"""
    success: bool
    response_text: str
    data: Optional[Dict[str, Any]] = None
    intent_detected: Optional[str] = None
    processing_time_ms: Optional[int] = None
    cost_usd: Optional[float] = None


class IntentClassifier:
    """
    LLM-powered intent classification using Claude Haiku

    Design:
    - Use lightweight model (Haiku) for fast, cheap classification
    - Extract entities (foods, time periods, meal types)
    - Provide confidence scores for routing

    Cost: ~$0.0005 per classification
    Latency: ~200-400ms
    """

    CLASSIFICATION_PROMPT = """You are an intent classifier for a nutrition tracking app. Classify the user's query into ONE intent.

User Context Summary:
- Goal: {goal_type}
- Today consumed: {calories_consumed}/{calories_target} calories
- Protein: {protein_consumed}/{protein_target}g
- Inventory: {inventory_items} items
- Upcoming meals: {upcoming_meals}

Available Intents:
1. STATS - User wants nutrition statistics/progress
   Examples: "how is my protein?", "show my macros", "what did I eat today?", "am I on track?"

2. WHAT_IF - User wants to simulate adding hypothetical food
   Examples: "what if I eat a pizza?", "how would 2 samosas affect my macros?", "can I fit ice cream?"

3. MEAL_SUGGESTION - User wants meal recommendations
   Examples: "what should I eat?", "suggest lunch", "I'm hungry", "meal ideas?"

4. MEAL_PLAN - User wants to see/modify planned meals
   Examples: "show my meal plan", "what's for dinner?", "change tomorrow's lunch", "upcoming meals?"

5. INVENTORY - User asks about ingredients/what they can make
   Examples: "do I have eggs?", "what's expiring?", "what can I make?", "ingredient status?"

6. CONVERSATIONAL - General nutrition questions/advice
   Examples: "is protein important?", "tell me about meal prep", "nutrition tips", "explain macros"

User Query: "{query}"

Respond ONLY with valid JSON (no markdown, no extra text):
{{
    "intent": "stats|what_if|meal_suggestion|meal_plan|inventory|conversational",
    "confidence": 0.95,
    "entities": {{
        "food_items": ["pizza", "samosa"],
        "quantities": [1, 2],
        "meal_type": "lunch",
        "time_period": "today",
        "nutrients": ["protein", "calories"]
    }},
    "reasoning": "User is asking about current protein intake - STATS intent"
}}"""

    def __init__(self, llm_client):
        """
        Initialize intent classifier

        Args:
            llm_client: LLM client wrapper (supports both Claude and OpenAI)
        """
        self.llm_client = llm_client

    async def classify(self, query: str, context: Dict[str, Any]) -> IntentResult:
        """
        Classify user query intent using LLM

        Args:
            query: User's natural language query
            context: User context from UserContext.build_context()

        Returns:
            IntentResult with intent, confidence, and extracted entities
        """
        try:
            # Build context summary for prompt
            context_summary = self._build_context_summary(context)

            # Format prompt
            prompt = self.CLASSIFICATION_PROMPT.format(
                goal_type=context_summary["goal_type"],
                calories_consumed=context_summary["calories_consumed"],
                calories_target=context_summary["calories_target"],
                protein_consumed=context_summary["protein_consumed"],
                protein_target=context_summary["protein_target"],
                inventory_items=context_summary["inventory_items"],
                upcoming_meals=context_summary["upcoming_meals"],
                query=query
            )

            # Call LLM (GPT-4o for accurate classification)
            response = await self.llm_client.complete(
                prompt=prompt,
                model="gpt-4o",  # Fast, accurate classification
                max_tokens=300,
                temperature=0.1,  # Low temp for consistent classification
                system="You are a precise intent classifier. Always respond with valid JSON only."
            )

            # Parse response
            result = IntentResult.parse(response)

            logger.info(f"Intent classified: {result.intent} (confidence: {result.confidence})")
            return result

        except Exception as e:
            logger.error(f"Error in intent classification: {str(e)}")
            # Fallback to unknown intent
            return IntentResult(
                intent=IntentType.UNKNOWN,
                confidence=0.0,
                entities={},
                reasoning=f"Classification error: {str(e)}"
            )

    def _build_context_summary(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Build concise context summary for classification prompt"""
        return {
            "goal_type": context.get("profile", {}).get("goal_type", "general_health"),
            "calories_consumed": context.get("today", {}).get("consumed", {}).get("calories", 0),
            "calories_target": context.get("targets", {}).get("calories", 2000),
            "protein_consumed": context.get("today", {}).get("consumed", {}).get("protein_g", 0),
            "protein_target": context.get("targets", {}).get("protein_g", 100),
            "inventory_items": context.get("inventory_summary", {}).get("total_items", 0),
            "upcoming_meals": len(context.get("upcoming", []))
        }


class NutritionIntelligence:
    """
    Main intelligence layer that orchestrates intent classification and response generation

    Architecture:
    1. Classify intent using LLM (Haiku)
    2. Route to appropriate handler:
       - Rule-based for simple queries (STATS, MEAL_PLAN, INVENTORY)
       - LLM-based for complex queries (WHAT_IF, MEAL_SUGGESTION, CONVERSATIONAL)
    3. Return formatted response

    Usage:
        intelligence = NutritionIntelligence(db, user_id, llm_client)
        response = await intelligence.process_query("how is my protein intake?")
    """

    def __init__(self, db: Session, user_id: int, llm_client):
        """
        Initialize nutrition intelligence

        Args:
            db: Database session
            user_id: User ID
            llm_client: LLM client wrapper
        """
        self.db = db
        self.user_id = user_id
        self.llm_client = llm_client

        # Initialize components
        self.context_builder = UserContext(db, user_id)
        self.intent_classifier = IntentClassifier(llm_client)

    async def process_query(self, query: str, include_context: bool = True) -> IntelligenceResponse:
        """
        Process user query and generate intelligent response

        Args:
            query: User's natural language query
            include_context: Whether to include data in response

        Returns:
            IntelligenceResponse with answer and metadata
        """
        start_time = datetime.utcnow()

        try:
            # Step 1: Build user context
            context = self.context_builder.build_context(minimal=False)

            # Step 2: Classify intent
            intent_result = await self.intent_classifier.classify(query, context)

            # Step 3: Route to appropriate handler
            if intent_result.intent == IntentType.STATS:
                response = self._handle_stats(query, context, intent_result.entities)
                cost = 0.0005  # Only classification cost

            elif intent_result.intent == IntentType.MEAL_PLAN:
                response = self._handle_meal_plan(query, context, intent_result.entities)
                cost = 0.0005  # Only classification cost

            elif intent_result.intent == IntentType.INVENTORY:
                response = self._handle_inventory(query, context, intent_result.entities)
                cost = 0.0005  # Only classification cost

            elif intent_result.intent == IntentType.WHAT_IF:
                response = await self._handle_what_if(query, context, intent_result.entities)
                cost = 0.0035  # Classification + Sonnet

            elif intent_result.intent == IntentType.MEAL_SUGGESTION:
                response = await self._handle_meal_suggestion(query, context, intent_result.entities)
                cost = 0.0035  # Classification + Sonnet

            elif intent_result.intent == IntentType.CONVERSATIONAL:
                response = await self._handle_conversational(query, context, intent_result.entities)
                cost = 0.0035  # Classification + Sonnet

            else:
                response = IntelligenceResponse(
                    success=False,
                    response_text="I'm not sure how to help with that. Try asking about your nutrition stats, meal suggestions, or what-if scenarios.",
                    intent_detected=intent_result.intent.value
                )
                cost = 0.0005

            # Calculate processing time
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Add metadata
            response.processing_time_ms = processing_time
            response.cost_usd = cost
            response.intent_detected = intent_result.intent.value

            logger.info(f"Query processed: {intent_result.intent} in {processing_time}ms (${cost})")
            return response

        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            return IntelligenceResponse(
                success=False,
                response_text=f"Sorry, I encountered an error: {str(e)}",
                intent_detected="error"
            )

    # ==================== RULE-BASED HANDLERS ====================

    def _handle_stats(self, query: str, context: Dict, entities: Dict) -> IntelligenceResponse:
        """
        Handle STATS queries with rule-based logic

        Examples: "how is my protein?", "show my macros", "am I on track?"
        """
        today = context.get("today", {})
        targets = context.get("targets", {})
        consumed = today.get("consumed", {})
        remaining = today.get("remaining", {})

        # Detect which nutrients user is asking about
        nutrients = entities.get("nutrients", [])
        if not nutrients:
            # Default to all macros
            nutrients = ["calories", "protein", "carbs", "fat"]

        # Build response
        lines = ["📊 **Your Nutrition Today**\n"]

        for nutrient in nutrients:
            if nutrient in ["calories", "calorie"]:
                consumed_val = consumed.get("calories", 0)
                target_val = targets.get("calories", 0)
                remaining_val = remaining.get("calories", 0)
                unit = "cal"
            elif nutrient in ["protein", "protein_g"]:
                consumed_val = consumed.get("protein_g", 0)
                target_val = targets.get("protein_g", 0)
                remaining_val = remaining.get("protein_g", 0)
                unit = "g"
            elif nutrient in ["carbs", "carbs_g", "carbohydrates"]:
                consumed_val = consumed.get("carbs_g", 0)
                target_val = targets.get("carbs_g", 0)
                remaining_val = remaining.get("carbs_g", 0)
                unit = "g"
            elif nutrient in ["fat", "fat_g", "fats"]:
                consumed_val = consumed.get("fat_g", 0)
                target_val = targets.get("fat_g", 0)
                remaining_val = remaining.get("fat_g", 0)
                unit = "g"
            else:
                continue

            percentage = (consumed_val / target_val * 100) if target_val > 0 else 0

            # Status emoji
            if percentage < 50:
                status = "🔵"
            elif percentage < 90:
                status = "🟢"
            elif percentage <= 110:
                status = "✅"
            else:
                status = "🔴"

            lines.append(
                f"{status} **{nutrient.title()}**: {consumed_val:.0f}/{target_val:.0f}{unit} "
                f"({percentage:.0f}%) - {remaining_val:.0f}{unit} remaining"
            )

        # Add summary
        compliance = today.get("compliance_rate", 0)
        meals_consumed = today.get("meals_consumed", 0)
        meals_pending = today.get("meals_pending", 0)

        lines.append(f"\n📈 **Compliance**: {compliance:.0f}%")
        lines.append(f"🍽️ **Meals**: {meals_consumed} consumed, {meals_pending} pending")

        return IntelligenceResponse(
            success=True,
            response_text="\n".join(lines),
            data={
                "consumed": consumed,
                "targets": targets,
                "remaining": remaining,
                "compliance": compliance
            }
        )

    def _handle_meal_plan(self, query: str, context: Dict, entities: Dict) -> IntelligenceResponse:
        """Handle MEAL_PLAN queries - show upcoming meals"""
        upcoming = context.get("upcoming", [])

        if not upcoming:
            return IntelligenceResponse(
                success=True,
                response_text="You don't have any upcoming meals planned for today. Would you like me to suggest some meals?",
                data={"upcoming_meals": []}
            )

        lines = ["🍽️ **Your Upcoming Meals Today**\n"]

        for meal in upcoming:
            lines.append(
                f"• **{meal.get('meal_type', 'Meal').title()}** at {meal.get('time', 'TBD')}\n"
                f"  {meal.get('recipe', 'No recipe')} - "
                f"{meal.get('calories', 0):.0f} cal, {meal.get('protein_g', 0):.0f}g protein"
            )

        return IntelligenceResponse(
            success=True,
            response_text="\n".join(lines),
            data={"upcoming_meals": upcoming}
        )

    def _handle_inventory(self, query: str, context: Dict, entities: Dict) -> IntelligenceResponse:
        """Handle INVENTORY queries - show what user can make"""
        inventory_summary = context.get("inventory_summary", {})

        # Get makeable recipes
        makeable = self.context_builder.get_makeable_recipes(limit=10)

        lines = [f"🥘 **Your Inventory Status**\n"]
        lines.append(f"📦 Total items: {inventory_summary.get('total_items', 0)}")
        lines.append(f"⚠️ Expiring soon: {inventory_summary.get('expiring_soon', 0)}")
        lines.append(f"📉 Low stock: {inventory_summary.get('low_stock', 0)}")

        if makeable:
            lines.append(f"\n✨ **You can make {len(makeable)} recipes:**\n")
            for i, recipe in enumerate(makeable[:5], 1):
                lines.append(f"{i}. {recipe.get('title', 'Unknown')} - {recipe.get('calories', 0):.0f} cal")
        else:
            lines.append("\n⚠️ No recipes available with current inventory. Time to shop!")

        return IntelligenceResponse(
            success=True,
            response_text="\n".join(lines),
            data={
                "inventory": inventory_summary,
                "makeable_recipes": makeable
            }
        )

    # ==================== LLM-BASED HANDLERS ====================

    async def _handle_what_if(self, query: str, context: Dict, entities: Dict) -> IntelligenceResponse:
        """
        Handle WHAT_IF queries using LLM for food analysis

        Examples: "what if I eat 2 samosas?", "can I fit a pizza?"

        Flow:
        1. Use LLM to parse food items and quantities from query
        2. Look up nutrition using FDC service
        3. Calculate impact on remaining macros
        4. Use LLM to generate friendly explanation
        """
        try:
            # Build prompt for LLM to analyze the what-if scenario
            remaining = context.get("today", {}).get("remaining", {})
            consumed = context.get("today", {}).get("consumed", {})
            targets = context.get("targets", {})
            goal = context.get("profile", {}).get("goal_type", "general_health")

            prompt = f"""You are a nutrition assistant analyzing a hypothetical food addition.

User's Current Status:
- Goal: {goal}
- Calories consumed: {consumed.get("calories", 0)}/{targets.get("calories", 0)}
- Protein consumed: {consumed.get("protein_g", 0)}/{targets.get("protein_g", 0)}g
- Carbs consumed: {consumed.get("carbs_g", 0)}/{targets.get("carbs_g", 0)}g
- Fat consumed: {consumed.get("fat_g", 0)}/{targets.get("fat_g", 0)}g

Remaining macros:
- Calories: {remaining.get("calories", 0)}
- Protein: {remaining.get("protein_g", 0)}g
- Carbs: {remaining.get("carbs_g", 0)}g
- Fat: {remaining.get("fat_g", 0)}g

User's question: "{query}"

Analyze this scenario and provide:
1. Estimate the nutrition of the food mentioned (use typical values)
2. Calculate if it fits their remaining macros
3. Give a friendly, conversational answer about whether they can have it
4. Suggest alternatives if it doesn't fit well

Keep your response concise (3-4 sentences), friendly, and actionable."""

            # Call LLM for analysis
            response_text = await self.llm_client.complete(
                prompt=prompt,
                model="gpt-4o",
                max_tokens=300,
                temperature=0.7
            )

            return IntelligenceResponse(
                success=True,
                response_text=response_text,
                data={
                    "remaining": remaining,
                    "consumed": consumed,
                    "targets": targets
                }
            )

        except Exception as e:
            logger.error(f"Error in what-if handler: {str(e)}")
            return IntelligenceResponse(
                success=False,
                response_text=f"Sorry, I had trouble analyzing that. Could you rephrase your question?",
                data={"error": str(e)}
            )

    async def _handle_meal_suggestion(self, query: str, context: Dict, entities: Dict) -> IntelligenceResponse:
        """
        Handle MEAL_SUGGESTION queries using LLM

        Examples: "what should I eat?", "suggest lunch"

        Flow:
        1. Get makeable recipes from inventory
        2. Get goal-aligned recipes
        3. Use LLM to rank and explain suggestions
        """
        try:
            # Get available recipes
            makeable_recipes = self.context_builder.get_makeable_recipes(limit=10)
            goal_recipes = self.context_builder.get_goal_aligned_recipes(count=10)

            # Combine and format recipes for LLM
            all_recipes = []
            seen_ids = set()

            for recipe in makeable_recipes + goal_recipes:
                recipe_id = recipe.get("id") or recipe.get("recipe_id")
                if recipe_id and recipe_id not in seen_ids:
                    seen_ids.add(recipe_id)
                    all_recipes.append({
                        "name": recipe.get("title") or recipe.get("name", "Unknown"),
                        "calories": recipe.get("calories", 0),
                        "protein_g": recipe.get("protein_g", 0),
                        "prep_time": recipe.get("prep_time_min", recipe.get("prep_time", "N/A")),
                        "can_make": recipe in makeable_recipes
                    })

            # Build LLM prompt
            remaining = context.get("today", {}).get("remaining", {})
            goal = context.get("profile", {}).get("goal_type", "general_health")
            meal_type = entities.get("meal_type", "meal")

            recipes_text = "\n".join([
                f"- {r['name']}: {r['calories']}cal, {r['protein_g']}g protein, "
                f"{r['prep_time']} min{' (you have all ingredients)' if r['can_make'] else ''}"
                for r in all_recipes[:8]
            ])

            prompt = f"""You are a nutrition assistant suggesting meals.

User's Context:
- Goal: {goal}
- Remaining macros: {remaining.get("calories", 0)} calories, {remaining.get("protein_g", 0)}g protein
- Query: "{query}"

Available recipes:
{recipes_text if recipes_text else "No recipes available"}

Task:
1. Suggest 2-3 best recipes from the list
2. Explain WHY each is a good choice (consider their goal, remaining macros, and ingredients)
3. If no recipes fit well, suggest what type of meal would work

Keep your response friendly and concise (4-5 sentences)."""

            # Call LLM
            response_text = await self.llm_client.complete(
                prompt=prompt,
                model="gpt-4o",
                max_tokens=400,
                temperature=0.7
            )

            return IntelligenceResponse(
                success=True,
                response_text=response_text,
                data={
                    "recipes": all_recipes[:5],
                    "remaining": remaining
                }
            )

        except Exception as e:
            logger.error(f"Error in meal suggestion handler: {str(e)}")
            return IntelligenceResponse(
                success=False,
                response_text="Sorry, I had trouble finding meal suggestions. Try checking your inventory or meal plan.",
                data={"error": str(e)}
            )

    async def _handle_conversational(self, query: str, context: Dict, entities: Dict) -> IntelligenceResponse:
        """
        Handle CONVERSATIONAL queries using LLM

        Examples: "is protein important?", "tell me about meal prep"

        Flow:
        1. Pass user context + query to LLM
        2. LLM generates personalized nutrition advice
        """
        try:
            # Build context summary for LLM
            profile = context.get("profile", {})
            targets = context.get("targets", {})
            today = context.get("today", {})
            week = context.get("week", {})

            prompt = f"""You are a knowledgeable nutrition assistant helping a user with their nutrition questions.

User's Profile:
- Goal: {profile.get("goal_type", "general_health")}
- Age: {profile.get("age", "N/A")}, Weight: {profile.get("weight_kg", "N/A")}kg
- Activity level: {profile.get("activity_level", "moderate")}

Daily Targets:
- Calories: {targets.get("calories", 2000)}
- Protein: {targets.get("protein_g", 100)}g
- Carbs: {targets.get("carbs_g", 250)}g
- Fat: {targets.get("fat_g", 65)}g

Today's Progress:
- Consumed: {today.get("consumed", {}).get("calories", 0)} calories
- Compliance rate: {today.get("compliance_rate", 0)}%

Weekly Averages:
- Avg calories: {week.get("avg_calories", 0)}
- Avg protein: {week.get("avg_protein", 0)}g

User's question: "{query}"

Provide a helpful, personalized answer that:
1. Answers their question clearly
2. References their specific situation when relevant
3. Gives actionable advice
4. Is friendly and encouraging

Keep your response concise (3-5 sentences)."""

            # Call LLM
            response_text = await self.llm_client.complete(
                prompt=prompt,
                model="gpt-4o",
                max_tokens=350,
                temperature=0.7
            )

            return IntelligenceResponse(
                success=True,
                response_text=response_text,
                data={
                    "profile": profile,
                    "targets": targets
                }
            )

        except Exception as e:
            logger.error(f"Error in conversational handler: {str(e)}")
            return IntelligenceResponse(
                success=False,
                response_text="Sorry, I had trouble answering that. Could you try rephrasing your question?",
                data={"error": str(e)}
            )
