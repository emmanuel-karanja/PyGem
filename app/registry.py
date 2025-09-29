from typing import Any, Dict, Set, Tuple, Type

# Global DI state (shared by PyGem and annotations)
_SINGLETONS:Dict[type, Any] = {}
_PRODUCER_REGISTRY=set()
_REQUEST_SCOPE:Dict[Type, Any] = {}
_CONSUMER_REGISTRY: Set[Tuple[str, Type, str]] = set()