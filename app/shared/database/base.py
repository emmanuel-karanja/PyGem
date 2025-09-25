from abc import ABC, abstractmethod
from typing import Any, List, Tuple, Dict, Callable, Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import declarative_base

# Declarative base for models
Base = declarative_base()

# Singleton async engine
_engine: Optional[AsyncEngine] = None


def get_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    """
    Initialize and return a singleton SQLAlchemy async engine with pooling options.

    Args:
        database_url (str): Database connection string.
        echo (bool): Enable SQL query logging.

    Returns:
        AsyncEngine: Configured SQLAlchemy async engine.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            database_url,
            echo=echo,
            pool_size=10,        # Minimum connections in pool
            max_overflow=20,     # Extra connections allowed beyond pool_size
            pool_timeout=30,     # Seconds to wait for a connection before timeout
            pool_recycle=1800,   # Recycle connections every 30 minutes
        )
    return _engine


class DatabaseClient(ABC):
    """
    Abstract base class defining the interface for async database clients.
    """

    @abstractmethod
    async def start(self) -> None:
        """Initialize the database connection/pool."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Close the database connection/pool."""
        ...

    @abstractmethod
    async def execute(self, query: str, *args: Any) -> None:
        """Execute a query without returning results."""
        ...

    @abstractmethod
    async def fetch(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return all rows."""
        ...

    @abstractmethod
    async def fetch_one(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        """Execute a SELECT query and return a single row (or None)."""
        ...

    @abstractmethod
    async def run_in_transaction(self, callback: Callable[..., Any]) -> Any:
        """Run a callback inside a transaction."""
        ...

    @abstractmethod
    async def batch_execute(self, query: str, params_list: List[Tuple[Any, ...]]) -> None:
        """Execute multiple queries in batches."""
        ...

    @abstractmethod
    async def bulk_insert(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """Bulk insert rows into a table."""
        ...
