from pydantic_settings import BaseSettings
from pydantic import PostgresDsn

class Settings(BaseSettings):
    # General
    app_name: str = "ModularMonolithApp"
    debug: bool = True

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "feature_events"
    kafka_dlq_topic: str = "feature_events_dlq"
    kafka_group_id: str = "feature_group"

    # Logger
    log_file: str = "app.log"
    log_level: str = "INFO"

    # PostgreSQL / SQLAlchemy
    database_url: PostgresDsn = "postgresql+asyncpg://user:password@localhost:5432/mydatabase"
    db_echo: bool = False              # Enable SQLAlchemy echo for debugging
    db_pool_size: int = 10             # Minimum connections in pool
    db_max_overflow: int = 20          # Extra connections allowed
    db_pool_timeout: int = 30          # Seconds to wait for a connection
    db_pool_recycle: int = 1800        # Recycle connections every 30 minutes

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
