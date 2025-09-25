from pydantic_settings import BaseSettings
from pydantic import PostgresDsn

class Settings(BaseSettings):
    # ----------------------------
    # General
    # ----------------------------
    app_name: str = "ModularMonolithApp"
    debug: bool = True

    # ----------------------------
    # Redis
    # ----------------------------
    redis_host: str = "pygem_redis"
    redis_port: int = 6379

    @property
    def redis_url(self) -> str:
        host = self.redis_host
        try:
            import socket
            socket.gethostbyname(host)
        except:
            host = "localhost"
        return f"redis://{host}:{self.redis_port}"

    # ----------------------------
    # Kafka
    # ----------------------------
    kafka_host: str = "pygem_kafka"
    kafka_port: int = 9092
    kafka_topic: str = "feature_events"
    kafka_dlq_topic: str = "feature_events_dlq"
    kafka_group_id: str = "feature_group"

    @property
    def kafka_bootstrap_servers(self) -> str:
        return f"{self.kafka_host}:{self.kafka_port}"

    # ----------------------------
    # Logger
    # ----------------------------
    log_file: str = "app.log"
    log_level: str = "INFO"

    # ----------------------------
    # PostgreSQL / SQLAlchemy
    # ----------------------------
    db_host: str = "pygem_postgres"
    db_port: int = 5432
    db_user: str = "myuser"
    db_password: str = "mypassword"
    db_name: str = "mydatabase"

    # Fix to Pydantic2 issue of Pydanticv2 _BaseMultiHostUrl.build() no longer supports user or password
    @property
    def database_url(self) -> PostgresDsn:
        url = f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        return PostgresDsn(url)

    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # ----------------------------
    # Pydantic configuration
    # ----------------------------
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
