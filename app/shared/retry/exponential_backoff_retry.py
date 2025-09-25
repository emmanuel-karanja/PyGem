from typing import Any, Awaitable, Callable

from retry.base import RetryPolicy


class ExponentialBackoffRetry(RetryPolicy):
    def __init__(self, max_retries: int = 5, base_delay: float = 0.5):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute(self, func: Callable[..., Awaitable[Any]], *args, **kwargs):
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(self.base_delay * (2 ** (attempt - 1)))
