from fastapi import FastAPI, APIRouter
from app.config.logger import JohnWickLogger
from app.shared.health import HealthChecker  # Assuming HealthChecker is in services/health_check.py
import asyncio

logger = JohnWickLogger("health_service")

# Create FastAPI router for health endpoints
health_router = APIRouter(prefix="/health", tags=["health"])

# Initialize HealthChecker
health_checker = HealthChecker(logger=logger)

@health_router.get("/", summary="Check all services")
async def check_all_services():
    """
    Run health checks for all registered services.
    Returns JSON with each service's health and a summary.
    """
    results = await health_checker.run_all()
    return results

@health_router.get("/redis", summary="Check Redis")
async def check_redis():
    result = await health_checker.check_redis()
    return {"redis": result}

@health_router.get("/postgres", summary="Check Postgres")
async def check_postgres():
    result = await health_checker.check_postgres()
    return {"postgres": result}

@health_router.get("/kafka", summary="Check Kafka")
async def check_kafka():
    result = await health_checker.check_kafka()
    return {"kafka": result}

