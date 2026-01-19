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

from app.models.database import User, Item
from app.services.intelligent_inventory_service_v2 import IntelligentInventoryServiceV2
from app.dependencies import get_intelligent_inventory_service_v2, get_current_user

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
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """
    Add items to inventory from text input (receipt or list).
    Uses AI normalization to understand various formats.

    MIGRATED FROM: inventory.py:40-82

    CLEAN ARCHITECTURE V2:
    - Uses IntelligentInventoryServiceV2 (async, dependency injection)
    - Calls await service.add_items_from_text() (no event loop conflict)
    """
    logger.info("=" * 80)
    logger.info("🔵 ADD ITEMS API ENDPOINT CALLED (V2)")
    logger.info(f"User ID: {current_user.id}")
    logger.info(f"Input text:\n{request.text_input}")
    logger.info("=" * 80)

    try:
        logger.info("✅ IntelligentInventoryServiceV2 injected via DI")

        # ✅ CRITICAL FIX: await the async service call
        results = await service.add_items_from_text(current_user.id, request.text_input)

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
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """
    Confirm and add an item that had medium confidence.

    MIGRATED FROM: inventory.py:84-147

    CLEAN ARCHITECTURE V2:
    - Uses IntelligentInventoryServiceV2 (async, dependency injection)
    """
    logger.info("=" * 80)
    logger.info("🔵 CONFIRM ITEM API ENDPOINT CALLED (V2)")
    logger.info(f"User ID: {current_user.id}")
    logger.info(f"Original text: {request.original_text}")
    logger.info(f"Item ID to confirm: {request.item_id}")
    logger.info(f"Quantity: {request.quantity_grams}g")
    logger.info("=" * 80)

    try:
        # ✅ Delegate to service layer - no DB access in API
        logger.info(f"📦 Confirming item ID {request.item_id}, {request.quantity_grams}g")
        result = await service.add_item(
            user_id=current_user.id,
            item_id=request.item_id,
            quantity_grams=request.quantity_grams,
            source="confirmation"
        )

        if not result["success"]:
            error_msg = result.get("error", "Failed to add item")
            # Service returns "Item not found" when item_id is invalid
            if "not found" in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

        logger.info(f"✅ Added to inventory successfully: {result['remaining_quantity']}g")

        logger.info("=" * 80)
        logger.info("🟢 CONFIRM ITEM COMPLETE")
        logger.info(f"Item added: {result['item']} ({result['quantity_added']}g)")
        logger.info("=" * 80)

        return {
            "status": "added",
            "item": result['item'],
            "quantity": f"{result['quantity_added']}g"
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
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """
    Get comprehensive inventory status with AI insights.

    MIGRATED FROM: inventory.py:149-167

    CLEAN ARCHITECTURE V2:
    - Uses IntelligentInventoryServiceV2 (async, dependency injection)
    """
    # Service already returns dict (not dataclass) for API compatibility
    status = await service.get_inventory_status(current_user.id)
    return status


@router.get("/items")
async def get_inventory_items(
    category: Optional[str] = None,
    low_stock_only: bool = False,
    expiring_soon: bool = False,
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """
    Get user's inventory items with filters.

    MIGRATED FROM: inventory.py:169-224

    Clean Architecture V2:
    - API layer delegates to service (no business logic)
    - Service layer contains filtering, calculations, formatting
    - Consistent with other endpoints (GET /status, POST /confirm-item)
    """
    try:
        # ✅ Delegate to service layer - all business logic is in service
        return await service.get_inventory_items(
            user_id=current_user.id,
            category=category,
            low_stock_only=low_stock_only,
            expiring_soon=expiring_soon
        )

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
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """
    Deduct ingredients when user consumes a meal.

    MIGRATED FROM: inventory.py:226-240

    CLEAN ARCHITECTURE V2:
    - Uses IntelligentInventoryServiceV2 (async, dependency injection)
    """
    result = await service.deduct_for_meal(
        user_id=current_user.id,
        recipe_id=request.recipe_id,
        portion_multiplier=request.portion_multiplier
    )

    return result


@router.get("/makeable-recipes")
async def get_makeable_recipes(
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """
    Get recipes user can make with current inventory.

    Returns categorized results:
    - fully_makeable: Recipes with 100% ingredient match
    - partially_makeable: Recipes with 80-99% ingredient match

    MIGRATED FROM: inventory.py:242-264

    CLEAN ARCHITECTURE V2:
    - Uses IntelligentInventoryServiceV2 (async, dependency injection)
    """
    result = await service.get_makeable_recipes(user_id=current_user.id, limit=limit)

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
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """
    Check if user has ingredients for a specific recipe.

    MIGRATED FROM: inventory.py:266-276

    CLEAN ARCHITECTURE V2:
    - Uses IntelligentInventoryServiceV2 (async, dependency injection)
    """
    availability = await service.check_recipe_availability(user_id=current_user.id, recipe_id=recipe_id)

    return availability


@router.delete("/item/{inventory_id}")
async def remove_inventory_item(
    inventory_id: int,
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """
    Remove an item from inventory.

    Clean Architecture V2:
    - Uses service layer for transaction management
    - Service handles commit/rollback
    """
    try:
        deleted = await service.delete_inventory_item(
            user_id=current_user.id,
            inventory_id=inventory_id
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
