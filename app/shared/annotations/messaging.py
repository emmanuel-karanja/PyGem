import asyncio
from functools import wraps
from typing import Callable
from app.shared.annotations.core import get_subscribe_registry
from app.shared.messaging.event_bus_factory import EventBusFactory

def EventBusBinding(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if "event_bus" not in kwargs:
            factory_instance = EventBusFactory()  # or Inject(EventBusFactory)
            kwargs['event_bus'] = factory_instance.create_event_bus()
        return await func(*args, **kwargs)
    return wrapper

def Subscribe(event_name: str):
    """Mark function/method as subscriber."""
    def decorator(func: Callable):
        get_subscribe_registry().setdefault(event_name, []).append(func)
        return func
    return decorator

def Producer(topic: str):
    """Inject EventBus producer to class."""
    def decorator(cls):
        orig_init = cls.__init__
        @wraps(orig_init)
        def __init__(self, *args, **kwargs):
            if 'event_bus' not in kwargs:
               factory_instance = EventBusFactory()  # or Inject(EventBusFactory)
               kwargs['event_bus'] = factory_instance.create_event_bus()
            self._topic = topic
            orig_init(self, *args, **kwargs)
        cls.__init__ = __init__

        if not hasattr(cls, "publish"):
            async def publish(self, payload: dict):
                await self.event_bus.publish(self._topic, payload)
            cls.publish = publish

        return cls
    return decorator

def Consumer(topic: str):
    """Subscribe async function to EventBus topic."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        factory_instance = EventBusFactory() 
        bus = factory_instance.create_event_bus()
        asyncio.create_task(bus.on(topic, wrapper))
        return wrapper
    return decorator
