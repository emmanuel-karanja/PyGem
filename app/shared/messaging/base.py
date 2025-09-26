from typing import Callable, Protocol

class EventBus(Protocol):
    async def publish(self, event_name: str, payload: dict):
        raise NotImplementedError

    async def on(self, event_name: str, callback: Callable):
        raise NotImplementedError
