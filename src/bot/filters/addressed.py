"""Filter that admits only messages addressed to the bot."""

from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message

from bot.telegram.identity import BotIdentity
from bot.telegram.mentions import TextPayload, is_bot_mention


class AddressedFilter(Filter):
    """Pass iff the message either replies to the bot or @-mentions it.

    The bot's identity is injected (resolved once at startup), so this filter
    does no I/O. Both ``mention`` (``@username``) and ``text_mention``
    (mention-by-id) entities are recognised.
    """

    async def __call__(self, message: Message, identity: BotIdentity) -> bool:
        if self._is_reply_to_bot(message, identity.id):
            return True

        payload = TextPayload.from_message(message)
        if payload.is_empty:
            return False

        return any(
            is_bot_mention(e, payload.text, identity.id, identity.username)
            for e in payload.entities
        )

    @staticmethod
    def _is_reply_to_bot(message: Message, bot_id: int) -> bool:
        reply = message.reply_to_message
        return (
            reply is not None
            and reply.from_user is not None
            and reply.from_user.id == bot_id
        )
