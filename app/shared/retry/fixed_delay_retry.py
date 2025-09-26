import asyncio
from typing import Any, Awaitable, Callable
from app.shared.retry.base import RetryPolicy
from app.shared.logger import JohnWickLogger


class FixedDelayRetry(RetryPolicy):
    def __init__(self, max_retries: int = 3, delay: float = 1.0):
        self.max_retries = max_retries
        self.delay = delay
        self.logger = JohnWickLogger(name="FixedDelayRetry")

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
                        "FixedDelay retries exhausted",
                        extra={
                            "function": getattr(func, "__name__", str(func)),
                            "error": str(exc),
                            "attempts": self.max_retries,
                        },
                    )
                    raise
                self.logger.warning(
                    f"Attempt {attempt} failed, retrying in {self.delay:.2f}s",
                    extra={"error": str(exc)},
                )
                try:
                    await asyncio.sleep(self.delay)
                except asyncio.CancelledError:
                    self.logger.info("Retry sleep cancelled")
                    raise
