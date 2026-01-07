"""
Simple PyGem framework with lean CDI.
"""

from typing import Any, List, Type, Optional
from app.shared.cdi import get_container, initialize_cdi
from app.shared.annotations import register_consumers
from app.shared.logger.john_wick_logger import create_logger


class PyGem:
    """Simple PyGem framework."""
    
    def __init__(self, packages: Optional[List[str]] = None):
        self.logger = create_logger("PyGem")
        self.packages = packages or self._default_packages()
        self._initialized = False
    
    def _default_packages(self) -> List[str]:
        """Default packages to scan."""
        return [
            "app.orders",
            "app.notifications", 
            "app.shared"
        ]
    
    def initialize(self) -> None:
        """Initialize PyGem with CDI."""
        if self._initialized:
            return
        
        self.logger.info(f"Initializing PyGem with packages: {self.packages}")
        
        # Initialize CDI container
        container = initialize_cdi(self.packages)
        
        self.logger.info(f"Discovered {len(container._beans)} beans")
        self._initialized = True
    
    def get(self, cls: Type) -> Any:
        """Get bean instance."""
        if not self._initialized:
            self.initialize()
        
        return get_container().get(cls)
    
    async def register_consumers(self):
        """Register event consumers."""
        await register_consumers()
    
    def list_beans(self) -> List[str]:
        """List discovered beans."""
        if not self._initialized:
            return []
        
        container = get_container()
        return list(container._beans.keys())