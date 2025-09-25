# app/shared/database/postgres_client_v3.py

import asyncio
import asyncpg
import io
from typing import Callable, Any, List, Optional, Tuple, Dict

from app.shared.database.base import DatabaseClient
from app.shared.retry import RetryPolicy,ExponentialBackoffRetry
from app.config.logger import JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector

logger = JohnWickLogger(name="PostgresClientV3")


class PostgresClient(DatabaseClient):
    """
    Robust async PostgreSQL client with:
      - Connection pooling with retryable initialization
      - Semaphore-based concurrency control with timeout
      - Retryable queries & transactions using ExponentialBackoffRetry
      - Batch execution & bulk inserts
      - High-performance COPY inserts
      - Async metrics reporting and structured logging
    """

    def __init__(
        self,
        dsn: str,
        logger: Optional[JohnWickLogger] = None,
        retry_policy: Optional[ExponentialBackoffRetry] = None,
        max_concurrency: int = 5,
        batch_size: int = 50,
        pool_retry_attempts: int = 3,
        pool_retry_delay: float = 2.0,
        semaphore_timeout: float = 30.0,
    ):
        self.dsn = dsn
        self.logger = logger or logger
        self.retry_policy = retry_policy or ExponentialBackoffRetry()
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.semaphore_timeout = semaphore_timeout
        self.batch_size = batch_size
        self.metrics = MetricsCollector(self.logger)
        self.pool_retry_attempts = pool_retry_attempts
        self.pool_retry_delay = pool_retry_delay

        self.pool: Optional[asyncpg.Pool] = None
        self._stop_event = asyncio.Event()

    # ------------------- Pool Management ------------------- #
    async def _ensure_pool(self):
        """Initialize connection pool with retry support."""
        if self.pool is not None:
            return

        for attempt in range(1, self.pool_retry_attempts + 1):
            try:
                self.pool = await asyncpg.create_pool(dsn=self.dsn)
                self.logger.info("PostgreSQL connection pool started")
                return
            except Exception as e:
                self.logger.exception(f"Pool creation failed (attempt {attempt})")
                if attempt < self.pool_retry_attempts:
                    await asyncio.sleep(self.pool_retry_delay)
                else:
                    raise

    async def start(self):
        """Start connection pool."""
        await self._ensure_pool()

    async def stop(self):
        """Gracefully close connection pool."""
        self._stop_event.set()
        if self.pool:
            await self.pool.close()
            self.logger.info("PostgreSQL connection pool stopped")

    # ------------------- Semaphore ------------------- #
    async def _acquire_semaphore(self):
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=self.semaphore_timeout)
        except asyncio.TimeoutError:
            raise RuntimeError("Semaphore acquire timed out")

    # ------------------- Core Execution ------------------- #
    async def _execute(self, func: Callable[..., Any], *args, **kwargs):
        await self._ensure_pool()
        await self._acquire_semaphore()
        try:
            async with self.pool.acquire() as conn:
                result = await self.retry_policy.execute(func, *args, **kwargs)
            self.metrics.increment("success")
            return result
        except Exception as e:
            self.metrics.increment("failure")
            self.logger.exception("Query failed", extra={"error": str(e), "args": args})
            raise
        finally:
            self.semaphore.release()
            await self.metrics.report_async()

    # ------------------- Public Methods ------------------- #
    async def execute(self, query: str, *args):
        """Execute query without returning results."""
        async def _func(conn):
            return await conn.execute(query, *args)

        return await self._execute(_func)

    async def fetch(self, query: str, *args) -> List[asyncpg.Record]:
        """Execute SELECT query and return all rows."""
        async def _func(conn):
            return await conn.fetch(query, *args)

        return await self._execute(_func)

    async def fetch_one(self, query: str, *args) -> Optional[asyncpg.Record]:
        results = await self.fetch(query, *args)
        return results[0] if results else None

    async def run_in_transaction(self, callback: Callable[[asyncpg.Connection], Any]):
        """Run a callback inside a transaction with retry support."""
        async def _func(conn):
            async with conn.transaction():
                return await callback(conn)

        return await self._execute(_func)

    # ------------------- Batch & Bulk ------------------- #
    async def batch_execute(self, query: str, params_list: List[Tuple[Any, ...]]):
        if not params_list:
            return

        for i in range(0, len(params_list), self.batch_size):
            batch = params_list[i:i + self.batch_size]

            async def _func(conn):
                return await conn.executemany(query, batch)

            await self._execute(_func)
            self.metrics.increment("processed", len(batch))
            self.logger.info("Batch executed", extra={"batch_size": len(batch)})

    async def bulk_insert(self, table: str, rows: List[Dict[str, Any]]):
        """Bulk insert using executemany."""
        if not rows:
            return

        columns = list(rows[0].keys())
        col_names = ", ".join(columns)
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        params_list = [tuple(row[col] for col in columns) for row in rows]

        await self.batch_execute(query, params_list)

    async def copy_bulk_insert(self, table: str, rows: List[Dict[str, Any]]):
        """High-performance COPY insert with safe type handling."""
        if not rows:
            return

        columns = list(rows[0].keys())
        buffer = io.StringIO()
        for row in rows:
            line = "\t".join(str(row.get(col)) if row.get(col) is not None else "\\N" for col in columns)
            buffer.write(line + "\n")
        buffer.seek(0)

        async def _func(conn):
            return await conn.copy_to_table(
                table,
                source=buffer,
                format="csv",
                columns=columns,
                delimiter="\t",
                null="\\N",
            )

        await self._execute(_func)
        self.metrics.increment("processed", len(rows))
        self.logger.info("COPY bulk insert executed", extra={"table": table, "rows": len(rows)})
