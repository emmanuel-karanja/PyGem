# john_wick_logger_fast_colored.py
import sys
import asyncio
from loguru import logger

# Mapping log levels to colors for console
LEVEL_COLORS = {
    "DEBUG": "<blue>{level}</blue>",
    "INFO": "<green>{level}</green>",
    "WARNING": "<yellow>{level}</yellow>",
    "ERROR": "<red>{level}</red>",
    "CRITICAL": "<magenta>{level}</magenta>",
    "EXCEPTION": "<red>{level}</red>",
}

class JohnWickLogger:
    def __init__(self, name: str = "default", log_file: str = "app.log", level: str = "INFO"):
        """
        name: kept for interface compatibility
        log_file: file path for detailed logging
        level: minimum log level
        """
        self.name = name

        # Remove default Loguru logger
        logger.remove()

        # ----------------------------
        # File logger (detailed, structured JSON)
        # ----------------------------
        logger.add(
            log_file,
            rotation="10 MB",
            retention=5,
            level=level,
            serialize=True,  # JSON
            enqueue=True,    # async-safe
        )

        # ----------------------------
        # Console logger (minimal + colored levels)
        # ----------------------------
        logger.add(
            sys.stdout,
            colorize=True,
            level=level,
            format="<green>{time:HH:mm:ss}</green> | {level} | {message}",
            enqueue=True,
        )

    # ----------------------------
    # Logging methods
    # ----------------------------
    def debug(self, msg: str, **extra):
        logger.bind(**extra).debug(msg)

    def info(self, msg: str, **extra):
        logger.bind(**extra).info(msg)

    def warning(self, msg: str, **extra):
        logger.bind(**extra).warning(msg)

    def error(self, msg: str, **extra):
        logger.bind(**extra).error(msg)

    def exception(self, msg: str, **extra):
        logger.bind(**extra).exception(msg)

    # ----------------------------
    # Async logging
    # ----------------------------
    async def log_async(self, level: str, msg: str, **extra):
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: logger.bind(**extra).log(level, msg))
