import asyncio
import inspect
from typing import Callable, Dict, List, Any

from app.shared.event_bus.base import EventBus
from app.config.logger import get_logger, BulletproofLogger
from app.shared.metrics.metrics_collector import MetricsCollector


class InProcessEventBus(EventBus):
    """
    Lightweight in-memory event bus for local pub/sub communication.
    Suitable for development, testing, and small-scale systems.
    """

    def __init__(self, max_retries: int = 3, logger: BulletproofLogger = None):
        self.subscribers: Dict[str, List[Callable[[Any], Any]]] = {}
        self.max_retries = max_retries
        self.logger: BulletproofLogger = logger or get_logger("InProcessEventBus")
        self.metrics = MetricsCollector(self.logger)

    async def publish(self, event_name: str, payload: dict):
        """
        Publish an event to all subscribers.
        Each subscriber runs in isolation with retries.
        """
        subscribers = self.subscribers.get(event_name, [])
        if not subscribers:
            self.logger.debug("No subscribers for event", extra={"event": event_name})
            return

        self.logger.info("Publishing event", extra={"event": event_name, "payload": payload})

        for callback in subscribers:
            # Fire-and-forget safely
            asyncio.create_task(self._safe_invoke(callback, event_name, payload))

    async def subscribe(self, event_name: str, callback: Callable):
        """
        Subscribe a callback to an event.
        """
        self.subscribers.setdefault(event_name, []).append(callback)
        self.logger.info(
            "Subscriber added",
            extra={"event": event_name, "callback": getattr(callback, "__name__", str(callback))}
        )

    async def _safe_invoke(self, callback: Callable, event_name: str, payload: dict):
        """
        Safely invoke a subscriber with retry logic.
        Supports both async and sync callbacks.
        Updates metrics accordingly.
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(payload)
                else:
                    callback(payload)

                self.metrics.increment("subscriber_success")
                self.logger.debug(
                    "Subscriber executed successfully",
                    extra={"event": event_name, "callback": getattr(callback, "__name__", str(callback))}
                )
                return
            except Exception as exc:
                self.metrics.increment("subscriber_failure")
                self.logger.warning(
                    f"Subscriber failed on attempt {attempt}",
                    extra={
                        "event": event_name,
                        "callback": getattr(callback, "__name__", str(callback)),
                        "error": str(exc),
                    }
                )
                await asyncio.sleep(0.5 * attempt)

        self.logger.error(
            "Subscriber permanently failed after retries",
            extra={
                "event": event_name,
                "callback": getattr(callback, "__name__", str(callback)),
                "payload": payload
            }
        )
        self.metrics.increment("subscriber_failure")
        self.metrics.report()
