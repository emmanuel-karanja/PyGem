import logging
import sys
from logging.handlers import RotatingFileHandler
import json
from typing import Any, Dict, Optional
from colorama import init as colorama_init, Fore, Style
import threading
import queue

colorama_init(autoreset=True)

# ----------------------------
# Queue for interactive log expansion
# ----------------------------
expand_queue = queue.Queue()

def listen_for_expand():
    if not sys.stdin or not sys.stdin.isatty():
        # Skip in non-interactive environments (pytest, Docker, etc.)
        return
    while True:
        _ = sys.stdin.readline()  # Wait for Enter
        try:
            record = expand_queue.get_nowait()
            print("\n💡 Expanded log extra:")
            print(json.dumps(record, indent=2))
        except queue.Empty:
            continue

threading.Thread(target=listen_for_expand, daemon=True).start()

# ----------------------------
# JSON Formatter
# ----------------------------
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra") and record.extra:
            log_record["extra"] = record.extra
            # Push extra to interactive queue
            expand_queue.put(record.extra)
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
        "CRITICAL": Fore.MAGENTA
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        msg = f"{self.formatTime(record, '%Y-%m-%d %H:%M:%S')} - {record.name} - {record.levelname} - {record.getMessage()}"
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
        json_format: bool = True
    ):
        super().__init__(name, level=level)
        self.propagate = False

        if not self.handlers:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(
                ColoredFormatter() if not json_format else JsonFormatter()
            )

            # Rotating file handler
            file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
            file_handler.setLevel(level)
            file_handler.setFormatter(JsonFormatter())

            self.addHandler(console_handler)
            self.addHandler(file_handler)

    # Convenience methods supporting extra metadata
    def debug(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        super().debug(msg, extra={"extra": extra} if extra else None, *args, **kwargs)

    def info(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        super().info(msg, extra={"extra": extra} if extra else None, *args, **kwargs)

    def warning(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        super().warning(msg, extra={"extra": extra} if extra else None, *args, **kwargs)

    def error(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        super().error(msg, extra={"extra": extra} if extra else None, *args, **kwargs)

    def exception(self, msg: str, extra: Optional[Dict[str, Any]] = None, *args, **kwargs):
        super().exception(msg, extra={"extra": extra} if extra else None, *args, **kwargs)
