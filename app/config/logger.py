# app/shared/logger

import os
from logging import Logger
from app.shared.logger.john_wick_logger import JohnWickLogger
from app.config.settings import Settings

settings = Settings()

# Ensure the log directory exists
log_dir = os.path.dirname(settings.log_file)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

# Private singleton instance
_logger: Logger | None = None

def get_logger() -> Logger:
    """
    Return a global JohnWickLogger instance.
    Creates it on first call (singleton pattern).
    Loads app_name and log_file from settings.
    """
    global _logger
    if _logger is None:
        _logger = JohnWickLogger(
            name=settings.app_name,
            log_file=settings.log_file,
            level=settings.log_level
        )
    return _logger

# Expose both convenience and full control
logger: Logger = get_logger()
JohnWickLogger = JohnWickLogger  # re-export for direct access
