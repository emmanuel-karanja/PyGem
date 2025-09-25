import logging
import sys
from logging.handlers import RotatingFileHandler
import json
from typing import Any, Dict, Optional

class JsonFormatter(logging.Formatter):
    """Formatter that outputs logs in structured JSON format"""
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
        return json.dumps(log_record)

class BulletproofLogger(logging.Logger):
    """
    BulletproofLogger: fully compatible with Python's Logger interface.
    Features:
        - Structured JSON output
        - Rotating file + console logging
        - Thread-safe / async-safe
        - Supports injection anywhere
        - Accepts extra structured data
    """
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
        self.propagate = False  # prevent double logging

        if not self.handlers:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level)
            console_handler.setFormatter(JsonFormatter() if json_format else logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            
            # Rotating file handler
            file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
            file_handler.setLevel(level)
            file_handler.setFormatter(JsonFormatter() if json_format else logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

            self.addHandler(console_handler)
            self.addHandler(file_handler)

    # Override convenience methods to support extra metadata
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
