"""Tests for AddressedFilter."""

from __future__ import annotations

import pytest

from bot.filters.addressed import AddressedFilter
from bot.telegram.identity import BotIdentity
from tests.factories import make_message, make_user, utf16_entity

BOT = BotIdentity(id=42, username="mybot")


@pytest.fixture
def filt() -> AddressedFilter:
    return AddressedFilter()


async def test_passes_on_reply_to_bot(filt: AddressedFilter):
    bot_msg = make_message(text="prev", from_user=make_user(user_id=BOT.id, is_bot=True))
    msg = make_message(text="thanks", reply_to=bot_msg)
    assert await filt(msg, BOT) is True


async def test_rejects_reply_to_other_user(filt: AddressedFilter):
    other = make_message(text="prev", from_user=make_user(user_id=999))
    msg = make_message(text="thanks", reply_to=other)
    assert await filt(msg, BOT) is False


async def test_passes_on_at_mention(filt: AddressedFilter):
    text = "@mybot please"
    msg = make_message(text=text, entities=[utf16_entity(text, "@mybot")])
    assert await filt(msg, BOT) is True


async def test_passes_on_at_mention_with_emoji_prefix(filt: AddressedFilter):
    text = "🙂 @mybot please"
    msg = make_message(text=text, entities=[utf16_entity(text, "@mybot")])
    assert await filt(msg, BOT) is True


async def test_passes_on_text_mention(filt: AddressedFilter):
    text = "hey mybot"
    bot_user = make_user(user_id=BOT.id, username=None, is_bot=True)
    msg = make_message(
        text=text,
        entities=[utf16_entity(text, "mybot", entity_type="text_mention", user=bot_user)],
    )
    assert await filt(msg, BOT) is True


async def test_rejects_at_mention_of_other_bot(filt: AddressedFilter):
    text = "@somebody ping"
    msg = make_message(text=text, entities=[utf16_entity(text, "@somebody")])
    assert await filt(msg, BOT) is False


async def test_rejects_plain_message(filt: AddressedFilter):
    msg = make_message(text="just chatting")
    assert await filt(msg, BOT) is False


async def test_rejects_empty_message(filt: AddressedFilter):
    msg = make_message(text=None)
    assert await filt(msg, BOT) is False


async def test_works_on_caption(filt: AddressedFilter):
    caption = "@mybot what is this"
    msg = make_message(
        caption=caption,
        caption_entities=[utf16_entity(caption, "@mybot")],
    )
    assert await filt(msg, BOT) is True
