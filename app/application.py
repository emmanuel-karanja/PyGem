"""
PyGem Application Entrypoint
Quarkus-inspired application bootstrap.
"""

import asyncio
from typing import Optional, List
from fastapi import FastAPI

from app.bootstrap import get_bootstrap
from app.shared.annotations import register_consumers
from app.shared.pygem_simple import PyGem


class PyGemApplication:
    """Main PyGem application class."""
    
    def __init__(self):
        self.bootstrap = get_bootstrap()
        self.app = FastAPI(title="PyGem Application")
        self.gem = PyGem()
        self._configured = False
    
    async def __call__(self, scope, receive, send):
        """Make PyGemApplication ASGI-compatible."""
        return await self.app(scope, receive, send)
    
    def configure(self, packages: Optional[List[str]] = None):
        """Configure application."""
        if self._configured:
            return
        
        # Bootstrap framework
        self.bootstrap.bootstrap(packages)
        
        # Initialize CDI
        self.gem.packages = packages or self.bootstrap.config.packages
        self.gem.initialize()
        
        # Add health endpoint
        @self.app.get("/health")
        async def health_check():
            return {"status": "healthy", "application": "PyGem"}
        
        # Add root endpoint
        @self.app.get("/")
        async def root():
            return {"message": "PyGem Application", "status": "running"}
        
        self._configured = True
        return self
    
    def add_routes(self, *routes):
        """Add FastAPI routes."""
        for route in routes:
            self.app.include_router(route)
        return self
    
    def add_event_handler(self, event_type: str, handler):
        """Add FastAPI event handler."""
        self.app.add_event_handler(event_type, handler)
        return self
    
    async def startup_handler(self):
        """Application startup handler."""
        if not self._configured:
            self.configure()
        
        print("Application startup complete")
        
        # Register event consumers
        await self.gem.register_consumers()
        
        # Print application info
        config = self.bootstrap.config
        print(f"   Server: {config.get_server_url()}")
        print(f"   Beans: {self.gem.list_beans()}")
    
    def run(self, host: Optional[str] = None, port: Optional[int] = None):
        """Run FastAPI application."""
        if not self._configured:
            self.configure()
        
        # Override server config from parameters
        if host:
            self.app.state.host = host
        if port:
            self.app.state.port = port
        
        # Add startup handler
        self.add_event_handler("startup", self.startup_handler)
        
        # Run server
        import uvicorn
        server_config = self.bootstrap.config.server
        uvicorn.run(
            self.app,
            host=host or server_config['host'],
            port=port or server_config['port'],
            log_level=self.bootstrap.config.logging['level'].lower()
        )


# Convenience function for quick application startup
def create_app(packages: Optional[List[str]] = None) -> PyGemApplication:
    """Create and configure a PyGem application."""
    app = PyGemApplication()
    return app.configure(packages)