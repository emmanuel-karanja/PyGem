import logging
import sys
from logging.handlers import RotatingFileHandler
import json
from typing import Any, Dict, Optional
from colorama import init as colorama_init, Fore, Style
import threading
import queue
import inspect

colorama_init(autoreset=True)

# ----------------------------
# Queue for interactive log expansion
# ----------------------------
expand_queue = queue.Queue()


def listen_for_expand():
    """Wait for Enter to expand logs interactively."""
    if not sys.stdin or not sys.stdin.isatty():
        return  # Skip non-interactive environments
    while True:
        _ = sys.stdin.readline()
        try:
            record = expand_queue.get_nowait()
            print("\n💡 Expanded log extra:")
            print(json.dumps(record, indent=2))
        except queue.Empty:
            continue


# ----------------------------
# JSON Formatter
# ----------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": f"[{getattr(record, '_module', record.module)}][{getattr(record, '_class', 'unknown_class')}]",
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra") and record.extra:
            log_record["extra"] = record.extra
        return json.dumps(log_record)


# ----------------------------
# Colored Console Formatter
# ----------------------------
class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": Fore.CYAN,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.MAGENTA,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        logger_name = f"[{getattr(record, '_module', record.module)}][{getattr(record, '_class', 'unknown_class')}]"
        msg = f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} [{record.levelname}] {logger_name} {record.getMessage()}"
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        return f"{color}{msg}{Style.RESET_ALL}"


# ----------------------------
# JohnWickLogger
# ----------------------------
class JohnWickLogger(logging.Logger):
    def __init__(
        self,
        name: str,
        log_file: str = "app.log",
        max_bytes: int = 10_000_000,
        backup_count: int = 5,
        level: int = logging.INFO,
        interactive: bool = False,
    ):
        super().__init__(name, level=level)
        self.propagate = False

        if not self.handlers:
            # File handler
            file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
            file_handler.setLevel(level)
            file_handler.setFormatter(JsonFormatter())
            self.addHandler(file_handler)

            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(JsonFormatter())  # JSON in console too
            self.addHandler(console_handler)

        # Interactive expansion
        if interactive:
            threading.Thread(target=listen_for_expand, daemon=True).start()
            self._interactive_enabled = True
        else:
            self._interactive_enabled = False

    # ----------------------------
    # Internal helper to attach module/class safely
    # ----------------------------
    def _log_with_extra(self, level_func, msg: str, extra: Optional[Dict[str, Any]], *args, **kwargs):
        frame = inspect.currentframe().f_back
        module_name = frame.f_globals.get("__name__", "unknown_module")
        class_instance = frame.f_locals.get("self", None)
        class_name = class_instance.__class__.__name__ if class_instance else "unknown_class"

        log_extra = extra.copy() if extra else {}
        log_extra.update({"_module": module_name, "_class": class_name})

        if log_extra and getattr(self, "_interactive_enabled", False):
            expand_queue.put(log_extra)

        kwargs["extra"] = {"extra": log_extra}
        level_func(msg, *args, **kwargs)

    # ----------------------------
    # Override convenience methods
    # ----------------------------
    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        self._log_with_extra(super().debug, msg, extra, *args, **kwargs)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        self._log_with_extra(super().info, msg, extra, *args, **kwargs)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        self._log_with_extra(super().warning, msg, extra, *args, **kwargs)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        self._log_with_extra(super().error, msg, extra, *args, **kwargs)

    def exception(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        self._log_with_extra(super().exception, msg, extra, *args, **kwargs)
