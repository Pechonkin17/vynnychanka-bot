"""Tests for retry_async."""

from __future__ import annotations

import pytest

from brain.retry import retry_async


async def test_returns_first_success():
    calls = 0

    async def op() -> str:
        nonlocal calls
        calls += 1
        return "ok"

    assert await retry_async(op, attempts=3, base_backoff=0) == "ok"
    assert calls == 1


async def test_retries_then_succeeds():
    calls = 0

    async def op() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("transient")
        return "ok"

    assert await retry_async(op, attempts=3, base_backoff=0) == "ok"
    assert calls == 3


async def test_raises_last_exception_when_exhausted():
    async def op() -> str:
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        await retry_async(op, attempts=2, base_backoff=0)


async def test_non_retryable_propagates_immediately():
    calls = 0

    async def op() -> str:
        nonlocal calls
        calls += 1
        raise ValueError("fatal")

    with pytest.raises(ValueError):
        await retry_async(op, attempts=3, base_backoff=0, retryable=(RuntimeError,))
    assert calls == 1


async def test_attempts_must_be_positive():
    async def op() -> str:
        return "x"

    with pytest.raises(ValueError):
        await retry_async(op, attempts=0, base_backoff=0)
