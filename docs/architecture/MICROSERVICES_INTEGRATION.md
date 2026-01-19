# Microservices Integration Strategy

**Date**: 2025-11-24
**Purpose**: How microservices fit into the target architecture

---

## Current Microservices

1. **Receipt Scanner Microservice** (Python FastAPI)
2. **WhatsApp Agent** (Node.js)
3. **Notification Service** (Planned)

---

## Integration Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Main NutriLens Backend                       │
│                       (Python FastAPI)                           │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │     API      │───▶│ Orchestrator │───▶│   Services   │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│                             │                     │              │
│                             ▼                     ▼              │
│                      ┌──────────────┐    ┌──────────────┐      │
│                      │ Service      │───▶│ Repository   │      │
│                      │ Clients      │    └──────────────┘      │
│                      └──────────────┘                           │
│                             │                                    │
└─────────────────────────────┼────────────────────────────────────┘
                              │
                              │ HTTP/gRPC/Message Queue
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐    ┌───────────────┐
│    Receipt    │     │   WhatsApp    │    │ Notification  │
│    Scanner    │     │     Agent     │    │    Service    │
│ Microservice  │     │ Microservice  │    │ Microservice  │
│               │     │               │    │               │
│  Own DB       │     │  Own DB       │    │  Own DB       │
│  Own Services │     │  Own Services │    │  Own Services │
│  Own Repos    │     │  Own Repos    │    │  Own Repos    │
└───────────────┘     └───────────────┘    └───────────────┘
```

---

## Integration Pattern: Service Client Layer

### 1. Receipt Scanner Integration

#### Current Flow (Bad)
```python
# backend/app/api/receipt.py:88-96
# API directly calls microservice with httpx
async with httpx.AsyncClient(timeout=60.0) as client:
    response = await client.post(
        f"{settings.receipt_scanner_url}/scan",
        json={"image_url": presigned_url}
    )
```

**Problems**:
- API has HTTP client code
- No retry logic
- No circuit breaker
- No error handling abstraction
- Hard to test
- Hard to mock

#### Target Flow (Good)

```python
# ===== Service Client Interface =====
# backend/app/clients/receipt_scanner_client.py
from abc import ABC, abstractmethod

class IReceiptScannerClient(ABC):
    """Interface for receipt scanner microservice."""

    @abstractmethod
    async def scan_receipt(self, image_url: str) -> ReceiptScanResult:
        """Scan receipt and extract items."""
        pass


# ===== HTTP Implementation =====
# backend/app/clients/http_receipt_scanner_client.py
class HttpReceiptScannerClient(IReceiptScannerClient):
    """HTTP client for receipt scanner microservice."""

    def __init__(self, base_url: str, timeout: int = 60, max_retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

    async def scan_receipt(self, image_url: str) -> ReceiptScanResult:
        """
        Scan receipt with retry logic and circuit breaker.
        """
        if self._circuit_breaker.is_open():
            raise ServiceUnavailableError("Receipt scanner is down")

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/scan",
                        json={"image_url": image_url}
                    )
                    response.raise_for_status()

                    data = response.json()

                    # Convert to domain model
                    return ReceiptScanResult(
                        items=[
                            ReceiptItem(
                                name=item["name"],
                                quantity=item.get("quantity", 1),
                                unit=item.get("unit", "unit"),
                                price=item.get("price")
                            )
                            for item in data.get("items", [])
                        ],
                        total_price=data.get("total"),
                        scan_confidence=data.get("confidence", 0.8)
                    )

            except httpx.HTTPError as e:
                if attempt == self.max_retries - 1:
                    self._circuit_breaker.record_failure()
                    raise ServiceUnavailableError(f"Receipt scanner failed: {str(e)}")

                await asyncio.sleep(2 ** attempt)  # Exponential backoff

        self._circuit_breaker.record_success()


# ===== Mock Implementation for Testing =====
# backend/app/clients/mock_receipt_scanner_client.py
class MockReceiptScannerClient(IReceiptScannerClient):
    """Mock client for testing."""

    async def scan_receipt(self, image_url: str) -> ReceiptScanResult:
        """Return mock data."""
        return ReceiptScanResult(
            items=[
                ReceiptItem(name="Chicken Breast", quantity=500, unit="g"),
                ReceiptItem(name="Broccoli", quantity=300, unit="g")
            ],
            total_price=15.99,
            scan_confidence=0.95
        )


# ===== Service Uses Client =====
# backend/app/services/receipt_processing_service.py
class ReceiptProcessingService:
    """Service that uses receipt scanner client."""

    def __init__(
        self,
        receipt_scanner_client: IReceiptScannerClient,
        item_enrichment_service: ItemEnrichmentService,
        inventory_service: InventoryService
    ):
        self.receipt_scanner_client = receipt_scanner_client
        self.item_enrichment_service = item_enrichment_service
        self.inventory_service = inventory_service

    async def process_receipt(
        self,
        user_id: int,
        image_url: str
    ) -> ProcessedReceipt:
        """Process receipt using microservice."""

        # Call microservice via client (abstracted)
        scan_result = await self.receipt_scanner_client.scan_receipt(image_url)

        # Business logic continues
        enriched_items = await self.item_enrichment_service.enrich_batch(
            [item.name for item in scan_result.items]
        )

        # Add to inventory
        for item, enriched in zip(scan_result.items, enriched_items):
            await self.inventory_service.add_item(
                user_id=user_id,
                item_id=enriched.item_id,
                quantity=item.quantity
            )

        return ProcessedReceipt(...)


# ===== Orchestrator Uses Service =====
# backend/app/orchestrators/receipt_orchestrator.py
class ReceiptOrchestrator:
    """Orchestrator for receipt workflow."""

    def __init__(
        self,
        receipt_storage_service: ReceiptStorageService,
        receipt_processing_service: ReceiptProcessingService,
        event_publisher: EventPublisher
    ):
        self.receipt_storage_service = receipt_storage_service
        self.receipt_processing_service = receipt_processing_service
        self.event_publisher = event_publisher

    async def process_receipt_upload(
        self,
        user_id: int,
        uploaded_file: UploadFile
    ) -> ProcessedReceipt:
        """Complete receipt processing workflow."""

        # 1. Upload to S3
        image_url = await self.receipt_storage_service.upload(uploaded_file)

        # 2. Process receipt (calls microservice internally)
        result = await self.receipt_processing_service.process_receipt(
            user_id=user_id,
            image_url=image_url
        )

        # 3. Publish event
        await self.event_publisher.publish(
            "receipt.processed",
            ReceiptProcessedEvent(user_id=user_id, receipt_id=result.id)
        )

        return result


# ===== API Layer =====
# backend/app/api/receipt.py
@router.post("/upload")
async def upload_receipt(
    file: UploadFile = File(...),
    orchestrator: ReceiptOrchestrator = Depends(get_receipt_orchestrator),
    current_user: User = Depends(get_current_user)
):
    """API delegates to orchestrator - doesn't know about microservice."""
    result = await orchestrator.process_receipt_upload(
        user_id=current_user.id,
        uploaded_file=file
    )
    return ReceiptResponse.from_domain(result)
```

### Benefits
✅ API doesn't know about HTTP calls
✅ Easy to test (inject mock client)
✅ Retry logic centralized
✅ Circuit breaker for fault tolerance
✅ Can swap microservice implementation

---

### 2. WhatsApp Agent Integration

#### Current Flow (Bad)
```python
# WhatsApp agent directly calls NutriLens API endpoints
# Duplicates tracking.py logic in orchestrator.py
```

**Problems**:
- Code duplication (188 lines duplicated)
- Both implement same business logic
- Hard to keep in sync

#### Target Flow (Good)

```python
# ===== Shared Service Layer =====
# WhatsApp Agent and Main API use SAME services via HTTP/gRPC

# Main API
@router.post("/tracking/log-meal")
async def log_meal(
    request: LogMealRequest,
    orchestrator: TrackingOrchestrator = Depends(get_tracking_orchestrator),
    current_user: User = Depends(get_current_user)
):
    result = await orchestrator.log_meal_consumption(
        user_id=current_user.id,
        meal_log_id=request.meal_log_id,
        portion_multiplier=request.portion_multiplier
    )
    return LogMealResponse.from_domain(result)


# WhatsApp Agent calls Main API
# backend_whatsapp/clients/nutrilens_client.py (in WhatsApp microservice)
class NutriLensClient:
    """Client to call main NutriLens API."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key

    async def log_meal(
        self,
        user_id: int,
        meal_log_id: int,
        portion_multiplier: float = 1.0
    ) -> LogMealResult:
        """Call main API to log meal."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tracking/log-meal",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "user_id": user_id,
                    "meal_log_id": meal_log_id,
                    "portion_multiplier": portion_multiplier
                }
            )
            return LogMealResult(**response.json())


# ===== WhatsApp Service Uses Client =====
# backend_whatsapp/services/meal_logging_service.py (in WhatsApp microservice)
class MealLoggingService:
    """WhatsApp service delegates to main API."""

    def __init__(self, nutrilens_client: NutriLensClient):
        self.nutrilens_client = nutrilens_client

    async def log_meal_from_whatsapp(
        self,
        user_id: int,
        meal_type: str,
        portion: str
    ):
        """Log meal via WhatsApp - delegates to main API."""

        # WhatsApp-specific logic (parse message, validate)
        meal_log_id = await self._find_planned_meal(user_id, meal_type)
        portion_multiplier = self._parse_portion(portion)

        # Delegate to main API (no duplication!)
        result = await self.nutrilens_client.log_meal(
            user_id=user_id,
            meal_log_id=meal_log_id,
            portion_multiplier=portion_multiplier
        )

        # WhatsApp-specific response
        return self._format_whatsapp_message(result)
```

### Benefits
✅ Zero code duplication
✅ Single source of truth (main API)
✅ WhatsApp agent is thin (just message parsing + API calls)
✅ Business logic in one place

---

### 3. Notification Service Integration

#### Architecture

```python
# ===== Event-Driven Integration =====

# Main Backend publishes events
# backend/app/events/event_publisher.py
class EventPublisher:
    """Publishes events to message queue."""

    def __init__(self, rabbitmq_client: RabbitMQClient):
        self.rabbitmq_client = rabbitmq_client

    async def publish(self, event_type: str, event_data: Any):
        """Publish event to message queue."""
        await self.rabbitmq_client.publish(
            exchange="nutrilens.events",
            routing_key=event_type,
            message=event_data
        )


# Notification Service subscribes to events
# backend_notifications/consumers/meal_plan_consumer.py (in Notification microservice)
class MealPlanEventConsumer:
    """Consumes meal plan events from message queue."""

    def __init__(
        self,
        rabbitmq_client: RabbitMQClient,
        notification_service: NotificationService
    ):
        self.rabbitmq_client = rabbitmq_client
        self.notification_service = notification_service

    async def consume(self):
        """Listen for events and send notifications."""

        await self.rabbitmq_client.subscribe(
            exchange="nutrilens.events",
            routing_key="meal_plan.generated",
            callback=self.handle_meal_plan_generated
        )

        await self.rabbitmq_client.subscribe(
            exchange="nutrilens.events",
            routing_key="meal.logged",
            callback=self.handle_meal_logged
        )

    async def handle_meal_plan_generated(self, event: MealPlanGeneratedEvent):
        """React to meal plan generation."""
        await self.notification_service.send_push_notification(
            user_id=event.user_id,
            title="Meal Plan Ready! 🍽️",
            body="Your personalized meal plan for the week is ready.",
            data={"plan_id": event.meal_plan_id}
        )

        await self.notification_service.send_email(
            user_id=event.user_id,
            subject="Your Weekly Meal Plan",
            template="meal_plan_ready",
            data={"plan_id": event.meal_plan_id}
        )

    async def handle_meal_logged(self, event: MealLoggedEvent):
        """React to meal logging."""
        # Check if user hit daily goals
        if event.is_goal_met:
            await self.notification_service.send_push_notification(
                user_id=event.user_id,
                title="Goals Achieved! 🎉",
                body=f"You've hit your daily {event.goal_type} goal!",
                data={"meal_log_id": event.meal_log_id}
            )
```

### Benefits
✅ Asynchronous communication (non-blocking)
✅ Notification service is independent
✅ Can have multiple consumers
✅ Event replay for debugging

---

## Microservice Communication Patterns

### Pattern 1: Synchronous (HTTP/gRPC)
**Use When**: Need immediate response

```python
# Receipt Scanner, WhatsApp Agent → Main API
result = await nutrilens_client.log_meal(...)
```

**Pros**: Simple, immediate feedback
**Cons**: Coupling, latency, failure propagation

### Pattern 2: Asynchronous (Message Queue)
**Use When**: Fire-and-forget operations

```python
# Main API → Notification Service
await event_publisher.publish("meal_plan.generated", event_data)
```

**Pros**: Decoupled, fault-tolerant, scalable
**Cons**: Eventual consistency, harder debugging

### Pattern 3: API Gateway (Future)
**Use When**: Multiple clients, rate limiting needed

```
┌──────────────┐
│ API Gateway  │ ← All clients go through gateway
└──────────────┘
        │
        ├──▶ Main NutriLens API
        ├──▶ Receipt Scanner
        ├──▶ WhatsApp Agent
        └──▶ Notification Service
```

---

## Service Discovery

### Current (Hardcoded)
```python
# settings.py
RECEIPT_SCANNER_URL = "http://localhost:8001"
WHATSAPP_AGENT_URL = "http://localhost:3000"
```

### Target (Service Registry)
```python
# Using Consul/etcd for service discovery
class ServiceRegistry:
    """Discover microservices dynamically."""

    def __init__(self, consul_client):
        self.consul_client = consul_client

    async def get_service_url(self, service_name: str) -> str:
        """Get service URL from registry."""
        service = await self.consul_client.discover(service_name)
        return f"http://{service.address}:{service.port}"


# Client uses service discovery
class HttpReceiptScannerClient:
    def __init__(self, service_registry: ServiceRegistry):
        self.service_registry = service_registry

    async def scan_receipt(self, image_url: str):
        # Discover service dynamically
        base_url = await self.service_registry.get_service_url("receipt-scanner")

        async with httpx.AsyncClient() as client:
            response = await client.post(f"{base_url}/scan", ...)
```

---

## Error Handling Strategy

### Circuit Breaker Pattern

```python
# backend/app/clients/circuit_breaker.py
class CircuitBreaker:
    """Prevents cascading failures."""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open

    def is_open(self) -> bool:
        """Check if circuit is open."""
        if self.state == "open":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half-open"
                return False
            return True
        return False

    def record_failure(self):
        """Record failure."""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.last_failure_time = time.time()

    def record_success(self):
        """Record success."""
        self.failure_count = 0
        self.state = "closed"
```

---

## Testing Microservices Integration

### Unit Tests (Mock Client)
```python
def test_receipt_processing():
    """Test with mock client."""
    mock_client = MockReceiptScannerClient()
    service = ReceiptProcessingService(mock_client, ...)

    result = await service.process_receipt(user_id=1, image_url="...")

    assert result.items[0].name == "Chicken Breast"
```

### Integration Tests (Real Microservice)
```python
@pytest.mark.integration
def test_receipt_scanner_integration():
    """Test with real microservice."""
    client = HttpReceiptScannerClient(base_url="http://localhost:8001")

    result = await client.scan_receipt("https://s3.../receipt.jpg")

    assert len(result.items) > 0
```

### Contract Tests (Pact)
```python
# Ensure main API and microservice agree on contract
def test_receipt_scanner_contract():
    """Consumer-driven contract test."""
    # Define expected contract
    expected_response = {
        "items": [
            {"name": str, "quantity": float, "unit": str}
        ],
        "total": float
    }

    # Verify microservice honors contract
    # ...
```

---

## Migration Strategy for Microservices

### Phase 1: Extract Service Clients
1. Create `IReceiptScannerClient` interface
2. Implement `HttpReceiptScannerClient`
3. Replace direct httpx calls with client

### Phase 2: Consolidate WhatsApp Logic
1. Remove duplicate code from `orchestrator.py`
2. Make WhatsApp agent call main API
3. Delete duplicated endpoints

### Phase 3: Event-Driven Notifications
1. Set up RabbitMQ/Redis Pub/Sub
2. Create EventPublisher
3. Build Notification Service as subscriber

### Phase 4: Add Resilience
1. Implement Circuit Breaker
2. Add retry logic
3. Implement service discovery

---

## Microservices Summary

| Microservice | Communication | Integration Point | Pattern |
|--------------|---------------|-------------------|---------|
| **Receipt Scanner** | Synchronous HTTP | Service Client | Request/Response |
| **WhatsApp Agent** | Synchronous HTTP | Calls Main API | API Client |
| **Notification Service** | Asynchronous | Message Queue | Event-Driven |

All microservices integrate through the **Service Client Layer**, maintaining clean architecture.
