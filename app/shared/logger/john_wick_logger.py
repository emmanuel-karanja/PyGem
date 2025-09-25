# john_wick_logger_structlog.py
import sys
import threading
import queue
import json
import inspect
from typing import Any, Dict, Optional
from logging import StreamHandler, Formatter, getLogger, INFO
from logging.handlers import RotatingFileHandler

import structlog
from structlog.stdlib import LoggerFactory
from structlog.processors import TimeStamper, JSONRenderer
from colorama import init as colorama_init, Fore, Style



colorama_init(autoreset=True)

# ----------------------------
# Queue for interactive log expansion
# ----------------------------
expand_queue = queue.Queue()

def listen_for_expand():
    """Wait for Enter to expand logs interactively."""
    if not sys.stdin or not sys.stdin.isatty():
        return
    while True:
        _ = sys.stdin.readline()
        try:
            record = expand_queue.get_nowait()
            print("\n💡 Expanded log extra:")
            print(json.dumps(record, indent=2))
        except queue.Empty:
            continue

# ----------------------------
# Custom processors
# ----------------------------
def add_module_class(logger, method_name, event_dict):
    """Add caller module and class info dynamically."""
    frame = inspect.currentframe()
    if frame is None:
        return event_dict
    frame = frame.f_back.f_back  # Skip structlog internal frames
    module_name = frame.f_globals.get("__name__", "unknown_module")
    cls = frame.f_locals.get("self", None)
    class_name = cls.__class__.__name__ if cls else "unknown_class"
    event_dict["logger"] = f"[{module_name}][{class_name}]"
    return event_dict

def interactive_queue_processor(logger, method_name, event_dict):
    """Push log extras to the interactive queue if present."""
    extra = event_dict.get("extra")
    if extra:
        expand_queue.put(extra)
    return event_dict

def color_console_renderer(_, __, event_dict):
    """Render colored JSON log for console."""
    level = event_dict.get("level", "INFO")
    color_map = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.MAGENTA
    }
    color = color_map.get(level, Fore.WHITE)
    json_str = json.dumps(event_dict)
    return f"{color}{json_str}{Style.RESET_ALL}"

# ----------------------------
# JohnWickLogger
# ----------------------------
class JohnWickLogger:
    def __init__(
        self,
        name: str,
        log_file: str = "app.log",
        max_bytes: int = 10_000_000,
        backup_count: int = 5,
        level: str = "INFO",
        interactive: bool = False,
        color_console: bool = True,
    ):
        self.name = name
        self.interactive = interactive
        self.color_console = color_console

        # Start interactive thread
        if self.interactive:
            threading.Thread(target=listen_for_expand, daemon=True).start()

        # Standard library root logger for file + console
        root_logger = getLogger(name)
        root_logger.setLevel(level)
        root_logger.propagate = False

        # Rotating file handler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(Formatter("%(message)s"))
        root_logger.addHandler(file_handler)

        # Console handler
        console_handler = StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(Formatter("%(message)s"))
        root_logger.addHandler(console_handler)

        # Configure structlog
        structlog.configure(
            processors=[
                add_module_class,
                interactive_queue_processor if self.interactive else (lambda logger, method_name, event_dict: event_dict),
                structlog.processors.add_log_level,
                TimeStamper(fmt="iso"),
                JSONRenderer() if not color_console else color_console_renderer,
            ],
            context_class=dict,
            logger_factory=LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        self._logger = structlog.get_logger(name).bind(name=name)

    # ----------------------------
    # Logging methods
    # ----------------------------
    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.debug(msg, extra=extra, **kwargs)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.info(msg, extra=extra, **kwargs)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.warning(msg, extra=extra, **kwargs)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.error(msg, extra=extra, **kwargs)

    def exception(self, msg: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        self._logger.exception(msg, extra=extra, **kwargs)
