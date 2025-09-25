# app/shared/logger/__init__.py

import os
from logging import Logger
from app.shared.logger.bulletproof_logger import BulletproofLogger
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
    Return a global BulletproofLogger instance.
    Creates it on first call (singleton pattern).
    Loads app_name and log_file from settings.
    """
    global _logger
    if _logger is None:
        _logger = BulletproofLogger(
            name=settings.app_name,
            log_file=settings.log_file,
            level=settings.log_level
        )
    return _logger

# Expose both convenience and full control
logger: Logger = get_logger()
BulletproofLogger = BulletproofLogger  # re-export for direct access
