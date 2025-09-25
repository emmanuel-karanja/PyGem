import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import socket

import aioredis
import asyncpg

from app.shared.logger import JohnWickLogger
from app.config.settings import Settings
from app.shared.retry.base import RetryPolicy
from app.shared.retry import FixedDelayRetry

settings = Settings()


class HealthChecker:
    def __init__(
        self,
        logger: JohnWickLogger,
        retry_policy: Optional[RetryPolicy] = None
    ):
        """
        Initialize the health checker.
        :param logger: JohnWickLogger instance
        :param retry_policy: RetryPolicy instance (default FixedDelayRetry)
        """
        self.logger = logger
        self.retry_policy: RetryPolicy = retry_policy or FixedDelayRetry(max_retries=3)

    async def check_redis(self) -> Dict[str, Any]:
        """Redis health check using retry policy."""
        host, port = settings.redis.host, settings.redis.port

        async def _check():
            self.logger.info("Checking Redis...")
            r = aioredis.Redis(host=host, port=port, decode_responses=True)
            pong = await r.ping()
            await r.close()
            if pong:
                self.logger.info("✅ Redis healthy")
                return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}
            raise ConnectionError("Redis did not respond to PING")

        try:
            return await self.retry_policy.execute(_check)
        except Exception as e:
            self.logger.warning("Redis check failed", extra={"error": str(e)})
            return {"status": "unhealthy", "error": str(e), "checked_at": datetime.utcnow().isoformat()}

    async def check_postgres(self) -> Dict[str, Any]:
        """Postgres health check using retry policy."""
        dsn = settings.postgres.get_database_url(settings.app.env_mode)

        async def _check():
            self.logger.info("Checking Postgres...")
            conn = await asyncpg.connect(dsn=dsn)
            await conn.close()
            self.logger.info("✅ Postgres healthy")
            return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}

        try:
            return await self.retry_policy.execute(_check)
        except Exception as e:
            self.logger.warning("Postgres check failed", extra={"error": str(e)})
            return {"status": "unhealthy", "error": str(e), "checked_at": datetime.utcnow().isoformat()}

    async def check_kafka(self) -> Dict[str, Any]:
        """Kafka TCP health check using retry policy."""
        host, port = settings.kafka.host, settings.kafka.port

        async def _check():
            self.logger.info("Checking Kafka...")
            with socket.create_connection((host, port), timeout=5):
                self.logger.info("✅ Kafka healthy")
                return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}

        try:
            return await self.retry_policy.execute(_check)
        except Exception as e:
            self.logger.warning("Kafka check failed", extra={"error": str(e)})
            return {"status": "unhealthy", "error": str(e), "checked_at": datetime.utcnow().isoformat()}

    async def run_all(self, services: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run all health checks or a subset of services."""
        if services is None:
            services = ["redis", "postgres", "kafka"]

        self.logger.info(f"Running health checks for services: {services}")
        results: Dict[str, Any] = {}
        tasks = []

        if "redis" in services:
            tasks.append(self.check_redis())
        if "postgres" in services:
            tasks.append(self.check_postgres())
        if "kafka" in services:
            tasks.append(self.check_kafka())

        check_results = await asyncio.gather(*tasks)
        for service_name, result in zip(services, check_results):
            results[service_name] = result

        # Add summary
        total = len(results)
        healthy = sum(1 for r in results.values() if r["status"] == "healthy")
        results["summary"] = {"total": total, "healthy": healthy, "unhealthy": total - healthy}

        return results
