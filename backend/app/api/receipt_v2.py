"""
Receipt API Endpoints V2 - Clean Architecture

Provides receipt scanning and processing endpoints using repository pattern.

MIGRATED FROM: receipt.py
USES:
- ReceiptRepository for data access
- IntelligentInventoryService for item normalization
- S3Service, ReceiptItemEnricher, EmbeddingService for business logic
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from typing import List, Dict
from datetime import datetime
from pydantic import BaseModel
import logging

from app.models.database import get_db, User, Item
from app.services.inventory_service import IntelligentInventoryService
from app.services.s3_service import S3Service
from app.core.config import settings
from app.repositories.receipt_repository import ReceiptRepository
from app.dependencies import (
    get_receipt_repository,
    get_current_user,
    get_s3_service,
    get_receipt_processing_service
)
from app.services.receipt_processing_service import ReceiptProcessingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/receipt/v2", tags=["receipt-v2"])


# ===== REQUEST/RESPONSE SCHEMAS =====

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
    """Response for process receipt"""
    receipt_id: int
    status: str
    image_url: str
    total_items: int
    auto_added_count: int
    auto_added: List[Dict]
    needs_confirmation_count: int
    needs_confirmation: List[Dict]


class ConfirmItemsRequest(BaseModel):
    """Request for confirming enriched items"""
    items: List[Dict]  # [{"pending_item_id": 1, "action": "confirm"/"skip"}]


# ===== ENDPOINTS =====

@router.post("/initiate", response_model=InitiateUploadResponse)
async def initiate_receipt_upload(
    request: InitiateUploadRequest,
    current_user: User = Depends(get_current_user),
    receipt_repo: ReceiptRepository = Depends(get_receipt_repository),
    s3_service: S3Service = Depends(get_s3_service)
):
    """
    Step 1: Generate presigned URL for client-side upload.

    Client will upload file directly to S3 using the presigned URL,
    then call /process endpoint to trigger processing.

    Args:
        request: Upload initiation request with filename and content type
        current_user: Authenticated user
        receipt_repo: Receipt repository (injected)
        s3_service: S3 service (injected)

    Returns:
        InitiateUploadResponse with presigned URL and receipt ID
    """
    try:
        # Generate unique S3 key
        s3_key = f"receipts/user_{current_user.id}/{uuid.uuid4()}.jpg"

        # Create receipt record with status 'uploading'
        s3_url = f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{s3_key}"
        receipt_scan = receipt_repo.create_receipt_scan(
            user_id=current_user.id,
            s3_url=s3_url,
            status='uploading'
        )

        # Generate presigned URL for client upload
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
    """
    Step 2: Process uploaded receipt after client has uploaded to S3.

    Validates the receipt, calls scanner microservice, normalizes items,
    and stores unknown items for admin enrichment.

    Args:
        request: Process request with receipt_id and s3_key
        current_user: Authenticated user
        receipt_service: Receipt processing service (injected)

    Returns:
        ProcessReceiptResponse with processing results
    """
    result = await receipt_service.process_receipt(
        receipt_id=request.receipt_id,
        s3_key=request.s3_key,
        user_id=current_user.id
    )

    return ProcessReceiptResponse(**result)


@router.get("/{receipt_id}/pending")
async def get_receipt_pending_items(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    receipt_repo: ReceiptRepository = Depends(get_receipt_repository)
):
    """
    Get pending items for a specific receipt with enrichment data.

    MIGRATED FROM: receipt.py:205-267

    Uses:
    - ReceiptRepository for data access (receipt validation, pending items query)

    Returns:
        {
            "receipt_id": int,
            "count": int,
            "items": [
                {
                    "id": int,
                    "item_name": str,  # Original from receipt
                    "quantity": float,
                    "unit": str,
                    "canonical_name": str,  # Normalized name
                    "category": str,
                    "nutrition_data": {...},
                    "enrichment_confidence": float,
                    "enrichment_reasoning": str
                }
            ]
        }
    """
    # Verify receipt belongs to user - using repository
    receipt_scan = receipt_repo.get_receipt_scan(
        receipt_id=receipt_id,
        user_id=current_user.id
    )

    if not receipt_scan:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Get pending items for this receipt - using repository
    pending = receipt_repo.get_pending_items(
        receipt_id=receipt_id,
        status='pending'
    )

    return {
        "receipt_id": receipt_id,
        "count": len(pending),
        "items": [
            {
                "id": item.id,
                "item_name": item.item_name,  # Original from receipt
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
    db: Session = Depends(get_db)
):
    """
    Confirm enriched items, seed to items database, and add to inventory.

    MIGRATED FROM: receipt.py:270-397

    Uses:
    - ReceiptRepository for pending item data access
    - EmbeddingService for generating item embeddings (business logic)
    - IntelligentInventoryService for adding to inventory (business logic)

    Request body:
        {
            "items": [
                {
                    "pending_item_id": 1,
                    "action": "confirm"  # or "skip"
                }
            ]
        }

    Returns:
        {
            "status": "success",
            "seeded_count": int,
            "added_count": int,
            "seeded_items": [...]
        }
    """
    from app.services.embedding_service import EmbeddingService

    inventory_service = IntelligentInventoryService(db)
    embedder = EmbeddingService(api_key=settings.openai_api_key)

    seeded_count = 0
    added_count = 0
    seeded_items = []

    for item_data in request.items:
        pending_id = item_data.get("pending_item_id")
        action = item_data.get("action")

        # Get pending item - using repository
        pending_item = receipt_repo.get_pending_item(pending_id)

        if not pending_item:
            continue

        # Verify ownership - using repository
        receipt_scan = receipt_repo.get_receipt_scan(
            receipt_id=pending_item.receipt_scan_id,
            user_id=current_user.id
        )

        if not receipt_scan:
            continue

        if action == "confirm":
            # Check if enrichment data exists
            if not pending_item.canonical_name or not pending_item.nutrition_data:
                logger.warning(f"Skipping {pending_item.item_name}: missing enrichment data")
                continue

            # Check if item already exists
            existing_item = db.query(Item).filter(
                Item.canonical_name == pending_item.canonical_name
            ).first()

            if existing_item:
                item_id = existing_item.id
                logger.info(f"Item '{pending_item.canonical_name}' already exists (ID: {item_id})")
            else:
                # Create new item in database
                embedding_text = f"{pending_item.canonical_name} {pending_item.category}"
                embedding = await embedder.get_embedding(embedding_text)
                embedding_json = embedder.embedding_to_db_string(embedding)

                new_item = Item(
                    canonical_name=pending_item.canonical_name,
                    aliases=[pending_item.item_name],  # Add original name as alias
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
                db.flush()  # Get the ID

                item_id = new_item.id
                seeded_count += 1
                seeded_items.append({
                    "canonical_name": pending_item.canonical_name,
                    "category": pending_item.category,
                    "item_id": item_id
                })
                logger.info(f"Seeded new item: {pending_item.canonical_name} (ID: {item_id})")

            # Add to inventory - using inventory service
            result = inventory_service.add_item(
                user_id=current_user.id,
                item_id=item_id,
                quantity_grams=pending_item.quantity,  # Use original quantity from receipt
                source='receipt_scanner'
            )

            if result.get("success"):
                # Update pending item status - using repository
                receipt_repo.update_pending_item_status(
                    pending_item_id=pending_id,
                    status='confirmed'
                )
                added_count += 1
                logger.info(f"Added to inventory: {pending_item.canonical_name}")

        elif action == "skip":
            # Update pending item status - using repository
            receipt_repo.update_pending_item_status(
                pending_item_id=pending_id,
                status='skipped'
            )
            logger.info(f"Skipped pending item: {pending_item.item_name}")

    db.commit()

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
    """
    Get user's receipt scan history.

    MIGRATED FROM: receipt.py:400-446

    Uses:
    - ReceiptRepository for history query

    Returns:
        {
            "count": int,
            "receipts": [
                {
                    "id": int,
                    "s3_url": str,
                    "status": str,
                    "items_count": int,
                    "auto_added_count": int,
                    "needs_confirmation_count": int,
                    "created_at": str,
                    "processed_at": str
                }
            ]
        }
    """
    # Get receipt history - using repository
    receipts = receipt_repo.get_receipt_history(
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
