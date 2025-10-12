"""
Populate Dashboard Test Data
Comprehensive script to populate database with realistic test data for dashboard testing
"""

import sys
import os
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import (
    User, UserProfile, UserGoal, Recipe, MealLog, 
    UserInventory, Item, MealPlan
)
from app.core.config import settings

def print_status(message, status="INFO"):
    symbols = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "ERROR": "❌",
        "WARNING": "⚠️"
    }
    print(f"{symbols.get(status, 'ℹ️')} {message}")

def get_user_by_credentials(db, email, password_hash=None):
    """Get user by email"""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        print_status(f"User not found: {email}", "ERROR")
        return None
    
    print_status(f"Found user: {email} (ID: {user.id})", "SUCCESS")
    return user

def populate_todays_meals(db, user_id):
    """Create today's meal logs with different states"""
    print_status("\n[1] Creating Today's Meals...", "INFO")
    
    # Get a recipe for meals
    recipe = db.query(Recipe).first()
    if not recipe:
        print_status("No recipes found in database", "ERROR")
        return False
    
    today = date.today()
    now = datetime.now()
    
    meals_data = [
        {
            "meal_type": "breakfast",
            "hour": 8,
            "consumed": True,
            "skipped": False,
            "description": "Consumed"
        },
        {
            "meal_type": "lunch",
            "hour": 13,
            "consumed": True,
            "skipped": False,
            "description": "Consumed"
        },
        {
            "meal_type": "snack",
            "hour": 16,
            "consumed": False,
            "skipped": True,
            "description": "Skipped"
        },
        {
            "meal_type": "dinner",
            "hour": 19,
            "consumed": False,
            "skipped": False,
            "description": "Pending"
        }
    ]
    
    created_count = 0
    for meal in meals_data:
        planned_time = datetime.combine(today, datetime.min.time()) + timedelta(hours=meal["hour"])
        
        # Only mark as consumed if the planned time is in the past
        consumed_time = None
        if meal["consumed"] and planned_time < now:
            consumed_time = planned_time + timedelta(minutes=30)
        
        meal_log = MealLog(
            user_id=user_id,
            recipe_id=recipe.id,
            meal_type=meal["meal_type"],
            planned_datetime=planned_time,
            consumed_datetime=consumed_time,
            was_skipped=meal["skipped"],
            skip_reason="Not hungry" if meal["skipped"] else None,
            portion_multiplier=1.0
        )
        db.add(meal_log)
        created_count += 1
        print_status(f"  - {meal['meal_type'].capitalize()}: {meal['description']}", "SUCCESS")
    
    db.commit()
    print_status(f"Created {created_count} meals for today", "SUCCESS")
    return True

def populate_historical_meals(db, user_id, days=14):
    """Create historical meal logs with patterns"""
    print_status(f"\n[2] Creating {days} Days of Historical Meals...", "INFO")
    
    recipe = db.query(Recipe).first()
    if not recipe:
        print_status("No recipes found", "ERROR")
        return False
    
    created_count = 0
    
    for days_ago in range(1, days + 1):  # Start from yesterday
        past_date = date.today() - timedelta(days=days_ago)
        day_of_week = past_date.weekday()  # 0=Monday, 6=Sunday
        
        # Pattern: Skip dinner on weekends
        skip_dinner = day_of_week >= 5
        
        # Pattern: Skip snacks on weekdays
        skip_snack = day_of_week < 5
        
        meals = [
            ("breakfast", 8, False, False),
            ("lunch", 12, False, False),
            ("snack", 16, False, skip_snack),
            ("dinner", 19, False, skip_dinner)
        ]
        
        for meal_type, hour, consumed_flag, skip_flag in meals:
            planned_time = datetime.combine(past_date, datetime.min.time()) + timedelta(hours=hour)
            
            # All past meals are either consumed or skipped
            consumed_time = planned_time + timedelta(minutes=30) if not skip_flag else None
            
            meal_log = MealLog(
                user_id=user_id,
                recipe_id=recipe.id,
                meal_type=meal_type,
                planned_datetime=planned_time,
                consumed_datetime=consumed_time,
                was_skipped=skip_flag,
                skip_reason="Weekend plans" if skip_flag and day_of_week >= 5 else ("Too busy" if skip_flag else None),
                portion_multiplier=1.0
            )
            db.add(meal_log)
            created_count += 1
    
    db.commit()
    print_status(f"Created {created_count} historical meal logs", "SUCCESS")
    return True

def populate_inventory(db, user_id):
    """Create inventory with various states"""
    print_status("\n[3] Creating Inventory Items...", "INFO")
    
    # Common items with realistic data
    items_to_create = [
        {
            "name": "chicken breast",
            "category": "protein",
            "nutrition": {"calories": 165, "protein_g": 31, "carbs_g": 0, "fat_g": 3.6},
            "quantity": 1000.0,
            "expiry_days": 5,
            "description": "Good stock"
        },
        {
            "name": "rice",
            "category": "grains",
            "nutrition": {"calories": 130, "protein_g": 2.7, "carbs_g": 28, "fat_g": 0.3},
            "quantity": 150.0,
            "expiry_days": 30,
            "description": "Low stock"
        },
        {
            "name": "broccoli",
            "category": "vegetables",
            "nutrition": {"calories": 34, "protein_g": 2.8, "carbs_g": 7, "fat_g": 0.4},
            "quantity": 300.0,
            "expiry_days": 1,
            "description": "Expiring tomorrow"
        },
        {
            "name": "eggs",
            "category": "protein",
            "nutrition": {"calories": 155, "protein_g": 13, "carbs_g": 1.1, "fat_g": 11},
            "quantity": 600.0,
            "expiry_days": 3,
            "description": "Expiring in 3 days"
        },
        {
            "name": "milk",
            "category": "dairy",
            "nutrition": {"calories": 42, "protein_g": 3.4, "carbs_g": 5, "fat_g": 1},
            "quantity": 500.0,
            "expiry_days": 4,
            "description": "Normal stock"
        },
        {
            "name": "tomatoes",
            "category": "vegetables",
            "nutrition": {"calories": 18, "protein_g": 0.9, "carbs_g": 3.9, "fat_g": 0.2},
            "quantity": 80.0,
            "expiry_days": 2,
            "description": "Low stock + expiring"
        },
        {
            "name": "oats",
            "category": "grains",
            "nutrition": {"calories": 389, "protein_g": 16.9, "carbs_g": 66.3, "fat_g": 6.9},
            "quantity": 1200.0,
            "expiry_days": 90,
            "description": "Good stock"
        }
    ]
    
    today = datetime.utcnow()
    created_count = 0
    
    for item_data in items_to_create:
        # Get or create item
        item = db.query(Item).filter(Item.canonical_name == item_data["name"]).first()
        if not item:
            item = Item(
                canonical_name=item_data["name"],
                category=item_data["category"],
                unit="g",
                nutrition_per_100g=item_data["nutrition"]
            )
            db.add(item)
            db.flush()
        
        # Create inventory entry
        inventory = UserInventory(
            user_id=user_id,
            item_id=item.id,
            quantity_grams=item_data["quantity"],
            purchase_date=today - timedelta(days=2),
            expiry_date=(today + timedelta(days=item_data["expiry_days"])).date(),
            source="manual"
        )
        db.add(inventory)
        created_count += 1
        print_status(f"  - {item_data['name']}: {item_data['description']}", "SUCCESS")
    
    db.commit()
    print_status(f"Created {created_count} inventory items", "SUCCESS")
    return True

def populate_meal_plan(db, user_id):
    """Create an active meal plan"""
    print_status("\n[4] Creating Active Meal Plan...", "INFO")
    
    # Get recipes for the plan
    recipes = db.query(Recipe).limit(10).all()
    if len(recipes) < 7:
        print_status("Not enough recipes for meal plan", "WARNING")
        return False
    
    # Create a simple 7-day plan
    week_start = date.today() - timedelta(days=date.today().weekday())  # This week's Monday
    
    week_plan = {}
    for day_num in range(7):
        day_date = week_start + timedelta(days=day_num)
        day_name = day_date.strftime("%A").lower()
        
        # Use different recipes for variety
        breakfast_recipe = recipes[day_num % len(recipes)]
        lunch_recipe = recipes[(day_num + 1) % len(recipes)]
        dinner_recipe = recipes[(day_num + 2) % len(recipes)]
        
        week_plan[day_name] = {
            "date": day_date.isoformat(),
            "meals": {
                "breakfast": {
                    "recipe_id": breakfast_recipe.id,
                    "recipe_name": breakfast_recipe.title,
                    "macros": breakfast_recipe.macros_per_serving or {}
                },
                "lunch": {
                    "recipe_id": lunch_recipe.id,
                    "recipe_name": lunch_recipe.title,
                    "macros": lunch_recipe.macros_per_serving or {}
                },
                "dinner": {
                    "recipe_id": dinner_recipe.id,
                    "recipe_name": dinner_recipe.title,
                    "macros": dinner_recipe.macros_per_serving or {}
                }
            }
        }
    
    # Deactivate any existing plans
    db.query(MealPlan).filter(
        MealPlan.user_id == user_id,
        MealPlan.is_active == True
    ).update({"is_active": False})
    
    # Create new meal plan
    meal_plan = MealPlan(
        user_id=user_id,
        week_start_date=week_start,
        plan_data=week_plan,
        grocery_list={},
        total_calories=14000.0,  # Approximate
        avg_macros={"protein_g": 150, "carbs_g": 200, "fat_g": 60},
        is_active=True
    )
    db.add(meal_plan)
    db.commit()
    
    print_status(f"Created active meal plan starting {week_start}", "SUCCESS")
    return True

def verify_data(db, user_id):
    """Verify all data was created successfully"""
    print_status("\n[5] Verifying Created Data...", "INFO")
    
    # Count today's meals
    today_meals = db.query(MealLog).filter(
        MealLog.user_id == user_id,
        MealLog.planned_datetime >= datetime.combine(date.today(), datetime.min.time())
    ).count()
    print_status(f"  - Today's meals: {today_meals}", "SUCCESS" if today_meals > 0 else "WARNING")
    
    # Count historical meals
    historical_meals = db.query(MealLog).filter(
        MealLog.user_id == user_id,
        MealLog.planned_datetime < datetime.combine(date.today(), datetime.min.time())
    ).count()
    print_status(f"  - Historical meals: {historical_meals}", "SUCCESS" if historical_meals > 0 else "WARNING")
    
    # Count inventory items
    inventory_count = db.query(UserInventory).filter(
        UserInventory.user_id == user_id
    ).count()
    print_status(f"  - Inventory items: {inventory_count}", "SUCCESS" if inventory_count > 0 else "WARNING")
    
    # Check for active meal plan
    active_plan = db.query(MealPlan).filter(
        MealPlan.user_id == user_id,
        MealPlan.is_active == True
    ).first()
    print_status(f"  - Active meal plan: {'Yes' if active_plan else 'No'}", 
                "SUCCESS" if active_plan else "WARNING")
    
    return True

def main():
    """Main execution"""
    print("\n" + "="*60)
    print("POPULATE DASHBOARD TEST DATA")
    print("="*60)
    
    # Get user credentials
    print_status("\nEnter test user credentials:", "INFO")
    email = input("Email: ").strip()
    
    if not email:
        print_status("Email is required", "ERROR")
        return
    
    # Create database connection
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Get user
        user = get_user_by_credentials(db, email)
        if not user:
            return
        
        user_id = user.id
        
        # Check if user has profile
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not profile:
            print_status("User has not completed onboarding", "ERROR")
            print_status("Please complete onboarding first", "INFO")
            return
        
        print_status(f"\nUser Profile: {profile.name}, {profile.age}y, {profile.weight_kg}kg", "INFO")
        
        # Ask for confirmation
        confirm = input("\nPopulate test data for this user? (yes/no): ").strip().lower()
        if confirm != "yes":
            print_status("Operation cancelled", "INFO")
            return
        
        # Populate data
        print_status("\n" + "="*60, "INFO")
        print_status("POPULATING TEST DATA", "INFO")
        print_status("="*60, "INFO")
        
        success = True
        success = populate_todays_meals(db, user_id) and success
        success = populate_historical_meals(db, user_id, days=14) and success
        success = populate_inventory(db, user_id) and success
        success = populate_meal_plan(db, user_id) and success
        success = verify_data(db, user_id) and success
        
        if success:
            print_status("\n" + "="*60, "SUCCESS")
            print_status("DATA POPULATION COMPLETE", "SUCCESS")
            print_status("="*60, "SUCCESS")
            print_status("\nYou can now test the dashboard endpoints:", "INFO")
            print_status("  - GET /dashboard/summary", "INFO")
            print_status("  - GET /dashboard/recent-activity", "INFO")
            print_status("  - GET /tracking/today", "INFO")
            print_status("  - GET /tracking/history?days=7", "INFO")
            print_status("  - GET /tracking/patterns", "INFO")
            print_status("  - GET /tracking/inventory-status", "INFO")
        else:
            print_status("\nSome operations failed. Check logs above.", "WARNING")
        
    except Exception as e:
        db.rollback()
        print_status(f"Error: {str(e)}", "ERROR")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()