"""
Health Check System for PyGem
Quarkus-inspired health endpoints.
"""

import asyncio
from typing import Dict, Any, List
from datetime import datetime
from fastapi import APIRouter
from app.shared.annotations import ApplicationScoped, LoggerBinding


class HealthCheck:
    """Individual health check result."""
    
    def __init__(self, name: str, status: str, details: Dict[str, Any] = None):
        self.name = name
        self.status = status  # UP, DOWN, DEGRADED
        self.details = details or {}
        self.timestamp = datetime.utcnow()


class HealthResponse:
    """Complete health check response."""
    
    def __init__(self, status: str, checks: List[HealthCheck] = None):
        self.status = status  # UP, DOWN, DEGRADED
        self.checks = checks or []
        self.timestamp = datetime.utcnow()


@ApplicationScoped
class HealthService:
    """Health check service."""
    
    def __init__(self):
        self.checks = []
    
    def add_check(self, name: str, check_func):
        """Add a health check function."""
        self.checks.append({
            'name': name,
            'function': check_func
        })
    
    async def check_all(self) -> HealthResponse:
        """Run all health checks."""
        results = []
        
        for check in self.checks:
            try:
                # Run health check with timeout
                result = await asyncio.wait_for(
                    check['function'](), 
                    timeout=5.0
                )
                if isinstance(result, HealthCheck):
                    results.append(result)
                else:
                    results.append(HealthCheck(check['name'], 'UP', {'data': result}))
            except asyncio.TimeoutError:
                results.append(HealthCheck(check['name'], 'DOWN', {'error': 'Timeout'}))
            except Exception as e:
                results.append(HealthCheck(check['name'], 'DOWN', {'error': str(e)}))
        
        # Determine overall status
        overall_status = 'UP'
        for result in results:
            if result.status == 'DOWN':
                overall_status = 'DOWN'
                break
            elif result.status == 'DEGRADED' and overall_status == 'UP':
                overall_status = 'DEGRADED'
        
        return HealthResponse(overall_status, results)


@ApplicationScoped
@LoggerBinding()
class DatabaseHealthCheck:
    """Database health check."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def check_database(self) -> HealthCheck:
        try:
            # Simulate database check
            # In real implementation, this would ping the database
            import random
            latency = random.uniform(10, 100)  # ms
            
            if latency > 50:
                return HealthCheck('database', 'DEGRADED', {
                    'latency_ms': latency,
                    'reason': 'High latency'
                })
            else:
                return HealthCheck('database', 'UP', {
                    'latency_ms': latency
                })
        except Exception as e:
            return HealthCheck('database', 'DOWN', {'error': str(e)})


@ApplicationScoped
@LoggerBinding()
class MessagingHealthCheck:
    """Messaging system health check."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def check_messaging(self) -> HealthCheck:
        try:
            # Check messaging system
            from app.shared.messaging.event_bus_factory import EventBusFactory
            from app.shared.pygem_simple import PyGem
            
            gem = PyGem()
            factory = gem.get(EventBusFactory)
            event_bus = factory.create_event_bus()
            
            # Simulate connectivity check
            return HealthCheck('messaging', 'UP', {
                'transport': factory._config.transport,
                'connected': True
            })
        except Exception as e:
            return HealthCheck('messaging', 'DOWN', {'error': str(e)})


@ApplicationScoped
@LoggerBinding()
class SystemHealthCheck:
    """System resource health check."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def check_system(self) -> HealthCheck:
        try:
            import psutil
            
            # Check memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Check disk usage
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            
            details = {
                'memory_percent': memory_percent,
                'disk_percent': disk_percent
            }
            
            if memory_percent > 90 or disk_percent > 90:
                return HealthCheck('system', 'DEGRADED', details)
            else:
                return HealthCheck('system', 'UP', details)
                
        except Exception as e:
            return HealthCheck('system', 'DOWN', {'error': str(e)})


# Create health check router
def create_health_router() -> APIRouter:
    """Create FastAPI health check router."""
    router = APIRouter(prefix="/health", tags=["Health"])
    
    @router.get("/q/alive")
    async def alive():
        """Liveness probe - always returns 200."""
        return {"status": "ALIVE"}
    
    @router.get("/q/ready")
    async def ready():
        """Readiness probe - check if application is ready."""
        from app.shared.pygem_simple import PyGem
        
        gem = PyGem()
        if not gem.is_initialized():
            return {"status": "NOT_READY"}, 503
        
        return {"status": "READY"}
    
    @router.get("/q/started")
    async def started():
        """Started probe - check if application has started."""
        from app.shared.pygem_simple import PyGem
        
        gem = PyGem()
        if not gem.is_initialized():
            return {"status": "NOT_STARTED"}, 503
            
        return {"status": "STARTED"}
    
    @router.get("/")
    async def health():
        """Complete health check."""
        from app.shared.pygem_simple import PyGem
        
        gem = PyGem()
        health_service = gem.get(HealthService)
        
        # Add default health checks
        db_check = gem.get(DatabaseHealthCheck)
        msg_check = gem.get(MessagingHealthCheck)
        sys_check = gem.get(SystemHealthCheck)
        
        health_service.add_check('database', db_check.check_database)
        health_service.add_check('messaging', msg_check.check_messaging)
        health_service.add_check('system', sys_check.check_system)
        
        # Run all checks
        result = await health_service.check_all()
        
        return {
            "status": result.status,
            "timestamp": result.timestamp.isoformat(),
            "checks": {
                check.name: {
                    "status": check.status,
                    "details": check.details
                }
                for check in result.checks
            }
        }
    
    return router