"""Per-key token-bucket rate limiter + atomic multi-bucket consume helper.

Token bucket semantics:
  * Each key has a bucket that holds at most ``capacity`` tokens.
  * Tokens refill at a steady rate up to the capacity.
  * Each accepted request consumes one token.
  * If the bucket is empty when a request arrives, it is rejected.

Memory: the bucket dict is bounded by ``max_keys`` using LRU eviction. Every
access (peek or try_acquire) marks a key as recently-used; when the dict is
full, inserting a new key evicts the least-recently-used one. This is the
correct semantic — a long-quiet user who returns gets a fresh bucket, which
is no different from what they'd see after a process restart.

Concurrency: safe under a single asyncio event loop (no awaits inside any
method, no preemption). NOT safe across OS threads or processes — for that
you need a shared store (e.g. Redis).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(slots=True)
class _Bucket:
    tokens: float
    last_refill: float


class TokenBucketLimiter:
    """Per-key token bucket with LRU-bounded memory."""

    def __init__(
        self,
        *,
        capacity: int,
        refill_per_second: float,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create a limiter.

        :param capacity: Maximum tokens per bucket (the burst limit).
        :param refill_per_second: Tokens added per second (the sustained rate).
        :param max_keys: Cap on tracked keys; oldest is evicted on overflow.
        :param clock: Source of monotonic time, injectable for tests.
        :raises ValueError: on non-positive inputs.
        """
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        if refill_per_second <= 0:
            raise ValueError("refill_per_second must be > 0")
        if max_keys < 1:
            raise ValueError("max_keys must be >= 1")

        self._capacity = capacity
        self._refill = refill_per_second
        self._max_keys = max_keys
        self._clock = clock
        self._buckets: OrderedDict[int, _Bucket] = OrderedDict()

    def try_acquire(self, key: int) -> bool:
        """Attempt to consume one token for ``key``. Return True on success.

        A first-ever request from a key (or a re-request after LRU eviction)
        is always allowed: the bucket is created full and one token is
        immediately consumed.
        """
        now = self._clock()
        bucket = self._buckets.get(key)
        if bucket is None:
            self._insert(key, _Bucket(tokens=self._capacity - 1, last_refill=now))
            return True

        self._buckets.move_to_end(key)
        elapsed = max(0.0, now - bucket.last_refill)
        bucket.tokens = min(self._capacity, bucket.tokens + elapsed * self._refill)
        bucket.last_refill = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True
        return False

    def peek(self, key: int) -> bool:
        """Return True iff :meth:`try_acquire` would currently succeed.

        Does NOT mutate bucket state (tokens, last_refill). Does update the
        key's LRU position, since "we looked at it" is a form of usage.
        """
        bucket = self._buckets.get(key)
        if bucket is None:
            return True

        self._buckets.move_to_end(key)
        elapsed = max(0.0, self._clock() - bucket.last_refill)
        available = min(self._capacity, bucket.tokens + elapsed * self._refill)
        return available >= 1.0

    def _insert(self, key: int, bucket: _Bucket) -> None:
        if len(self._buckets) >= self._max_keys:
            self._buckets.popitem(last=False)
        self._buckets[key] = bucket


def try_acquire_all(
    pairs: Sequence[tuple[TokenBucketLimiter, int]],
) -> int | None:
    """Atomically: peek every (limiter, key); if any would deny, consume none.

    On success, every limiter has one token consumed and ``None`` is returned.
    On failure, returns the index of the first pair that would deny — and no
    limiter is mutated, so a single noisy bucket cannot unfairly burn tokens
    from the others.

    Atomicity holds because no ``await`` happens between peek and acquire;
    asyncio cannot preempt this function mid-execution. Do not introduce
    awaits inside this function.
    """
    for index, (limiter, key) in enumerate(pairs):
        if not limiter.peek(key):
            return index

    for limiter, key in pairs:
        limiter.try_acquire(key)
    return None
