"""
Focused test for auto_deduct_ingredients() function only
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import User, Recipe, RecipeIngredient, Item, UserInventory
from app.services.consumption_services import ConsumptionService
from app.core.config import settings

def print_result(test_name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if details:
        print(f"     └─ {details}")

def setup():
    """Create test data with inventory"""
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Create user
        user = User(
            email=f"test_deduct_{datetime.now().timestamp()}@test.com",
            hashed_password="test_hash",
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Get recipe with ingredients
        recipe = db.query(Recipe).join(RecipeIngredient).first()
        if not recipe:
            print("❌ ERROR: No recipes with ingredients in database")
            db.close()
            return None
        
        # Get recipe ingredients
        ingredients = db.query(RecipeIngredient).filter(
            RecipeIngredient.recipe_id == recipe.id
        ).all()
        
        if not ingredients:
            print("❌ ERROR: Recipe has no ingredients")
            db.close()
            return None
        
        print(f"Recipe '{recipe.title}' has {len(ingredients)} ingredients")
        
        # Add inventory for each ingredient
        inventory_items = []
        for ing in ingredients:
            inventory = UserInventory(
                user_id=user.id,
                item_id=ing.item_id,
                quantity_grams=1000.0,  # 1kg of each
                purchase_date=datetime.utcnow(),
                source="manual"
            )
            db.add(inventory)
            inventory_items.append(inventory)
        
        db.flush()
        db.commit()
        
        print(f"✅ Setup complete: User {user.id}, Recipe {recipe.id}, {len(inventory_items)} inventory items")
        
        return {
            "user_id": user.id,
            "recipe_id": recipe.id,
            "ingredients": ingredients,
            "inventory_items": inventory_items,
            "db": db
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Setup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return None

def test_auto_deduct_ingredients(test_data):
    """Test auto_deduct_ingredients() function"""
    
    print("\n" + "="*60)
    print("Testing: auto_deduct_ingredients()")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    
    # Get initial quantities
    print("inventory items", test_data["inventory_items"])
    db_check = SessionLocal()
    initial_quantities = {}
    for inv in test_data["inventory_items"]:
        inv = db_check.merge(inv)
        db_check.refresh(inv)
        initial_quantities[inv.item_id] = inv.quantity_grams
        print(f"Initial - Item {inv.item_id}: {inv.quantity_grams}g")
    db_check.close()
    
    # TEST 1: Deduct with portion 1.0
    print("\n[Test 1] Deduct ingredients with portion 1.0")
    db1 = SessionLocal()
    service1 = ConsumptionService(db1)
    
    result = service1.auto_deduct_ingredients(
        recipe_id=test_data["recipe_id"],
        portion_multiplier=1.0,
        user_id=test_data["user_id"]
    )
    
    if result.get("success"):
        db1.commit()
    db1.close()
    
    # Validate result
    is_success = result.get("success", False)
    print_result("Returns success=True", is_success,
                f"Error: {result.get('error', 'None')}" if not is_success else "")
    
    if is_success:
        has_deducted = "deducted_items" in result
        print_result("Has deducted_items", has_deducted)
        
        if has_deducted:
            deducted = result["deducted_items"]
            items_count = len(deducted)
            expected_count = len(test_data["ingredients"])
            print_result(f"Deducted {expected_count} items", items_count == expected_count,
                        f"Got {items_count}, expected {expected_count}")
    
    # Verify database deduction
    print("\n[Test 2] Database inventory was reduced")
    db2 = SessionLocal()
    
    all_reduced = True
    for inv in test_data["inventory_items"]:
        current = db2.query(UserInventory).filter(
            UserInventory.user_id == test_data["user_id"],
            UserInventory.item_id == inv.item_id
        ).first()
        
        if current:
            initial = initial_quantities[inv.item_id]
            was_reduced = current.quantity_grams < initial
            print_result(f"Item {inv.item_id} reduced", was_reduced,
                        f"Was {initial}g, now {current.quantity_grams}g")
            all_reduced = all_reduced and was_reduced
    
    print_result("All items reduced", all_reduced)
    db2.close()
    
    # TEST 3: Deduct with portion 2.0
    print("\n[Test 3] Deduct with portion multiplier 2.0")
    
    # Get quantities before
    db_before = SessionLocal()
    quantities_before = {}
    for inv in test_data["inventory_items"]:
        current = db_before.query(UserInventory).filter(
            UserInventory.user_id == test_data["user_id"],
            UserInventory.item_id == inv.item_id
        ).first()
        if current:
            quantities_before[inv.item_id] = current.quantity_grams
    db_before.close()
    
    # Deduct with 2x portion
    db3 = SessionLocal()
    service3 = ConsumptionService(db3)
    
    result_2x = service3.auto_deduct_ingredients(
        recipe_id=test_data["recipe_id"],
        portion_multiplier=2.0,
        user_id=test_data["user_id"]
    )
    
    if result_2x.get("success"):
        db3.commit()
    db3.close()
    
    is_success = result_2x.get("success", False)
    print_result("Returns success=True for 2x portion", is_success)
    
    # Verify 2x deduction
    db_after = SessionLocal()
    for ing in test_data["ingredients"]:
        before = quantities_before.get(ing.item_id, 0)
        
        after = db_after.query(UserInventory).filter(
            UserInventory.user_id == test_data["user_id"],
            UserInventory.item_id == ing.item_id
        ).first()
        
        if after:
            # Expected deduction: 2.0 * ingredient quantity
            expected_deduction = 2.0 * ing.quantity_grams
            actual_deduction = before - after.quantity_grams
            
            # Allow 0.1g tolerance for floating point
            is_correct = abs(actual_deduction - expected_deduction) < 0.1
            print_result(f"Item {ing.item_id} 2x deduction correct", is_correct,
                        f"Expected -{expected_deduction}g, got -{actual_deduction}g")
    
    db_after.close()
    
    # TEST 4: Invalid recipe_id
    print("\n[Test 4] Handle invalid recipe_id")
    db4 = SessionLocal()
    service4 = ConsumptionService(db4)
    
    result_invalid = service4.auto_deduct_ingredients(
        recipe_id=999999,
        portion_multiplier=1.0,
        user_id=test_data["user_id"]
    )
    db4.close()
    
    is_error = not result_invalid.get("success", True)
    print_result("Returns success=False", is_error)
    
    has_error = "error" in result_invalid
    print_result("Has error message", has_error,
                f"Error: {result_invalid.get('error', 'None')}")

def cleanup(test_data):
    """Clean up test data"""
    print("\n" + "="*60)
    print("Cleanup")
    print("="*60)
    
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        db.query(UserInventory).filter(UserInventory.user_id == test_data["user_id"]).delete()
        db.query(User).filter(User.id == test_data["user_id"]).delete()
        db.commit()
        print("✅ Cleanup complete")
    except Exception as e:
        db.rollback()
        print(f"⚠️  Cleanup error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("\n" + "="*60)
    print("FOCUSED TEST: auto_deduct_ingredients() ONLY")
    print("="*60)
    
    test_data = setup()
    if test_data:
        test_auto_deduct_ingredients(test_data)
        # cleanup(test_data)
    else:
        print("❌ Setup failed, cannot run tests")