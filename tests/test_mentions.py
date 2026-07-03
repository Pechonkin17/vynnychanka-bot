"""Tests for bot.telegram.mentions — the UTF-16-correctness lives or dies here."""

from __future__ import annotations

from bot.telegram.mentions import (
    TextPayload,
    bot_mention_entities,
    is_bot_mention,
    slice_entity,
    strip_entities,
)
from tests.factories import make_user, utf16_entity


def test_slice_entity_ascii():
    text = "hello @bot world"
    entity = utf16_entity(text, "@bot")
    assert slice_entity(text, entity) == "@bot"


def test_slice_entity_after_surrogate_pair():
    """The classic bug: an emoji before the mention shifts UTF-16 offsets."""
    text = "🙂 @bot hi"
    entity = utf16_entity(text, "@bot")
    assert slice_entity(text, entity) == "@bot"


def test_strip_entities_removes_target_and_keeps_surroundings():
    text = "🙂 @bot please explain"
    entity = utf16_entity(text, "@bot")
    assert strip_entities(text, [entity]).strip() == "🙂  please explain".strip()


def test_strip_entities_multiple_occurrences():
    """Stripping must cope when the same fragment appears more than once."""
    from aiogram.types import MessageEntity

    text = "@bot ping @bot pong"
    encoded = text.encode("utf-16-le")
    fragment = "@bot".encode("utf-16-le")
    first = encoded.find(fragment)
    second = encoded.find(fragment, first + 1)
    entities = [
        MessageEntity(type="mention", offset=first // 2, length=4),
        MessageEntity(type="mention", offset=second // 2, length=4),
    ]
    assert "@bot" not in strip_entities(text, entities)


def test_is_bot_mention_username_match_is_case_insensitive():
    text = "yo @MyBot"
    entity = utf16_entity(text, "@MyBot")
    assert is_bot_mention(entity, text, bot_id=42, bot_username="mybot") is True


def test_is_bot_mention_username_mismatch():
    text = "yo @other"
    entity = utf16_entity(text, "@other")
    assert is_bot_mention(entity, text, bot_id=42, bot_username="mybot") is False


def test_is_bot_mention_text_mention_matches_by_id():
    bot_user = make_user(user_id=42, username=None, is_bot=True)
    text = "hello bot"
    entity = utf16_entity(text, "bot", entity_type="text_mention", user=bot_user)
    assert is_bot_mention(entity, text, bot_id=42, bot_username=None) is True


def test_is_bot_mention_text_mention_wrong_id():
    other = make_user(user_id=99, username=None)
    text = "hello bot"
    entity = utf16_entity(text, "bot", entity_type="text_mention", user=other)
    assert is_bot_mention(entity, text, bot_id=42, bot_username=None) is False


def test_is_bot_mention_other_entity_types_ignored():
    text = "see https://example.com"
    entity = utf16_entity(text, "https://example.com", entity_type="url")
    assert is_bot_mention(entity, text, bot_id=42, bot_username="x") is False


def test_text_payload_is_empty():
    assert TextPayload(text="", entities=()).is_empty
    assert not TextPayload(text="hi", entities=()).is_empty


def test_bot_mention_entities_filters_correctly():
    text = "@mybot ping @somebody"
    mine = utf16_entity(text, "@mybot")
    other = utf16_entity(text, "@somebody")
    payload = TextPayload(text=text, entities=(mine, other))
    result = bot_mention_entities(payload, bot_id=1, bot_username="mybot")
    assert result == (mine,)
