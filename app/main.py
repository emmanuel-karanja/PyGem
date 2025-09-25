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

settings = Settings()

# Apparently startup events  i.e. 
# starting FastAPI 0.101+, the @app.on_event("startup") and @app.on_event("shutdown") decorators are deprecated.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ----------------------------
    # Startup logic
    # ----------------------------
    logger.info("🚀 Starting application...")

    # Redis
    await redis_client.connect()
    logger.info("✅ Redis connected")

    # Kafka
    await event_bus.start()
    logger.info("✅ Kafka client started")

    # SQLAlchemy: import feature models and create tables
    await init_db(str(settings.database_url), app_path="app")
    logger.info("✅ SQLAlchemy DB initialized")

    # HighThroughputPostgresClient
    await postgres_client.start()
    logger.info("✅ HighThroughputPostgresClient started")

    logger.info("🎉 Application startup complete")

    yield  # Hand control back to FastAPI; the app is running

    # ----------------------------
    # Shutdown logic
    # ----------------------------
    logger.info("⚠️ Shutting down application...")

    # HighThroughputPostgresClient
    await postgres_client.stop()
    logger.info("✅ HighThroughputPostgresClient stopped")

    # Kafka
    await event_bus.stop()
    logger.info("✅ Kafka client stopped")

    # Redis
    await redis_client.close()
    logger.info("✅ Redis disconnected")

    logger.info("🎯 Application shutdown complete")


app = FastAPI(title="Modular Monolith FastAPI App", lifespan=lifespan)

# Include feature routers
app.include_router(feature1_router, prefix="/feature1")
app.include_router(feature2_router, prefix="/feature2")
