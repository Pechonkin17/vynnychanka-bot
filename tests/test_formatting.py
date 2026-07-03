"""Tests for the Telegram outbound-length clip."""

from __future__ import annotations

from bot.telegram.formatting import (
    TELEGRAM_MESSAGE_LIMIT,
    clip_to_telegram_limit,
)


def test_short_text_unchanged():
    assert clip_to_telegram_limit("hello") == "hello"


def test_text_exactly_at_limit_unchanged():
    text = "a" * TELEGRAM_MESSAGE_LIMIT
    assert clip_to_telegram_limit(text) == text


def test_over_limit_is_truncated_with_ellipsis():
    text = "a" * (TELEGRAM_MESSAGE_LIMIT + 500)
    out = clip_to_telegram_limit(text)
    assert len(out) <= TELEGRAM_MESSAGE_LIMIT
    assert out.endswith("…")


def test_custom_limit():
    assert clip_to_telegram_limit("abcdef", limit=4) == "abc…"
