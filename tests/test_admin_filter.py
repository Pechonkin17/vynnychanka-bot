"""Tests for AdminFilter."""

from __future__ import annotations

import pytest

from bot.filters.admin import AdminFilter
from tests.factories import make_message, make_user


@pytest.fixture
def filt() -> AdminFilter:
    return AdminFilter(allowed_ids=frozenset({42, 99}))


async def test_admin_passes(filt: AdminFilter):
    msg = make_message(text="hi", from_user=make_user(user_id=42))
    assert await filt(msg) is True


async def test_non_admin_denied(filt: AdminFilter):
    msg = make_message(text="hi", from_user=make_user(user_id=7))
    assert await filt(msg) is False


async def test_bot_denied_even_if_id_matches(filt: AdminFilter):
    msg = make_message(text="hi", from_user=make_user(user_id=42, is_bot=True))
    assert await filt(msg) is False


async def test_empty_allowlist_denies_everyone():
    filt = AdminFilter(allowed_ids=frozenset())
    msg = make_message(text="hi", from_user=make_user(user_id=42))
    assert await filt(msg) is False
