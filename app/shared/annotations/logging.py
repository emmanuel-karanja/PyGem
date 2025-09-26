from functools import wraps
import inspect
from app.shared.logger import JohnWickLogger

def LoggerBinding(name: str = None):
    """Inject JohnWickLogger into classes or functions."""
    def decorator(obj):
        if isinstance(obj, type):
            orig_init = obj.__init__
            sig = inspect.signature(orig_init)
            accepts_logger = "logger" in sig.parameters

            @wraps(orig_init)
            def __init__(self, *args, **kwargs):
                if accepts_logger and "logger" not in kwargs:
                    kwargs["logger"] = JohnWickLogger(name or obj.__name__)
                orig_init(self, *args, **kwargs)

            obj.__init__ = __init__
            return obj
        elif callable(obj):
            @wraps(obj)
            def wrapper(*args, **kwargs):
                kwargs.setdefault("logger", JohnWickLogger(name or obj.__name__))
                return obj(*args, **kwargs)
            return wrapper
        return obj
    return decorator
