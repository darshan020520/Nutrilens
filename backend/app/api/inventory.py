from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from typing import List, Dict, Optional
from app.models.database import get_db, UserInventory, Item, User
from app.services.inventory_service import IntelligentInventoryService
from app.services.auth import get_current_user_dependency as get_current_user
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory", tags=["Inventory"])

# Request/Response models
class AddItemsRequest(BaseModel):
    text_input: str
    
class ConfirmItemRequest(BaseModel):
    original_text: str
    item_id: int
    quantity_grams: float

class DeductMealRequest(BaseModel):
    recipe_id: int
    portion_multiplier: float = 1.0

class InventoryItemResponse(BaseModel):
    id: int
    item_id: int
    item_name: str
    category: str
    quantity_grams: float
    expiry_date: Optional[str]
    days_until_expiry: Optional[int]
    
    class Config:
        orm_mode = True

@router.post("/add-items")
def add_items_from_text(
    request: AddItemsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add items to inventory from text input (receipt or list)
    Uses AI normalization to understand various formats
    """
    logger.info("=" * 80)
    logger.info("🔵 ADD ITEMS API ENDPOINT CALLED")
    logger.info(f"User ID: {current_user.id}")
    logger.info(f"Input text:\n{request.text_input}")
    logger.info("=" * 80)

    try:
        service = IntelligentInventoryService(db)
        logger.info("✅ IntelligentInventoryService initialized")

        results = service.add_items_from_text(current_user.id, request.text_input)

        logger.info("=" * 80)
        logger.info("🟢 ADD ITEMS PROCESSING COMPLETE")
        logger.info(f"Summary: {results['summary']}")
        logger.info(f"Successful: {len(results.get('successful', []))}")
        logger.info(f"Needs confirmation: {len(results.get('needs_confirmation', []))}")
        logger.info(f"Failed: {len(results.get('failed', []))}")
        logger.info("=" * 80)

        return {
            "status": "processed",
            "results": results,
            "message": f"Successfully added {results['summary']['successful']} items"
        }
    except Exception as e:
        logger.error("=" * 80)
        logger.error("🔴 ERROR IN ADD ITEMS ENDPOINT")
        logger.error(f"Error: {str(e)}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        raise

@router.post("/confirm-item")
def confirm_item(
    request: ConfirmItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Confirm and add an item that had medium confidence"""
    logger.info("=" * 80)
    logger.info("🔵 CONFIRM ITEM API ENDPOINT CALLED")
    logger.info(f"User ID: {current_user.id}")
    logger.info(f"Original text: {request.original_text}")
    logger.info(f"Item ID to confirm: {request.item_id}")
    logger.info(f"Quantity: {request.quantity_grams}g")
    logger.info("=" * 80)

    try:
        service = IntelligentInventoryService(db)

        # Get the item
        item = db.query(Item).filter(Item.id == request.item_id).first()
        if not item:
            logger.error(f"❌ Item with ID {request.item_id} not found in database")
            raise HTTPException(status_code=404, detail="Item not found")

        logger.info(f"✅ Found item: {item.canonical_name} (ID: {item.id})")

        # Add to inventory
        logger.info(f"📦 Adding to inventory: {item.canonical_name}, {request.quantity_grams}g")
        inventory_item = service._add_to_inventory(
            current_user.id,
            item.id,
            request.quantity_grams
        )

        logger.info(f"✅ Added to inventory successfully: {inventory_item.quantity_grams}g")

        # Learn from confirmation (improves future matching)
        logger.info(f"🎓 Learning from confirmation: '{request.original_text}' → '{item.canonical_name}'")
        service.normalizer.learn_from_confirmation(
            request.original_text,
            item,
            was_correct=True
        )

        logger.info("=" * 80)
        logger.info("🟢 CONFIRM ITEM COMPLETE")
        logger.info(f"Item added: {item.canonical_name} ({inventory_item.quantity_grams}g)")
        logger.info("=" * 80)

        return {
            "status": "added",
            "item": item.canonical_name,
            "quantity": f"{inventory_item.quantity_grams}g"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error("🔴 ERROR IN CONFIRM ITEM ENDPOINT")
        logger.error(f"Error: {str(e)}")
        logger.error("=" * 80)
        import traceback
        traceback.print_exc()
        raise

@router.get("/status")
def get_inventory_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get comprehensive inventory status with AI insights"""
    service = IntelligentInventoryService(db)
    status = service.get_inventory_status(current_user.id)
    
    return {
        "total_items": status.total_items,
        "total_weight_g": status.total_weight_g,
        "expiring_soon": status.expiring_soon,
        "low_stock": status.low_stock,
        "categories": status.categories_available,
        "nutritional_capacity": status.nutritional_capacity,
        "estimated_days_remaining": status.estimated_days_remaining,
        "ai_recommendations": status.recommendations
    }

@router.get("/items")
def get_inventory_items(
    category: Optional[str] = None,
    low_stock_only: bool = False,
    expiring_soon: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's inventory items with filters"""
    # OPTIMIZATION: Eager load Item to avoid N+1 query problem
    query = db.query(UserInventory).options(
        joinedload(UserInventory.item)
    ).filter(UserInventory.user_id == current_user.id)

    if low_stock_only:
        query = query.filter(UserInventory.quantity_grams < 100)

    if expiring_soon:
        three_days_later = datetime.now() + timedelta(days=3)
        query = query.filter(UserInventory.expiry_date <= three_days_later)

    inventory_items = query.all()

    # Format response
    items = []

    for inv in inventory_items:
        # Use eager-loaded relationship instead of querying
        item = inv.item

        # Skip if item not found or doesn't match category filter
        if not item:
            continue

        if category and item.category != category:
            continue

        days_until_expiry = None
        if inv.expiry_date:
            days_until_expiry = (inv.expiry_date - datetime.now()).days

        items.append({
            "id": inv.id,
            "item_id": item.id,
            "item_name": item.canonical_name,
            "category": item.category,
            "quantity_grams": inv.quantity_grams,
            "expiry_date": inv.expiry_date.isoformat() if inv.expiry_date else None,
            "days_until_expiry": days_until_expiry,
            "is_depleted": (inv.quantity_grams or 0) <= 0  # Flag for fully consumed items
        })

    return {
        "count": len(items),
        "items": items
    }

@router.post("/deduct-meal")
def deduct_meal_ingredients(
    request: DeductMealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deduct ingredients when user consumes a meal"""
    service = IntelligentInventoryService(db)
    result = service.deduct_for_meal(
        current_user.id,
        request.recipe_id,
        request.portion_multiplier
    )
    
    return result

@router.get("/makeable-recipes")
def get_makeable_recipes(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recipes user can make with current inventory

    Returns categorized results:
    - fully_makeable: Recipes with 100% ingredient match
    - partially_makeable: Recipes with 80-99% ingredient match
    """
    service = IntelligentInventoryService(db)
    result = service.get_makeable_recipes(current_user.id, limit)

    total_count = len(result['fully_makeable']) + len(result['partially_makeable'])

    return {
        "count": total_count,
        "fully_makeable": result['fully_makeable'],
        "partially_makeable": result['partially_makeable']
    }

@router.get("/check-recipe/{recipe_id}")
def check_recipe_availability(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if user has ingredients for a specific recipe"""
    service = IntelligentInventoryService(db)
    availability = service.check_recipe_availability(current_user.id, recipe_id)
    
    return availability

@router.delete("/item/{inventory_id}")
def remove_inventory_item(
    inventory_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove an item from inventory"""
    item = db.query(UserInventory).filter(
        and_(
            UserInventory.id == inventory_id,
            UserInventory.user_id == current_user.id
        )
    ).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in your inventory")
    
    db.delete(item)
    db.commit()
    
    return {"status": "deleted", "message": "Item removed from inventory"}