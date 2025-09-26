# john_wick_logger_uvicorn_full_auto.py
import asyncio
import logging
import structlog
import inspect
from typing import Optional, Dict
from datetime import datetime

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
        # Stack walker processor
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

        # ----------------------------
        # Console processor
        # ----------------------------
        def console_processor(logger, method_name, event_dict):
            ts = event_dict.get("timestamp") or datetime.utcnow().isoformat()
            level = event_dict.get("level", method_name).upper()
            logger_name = event_dict.get("logger", self.name).replace("_console", "")
            msg = event_dict.get("event", "")

            # Only show caller info for WARNING and above
            if level in ("WARNING", "ERROR", "CRITICAL"):
                module = event_dict.get("module", "")
                func = event_dict.get("function", "")
                lineno = event_dict.get("lineno", "")
                caller = f"{module}.{func}:{lineno}" if module and func else ""
            else:
                caller = ""

            color = self.LEVEL_COLORS.get(level, "")
            return f"{color}{ts} [{logger_name}] {level}: {msg} {caller}{self.RESET_COLOR}"

        # ----------------------------
        # Console logger
        # ----------------------------
        console_logger = logging.getLogger(f"{name}_console")
        console_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        if not console_logger.hasHandlers():
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter("%(message)s"))
            console_logger.addHandler(ch)

        self.console_logger = structlog.wrap_logger(
            console_logger,
            processors=[
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                add_caller_stack,
                console_processor
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True
        ).bind(logger=name, **self.context)  # auto bind logger name

        # ----------------------------
        # File logger (JSON)
        # ----------------------------
        file_logger = logging.getLogger(f"{name}_file")
        file_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        if not any(isinstance(h, logging.FileHandler) for h in file_logger.handlers):
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(message)s"))
            file_logger.addHandler(fh)

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
        ).bind(logger=name, **self.context)

        self._logger_cache[name] = self

    # ----------------------------
    # Logging methods
    # ----------------------------
    def debug(self, msg: str, **extra):
        self.console_logger.debug(msg, **extra)
        self.file_logger.debug(msg, **extra)

    def info(self, msg: str, **extra):
        self.console_logger.info(msg, **extra)
        self.file_logger.info(msg, **extra)

    def warning(self, msg: str, **extra):
        self.console_logger.warning(msg, **extra)
        self.file_logger.warning(msg, **extra)

    def error(self, msg: str, **extra):
        self.console_logger.error(msg, **extra)
        self.file_logger.error(msg, **extra)

    def critical(self, msg: str, **extra):
        self.console_logger.critical(msg, **extra)
        self.file_logger.critical(msg, **extra)

    def exception(self, msg: str, **extra):
        self.console_logger.exception(msg, **extra)
        self.file_logger.exception(msg, **extra)

    # ----------------------------
    # Async logging helper
    # ----------------------------
    async def log_async(self, level: str, msg: str, **extra):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: getattr(self, level.lower())(msg, **extra))
