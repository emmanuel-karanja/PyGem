from abc import ABC, abstractmethod
from typing import Any, List, Tuple, Dict, Callable

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
            pool_size=10,          # minimum connections in pool
            max_overflow=20,       # extra connections allowed
            pool_timeout=30,       # seconds to wait for a connection
            pool_recycle=1800,     # recycle connections every 30 minutes
        )
    return engine


class DatabaseClient(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Initialize the database connection/pool"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Close the database connection/pool"""
        pass

    @abstractmethod
    async def execute(self, query: str, *args: Any) -> None:
        """Execute a query without returning results"""
        pass

    @abstractmethod
    async def fetch(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        """Execute a SELECT query and return all rows"""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, *args: Any) -> Dict[str, Any]:
        """Execute a SELECT query and return a single row"""
        pass

    @abstractmethod
    async def run_in_transaction(self, callback: Callable) -> Any:
        """Run a callback inside a transaction"""
        pass

    @abstractmethod
    async def batch_execute(self, query: str, params_list: List[Tuple[Any, ...]]) -> None:
        """Execute multiple queries in batches"""
        pass

    @abstractmethod
    async def bulk_insert(self, table: str, rows: List[Dict[str, Any]]) -> None:
        """Bulk insert rows into a table"""
        pass

