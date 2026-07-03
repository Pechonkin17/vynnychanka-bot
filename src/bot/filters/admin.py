"""Filter that admits only messages from a configured admin allow-list."""

from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import Message


class AdminFilter(Filter):
    """Pass iff ``message.from_user.id`` is in the allow-list.

    Bot users and anonymous messages are rejected. If the allow-list is
    empty, no one passes — which deliberately makes admin commands unusable
    when not configured.
    """

    def __init__(self, allowed_ids: frozenset[int]) -> None:
        self._allowed = allowed_ids

    async def __call__(self, message: Message) -> bool:
        user = message.from_user
        return user is not None and not user.is_bot and user.id in self._allowed
