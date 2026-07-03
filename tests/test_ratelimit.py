"""Tests for TokenBucketLimiter + try_acquire_all — driven by a fake clock."""

from __future__ import annotations

import pytest

from bot.ratelimit import TokenBucketLimiter, try_acquire_all


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _make(
    capacity: int = 3,
    refill_per_second: float = 1.0,
    max_keys: int = 10_000,
) -> tuple[TokenBucketLimiter, FakeClock]:
    clock = FakeClock()
    limiter = TokenBucketLimiter(
        capacity=capacity,
        refill_per_second=refill_per_second,
        max_keys=max_keys,
        clock=clock,
    )
    return limiter, clock


def test_first_request_always_passes():
    limiter, _ = _make()
    assert limiter.try_acquire(user_id := 42) is True
    del user_id


def test_burst_up_to_capacity_then_blocks():
    limiter, _ = _make(capacity=3)
    assert [limiter.try_acquire(1) for _ in range(3)] == [True, True, True]
    assert limiter.try_acquire(1) is False


def test_refill_restores_one_token():
    limiter, clock = _make(capacity=3, refill_per_second=1.0)
    for _ in range(3):
        limiter.try_acquire(1)
    assert limiter.try_acquire(1) is False
    clock.advance(1.0)
    assert limiter.try_acquire(1) is True
    assert limiter.try_acquire(1) is False  # bucket back to empty


def test_refill_caps_at_capacity():
    limiter, clock = _make(capacity=3, refill_per_second=1.0)
    for _ in range(3):
        limiter.try_acquire(1)
    # Waiting much longer than needed must NOT give more than capacity.
    clock.advance(100.0)
    assert [limiter.try_acquire(1) for _ in range(3)] == [True, True, True]
    assert limiter.try_acquire(1) is False


def test_buckets_are_per_key():
    limiter, _ = _make(capacity=1)
    assert limiter.try_acquire(1) is True
    assert limiter.try_acquire(2) is True
    assert limiter.try_acquire(1) is False
    assert limiter.try_acquire(2) is False


def test_capacity_must_be_positive():
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=0, refill_per_second=1.0)


def test_refill_must_be_positive():
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=1, refill_per_second=0)


def test_max_keys_must_be_positive():
    with pytest.raises(ValueError):
        TokenBucketLimiter(capacity=1, refill_per_second=1, max_keys=0)


# --- peek -------------------------------------------------------------------


def test_peek_new_key_returns_true():
    limiter, _ = _make()
    assert limiter.peek(99) is True


def test_peek_does_not_mutate_bucket():
    limiter, _ = _make(capacity=3)
    for _ in range(3):
        limiter.try_acquire(1)
    # Repeated peeks while empty stay false and never let try_acquire succeed.
    for _ in range(5):
        assert limiter.peek(1) is False
    assert limiter.try_acquire(1) is False


def test_peek_reflects_refilled_state_without_consuming():
    limiter, clock = _make(capacity=2, refill_per_second=1.0)
    limiter.try_acquire(1)
    limiter.try_acquire(1)  # bucket empty
    assert limiter.peek(1) is False
    clock.advance(1.0)
    assert limiter.peek(1) is True
    # Peek did NOT consume — a subsequent try_acquire still succeeds.
    assert limiter.try_acquire(1) is True
    # And after consuming, peek goes back to False.
    assert limiter.peek(1) is False


# --- LRU eviction -----------------------------------------------------------


def test_evicts_least_recently_used_on_overflow():
    limiter, _ = _make(capacity=1, max_keys=3)
    # Fill three buckets (all exhausted: capacity=1, first acquire consumes it).
    for k in (1, 2, 3):
        limiter.try_acquire(k)
    # Touch 1 so 2 becomes the LRU.
    limiter.peek(1)
    # Inserting 4 evicts 2 (the current LRU).
    limiter.try_acquire(4)
    # 2 was evicted → fresh bucket → first acquire succeeds.
    assert limiter.try_acquire(2) is True
    # 1 is still tracked → still exhausted → denied.
    assert limiter.try_acquire(1) is False


def test_peek_does_not_grow_dict():
    """Peeking unknown keys must not insert (otherwise spam-peeks would OOM)."""
    limiter, _ = _make(capacity=1, max_keys=2)
    for key in range(1000):
        assert limiter.peek(key) is True
    # Only an actual acquire should occupy a slot.
    limiter.try_acquire(99)
    # And the dict is still small enough that a fresh user gets a bucket.
    assert limiter.try_acquire(100) is True


# --- try_acquire_all --------------------------------------------------------


def test_try_acquire_all_success_consumes_from_every_pair():
    a, _ = _make(capacity=2)
    b, _ = _make(capacity=2)
    assert try_acquire_all([(a, 1), (b, 1)]) is None
    # Both buckets debited.
    assert a.peek(1) is True   # one token left
    assert b.peek(1) is True
    assert try_acquire_all([(a, 1), (b, 1)]) is None
    # Now both empty.
    assert a.peek(1) is False
    assert b.peek(1) is False


def test_try_acquire_all_denies_on_first_failing_returns_index():
    a, _ = _make(capacity=1)
    b, _ = _make(capacity=1)
    # Exhaust b only.
    b.try_acquire(1)
    # a is fresh (peek=True), b is empty (peek=False) → deny at index 1.
    assert try_acquire_all([(a, 1), (b, 1)]) == 1
    # a was NOT consumed — fairness guaranteed.
    assert a.peek(1) is True
    assert a.try_acquire(1) is True


def test_try_acquire_all_short_circuits_on_earlier_denial():
    a, _ = _make(capacity=1)
    b, _ = _make(capacity=1)
    a.try_acquire(1)  # a is now empty
    assert try_acquire_all([(a, 1), (b, 1)]) == 0
    # b was never touched — still has its initial token.
    assert b.try_acquire(1) is True


def test_try_acquire_all_empty_input_succeeds():
    assert try_acquire_all([]) is None
