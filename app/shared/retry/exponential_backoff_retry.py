import asyncio
from typing import Any, Awaitable, Callable
from app.shared.retry.base import RetryPolicy
from app.config.logger import get_logger, JohnWickLogger


class ExponentialBackoffRetry(RetryPolicy):
    def __init__(self, max_retries: int = 5, base_delay: float = 0.5):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.logger = get_logger() or JohnWickLogger(name="ExponentialBackoffRetry")

    async def execute(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except asyncio.CancelledError:
                # Propagate cancellation immediately
                raise
            except Exception as exc:
                if attempt == self.max_retries:
                    self.logger.error(
                        "Exponential backoff retries exhausted",
                        extra={
                            "function": getattr(func, "__name__", str(func)),
                            "error": str(exc),
                            "attempts": self.max_retries,
                        },
                    )
                    raise
                delay = self.base_delay * (2 ** (attempt - 1))
                self.logger.warning(
                    f"Attempt {attempt} failed, retrying after {delay:.2f}s",
                    extra={"error": str(exc)},
                )
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    self.logger.info("Retry sleep cancelled")
                    raise
