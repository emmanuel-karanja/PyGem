class FixedDelayRetry(RetryPolicy):
    def __init__(self, max_retries: int = 3, delay: float = 1.0):
        self.max_retries = max_retries
        self.delay = delay

    async def execute(self, func: Callable[..., Awaitable[Any]], *args, **kwargs):
        for attempt in range(1, self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as exc:
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(self.delay)
