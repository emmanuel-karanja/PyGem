# app/pygem.py
import os
import sys
import pkgutil
import importlib
import inspect
import ast
import traceback
import contextlib
import asyncio
from typing import Any, Type, Iterable, Tuple

from app.registry import (
    _REQUEST_SCOPE,
    _SINGLETONS,
    _CONSUMER_REGISTRY,
    _PRODUCER_REGISTRY,
)
from app.shared.logger.john_wick_logger import JohnWickLogger


class PyGem:
    """
    Dependency / annotation bootstrapper.

    Scans the package source (AST-only pass) for classes decorated with:
      - ApplicationScoped
      - RequestScoped
      - Producer
      - Consumer

    Only modules that contain annotated classes are imported (minimizes import-time side-effects).
    """

    # decorator names we look for in AST
    _ANNOTATION_NAMES = {"ApplicationScoped", "RequestScoped", "Producer", "Consumer"}

    def __init__(self, package: str = "app"):
        self.package = package
        self.logger = JohnWickLogger(name="PyGem")
        self.logger.info("Starting PyGem bootstrap...")
        self.bootstrap()

    # -------------------------
    # Main bootstrap flow
    # -------------------------
    def bootstrap(self):
        self.logger.info("Scanning for annotated classes...")
        self._register_annotated_classes(self.package)
        self.logger.info("Annotated classes registered successfully.")

        # initialize event bus factory (lazily to avoid circular imports)
        try:
            event_bus_factory = self.get_event_bus_factory()
            self.logger.info("Bootstrapping EventBusFactory...")
            res = event_bus_factory.bootstrap()
            # if bootstrap returned an awaitable, run or schedule it depending on current loop
            if inspect.isawaitable(res):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # no running loop — safe to run
                    asyncio.run(res)
                else:
                    # running loop — schedule it
                    asyncio.create_task(res)
            self.logger.info("EventBusFactory bootstrapped.")
        except Exception as e:
            self.logger.warning(f"EventBusFactory bootstrap skipped/failed: {e}")
            self.logger.debug(traceback.format_exc())

    # -------------------------
    # AST-based scanner (no eager imports)
    # -------------------------
    def _scan_for_annotated_classes(self, package_name: str) -> Iterable[Tuple[str, str, str]]:
        """
        Walk files under the package and yield (module_name, class_name, decorator_name)
        for top-level classes that have one of the annotation decorators.

        This uses AST parsing only (doesn't execute module code) to find candidate annotated classes.
        """
        try:
            pkg = importlib.import_module(package_name)
        except Exception as e:
            self.logger.warning(f"Could not import package '{package_name}' for path discovery: {e}")
            return

        if not hasattr(pkg, "__path__"):
            self.logger.debug(f"Package '{package_name}' is a single module; skipping tree scan.")
            return

        base_paths = list(pkg.__path__)
        for base_path in base_paths:
            for dirpath, dirnames, filenames in os.walk(base_path):
                # skip hidden/dunder directories like __pycache__
                dirnames[:] = [d for d in dirnames if not (d.startswith("_") or d == "__pycache__")]

                for fname in filenames:
                    if not fname.endswith(".py"):
                        continue
                    if fname.startswith("_"):  # skip private/dunder files here
                        continue

                    filepath = os.path.join(dirpath, fname)
                    rel = os.path.relpath(filepath, base_path)
                    mod_rel = rel[:-3].replace(os.path.sep, ".")  # strip .py
                    module_name = f"{package_name}.{mod_rel}" if mod_rel != "__init__" else package_name

                    self.logger.debug(f"AST scanning file: {filepath} -> candidate module: {module_name}")

                    try:
                        with open(filepath, "r", encoding="utf-8") as fh:
                            source = fh.read()
                        tree = ast.parse(source, filename=filepath)
                    except Exception as e:
                        self.logger.warning(f"Failed to parse {filepath}: {e}")
                        self.logger.debug(traceback.format_exc())
                        continue

                    # examine top-level class definitions
                    for node in tree.body:
                        if not isinstance(node, ast.ClassDef):
                            continue
                        class_name = node.name
                        # inspect decorators on the class node
                        for deco in node.decorator_list:
                            deco_name = self._get_decorator_base_name(deco)
                            if deco_name in self._ANNOTATION_NAMES:
                                self.logger.debug(f"AST found annotated class: {module_name}.{class_name} @{deco_name}")
                                yield module_name, class_name, deco_name
                                break  # class may have multiple decorations; emit once per class

    def _get_decorator_base_name(self, deco_node: ast.AST) -> str:
        """
        Extract the base name of a decorator AST node.
        Examples handled:
          - @ApplicationScoped  -> "ApplicationScoped"
          - @annotations.core.ApplicationScoped -> "ApplicationScoped"
          - @Producer(topic="x") -> "Producer"
        """
        # decorator is a call: @Something(...)
        if isinstance(deco_node, ast.Call):
            return self._get_decorator_base_name(deco_node.func)

        # decorator is a simple name: @Name
        if isinstance(deco_node, ast.Name):
            return deco_node.id

        # decorator is attribute: @pkg.Some
        if isinstance(deco_node, ast.Attribute):
            return deco_node.attr

        # fallback
        return getattr(deco_node, "id", "") or getattr(deco_node, "attr", "")

    # -------------------------
    # Registration using targeted imports
    # -------------------------

    def _register_annotated_classes(self, package: str) -> None:
        """Scan a package for annotated classes and register them."""
        base_path = package.replace(".", os.sep)
        self.logger.info(f"Scanning for annotated classes under: {package}")

        for finder, name, ispkg in pkgutil.walk_packages([base_path], prefix=f"{package}."):
            try:
                module = importlib.import_module(name)
            except Exception as e:
                self.logger.warning(f"Could not import module {name}: {e}")
                continue

            # Parse the file with AST to find declared classes
            module_file = getattr(module, "__file__", None)
            if not module_file or not os.path.exists(module_file):
                continue

            with open(module_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=module_file)

            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_name = node.name
                    cls = getattr(module, class_name, None)

                    if cls is None:
                        self.logger.warning(
                            f"Annotated class {class_name} not found as class object in {name}"
                        )
                        continue

                    # Register based on annotation
                    if getattr(cls, "__application_scoped__", False):
                        self.get(cls)  # ensure singleton created
                        self.logger.debug(f"Registered ApplicationScoped: {cls.__name__}")

                    elif getattr(cls, "__request_scoped__", False):
                        self._request_scoped.add(cls)
                        self.logger.debug(f"Registered RequestScoped: {cls.__name__}")

                    # Consumers
                    for topic, method in getattr(cls, "__consumers__", []):
                        if cls is None:
                            self.logger.warning(
                                f"Skipping consumer {method} on {topic} — no class resolved"
                            )
                            continue
                        self._consumer_registry.add((topic, cls, method))
                        self.logger.debug(f"Registered Consumer: {cls.__name__}.{method} -> {topic}")

                    # Producers
                    for topic, method in getattr(cls, "__producers__", []):
                        if cls is None:
                            self.logger.warning(
                                f"Skipping producer {method} on {topic} — no class resolved"
                            )
                            continue
                        self._producer_registry.add((topic, cls, method))
                        self.logger.debug(f"Registered Producer: {cls.__name__}.{method} -> {topic}")

    # -------------------------
    # Instantiation helpers
    # -------------------------
    def _instantiate_with_injection(self, cls: Type, Inject) -> Any:
        """
        Create an instance of `cls`, resolving constructor args via Inject when annotated.
        - Skip typing hints and primitives (Inject should handle that).
        """
        try:
            sig = inspect.signature(cls.__init__)
        except (TypeError, ValueError):
            # Builtins or callables without signature
            return cls()

        kwargs = {}
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            if param.annotation != inspect.Parameter.empty:
                try:
                    val = Inject(param.annotation)
                except Exception:
                    val = None
                if val is not None:
                    kwargs[name] = val
                elif param.default != inspect.Parameter.empty:
                    kwargs[name] = param.default
            elif param.default != inspect.Parameter.empty:
                kwargs[name] = param.default

        return cls(**kwargs)

    # -------------------------
    # Public get() lifecycle API
    # -------------------------
    def get(self, cls: Type) -> Any:
        """
        Retrieve or create managed instance (ApplicationScoped, RequestScoped, Producer, Consumer).
        - ApplicationScoped: created once and stored in _SINGLETONS
        - RequestScoped: per-request stored in _REQUEST_SCOPE (cleared by request_scope())
        - Producer: treated as singleton and registered
        - Consumer: treated as singleton and its methods registered
        """
        # ApplicationScoped
        if getattr(cls, "_is_application_scoped", False):
            if cls in _SINGLETONS and _SINGLETONS[cls] is not None:
                return _SINGLETONS[cls]
            instance = self._instantiate_with_injection(cls, importlib.import_module("app.shared.annotations.core").Inject)
            _SINGLETONS[cls] = instance
            self.logger.debug(f"Created ApplicationScoped singleton: {cls.__name__}")
            return instance

        # RequestScoped (per-request) — create if not present in current request scope
        if getattr(cls, "_is_request_scoped", False):
            if cls not in _REQUEST_SCOPE or _REQUEST_SCOPE[cls] is None:
                instance = self._instantiate_with_injection(cls, importlib.import_module("app.shared.annotations.core").Inject)
                _REQUEST_SCOPE[cls] = instance
                self.logger.debug(f"Created RequestScoped instance: {cls.__name__}")
            return _REQUEST_SCOPE[cls]

        # Producer
        if getattr(cls, "_is_producer", False):
            if cls not in _SINGLETONS:
                instance = self._instantiate_with_injection(cls, importlib.import_module("app.shared.annotations.core").Inject)
                _SINGLETONS[cls] = instance
                _PRODUCER_REGISTRY.add(cls)
                self.logger.debug(f"Created Producer and registered: {cls.__name__}")
            return _SINGLETONS[cls]

        # Consumer (method-level) — create singleton and register consumer methods if not present
        if any(getattr(m, "_is_consumer_method", False) or getattr(getattr(m, "__wrapped__", m), "_is_consumer_method", False)
               for _, m in inspect.getmembers(cls, inspect.isfunction)):
            if cls not in _SINGLETONS:
                instance = self._instantiate_with_injection(cls, importlib.import_module("app.shared.annotations.core").Inject)
                _SINGLETONS[cls] = instance
                # register consumer methods
                for name, method in inspect.getmembers(cls, inspect.isfunction):
                    target = getattr(method, "__wrapped__", method)
                    if getattr(target, "_is_consumer_method", False):
                        topic = getattr(target, "_topic", None)
                        if topic:
                            _CONSUMER_REGISTRY.add((topic, cls, name))
                            self.logger.debug(f"Registered consumer method at get(): {cls.__name__}.{name} -> {topic}")
            return _SINGLETONS[cls]

        # fallback: treat as singleton
        if cls in _SINGLETONS and _SINGLETONS[cls] is not None:
            return _SINGLETONS[cls]

        instance = self._instantiate_with_injection(cls, importlib.import_module("app.shared.annotations.core").Inject)
        _SINGLETONS[cls] = instance
        self.logger.debug(f"Created plain singleton: {cls.__name__}")
        return instance

    # -------------------------
    # Helpers
    # -------------------------
    def get_event_bus_factory(self):
        """Lazy getter for EventBusFactory"""
        mod = importlib.import_module("app.shared.messaging.event_bus_factory")
        EventBusFactory = getattr(mod, "EventBusFactory")
        return self.get(EventBusFactory)

    @contextlib.contextmanager
    def request_scope(self):
        """Context manager to create a request scope and clear it on exit."""
        try:
            yield
        finally:
            _REQUEST_SCOPE.clear()
            self.logger.debug("Cleared RequestScope instances")

    # -------------------------
    # Introspection utilities
    # -------------------------
    def list_singletons(self) -> list[str]:
        return [cls.__name__ for cls, inst in _SINGLETONS.items() if inst is not None]

    def list_consumers(self) -> list[str]:
        return [f"{cls.__name__}.{method} -> {topic}" for topic, cls, method in _CONSUMER_REGISTRY]

    def list_producers(self) -> list[str]:
        return [cls.__name__ for cls in _PRODUCER_REGISTRY]
