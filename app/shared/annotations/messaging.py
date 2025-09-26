import asyncio
from functools import wraps
from typing import Callable, List, Tuple
from app.shared.annotations.core import get_subscribe_registry
from app.shared.messaging.event_bus_factory import EventBusFactory

# Deferred consumer registry
_CONSUMER_REGISTRY: List[Tuple[str, Callable]] = []


def EventBusBinding(func):
    """Inject EventBus into function parameter if missing."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if "event_bus" not in kwargs:
            factory_instance = EventBusFactory()  # or Inject(EventBusFactory)
            kwargs['event_bus'] = factory_instance.create_event_bus()
        return await func(*args, **kwargs)
    return wrapper


def Subscribe(event_name: str):
    """Mark function/method as subscriber (auto-registered at bus creation)."""
    def decorator(func: Callable):
        get_subscribe_registry().setdefault(event_name, []).append(func)
        return func
    return decorator


def Producer(topic: str):
    """Inject EventBus producer to a class and optionally provide publish()."""
    def decorator(cls):
        orig_init = cls.__init__

        @wraps(orig_init)
        def __init__(self, *args, **kwargs):
            if 'event_bus' not in kwargs:
                factory_instance = EventBusFactory()
                kwargs['event_bus'] = factory_instance.create_event_bus()
            self._topic = topic
            orig_init(self, *args, **kwargs)

        cls.__init__ = __init__

        # Provide convenience publish method if not defined
        if not hasattr(cls, "publish"):
            async def publish(self, payload: dict):
                await self.event_bus.publish(self._topic, payload)
            cls.publish = publish

        return cls
    return decorator


def Consumer(topic: str):
    """Marks a class method as a consumer."""
    def decorator(func: Callable):
        cls_name = func.__qualname__.split(".")[0]
        _CONSUMER_REGISTRY.append((topic, cls_name, func.__name__))

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Optional: log invocation
            instance = args[0]  # first arg is 'self'
            if hasattr(instance, "logger"):
                instance.logger.info(f"Subscriber called: {cls_name}.{func.__name__} with args={args[1:]}, kwargs={kwargs}")
            return await func(*args, **kwargs)

        return wrapper
    return decorator

async def register_consumers():
    """Bind all deferred consumers to the EventBus after singletons exist."""
    event_bus = EventBusFactory().create_event_bus()

    for topic, cls_name, method_name in _CONSUMER_REGISTRY:
        # Look up the singleton instance
        from app.shared.annotations.core import _SINGLETONS
        instance = next((obj for cls, obj in _SINGLETONS.items() if cls.__name__ == cls_name), None)
        if instance:
            callback = getattr(instance, method_name)
            await event_bus.subscribe(topic, callback)
            if hasattr(instance, "logger"):
                instance.logger.info(f"Subscribed {cls_name}.{method_name} to {topic}")
