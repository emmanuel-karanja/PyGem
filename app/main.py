from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config.dependencies import redis_client, event_bus, postgres_client, async_sessionmaker
from app.config.settings import Settings
from app.config.db_session import init_db
from app.config.logger import logger
from app.shared.health import health_router
import asyncio

settings = Settings()

async def wait_with_retry(name: str, coro_func, retries: int = 10, delay: int = 2):
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
    logger.info("🚀 Starting application...")

    # Wait for Redis to be ready
    await wait_with_retry("Redis", redis_client.connect)

    # Wait for Kafka, note that event_bus.start_producer() is a function and start_producer() is a coroutine object
    await wait_with_retry("Kafka client", event_bus.start_producer)

    # Init DB
    await init_db(str(settings.database_url), app_path="app")
    logger.info("✅ SQLAlchemy DB initialized")

    # Wait for HighThroughputPostgresClient
    await wait_with_retry("PostgresClient", postgres_client.start)

    logger.info("🎉 Application startup complete")
    yield

    # Shutdown
    logger.info("⚠️ Shutting down application...")
    await postgres_client.stop()
    await event_bus.stop()
    await redis_client.close()
    logger.info("🎯 Application shutdown complete")

# Create app
app = FastAPI(title="Modular Monolith FastAPI App", lifespan=lifespan)
app.include_router(health_router)
logger.info("✅ Health routes initialized")