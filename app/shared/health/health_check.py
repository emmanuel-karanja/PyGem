import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
import socket

from app.shared.logger import JohnWickLogger
from app.config.dependencies import  postgres_client
import redis.asyncio as aioredis
import asyncpg

# ----------------------------
# HealthChecker Class
# ----------------------------
class HealthChecker:
    def __init__(self, logger: JohnWickLogger, retries: int = 3, retry_delay: float = 2.0):
        """
        Initialize the health checker.
        :param logger: JohnWickLogger instance
        :param retries: Number of retries per service
        :param retry_delay: Delay in seconds between retries
        """
        self.logger = logger
        self.retries = retries
        self.retry_delay = retry_delay

    async def check_redis(self, host: str = "127.0.0.1", port: int = 6379) -> Dict[str, Any]:
        """Direct Redis health check without using redis_client"""
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Checking Redis (attempt {attempt})...")
                r = aioredis.Redis(host=host, port=port, decode_responses=True)
                pong = await r.ping()
                await r.close()
                if pong:
                    self.logger.info("✅ Redis healthy")
                    return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}
            except Exception as e:
                self.logger.warning(
                    "Redis check failed", extra={"attempt": attempt, "error": str(e)}
                )
                await asyncio.sleep(self.retry_delay)
        return {
            "status": "unhealthy",
            "error": "Cannot connect to Redis",
            "checked_at": datetime.utcnow().isoformat(),
        }

    async def check_postgres(self) -> Dict[str, Any]:
        """Check PostgreSQL health"""
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Checking Postgres (attempt {attempt})...")
                conn = await asyncpg.connect(dsn=str(postgres_client.dsn))
                await conn.close()
                self.logger.info("✅ Postgres healthy")
                return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}
            except Exception as e:
                self.logger.warning(
                    "Postgres check failed", extra={"attempt": attempt, "error": str(e)}
                )
                await asyncio.sleep(self.retry_delay)
        return {
            "status": "unhealthy",
            "error": "Cannot connect to Postgres",
            "checked_at": datetime.utcnow().isoformat(),
        }

    async def check_kafka(self, host: str = "localhost", port: int = 9092) -> Dict[str, Any]:
        """Simple TCP check to Kafka broker"""
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Checking Kafka (attempt {attempt})...")
                with socket.create_connection((host, port), timeout=5):
                    self.logger.info("✅ Kafka healthy")
                    return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}
            except Exception as e:
                self.logger.warning(
                    "Kafka check failed", extra={"attempt": attempt, "error": str(e)}
                )
                await asyncio.sleep(self.retry_delay)
        return {
            "status": "unhealthy",
            "error": "Cannot connect to Kafka",
            "checked_at": datetime.utcnow().isoformat(),
        }

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
