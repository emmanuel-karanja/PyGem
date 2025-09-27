import asyncio
from functools import wraps
from typing import Callable, Tuple, Type, Optional, Set

from app.shared.messaging.event_bus_factory import EventBusFactory
from app.shared.annotations.core import _SINGLETONS
from app.shared.registry import _PRODUCER_REGISTRY,_SINGLETONS,_CONSUMER_REGISTRY


# -------------------
# EventBus Injection
# -------------------
def EventBusBinding(func: Callable):
    """Inject EventBus into a function if missing."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if "event_bus" not in kwargs:
            kwargs["event_bus"] = EventBusFactory().create_event_bus()
        return await func(*args, **kwargs)
    return wrapper


# -------------------
# Producer Decorator
# -------------------
def Producer(topic: str):
    """Class decorator to inject EventBus and provide automatic `publish()` method."""
    def decorator(cls):
        orig_init = cls.__init__

        @wraps(orig_init)
        def __init__(self, *args, **kwargs):
            if "event_bus" not in kwargs:
                kwargs["event_bus"] = EventBusFactory().create_event_bus()
            self._topic = topic
            orig_init(self, *args, **kwargs)

        cls.__init__ = __init__

        if not hasattr(cls, "publish"):
            async def publish(self, payload: dict):
                await self.event_bus.publish(self._topic, payload)
            cls.publish = publish

        return cls
    return decorator


# -------------------
# Consumer Decorator
# -------------------
def Consumer(topic: str):
    """Marks a class method as a consumer to a topic."""
    def decorator(func: Callable):
        cls_type: Optional[Type] = None
        qualname = func.__qualname__
        if "." in qualname:
            cls_name = qualname.split(".")[0]
            # Lazy resolution: store cls_type as None and resolve later
            for cls in _SINGLETONS.keys():
                if cls.__name__ == cls_name:
                    cls_type = cls
                    break

        # Prevent duplicates
        _CONSUMER_REGISTRY.add((topic, cls_type, func.__name__))

        @wraps(func)
        async def wrapper(*args, **kwargs):
            instance = args[0]  # self
            if hasattr(instance, "logger"):
                instance.logger.info(
                    f"Subscriber called: {func.__qualname__} args={args[1:]}, kwargs={kwargs}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# -------------------
# Consumer Registration
# -------------------
async def register_consumers():
    """Bind all deferred consumers to the EventBus safely."""
    event_bus = EventBusFactory().create_event_bus()

    for topic, cls_type, method_name in list(_CONSUMER_REGISTRY):
        # Lazy resolve class if None
        if cls_type is None:
            for cls, instance in _SINGLETONS.items():
                if method_name in dir(instance):
                    cls_type = cls
                    break

        if cls_type is None:
            continue

        instance = _SINGLETONS.get(cls_type)
        if instance is None:
            continue

        callback = getattr(instance, method_name)

        # Optional: wrap callback for metrics / retry here
        await event_bus.subscribe(topic, callback)

        if hasattr(instance, "logger"):
            instance.logger.info(
                f"Subscribed {cls_type.__name__}.{method_name} to topic '{topic}'"
            )


# -------------------
# Synchronous wrapper
# -------------------
def subscribe_all_sync():
    """Schedule consumer registration on the event loop."""
    asyncio.create_task(register_consumers())
