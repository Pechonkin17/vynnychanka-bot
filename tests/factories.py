"""Test helpers: build aiogram model instances without hitting Telegram."""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram.types import Chat, Message, MessageEntity, User


def make_user(*, user_id: int = 1, username: str | None = "alice", is_bot: bool = False) -> User:
    return User(id=user_id, is_bot=is_bot, first_name="A", username=username)


def make_chat(*, chat_id: int = -100123, chat_type: str = "supergroup") -> Chat:
    return Chat(id=chat_id, type=chat_type)


def utf16_entity(
    text: str,
    fragment: str,
    *,
    entity_type: str = "mention",
    user: User | None = None,
) -> MessageEntity:
    """Build a MessageEntity for ``fragment`` inside ``text`` with correct UTF-16 offsets."""
    encoded = text.encode("utf-16-le")
    fragment_encoded = fragment.encode("utf-16-le")
    byte_offset = encoded.find(fragment_encoded)
    if byte_offset < 0:
        raise AssertionError(f"{fragment!r} not in {text!r}")
    if byte_offset % 2:
        raise AssertionError("UTF-16 fragment did not start on a code unit boundary")
    return MessageEntity(
        type=entity_type,
        offset=byte_offset // 2,
        length=len(fragment_encoded) // 2,
        user=user,
    )


def make_message(
    *,
    text: str | None = None,
    caption: str | None = None,
    entities: list[MessageEntity] | None = None,
    caption_entities: list[MessageEntity] | None = None,
    reply_to: Message | None = None,
    from_user: User | None = None,
    chat: Chat | None = None,
) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=chat or make_chat(),
        from_user=from_user or make_user(),
        text=text,
        caption=caption,
        entities=entities,
        caption_entities=caption_entities,
        reply_to_message=reply_to,
    )
