"""Handler for addressed messages in group chats."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction, ChatType
from aiogram.types import Message

from bot.filters.addressed import AddressedFilter
from bot.limits import InputLimits
from bot.messages import Messages
from bot.telegram.formatting import clip_to_telegram_limit
from bot.telegram.identity import BotIdentity
from bot.telegram.mentions import (
    TextPayload,
    bot_mention_entities,
    strip_entities,
)
from brain.contract import ChatBackend, ChatBackendError, ChatRequest

logger = logging.getLogger(__name__)

group_router = Router(name="group")
group_router.message.filter(
    F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP})
)


@group_router.message(AddressedFilter())
async def handle_addressed_message(
    message: Message,
    bot: Bot,
    backend: ChatBackend,
    identity: BotIdentity,
    messages: Messages,
    limits: InputLimits,
) -> None:
    """Strip the bot's own mention from the message, then ask the backend."""
    user_text = _extract_user_text(message, identity)
    if not user_text:
        return

    if limits.is_too_long(user_text):
        await message.reply(messages.errors.message_too_long)
        return

    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)

    request = ChatRequest(
        text=user_text,
        chat_id=message.chat.id,
        user_id=message.from_user.id if message.from_user else 0,
    )
    try:
        reply = await backend.reply(request)
    except ChatBackendError:
        logger.exception("Backend failed for chat %s", message.chat.id)
        await message.reply(messages.errors.generation_failed)
        return

    await message.reply(clip_to_telegram_limit(reply))


def _extract_user_text(message: Message, identity: BotIdentity) -> str:
    """Return the user-facing text with the bot's own mentions removed."""
    payload = TextPayload.from_message(message)
    mentions = bot_mention_entities(payload, identity.id, identity.username)
    return strip_entities(payload.text, mentions).strip()
