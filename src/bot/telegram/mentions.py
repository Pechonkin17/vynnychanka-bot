"""UTF-16-safe helpers for working with Telegram message entities.

Telegram reports entity ``offset`` and ``length`` in UTF-16 code units, while
Python strings are indexed in Unicode code points. Naively slicing a Python
string with those offsets corrupts messages that contain characters outside
the Basic Multilingual Plane (most emoji, some CJK).

These helpers keep all entity-aware operations in one place so the rest of the
codebase never has to think about UTF-16 again.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from aiogram.types import Message, MessageEntity

_UTF16 = "utf-16-le"


@dataclass(frozen=True, slots=True)
class TextPayload:
    """Whatever textual content a message carries, paired with its entities.

    A message can hold text *or* a media caption — both use the same entity
    model. This type lets callers ignore the distinction.
    """

    text: str
    entities: tuple[MessageEntity, ...]

    @classmethod
    def from_message(cls, message: Message) -> "TextPayload":
        text = message.text or message.caption or ""
        entities = message.entities or message.caption_entities or ()
        return cls(text=text, entities=tuple(entities))

    @property
    def is_empty(self) -> bool:
        return not self.text


def slice_entity(text: str, entity: MessageEntity) -> str:
    """Return the substring covered by ``entity``, honouring UTF-16 offsets."""
    encoded = text.encode(_UTF16)
    start = entity.offset * 2
    end = (entity.offset + entity.length) * 2
    return encoded[start:end].decode(_UTF16)


def strip_entities(text: str, entities: Iterable[MessageEntity]) -> str:
    """Return ``text`` with the byte ranges of the given entities removed.

    Operates in UTF-16 space so multi-code-unit characters (emoji etc.) before
    the entities don't shift the cut points.
    """
    ranges = sorted(
        ((e.offset, e.offset + e.length) for e in entities),
        reverse=True,
    )
    if not ranges:
        return text

    encoded = bytearray(text.encode(_UTF16))
    for start, end in ranges:
        del encoded[start * 2 : end * 2]
    return encoded.decode(_UTF16)


def is_bot_mention(
    entity: MessageEntity,
    text: str,
    bot_id: int,
    bot_username: str | None,
) -> bool:
    """Return True iff ``entity`` is a mention that targets the bot.

    Handles both ``mention`` (``@username`` literal) and ``text_mention``
    (mention by user id, used when the target has no public username).
    """
    if entity.type == "mention" and bot_username:
        return slice_entity(text, entity).lower() == f"@{bot_username.lower()}"
    if entity.type == "text_mention" and entity.user is not None:
        return entity.user.id == bot_id
    return False


def bot_mention_entities(
    payload: TextPayload,
    bot_id: int,
    bot_username: str | None,
) -> Sequence[MessageEntity]:
    """Return only the entities that mention the bot, in original order."""
    return tuple(
        e for e in payload.entities
        if is_bot_mention(e, payload.text, bot_id, bot_username)
    )
