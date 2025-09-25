# app/shared/database/postgres_client.py

import asyncio
import asyncpg
import io
from typing import Callable, Any, List, Optional, Tuple

from app.shared.database.base import DatabaseClient
from app.shared.retry.base import RetryPolicy
from app.config.logger import get_logger, JohnWickLogger
from app.shared.metrics.metrics_collector import MetricsCollector


class PostgresClient(DatabaseClient):
    """
    Async PostgreSQL client with connection pooling, retries, batching,
    transactions, metrics, structured logging, and COPY-based bulk insert.
    """

    def __init__(
        self,
        dsn: str,
        logger: get_logger() or Optional[JohnWickLogger] = None,
        retry_policy: Optional[RetryPolicy] = None,
        max_concurrency: int = 5,
        batch_size: int = 50,
    ):
        self.dsn = dsn
        self.logger = logger or logger
        self.retry_policy = retry_policy
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.batch_size = batch_size
        self.metrics = MetricsCollector(self.logger)

        self.pool: Optional[asyncpg.Pool] = None
        self._stop_event = asyncio.Event()

    async def _ensure_pool(self):
        """Ensure the connection pool is initialized."""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(dsn=self.dsn)
            self.logger.info("PostgreSQL connection pool started")

    async def start(self):
        """Manually start the connection pool (optional)."""
        await self._ensure_pool()

    async def stop(self):
        """Close connection pool gracefully."""
        self._stop_event.set()
        if self.pool:
            await self.pool.close()
            self.logger.info("PostgreSQL connection pool stopped")

    async def _execute_with_retry(self, func: Callable, *args, **kwargs):
        """Helper: run with retry policy if provided."""
        if self.retry_policy:
            return await self.retry_policy.execute(func, *args, **kwargs)
        return await func(*args, **kwargs)

    async def execute(self, query: str, *args):
        """Execute a query without returning results."""
        await self._ensure_pool()
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    await self._execute_with_retry(conn.execute, query, *args)
                    self.metrics.increment("success")
                    self.logger.info("Query executed", extra={"query": query, "args": args})
                except Exception:
                    self.metrics.increment("failure")
                    self.logger.exception("Query execution failed", extra={"query": query, "args": args})
                    raise
                finally:
                    self.metrics.report()

    async def fetch(self, query: str, *args):
        """Execute a SELECT query and return all rows."""
        await self._ensure_pool()
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    result = await self._execute_with_retry(conn.fetch, query, *args)
                    self.metrics.increment("success")
                    self.logger.info("Query fetched", extra={"query": query, "args": args})
                    return result
                except Exception:
                    self.metrics.increment("failure")
                    self.logger.exception("Query fetch failed", extra={"query": query, "args": args})
                    raise
                finally:
                    self.metrics.report()

    async def fetch_one(self, query: str, *args):
        """Execute a SELECT query and return a single row."""
        await self._ensure_pool()
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    result = await self._execute_with_retry(conn.fetchrow, query, *args)
                    self.metrics.increment("success")
                    self.logger.info("Query fetched one row", extra={"query": query, "args": args})
                    return result
                except Exception:
                    self.metrics.increment("failure")
                    self.logger.exception("Query fetch_one failed", extra={"query": query, "args": args})
                    raise
                finally:
                    self.metrics.report()

    async def run_in_transaction(self, callback: Callable[[asyncpg.Connection], Any]):
        """Run a callback inside a transaction with optional retry."""
        await self._ensure_pool()
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    async with conn.transaction():
                        if self.retry_policy:
                            result = await self.retry_policy.execute(callback, conn)
                        else:
                            result = await callback(conn)
                    self.metrics.increment("success")
                    return result
                except Exception:
                    self.metrics.increment("failure")
                    self.logger.exception("Transaction failed")
                    raise
                finally:
                    self.metrics.report()

    async def batch_execute(self, query: str, params_list: List[Tuple[Any, ...]]):
        """Execute multiple queries in batches."""
        if not params_list:
            return

        await self._ensure_pool()
        for i in range(0, len(params_list), self.batch_size):
            batch = params_list[i:i + self.batch_size]
            async with self.semaphore:
                async with self.pool.acquire() as conn:
                    try:
                        await self._execute_with_retry(conn.executemany, query, batch)
                        self.metrics.increment("processed", len(batch))
                        self.logger.info("Batch executed", extra={"query": query, "batch_size": len(batch)})
                    except Exception:
                        self.metrics.increment("failed_process", len(batch))
                        self.logger.exception("Batch execution failed", extra={"query": query, "batch": batch})
                        raise
                    finally:
                        self.metrics.report()

    async def bulk_insert(self, table: str, rows: list[dict]):
        """Bulk insert rows using batches of executemany."""
        if not rows:
            return

        await self._ensure_pool()
        columns = rows[0].keys()
        col_names = ", ".join(columns)
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"
        params_list = [tuple(row[col] for col in columns) for row in rows]

        for i in range(0, len(params_list), self.batch_size):
            batch = params_list[i:i + self.batch_size]
            async with self.semaphore:
                async with self.pool.acquire() as conn:
                    try:
                        await self._execute_with_retry(conn.executemany, query, batch)
                        self.metrics.increment("processed", len(batch))
                        self.logger.info("Bulk insert batch executed", extra={"table": table, "batch_size": len(batch)})
                    except Exception:
                        self.metrics.increment("failed_process", len(batch))
                        self.logger.exception("Bulk insert batch failed", extra={"table": table, "batch": batch})
                        raise
                    finally:
                        self.metrics.report()

    async def copy_bulk_insert(self, table: str, rows: list[dict]):
        """Ultra-fast bulk insert using PostgreSQL COPY command."""
        if not rows:
            return

        await self._ensure_pool()
        columns = list(rows[0].keys())
        col_names = ", ".join(columns)

        buffer = io.StringIO()
        for row in rows:
            buffer.write("\t".join(str(row[col]) if row[col] is not None else "\\N" for col in columns))
            buffer.write("\n")
        buffer.seek(0)

        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    await self._execute_with_retry(
                        conn.copy_to_table,
                        table,
                        source=buffer,
                        format="csv",
                        columns=columns,
                        delimiter="\t",
                        null="\\N",
                    )
                    self.metrics.increment("processed", len(rows))
                    self.logger.info("COPY bulk insert executed", extra={"table": table, "rows": len(rows)})
                except Exception:
                    self.metrics.increment("failed_process", len(rows))
                    self.logger.exception("COPY bulk insert failed", extra={"table": table, "rows": len(rows)})
                    raise
                finally:
                    self.metrics.report()
