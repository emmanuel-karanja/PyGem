import asyncio
import asyncpg
import time
from typing import Callable, Any, List, Tuple
from logging import Logger

from database.base import DatabaseClient
from retry.base import RetryPolicy
from metrics.metrics_collector import MetricsCollector


class PostgresClient(DatabaseClient):
    def __init__(
        self,
        dsn: str,
        logger: Logger,
        retry_policy: RetryPolicy = None,
        max_concurrency: int = 5,
        batch_size: int = 50
    ):
        """
        Async PostgreSQL client with connection pooling, retries, batching, and metrics.

        Args:
            dsn (str): PostgreSQL DSN
            logger (Logger): Logger instance
            retry_policy (RetryPolicy, optional): Retry logic
            max_concurrency (int, optional): Max concurrent queries
            batch_size (int, optional): Max batch size for batched operations
        """
        self.dsn = dsn
        self.logger = logger
        self.retry_policy = retry_policy
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.batch_size = batch_size
        self.metrics = MetricsCollector(logger)

        self.pool: asyncpg.Pool | None = None
        self._stop_event = asyncio.Event()

    async def start(self):
        """Initialize connection pool"""
        self.pool = await asyncpg.create_pool(dsn=self.dsn)
        self.logger.info("PostgreSQL connection pool started")

    async def stop(self):
        """Close connection pool"""
        self._stop_event.set()
        if self.pool:
            await self.pool.close()
            self.logger.info("PostgreSQL connection pool stopped")

    async def execute(self, query: str, *args):
        """Execute a query without returning results"""
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    if self.retry_policy:
                        await self.retry_policy.execute(lambda: conn.execute(query, *args))
                    else:
                        await conn.execute(query, *args)
                    self.metrics.processed += 1
                    self.logger.info("Query executed", extra={"query": query, "args": args})
                except Exception as exc:
                    self.metrics.failed_process += 1
                    self.logger.exception("Query execution failed", extra={"query": query, "args": args})
                    raise
                finally:
                    self.metrics.report()

    async def fetch(self, query: str, *args):
        """Execute a SELECT query and return all rows"""
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    if self.retry_policy:
                        result = await self.retry_policy.execute(lambda: conn.fetch(query, *args))
                    else:
                        result = await conn.fetch(query, *args)
                    self.metrics.processed += 1
                    self.logger.info("Query fetched", extra={"query": query, "args": args})
                    return result
                except Exception as exc:
                    self.metrics.failed_process += 1
                    self.logger.exception("Query fetch failed", extra={"query": query, "args": args})
                    raise
                finally:
                    self.metrics.report()

    async def fetch_one(self, query: str, *args):
        """Execute a SELECT query and return a single row"""
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    if self.retry_policy:
                        result = await self.retry_policy.execute(lambda: conn.fetchrow(query, *args))
                    else:
                        result = await conn.fetchrow(query, *args)
                    self.metrics.processed += 1
                    self.logger.info("Query fetched one row", extra={"query": query, "args": args})
                    return result
                except Exception as exc:
                    self.metrics.failed_process += 1
                    self.logger.exception("Query fetch_one failed", extra={"query": query, "args": args})
                    raise
                finally:
                    self.metrics.report()

    async def run_in_transaction(self, callback: Callable[[asyncpg.Connection], Any]):
        """Run a callback inside a transaction"""
        async with self.semaphore:
            async with self.pool.acquire() as conn:
                try:
                    async with conn.transaction():
                        result = await callback(conn)
                    self.metrics.processed += 1
                    return result
                except Exception as exc:
                    self.metrics.failed_process += 1
                    self.logger.exception("Transaction failed")
                    raise
                finally:
                    self.metrics.report()

    async def batch_execute(self, query: str, params_list: List[Tuple[Any, ...]]):
        """
        Execute multiple queries in batches for high throughput.
        
        Args:
            query (str): SQL query with placeholders
            params_list (List[Tuple[Any]]): List of parameter tuples
        """
        if not params_list:
            return

        # Split into batches
        for i in range(0, len(params_list), self.batch_size):
            batch = params_list[i:i + self.batch_size]

            async def _batch_task():
                async with self.semaphore:
                    async with self.pool.acquire() as conn:
                        try:
                            if self.retry_policy:
                                await self.retry_policy.execute(lambda: conn.executemany(query, batch))
                            else:
                                await conn.executemany(query, batch)
                            self.metrics.processed += len(batch)
                            self.logger.info("Batch executed", extra={"query": query, "batch_size": len(batch)})
                        except Exception as exc:
                            self.metrics.failed_process += len(batch)
                            self.logger.exception("Batch execution failed", extra={"query": query, "batch": batch})
                            raise
                        finally:
                            self.metrics.report()

            await _batch_task()
    async def bulk_insert(self, table: str, rows: list[dict]):
        """
        Bulk insert a list of dictionaries into a table with batching.

        Args:
            table (str): Table name
            rows (List[dict]): List of rows, each row as a dict {column: value}
        """
        if not rows:
            return

        columns = rows[0].keys()
        col_names = ", ".join(columns)
        placeholders = ", ".join(f"${i+1}" for i in range(len(columns)))
        query = f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})"

        # Convert dicts to tuples matching column order
        params_list = [tuple(row[col] for col in columns) for row in rows]

        # Execute in batches
        for i in range(0, len(params_list), self.batch_size):
            batch = params_list[i:i + self.batch_size]

            async def _insert_batch():
                async with self.semaphore:
                    async with self.pool.acquire() as conn:
                        try:
                            if self.retry_policy:
                                await self.retry_policy.execute(lambda: conn.executemany(query, batch))
                            else:
                                await conn.executemany(query, batch)
                            self.metrics.processed += len(batch)
                            self.logger.info(
                                "Bulk insert batch executed",
                                extra={"table": table, "batch_size": len(batch)}
                            )
                        except Exception as exc:
                            self.metrics.failed_process += len(batch)
                            self.logger.exception(
                                "Bulk insert batch failed",
                                extra={"table": table, "batch": batch}
                            )
                            raise
                        finally:
                            self.metrics.report()

            await _insert_batch()
