from typing import Callable

class EventBus:
    async def publish(self, event_name: str, payload: dict):
        raise NotImplementedError

    async def subscribe(self, event_name: str, callback: Callable):
        raise NotImplementedError
