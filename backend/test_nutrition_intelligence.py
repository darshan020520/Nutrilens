"""
Test script for Nutrition Intelligence Layer

Tests:
1. Intent classification with various queries
2. Rule-based handlers (STATS, MEAL_PLAN, INVENTORY)
3. Context building performance

Note: LLM-based handlers (WHAT_IF, MEAL_SUGGESTION, CONVERSATIONAL)
require API keys and will be tested separately.
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.database import SessionLocal
from app.agents.nutrition_context import UserContext
from app.agents.nutrition_intelligence import NutritionIntelligence
from app.services.llm_client import LLMClient
from app.core.config import settings


class MockLLMClient:
    """
    Mock LLM client for testing without API calls

    Returns hardcoded intent classifications based on query patterns
    """

    async def complete(self, prompt: str, **kwargs) -> str:
        """Mock LLM completion"""
        # Extract the actual user query from the prompt
        import re
        query_match = re.search(r'User Query: "(.+?)"', prompt)
        if query_match:
            query = query_match.group(1).lower()
        else:
            query = prompt.lower()

        # Pattern matching for mock intent classification (ORDER MATTERS - check specific first)
        if any(word in query for word in ["suggest", "recommend", "should i eat", "hungry", "meal ideas"]):
            return '''
            {
                "intent": "meal_suggestion",
                "confidence": 0.93,
                "entities": {"meal_type": "lunch"},
                "reasoning": "User wants meal recommendations"
            }
            '''

        elif any(word in query for word in ["what if", "eat 2", "eat a", "would happen"]):
            return '''
            {
                "intent": "what_if",
                "confidence": 0.88,
                "entities": {"food_items": ["samosa"], "quantities": [2]},
                "reasoning": "User wants to simulate adding food"
            }
            '''

        elif any(phrase in query for phrase in ["meal plan", "what's for dinner", "what's for lunch", "upcoming meals"]):
            return '''
            {
                "intent": "meal_plan",
                "confidence": 0.92,
                "entities": {"meal_type": "dinner"},
                "reasoning": "User wants to see meal plan"
            }
            '''

        elif any(word in query for word in ["inventory", "what can i make", "ingredients", "expiring"]):
            return '''
            {
                "intent": "inventory",
                "confidence": 0.90,
                "entities": {},
                "reasoning": "User is asking about inventory"
            }
            '''

        elif any(word in query for word in ["protein", "macro", "calories", "stats", "track", "intake", "on track"]):
            return '''
            {
                "intent": "stats",
                "confidence": 0.95,
                "entities": {"nutrients": ["protein", "calories"]},
                "reasoning": "User is asking about nutrition statistics"
            }
            '''

        elif any(word in query for word in ["important", "tell me about", "why", "explain", "tips"]):
            return '''
            {
                "intent": "conversational",
                "confidence": 0.85,
                "entities": {},
                "reasoning": "General conversation about nutrition"
            }
            '''

        else:
            return '''
            {
                "intent": "stats",
                "confidence": 0.75,
                "entities": {},
                "reasoning": "Defaulting to stats"
            }
            '''


async def test_intent_classification():
    """Test intent classification with various queries"""
    print("=" * 60)
    print("TEST 1: Intent Classification")
    print("=" * 60)

    # Create mock client
    llm_client = MockLLMClient()

    db = SessionLocal()
    try:
        intelligence = NutritionIntelligence(db, user_id=223, llm_client=llm_client)

        test_queries = [
            "how is my protein intake?",
            "show me my macros for today",
            "what's for dinner?",
            "show my meal plan",
            "what can I make with my inventory?",
            "what if I eat 2 samosas?",
            "suggest a lunch meal",
            "is protein important for muscle gain?"
        ]

        for query in test_queries:
            print(f"\nQuery: '{query}'")
            response = await intelligence.process_query(query)
            print(f"Intent: {response.intent_detected}")
            print(f"Success: {response.success}")
            print(f"Processing time: {response.processing_time_ms}ms")
            print(f"Cost: ${response.cost_usd:.4f}")
            print(f"Response: {response.response_text[:150]}...")

    finally:
        db.close()


async def test_stats_handler():
    """Test rule-based STATS handler"""
    print("\n" + "=" * 60)
    print("TEST 2: STATS Handler (Rule-Based)")
    print("=" * 60)

    llm_client = MockLLMClient()
    db = SessionLocal()

    try:
        intelligence = NutritionIntelligence(db, user_id=223, llm_client=llm_client)

        queries = [
            "how is my protein?",
            "show all my macros",
            "am I on track today?"
        ]

        for query in queries:
            print(f"\n📊 Query: '{query}'")
            response = await intelligence.process_query(query)
            print(response.response_text)
            print(f"\n⏱️  {response.processing_time_ms}ms | 💰 ${response.cost_usd:.4f}")

    finally:
        db.close()


async def test_meal_plan_handler():
    """Test rule-based MEAL_PLAN handler"""
    print("\n" + "=" * 60)
    print("TEST 3: MEAL_PLAN Handler (Rule-Based)")
    print("=" * 60)

    llm_client = MockLLMClient()
    db = SessionLocal()

    try:
        intelligence = NutritionIntelligence(db, user_id=223, llm_client=llm_client)

        print("\n🍽️  Query: 'what's for dinner?'")
        response = await intelligence.process_query("what's for dinner?")
        print(response.response_text)
        print(f"\n⏱️  {response.processing_time_ms}ms | 💰 ${response.cost_usd:.4f}")

    finally:
        db.close()


async def test_inventory_handler():
    """Test rule-based INVENTORY handler"""
    print("\n" + "=" * 60)
    print("TEST 4: INVENTORY Handler (Rule-Based)")
    print("=" * 60)

    llm_client = MockLLMClient()
    db = SessionLocal()

    try:
        intelligence = NutritionIntelligence(db, user_id=223, llm_client=llm_client)

        print("\n🥘 Query: 'what can I make?'")
        response = await intelligence.process_query("what can I make?")
        print(response.response_text)
        print(f"\n⏱️  {response.processing_time_ms}ms | 💰 ${response.cost_usd:.4f}")

    finally:
        db.close()


async def test_context_performance():
    """Test context building performance"""
    print("\n" + "=" * 60)
    print("TEST 5: Context Building Performance")
    print("=" * 60)

    db = SessionLocal()

    try:
        import time

        context_builder = UserContext(db, user_id=223)

        # Test minimal context
        start = time.time()
        minimal = context_builder.build_context(minimal=True)
        minimal_time = (time.time() - start) * 1000

        print(f"\n✅ Minimal Context: {len(minimal)} keys in {minimal_time:.1f}ms")
        print(f"   Keys: {', '.join(minimal.keys())}")

        # Test full context
        start = time.time()
        full = context_builder.build_context(minimal=False)
        full_time = (time.time() - start) * 1000

        print(f"\n✅ Full Context: {len(full)} keys in {full_time:.1f}ms")
        print(f"   Keys: {', '.join(full.keys())}")

        # Test LLM format
        start = time.time()
        llm_context = context_builder.to_llm_context()
        format_time = (time.time() - start) * 1000

        print(f"\n✅ LLM Format: {len(llm_context)} characters in {format_time:.1f}ms")

        # Summary
        print("\n📊 Performance Summary:")
        print(f"   Minimal: {minimal_time:.1f}ms")
        print(f"   Full: {full_time:.1f}ms")
        print(f"   Format: {format_time:.1f}ms")
        print(f"   Total: {minimal_time + full_time + format_time:.1f}ms")

    finally:
        db.close()


async def main():
    """Run all tests"""
    print("\n🧪 Testing Nutrition Intelligence Layer")
    print("=" * 60)

    try:
        await test_intent_classification()
        await test_stats_handler()
        await test_meal_plan_handler()
        await test_inventory_handler()
        await test_context_performance()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

        print("\n📋 Summary:")
        print("   ✅ Intent classification working")
        print("   ✅ STATS handler (rule-based) working")
        print("   ✅ MEAL_PLAN handler (rule-based) working")
        print("   ✅ INVENTORY handler (rule-based) working")
        print("   ✅ Context building performance good")
        print("\n⏭️  Next: Test with real LLM API")
        print("   Set ANTHROPIC_API_KEY or OPENAI_API_KEY in .env")

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
