"""aiogram middleware that enforces an arbitrary list of throttling scopes."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.ratelimit import TokenBucketLimiter, try_acquire_all

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ThrottleScope:
    """One dimension of throttling.

    Bundles three things that always travel together:
      * the :class:`TokenBucketLimiter` doing the counting,
      * a ``key_of`` extractor returning the bucket key for a given message
        (return ``None`` to skip this scope for that message),
      * the user-facing deny message specific to this scope.

    Examples: per-user, per-chat, per-org, per-IP — add another scope to
    extend.
    """

    name: str
    limiter: TokenBucketLimiter
    key_of: Callable[[Message], int | None]
    deny_message: str


class ThrottleMiddleware(BaseMiddleware):
    """Reject messages that would exceed any of a sequence of throttle scopes.

    All scopes are checked first (peek); only if every scope has a token
    available is anything consumed. This guarantees fairness — a single
    saturated scope cannot burn tokens from the others.

    The deny REPLY is itself rate-limited per user via ``notice_limiter``,
    so a flooding user receives at most one ``rate_limit_*`` message per the
    configured window instead of one per spam attempt.

    Mounted on a router so it scopes to that router's messages only.
    Non-message events, messages without ``from_user``, and other bots'
    messages bypass throttling entirely.
    """

    def __init__(
        self,
        *,
        scopes: Sequence[ThrottleScope],
        notice_limiter: TokenBucketLimiter,
    ) -> None:
        if not scopes:
            raise ValueError("at least one ThrottleScope is required")
        self._scopes: tuple[ThrottleScope, ...] = tuple(scopes)
        self._notice_limiter = notice_limiter

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        user = event.from_user
        if user is None or user.is_bot:
            return await handler(event, data)

        # Build the (scope, key) pairs, skipping any scope whose extractor
        # returns None for this message.
        active: list[tuple[ThrottleScope, int]] = []
        for scope in self._scopes:
            key = scope.key_of(event)
            if key is None:
                continue
            active.append((scope, key))

        if not active:
            return await handler(event, data)

        denied_index = try_acquire_all([(s.limiter, k) for s, k in active])
        if denied_index is None:
            return await handler(event, data)

        denied_scope, _ = active[denied_index]
        logger.info(
            "Rate-limited (%s) user=%s chat=%s",
            denied_scope.name,
            user.id,
            event.chat.id,
        )
        await self._maybe_notify(event, user.id, denied_scope.deny_message)
        return None

    async def _maybe_notify(
        self,
        event: Message,
        user_id: int,
        deny_message: str,
    ) -> None:
        if not self._notice_limiter.try_acquire(user_id):
            return  # already told this user recently — stay silent
        try:
            await event.reply(deny_message)
        except Exception:  # noqa: BLE001 — best-effort notice
            logger.exception(
                "Failed to send rate-limit notice to %s",
                event.chat.id,
            )
