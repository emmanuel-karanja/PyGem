"""
Lean CDI Annotations.
Simple and focused dependency injection.
"""

import inspect
from functools import wraps
from typing import Any, Callable


def ApplicationScoped(cls):
    """Mark class as application-scoped singleton."""
    cls._cdi_bean = True
    return cls


def RequestScoped(cls):
    """Mark class as request-scoped (treated as singleton for simplicity)."""
    cls._cdi_bean = True
    return cls


def LoggerBinding(name: str = None):
    """Inject logger into class with improved caching."""
    def decorator(cls):
        orig_init = cls.__init__
        
        @wraps(orig_init)
        def __init__(self, *args, **kwargs):
            if "logger" not in kwargs:
                from app.shared.logger.john_wick_logger import create_logger
                kwargs["logger"] = create_logger(name or cls.__name__)
            orig_init(self, *args, **kwargs)
        
        cls.__init__ = __init__
        return cls
    return decorator


def Inject(cls):
    """Get bean instance."""
    from app.shared.cdi import get_container
    return get_container().get(cls)


def Producer(topic: str):
    """Mark class as event producer."""
    def decorator(cls):
        cls._producer_topic = topic
        
        orig_init = cls.__init__
        
        @wraps(orig_init)
        def __init__(self, *args, **kwargs):
            if "event_bus" not in kwargs:
                # Direct instantiation to avoid circular dependency
                from app.shared.messaging.event_bus_factory import EventBusFactory
                factory = EventBusFactory()
                kwargs["event_bus"] = factory.create_event_bus()
            
            orig_init(self, *args, **kwargs)
        
        cls.__init__ = __init__
        
        if not hasattr(cls, 'publish'):
            def publish(self, payload: dict):
                return self.event_bus.publish(topic, payload)
            cls.publish = publish
        
        return cls
    return decorator


def Consumer(topic: str):
    """Mark method as event consumer."""
    def decorator(func):
        func._consumer_topic = topic
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Auto-inject logger if needed
            sig = inspect.signature(func)
            if "logger" in sig.parameters and "logger" not in kwargs:
                from app.shared.logger.john_wick_logger import create_logger
                kwargs["logger"] = create_logger(f"consumer.{func.__name__}")
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def Subscribe(event_name: str):
    """Alias for Consumer."""
    return Consumer(event_name)


# Consumer registration
async def register_consumers():
    """Register all consumers with EventBus."""
    from app.shared.cdi import get_container
    
    container = get_container()
    if not container._initialized:
        return
    
    # Get EventBus
    from app.shared.messaging.event_bus_factory import EventBusFactory
    factory = container.get(EventBusFactory)
    event_bus = factory.create_event_bus()
    
    # Register consumers
    await container.register_consumers(event_bus)