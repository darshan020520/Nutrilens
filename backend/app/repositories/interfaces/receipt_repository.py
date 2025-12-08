"""
Receipt Repository Interface

Defines data access operations for receipt scanning and processing.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime

from app.models.database import ReceiptScan, ReceiptPendingItem


class IReceiptRepository(ABC):
    """
    Interface for receipt data access operations.

    Responsibilities:
    - CRUD operations for ReceiptScan
    - CRUD operations for ReceiptPendingItem
    - Query operations for history and pending items

    This is a DATA ACCESS layer - NO business logic here.
    """

    # =========================================================================
    # RECEIPT SCAN OPERATIONS
    # =========================================================================

    @abstractmethod
    def create_receipt_scan(
        self,
        user_id: int,
        s3_url: str,
        status: str = "processing"
    ) -> ReceiptScan:
        """
        Create a new receipt scan record.

        Args:
            user_id: User ID
            s3_url: S3 URL of uploaded receipt image
            status: Initial status (default: "processing")

        Returns:
            Created ReceiptScan with ID populated and refreshed from DB
        """
        pass

    @abstractmethod
    def get_receipt_scan(
        self,
        receipt_id: int,
        user_id: int
    ) -> Optional[ReceiptScan]:
        """
        Get receipt scan by ID with user validation.

        Args:
            receipt_id: Receipt scan ID
            user_id: User ID for ownership validation

        Returns:
            ReceiptScan if found and belongs to user, None otherwise
        """
        pass

    @abstractmethod
    def update_receipt_scan_status(
        self,
        receipt_id: int,
        status: str,
        items_count: Optional[int] = None,
        auto_added_count: Optional[int] = None,
        needs_confirmation_count: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> Optional[ReceiptScan]:
        """
        Update receipt scan status and counts.

        CRITICAL: Returns fresh ReceiptScan object after update.

        Args:
            receipt_id: Receipt scan ID
            status: New status ("processing", "completed", "failed")
            items_count: Total items found
            auto_added_count: Items auto-added to inventory
            needs_confirmation_count: Items needing confirmation
            error_message: Error message if failed

        Returns:
            Updated ReceiptScan with fresh data from DB, None if not found
        """
        pass

    @abstractmethod
    def get_receipt_history(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[ReceiptScan]:
        """
        Get user's receipt scan history.

        Args:
            user_id: User ID
            limit: Maximum number of receipts to return

        Returns:
            List of receipt scans ordered by created_at DESC
        """
        pass

    # =========================================================================
    # PENDING ITEM OPERATIONS
    # =========================================================================

    @abstractmethod
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
        """
        Create a pending item for user confirmation.

        Args:
            receipt_scan_id: Receipt scan ID
            item_name: Original item name from receipt
            quantity: Quantity
            unit: Unit of measurement
            suggested_item_id: Suggested item ID from normalization
            confidence: Normalization confidence
            canonical_name: Enriched canonical name
            category: Enriched category
            fdc_id: FDC ID from enrichment
            nutrition_data: Nutrition data from enrichment
            enrichment_confidence: Enrichment confidence score
            enrichment_reasoning: Enrichment reasoning

        Returns:
            Created ReceiptPendingItem with ID populated and refreshed from DB
        """
        pass

    @abstractmethod
    def get_pending_items(
        self,
        receipt_id: int,
        status: str = "pending"
    ) -> List[ReceiptPendingItem]:
        """
        Get pending items for a receipt.

        Args:
            receipt_id: Receipt scan ID
            status: Item status filter (default: "pending")

        Returns:
            List of pending items
        """
        pass

    @abstractmethod
    def get_pending_item(
        self,
        pending_item_id: int
    ) -> Optional[ReceiptPendingItem]:
        """
        Get a specific pending item by ID.

        Args:
            pending_item_id: Pending item ID

        Returns:
            ReceiptPendingItem if found, None otherwise
        """
        pass

    @abstractmethod
    def update_pending_item_status(
        self,
        pending_item_id: int,
        status: str
    ) -> Optional[ReceiptPendingItem]:
        """
        Update pending item status.

        CRITICAL: Returns fresh ReceiptPendingItem object after update.

        Args:
            pending_item_id: Pending item ID
            status: New status ("pending", "confirmed", "skipped")

        Returns:
            Updated ReceiptPendingItem with fresh data from DB, None if not found
        """
        pass

    @abstractmethod
    def bulk_create_pending_items(
        self,
        pending_items: List[ReceiptPendingItem]
    ) -> List[ReceiptPendingItem]:
        """
        Create multiple pending items in one transaction.

        Args:
            pending_items: List of ReceiptPendingItem entities

        Returns:
            List of created items with IDs populated and refreshed from DB
        """
        pass