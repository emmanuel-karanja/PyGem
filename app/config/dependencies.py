from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config.db_session import get_sessionmaker
from app.shared.database import PostgresClient
from app.config.factory import get_logger, get_redis_client, get_kafka_event_bus,get_kafka_client,get_redis_event_bus,get_postgres_client
from app.config.settings import Settings

# ----------------------------
# Config / Singleton Instances
# ----------------------------
settings = Settings()
logger = get_logger()
redis_client = get_redis_client()
redis_event_bus=get_redis_event_bus()
kafka_client=get_kafka_client()
kafka_event_bus = get_kafka_event_bus()
postgres_client = get_postgres_client()

# SQLAlchemy AsyncSession factory
async_sessionmaker = get_sessionmaker(settings.postgres.get_database_url(settings.app.env_mode,for_asyncpg=False))

# ----------------------------
# Dependency Injection Functions
# ----------------------------

# Redis client
def get_redis():
    return redis_client

#Kafka client

def get_kafka_client():
    return kafka_client

# Kafka event bus
def get_kafka():
    return kafka_event_bus

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

