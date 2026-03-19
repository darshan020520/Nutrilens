from app.infrastructure.normalization.adapters.embedding_adapter import EmbeddingAdapter
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel
import logging

from app.models.database import get_async_db, User, Item
from app.services.intelligent_inventory_service_v2 import IntelligentInventoryServiceV2
from app.services.s3_service import S3Service
from app.core.config import settings
from app.repositories.receipt_repository import ReceiptRepository
from app.dependencies import (
    get_intelligent_inventory_service_v2,
    get_openai_embedding_adapter,
    get_receipt_repository,
    get_current_user,
    get_s3_service,
    get_receipt_processing_service
)
from app.services.receipt_processing_service import ReceiptProcessingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/receipt/v2", tags=["receipt-v2"])

class InitiateUploadRequest(BaseModel):
    """Request for initiating receipt upload"""
    filename: str
    content_type: str = "image/jpeg"


class InitiateUploadResponse(BaseModel):
    """Response for initiate upload"""
    receipt_id: int
    presigned_url: str
    s3_key: str
    expires_in: int


class ProcessReceiptRequest(BaseModel):
    """Request for processing uploaded receipt"""
    receipt_id: int
    s3_key: str


class ProcessReceiptResponse(BaseModel):
    """Response for process receipt — receipt queued for async processing"""
    receipt_id: int
    status: str


class ReceiptStatusResponse(BaseModel):
    """Response for receipt status polling"""
    receipt_id: int
    status: str
    result: Optional[Dict] = None
    error_message: Optional[str] = None


class ConfirmItemsRequest(BaseModel):
    """Request for confirming enriched items"""
    items: List[Dict]  # [{"pending_item_id": 1, "action": "confirm"/"skip"}]

@router.post("/initiate", response_model=InitiateUploadResponse)
async def initiate_receipt_upload(
    request: InitiateUploadRequest,
    current_user: User = Depends(get_current_user),
    receipt_repo: ReceiptRepository = Depends(get_receipt_repository),
    s3_service: S3Service = Depends(get_s3_service)
):

    try:
        s3_key = f"receipts/user_{current_user.id}/{uuid.uuid4()}.jpg"

        s3_url = f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{s3_key}"
        receipt_scan = await receipt_repo.create_receipt_scan(
            user_id=current_user.id,
            s3_url=s3_url,
            status='uploading'
        )

        presigned_url = s3_service.generate_presigned_upload_url(
            s3_key=s3_key,
            content_type=request.content_type,
            expiration=3600
        )

        logger.info(f"Initiated receipt upload {receipt_scan.id} for user {current_user.id}")

        return InitiateUploadResponse(
            receipt_id=receipt_scan.id,
            presigned_url=presigned_url,
            s3_key=s3_key,
            expires_in=3600
        )

    except Exception as e:
        logger.error(f"Error initiating receipt upload: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate upload: {str(e)}"
        )


@router.post("/process", response_model=ProcessReceiptResponse)
async def process_receipt(
    request: ProcessReceiptRequest,
    current_user: User = Depends(get_current_user),
    receipt_service: ReceiptProcessingService = Depends(get_receipt_processing_service)
):
    try:
        receipt_id = receipt_service.validate_and_queue(
            receipt_id=request.receipt_id,
            s3_key=request.s3_key,
            user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse(
        status_code=202,
        content={"receipt_id": receipt_id, "status": "uploaded"}
    )


@router.get("/{receipt_id}/status", response_model=ReceiptStatusResponse)
async def get_receipt_status(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    receipt_repo: ReceiptRepository = Depends(get_receipt_repository)
):
    receipt_scan = await receipt_repo.get_receipt_scan(
        receipt_id=receipt_id,
        user_id=current_user.id
    )

    if not receipt_scan:
        raise HTTPException(status_code=404, detail="Receipt not found")

    return ReceiptStatusResponse(
        receipt_id=receipt_scan.id,
        status=receipt_scan.status,
        result=receipt_scan.result,
        error_message=receipt_scan.error_message
    )


@router.get("/{receipt_id}/pending")
async def get_receipt_pending_items(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    receipt_repo: ReceiptRepository = Depends(get_receipt_repository)
):

    receipt_scan = await receipt_repo.get_receipt_scan(
        receipt_id=receipt_id,
        user_id=current_user.id
    )

    if not receipt_scan:
        raise HTTPException(status_code=404, detail="Receipt not found")

    pending = await receipt_repo.get_pending_items(
        receipt_id=receipt_id,
        status='pending'
    )

    return {
        "receipt_id": receipt_id,
        "count": len(pending),
        "items": [
            {
                "id": item.id,
                "item_name": item.item_name,
                "quantity": item.quantity,
                "unit": item.unit,
                # Enrichment data
                "canonical_name": item.canonical_name,
                "category": item.category,
                "fdc_id": item.fdc_id,
                "nutrition_data": item.nutrition_data,
                "enrichment_confidence": item.enrichment_confidence,
                "enrichment_reasoning": item.enrichment_reasoning
            }
            for item in pending
        ]
    }


@router.post("/confirm-and-seed")
async def confirm_and_seed_items(
    request: ConfirmItemsRequest,
    current_user: User = Depends(get_current_user),
    receipt_repo: ReceiptRepository = Depends(get_receipt_repository),
    inventory_service: IntelligentInventoryServiceV2 = Depends(get_intelligent_inventory_service_v2),
    embedding_adapter: EmbeddingAdapter = Depends(get_openai_embedding_adapter),
    db: AsyncSession = Depends(get_async_db)
):

    seeded_count = 0
    added_count = 0
    seeded_items = []

    for item_data in request.items:
        pending_id = item_data.get("pending_item_id")
        action = item_data.get("action")

        pending_item = await receipt_repo.get_pending_item(pending_id)

        if not pending_item:
            continue

        receipt_scan = await receipt_repo.get_receipt_scan(
            receipt_id=pending_item.receipt_scan_id,
            user_id=current_user.id
        )

        if not receipt_scan:
            continue

        if action == "confirm":
            if not pending_item.canonical_name or not pending_item.nutrition_data:
                logger.warning(f"Skipping {pending_item.item_name}: missing enrichment data")
                continue

            existing_result = await db.execute(
                select(Item).where(Item.canonical_name == pending_item.canonical_name)
            )
            existing_item = existing_result.scalars().first()

            if existing_item:
                item_id = existing_item.id
                logger.info(f"Item '{pending_item.canonical_name}' already exists (ID: {item_id})")
            else:

                embedding_text = f"{pending_item.canonical_name} {pending_item.category}"
                embedding = await embedding_adapter.get_embedding(embedding_text)
                embedding_json = await embedding_adapter.embedding_to_db_string(embedding)

                new_item = Item(
                    canonical_name=pending_item.canonical_name,
                    aliases=[pending_item.item_name],
                    category=pending_item.category,
                    unit="g",
                    fdc_id=pending_item.fdc_id,
                    nutrition_per_100g=pending_item.nutrition_data,
                    is_staple=False,
                    embedding=embedding_json,
                    embedding_model="text-embedding-3-small",
                    embedding_version=1,
                    source="receipt_enrichment"
                )
                db.add(new_item)
                await db.flush()

                item_id = new_item.id
                seeded_count += 1
                seeded_items.append({
                    "canonical_name": pending_item.canonical_name,
                    "category": pending_item.category,
                    "item_id": item_id
                })
                logger.info(f"Seeded new item: {pending_item.canonical_name} (ID: {item_id})")

            result = await inventory_service.add_item(
                user_id=current_user.id,
                item_id=item_id,
                quantity_grams=pending_item.quantity,
                source='receipt_scanner'
            )

            if result.get("success"):

                await receipt_repo.update_pending_item_status(
                    pending_item_id=pending_id,
                    status='confirmed'
                )
                added_count += 1
                logger.info(f"Added to inventory: {pending_item.canonical_name}")

        elif action == "skip":

            await receipt_repo.update_pending_item_status(
                pending_item_id=pending_id,
                status='skipped'
            )
            logger.info(f"Skipped pending item: {pending_item.item_name}")

    await db.commit()

    return {
        "status": "success",
        "seeded_count": seeded_count,
        "added_count": added_count,
        "seeded_items": seeded_items
    }


@router.get("/history")
async def get_receipt_history(
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    receipt_repo: ReceiptRepository = Depends(get_receipt_repository)
):

    receipts = await receipt_repo.get_receipt_history(
        user_id=current_user.id,
        limit=limit
    )

    return {
        "count": len(receipts),
        "receipts": [
            {
                "id": receipt.id,
                "s3_url": receipt.s3_url,
                "status": receipt.status,
                "items_count": receipt.items_count,
                "auto_added_count": receipt.auto_added_count,
                "needs_confirmation_count": receipt.needs_confirmation_count,
                "created_at": receipt.created_at.isoformat() if receipt.created_at else None,
                "processed_at": receipt.processed_at.isoformat() if receipt.processed_at else None,
                "error_message": receipt.error_message
            }
            for receipt in receipts
        ]
    }
