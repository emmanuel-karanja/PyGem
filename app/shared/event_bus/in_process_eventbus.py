# my_event_system/event_bus/inprocess.py
from typing import Callable, Dict, List
from .base import EventBus

class InProcessEventBus(EventBus):
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = {}

    async def publish(self, event_name: str, payload: dict):
        for callback in self.subscribers.get(event_name, []):
            await callback(payload)

    async def subscribe(self, event_name: str, callback: Callable):
        self.subscribers.setdefault(event_name, []).append(callback)
