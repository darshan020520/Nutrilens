"""
Receipt Processing Service

Orchestrates the complete receipt processing workflow:
- Validation and queuing
- Scanner microservice integration
- Item normalization
- Pending items storage
- Status updates
"""

import logging
import httpx
import time
from typing import Dict, List

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

    def validate_and_queue(
        self,
        receipt_id: int,
        s3_key: str,
        user_id: int
    ) -> int:
        """
        Validate uploaded receipt and mark as ready for processing.

        Steps:
        1. Validate receipt exists and belongs to user
        2. Validate status is 'uploading' (idempotency guard)
        3. Validate s3_key matches stored value (security check)
        4. Update status to 'uploaded' for worker to pick up

        Args:
            receipt_id: Receipt scan ID
            s3_key: S3 key provided by client
            user_id: User ID for ownership validation

        Returns:
            receipt_id

        Raises:
            ValueError: On validation failures
        """
        receipt_scan = self.receipt_repo.get_receipt_scan(
            receipt_id=receipt_id,
            user_id=user_id
        )

        if not receipt_scan:
            raise ValueError("Receipt not found")

        if receipt_scan.status != 'uploading':
            raise ValueError(f"Receipt cannot be processed. Current status: {receipt_scan.status}")

        stored_s3_key = receipt_scan.s3_url.split('.amazonaws.com/')[-1]
        if stored_s3_key != s3_key:
            raise ValueError("Invalid s3_key")

        self.receipt_repo.update_receipt_scan_status(
            receipt_id=receipt_id,
            status='uploaded'
        )

        logger.info(f"Receipt {receipt_id} validated and queued for processing")
        return receipt_id

    async def execute_processing(
        self,
        receipt_id: int,
        user_id: int,
        s3_key: str,
        auto_add_threshold: float = 0.75
    ) -> None:
        """
        Execute full receipt processing. Called by worker task.

        Steps:
        1. Update status to 'processing'
        2. Generate presigned URL and call scanner microservice
        3. Normalize items via inventory service
        4. Store unknown items in pending items table
        5. Update receipt status to 'completed' with full result
        6. On any failure update status to 'failed' with error details

        Args:
            receipt_id: Receipt scan ID
            user_id: User ID
            s3_key: S3 key of uploaded image
            auto_add_threshold: Confidence threshold for auto-adding items
        """
        self.receipt_repo.update_receipt_scan_status(
            receipt_id=receipt_id,
            status='processing'
        )

        logger.info(f"Receipt {receipt_id} processing started")

        try:
            t0 = time.perf_counter()
            presigned_url = self.s3_service.generate_presigned_url(
                s3_key=s3_key,
                expiration=3600
            )
            logger.info("receipt.presigned_url_generated receipt_id=%s duration_ms=%.1f", receipt_id, (time.perf_counter() - t0) * 1000)

            t1 = time.perf_counter()
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.scanner_url}/scan",
                    json={"image_url": presigned_url}
                )
                response.raise_for_status()
                scanner_result = response.json()
            logger.info("receipt.scanner_completed receipt_id=%s items=%s duration_ms=%.1f", receipt_id, len(scanner_result.get("items", [])), (time.perf_counter() - t1) * 1000)

            receipt_items = scanner_result.get("items", [])

        except httpx.HTTPError as e:
            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='failed',
                error_message=f"SCAN_FAILED: {str(e)}"
            )
            logger.error(f"Receipt {receipt_id} scan failed: {e}")
            return

        except Exception as e:
            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='failed',
                error_message=f"SCAN_FAILED: {str(e)}"
            )
            logger.error(f"Receipt {receipt_id} scan error: {e}")
            return

        try:
            t2 = time.perf_counter()
            processing_result = await self.inventory_service.process_receipt_items(
                user_id=user_id,
                receipt_items=receipt_items,
                auto_add_threshold=auto_add_threshold
            )

            auto_added = processing_result["auto_added"]
            needs_confirmation = processing_result["needs_confirmation"]

            logger.info("receipt.normalization_completed receipt_id=%s auto_added=%s needs_confirmation=%s duration_ms=%.1f", receipt_id, len(auto_added), len(needs_confirmation), (time.perf_counter() - t2) * 1000)

            unknown_items_count = 0
            for item in needs_confirmation:
                if not item.get('item_id'):
                    extracted = item.get('extracted', {})
                    item_name = extracted.get('item_text', '') or item.get('input', 'Unknown')
                    quantity = extracted.get('quantity', 0)
                    unit = extracted.get('unit', '')

                    self.receipt_repo.create_pending_item(
                        receipt_scan_id=receipt_id,
                        item_name=item_name,
                        quantity=quantity,
                        unit=unit,
                        suggested_item_id=None,
                        confidence=item.get('confidence', 0.0)
                    )
                    unknown_items_count += 1

            if unknown_items_count > 0:
                logger.info(f"Receipt {receipt_id}: stored {unknown_items_count} unknown items")

            receipt_scan = self.receipt_repo.get_receipt_scan(
                receipt_id=receipt_id,
                user_id=user_id
            )

            full_result = {
                "receipt_id": receipt_id,
                "status": "completed",
                "image_url": receipt_scan.s3_url,
                "total_items": len(receipt_items),
                "auto_added_count": len(auto_added),
                "auto_added": auto_added,
                "needs_confirmation_count": len(needs_confirmation),
                "needs_confirmation": needs_confirmation
            }

            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='completed',
                items_count=len(receipt_items),
                auto_added_count=len(auto_added),
                needs_confirmation_count=len(needs_confirmation),
                result=full_result
            )

            logger.info(f"Receipt {receipt_id} processing completed successfully")

        except Exception as e:
            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='failed',
                error_message=f"PROCESSING_FAILED: {str(e)}"
            )
            logger.error(f"Receipt {receipt_id} post-processing error: {e}")
