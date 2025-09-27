# app/shared/pygem.py
import logging
from typing import Any, Type, List

from app.shared.registry import (
    _SINGLETONS,
    _REQUEST_SCOPE,
    _CONSUMER_REGISTRY,
    _PRODUCER_REGISTRY,
)
from app.shared.messaging.event_bus_factory import EventBusFactory


class PyGem:
    def __init__(self):
        self.logger = logging.getLogger("PyGem")

    def get(self, cls: Type) -> Any:
        """Retrieve an instance of the given class (singleton or request-scoped)."""
        if cls in _SINGLETONS:
            return _SINGLETONS[cls]

        # Create and store a singleton instance
        instance = cls()
        _SINGLETONS[cls] = instance
        self.logger.debug("Created singleton: %s", cls.__name__)

        # --- Autowire EventBus for producers/consumers ---
        if isinstance(instance, EventBusFactory):
            self.logger.info("Bootstrapping EventBus through PyGem")
            instance.bootstrap()

        return instance

    def list_singletons(self) -> List[str]:
        """Return names of all registered singleton classes."""
        return [cls.__name__ for cls in _SINGLETONS.keys()]

    def list_consumers(self) -> List[str]:
        """Return formatted list of all registered consumers."""
        return [
            f"{(t[1].__name__ if t[1] else 'Unknown')}.{t[2]} -> {t[0]}"
            for t in _CONSUMER_REGISTRY
        ]

    def list_producers(self) -> List[str]:
        """Return names of all registered producer classes."""
        return [cls.__name__ for cls in _PRODUCER_REGISTRY]
