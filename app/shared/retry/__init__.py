import pkgutil
import importlib

__all__ = []

# Auto-discover all modules in this package
for loader, module_name, is_pkg in pkgutil.walk_packages(__path__):
    module = importlib.import_module(f"{__name__}.{module_name}")
    for attr in dir(module):
        # Export only classes (you can refine filter to match naming, e.g., endswith "Client")
        if not attr.startswith("_"):
            globals()[attr] = getattr(module, attr)
            __all__.append(attr)
