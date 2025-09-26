from fastapi import FastAPI
from app.config.dependencies import (
    get_redis_client,
    get_redis_event_bus,
    get_postgres_client,
    get_kafka_client,
    get_kafka_event_bus,
)
from app.config.settings import Settings
from app.config.db_session import init_db
from app.shared.health import health_router
from app.shared.logger import JohnWickLogger
import asyncio

logger=JohnWickLogger(name="AppMain")
settings = Settings()
app = FastAPI(title="AppMain")

# ----------------------------
# Test endpoint
# ----------------------------
@app.get("/ping")
async def ping():
    """
    Simple test endpoint to verify the server is running.
    """
    logger.info("🏓 Ping endpoint hit")
    return {"status": "ok", "message": "pong"}

# ----------------------------
# Include the health check routes
# ----------------------------
app.include_router(health_router)
logger.info("✅ Health routes initialized")

# ----------------------------
# Startup event
# ----------------------------
@app.on_event("startup")
async def startup_event():
    # Initialize clients
    app.state.redis_client = get_redis_client()
    app.state.redis_event_bus = get_redis_event_bus()
    app.state.postgres_client = get_postgres_client()
    app.state.kafka_client = get_kafka_client()
    app.state.kafka_event_bus = get_kafka_event_bus()

    # Start all services concurrently
    await asyncio.gather(
        app.state.redis_client.connect(),
        app.state.redis_event_bus.start(),
        app.state.kafka_client.start(),
        app.state.kafka_event_bus.start(),
        app.state.postgres_client.start(),
    )

    # Initialize DB
    await init_db(
        str(settings.postgres.get_database_url(settings.app.env_mode, for_asyncpg=False)),
        app_path="app"
    )
    logger.info("✅ Application startup complete")

# ----------------------------
# Shutdown event
# ----------------------------
@app.on_event("shutdown")
async def shutdown_event():
    # Stop all services concurrently
    await asyncio.gather(
        app.state.postgres_client.stop(),
        app.state.kafka_event_bus.stop(),
        app.state.redis_event_bus.stop(),
        app.state.kafka_client.stop(),
        app.state.redis_client.close(),
    )
    logger.info("🎯 Application shutdown complete")
