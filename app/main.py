from fastapi import FastAPI
from app.feature1.routes import router as feature1_router
from app.feature2.routes import router as feature2_router
from app.config.dependencies import (
    logger,
    redis_client,
    event_bus,
    postgres_client,
)
from app.config.db_session import init_db, get_sessionmaker
from app.config.settings import Settings

settings = Settings()
app = FastAPI(title=settings.app_name)

# ----------------------------
# Include Feature Routers
# ----------------------------
app.include_router(feature1_router, prefix="/feature1")
app.include_router(feature2_router, prefix="/feature2")

# ----------------------------
# Startup / Shutdown Events
# ----------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting application...")

    # Redis
    await redis_client.connect()
    logger.info("✅ Redis connected")

    # Kafka / EventBus
    await event_bus.start()
    logger.info("✅ EventBus started")

    # SQLAlchemy async session and DB init
    get_sessionmaker(settings.database_url, echo=settings.db_echo)
    await init_db(settings.database_url, app_path="app")
    logger.info("✅ SQLAlchemy DB initialized")

    # HighThroughputPostgresClient
    await postgres_client.start()
    logger.info("✅ HighThroughputPostgresClient started")

    logger.info("🎉 Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("⚠️ Shutting down application...")

    # HighThroughputPostgresClient
    await postgres_client.stop()
    logger.info("✅ HighThroughputPostgresClient stopped")

    # Kafka / EventBus
    await event_bus.stop()
    logger.info("✅ EventBus stopped")

    # Redis
    await redis_client.close()
    logger.info("✅ Redis disconnected")

    logger.info("🎯 Application shutdown complete")
