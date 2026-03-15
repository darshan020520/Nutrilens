import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.interfaces.receipt_repository import IReceiptRepository
from app.models.database import ReceiptScan, ReceiptPendingItem

logger = logging.getLogger(__name__)


class ReceiptRepository(IReceiptRepository):
    def __init__(self, db: Session):
        self.db = db

    def create_receipt_scan(
        self,
        user_id: int,
        s3_url: str,
        status: str = "processing"
    ) -> ReceiptScan:
        try:
            receipt_scan = ReceiptScan(
                user_id=user_id,
                s3_url=s3_url,
                status=status
            )
            self.db.add(receipt_scan)
            self.db.commit()
            self.db.refresh(receipt_scan)

            logger.info(f"Created receipt scan {receipt_scan.id} for user {user_id}")
            return receipt_scan

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating receipt scan: {e}")
            raise

    def get_receipt_scan(
        self,
        receipt_id: int,
        user_id: int
    ) -> Optional[ReceiptScan]:
        try:
            receipt_scan = self.db.query(ReceiptScan).filter(
                ReceiptScan.id == receipt_id,
                ReceiptScan.user_id == user_id
            ).first()

            return receipt_scan

        except Exception as e:
            logger.error(f"Error getting receipt scan {receipt_id}: {e}")
            raise

    def update_receipt_scan_status(
        self,
        receipt_id: int,
        status: str,
        items_count: Optional[int] = None,
        auto_added_count: Optional[int] = None,
        needs_confirmation_count: Optional[int] = None,
        error_message: Optional[str] = None,
        result: Optional[dict] = None
    ) -> Optional[ReceiptScan]:
        try:
            receipt_scan = self.db.query(ReceiptScan).filter(
                ReceiptScan.id == receipt_id
            ).first()

            if not receipt_scan:
                logger.warning(f"Receipt scan {receipt_id} not found for update")
                return None

            receipt_scan.status = status

            if items_count is not None:
                receipt_scan.items_count = items_count

            if auto_added_count is not None:
                receipt_scan.auto_added_count = auto_added_count

            if needs_confirmation_count is not None:
                receipt_scan.needs_confirmation_count = needs_confirmation_count

            if error_message is not None:
                receipt_scan.error_message = error_message

            if result is not None:
                receipt_scan.result = result

            if status == "completed":
                receipt_scan.processed_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(receipt_scan)

            logger.info(f"Updated receipt scan {receipt_id} to status '{status}'")
            return receipt_scan

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating receipt scan {receipt_id}: {e}")
            raise

    def get_receipt_history(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[ReceiptScan]:
        try:
            receipts = self.db.query(ReceiptScan).filter(
                ReceiptScan.user_id == user_id
            ).order_by(ReceiptScan.created_at.desc()).limit(limit).all()

            return receipts

        except Exception as e:
            logger.error(f"Error getting receipt history for user {user_id}: {e}")
            raise


    def get_uploaded_receipts(self, limit: int) -> List[ReceiptScan]:
        try:
            receipts = self.db.query(ReceiptScan).filter(
                ReceiptScan.status == 'uploaded'
            ).with_for_update(skip_locked=True).limit(limit).all()

            return receipts

        except Exception as e:
            logger.error(f"Error fetching uploaded receipts: {e}")
            raise

    def create_pending_item(
        self,
        receipt_scan_id: int,
        item_name: str,
        quantity: float,
        unit: str,
        suggested_item_id: Optional[int] = None,
        confidence: Optional[float] = None,
        canonical_name: Optional[str] = None,
        category: Optional[str] = None,
        fdc_id: Optional[str] = None,
        nutrition_data: Optional[dict] = None,
        enrichment_confidence: Optional[float] = None,
        enrichment_reasoning: Optional[str] = None
    ) -> ReceiptPendingItem:
        try:
            pending_item = ReceiptPendingItem(
                receipt_scan_id=receipt_scan_id,
                item_name=item_name,
                quantity=quantity,
                unit=unit,
                suggested_item_id=suggested_item_id,
                confidence=confidence,
                status='pending',
                canonical_name=canonical_name,
                category=category,
                fdc_id=fdc_id,
                nutrition_data=nutrition_data,
                enrichment_confidence=enrichment_confidence,
                enrichment_reasoning=enrichment_reasoning
            )
            self.db.add(pending_item)
            self.db.commit()
            self.db.refresh(pending_item)

            logger.info(f"Created pending item {pending_item.id} for receipt {receipt_scan_id}")
            return pending_item

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating pending item: {e}")
            raise

    def get_pending_items(
        self,
        receipt_id: int,
        status: str = "pending"
    ) -> List[ReceiptPendingItem]:
        try:
            pending = self.db.query(ReceiptPendingItem).filter(
                ReceiptPendingItem.receipt_scan_id == receipt_id,
                ReceiptPendingItem.status == status
            ).all()

            return pending

        except Exception as e:
            logger.error(f"Error getting pending items for receipt {receipt_id}: {e}")
            raise

    def get_pending_item(
        self,
        pending_item_id: int
    ) -> Optional[ReceiptPendingItem]:
        try:
            pending_item = self.db.query(ReceiptPendingItem).filter(
                ReceiptPendingItem.id == pending_item_id
            ).first()

            return pending_item

        except Exception as e:
            logger.error(f"Error getting pending item {pending_item_id}: {e}")
            raise

    def update_pending_item_status(
        self,
        pending_item_id: int,
        status: str
    ) -> Optional[ReceiptPendingItem]:
        try:
            pending_item = self.db.query(ReceiptPendingItem).filter(
                ReceiptPendingItem.id == pending_item_id
            ).first()

            if not pending_item:
                logger.warning(f"Pending item {pending_item_id} not found for update")
                return None

            pending_item.status = status

            if status == "confirmed":
                pending_item.confirmed_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(pending_item)

            logger.info(f"Updated pending item {pending_item_id} to status '{status}'")
            return pending_item

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating pending item {pending_item_id}: {e}")
            raise

    def bulk_create_pending_items(
        self,
        pending_items: List[ReceiptPendingItem]
    ) -> List[ReceiptPendingItem]:
        try:
            self.db.add_all(pending_items)
            self.db.commit()

            for item in pending_items:
                self.db.refresh(item)

            logger.info(f"Bulk created {len(pending_items)} pending items")
            return pending_items

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error bulk creating pending items: {e}")
            raise
