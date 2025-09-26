# john_wick_logger_uvicorn_color.py
import asyncio
import logging
from typing import Optional, Dict
import structlog

class JohnWickLogger:
    _logger_cache: Dict[str, "JohnWickLogger"] = {}

    # Simple ANSI colors
    LEVEL_COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[1;31m" # bold red
    }
    RESET_COLOR = "\033[0m"

    def __init__(self, name: str = "default", log_file: str = "app.log", level: str = "INFO", context: Optional[dict] = None):
        self.name = name
        self.context = context or {}

        if name in self._logger_cache:
            cached = self._logger_cache[name]
            self.console_logger = cached.console_logger
            self.file_logger = cached.file_logger
            return

        # ----------------------------
        # Console logger (colored)
        # ----------------------------
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

        # File logger
        file_handler = logging.FileHandler(log_file, encoding="utf-8")

        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            handlers=[console_handler, file_handler],
            format="%(message)s",
        )

        # ----------------------------
        # Structlog processors for JSON file
        # ----------------------------
        file_processors = [
            structlog.processors.TimeStamper(fmt="ISO"),       # adds timestamp
            structlog.stdlib.add_log_level,                    # adds level
            structlog.stdlib.add_logger_name,                 # adds logger name
            structlog.stdlib.PositionalArgumentsFormatter(),  # formats args
            structlog.processors.StackInfoRenderer(),         # adds stack info if stack=True
            structlog.processors.format_exc_info,             # adds exception info
            structlog.processors.UnicodeDecoder(),           # ensures unicode
            structlog.processors.JSONRenderer()              # outputs JSON
        ]


        # ----------------------------
        # Loggers
        # ----------------------------
        self.console_logger = logging.getLogger(f"{name}_console")
        self.console_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        self.file_logger = structlog.wrap_logger(
            logging.getLogger(f"{name}_file"),
            processors=file_processors,
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True
        ).bind(**self.context)

        self._logger_cache[name] = self

    # ----------------------------
    # Colored console helper
    # ----------------------------
    def _color_msg(self, level: str, msg: str):
        color = self.LEVEL_COLORS.get(level.upper(), "")
        return f"{color}{level.upper()}: {msg}{self.RESET_COLOR}"

    # ----------------------------
    # Logging methods
    # ----------------------------
    def debug(self, msg: str, **extra):
        self.console_logger.info(self._color_msg("DEBUG", msg))
        self.file_logger.debug(msg, **extra)

    def info(self, msg: str, **extra):
        self.console_logger.info(self._color_msg("INFO", msg))
        self.file_logger.info(msg, **extra)

    def warning(self, msg: str, **extra):
        self.console_logger.info(self._color_msg("WARNING", msg))
        self.file_logger.warning(msg, **extra)

    def error(self, msg: str, **extra):
        self.console_logger.info(self._color_msg("ERROR", msg))
        self.file_logger.error(msg, **extra)

    def critical(self, msg: str, **extra):
        self.console_logger.info(self._color_msg("CRITICAL", msg))
        self.file_logger.critical(msg, **extra)

    def exception(self, msg: str, **extra):
        self.console_logger.info(self._color_msg("ERROR", msg))
        self.file_logger.exception(msg, **extra)

    # ----------------------------
    # Async logging helper
    # ----------------------------
    async def log_async(self, level: str, msg: str, **extra):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: getattr(self, level.lower())(msg, **extra))
