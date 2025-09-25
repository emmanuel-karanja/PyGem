import threading
from logging import Logger
from typing import Dict

class MetricsCollector:
    """
    Simple metrics collector to track counters across components.
    Supports thread-safe increments and structured logging via injected logger.
    """
    def __init__(self, logger: Logger):
        self.logger = logger
        self._counters: Dict[str, int] = {}
        self._lock = threading.Lock()  # thread-safe increments

    def increment(self, key: str, amount: int = 1):
        """Increment a metric counter"""
        with self._lock:
            self._counters[key] = self._counters.get(key, 0) + amount

    def decrement(self, key: str, amount: int = 1):
        """Decrement a metric counter"""
        with self._lock:
            self._counters[key] = max(0, self._counters.get(key, 0) - amount)

    def reset(self, key: str):
        """Reset a specific metric"""
        with self._lock:
            self._counters[key] = 0

    def report(self):
        """Emit structured log of current metrics"""
        with self._lock:
            if self._counters:
                self.logger.info("Metrics update", extra=self._counters.copy())

    def get(self, key: str) -> int:
        """Get the current value of a metric"""
        with self._lock:
            return self._counters.get(key, 0)
