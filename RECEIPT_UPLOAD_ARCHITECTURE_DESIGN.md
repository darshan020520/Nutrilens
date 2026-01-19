# Receipt Upload Architecture Design

## Executive Summary

**Current Problem**: Receipt upload has fundamental design flaws:
1. Double file write (temp disk → S3) wastes storage and I/O
2. Server becomes bandwidth bottleneck (client → server → S3)
3. Synchronous processing blocks for 25-105 seconds
4. 8 architectural violations (direct DB access, manual instantiation, business logic in API)

**Proposed Solution**: Presigned URL-based upload with clean architecture separation

**Two Approaches Analyzed**:
- **Approach A**: Presigned URL + Synchronous Processing (simpler, user still waits)
- **Approach B**: Presigned URL + Asynchronous Processing (scalable, better UX, complex)

---

## Design Goals

1. **Eliminate server bottleneck**: Client uploads directly to S3
2. **Clean architecture**: Strict API → Service → Repository separation
3. **Scalability**: Handle high upload volume without server degradation
4. **Transaction safety**: Proper commit/rollback handling
5. **UX**: User sees results immediately (or with minimal polling)
6. **Extensibility**: Easy to add features (retry, progress tracking, webhooks)

---

## Approach A: Presigned URL + Synchronous Processing

### Architecture Overview

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ Client  │                    │ Backend │                    │   S3    │
└────┬────┘                    └────┬────┘                    └────┬────┘
     │                              │                              │
     │ 1. POST /receipt/initiate    │                              │
     │─────────────────────────────>│                              │
     │                              │                              │
     │ 2. {presigned_url, receipt_id}                              │
     │<─────────────────────────────│                              │
     │                              │                              │
     │ 3. PUT (file) to presigned_url                              │
     │─────────────────────────────────────────────────────────────>│
     │                              │                              │
     │ 4. S3 Upload Success         │                              │
     │<─────────────────────────────────────────────────────────────│
     │                              │                              │
     │ 5. POST /receipt/process     │                              │
     │      {receipt_id, s3_key}    │                              │
     │─────────────────────────────>│                              │
     │                              │                              │
     │         (Server processes synchronously - 25-105s)          │
     │                              │                              │
     │                              │ 6. GET s3_url                │
     │                              │─────────────────────────────>│
     │                              │<─────────────────────────────│
     │                              │                              │
     │                              │ 7. Call Receipt Scanner      │
     │                              │    Microservice              │
     │                              │                              │
     │                              │ 8. Normalize with LLM        │
     │                              │                              │
     │                              │ 9. Enrich items              │
     │                              │                              │
     │ 10. {auto_added,             │                              │
     │      needs_confirmation}     │                              │
     │<─────────────────────────────│                              │
     │                              │                              │
```

### API Endpoints

#### **Endpoint 1: POST /receipt/v2/initiate**

**Purpose**: Generate presigned URL and create receipt record

**Request**:
```json
{
  "filename": "receipt.jpg",
  "content_type": "image/jpeg"
}
```

**Response**:
```json
{
  "receipt_id": 123,
  "presigned_url": "https://s3.amazonaws.com/bucket/receipts/user_5/uuid.jpg?X-Amz-Signature=...",
  "s3_key": "receipts/user_5/uuid.jpg",
  "expires_in": 3600
}
```

**Flow**:
```
API Layer → ReceiptService.initiate_upload() → ReceiptRepository.create_receipt_scan()
                                            → S3Service.generate_presigned_upload_url()
```

---

#### **Endpoint 2: POST /receipt/v2/process**

**Purpose**: Process uploaded receipt (scanner + normalization + enrichment)

**Request**:
```json
{
  "receipt_id": 123,
  "s3_key": "receipts/user_5/uuid.jpg"
}
```

**Response** (after 25-105 seconds):
```json
{
  "receipt_id": 123,
  "status": "completed",
  "total_items": 8,
  "auto_added_count": 5,
  "auto_added": [...],
  "needs_confirmation_count": 3,
  "needs_confirmation": [...]
}
```

**Flow**:
```
API Layer → ReceiptService.process_receipt()
              ├─> ReceiptRepository.update_status('processing')
              ├─> S3Service.generate_presigned_url() [for scanner microservice]
              ├─> ReceiptScannerClient.scan()
              ├─> InventoryService.process_receipt_items()
              ├─> ItemRepository.get_all_items() [for enrichment]
              ├─> ReceiptItemEnricher.enrich_batch()
              ├─> ReceiptRepository.bulk_create_pending_items()
              └─> ReceiptRepository.update_status('completed')
```

---

### Service Layer Design

#### **ReceiptService** (NEW)

```python
class ReceiptService:
    """
    Service for receipt upload and processing.

    Responsibilities:
    - Coordinate receipt upload flow
    - Orchestrate processing pipeline (scanner → normalize → enrich)
    - Transaction management
    """

    def __init__(
        self,
        db: Session,
        receipt_repo: ReceiptRepository,
        inventory_service: IntelligentInventoryService,
        item_repo: ItemRepository,
        s3_service: S3Service,
        scanner_client: ReceiptScannerClient,
        enricher_service: ReceiptEnricherService
    ):
        self.db = db
        self.receipt_repo = receipt_repo
        self.inventory_service = inventory_service
        self.item_repo = item_repo
        self.s3_service = s3_service
        self.scanner_client = scanner_client
        self.enricher_service = enricher_service

    async def initiate_upload(
        self,
        user_id: int,
        filename: str,
        content_type: str
    ) -> Dict:
        """
        Step 1: Create receipt record and generate presigned URL.

        Returns:
            {
                'receipt_id': int,
                'presigned_url': str,
                's3_key': str,
                'expires_in': int
            }
        """
        try:
            # Generate unique S3 key
            s3_key = f"receipts/user_{user_id}/{uuid.uuid4()}.jpg"

            # Create receipt record with status 'uploading'
            receipt_scan = self.receipt_repo.create_receipt_scan(
                user_id=user_id,
                s3_url=f"s3://{settings.s3_bucket_name}/{s3_key}",
                status='uploading'
            )
            self.db.commit()

            # Generate presigned URL for client upload
            presigned_url = self.s3_service.generate_presigned_upload_url(
                s3_key=s3_key,
                content_type=content_type,
                expiration=3600
            )

            return {
                'receipt_id': receipt_scan.id,
                'presigned_url': presigned_url,
                's3_key': s3_key,
                'expires_in': 3600
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error initiating receipt upload: {e}")
            raise

    async def process_receipt(
        self,
        user_id: int,
        receipt_id: int,
        s3_key: str
    ) -> Dict:
        """
        Step 2: Process uploaded receipt (SYNCHRONOUS).

        Flow:
        1. Validate receipt ownership
        2. Update status to 'processing'
        3. Call receipt scanner microservice
        4. Normalize items with LLM
        5. Enrich items needing confirmation
        6. Update status to 'completed'

        Returns:
            {
                'receipt_id': int,
                'status': 'completed',
                'total_items': int,
                'auto_added': [...],
                'needs_confirmation': [...]
            }
        """
        try:
            # Validate receipt belongs to user
            receipt = self.receipt_repo.get_receipt_scan(
                receipt_id=receipt_id,
                user_id=user_id
            )

            if not receipt:
                raise ValueError(f"Receipt {receipt_id} not found for user {user_id}")

            if receipt.status != 'uploading':
                raise ValueError(f"Receipt {receipt_id} has invalid status: {receipt.status}")

            # Update status to processing
            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='processing'
            )
            self.db.commit()

            # Generate presigned URL for scanner microservice to read
            presigned_read_url = self.s3_service.generate_presigned_url(
                s3_key=s3_key,
                expiration=3600
            )

            # Call receipt scanner microservice
            scanner_result = await self.scanner_client.scan_receipt(presigned_read_url)
            receipt_items = scanner_result.get('items', [])

            # Normalize items with LLM (auto-add high confidence, flag low confidence)
            process_result = await self.inventory_service.process_receipt_items(
                user_id=user_id,
                receipt_items=receipt_items,
                auto_add_threshold=settings.receipt_auto_add_threshold
            )

            auto_added = process_result['auto_added']
            needs_confirmation = process_result['needs_confirmation']

            # Enrich items needing confirmation
            if needs_confirmation:
                # Get all items for enrichment context
                all_items = await self.item_repo.get_all_items()

                # Extract item names
                item_names = [
                    item.get('original_input', item.get('item_name', ''))
                    for item in needs_confirmation
                ]

                # Batch enrich
                enriched_items = await self.enricher_service.enrich_batch(
                    item_names=item_names,
                    existing_items=all_items
                )

                # Create pending items with enrichment data
                pending_items = [
                    ReceiptPendingItem(
                        receipt_scan_id=receipt_id,
                        item_name=item_data.get('original_input', item_data.get('item_name', 'Unknown')),
                        quantity=item_data.get('quantity', 0),
                        unit=item_data.get('unit', 'unit'),
                        suggested_item_id=item_data.get('item_id'),
                        confidence=item_data.get('confidence', 0),
                        status='pending',
                        canonical_name=enriched.get('canonical_name'),
                        category=enriched.get('category'),
                        fdc_id=enriched.get('fdc_id'),
                        nutrition_data=enriched.get('nutrition_per_100g'),
                        enrichment_confidence=enriched.get('confidence'),
                        enrichment_reasoning=enriched.get('reasoning')
                    )
                    for item_data, enriched in zip(needs_confirmation, enriched_items)
                ]

                self.receipt_repo.bulk_create_pending_items(pending_items)

            # Update status to completed
            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='completed',
                items_count=len(receipt_items),
                auto_added_count=len(auto_added),
                needs_confirmation_count=len(needs_confirmation)
            )
            self.db.commit()

            return {
                'receipt_id': receipt_id,
                'status': 'completed',
                'total_items': len(receipt_items),
                'auto_added_count': len(auto_added),
                'auto_added': auto_added,
                'needs_confirmation_count': len(needs_confirmation),
                'needs_confirmation': needs_confirmation
            }

        except Exception as e:
            self.db.rollback()

            # Mark receipt as failed
            try:
                self.receipt_repo.update_receipt_scan_status(
                    receipt_id=receipt_id,
                    status='failed',
                    error_message=str(e)
                )
                self.db.commit()
            except:
                pass

            logger.error(f"Error processing receipt {receipt_id}: {e}")
            raise
```

---

### Client Infrastructure (NEW)

#### **ReceiptScannerClient** (NEW)

```python
class ReceiptScannerClient:
    """
    Client for receipt scanner microservice.

    Encapsulates external API calls.
    """

    def __init__(self, scanner_url: str):
        self.scanner_url = scanner_url

    async def scan_receipt(self, image_url: str) -> Dict:
        """
        Call receipt scanner microservice.

        Args:
            image_url: Presigned URL to receipt image

        Returns:
            {'items': [...]}

        Raises:
            httpx.HTTPError: If scanner fails
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.scanner_url}/scan",
                json={"image_url": image_url}
            )
            response.raise_for_status()
            return response.json()
```

---

#### **ReceiptEnricherService** (NEW - extracted from ReceiptItemEnricher)

```python
class ReceiptEnricherService:
    """
    Service for enriching receipt items with nutrition data.

    Wraps ReceiptItemEnricher with clean interface.
    """

    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key

    async def enrich_batch(
        self,
        item_names: List[str],
        existing_items: List[Item]
    ) -> List[Dict]:
        """
        Enrich batch of item names.

        Args:
            item_names: List of item names from receipt
            existing_items: All items in database (for context)

        Returns:
            List of enriched item dicts
        """
        from app.services.receipt_item_enricher import ReceiptItemEnricher

        enricher = ReceiptItemEnricher(
            openai_api_key=self.openai_api_key,
            existing_items=existing_items
        )

        return await enricher.enrich_batch(item_names)
```

---

### Repository Layer Changes

#### **ItemRepository** (NEW)

```python
class ItemRepository:
    """
    Repository for Item data access.
    """

    def __init__(self, db: Session):
        self.db = db

    async def get_all_items(self) -> List[Item]:
        """
        Get all items in database.

        Used for enrichment context.

        Returns:
            List of all Item objects
        """
        return self.db.query(Item).all()
```

---

### S3Service Changes

#### **Add presigned upload URL generation**

```python
class S3Service:
    """
    Service for S3 operations.
    """

    def generate_presigned_upload_url(
        self,
        s3_key: str,
        content_type: str,
        expiration: int = 3600
    ) -> str:
        """
        Generate presigned URL for client-side upload.

        Args:
            s3_key: S3 object key
            content_type: MIME type (e.g., 'image/jpeg')
            expiration: URL expiration in seconds

        Returns:
            Presigned PUT URL
        """
        return self.s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': s3_key,
                'ContentType': content_type
            },
            ExpiresIn=expiration
        )
```

---

### Frontend Changes

#### **Current Flow (BROKEN)**

```typescript
// Current: Upload file to backend
const formData = new FormData();
formData.append('file', file);

const response = await fetch('/api/receipt/v2/upload', {
  method: 'POST',
  body: formData
});
// Wait 25-105 seconds...
const result = await response.json();
```

#### **New Flow (CLEAN)**

```typescript
// Step 1: Get presigned URL
const initResponse = await fetch('/api/receipt/v2/initiate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    filename: file.name,
    content_type: file.type
  })
});
const { receipt_id, presigned_url, s3_key } = await initResponse.json();

// Step 2: Upload directly to S3
const uploadResponse = await fetch(presigned_url, {
  method: 'PUT',
  body: file,
  headers: { 'Content-Type': file.type }
});

if (!uploadResponse.ok) {
  throw new Error('S3 upload failed');
}

// Step 3: Trigger processing
const processResponse = await fetch('/api/receipt/v2/process', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ receipt_id, s3_key })
});
// Wait 25-105 seconds...
const result = await processResponse.json();
```

---

### Pros and Cons

**✅ Pros**:
1. **Eliminates server bottleneck**: Client uploads directly to S3
2. **Clean architecture**: Proper service layer separation
3. **Simpler implementation**: No background job infrastructure needed
4. **Immediate results**: User sees results after processing completes
5. **Transaction safety**: Service layer controls commits
6. **Resumable uploads**: S3 supports multipart uploads natively

**❌ Cons**:
1. **User still waits 25-105 seconds**: HTTP connection held during processing
2. **Server resources blocked**: Worker/thread tied up during LLM calls
3. **No progress updates**: User sees loading spinner, no intermediate feedback
4. **Connection timeout risk**: Long requests may timeout on some networks
5. **Not horizontally scalable**: Can't distribute processing across workers

---

## Approach B: Presigned URL + Asynchronous Processing

### Architecture Overview

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐                    ┌─────────┐
│ Client  │                    │ Backend │                    │  Queue  │                    │   S3    │
└────┬────┘                    └────┬────┘                    └────┬────┘                    └────┬────┘
     │                              │                              │                              │
     │ 1. POST /receipt/initiate    │                              │                              │
     │─────────────────────────────>│                              │                              │
     │                              │                              │                              │
     │ 2. {presigned_url, receipt_id}                              │                              │
     │<─────────────────────────────│                              │                              │
     │                              │                              │                              │
     │ 3. PUT (file) to presigned_url                              │                              │
     │─────────────────────────────────────────────────────────────────────────────────────────>│
     │                              │                              │                              │
     │ 4. S3 Upload Success         │                              │                              │
     │<─────────────────────────────────────────────────────────────────────────────────────────│
     │                              │                              │                              │
     │ 5. POST /receipt/process-async                              │                              │
     │      {receipt_id, s3_key}    │                              │                              │
     │─────────────────────────────>│                              │                              │
     │                              │                              │                              │
     │                              │ 6. Enqueue job               │                              │
     │                              │─────────────────────────────>│                              │
     │                              │                              │                              │
     │ 7. {job_id, status: queued}  │                              │                              │
     │<─────────────────────────────│                              │                              │
     │                              │                              │                              │
     │         (Client polls every 2s)                             │                              │
     │                              │                              │                              │
     │ 8. GET /receipt/status/{job_id}                             │                              │
     │─────────────────────────────>│                              │                              │
     │                              │                              │                              │
     │ 9. {status: processing, progress: 33%}                      │                              │
     │<─────────────────────────────│                              │                              │
     │                              │                              │                              │
     │                              │        (Background worker)   │                              │
     │                              │                              │                              │
     │                              │                         10. Dequeue job                     │
     │                              │                              │                              │
     │                              │                         11. Process receipt                │
     │                              │                              │                              │
     │                              │                         12. Update status                   │
     │                              │                              │                              │
     │ 13. GET /receipt/status/{job_id}                            │                              │
     │─────────────────────────────>│                              │                              │
     │                              │                              │                              │
     │ 14. {status: completed, result: {...}}                      │                              │
     │<─────────────────────────────│                              │                              │
     │                              │                              │                              │
```

### API Endpoints

#### **Endpoint 1: POST /receipt/v2/initiate** (SAME AS APPROACH A)

---

#### **Endpoint 2: POST /receipt/v2/process-async**

**Purpose**: Enqueue receipt processing job

**Request**:
```json
{
  "receipt_id": 123,
  "s3_key": "receipts/user_5/uuid.jpg"
}
```

**Response** (IMMEDIATE - < 100ms):
```json
{
  "job_id": "receipt_job_123_abc",
  "receipt_id": 123,
  "status": "queued",
  "estimated_time_seconds": 60
}
```

**Flow**:
```
API Layer → ReceiptService.process_receipt_async()
              ├─> ReceiptRepository.update_status('queued')
              └─> Queue.enqueue(process_receipt_task, receipt_id, s3_key)
```

---

#### **Endpoint 3: GET /receipt/v2/status/{job_id}**

**Purpose**: Check processing status (for polling)

**Response** (while processing):
```json
{
  "job_id": "receipt_job_123_abc",
  "receipt_id": 123,
  "status": "processing",
  "progress_percentage": 66,
  "stage": "enriching_items",
  "estimated_remaining_seconds": 20
}
```

**Response** (when completed):
```json
{
  "job_id": "receipt_job_123_abc",
  "receipt_id": 123,
  "status": "completed",
  "progress_percentage": 100,
  "result": {
    "total_items": 8,
    "auto_added_count": 5,
    "auto_added": [...],
    "needs_confirmation_count": 3,
    "needs_confirmation": [...]
  }
}
```

**Response** (if failed):
```json
{
  "job_id": "receipt_job_123_abc",
  "receipt_id": 123,
  "status": "failed",
  "error": "Receipt scanner service unavailable"
}
```

**Flow**:
```
API Layer → ReceiptService.get_job_status()
              └─> JobStatusRepository.get_by_id(job_id)
```

---

### Service Layer Design

#### **ReceiptService** (EXTENDED)

```python
class ReceiptService:
    """
    Service for receipt upload and processing.
    """

    async def process_receipt_async(
        self,
        user_id: int,
        receipt_id: int,
        s3_key: str
    ) -> Dict:
        """
        Enqueue receipt processing job (ASYNCHRONOUS).

        Returns immediately with job ID.

        Returns:
            {
                'job_id': str,
                'receipt_id': int,
                'status': 'queued',
                'estimated_time_seconds': int
            }
        """
        try:
            # Validate receipt
            receipt = self.receipt_repo.get_receipt_scan(
                receipt_id=receipt_id,
                user_id=user_id
            )

            if not receipt or receipt.status != 'uploading':
                raise ValueError(f"Invalid receipt {receipt_id}")

            # Update status to queued
            self.receipt_repo.update_receipt_scan_status(
                receipt_id=receipt_id,
                status='queued'
            )

            # Create job record
            job = self.job_status_repo.create_job(
                job_type='receipt_processing',
                user_id=user_id,
                receipt_id=receipt_id,
                status='queued'
            )

            self.db.commit()

            # Enqueue background task
            job_id = f"receipt_job_{receipt_id}_{uuid.uuid4().hex[:8]}"
            self.queue.enqueue(
                process_receipt_task,
                job_id=job_id,
                receipt_id=receipt_id,
                user_id=user_id,
                s3_key=s3_key
            )

            return {
                'job_id': job_id,
                'receipt_id': receipt_id,
                'status': 'queued',
                'estimated_time_seconds': 60
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error enqueueing receipt processing: {e}")
            raise

    async def get_job_status(self, job_id: str, user_id: int) -> Dict:
        """
        Get processing job status.

        Returns:
            {
                'job_id': str,
                'receipt_id': int,
                'status': 'queued' | 'processing' | 'completed' | 'failed',
                'progress_percentage': int,
                'stage': str,
                'result': Dict (if completed),
                'error': str (if failed)
            }
        """
        job = self.job_status_repo.get_by_id(job_id)

        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Validate ownership
        if job.user_id != user_id:
            raise ValueError(f"Job {job_id} does not belong to user {user_id}")

        return {
            'job_id': job_id,
            'receipt_id': job.receipt_id,
            'status': job.status,
            'progress_percentage': job.progress_percentage,
            'stage': job.stage,
            'result': job.result if job.status == 'completed' else None,
            'error': job.error_message if job.status == 'failed' else None
        }
```

---

### Background Worker (NEW)

#### **Celery Task** (or RQ/Arq)

```python
from celery import Celery
from app.dependencies import get_db

celery_app = Celery('receipt_processor', broker='redis://localhost:6379/0')

@celery_app.task(bind=True)
def process_receipt_task(
    self,
    job_id: str,
    receipt_id: int,
    user_id: int,
    s3_key: str
):
    """
    Background task to process receipt.

    Updates job status throughout processing.
    """
    db = next(get_db())

    try:
        # Initialize services
        receipt_repo = ReceiptRepository(db)
        job_repo = JobStatusRepository(db)
        s3_service = S3Service()
        scanner_client = ReceiptScannerClient(settings.receipt_scanner_url)
        # ... other services

        # Update job status: processing, stage: scanning
        job_repo.update_job(
            job_id=job_id,
            status='processing',
            progress_percentage=10,
            stage='scanning_receipt'
        )
        db.commit()

        # Call receipt scanner
        presigned_read_url = s3_service.generate_presigned_url(s3_key, 3600)
        scanner_result = await scanner_client.scan_receipt(presigned_read_url)
        receipt_items = scanner_result.get('items', [])

        # Update progress: 33%
        job_repo.update_job(
            job_id=job_id,
            progress_percentage=33,
            stage='normalizing_items'
        )
        db.commit()

        # Normalize with LLM
        inventory_service = IntelligentInventoryService(db)
        process_result = await inventory_service.process_receipt_items(
            user_id=user_id,
            receipt_items=receipt_items,
            auto_add_threshold=settings.receipt_auto_add_threshold
        )

        auto_added = process_result['auto_added']
        needs_confirmation = process_result['needs_confirmation']

        # Update progress: 66%
        job_repo.update_job(
            job_id=job_id,
            progress_percentage=66,
            stage='enriching_items'
        )
        db.commit()

        # Enrich items
        if needs_confirmation:
            item_repo = ItemRepository(db)
            all_items = await item_repo.get_all_items()

            enricher_service = ReceiptEnricherService(settings.openai_api_key)
            item_names = [
                item.get('original_input', item.get('item_name', ''))
                for item in needs_confirmation
            ]
            enriched_items = await enricher_service.enrich_batch(item_names, all_items)

            # Create pending items
            pending_items = [...]  # Same as Approach A
            receipt_repo.bulk_create_pending_items(pending_items)

        # Update job: completed
        result = {
            'total_items': len(receipt_items),
            'auto_added_count': len(auto_added),
            'auto_added': auto_added,
            'needs_confirmation_count': len(needs_confirmation),
            'needs_confirmation': needs_confirmation
        }

        job_repo.update_job(
            job_id=job_id,
            status='completed',
            progress_percentage=100,
            result=result
        )

        receipt_repo.update_receipt_scan_status(
            receipt_id=receipt_id,
            status='completed',
            items_count=len(receipt_items),
            auto_added_count=len(auto_added),
            needs_confirmation_count=len(needs_confirmation)
        )

        db.commit()

    except Exception as e:
        db.rollback()

        # Mark job as failed
        job_repo.update_job(
            job_id=job_id,
            status='failed',
            error_message=str(e)
        )

        receipt_repo.update_receipt_scan_status(
            receipt_id=receipt_id,
            status='failed',
            error_message=str(e)
        )

        db.commit()
        raise
```

---

### Database Schema Changes

#### **New Table: job_status**

```sql
CREATE TABLE job_status (
    id VARCHAR(255) PRIMARY KEY,  -- e.g., "receipt_job_123_abc"
    job_type VARCHAR(50) NOT NULL,  -- 'receipt_processing'
    user_id INTEGER NOT NULL REFERENCES users(id),
    receipt_id INTEGER REFERENCES receipt_scans(id),
    status VARCHAR(20) NOT NULL,  -- 'queued', 'processing', 'completed', 'failed'
    progress_percentage INTEGER DEFAULT 0,
    stage VARCHAR(50),  -- 'scanning_receipt', 'normalizing_items', etc.
    result JSONB,  -- Final result when completed
    error_message TEXT,  -- Error if failed
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_job_status_user_id ON job_status(user_id);
CREATE INDEX idx_job_status_receipt_id ON job_status(receipt_id);
```

---

### Repository Layer Changes

#### **JobStatusRepository** (NEW)

```python
class JobStatusRepository:
    """
    Repository for job status tracking.
    """

    def __init__(self, db: Session):
        self.db = db

    def create_job(
        self,
        job_id: str,
        job_type: str,
        user_id: int,
        receipt_id: int,
        status: str
    ) -> JobStatus:
        """
        Create job record.
        """
        job = JobStatus(
            id=job_id,
            job_type=job_type,
            user_id=user_id,
            receipt_id=receipt_id,
            status=status,
            progress_percentage=0
        )
        self.db.add(job)
        self.db.flush()
        return job

    def get_by_id(self, job_id: str) -> Optional[JobStatus]:
        """
        Get job by ID.
        """
        return self.db.query(JobStatus).filter_by(id=job_id).first()

    def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress_percentage: Optional[int] = None,
        stage: Optional[str] = None,
        result: Optional[Dict] = None,
        error_message: Optional[str] = None
    ) -> JobStatus:
        """
        Update job status.
        """
        job = self.get_by_id(job_id)

        if not job:
            raise ValueError(f"Job {job_id} not found")

        if status is not None:
            job.status = status
        if progress_percentage is not None:
            job.progress_percentage = progress_percentage
        if stage is not None:
            job.stage = stage
        if result is not None:
            job.result = result
        if error_message is not None:
            job.error_message = error_message

        job.updated_at = datetime.utcnow()
        self.db.flush()
        return job
```

---

### Frontend Changes

#### **New Flow with Polling**

```typescript
// Step 1: Get presigned URL (same as Approach A)
const initResponse = await fetch('/api/receipt/v2/initiate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    filename: file.name,
    content_type: file.type
  })
});
const { receipt_id, presigned_url, s3_key } = await initResponse.json();

// Step 2: Upload to S3 (same as Approach A)
const uploadResponse = await fetch(presigned_url, {
  method: 'PUT',
  body: file,
  headers: { 'Content-Type': file.type }
});

if (!uploadResponse.ok) {
  throw new Error('S3 upload failed');
}

// Step 3: Trigger async processing
const processResponse = await fetch('/api/receipt/v2/process-async', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ receipt_id, s3_key })
});
const { job_id } = await processResponse.json();

// Step 4: Poll for completion
const pollInterval = 2000; // 2 seconds
let result;

while (true) {
  const statusResponse = await fetch(`/api/receipt/v2/status/${job_id}`);
  const status = await statusResponse.json();

  // Update UI with progress
  updateProgressBar(status.progress_percentage);
  updateStageLabel(status.stage);

  if (status.status === 'completed') {
    result = status.result;
    break;
  }

  if (status.status === 'failed') {
    throw new Error(status.error);
  }

  // Wait before next poll
  await new Promise(resolve => setTimeout(resolve, pollInterval));
}

// Display results
displayResults(result);
```

---

### Infrastructure Requirements

1. **Message Queue**: Redis or RabbitMQ
2. **Task Queue**: Celery, RQ, or Arq
3. **Background Workers**: 2-5 workers (scale based on volume)
4. **Database**: Add job_status table
5. **Monitoring**: Track job queue length, processing time, failure rate

---

### Pros and Cons

**✅ Pros**:
1. **Immediate response**: API returns in < 100ms
2. **Server resources freed**: Workers handle long-running tasks
3. **Progress updates**: User sees real-time progress (scanning → normalizing → enriching)
4. **Horizontally scalable**: Add more workers to handle load
5. **Retry support**: Failed jobs can be retried automatically
6. **No timeout risk**: Client polls instead of holding connection
7. **Better UX**: User can leave page and come back (job continues)

**❌ Cons**:
1. **Infrastructure complexity**: Requires queue + workers + monitoring
2. **Polling overhead**: Client makes multiple requests (but small payloads)
3. **Eventual consistency**: Results not immediately available
4. **More code**: Background tasks, job tracking, polling logic
5. **Debugging harder**: Distributed system with async execution

---

## Comparison: Approach A vs Approach B

| Aspect | Approach A (Sync) | Approach B (Async) |
|--------|-------------------|-------------------|
| **Response Time** | 25-105 seconds | < 100ms (queued) |
| **User Wait Time** | Same as response time | Same (via polling) |
| **Progress Updates** | None | Real-time (scanning, normalizing, enriching) |
| **Server Resources** | Blocked during processing | Freed immediately |
| **Scalability** | Limited (thread pool) | High (add workers) |
| **Timeout Risk** | High (long connections) | None (short polling) |
| **Infrastructure** | None (FastAPI only) | Queue + Workers + Monitoring |
| **Code Complexity** | Low | Medium-High |
| **Retry Support** | Manual (client retries) | Automatic (job queue) |
| **User Can Leave Page** | No (loses progress) | Yes (job continues) |
| **Debugging** | Simple (synchronous) | Complex (distributed) |
| **Total Implementation Time** | 1-2 days | 3-5 days |

---

## Recommendation

### For Current MVP: **Approach A (Synchronous)**

**Rationale**:
1. User explicitly said "the user can wait because it needs to see the results"
2. Simpler implementation = faster time to market
3. Presigned URL already solves the main bottleneck (file upload)
4. Can migrate to async later without breaking API contract (add /process-async alongside /process)

**Implementation Plan**:
1. Add presigned URL endpoints (/initiate)
2. Create ReceiptService with process_receipt()
3. Create ReceiptScannerClient
4. Create ReceiptEnricherService
5. Create ItemRepository
6. Update frontend to use two-step upload
7. Remove old /upload endpoint

**Timeline**: 1-2 days

---

### For Production Scale: **Approach B (Asynchronous)**

**Rationale**:
1. Better UX with progress updates
2. Horizontally scalable (critical for growth)
3. Handles high volume without degradation
4. Users can leave page and come back
5. Automatic retry on failures

**Migration Path from A → B**:
1. Keep /initiate endpoint (no change)
2. Add /process-async alongside /process (both exist)
3. Add /status/{job_id} endpoint
4. Set up queue infrastructure (Redis + Celery)
5. Update frontend to use polling
6. Gradually migrate users to async flow
7. Deprecate /process endpoint

**Timeline**: 3-5 days (after Approach A is working)

---

## Next Steps

1. **User Decision**: Choose Approach A or Approach B
2. **Implementation**: I will implement chosen approach with complete clean architecture
3. **Testing**: Verify all architectural violations are eliminated
4. **Frontend**: Update frontend to use new flow

**Question for User**: Should we proceed with Approach A (simpler, faster) and migrate to Approach B later, or build Approach B directly?
