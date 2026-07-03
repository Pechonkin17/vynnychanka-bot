"""Abstract chat-backend contract — the seam between ``bot/`` and ``brain/``.

The Telegram layer depends on :class:`ChatBackend`, never on a concrete
provider, so the model behind the clone (Gemini today, a LangGraph memory
pipeline tomorrow) can be swapped without touching ``bot/``.

The contract is deliberately *request-shaped* rather than a bare string: even
though the bot is stateless today, ``chat_id`` / ``user_id`` already flow
through it, so conversation memory can be added later without changing a
single line in the Telegram layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class ChatBackendError(RuntimeError):
    """Raised when the backend cannot produce a usable response.

    All concrete backends MUST translate transport- and provider-specific
    failures into this exception so callers have a single thing to catch.
    """


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """One user turn, plus the context a stateful backend will eventually need.

    Today only :attr:`text` is consumed. :attr:`chat_id` and :attr:`user_id`
    are carried now so that adding per-chat memory later is a change confined
    to ``brain/`` — the Telegram handler already supplies them.
    """

    text: str
    chat_id: int
    user_id: int


@runtime_checkable
class ChatBackend(Protocol):
    """Generates a reply for a single user turn.

    Implementations are expected to be safe to call concurrently. Anything
    stateful (conversation history, rate limiting) is the implementation's
    responsibility — this contract is intentionally minimal.
    """

    async def reply(self, request: ChatRequest) -> str:
        """Return a non-empty reply for ``request`` or raise.

        :raises ChatBackendError: if no usable response could be produced
            (after the implementation's own retry policy is exhausted).
        """

    async def aclose(self) -> None:
        """Release any underlying network resources."""
