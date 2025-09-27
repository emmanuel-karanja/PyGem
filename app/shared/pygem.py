# app/shared/pygem.py
import logging
from typing import Any, Type, List
from app.shared.registry import _SINGLETONS, _CONSUMER_REGISTRY, _PRODUCER_REGISTRY

from app.shared.messaging.event_bus_factory import EventBusFactory  # <-- proper class


class PyGem:
    def __init__(self):
        self.logger = logging.getLogger("PyGem")

    def get(self, cls: Type) -> Any:
        """Retrieve or create a singleton instance. Special-case EventBusFactory for autowiring."""
        if cls in _SINGLETONS:
            return _SINGLETONS[cls]

        # --- Create instance ---
        instance = cls()
        _SINGLETONS[cls] = instance
        self.logger.debug("Created singleton: %s", cls.__name__)

        # --- Autowire EventBusFactory ---
        if cls is EventBusFactory:
            self.logger.info("Initializing EventBusFactory...")
            instance.bootstrap()  # ensure event bus + consumers/producers bound
            self.logger.info("EventBusFactory initialized and bootstrapped")

        return instance

    def list_singletons(self) -> List[str]:
        return [cls.__name__ for cls in _SINGLETONS.keys()]

    def list_consumers(self) -> List[str]:
        return [
            f"{(t[1].__name__ if t[1] else 'Unknown')}.{t[2]} -> {t[0]}"
            for t in _CONSUMER_REGISTRY
        ]

    def list_producers(self) -> List[str]:
        return [cls.__name__ for cls in _PRODUCER_REGISTRY]
