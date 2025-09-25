from pydantic_settings import BaseSettings
from pydantic import field_validator
import os


class Settings(BaseSettings):
    # ----------------------------
    # General
    # ----------------------------
    app_name: str = "ModularMonolithApp"
    debug: bool = True
    env_mode: str = "local"  # "local" or "docker"

    # ----------------------------
    # Redis
    # ----------------------------
    redis_host_local: str = "127.0.0.1"
    redis_host_docker: str = "pygem_redis"
    redis_port: int = 6379

    @property
    def redis_host(self) -> str:
        return self.redis_host_docker if self.env_mode == "docker" else self.redis_host_local

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    # ----------------------------
    # Kafka
    # ----------------------------
    kafka_host_local: str = "127.0.0.1"
    kafka_host_docker: str = "pygem_kafka"
    kafka_port: int = 9092
    kafka_topic: str = "feature_events"
    kafka_dlq_topic: str = "feature_events_dlq"
    kafka_group_id: str = "feature_group"

    @property
    def kafka_host(self) -> str:
        return self.kafka_host_docker if self.env_mode == "docker" else self.kafka_host_local

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
    db_host_local: str = "127.0.0.1"
    db_host_docker: str = "pygem_postgres"
    db_port: int = 5432
    db_user: str = "myuser"
    db_password: str = "mypassword"
    db_name: str = "mydatabase"

    @property
    def db_host(self) -> str:
        return self.db_host_docker if self.env_mode == "docker" else self.db_host_local

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

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
