from logging import Logger
from logger import BulletproofLogger

# Single logger instance for the whole app
logger = BulletproofLogger(name="ModularApp", log_file="modular_app.log")
