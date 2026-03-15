"""
Receipt Worker

Standalone process that polls receipt_scans for receipts in 'uploaded' state
and processes them asynchronously.

Run as:
    python -m app.workers.receipt_worker
"""

import asyncio
import logging
import signal

from sqlalchemy.orm import sessionmaker

from app.models.database import engine
from app.repositories.receipt_repository import ReceiptRepository
from app.repositories import InventoryRepository, UserProfileRepository, MealPlanRepository
from app.repositories.recipe_repository import RecipeRepository
from app.services.receipt_processing_service import ReceiptProcessingService
from app.services.intelligent_inventory_service_v2 import IntelligentInventoryServiceV2
from app.infrastructure.normalization.factory import create_normalizer
from app.infrastructure.normalization.repositories.item_repository import ItemRepository
from app.infrastructure.normalization.adapters.redis_cache_adapter import RedisCacheAdapter
from app.dependencies import get_s3_service, get_llm_orchestrator, get_openai_embedding_adapter
from app.core.redis_client import get_redis_client
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
BATCH_SIZE = 10
MAX_CONCURRENT_JOBS = 10


class ReceiptWorker:
    def __init__(self):
        self.should_stop = False
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
        self.session_factory = sessionmaker(bind=engine)

        # Stateless singletons — initialized once in initialize()
        self.s3_service = None
        self.redis_client = None
        self.llm_orchestrator = None
        self.embedding_adapter = None

        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)

    def _handle_shutdown(self, signum, _frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.should_stop = True

    async def initialize(self):
        self.s3_service = get_s3_service()
        self.redis_client = get_redis_client()
        self.llm_orchestrator = await get_llm_orchestrator()
        self.embedding_adapter = await get_openai_embedding_adapter()
        logger.info("Receipt worker initialized")

    async def _process_job(self, receipt_id: int, user_id: int, s3_key: str) -> None:
        async with self.semaphore:
            db = self.session_factory()
            try:
                # DB-dependent objects created per job — cannot be shared across concurrent sessions
                cache_adapter = RedisCacheAdapter(redis_client=self.redis_client)
                item_repo = ItemRepository(db=db, cache_adapter=cache_adapter)

                normalizer = await create_normalizer(
                    db=db,
                    redis_client=self.redis_client,
                    llm_orchestrator=self.llm_orchestrator,
                    embedding_adapter=self.embedding_adapter,
                    item_repo=item_repo
                )

                inventory_service = IntelligentInventoryServiceV2(
                    inventory_repo=InventoryRepository(db),
                    recipe_repo=RecipeRepository(db),
                    normalizer=normalizer,
                    item_repo=item_repo,
                    db=db,
                    llm_orchestrator=self.llm_orchestrator,
                    embedding_adapter=self.embedding_adapter,
                    user_profile_repo=UserProfileRepository(db),
                    meal_plan_repo=MealPlanRepository(db)
                )

                receipt_service = ReceiptProcessingService(
                    receipt_repo=ReceiptRepository(db),
                    s3_service=self.s3_service,
                    inventory_service=inventory_service,
                    scanner_url=settings.receipt_scanner_url
                )

                await receipt_service.execute_processing(
                    receipt_id=receipt_id,
                    user_id=user_id,
                    s3_key=s3_key
                )

            except Exception as e:
                logger.error(f"Unhandled error processing receipt {receipt_id}: {e}")
            finally:
                db.close()

    async def run(self):
        await self.initialize()
        logger.info("Receipt worker started")

        while not self.should_stop:
            try:
                db = self.session_factory()
                try:
                    receipt_repo = ReceiptRepository(db)
                    uploaded_receipts = receipt_repo.get_uploaded_receipts(limit=BATCH_SIZE)

                    if uploaded_receipts:
                        for receipt in uploaded_receipts:
                            s3_key = receipt.s3_url.split('.amazonaws.com/')[-1]
                            receipt_repo.update_receipt_scan_status(
                                receipt_id=receipt.id,
                                status='processing'
                            )
                            asyncio.create_task(
                                self._process_job(
                                    receipt_id=receipt.id,
                                    user_id=receipt.user_id,
                                    s3_key=s3_key
                                )
                            )
                            logger.info(f"Queued receipt {receipt.id} for processing")

                finally:
                    db.close()

            except Exception as e:
                logger.error(f"Receipt worker poll error: {e}")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        logger.info("Receipt worker stopped")


async def main():
    worker = ReceiptWorker()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())