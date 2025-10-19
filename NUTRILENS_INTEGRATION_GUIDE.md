# Complete End-to-End Integration Guide: Receipt Scanner + Nutrilens

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                          NUTRILENS (Port 8000)                          │
│                                                                          │
│  Frontend → API → S3 Upload → Receipt Scanner → Normalizer → Database  │
└────────────────────────────────────────────────────────────────────────┘
                                    ↓
                                    ↓
┌────────────────────────────────────────────────────────────────────────┐
│                    RECEIPT SCANNER (Port 8001)                          │
│                         Microservice                                    │
│                                                                          │
│              Download S3 → Process → Return Items                       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Complete Flow Diagram

```
USER UPLOADS IMAGE
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: Nutrilens Frontend (React/Mobile)                    │
│ - User selects receipt image                                 │
│ - POST /api/receipt/upload (multipart/form-data)            │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 2: Nutrilens Backend - S3 Upload                        │
│ Route: POST /api/receipt/upload                              │
│                                                               │
│ 1. Receive file upload                                       │
│ 2. Generate unique filename: receipts/user_123/uuid.jpg     │
│ 3. Upload to S3 bucket: nutrilens-receipts                  │
│ 4. Get public/signed URL                                     │
│ 5. Save to DB: receipt_scans table                          │
│    - user_id, s3_url, status='processing'                   │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 3: Call Receipt Scanner Microservice                    │
│ POST http://localhost:8001/scan                              │
│ Body: {"image_url": "https://s3.../receipts/user_123/..."}  │
│                                                               │
│ Receipt Scanner:                                              │
│ 1. Download image from S3                                    │
│ 2. Preprocess (cv2)                                          │
│ 3. Run OCR Pipeline (Tesseract + GPT-4o)                    │
│ 4. Run Vision Pipeline (GPT-4o-vision)                      │
│ 5. Intelligent Merge (vision-first)                         │
│                                                               │
│ Returns:                                                      │
│ {                                                            │
│   "items": [                                                 │
│     {"item_name": "Onion", "quantity": 2, "unit": "kg"},   │
│     {"item_name": "Milk", "quantity": 1, "unit": "L"}      │
│   ],                                                         │
│   "metadata": {                                              │
│     "merge_strategy": "vision_primary",                     │
│     "agreement_score": 0.85                                 │
│   }                                                          │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 4: Nutrilens - Item Normalization                       │
│ Using: IntelligentItemNormalizer (NEW)                       │
│                                                               │
│ 1. Load user's inventory items from DB                       │
│ 2. Initialize normalizer with items + OpenAI key            │
│ 3. Call: normalizer.normalize_batch(receipt_items)          │
│                                                               │
│ For each item:                                               │
│   a) Try traditional matching (exact, alias, fuzzy)         │
│   b) If high confidence (≥0.85) → Convert to grams         │
│   c) If low confidence (<0.85) → Queue for LLM             │
│                                                               │
│ ONE LLM call for all low-confidence items:                  │
│   - Match to inventory items                                │
│   - Convert unknown units to grams                          │
│                                                               │
│ Returns:                                                      │
│ [                                                            │
│   {                                                          │
│     "item_id": 1,                                           │
│     "item_name": "onion",                                   │
│     "quantity_grams": 2000,                                 │
│     "confidence": 1.0,                                      │
│     "matched_on": "exact"                                   │
│   },                                                         │
│   {                                                          │
│     "item_id": 18,                                          │
│     "item_name": "milk",                                    │
│     "quantity_grams": 1030,                                 │
│     "confidence": 0.95,                                     │
│     "matched_on": "alias"                                   │
│   }                                                          │
│ ]                                                            │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 5: Categorize by Confidence                             │
│                                                               │
│ Auto-Add Threshold: 0.75 (configurable)                     │
│                                                               │
│ High Confidence (≥0.75):                                     │
│   → Add directly to user_inventory                          │
│   → Source: 'receipt_scanner'                               │
│                                                               │
│ Low Confidence (<0.75):                                      │
│   → Save to receipt_pending_items table                     │
│   → Status: 'needs_confirmation'                            │
│   → User will review later                                  │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 6: Update Database                                      │
│                                                               │
│ A) Update receipt_scans:                                     │
│    - status = 'completed'                                    │
│    - processed_at = now()                                    │
│    - items_count = total items                              │
│    - auto_added_count = high confidence count               │
│                                                               │
│ B) Insert into user_inventory (auto-added):                 │
│    - user_id, item_id, quantity_grams                       │
│    - purchase_date = now()                                   │
│    - source = 'receipt_scanner'                             │
│                                                               │
│ C) Insert into receipt_pending_items (low confidence):      │
│    - receipt_scan_id, item_name, quantity, unit            │
│    - suggested_item_id (if any match)                       │
│    - confidence, status = 'pending'                         │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 7: Return Response to Frontend                          │
│ {                                                            │
│   "receipt_id": 123,                                        │
│   "status": "success",                                      │
│   "image_url": "https://s3.../...",                        │
│   "auto_added_count": 8,                                    │
│   "auto_added": [...],                                      │
│   "needs_confirmation_count": 3,                            │
│   "needs_confirmation": [...]                               │
│ }                                                            │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 8: Frontend Display                                     │
│                                                               │
│ Success Message:                                             │
│ ✅ Receipt processed successfully!                           │
│ ✅ 8 items added to inventory                               │
│ ⚠️  3 items need your review                                │
│                                                               │
│ [View Added Items] [Review Pending Items]                   │
└──────────────────────────────────────────────────────────────┘
       ↓
┌──────────────────────────────────────────────────────────────┐
│ STEP 9: User Reviews Pending Items (Optional)                │
│                                                               │
│ Frontend shows list:                                         │
│ - Item: "Herb Mint" (100g)                                  │
│   Matched to: mint (80% confidence)                         │
│   [✓ Add to Inventory] [✗ Skip] [Edit]                     │
│                                                               │
│ User clicks "Add" → POST /api/receipt/confirm               │
│ Body: [{"item_id": 7, "quantity_grams": 100}]              │
│                                                               │
│ Backend adds to user_inventory                              │
└──────────────────────────────────────────────────────────────┘
```

---

## Component 1: Receipt Scanner Microservice

### Configuration

**Port**: 8001 (to avoid conflict with Nutrilens on 8000)

Update `uvicorn` command or add to code:
```python
# If running directly:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

Or run with:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### API Endpoint (Already Added)

**POST /scan**

Request:
```json
{
  "image_url": "https://s3.amazonaws.com/nutrilens-receipts/user_123/uuid.jpg"
}
```

Response:
```json
{
  "items": [
    {
      "item_name": "Onion",
      "quantity": 2.0,
      "unit": "kg"
    },
    {
      "item_name": "Milk",
      "quantity": 1.0,
      "unit": "L"
    }
  ],
  "metadata": {
    "merge_strategy": "vision_primary",
    "agreement_score": 0.85,
    "ocr_items_count": 10,
    "vision_items_count": 11
  }
}
```

---

## Component 2: Nutrilens Changes

### 2.1: Database Schema

Add these tables to Nutrilens:

```sql
-- Track all receipt scans
CREATE TABLE receipt_scans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    s3_url TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'processing', -- processing, completed, failed
    items_count INTEGER,
    auto_added_count INTEGER,
    needs_confirmation_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP,
    error_message TEXT,
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Store items needing user confirmation
CREATE TABLE receipt_pending_items (
    id SERIAL PRIMARY KEY,
    receipt_scan_id INTEGER NOT NULL REFERENCES receipt_scans(id),
    item_name TEXT NOT NULL,
    quantity FLOAT NOT NULL,
    unit VARCHAR(20) NOT NULL,
    suggested_item_id INTEGER REFERENCES items(id), -- Best match from normalizer
    confidence FLOAT,
    status VARCHAR(20) DEFAULT 'pending', -- pending, confirmed, skipped
    created_at TIMESTAMP DEFAULT NOW(),
    confirmed_at TIMESTAMP,
    CONSTRAINT fk_receipt FOREIGN KEY (receipt_scan_id) REFERENCES receipt_scans(id) ON DELETE CASCADE
);

CREATE INDEX idx_receipt_scans_user ON receipt_scans(user_id);
CREATE INDEX idx_pending_items_receipt ON receipt_pending_items(receipt_scan_id);
CREATE INDEX idx_pending_items_status ON receipt_pending_items(status);
```

**SQLAlchemy Models** (add to `nutrilens/app/models.py`):

```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

class ReceiptScan(Base):
    __tablename__ = "receipt_scans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    s3_url = Column(Text, nullable=False)
    status = Column(String(20), default="processing")
    items_count = Column(Integer)
    auto_added_count = Column(Integer)
    needs_confirmation_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    processed_at = Column(DateTime)
    error_message = Column(Text)

    # Relationships
    user = relationship("User", back_populates="receipt_scans")
    pending_items = relationship("ReceiptPendingItem", back_populates="receipt_scan", cascade="all, delete-orphan")


class ReceiptPendingItem(Base):
    __tablename__ = "receipt_pending_items"

    id = Column(Integer, primary_key=True, index=True)
    receipt_scan_id = Column(Integer, ForeignKey("receipt_scans.id", ondelete="CASCADE"), nullable=False)
    item_name = Column(Text, nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(20), nullable=False)
    suggested_item_id = Column(Integer, ForeignKey("items.id"))
    confidence = Column(Float)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.now)
    confirmed_at = Column(DateTime)

    # Relationships
    receipt_scan = relationship("ReceiptScan", back_populates="pending_items")
    suggested_item = relationship("Item")
```

### 2.2: S3 Configuration

**Add to `nutrilens/app/config.py`:**

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Existing config...

# S3 Configuration for receipts
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "nutrilens-receipts")

# Receipt Scanner Microservice
RECEIPT_SCANNER_URL = os.getenv("RECEIPT_SCANNER_URL", "http://localhost:8001")

# OpenAI for normalizer
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Auto-add threshold
RECEIPT_AUTO_ADD_THRESHOLD = float(os.getenv("RECEIPT_AUTO_ADD_THRESHOLD", "0.75"))
```

**Add to `nutrilens/.env`:**

```env
# S3 Configuration
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=nutrilens-receipts

# Receipt Scanner Microservice
RECEIPT_SCANNER_URL=http://localhost:8001

# OpenAI API
OPENAI_API_KEY=sk-proj-...

# Receipt processing
RECEIPT_AUTO_ADD_THRESHOLD=0.75
```

### 2.3: S3 Service

**Create `nutrilens/app/services/s3_service.py`:**

```python
import boto3
from botocore.exceptions import ClientError
import logging
from app.config import AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET_NAME

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        self.bucket_name = S3_BUCKET_NAME

    def upload_file(self, file_path: str, s3_key: str) -> str:
        """
        Upload file to S3 and return public URL

        Args:
            file_path: Local file path
            s3_key: S3 object key (e.g., 'receipts/user_123/uuid.jpg')

        Returns:
            Public S3 URL
        """
        try:
            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs={'ContentType': 'image/jpeg'}
            )

            # Generate public URL
            url = f"https://{self.bucket_name}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            logger.info(f"Uploaded to S3: {url}")
            return url

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate presigned URL for private S3 object

        Args:
            s3_key: S3 object key
            expiration: URL expiration in seconds (default 1 hour)

        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': s3_key},
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"Presigned URL generation failed: {e}")
            raise
```

### 2.4: Copy Item Normalizer

**Copy file:**
```bash
cp receipt_scanner/app/services/item_normalizer.py nutrilens/app/services/item_normalizer.py
```

This is the NEW LLM-enhanced normalizer that replaces your existing one.

### 2.5: Update Inventory Service

**File: `nutrilens/app/services/inventory.py`**

**Simplify `_add_to_inventory` method:**

```python
def _add_to_inventory(
    self,
    user_id: int,
    item_id: int,
    quantity_grams: float,
    expiry_days: Optional[int] = None,
    source: str = 'manual'
) -> UserInventory:
    """
    Add item to inventory (quantity already in grams from normalizer)

    Args:
        user_id: User ID
        item_id: Item ID from items table
        quantity_grams: Quantity in grams (already converted)
        expiry_days: Optional expiry days from purchase
        source: Source of addition ('manual', 'receipt_scanner', 'whatsapp')
    """
    # Check if item already exists
    existing = self.db.query(UserInventory).filter(
        and_(
            UserInventory.user_id == user_id,
            UserInventory.item_id == item_id
        )
    ).first()

    if existing:
        # Update quantity
        existing.quantity_grams += quantity_grams
        existing.last_updated = datetime.now()
        inventory_item = existing
    else:
        # Create new entry
        inventory_item = UserInventory(
            user_id=user_id,
            item_id=item_id,
            quantity_grams=quantity_grams,
            purchase_date=datetime.now(),
            expiry_date=datetime.now() + timedelta(days=expiry_days) if expiry_days else None,
            source=source
        )
        self.db.add(inventory_item)

    self.db.commit()
    return inventory_item
```

**Add receipt processing method:**

```python
async def process_receipt_items(
    self,
    user_id: int,
    receipt_items: List[Dict],
    auto_add_threshold: float = 0.75
) -> Dict:
    """
    Process receipt items with LLM-enhanced normalizer

    Args:
        user_id: User ID
        receipt_items: Raw items from receipt scanner
        auto_add_threshold: Confidence threshold for auto-adding

    Returns:
        {
            "auto_added": List of auto-added items,
            "needs_confirmation": List of items needing review
        }
    """
    from app.services.item_normalizer import IntelligentItemNormalizer
    from app.config import OPENAI_API_KEY

    # Load all items
    items_list = self.db.query(Item).all()

    # Initialize normalizer
    normalizer = IntelligentItemNormalizer(items_list, OPENAI_API_KEY)

    # Normalize batch
    normalized_results = await normalizer.normalize_batch(receipt_items)

    # Categorize by confidence
    auto_added = []
    needs_confirmation = []

    for result in normalized_results:
        result_dict = result.to_dict()

        if result.confidence >= auto_add_threshold and result.item:
            # Auto-add to inventory
            self._add_to_inventory(
                user_id=user_id,
                item_id=result.item.id,
                quantity_grams=result.quantity_grams,
                source='receipt_scanner'
            )
            auto_added.append(result_dict)
        else:
            # Needs confirmation
            needs_confirmation.append(result_dict)

    return {
        "auto_added": auto_added,
        "needs_confirmation": needs_confirmation
    }
```

### 2.6: Receipt API Routes

**Create `nutrilens/app/routes/receipt.py`:**

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
import httpx
import uuid
import os
import tempfile
from typing import List, Dict
from datetime import datetime

from app.database import get_db
from app.services.inventory import InventoryService
from app.services.s3_service import S3Service
from app.models import ReceiptScan, ReceiptPendingItem
from app.auth import get_current_user  # Your existing auth
from app.config import RECEIPT_SCANNER_URL, RECEIPT_AUTO_ADD_THRESHOLD

router = APIRouter(prefix="/receipt", tags=["receipt"])


@router.post("/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Complete receipt processing flow:
    1. Upload image to S3
    2. Call receipt scanner microservice
    3. Normalize items with LLM
    4. Add to inventory / pending review
    """
    # Step 1: Save temp file
    tmp_dir = tempfile.gettempdir()
    temp_path = os.path.join(tmp_dir, f"{uuid.uuid4()}_{file.filename}")

    with open(temp_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    # Step 2: Upload to S3
    s3_service = S3Service()
    s3_key = f"receipts/user_{user_id}/{uuid.uuid4()}.jpg"
    s3_url = s3_service.upload_file(temp_path, s3_key)

    # Clean up temp file
    os.remove(temp_path)

    # Step 3: Create receipt_scan record
    receipt_scan = ReceiptScan(
        user_id=user_id,
        s3_url=s3_url,
        status='processing'
    )
    db.add(receipt_scan)
    db.commit()
    db.refresh(receipt_scan)

    try:
        # Step 4: Call receipt scanner microservice
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{RECEIPT_SCANNER_URL}/scan",
                json={"image_url": s3_url}
            )
            response.raise_for_status()
            scanner_result = response.json()

        receipt_items = scanner_result.get("items", [])

        # Step 5: Normalize items with LLM
        inventory_service = InventoryService(db)
        process_result = await inventory_service.process_receipt_items(
            user_id=user_id,
            receipt_items=receipt_items,
            auto_add_threshold=RECEIPT_AUTO_ADD_THRESHOLD
        )

        auto_added = process_result["auto_added"]
        needs_confirmation = process_result["needs_confirmation"]

        # Step 6: Save pending items
        for item_data in needs_confirmation:
            pending_item = ReceiptPendingItem(
                receipt_scan_id=receipt_scan.id,
                item_name=item_data.get("original_input", item_data.get("item_name")),
                quantity=item_data.get("quantity", 0),
                unit=item_data.get("unit", "unit"),
                suggested_item_id=item_data.get("item_id"),
                confidence=item_data.get("confidence", 0),
                status='pending'
            )
            db.add(pending_item)

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

    except Exception as e:
        # Mark as failed
        receipt_scan.status = 'failed'
        receipt_scan.error_message = str(e)
        db.commit()

        raise HTTPException(status_code=500, detail=f"Receipt processing failed: {str(e)}")


@router.get("/pending")
async def get_pending_items(
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all pending items needing user confirmation"""
    pending = db.query(ReceiptPendingItem).join(ReceiptScan).filter(
        ReceiptScan.user_id == user_id,
        ReceiptPendingItem.status == 'pending'
    ).all()

    return {
        "count": len(pending),
        "items": [
            {
                "id": item.id,
                "receipt_id": item.receipt_scan_id,
                "item_name": item.item_name,
                "quantity": item.quantity,
                "unit": item.unit,
                "suggested_item_id": item.suggested_item_id,
                "confidence": item.confidence
            }
            for item in pending
        ]
    }


@router.post("/confirm")
async def confirm_items(
    items: List[Dict],
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm pending items and add to inventory

    Body: [
        {
            "pending_item_id": 1,
            "action": "add",  # or "skip"
            "item_id": 7,  # optional override
            "quantity_grams": 100  # optional override
        }
    ]
    """
    inventory_service = InventoryService(db)
    added_count = 0

    for item_data in items:
        pending_id = item_data.get("pending_item_id")
        action = item_data.get("action")

        pending_item = db.query(ReceiptPendingItem).filter(
            ReceiptPendingItem.id == pending_id
        ).first()

        if not pending_item:
            continue

        if action == "add":
            item_id = item_data.get("item_id", pending_item.suggested_item_id)
            quantity_grams = item_data.get("quantity_grams")

            if item_id and quantity_grams:
                inventory_service._add_to_inventory(
                    user_id=user_id,
                    item_id=item_id,
                    quantity_grams=quantity_grams,
                    source='receipt_scanner'
                )
                pending_item.status = 'confirmed'
                pending_item.confirmed_at = datetime.now()
                added_count += 1

        elif action == "skip":
            pending_item.status = 'skipped'

    db.commit()

    return {
        "status": "success",
        "added_count": added_count
    }
```

**Register in main app (`nutrilens/app/main.py`):**

```python
from app.routes import receipt

app.include_router(receipt.router, prefix="/api")
```

---

## Environment Setup

### Receipt Scanner `.env`
```env
OPENAI_API_KEY=sk-proj-...
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=nutrilens-receipts
```

### Nutrilens `.env`
```env
# Existing config...

# S3
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=nutrilens-receipts

# Receipt Scanner
RECEIPT_SCANNER_URL=http://localhost:8001

# OpenAI
OPENAI_API_KEY=sk-proj-...

# Settings
RECEIPT_AUTO_ADD_THRESHOLD=0.75
```

---

## Running the Services

### Development

**Terminal 1: Receipt Scanner**
```bash
cd receipt_scanner
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

**Terminal 2: Nutrilens**
```bash
cd nutrilens
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Production (Docker Compose)

**`docker-compose.yml`:**
```yaml
version: '3.8'

services:
  receipt-scanner:
    build: ./receipt_scanner
    ports:
      - "8001:8001"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_REGION=${AWS_REGION}
      - S3_BUCKET_NAME=${S3_BUCKET_NAME}
    command: uvicorn app.main:app --host 0.0.0.0 --port 8001

  nutrilens:
    build: ./nutrilens
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AWS_REGION=${AWS_REGION}
      - S3_BUCKET_NAME=${S3_BUCKET_NAME}
      - RECEIPT_SCANNER_URL=http://receipt-scanner:8001
      - RECEIPT_AUTO_ADD_THRESHOLD=0.75
    depends_on:
      - receipt-scanner
      - postgres
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=nutrilens
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

---

## Testing the Complete Flow

### 1. Test Receipt Scanner Alone
```bash
curl -X POST http://localhost:8001/scan \
  -H "Content-Type: application/json" \
  -d '{"image_url": "https://s3.amazonaws.com/nutrilens-receipts/test/receipt.jpg"}'
```

### 2. Test Nutrilens Integration
```bash
curl -X POST http://localhost:8000/api/receipt/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@receipt4.jpg"
```

### 3. Test Pending Items Review
```bash
# Get pending items
curl -X GET http://localhost:8000/api/receipt/pending \
  -H "Authorization: Bearer YOUR_TOKEN"

# Confirm items
curl -X POST http://localhost:8000/api/receipt/confirm \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "pending_item_id": 1,
      "action": "add",
      "item_id": 7,
      "quantity_grams": 100
    }
  ]'
```

---

## Summary Checklist

### Receipt Scanner
- [x] `/scan` endpoint added (accepts S3 URL)
- [ ] Update port to 8001
- [x] Returns items + metadata (no DB save for integration mode)

### Nutrilens
- [ ] Copy `item_normalizer.py`
- [ ] Add database tables: `receipt_scans`, `receipt_pending_items`
- [ ] Create `s3_service.py`
- [ ] Update `inventory.py` (simplify `_add_to_inventory`, add `process_receipt_items`)
- [ ] Create `routes/receipt.py`
- [ ] Update `.env` with S3 and receipt scanner config
- [ ] Register receipt routes in main app

### Testing
- [ ] Test receipt scanner `/scan` endpoint
- [ ] Test full upload flow
- [ ] Test pending items review
- [ ] Test WhatsApp single item (bonus feature)

---

## Key Design Decisions

✅ **Nutrilens owns S3 upload** - Controls user data
✅ **Receipt scanner is stateless** - Just processes, doesn't store
✅ **One LLM call per batch** - Efficient token usage
✅ **Lower threshold for LLM** - 0.75 vs 0.85 (more accurate)
✅ **Auto-add high confidence** - Better UX
✅ **User reviews low confidence** - Ensures accuracy
✅ **Audit trail** - Receipt scans saved with S3 URLs
✅ **Microservice architecture** - Independent scaling

---

## Questions for Deployment

1. **S3 Bucket**: Create `nutrilens-receipts` bucket with appropriate permissions
2. **Image Retention**: Keep receipts for 30 days then auto-delete? (Lifecycle policy)
3. **Error Handling**: Failed scans - retry or manual upload?
4. **Rate Limiting**: Limit receipt uploads per user per day?
5. **Monitoring**: Track success rates, processing times

This is the complete end-to-end integration! 🎉
