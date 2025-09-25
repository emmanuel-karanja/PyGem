from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.feature1.routes import router as feature1_router
from app.feature2.routes import router as feature2_router
from app.config.dependencies import (
    logger,
    redis_client,
    event_bus,
    postgres_client,
    async_sessionmaker,
)
from app.config.settings import Settings
from app.config.db_session import init_db
import asyncio

settings = Settings()

async def wait_with_retry(name: str, coro_func, retries: int = 10, delay: int = 2):
    """Utility to attempt async startup with progress logs"""
    for i in range(1, retries + 1):
        try:
            await coro_func()
            logger.info(f"✅ {name} ready")
            return
        except Exception as e:
            logger.warning(f"[{i}/{retries}] {name} not ready: {e}")
            await asyncio.sleep(delay)
    raise RuntimeError(f"❌ {name} failed to start after {retries} retries")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ----------------------------
    # Startup logic
    # ----------------------------
    logger.info("🚀 Starting application...")

    # Redis
    await wait_with_retry("Redis", redis_client.connect)
    
    # Kafka
    await wait_with_retry("Kafka client", event_bus.start)

    # SQLAlchemy
    await init_db(str(settings.database_url), app_path="app")
    logger.info("✅ SQLAlchemy DB initialized")

    # HighThroughputPostgresClient
    await wait_with_retry("HighThroughputPostgresClient", postgres_client.start)

    logger.info("🎉 Application startup complete")
    yield  # Hand control back to FastAPI; the app is running

    # ----------------------------
    # Shutdown logic
    # ----------------------------
    logger.info("⚠️ Shutting down application...")

    await postgres_client.stop()
    logger.info("✅ HighThroughputPostgresClient stopped")

    await event_bus.stop()
    logger.info("✅ Kafka client stopped")

    await redis_client.close()
    logger.info("✅ Redis disconnected")

    logger.info("🎯 Application shutdown complete")


app = FastAPI(title="Modular Monolith FastAPI App", lifespan=lifespan)

# Include feature routers
app.include_router(feature1_router, prefix="/feature1")
app.include_router(feature2_router, prefix="/feature2")
