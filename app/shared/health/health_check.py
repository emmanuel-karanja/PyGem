import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.shared.logger import JohnWickLogger
from app.config.dependencies import redis_client, event_bus, postgres_client
import aioredis
import asyncpg
import socket
import time

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

    async def check_redis(self) -> Dict[str, Any]:
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Checking Redis (attempt {attempt})...")
                redis = await aioredis.from_url(f"redis://{redis_client.host}:{redis_client.port}")
                pong = await redis.ping()
                await redis.close()
                if pong:
                    self.logger.info("✅ Redis healthy")
                    return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}
            except Exception as e:
                self.logger.warning("Redis check failed", extra={"attempt": attempt, "error": str(e)})
                await asyncio.sleep(self.retry_delay)
        return {"status": "unhealthy", "error": "Cannot connect to Redis", "checked_at": datetime.utcnow().isoformat()}

    async def check_postgres(self) -> Dict[str, Any]:
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Checking Postgres (attempt {attempt})...")
                conn = await asyncpg.connect(dsn=str(postgres_client.dsn))
                await conn.close()
                self.logger.info("✅ Postgres healthy")
                return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}
            except Exception as e:
                self.logger.warning("Postgres check failed", extra={"attempt": attempt, "error": str(e)})
                await asyncio.sleep(self.retry_delay)
        return {"status": "unhealthy", "error": "Cannot connect to Postgres", "checked_at": datetime.utcnow().isoformat()}

    async def check_kafka(self, host: str = "localhost", port: int = 9092) -> Dict[str, Any]:
        """Simple TCP check to Kafka broker"""
        for attempt in range(1, self.retries + 1):
            try:
                self.logger.info(f"Checking Kafka (attempt {attempt})...")
                with socket.create_connection((host, port), timeout=5):
                    self.logger.info("✅ Kafka healthy")
                    return {"status": "healthy", "checked_at": datetime.utcnow().isoformat()}
            except Exception as e:
                self.logger.warning("Kafka check failed", extra={"attempt": attempt, "error": str(e)})
                await asyncio.sleep(self.retry_delay)
        return {"status": "unhealthy", "error": "Cannot connect to Kafka", "checked_at": datetime.utcnow().isoformat()}

    async def run_all(self, services: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Run all health checks or a subset of services.
        :param services: List of services to check (default: all)
        """
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

# ----------------------------
# CLI Example
# ----------------------------
if __name__ == "__main__":
    import typer

    app = typer.Typer()
    logger = JohnWickLogger("health_service")

    @app.command()
    def check(services: str = "all"):
        """Run health checks from CLI"""
        service_list = None if services == "all" else services.split(",")
        hc = HealthChecker(logger=logger)
        results = asyncio.run(hc.run_all(service_list))
        print(json.dumps(results, indent=2))

    app()
