"""Composition root: build the object graph (services + dispatcher).

This module wires objects together and nothing else. The *lifecycle* — create
the Bot, resolve its identity, poll, shut down — lives in ``bot.runtime``.
Keeping construction here (with no ``await``) means the wiring can be unit-
tested without a running event loop or a live Telegram token.
"""

from __future__ import annotations

from dataclasses import dataclass

from aiogram import Dispatcher

from bot import di
from bot.config import Settings
from bot.filters.admin import AdminFilter
from bot.handlers.admin import build_admin_router
from bot.handlers.commands import commands_router
from bot.handlers.errors import errors_router
from bot.handlers.group import group_router
from bot.limits import InputLimits
from bot.messages import Messages, load_messages
from bot.middlewares.throttle import ThrottleMiddleware, ThrottleScope
from bot.ratelimit import TokenBucketLimiter
from bot.telegram.identity import BotIdentity
from brain.contract import ChatBackend
from brain.gemini import GeminiBackend
from brain.persona import PersonaStore


@dataclass(frozen=True, slots=True)
class Services:
    """The fully-constructed object graph, minus anything needing an event loop.

    Built once by :func:`build_services`, then handed to
    :func:`build_dispatcher` together with the resolved bot identity.
    """

    messages: Messages
    persona_store: PersonaStore
    limits: InputLimits
    backend: ChatBackend
    throttle: ThrottleMiddleware
    admin_filter: AdminFilter


def build_services(settings: Settings) -> Services:
    """Construct every long-lived collaborator from ``settings``.

    Swapping the AI implementation (e.g. to a future ``LangGraphBackend``) is
    a one-line change here — the rest of the app depends only on
    :class:`~brain.contract.ChatBackend`.
    """
    messages = load_messages(settings.messages_path)
    persona_store = PersonaStore(
        active_path=settings.persona_path,
        archive_dir=settings.persona_archive_dir,
    )
    limits = InputLimits(max_user_text_length=settings.max_user_text_length)
    throttle = _build_throttle(settings, messages)
    backend: ChatBackend = GeminiBackend(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        get_persona=lambda: persona_store.text,
        max_output_tokens=settings.gemini_max_output_tokens,
    )
    admin_filter = AdminFilter(settings.admin_user_ids)
    return Services(
        messages=messages,
        persona_store=persona_store,
        limits=limits,
        backend=backend,
        throttle=throttle,
        admin_filter=admin_filter,
    )


def build_dispatcher(*, services: Services, identity: BotIdentity) -> Dispatcher:
    """Construct the dispatcher and pre-populate workflow data for DI."""
    dp = Dispatcher()
    dp[di.BACKEND] = services.backend
    dp[di.IDENTITY] = identity
    dp[di.MESSAGES] = services.messages
    dp[di.LIMITS] = services.limits
    dp[di.PERSONA_STORE] = services.persona_store

    dp.include_router(errors_router)
    dp.include_router(build_admin_router(services.admin_filter))
    dp.include_router(commands_router)
    # Throttle only the AI-bound group router; /start, /help, admin commands bypass.
    group_router.message.middleware(services.throttle)
    dp.include_router(group_router)
    return dp


def _build_throttle(settings: Settings, messages: Messages) -> ThrottleMiddleware:
    """Assemble the per-user and per-chat throttle scopes."""
    user_limiter = TokenBucketLimiter(
        capacity=settings.rate_limit_user_capacity,
        refill_per_second=settings.rate_limit_user_refill_per_minute / 60.0,
        max_keys=settings.rate_limit_bucket_max_keys,
    )
    chat_limiter = TokenBucketLimiter(
        capacity=settings.rate_limit_chat_capacity,
        refill_per_second=settings.rate_limit_chat_refill_per_minute / 60.0,
        max_keys=settings.rate_limit_bucket_max_keys,
    )
    notice_limiter = TokenBucketLimiter(
        capacity=1,
        refill_per_second=settings.rate_limit_notice_per_minute / 60.0,
        max_keys=settings.rate_limit_bucket_max_keys,
    )
    return ThrottleMiddleware(
        scopes=(
            ThrottleScope(
                name="user",
                limiter=user_limiter,
                key_of=lambda m: m.from_user.id if m.from_user else None,
                deny_message=messages.errors.rate_limit_user,
            ),
            ThrottleScope(
                name="chat",
                limiter=chat_limiter,
                key_of=lambda m: m.chat.id,
                deny_message=messages.errors.rate_limit_chat,
            ),
        ),
        notice_limiter=notice_limiter,
    )
