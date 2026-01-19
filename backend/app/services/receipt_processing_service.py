"""
Receipt Processing Service

Orchestrates the complete receipt processing workflow:
- Validation
- Scanner microservice integration
- Item normalization
- Pending items storage
- Status updates
"""

import logging
import httpx
from typing import Dict, List
from fastapi import HTTPException

from app.repositories.receipt_repository import ReceiptRepository
from app.services.s3_service import S3Service
from app.services.intelligent_inventory_service_v2 import IntelligentInventoryServiceV2

logger = logging.getLogger(__name__)


class ReceiptProcessingService:
    """
    Service layer for receipt processing workflow.

    Orchestrates validation, scanner calls, normalization, and storage.
    """

    def __init__(
        self,
        receipt_repo: ReceiptRepository,
        s3_service: S3Service,
        inventory_service: IntelligentInventoryServiceV2,
        scanner_url: str
    ):
        self.receipt_repo = receipt_repo
        self.s3_service = s3_service
        self.inventory_service = inventory_service
        self.scanner_url = scanner_url

    async def process_receipt(
        self,
        receipt_id: int,
        s3_key: str,
        user_id: int,
        auto_add_threshold: float = 0.75
    ) -> Dict:
        """
        Process uploaded receipt through complete workflow.

        Steps:
        1. Validate receipt (exists, belongs to user, correct status, s3_key matches)
        2. Update status to 'processing'
        3. Generate presigned URL and call scanner microservice
        4. Normalize items via inventory service
        5. Store unknown items in pending items table
        6. Update receipt status to 'completed'
        7. Return results

        Args:
            receipt_id: Receipt scan ID
            s3_key: S3 key for uploaded image
            user_id: User ID for ownership validation
            auto_add_threshold: Confidence threshold for auto-adding items

        Returns:
            Dict with processing results:
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

        Raises:
            HTTPException: On validation errors or processing failures
        """
        # Step 1: Validate receipt exists and belongs to user
        receipt_scan = self.receipt_repo.get_receipt_scan(
            receipt_id=receipt_id,
            user_id=user_id
        )

        if not receipt_scan:
            raise HTTPException(
                status_code=404,
                detail="Receipt not found"
            )

        # Step 2: Verify receipt is in correct status
        if receipt_scan.status != 'uploading':
            raise HTTPException(
                status_code=400,
                detail=f"Receipt cannot be processed. Current status: {receipt_scan.status}"
            )

        # Step 3: Validate s3_key matches what we gave them (security check)
        stored_s3_key = receipt_scan.s3_url.split('.amazonaws.com/')[-1]
        if stored_s3_key != s3_key:
            raise HTTPException(
                status_code=400,
                detail="Invalid s3_key"
            )

        logger.info(f"Validated receipt {receipt_id} for processing")

        # Step 4: Update status to 'processing'
        receipt_scan = self.receipt_repo.update_receipt_scan_status(
            receipt_id=receipt_id,
            status='processing'
        )

        logger.info(f"Updated receipt {receipt_id} to status 'processing'")

        try:
            # Step 5: Generate presigned READ URL for scanner microservice
            presigned_url = self.s3_service.generate_presigned_url(
                s3_key=s3_key,
                expiration=3600
            )

            logger.info(f"Generated presigned READ URL for scanner")

            # Step 6: Call receipt scanner microservice
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.scanner_url}/scan",
                    json={"image_url": presigned_url}
                )
                response.raise_for_status()
                scanner_result = response.json()

            receipt_items = scanner_result.get("items", [])
            logger.info(f"Receipt scanner found {len(receipt_items)} items")

            # Step 7: Normalize and process receipt items
            logger.info(f"Normalizing {len(receipt_items)} items...")
            processing_result = await self.inventory_service.process_receipt_items(
                user_id=user_id,
                receipt_items=receipt_items,
                auto_add_threshold=auto_add_threshold
            )

            auto_added = processing_result["auto_added"]
            needs_confirmation = processing_result["needs_confirmation"]

            logger.info(f"Processing complete: {len(auto_added)} auto-added, {len(needs_confirmation)} need confirmation")

            # Step 8: Store unknown items (no item_id) in pending items table
            unknown_items_count = 0
            for item in needs_confirmation:
                # Check if this is an unknown item (no item_id means not in database)
                if not item.get('item_id'):
                    # Extract data from failed normalization result
                    extracted = item.get('extracted', {})
                    item_name = extracted.get('item_text', '') or item.get('input', 'Unknown')
                    quantity = extracted.get('quantity', 0)
                    unit = extracted.get('unit', '')

                    # Create pending item for admin enrichment
                    self.receipt_repo.create_pending_item(
                        receipt_scan_id=receipt_id,
                        item_name=item_name,
                        quantity=quantity,
                        unit=unit,
                        suggested_item_id=None,  # Unknown item - no suggestion
                        confidence=item.get('confidence', 0.0)
                    )
                    unknown_items_count += 1
                    logger.info(f"Created pending item for unknown: {item_name}")

            if unknown_items_count > 0:
                logger.info(f"Stored {unknown_items_count} unknown items in pending items table")

            # Step 9: Update receipt status to completed
            receipt_scan = self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='completed',
                items_count=len(receipt_items),
                auto_added_count=len(auto_added),
                needs_confirmation_count=len(needs_confirmation)
            )

            logger.info(f"Receipt {receipt_id} processing completed successfully")

            # Step 10: Return results
            return {
                "receipt_id": receipt_scan.id,
                "status": "success",
                "image_url": receipt_scan.s3_url,
                "total_items": len(receipt_items),
                "auto_added_count": len(auto_added),
                "auto_added": auto_added,
                "needs_confirmation_count": len(needs_confirmation),
                "needs_confirmation": needs_confirmation
            }

        except httpx.HTTPError as e:
            # Mark as failed
            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='failed',
                error_message=f"Receipt scanner error: {str(e)}"
            )

            logger.error(f"Receipt scanner HTTP error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Receipt scanner failed: {str(e)}"
            )

        except Exception as e:
            # Mark as failed
            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='failed',
                error_message=str(e)
            )

            logger.error(f"Receipt processing error: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Receipt processing failed: {str(e)}"
            )