import inspect
from functools import wraps
from typing import Any, Callable, Dict, List,Type
from app.shared.registry import _SINGLETONS
def ApplicationScoped(cls):
    """Mark a class as a singleton-managed bean."""
    @wraps(cls)
    def wrapper(*args, **kwargs):
        if cls not in _SINGLETONS:
            _SINGLETONS[cls] = cls(*args, **kwargs)
        return _SINGLETONS[cls]
    return wrapper

def Inject(cls_or_factory):
    """Inject a class or factory."""
    if inspect.isclass(cls_or_factory):
        if cls_or_factory in _SINGLETONS:
            return _SINGLETONS[cls_or_factory]
        instance = cls_or_factory()
        _SINGLETONS[cls_or_factory] = instance
        return instance
    elif callable(cls_or_factory):
        return cls_or_factory()
    else:
        raise ValueError("Inject expects a class or factory callable")

def RequestScoped(cls: Type):
    """Mark a class to have request-scoped lifecycle."""
    @wraps(cls)
    def wrapper(*args, **kwargs):
        return cls(*args, **kwargs)
    return wrapper
