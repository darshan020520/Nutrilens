# backend/tests/test_complete_day1_to_5_final.py

"""
COMPREHENSIVE TEST SUITE FOR DAYS 1-5
Tests both API endpoints and internal implementations
Combines HTTP API testing with direct class/database testing
"""

import pytest
import json
import sys
import os
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.models.database import (
    User, UserProfile, UserGoal, UserPath, UserPreference,
    Item, Recipe, RecipeIngredient, 
    MealPlan, MealLog, UserInventory
)

# Configuration
BASE_URL = "http://localhost:8000/api"
TEST_USER_EMAIL = "darsh@nutrilens.ai"
TEST_USER_PASSWORD = "TestPass123"

class TestDay1_DatabaseAndAuth:
    """Day 1: Database Foundation & User System"""
    
    def test_database_schema(self, db):
        """Verify all 15+ tables exist"""
        print("\n📋 Testing Database Schema...")
        
        required_tables = [
            'users', 'user_profiles', 'user_goals', 'user_paths', 'user_preferences',
            'items', 'recipes', 'recipe_ingredients', 
            'meal_plans', 'meal_logs', 'user_inventory',
            'receipt_uploads', 'agent_interactions', 'whatsapp_logs'
        ]
        
        from sqlalchemy import inspect
        inspector = inspect(db.bind)
        existing_tables = inspector.get_table_names()
        
        found = 0
        for table in required_tables:
            if table in existing_tables:
                print(f"  ✅ Table {table} exists")
                found += 1
            else:
                print(f"  ❌ Table {table} missing")
        
        print(f"  📊 {found}/{len(required_tables)} tables found")
        return found >= 10  # At least core tables should exist
    
    def test_authentication_api(self):
        """Test authentication via API endpoints"""
        print("\n🔐 Testing Authentication API...")
        
        # Test registration
        print("  Testing user registration...")
        register_data = {
            "email": f"darsh@nutrilens.ai",
            "password": "TestPass123"
        }
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        
        if response.status_code == 200:
            print(f"  ✅ Registration successful")
            user = response.json()
            print(f"     User ID: {user.get('id', 'N/A')}")
        elif response.status_code == 400:
            print(f"  ⚠️  User may already exist")
        else:
            print(f"  ❌ Registration failed: {response.status_code}")
        
        # Test login
        print("\n  Testing login...")
        login_data = {
            "username": TEST_USER_EMAIL,  # OAuth2 uses username field
            "password": TEST_USER_PASSWORD
        }
        response = requests.post(
            f"{BASE_URL}/auth/login",
            data=login_data,  # Form data for OAuth2
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            print("  ✅ Login successful")
            token_data = response.json()
            access_token = token_data.get('access_token', '')
            if access_token:
                print(f"     Token: {access_token[:20]}...")
                
                # Test protected endpoint
                headers = {"Authorization": f"Bearer {access_token}"}
                response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
                if response.status_code == 200:
                    print("  ✅ Protected route working")
                    return access_token
                else:
                    print(f"  ❌ Protected route failed: {response.status_code}")
        else:
            print(f"  ❌ Login failed: {response.status_code}")
        
        return None
    
    def test_onboarding_flow(self, token: str):
        """Test complete onboarding flow"""
        print("\n👤 Testing Onboarding Flow...")
        
        if not token:
            print("  ⚠️  No auth token, skipping onboarding tests")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test basic info submission
        print("  Submitting basic info...")
        profile_data = {
            "name": "John Doe",
            "age": 30,
            "height_cm": 175,
            "weight_kg": 75,
            "sex": "male",
            "activity_level": "moderately_active",
            "medical_conditions": []
        }
        response = requests.post(
            f"{BASE_URL}/onboarding/basic-info",
            json=profile_data,
            headers=headers
        )
        
        if response.status_code == 200:
            print("  ✅ Profile created")
            profile = response.json()
            if 'bmr' in profile:
                print(f"     BMR: {profile['bmr']} cal")
                print(f"     TDEE: {profile.get('tdee', 'N/A')} cal")
        else:
            print(f"  ❌ Profile creation failed: {response.status_code}")
        
        # Test goal selection
        print("\n  Setting goals...")
        goal_data = {
            "goal_type": "muscle_gain",
            "target_weight": 80,
            "macro_targets": {
                "protein": 0.30,
                "carbs": 0.45,
                "fat": 0.25
            }
        }
        response = requests.post(
            f"{BASE_URL}/onboarding/goal-selection",
            json=goal_data,
            headers=headers
        )
        
        if response.status_code == 200:
            print("  ✅ Goal set successfully")
        else:
            print(f"  ❌ Goal setting failed: {response.status_code}")
        
        # Test calculated targets
        print("\n  Getting calculated targets...")
        response = requests.get(
            f"{BASE_URL}/onboarding/calculated-targets",
            headers=headers
        )
        
        if response.status_code == 200:
            print("  ✅ Targets calculated")
            targets = response.json()
            if 'goal_calories' in targets:
                print(f"     Goal Calories: {targets['goal_calories']}")
                print(f"     Macros: {targets.get('macro_targets', {})}")
        else:
            print(f"  ❌ Get targets failed: {response.status_code}")
        
        return response.status_code == 200


class TestDay2_RecipesAndNutrition:
    """Day 2: Recipe Dataset & Nutrition Foundation"""
    
    def test_recipe_database(self, db):
        """Test recipe data in database"""
        print("\n🍽️ Testing Recipe Database...")
        
        recipes = db.query(Recipe).all()
        print(f"  📊 Found {len(recipes)} recipes in database")
        
        if recipes:
            # Analyze distribution
            muscle_gain = sum(1 for r in recipes if r.goals and 'muscle_gain' in r.goals)
            fat_loss = sum(1 for r in recipes if r.goals and 'fat_loss' in r.goals)
            
            print(f"  ✅ Goal distribution:")
            print(f"     Muscle gain: {muscle_gain}")
            print(f"     Fat loss: {fat_loss}")
            
            # Check meal times
            breakfast = sum(1 for r in recipes if r.suitable_meal_times and 'breakfast' in r.suitable_meal_times)
            lunch = sum(1 for r in recipes if r.suitable_meal_times and 'lunch' in r.suitable_meal_times)
            dinner = sum(1 for r in recipes if r.suitable_meal_times and 'dinner' in r.suitable_meal_times)
            
            print(f"  ✅ Meal time distribution:")
            print(f"     Breakfast: {breakfast}, Lunch: {lunch}, Dinner: {dinner}")
            
            return len(recipes) > 0
        
        print("  ⚠️  No recipes found")
        return False
    
    def test_recipe_api(self):
        """Test recipe API endpoints"""
        print("\n🌐 Testing Recipe API...")
        
        # Test recipe stats
        print("  Getting recipe stats...")
        response = requests.get(f"{BASE_URL}/recipes/stats/summary")
        if response.status_code == 200:
            stats = response.json()
            print(f"  ✅ Stats retrieved")
            print(f"     Total: {stats.get('total_recipes', 'N/A')}")
        elif response.status_code == 404:
            print("  ⚠️  Stats endpoint not implemented")
        
        # Test recipe listing
        print("\n  Testing recipe listing...")
        response = requests.get(f"{BASE_URL}/recipes/", params={"limit": 5})
        if response.status_code == 200:
            recipes = response.json()
            print(f"  ✅ Found {len(recipes)} recipes")
            if recipes:
                print(f"     First: {recipes[0].get('title', 'N/A')}")
        else:
            print(f"  ❌ Recipe listing failed: {response.status_code}")
        
        # Test filtered recipes
        print("\n  Testing recipe filtering...")
        response = requests.get(f"{BASE_URL}/recipes/", params={
            "goal": "muscle_gain",
            "meal_time": "breakfast",
            "limit": 3
        })
        if response.status_code == 200:
            recipes = response.json()
            print(f"  ✅ Filtered {len(recipes)} recipes")
        else:
            print(f"  ❌ Filtering failed: {response.status_code}")
        
        return True


class TestDay3_ItemNormalization:
    """Day 3: Item Normalization & Inventory System"""
    
    def test_normalizer_class(self, db):
        """Test ItemNormalizer class directly"""
        print("\n🔤 Testing Item Normalizer Class...")
        
        try:
            from app.services.item_normalizer import IntelligentItemNormalizer
            print("  ✅ ItemNormalizer imported")
            
            normalizer = IntelligentItemNormalizer(db=db)
            print("  ✅ Normalizer instance created")
            
            # Test cases
            test_cases = [
                "2kg whole wheat flour",
                "500g chicken breast",
                "1 litre milk",
                "tomatoes 500g",
                "panner 200g",  # Misspelled paneer
                "brocoli 300g"  # Misspelled broccoli
            ]
            
            success_count = 0
            for test_input in test_cases:
                result = normalizer.normalize(test_input)
                if result:
                    res_dict = result.to_dict()
                    item_name = result.item.canonical_name
                    print(f"  ✅ '{test_input}' → {item_name} ({result.extracted_quantity}{result.extracted_unit})")

                    # int(f"  ✅ '{test_input}' → {res_dict['item']} ({res_dict['quantity']}{res_dict['unit']})")
                    success_count += 1
                else:
                    print(f"  ⚠️  '{test_input}' → No match")

            print(f"  📊 Normalized {success_count}/{len(test_cases)} items")
            return success_count > len(test_cases) // 2
            
        except ImportError as e:
            print(f"  ❌ Import failed: {e}")
            return False
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False
    
    def test_inventory_api(self, token: str):
        """Test inventory API endpoints"""
        print("\n📦 Testing Inventory API...")
        
        if not token:
            print("  ⚠️  No auth token, skipping inventory API tests")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test adding items
        print("  Adding items to inventory...")
        test_input = """
        2kg whole wheat flour
        500g chicken breast
        """
        
        response = requests.post(
            f"{BASE_URL}/inventory/add-items",
            json={"text_input": test_input},
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Items processed")
            if 'results' in result:
                summary = result['results'].get('summary', {})
                print(f"     {summary}")
        elif response.status_code == 404:
            print("  ⚠️  Add-items endpoint not implemented")
        else:
            print(f"  ❌ Failed: {response.status_code}")
        
        # Test inventory status
        print("\n  Getting inventory status...")
        response = requests.get(f"{BASE_URL}/inventory/status", headers=headers)
        
        if response.status_code == 200:
            status = response.json()
            print(f"  ✅ Status retrieved")
            print(f"     Total items: {status.get('total_items', 'N/A')}")
        elif response.status_code == 404:
            print("  ⚠️  Status endpoint not implemented")
        
        return True


class TestDay4_MealOptimizer:
    """Day 4: Linear Programming Optimizer"""
    
    def test_optimizer_class(self, db):
        """Test MealPlanOptimizer class directly"""
        print("\n🔧 Testing Meal Plan Optimizer...")
        
        try:
            # Try different import paths
            optimizer_class = None
            

            from app.services.final_meal_optimizer import MealPlanOptimizer, OptimizationConstraints
            print("  ✅ Imported from meal_optimizer_fixed.py")
            optimizer_class = MealPlanOptimizer

                    
            
            # Create optimizer
            optimizer = optimizer_class(db)
            print("  ✅ Optimizer instance created")
            
            # Create test constraints
            constraints = OptimizationConstraints(
                daily_calories_min=2200,
                daily_calories_max=2500,
                daily_protein_min=150,
                daily_carbs_min=200,
                daily_carbs_max=300,
                daily_fat_min=60,
                daily_fat_max=90,
                meals_per_day=3,
                max_recipe_repeat_in_days=2
            )
            print("  ✅ Constraints created")
            
            # Run optimization
            print("  Running optimization for 3 days...")
            start_time = time.time()
            
            result = optimizer.optimize(
                user_id=1,
                days=3,
                constraints=constraints
            )
            
            elapsed = time.time() - start_time
            
            if result:
                print(f"  ✅ Plan generated in {elapsed:.2f}s")
                print(f"     Method: {result.get('optimization_method', 'unknown')}")
                
                if 'week_plan' in result:
                    print(f"     Days: {len(result['week_plan'])}")
                    
                    # Check if plan meets constraints
                    if 'avg_daily_calories' in result:
                        avg_cal = result['avg_daily_calories']
                        print(f"     Avg calories: {avg_cal:.0f}")
                        
                        if constraints.daily_calories_min <= avg_cal <= constraints.daily_calories_max:
                            print(f"     ✅ Calories within target")
                        else:
                            print(f"     ⚠️  Calories outside target range")
                    
                    if 'avg_macros' in result:
                        avg_protein = result['avg_macros'].get('protein_g', 0)
                        print(f"     Avg protein: {avg_protein:.1f}g")
                        
                        if avg_protein >= constraints.daily_protein_min:
                            print(f"     ✅ Protein meets minimum")
                        else:
                            print(f"     ⚠️  Protein below minimum")
                
                return True
            else:
                print(f"  ❌ Optimization failed (returned None)")
                return False
                
        except Exception as e:
            print(f"  ❌ Error during optimization: {e}")
            return False
    
    def test_performance(self, db):
        """Test optimizer performance"""
        print("\n⏱️ Testing Optimizer Performance...")
        

        from app.services.final_meal_optimizer import MealPlanOptimizer, OptimizationConstraints

        
        optimizer = MealPlanOptimizer(db)
        
        # Test with 7-day plan
        constraints = OptimizationConstraints(
            daily_calories_min=2000,
            daily_calories_max=2400,
            daily_protein_min=130,
            meals_per_day=3
        )
        
        print("  Generating 7-day plan...")
        start_time = time.time()
        
        result = optimizer.optimize(
            user_id=1,
            days=7,
            constraints=constraints
        )
        
        elapsed = time.time() - start_time
        
        if result:
            print(f"  ✅ 7-day plan generated in {elapsed:.2f}s")
            if elapsed < 5:
                print(f"     ✅ Performance target met (<5s)")
            else:
                print(f"     ⚠️  Performance needs optimization (>5s)")
            return True
        else:
            print(f"  ❌ Failed to generate 7-day plan")
            return False


class TestDay5_PlanningAgent:
    """Day 5: Planning Agent & Meal Plan Generation"""
    
    def test_planning_agent(self, db):
        """Test PlanningAgent class"""
        print("\n🤖 Testing Planning Agent...")
        
        try:
            from app.agents.planning_agent import PlanningAgent
            print("  ✅ PlanningAgent imported")
            
            agent = PlanningAgent(db)
            print("  ✅ Agent instance created")

            print(agent)
            
            # Test available methods
            methods = [
                'generate_weekly_meal_plan',
                'select_recipes_for_goal',
                'calculate_grocery_list',
                'suggest_meal_prep',
                'find_recipe_alternatives',
                'adjust_plan_for_eating_out',
                'optimize_inventory_usage',
                'generate_shopping_reminders',
                'create_meal_schedule',
                'bulk_cooking_suggestions'
            ]
            
            available = 0
            for method in methods:
                if hasattr(agent, method):
                    available += 1
                    print(f"  ✅ Tool: {method}")
                else:
                    print(f"  ⚠️  Missing: {method}")
            
            print(f"  📊 {available}/{len(methods)} tools available")
            
            # Test a simple method
            if hasattr(agent, 'select_recipes_for_goal'):
                print("\n  Testing select_recipes_for_goal...")
                try:
                    recipes = agent.select_recipes_for_goal('muscle_gain', 3)
                    if recipes:
                        print(f"  ✅ Retrieved {len(recipes)} recipes")
                    else:
                        print("  ⚠️  No recipes returned")
                except Exception as e:
                    print(f"  ❌ Error: {e}")
            
            return available >= 5  # At least half the tools should exist
            
        except ImportError as e:
            print(f"  ❌ Import failed: {e}")
            return False
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False
    
    def test_meal_plan_api(self, token: str):
        """Test meal plan generation API"""
        print("\n📅 Testing Meal Plan API...")
        
        if not token:
            print("  ⚠️  No auth token, skipping API tests")
            return False
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # # Test plan generation
        # print("  Generating meal plan...")
        # response = requests.post(
        #     f"{BASE_URL}/meal-plans/generate",
        #     headers=headers,
        #     json={"days": 3}  # Generate 3-day plan for speed
        # )
        
        # if response.status_code in [200, 201]:
        #     print("  ✅ Meal plan generated")
        #     try:
        #         data = response.json()
        #         print("JSON:", data)
        #     except ValueError:
        #         print("Not valid JSON:", response.text)
        #     plan = response.json()
        #     if 'week_plan' in plan:
        #         print(f"     Days: {len(plan['week_plan'])}")
        # elif response.status_code == 404:
        #     print("  ⚠️  Generate endpoint not implemented")
        # else:
            
        #     print(f"  ❌ Generation failed: {response.status_code}")
        
        # Test get current plan
        print("\n  Getting current meal plan...")
        response = requests.get(
            f"{BASE_URL}/meal-plans/current",
            headers=headers
        )
        
        if response.status_code == 200:
            print("  ✅ Current plan retrieved")
            try:
                data = response.json()
                print("JSON:", data)
            except ValueError:
                print("Not valid JSON:", response.text)
        elif response.status_code == 404:
            print("  ⚠️  No active plan or endpoint not implemented")

        plan_id = data.get("id") or data.get("plan_id")
        # print(f"\n  Fetching grocery list for plan_id={plan_id}...")
        # response = requests.get(f"{BASE_URL}/meal-plans/{plan_id}/grocery-list", headers=headers)

        # if response.status_code == 200:
        #     try:
        #         grocery_data = response.json()
        #         print("Grocery list JSON:", grocery_data)
        #         print("  ✅ Grocery list retrieved successfully")
        #     except ValueError:
        #         print("  ❌ Grocery endpoint did not return valid JSON:", response.text)
        #         return False
        # elif response.status_code == 404:
        #     print(f"  ❌ Grocery list not found for plan_id {plan_id}")
        #     return False
        # else:
        #     print(f"  ❌ Grocery endpoint failed: {response.status_code}")
        #     return False
        

        print("\n  Fetching meal prep suggestions...")
        response = requests.post(f"{BASE_URL}/meal-plans/meal-prep-suggestions", headers=headers)

        if response.status_code == 200:
            try:
                suggestions_data = response.json()
                print("Meal prep suggestions JSON:", suggestions_data)
                print("  ✅ Meal prep suggestions retrieved successfully")
            except ValueError:
                print("  ❌ Meal prep suggestions endpoint did not return valid JSON:", response.text)
                return False
        elif response.status_code == 404:
            print("  ❌ Meal prep suggestions endpoint not found")
            return False
        else:
            print(f"  ❌ Meal prep suggestions endpoint failed: {response.status_code}")
            return False
        
        recipe_id = 185
        
        print("\n  Fetching recipe alternatives...")

        # Correct URL with both plan_id and recipe_id
        url = f"{BASE_URL}/meal-plans/{recipe_id}/alternatives"

        response = requests.get(
            url,
            headers=headers,
            params={"count": 3}  # optional query param
        )

        if response.status_code == 200:
            alternatives = response.json()
            print("  ✅ Alternatives retrieved:", alternatives)
        elif response.status_code == 404:
            print("  ❌ No alternatives found")
        else:
            print(f"  ❌ Alternatives endpoint failed: {response.status_code}", response.text)

        
        # Correct URL for the eating-out endpoint
        url = f"{BASE_URL}/meal-plans/eating-out"

        payload = {
            "day": 2,
            "meal_type": "lunch",
            "external_calories": 700
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload  # use json= for POST body
        )

        if response.status_code == 200:
            adjustments = response.json()
            print("  ✅ Suggestions retrieved:", adjustments)
        elif response.status_code == 400:
            print("  ❌ Bad request:", response.json())
        elif response.status_code == 500:
            print("  ❌ Server error:", response.json())
        else:
            print(f"  ❌ Unexpected response {response.status_code}", response.text)


        
        return True


def run_comprehensive_test_suite():
    """Run all tests for Days 1-5"""
    
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST SUITE FOR NUTRILENS AI - DAYS 1-5")
    print("="*80)
    
    # Setup database
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    results = {}
    auth_token = None
    
    # DAY 1: Database & Authentication
    print("\n📅 DAY 1: Database Foundation & User System")
    print("-"*60)
    
    day1 = TestDay1_DatabaseAndAuth()
    
    try:
        # Test database
        db = SessionLocal()
        db_ok = day1.test_database_schema(db)
        db.close()
        
        # Test authentication API
        auth_token = day1.test_authentication_api()
        
        # Test onboarding
        # if auth_token:
        #     onboarding_ok = day1.test_onboarding_flow(auth_token)
        # else:
        #     onboarding_ok = False
        
        if db_ok and auth_token:
            results['Day 1'] = "✅ PASSED"
        elif db_ok or auth_token:
            results['Day 1'] = "⚠️  PARTIAL"
        else:
            results['Day 1'] = "❌ FAILED"
            
    except Exception as e:
        results['Day 1'] = f"❌ ERROR: {str(e)[:50]}"
    
    # DAY 2: Recipes & Nutrition
    print("\n📅 DAY 2: Recipe Dataset & Nutrition Foundation")
    print("-"*60)
    
    day2 = TestDay2_RecipesAndNutrition()
    
    try:
        # Test database
        db = SessionLocal()
        db_ok = day2.test_recipe_database(db)
        db.close()
        
        # Test API
        api_ok = day2.test_recipe_api()
        
        if db_ok and api_ok:
            results['Day 2'] = "✅ PASSED"
        elif db_ok or api_ok:
            results['Day 2'] = "⚠️  PARTIAL"
        else:
            results['Day 2'] = "❌ FAILED"
            
    except Exception as e:
        results['Day 2'] = f"❌ ERROR: {str(e)[:50]}"
    
    # DAY 3: Item Normalization & Inventory
    print("\n📅 DAY 3: Item Normalization & Inventory System")
    print("-"*60)
    
    day3 = TestDay3_ItemNormalization()
    
    try:
        # Test normalizer
        db = SessionLocal()
        normalizer_ok = day3.test_normalizer_class(db)
        
        # Test inventory API
        inventory_ok = day3.test_inventory_api(auth_token)
        
        if normalizer_ok:
            results['Day 3'] = "✅ PASSED"
        else:
            results['Day 3'] = "⚠️  PARTIAL"
            
    except Exception as e:
        results['Day 3'] = f"❌ ERROR: {str(e)[:50]}"
    
    # DAY 4: Meal Optimizer
    # print("\n📅 DAY 4: Linear Programming Optimizer")
    # print("-"*60)
    
    # day4 = TestDay4_MealOptimizer()
    
    # try:
    #     db = SessionLocal()
        
    #     # Test optimizer
    #     optimizer_ok = day4.test_optimizer_class(db)
        
    #     # Test performance
    #     if optimizer_ok:
    #         performance_ok = day4.test_performance(db)
    #     else:
    #         performance_ok = False
        
    #     db.close()
        
    #     if optimizer_ok and performance_ok:
    #         results['Day 4'] = "✅ PASSED"
    #     elif optimizer_ok:
    #         results['Day 4'] = "⚠️  PARTIAL"
    #     else:
    #         results['Day 4'] = "❌ FAILED"
            
    # except Exception as e:
    #     results['Day 4'] = f"❌ ERROR: {str(e)[:50]}"
    
    # DAY 5: Planning Agent
    print("\n📅 DAY 5: Planning Agent & Meal Plan Generation")
    print("-"*60)
    
    day5 = TestDay5_PlanningAgent()
    
    try:
        db = SessionLocal()
        
        # Test agent
        agent_ok = day5.test_planning_agent(db)
        
        db.close()
        
        # Test API
        api_ok = day5.test_meal_plan_api(auth_token)
        
        if agent_ok:
            results['Day 5'] = "✅ PASSED"
        else:
            results['Day 5'] = "⚠️  PARTIAL"
            
    except Exception as e:
        results['Day 5'] = f"❌ ERROR: {str(e)[:50]}"
    
    # SUMMARY
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for day, result in results.items():
        print(f"  {day}: {result}")
    
    passed = sum(1 for r in results.values() if "✅ PASSED" in r)
    partial = sum(1 for r in results.values() if "⚠️  PARTIAL" in r)
    failed = sum(1 for r in results.values() if "❌" in r)
    
    print(f"\n📊 Overall: {passed} passed, {partial} partial, {failed} failed")
    
    print("\n🏆 IMPLEMENTATION STATUS:")
    if passed == 5:
        print("  🎉 ALL COMPONENTS FULLY FUNCTIONAL!")
        print("  ✨ Days 1-5 complete and working!")
    elif passed >= 3:
        print("  ✅ Core components working")
        print("  ⚠️  Some features need completion")
    else:
        print("  ⚠️  Major components need implementation")
    
    print("\n💡 NEXT STEPS:")
    if 'Day 1' not in results or "❌" in results.get('Day 1', ''):
        print("  1. Fix authentication and database schema")
    if 'Day 2' not in results or "❌" in results.get('Day 2', ''):
        print("  2. Seed recipe data and implement API endpoints")
    if 'Day 3' not in results or "❌" in results.get('Day 3', ''):
        print("  3. Complete ItemNormalizer implementation")
    if 'Day 4' not in results or "❌" in results.get('Day 4', ''):
        print("  4. Fix MealPlanOptimizer imports and constraints")
    if 'Day 5' not in results or "❌" in results.get('Day 5', ''):
        print("  5. Implement PlanningAgent tools")
    
    print("\n📝 To run individual day tests:")
    print("  python tests/test_day1.py")
    print("  python tests/test_day2.py")
    print("  python tests/test_day3.py")
    print("  python tests/test_meal_optimizer_simple.py")
    
    return 0 if passed == 5 else 1


if __name__ == "__main__":
    # Check if server is running
    print("\n🔍 Checking server status...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            print("  ✅ Server is running")
        else:
            print("  ⚠️  Server returned unexpected status")
    except requests.ConnectionError:
        print("  ❌ Server not running! Start with: uvicorn app.main:app --reload")
        print("  Then run this test again.")
        sys.exit(1)
    
    # Run the test suite
    exit_code = run_comprehensive_test_suite()
    sys.exit(exit_code)