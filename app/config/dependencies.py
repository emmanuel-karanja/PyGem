from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from session import get_sessionmaker
from database import HighThroughputPostgresClient
from app.config.factory import get_logger, get_redis_client, get_kafka_event_bus
from app.config.settings import Settings

# ----------------------------
# Config / Singleton Instances
# ----------------------------
settings = Settings()
logger = get_logger()
redis_client = get_redis_client(logger)
event_bus = get_kafka_event_bus(logger)
postgres_client = HighThroughputPostgresClient(dsn=settings.database_url, logger=logger)

# SQLAlchemy AsyncSession factory
async_sessionmaker = get_sessionmaker(settings.database_url)

# ----------------------------
# Dependency Injection Functions
# ----------------------------

# Redis client
def get_redis():
    return redis_client

# Kafka event bus
def get_kafka():
    return event_bus

# Async SQLAlchemy session (use with async context manager)
async def get_db_session() -> AsyncSession:
    async with async_sessionmaker() as session:
        yield session

# HighThroughputPostgresClient
def get_postgres_client():
    return postgres_client

# Logger
def get_app_logger():
    return logger
