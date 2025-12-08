"""
Inventory API Endpoints V2 - Clean Architecture

Provides inventory management endpoints using repository pattern for data access
and IntelligentInventoryService for business logic.

MIGRATED FROM: inventory.py
USES:
- InventoryRepository for simple CRUD operations
- IntelligentInventoryService for complex business logic (AI normalization, recommendations)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel
import logging

from app.models.database import get_db, User, Item
from app.services.auth import get_current_user_dependency as get_current_user
from app.services.inventory_service import IntelligentInventoryService
from app.repositories.inventory_repository import InventoryRepository
from app.dependencies import get_inventory_repository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory/v2", tags=["inventory-v2"])


# ===== REQUEST/RESPONSE SCHEMAS (IDENTICAL TO V1) =====

class AddItemsRequest(BaseModel):
    """Request for adding items from text input"""
    text_input: str


class ConfirmItemRequest(BaseModel):
    """Request for confirming a medium-confidence item"""
    original_text: str
    item_id: int
    quantity_grams: float


class DeductMealRequest(BaseModel):
    """Request for deducting meal ingredients"""
    recipe_id: int
    portion_multiplier: float = 1.0


class InventoryItemResponse(BaseModel):
    """Response for individual inventory item"""
    id: int
    item_id: int
    item_name: str
    category: str
    quantity_grams: float
    expiry_date: Optional[str]
    days_until_expiry: Optional[int]

    class Config:
        orm_mode = True


# ===== ENDPOINTS =====

@router.post("/add-items")
async def add_items_from_text(
    request: AddItemsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add items to inventory from text input (receipt or list).
    Uses AI normalization to understand various formats.

    MIGRATED FROM: inventory.py:40-82

    Uses:
    - IntelligentInventoryService for AI normalization and batch processing
      (Complex business logic - NOT repository pattern candidate)
    """
    logger.info("=" * 80)
    logger.info("🔵 ADD ITEMS API ENDPOINT CALLED (V2)")
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
async def confirm_item(
    request: ConfirmItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm and add an item that had medium confidence.

    MIGRATED FROM: inventory.py:84-147

    Uses:
    - IntelligentInventoryService for confirmation and learning
      (Business logic with ML learning - NOT repository pattern candidate)
    """
    logger.info("=" * 80)
    logger.info("🔵 CONFIRM ITEM API ENDPOINT CALLED (V2)")
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
async def get_inventory_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive inventory status with AI insights.

    MIGRATED FROM: inventory.py:149-167

    Uses:
    - IntelligentInventoryService.get_inventory_status() for AI-powered analytics
      (Complex business logic with recommendations - NOT repository pattern candidate)
    """
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
async def get_inventory_items(
    category: Optional[str] = None,
    low_stock_only: bool = False,
    expiring_soon: bool = False,
    current_user: User = Depends(get_current_user),
    inventory_repo: InventoryRepository = Depends(get_inventory_repository)
):
    """
    Get user's inventory items with filters.

    MIGRATED FROM: inventory.py:169-224

    Uses:
    - InventoryRepository for filtered queries (simple data access)
    """
    try:
        # Get inventory items based on filters
        if expiring_soon:
            inventory_items = await inventory_repo.get_expiring_items(
                user_id=current_user.id,
                days_threshold=3
            )
        elif low_stock_only:
            inventory_items = await inventory_repo.get_low_stock_items(
                user_id=current_user.id,
                threshold_grams=100
            )
        else:
            inventory_items = await inventory_repo.get_all_for_user(
                user_id=current_user.id,
                include_zero_quantity=False
            )

        # Format response
        items = []
        for inv in inventory_items:
            # Item already loaded via joinedload in repository
            item = inv.item

            # Skip if item not found or doesn't match category filter
            if not item:
                continue

            if category and item.category != category:
                continue

            from datetime import datetime
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

    except Exception as e:
        logger.error(f"Error getting inventory items: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve inventory items: {str(e)}"
        )


@router.post("/deduct-meal")
async def deduct_meal_ingredients(
    request: DeductMealRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deduct ingredients when user consumes a meal.

    MIGRATED FROM: inventory.py:226-240

    Uses:
    - IntelligentInventoryService.deduct_for_meal() for intelligent deduction with warnings
      (Business logic with complex validation - NOT repository pattern candidate)
    """
    service = IntelligentInventoryService(db)
    result = service.deduct_for_meal(
        current_user.id,
        request.recipe_id,
        request.portion_multiplier
    )

    return result


@router.get("/makeable-recipes")
async def get_makeable_recipes(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get recipes user can make with current inventory.

    Returns categorized results:
    - fully_makeable: Recipes with 100% ingredient match
    - partially_makeable: Recipes with 80-99% ingredient match

    MIGRATED FROM: inventory.py:242-264

    Uses:
    - IntelligentInventoryService.get_makeable_recipes() for complex matching algorithm
      (Complex business logic with SQL optimization - NOT repository pattern candidate)
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
async def check_recipe_availability(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user has ingredients for a specific recipe.

    MIGRATED FROM: inventory.py:266-276

    Uses:
    - IntelligentInventoryService.check_recipe_availability() for detailed analysis
      (Business logic with coverage percentage - NOT repository pattern candidate)
    """
    service = IntelligentInventoryService(db)
    availability = service.check_recipe_availability(current_user.id, recipe_id)

    return availability


@router.delete("/item/{inventory_id}")
async def remove_inventory_item(
    inventory_id: int,
    current_user: User = Depends(get_current_user),
    inventory_repo: InventoryRepository = Depends(get_inventory_repository)
):
    """
    Remove an item from inventory.

    MIGRATED FROM: inventory.py:278-298

    Uses:
    - InventoryRepository.delete() for simple deletion with user validation
    """
    try:
        # Delete using repository
        deleted = await inventory_repo.delete(
            inventory_id=inventory_id,
            user_id=current_user.id
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Item not found in your inventory"
            )

        return {"status": "deleted", "message": "Item removed from inventory"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting inventory item: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete inventory item: {str(e)}"
        )
