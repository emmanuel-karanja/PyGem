# john_wick_logger_uvicorn_stack.py
import asyncio
import logging
import structlog
import inspect
from typing import Optional, Dict

class JohnWickLogger:
    _logger_cache: Dict[str, "JohnWickLogger"] = {}

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
        console_logger = logging.getLogger(f"{name}_console")
        console_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        if not console_logger.hasHandlers():
            console_logger.addHandler(console_handler)
        self.console_logger = console_logger

        # ----------------------------
        # File logger (structlog JSON)
        # ----------------------------
        file_logger = logging.getLogger(f"{name}_file")
        file_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        if not any(isinstance(h, logging.FileHandler) for h in file_logger.handlers):
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(message)s"))
            file_logger.addHandler(fh)

        # ----------------------------
        # Custom processor to walk the stack
        # ----------------------------
        def add_caller_stack(logger, method_name, event_dict):
            frame = inspect.currentframe()
            while frame:
                module_name = frame.f_globals.get("__name__")
                if module_name and not module_name.startswith("structlog") and not module_name.endswith("john_wick_logger"):
                    event_dict["module"] = module_name
                    event_dict["function"] = frame.f_code.co_name
                    event_dict["file"] = frame.f_code.co_filename
                    event_dict["lineno"] = frame.f_lineno
                    cls = frame.f_locals.get("self")
                    if cls:
                        event_dict["class"] = cls.__class__.__name__
                    break
                frame = frame.f_back
            return event_dict

        file_processors = [
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            add_caller_stack,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ]

        self.file_logger = structlog.wrap_logger(
            file_logger,
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
