import asyncio
import importlib
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from database import get_engine, Base

# Import your logger
from logger import BulletproofLogger

# Single logger instance
from logger import logger  # assumes your snippet already defines it

# Global async session
async_session: sessionmaker[AsyncSession] | None = None

def get_sessionmaker(database_url: str, echo: bool = False) -> sessionmaker[AsyncSession]:
    """
    Return the async SQLAlchemy session factory
    """
    global async_session
    if async_session is None:
        logger.debug(f"Creating AsyncSession factory with database_url={database_url}")
        engine = get_engine(database_url, echo)
        async_session = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            class_=AsyncSession
        )
        logger.info("✅ AsyncSession factory created")
    else:
        logger.debug("AsyncSession factory already exists, returning existing instance")
    return async_session

def import_models_from_features(app_path: str = "app"):
    """
    Scan each feature directory and import all models to register them with Base.
    Logs every import success or failure using BulletproofLogger.
    """
    logger.info(f"Scanning '{app_path}' for feature models...")
    for feature_name in os.listdir(app_path):
        feature_dir = os.path.join(app_path, feature_name)
        if os.path.isdir(feature_dir):
            # Import models.py if it exists
            models_file = os.path.join(feature_dir, "models.py")
            if os.path.exists(models_file):
                module_name = f"{app_path}.{feature_name}.models".replace("/", ".").replace("\\", ".")
                try:
                    importlib.import_module(module_name)
                    logger.info(f"✅ Successfully imported models from {module_name}")
                except Exception as e:
                    logger.exception(f"⚠️ Failed to import {module_name}: {e}")
            else:
                logger.debug(f"No models.py found in {feature_dir}, skipping")

async def init_db(database_url: str, app_path: str = "app"):
    """
    Initialize DB: dynamically import all feature models and create tables.
    Fully logged with BulletproofLogger.
    """
    logger.info("🚀 Starting database initialization...")
    import_models_from_features(app_path)
    engine = get_engine(database_url)
    try:
        async with engine.begin() as conn:
            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created or already exist")
    except Exception as e:
        logger.exception(f"❌ Failed to initialize database: {e}")
        raise

async def drop_db(database_url: str):
    """
    Optional: drop all tables (useful for tests or reset scripts)
    """
    logger.warning("⚠️ Dropping all database tables...")
    engine = get_engine(database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("✅ All tables dropped successfully")
    except Exception as e:
        logger.exception(f"❌ Failed to drop tables: {e}")
        raise
