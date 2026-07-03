"""Global error router — last line of defence against unhandled exceptions."""

from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.types import ErrorEvent

from bot.messages import Messages

logger = logging.getLogger(__name__)

errors_router = Router(name="errors")


@errors_router.error()
async def on_error(event: ErrorEvent, bot: Bot, messages: Messages) -> bool:
    """Log the exception and try to send a generic apology to the chat.

    Reply failures are swallowed: the global error handler must not raise,
    or aiogram will log the cascade and we lose the original cause.

    Returns ``True`` so aiogram stops further error propagation.
    """
    update_id = event.update.update_id if event.update else None
    logger.exception("Unhandled exception (update=%s): %s", update_id, event.exception)

    chat_id = _chat_id_from(event)
    if chat_id is not None:
        try:
            await bot.send_message(chat_id, messages.errors.internal_error)
        except Exception:  # noqa: BLE001 — best-effort apology
            logger.exception("Failed to send internal_error apology to %s", chat_id)

    return True


def _chat_id_from(event: ErrorEvent) -> int | None:
    update = event.update
    if update is None:
        return None
    if update.message and update.message.chat:
        return update.message.chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    return None
