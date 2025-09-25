from pydantic_settings import BaseSettings
from pydantic import Field

# ----------------------------
# General / App settings
# ----------------------------
class AppSettings(BaseSettings):
    app_name: str = "ModularMonolithApp"
    debug: bool = True
    env_mode: str = "local"  # "local" or "docker"

    # Logger
    log_file: str = "app.log"
    log_level: str = "INFO"


# ----------------------------
# Redis settings
# ----------------------------
class RedisSettings(BaseSettings):
    host_local: str = "127.0.0.1"
    host_docker: str = "pygem_redis"
    port: int = 6379

    max_retries: int = 5
    retry_backoff: float = 1.0

    def get_host(self, env_mode: str) -> str:
        return self.host_docker if env_mode == "docker" else self.host_local

    def get_url(self, env_mode: str) -> str:
        return f"redis://{self.get_host(env_mode)}:{self.port}/0"


# ----------------------------
# Kafka settings
# ----------------------------
class KafkaSettings(BaseSettings):
    host_local: str = "127.0.0.1"
    host_docker: str = "pygem_kafka"
    port: int = 9092

    default_topic: str = "pygem_default"
    feature_topic: str = "feature_events"
    dlq_topic: str = "feature_events_dlq"
    group_id: str = "feature_group"

    max_concurrency: int = 5
    batch_size: int = 10
    max_retries: int = 5
    retry_backoff: float = 1.0

    def get_host(self, env_mode: str) -> str:
        return self.host_docker if env_mode == "docker" else self.host_local

    def get_bootstrap_servers(self, env_mode: str) -> str:
        return f"{self.get_host(env_mode)}:{self.port}"


# ----------------------------
# PostgreSQL / DB settings
# ----------------------------
class PostgresSettings(BaseSettings):
    host_local: str = "127.0.0.1"
    host_docker: str = "pygem_postgres"
    port: int = 5432
    user: str = "myuser"
    password: str = "mypassword"
    db_name: str = "mydatabase"

    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 1800

    max_retries: int = 3
    retry_backoff: float = 0.5

    def get_host(self, env_mode: str) -> str:
        return self.host_docker if env_mode == "docker" else self.host_local

    def get_database_url(self, env_mode: str) -> str:
        host = self.get_host(env_mode)
        return f"postgresql+asyncpg://{self.user}:{self.password}@{host}:{self.port}/{self.db_name}"


# ----------------------------
# Top-level settings
# ----------------------------
class Settings(BaseSettings):
    app: AppSettings = AppSettings()
    redis: RedisSettings = RedisSettings()
    kafka: KafkaSettings = KafkaSettings()
    postgres: PostgresSettings = PostgresSettings()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
