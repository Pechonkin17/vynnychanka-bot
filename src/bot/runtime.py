"""Entrypoint: load settings, configure logging, run the bot lifecycle.

Composition (building the object graph) lives in ``bot.app``; this module owns
the runtime lifecycle — creating the Bot, resolving its identity, polling, and
tearing everything down cleanly on exit.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot

from bot import app
from bot.config import Settings
from bot.logging_setup import configure_logging
from bot.telegram.identity import BotIdentity

logger = logging.getLogger(__name__)


async def _run(settings: Settings) -> None:
    services = app.build_services(settings)
    bot = Bot(token=settings.bot_token.get_secret_value())

    try:
        identity = await BotIdentity.resolve(bot)
        logger.info(
            "Starting bot @%s (id=%s); admins=%d",
            identity.username,
            identity.id,
            len(settings.admin_user_ids),
        )
        dp = app.build_dispatcher(services=services, identity=identity)
        await dp.start_polling(
            bot,
            drop_pending_updates=settings.drop_pending_updates,
        )
    finally:
        await services.backend.aclose()
        await bot.session.close()
        logger.info("Bot stopped")


def main() -> None:
    """Synchronous entrypoint — read settings, configure logging, run."""
    settings = Settings()
    configure_logging(settings.log_level)
    # User hit Ctrl-C — exit cleanly without a stack trace.
    # SystemExit is intentionally NOT suppressed: explicit sys.exit(code) must propagate.
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_run(settings))


if __name__ == "__main__":
    main()
