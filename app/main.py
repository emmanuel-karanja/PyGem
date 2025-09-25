from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
from app.config.logger import logger
from app.shared.health import health_router
from app.config.init_core_services import init_core_services
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting application...")
    redis_client, redis_event_bus, postgres_client, kafka_client, kafka_event_bus = await init_core_services()
    yield
    logger.info("⚠️ Shutting down application...")
    await asyncio.gather(
        postgres_client.stop(),
        kafka_event_bus.stop(),
        redis_event_bus.stop(),
        kafka_client.stop(),
        redis_client.close()
    )
    logger.info("🎯 Application shutdown complete")


app = FastAPI(title="Modular Monolith FastAPI App", lifespan=lifespan)
app.include_router(health_router)
logger.info("✅ Health routes initialized")
