"""
Simple Working Example of PyGem Framework
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.shared.annotations import ApplicationScoped, LoggerBinding
from fastapi import APIRouter
import asyncio


@ApplicationScoped
@LoggerBinding()
class SimpleService:
    def __init__(self, logger):
        self.logger = logger
        self.counter = 0
    
    def hello(self, name: str):
        self.counter += 1
        message = f"Hello {name}! (called {self.counter} times)"
        self.logger.info(message)
        return {"message": message, "count": self.counter}


# Create API routes
simple_router = APIRouter(prefix="/simple", tags=["simple"])

@simple_router.get("/hello/{name}")
async def hello_world(name: str):
    from app.shared.pygem_simple import PyGem
    
    gem = PyGem(["app.examples"])
    gem.initialize()
    
    service = gem.get(SimpleService)
    result = service.hello(name)
    
    return result


@simple_router.get("/status")
async def get_status():
    from app.shared.pygem_simple import PyGem
    
    gem = PyGem(["app.examples"])
    gem.initialize()
    
    return {
        "status": "running",
        "beans": gem.list_beans(),
        "framework": "PyGem"
    }


if __name__ == "__main__":
    from app.application import create_app
    
    # Create configuration
    config = """
profile: dev
server:
  host: 0.0.0.0
  port: 8080
messaging:
  transport: memory
logging:
  level: INFO
"""
    
    with open('pygem.yml', 'w') as f:
        f.write(config)
    
    try:
        app = create_app(["app.examples"])
        app.add_routes(simple_router)
        
        print("=== PyGem Simple Example ===")
        print("API: http://localhost:8080/docs")
        print("Hello: http://localhost:8080/simple/hello/World")
        print("Status: http://localhost:8080/simple/status")
        print("==========================")
        
        app.run()
    finally:
        if os.path.exists('pygem.yml'):
            os.remove('pygem.yml')