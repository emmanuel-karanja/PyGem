import asyncio
import importlib
import os
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker
from app.shared.logger import JohnWickLogger


logger=JohnWickLogger(name="DB_Session_Init")
# ----------------------------
# Base declarative class
# ----------------------------
Base = declarative_base()

# ----------------------------
# Global engine & session
# ----------------------------
engine: AsyncEngine | None = None
async_session: sessionmaker[AsyncSession] | None = None

# ----------------------------
# Engine factory
# ----------------------------
def get_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """
    Initialize or return the global SQLAlchemy async engine with pooling options.
    Uses singleton pattern to avoid multiple engines.
    """
    global engine
    if engine is None:
        engine = create_async_engine(
            str(database_url),   #Needed to avoid the Pydantic 2 → SQLAlchemy URL mismatch
            echo=echo,
            pool_size=10,        # minimum connections in pool
            max_overflow=20,     # extra connections allowed
            pool_timeout=30,     # seconds to wait for a connection
            pool_recycle=1800,   # recycle connections every 30 minutes
        )
        logger.info(f"✅ Async engine created for {database_url}")
    return engine

# ----------------------------
# Async session factory
# ----------------------------
def get_sessionmaker(database_url: str, echo: bool = False) -> sessionmaker[AsyncSession]:
    """
    Return the async SQLAlchemy session factory (singleton).
    """
    global async_session
    if async_session is None:
        logger.debug(f"Creating AsyncSession factory with database_url={database_url}")
        engine = get_engine(database_url, echo)
        async_session = sessionmaker(
            bind=engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        logger.info("✅ AsyncSession factory created")
    else:
        logger.debug("AsyncSession factory already exists, returning existing instance")
    return async_session

# ----------------------------
# Dynamic model import
# ----------------------------
def import_models_from_features(app_path: str = "app"):
    """
    Scan each feature directory and import all models to register them with Base.
    Logs every import success or failure using JohnWickLogger.
    """
    logger.info(f"Scanning '{app_path}' for feature models...")
    for feature_name in os.listdir(app_path):
        feature_dir = os.path.join(app_path, feature_name)
        if os.path.isdir(feature_dir):
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

# ----------------------------
# Database initialization
# ----------------------------
async def init_db(database_url: str, app_path: str = "app"):
    """
    Initialize DB: dynamically import all feature models and create tables.
    Fully logged with JohnWickLogger.
    """
    logger.info("🚀 Starting database initialization...")
    # import_models_from_features(app_path)
    engine = get_engine(database_url)
    try:
        async with engine.begin() as conn:
            logger.info("Creating database tables...")
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created or already exist")
    except Exception as e:
        logger.exception(f"❌ Failed to initialize database: {e}")
        raise

# ----------------------------
# Drop all tables (optional)
# ----------------------------
async def drop_db(database_url: str):
    """
    Drop all tables (useful for tests or reset scripts)
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
