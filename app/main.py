from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config.dependencies import redis_client, redis_event_bus, postgres_client, async_sessionmaker,kafka_client,redis_event_bus
from app.config.settings import Settings
from app.config.db_session import init_db
from app.config.logger import logger
from app.shared.health import health_router
import asyncio
import uuid

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

async def test_event_bus(bus, test_event: str, payload: dict):
    """
    Simple test: publish a message and subscribe to receive it once.
    """
    fut = asyncio.get_event_loop().create_future()

    async def callback(msg):
        logger.info(f"Received test message on {test_event}: {msg}")
        if not fut.done():
            fut.set_result(True)

    # Subscribe to test event
    await bus.subscribe(test_event, callback)

    # Publish test message
    await bus.publish(test_event, payload)

    try:
        await asyncio.wait_for(fut, timeout=5)
        logger.info(f"✅ Event bus '{bus.__class__.__name__}' test succeeded for event '{test_event}'")
    except asyncio.TimeoutError:
        logger.error(f"❌ Event bus '{bus.__class__.__name__}' test failed: message not received")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting application...")

    # Wait for Redis to be ready
    await wait_with_retry("Redis client", redis_client.connect)
   
    #Wait for Redis event bus
    await wait_with_retry("Redis event bus",redis_event_bus.start)

   # Wait for Kafka client
   # await wait_with_retry("Kafka client", kafka_client.start)
    # Wait for Kafka event bus
  #  await wait_with_retry("Kafka event bus", event_bus.start)

    # Init DB
    await init_db(str(settings.database_url), app_path="app")
    logger.info("✅ SQLAlchemy DB initialized")

    # Wait for HighThroughputPostgresClient
    await wait_with_retry("PostgresClient", postgres_client.start)

    # ----------------------------
    # Event Bus tests
    # ----------------------------
    test_payload = {"id": str(uuid.uuid4()), "message": "test"}
    await test_event_bus(redis_event_bus, "feature_events", test_payload)
    # If you have a Redis event bus, you can also test similarly:
    # await test_event_bus(redis_event_bus, "redis_test_event", test_payload)

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
