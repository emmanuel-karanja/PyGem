"""
Lean CDI Container - Quarkus-inspired dependency injection.
Clean, simple, and focused.
"""

import asyncio
import inspect
import threading
from typing import Any, Dict, Type, Optional, Callable
from pathlib import Path
import importlib


class BeanRegistry:
    """Thread-safe bean registry."""
    
    def __init__(self):
        self._singletons: Dict[Type, Any] = {}
        self._instances: Dict[str, Any] = {}
        self._lock = threading.RLock()
    
    def get_singleton(self, cls: Type) -> Any:
        """Get or create singleton instance."""
        with self._lock:
            if cls not in self._singletons:
                instance = cls()
                self._singletons[cls] = instance
            return self._singletons[cls]
    
    def get_instance(self, name: str) -> Optional[Any]:
        """Get instance by name."""
        with self._lock:
            return self._instances.get(name)
    
    def register_instance(self, name: str, instance: Any) -> None:
        """Register named instance."""
        with self._lock:
            self._instances[name] = instance


class BeanScanner:
    """Scans for CDI beans."""
    
    @staticmethod
    def scan_packages(packages: list) -> Dict[str, Type]:
        """Scan packages for beans."""
        beans = {}
        
        for package in packages:
            try:
                module = importlib.import_module(package)
                
                # Handle packages without __file__ (namespace packages)
                if not hasattr(module, '__file__') or module.__file__ is None:
                    beans.update(BeanScanner._scan_module(module))
                    continue
                
                package_dir = Path(module.__file__).parent
                
                for py_file in package_dir.glob("*.py"):
                    if py_file.name.startswith("__"):
                        continue
                    
                    module_name = f"{package}.{py_file.stem}"
                    try:
                        module = importlib.import_module(module_name)
                        beans.update(BeanScanner._scan_module(module))
                    except ImportError:
                        continue
                        
            except ImportError:
                continue
        
        return beans
    
    @staticmethod
    def _scan_module(module) -> Dict[str, Type]:
        """Scan module for bean classes."""
        beans = {}
        
        for name, obj in inspect.getmembers(module):
            if (inspect.isclass(obj) and 
                hasattr(obj, '__module__') and 
                obj.__module__ == module.__name__ and
                not name.startswith('_')):
                
                # Check for CDI annotations
                if hasattr(obj, '_cdi_bean'):
                    beans[name.lower()] = obj
        
        return beans


class CDIContainer:
    """Lean CDI container."""
    
    def __init__(self):
        self._registry = BeanRegistry()
        self._beans: Dict[str, Type] = {}
        self._consumers: list = []
        self._producers: list = []
        self._initialized = False
    
    def initialize(self, packages: list) -> None:
        """Initialize container by scanning packages."""
        if self._initialized:
            return
        
        # Scan for beans
        self._beans = BeanScanner.scan_packages(packages)
        
        # Register instances for named beans
        for name, bean_class in self._beans.items():
            instance = self._registry.get_singleton(bean_class)
            self._registry.register_instance(name, instance)
        
        # Collect producers and consumers
        self._collect_messaging_beans()
        
        self._initialized = True
    
    def _collect_messaging_beans(self):
        """Collect producers and consumers from beans."""
        for bean_class in self._beans.values():
            instance = self._registry.get_singleton(bean_class)
            
            # Check for producers
            if hasattr(bean_class, '_producer_topic'):
                self._producers.append(instance)
            
            # Check for consumers
            for attr_name in dir(instance):
                attr = getattr(instance, attr_name)
                if hasattr(attr, '_consumer_topic'):
                    self._consumers.append({
                        'instance': instance,
                        'method': attr,
                        'topic': attr._consumer_topic
                    })
    
    def get(self, cls: Type) -> Any:
        """Get bean instance by class."""
        if not self._initialized:
            raise RuntimeError("CDI container not initialized")
        
        return self._registry.get_singleton(cls)
    
    def get_by_name(self, name: str) -> Any:
        """Get bean instance by name."""
        if not self._initialized:
            raise RuntimeError("CDI container not initialized")
        
        return self._registry.get_instance(name)
    
    async def register_consumers(self, event_bus):
        """Register all consumers with event bus."""
        for consumer_info in self._consumers:
            await event_bus.subscribe(
                consumer_info['topic'], 
                consumer_info['method']
            )
    
    def list_beans(self) -> list[str]:
        """List all discovered beans."""
        return list(self._beans.keys())


# Global container
_container: Optional[CDIContainer] = None


def get_container() -> CDIContainer:
    """Get global CDI container."""
    global _container
    if _container is None:
        _container = CDIContainer()
    return _container


def initialize_cdi(packages: list) -> CDIContainer:
    """Initialize CDI container."""
    container = get_container()
    container.initialize(packages)
    return container