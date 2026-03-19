from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging

from app.models.database import User
from app.services.intelligent_inventory_service_v2 import IntelligentInventoryServiceV2
from app.dependencies import get_intelligent_inventory_service_v2, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/inventory/v2", tags=["inventory-v2"])



class AddItemsRequest(BaseModel):
    text_input: str


class ConfirmItemRequest(BaseModel):
    original_text: str
    item_id: int
    quantity_grams: float


class DeductMealRequest(BaseModel):
    recipe_id: int
    portion_multiplier: float = 1.0


class BulkRestockItem(BaseModel):
    item_id: int
    quantity_grams: float


class BulkAddFromRestockRequest(BaseModel):
    items: List[BulkRestockItem] = Field(..., min_length=1)


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
async def add_items_from_text(
    request: AddItemsRequest,
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    try:

        results = await service.add_items_from_text(current_user.id, request.text_input)

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
    try:

        result = await service.add_item(
            user_id=current_user.id,
            item_id=request.item_id,
            quantity_grams=request.quantity_grams,
            source="confirmation"
        )

        if not result["success"]:
            error_msg = result.get("error", "Failed to add item")

            if "not found" in error_msg.lower():
                raise HTTPException(status_code=404, detail=error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

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


@router.post("/bulk-add-from-restock")
async def bulk_add_from_restock(
    request: BulkAddFromRestockRequest,
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    try:
        result = await service.bulk_add_from_restock(
            user_id=current_user.id,
            items=[item.model_dump() for item in request.items]
        )
        return result
    except Exception as e:
        logger.error(f"Error in bulk add from restock: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to bulk add items: {str(e)}"
        )


@router.get("/status")
async def get_inventory_status(
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
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
    result = await service.get_makeable_recipes(user_id=current_user.id, limit=limit)

    total_count = len(result['fully_makeable']) + len(result['partially_makeable'])

    return {
        "count": total_count,
        "fully_makeable": result['fully_makeable'],
        "partially_makeable": result['partially_makeable']
    }


@router.get("/ai-recipes")
async def get_ai_recipes(
    mode: str = Query("goal_adherent", regex="^(goal_adherent|guilt_free)$"),
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    """Generate AI creative recipe suggestions from current inventory."""
    try:
        result = await service.generate_ai_recipes(
            user_id=current_user.id,
            mode=mode
        )
        return result
    except Exception as e:
        logger.error(f"Error generating AI recipes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate AI recipes: {str(e)}"
        )


@router.get("/check-recipe/{recipe_id}")
async def check_recipe_availability(
    recipe_id: int,
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):
    availability = await service.check_recipe_availability(user_id=current_user.id, recipe_id=recipe_id)

    return availability


@router.delete("/item/{inventory_id}")
async def remove_inventory_item(
    inventory_id: int,
    current_user: User = Depends(get_current_user),
    service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2)
):

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
