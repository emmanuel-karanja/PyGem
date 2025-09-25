from fastapi import FastAPI, APIRouter
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

# HealthChecker import
from app.shared.health import HealthChecker  # make sure you have this file

settings = Settings()
health_checker = HealthChecker(logger=logger)

# ----------------------------
# Utility function for startup retries
# ----------------------------
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


# ----------------------------
# Lifespan (startup/shutdown) logic
# ----------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting application...")

    await wait_with_retry("Redis", redis_client.connect)
    await wait_with_retry("Kafka client", event_bus.start)
    await init_db(str(settings.database_url), app_path="app")
    logger.info("✅ SQLAlchemy DB initialized")
    await wait_with_retry("HighThroughputPostgresClient", postgres_client.start)

    logger.info("🎉 Application startup complete")
    yield  # app is running

    logger.info("⚠️ Shutting down application...")
    await postgres_client.stop()
    logger.info("✅ HighThroughputPostgresClient stopped")
    await event_bus.stop()
    logger.info("✅ Kafka client stopped")
    await redis_client.close()
    logger.info("✅ Redis disconnected")
    logger.info("🎯 Application shutdown complete")


# ----------------------------
# FastAPI app
# ----------------------------
app = FastAPI(title="Modular Monolith FastAPI App", lifespan=lifespan)

# Feature routers
app.include_router(feature1_router, prefix="/feature1")
app.include_router(feature2_router, prefix="/feature2")

# ----------------------------
# Health routes
# ----------------------------
health_router = APIRouter(prefix="/health", tags=["health"])

@health_router.get("/", summary="Check all services")
async def check_all_services():
    """Run health checks for all registered services"""
    return await health_checker.run_all()

@health_router.get("/redis", summary="Check Redis")
async def check_redis():
    return {"redis": await health_checker.check_redis()}

@health_router.get("/postgres", summary="Check Postgres")
async def check_postgres():
    return {"postgres": await health_checker.check_postgres()}

@health_router.get("/kafka", summary="Check Kafka")
async def check_kafka():
    return {"kafka": await health_checker.check_kafka()}

app.include_router(health_router)
logger.info("✅ Health routes initialized")
