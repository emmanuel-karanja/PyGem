import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import socket

import aioredis
import asyncpg

from app.shared.logger import JohnWickLogger
from app.config.dependencies import postgres_client
from app.shared.retry import FixedDelayRetry
from app.shared.retry.base import RetryPolicy


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
        self.retry_policy: RetryPolicy = retry_policy or FixedDelayRetry()

    async def check_redis(self, host: str = "127.0.0.1", port: int = 6379) -> Dict[str, Any]:
        """Redis health check using retry policy."""
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
        async def _check():
            self.logger.info("Checking Postgres...")
            conn = await asyncpg.connect(dsn=str(postgres_client.dsn))
            await conn.close()
            self.logger.info("✅ Postgres healthy")
            return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}

        try:
            return await self.retry_policy.execute(_check)
        except Exception as e:
            self.logger.warning("Postgres check failed", extra={"error": str(e)})
            return {"status": "unhealthy", "error": str(e), "checked_at": datetime.utcnow().isoformat()}

    async def check_kafka(self, host: str = "localhost", port: int = 9092) -> Dict[str, Any]:
        """Kafka TCP health check using retry policy."""
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
