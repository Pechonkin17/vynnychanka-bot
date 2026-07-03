"""Tiny exponential-backoff retry helper.

Pulled out of :class:`~brain.gemini.GeminiBackend` so the backend has one
reason to change (talking to the provider) and the retry policy has one
reason to change (timing and which exceptions are retryable).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def retry_async[T](
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    base_backoff: float,
    retryable: tuple[type[BaseException], ...] = (Exception,),
    name: str = "operation",
) -> T:
    """Call ``operation`` up to ``attempts`` times with exponential backoff.

    Backoff between attempt *n* and *n+1* is ``base_backoff * 2**(n-1)``.

    :param operation: A zero-argument coroutine factory. It is *called* on each
        attempt — pass a lambda, not a coroutine object.
    :param attempts: Maximum number of attempts. Must be ``>= 1``.
    :param base_backoff: Seconds to wait before the second attempt.
    :param retryable: Exception types that trigger a retry. Anything else
        propagates immediately.
    :param name: Used only in log messages.
    :raises ValueError: if ``attempts < 1``.
    :raises Exception: the last exception raised by ``operation`` if every
        attempt fails. The exception type is preserved (no wrapping).
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except retryable as exc:
            last_exc = exc
            logger.warning(
                "%s failed (attempt %d/%d): %s",
                name,
                attempt,
                attempts,
                exc,
            )
            if attempt == attempts:
                break
            await asyncio.sleep(base_backoff * 2 ** (attempt - 1))

    assert last_exc is not None  # for the type checker; loop guarantees this
    raise last_exc
