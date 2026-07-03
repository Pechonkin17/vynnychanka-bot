"""Bot self-identity, resolved once at startup."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot


@dataclass(frozen=True, slots=True)
class BotIdentity:
    """The bot's own user id and username, captured once.

    Resolving this at startup avoids ``await bot.me()`` on every incoming
    update and keeps the rest of the codebase free of I/O for identity lookups.
    """

    id: int
    username: str | None

    @classmethod
    async def resolve(cls, bot: Bot) -> BotIdentity:
        me = await bot.me()
        return cls(id=me.id, username=me.username)
