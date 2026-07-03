"""Gemini-backed implementation of :class:`~brain.contract.ChatBackend`."""

from __future__ import annotations

import logging
from collections.abc import Callable

from google import genai
from google.genai import types

from brain.contract import ChatBackend, ChatBackendError, ChatRequest
from brain.retry import retry_async

logger = logging.getLogger(__name__)


class GeminiBackend(ChatBackend):
    """Calls Google Gemini via the ``google-genai`` async client.

    The persona (system prompt) is resolved through a ``get_persona`` callable
    on every request, so an admin updating it at runtime takes effect
    immediately without a restart. The compiled
    :class:`~google.genai.types.GenerateContentConfig` is cached and rebuilt
    only when the persona string changes.

    Stateless by design: :meth:`reply` reads only ``request.text``. The other
    fields on :class:`ChatRequest` are ignored today and become the hooks for
    memory later — a change that will not touch ``bot/``.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        get_persona: Callable[[], str],
        max_output_tokens: int = 400,
        max_attempts: int = 3,
        base_backoff: float = 1.0,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._get_persona = get_persona
        self._max_output_tokens = max_output_tokens
        self._cached_text: str | None = None
        self._cached_config: types.GenerateContentConfig | None = None
        self._max_attempts = max_attempts
        self._base_backoff = base_backoff

    async def reply(self, request: ChatRequest) -> str:
        """Return Gemini's reply to ``request.text``.

        Retries transient backend errors with exponential backoff. An empty
        response counts as a failure for retry purposes.

        :raises ChatBackendError: if no usable response is produced after
            ``max_attempts`` tries.
        """
        try:
            return await retry_async(
                lambda: self._call_once(request.text),
                attempts=self._max_attempts,
                base_backoff=self._base_backoff,
                name="gemini.generate_content",
            )
        except Exception as exc:
            raise ChatBackendError("AI backend did not return a usable response") from exc

    async def _call_once(self, user_text: str) -> str:
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=user_text,
            config=self._current_config(),
        )
        text = (response.text or "").strip()
        if not text:
            raise ChatBackendError("empty response from Gemini")
        return text

    def _current_config(self) -> types.GenerateContentConfig:
        text = self._get_persona()
        if text != self._cached_text:
            self._cached_config = types.GenerateContentConfig(
                system_instruction=text,
                max_output_tokens=self._max_output_tokens,
                # Disable "thinking": gemini-2.5-flash spends reasoning tokens
                # from the SAME max_output_tokens budget, so a low cap can be
                # fully consumed by thinking and return an empty answer. A
                # persona chat bot needs no chain-of-thought — send it all to
                # the reply. (2.5-flash supports budget 0; 2.5-pro does not.)
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            self._cached_text = text
        # mypy: _cached_config is non-None here because the branch above ran
        # at least once (on first call) when _cached_text was None.
        assert self._cached_config is not None
        return self._cached_config

    async def aclose(self) -> None:
        """Best-effort release of the genai client's HTTP resources.

        The exact close API varies between ``google-genai`` versions, so this
        accepts either a sync ``close()`` or an async ``aclose()`` and
        silently no-ops if neither is exposed.
        """
        for name in ("aclose", "close"):
            method = getattr(self._client, name, None)
            if not callable(method):
                continue
            result = method()
            if hasattr(result, "__await__"):
                await result
            return
