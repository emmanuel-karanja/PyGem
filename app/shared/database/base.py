from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import declarative_base

Base = declarative_base()
engine: AsyncEngine | None = None

def get_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """
    Initialize the SQLAlchemy async engine with pooling options.
    """
    global engine
    if engine is None:
        engine = create_async_engine(
            database_url,
            echo=echo,
            pool_size=10,        # minimum connections in pool
            max_overflow=20,     # extra connections allowed
            pool_timeout=30,     # seconds to wait for a connection
            pool_recycle=1800,   # recycle connections every 30 minutes
        )
    return engine
