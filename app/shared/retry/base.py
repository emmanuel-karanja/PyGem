# app/shared/retry/base.py
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable


class RetryPolicy(ABC):
    """
    Base class for retry policies.
    Defines the interface for executing an async function with retries.
    """

    @abstractmethod
    async def execute(self, func: Callable[..., Awaitable[Any]], *args, **kwargs) -> Any:
        """
        Execute the given async function with retries.

        Args:
            func: An async function to execute.
            *args: Positional arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.

        Returns:
            The result of the async function if successful.

        Raises:
            Exception: If retries are exhausted.
        """
        pass
