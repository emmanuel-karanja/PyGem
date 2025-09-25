# john_wick_logger_loguru.py
import sys
import threading
import queue
import json
import inspect
from typing import Any, Dict, Optional
from datetime import datetime
from loguru import logger
from colorama import init as colorama_init, Fore, Style
import asyncio

# Initialize colorama
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
            print("\nExpanded log extra:")
            print(json.dumps(record, indent=2, ensure_ascii=False))
        except queue.Empty:
            continue


# ----------------------------
# Helper: get caller module/class
# ----------------------------
def get_caller_info():
    """Get first non-logger caller module and class."""
    frame = inspect.currentframe()
    if not frame:
        return "unknown_module", "unknown_class"

    while frame:
        module_name = frame.f_globals.get("__name__", "")
        cls = frame.f_locals.get("self", None)
        if module_name != __name__:
            class_name = cls.__class__.__name__ if cls else "module-level"
            return module_name, class_name
        frame = frame.f_back

    return "unknown_module", "unknown_class"


# ----------------------------
# Console formatter
# ----------------------------
def console_formatter(record):
    timestamp = record["time"].isoformat()
    level = record["level"].name.ljust(9)  # fixed width for level
    msg = record["message"]

    color = {
        "DEBUG": Fore.BLUE,
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
        "CRITICAL": Fore.MAGENTA,
        "EXCEPTION": Fore.RED,
    }.get(record["level"].name, "")

    module = record["extra"].get("module", "unknown_module")
    cls = record["extra"].get("class", "unknown_class")
    extra_data = record["extra"].get("extra_data", {})

    # Fix width for module/class
    module_cls = f"[{module}][{cls}]".ljust(45)

    extra_json = f"\nExtra: {json.dumps(extra_data, indent=2, ensure_ascii=False)}" if extra_data else ""

    return f"{color}{timestamp} | {level} | {module_cls} {msg}{extra_json}{Style.RESET_ALL}\n"


# ----------------------------
# JohnWickLogger
# ----------------------------
class JohnWickLogger:
    def __init__(
        self,
        name: str,
        log_file: str = "app.log",
        level: str = "INFO",
        interactive: bool = False,
    ):
        self.name = name
        self.interactive = interactive

        if self.interactive:
            threading.Thread(target=listen_for_expand, daemon=True).start()

        # Remove default Loguru logger
        logger.remove()

        # File logger (JSON structured)
        logger.add(
            log_file,
            rotation="10 MB",
            retention=5,
            level=level,
            serialize=True,
            enqueue=True,  # thread-safe / async-safe
        )

        # Console logger (colored, human-readable)
        logger.add(
            sys.stdout,
            format=console_formatter,
            level=level,
            enqueue=True,  # thread-safe / async-safe
        )

    # ----------------------------
    # Logging methods
    # ----------------------------
    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        self._log("DEBUG", msg, extra)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        self._log("INFO", msg, extra)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        self._log("WARNING", msg, extra)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        self._log("ERROR", msg, extra)

    def exception(self, msg: str, extra: Optional[Dict[str, Any]] = None):
        self._log("EXCEPTION", msg, extra)

    # ----------------------------
    # Async helper
    # ----------------------------
    async def log_async(self, level: str, msg: str, extra: Optional[Dict[str, Any]] = None):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._log, level, msg, extra)

    # ----------------------------
    # Internal log helper
    # ----------------------------
    def _log(self, level: str, msg: str, extra: Optional[Dict[str, Any]]):
        module, cls = get_caller_info()
        log_extra = {
            "module": module,
            "class": cls,
            "extra_data": extra or {}
        }

        # Push extra to interactive queue
        if self.interactive and extra:
            expand_queue.put(extra)

        logger.log(level, msg, extra=log_extra)
