"""
Improved logger with memory-safe caching and simplified injection.
"""

import logging
import structlog
import inspect
from typing import Dict, Optional, Any
from datetime import datetime
import weakref


class JohnWickLogger:
    """Simplified, memory-safe structured logger."""
    
    # Use weak references to prevent memory leaks
    _logger_cache: Dict[str, weakref.ref] = {}
    
    LEVEL_COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m", 
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[1;31m"
    }
    RESET_COLOR = "\033[0m"
    
    def __init__(self, name: str = "default", level: str = "INFO", context: Optional[Dict[str, Any]] = None):
        self.name = name
        self.level = level.upper()
        self.context = context or {}
        
        # Check if logger already exists (using weak refs)
        existing_ref = self._logger_cache.get(name)
        if existing_ref and existing_ref() is not None:
            existing_logger = existing_ref()
            self.console_logger = existing_logger.console_logger
            self.file_logger = existing_logger.file_logger
            return
        
        # Create new logger
        self._setup_loggers()
        
        # Cache with weak reference
        self._logger_cache[name] = weakref.ref(self)
    
    def _setup_loggers(self):
        """Setup console and file loggers."""
        # Console logger with colors
        console_logger = logging.getLogger(f"{self.name}_console")
        console_logger.setLevel(getattr(logging, self.level, logging.INFO))
        
        if not console_logger.handlers:
            ch = logging.StreamHandler()
            ch.setFormatter(logging.Formatter("%(message)s"))
            console_logger.addHandler(ch)
        
        def add_caller_info(logger, method_name, event_dict):
            """Add caller information to log events."""
            frame = inspect.currentframe()
            while frame:
                module = frame.f_globals.get("__name__")
                if (module and 
                    not module.startswith("structlog") and 
                    not module.endswith("john_wick_logger")):
                    event_dict["module"] = module
                    event_dict["function"] = frame.f_code.co_name
                    break
                frame = frame.f_back
            return event_dict
        
        def console_format(logger, method_name, event_dict):
            """Format console output with colors."""
            level = event_dict.get("level", "INFO").upper()
            msg = event_dict.get("event", "")
            timestamp = event_dict.get("timestamp", datetime.now().isoformat())
            
            # Only show caller for warnings and above
            caller_info = ""
            if level in ("WARNING", "ERROR", "CRITICAL"):
                module = event_dict.get("module", "")
                func = event_dict.get("function", "")
                caller_info = f" ({module}.{func})" if module and func else ""
            
            color = self.LEVEL_COLORS.get(level, "")
            return f"{color}{timestamp} [{self.name}] {level}: {msg}{caller_info}{self.RESET_COLOR}"
        
        self.console_logger = structlog.wrap_logger(
            console_logger,
            processors=[
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                add_caller_info,
                console_format
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True
        ).bind(**self.context)
        
        # File logger with JSON
        file_logger = logging.getLogger(f"{self.name}_file")
        file_logger.setLevel(getattr(logging, self.level, logging.INFO))
        
        if not any(isinstance(h, logging.FileHandler) for h in file_logger.handlers):
            fh = logging.FileHandler("app.log", encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(message)s"))
            file_logger.addHandler(fh)
        
        self.file_logger = structlog.wrap_logger(
            file_logger,
            processors=[
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                add_caller_info,
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True
        ).bind(**self.context)
    
    # Logging methods
    def debug(self, msg: str, **kwargs):
        self.console_logger.debug(msg, **kwargs)
        self.file_logger.debug(msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        self.console_logger.info(msg, **kwargs)
        self.file_logger.info(msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        self.console_logger.warning(msg, **kwargs)
        self.file_logger.warning(msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        self.console_logger.error(msg, **kwargs)
        self.file_logger.error(msg, **kwargs)
    
    def critical(self, msg: str, **kwargs):
        self.console_logger.critical(msg, **kwargs)
        self.file_logger.critical(msg, **kwargs)
    
    def exception(self, msg: str, **kwargs):
        self.console_logger.exception(msg, **kwargs)
        self.file_logger.exception(msg, **kwargs)


# Factory function for injection
def create_logger(name: str = None, **context) -> JohnWickLogger:
    """Create logger instance (used by LoggerBinding)."""
    return JohnWickLogger(name or __name__, **context)