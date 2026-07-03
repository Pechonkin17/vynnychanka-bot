"""Tests for InputLimits."""

from __future__ import annotations

from bot.limits import InputLimits


def test_within_limit_is_not_too_long():
    limits = InputLimits(max_user_text_length=10)
    assert limits.is_too_long("0123456789") is False


def test_exactly_at_limit_is_not_too_long():
    limits = InputLimits(max_user_text_length=10)
    assert limits.is_too_long("a" * 10) is False


def test_over_limit_is_too_long():
    limits = InputLimits(max_user_text_length=10)
    assert limits.is_too_long("a" * 11) is True
