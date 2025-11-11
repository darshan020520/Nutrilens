from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
import httpx
import uuid
import os
import tempfile
from typing import List, Dict
from datetime import datetime

from app.models.database import get_db, ReceiptScan, ReceiptPendingItem, User, Item
from app.services.inventory_service import IntelligentInventoryService
from app.services.s3_service import S3Service
from app.services.auth import get_current_user_dependency as get_current_user
from app.core.config import settings
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/receipt", tags=["Receipt Scanner"])


# Request/Response models
class ConfirmItemsRequest(BaseModel):
    items: List[Dict]  # [{"pending_item_id": 1, "action": "add", "item_id": 7, "quantity_grams": 100}]


@router.post("/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete receipt processing flow:
    1. Upload image to S3
    2. Call receipt scanner microservice
    3. Normalize items with LLM
    4. Add to inventory / pending review

    Returns:
        {
            "receipt_id": int,
            "status": "success",
            "image_url": str,
            "total_items": int,
            "auto_added_count": int,
            "auto_added": [...],
            "needs_confirmation_count": int,
            "needs_confirmation": [...]
        }
    """
    try:
        # Step 1: Save temp file
        tmp_dir = tempfile.gettempdir()
        file_extension = os.path.splitext(file.filename)[1] or ".jpg"
        temp_filename = f"{uuid.uuid4()}{file_extension}"
        temp_path = os.path.join(tmp_dir, temp_filename)

        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        logger.info(f"Receipt image saved temporarily: {temp_path}")

        # Step 2: Upload to S3
        s3_service = S3Service()
        s3_key = f"receipts/user_{current_user.id}/{uuid.uuid4()}.jpg"
        s3_url = s3_service.upload_file(temp_path, s3_key)
        presigned_url = s3_service.generate_presigned_url(s3_key, expiration=3600)
        print(f"Presigned URL: {presigned_url}")
        # Clean up temp file
        os.remove(temp_path)
        logger.info(f"Receipt uploaded to S3: {s3_url}")

        # Step 3: Create receipt_scan record
        receipt_scan = ReceiptScan(
            user_id=current_user.id,
            s3_url=s3_url,
            status='processing'
        )
        db.add(receipt_scan)
        db.commit()
        db.refresh(receipt_scan)

        try:
            # Step 4: Call receipt scanner microservice
            print(f"Calling receipt scanner microservice at {settings.receipt_scanner_url}/scan")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{settings.receipt_scanner_url}/scan",
                    json={"image_url": presigned_url}
                )
                print("response for receipt endpoint", response)
                response.raise_for_status()
                scanner_result = response.json()

            receipt_items = scanner_result.get("items", [])
            print(receipt_items)
            logger.info(f"Receipt scanner found {len(receipt_items)} items")

            # Step 5: Normalize items with LLM
            inventory_service = IntelligentInventoryService(db)
            process_result = await inventory_service.process_receipt_items(
                user_id=current_user.id,
                receipt_items=receipt_items,
                auto_add_threshold=settings.receipt_auto_add_threshold
            )

            auto_added = process_result["auto_added"]
            needs_confirmation = process_result["needs_confirmation"]

            logger.info(f"Auto-added: {len(auto_added)}, Needs confirmation: {len(needs_confirmation)}")

            # Step 6: Enrich items that need confirmation
            if needs_confirmation:
                logger.info(f"Enriching {len(needs_confirmation)} unmatched items...")
                from app.services.receipt_item_enricher import ReceiptItemEnricher

                items_list = db.query(Item).all()
                enricher = ReceiptItemEnricher(
                    openai_api_key=settings.openai_api_key,
                    existing_items=items_list
                )

                # Extract item names for enrichment
                item_names = [item.get("original_input", item.get("item_name", "")) for item in needs_confirmation]

                # Batch enrich
                enriched_items = await enricher.enrich_batch(item_names)

                # Save pending items with enrichment data
                for idx, item_data in enumerate(needs_confirmation):
                    enriched = enriched_items[idx] if idx < len(enriched_items) else {}

                    pending_item = ReceiptPendingItem(
                        receipt_scan_id=receipt_scan.id,
                        item_name=item_data.get("original_input", item_data.get("item_name", "Unknown")),
                        quantity=item_data.get("quantity", 0),
                        unit=item_data.get("unit", "unit"),
                        suggested_item_id=item_data.get("item_id"),
                        confidence=item_data.get("confidence", 0),
                        status='pending',
                        # Enrichment data
                        canonical_name=enriched.get("canonical_name"),
                        category=enriched.get("category"),
                        fdc_id=enriched.get("fdc_id"),
                        nutrition_data=enriched.get("nutrition_per_100g"),
                        enrichment_confidence=enriched.get("confidence"),
                        enrichment_reasoning=enriched.get("reasoning")
                    )
                    db.add(pending_item)

                logger.info(f"Enriched and saved {len(needs_confirmation)} pending items")
            else:
                logger.info("No items need enrichment")

            # Step 7: Update receipt_scan status
            receipt_scan.status = 'completed'
            receipt_scan.processed_at = datetime.now()
            receipt_scan.items_count = len(receipt_items)
            receipt_scan.auto_added_count = len(auto_added)
            receipt_scan.needs_confirmation_count = len(needs_confirmation)

            db.commit()

            return {
                "receipt_id": receipt_scan.id,
                "status": "success",
                "image_url": s3_url,
                "total_items": len(receipt_items),
                "auto_added_count": len(auto_added),
                "auto_added": auto_added,
                "needs_confirmation_count": len(needs_confirmation),
                "needs_confirmation": needs_confirmation
            }

        except httpx.HTTPError as e:
            # Mark as failed
            receipt_scan.status = 'failed'
            receipt_scan.error_message = f"Receipt scanner error: {str(e)}"
            db.commit()

            logger.error(f"Receipt scanner HTTP error: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Receipt scanner failed: {str(e)}")

        except Exception as e:
            # Mark as failed
            receipt_scan.status = 'failed'
            receipt_scan.error_message = str(e)
            db.commit()

            logger.error(f"Receipt processing error: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Receipt processing failed: {str(e)}")

    except Exception as e:
        logger.error(f"Receipt upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload receipt: {str(e)}")


@router.get("/{receipt_id}/pending")
async def get_receipt_pending_items(
    receipt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get pending items for a specific receipt with enrichment data

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
    # Verify receipt belongs to user
    receipt_scan = db.query(ReceiptScan).filter(
        ReceiptScan.id == receipt_id,
        ReceiptScan.user_id == current_user.id
    ).first()

    if not receipt_scan:
        raise HTTPException(status_code=404, detail="Receipt not found")

    # Get pending items for this receipt
    pending = db.query(ReceiptPendingItem).filter(
        ReceiptPendingItem.receipt_scan_id == receipt_id,
        ReceiptPendingItem.status == 'pending'
    ).all()

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
    db: Session = Depends(get_db)
):
    """
    Confirm enriched items, seed to items database, and add to inventory

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
    from app.core.config import settings

    inventory_service = IntelligentInventoryService(db)
    embedder = EmbeddingService(api_key=settings.openai_api_key)

    seeded_count = 0
    added_count = 0
    seeded_items = []

    for item_data in request.items:
        pending_id = item_data.get("pending_item_id")
        action = item_data.get("action")

        pending_item = db.query(ReceiptPendingItem).filter(
            ReceiptPendingItem.id == pending_id
        ).first()

        if not pending_item:
            continue

        # Verify ownership
        receipt_scan = db.query(ReceiptScan).filter(
            ReceiptScan.id == pending_item.receipt_scan_id,
            ReceiptScan.user_id == current_user.id
        ).first()

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

            # Add to inventory
            result = inventory_service.add_item(
                user_id=current_user.id,
                item_id=item_id,
                quantity_grams=pending_item.quantity,  # Use original quantity from receipt
                source='receipt_scanner'
            )

            if result.get("success"):
                pending_item.status = 'confirmed'
                pending_item.confirmed_at = datetime.now()
                added_count += 1
                logger.info(f"Added to inventory: {pending_item.canonical_name}")

        elif action == "skip":
            pending_item.status = 'skipped'
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
    db: Session = Depends(get_db)
):
    """
    Get user's receipt scan history

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
    receipts = db.query(ReceiptScan).filter(
        ReceiptScan.user_id == current_user.id
    ).order_by(ReceiptScan.created_at.desc()).limit(limit).all()

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
