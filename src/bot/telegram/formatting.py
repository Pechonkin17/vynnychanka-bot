"""Outbound-message helpers for Telegram's hard limits.

Telegram rejects any ``sendMessage`` whose text exceeds 4096 UTF-16 code
units with ``message is too long``. A reply that trips this raises inside the
handler and the user sees nothing, so we clip defensively before sending.
"""

from __future__ import annotations

#: Telegram's maximum message length (characters). A send above this fails.
TELEGRAM_MESSAGE_LIMIT = 4096

_ELLIPSIS = "…"


def clip_to_telegram_limit(
    text: str, *, limit: int = TELEGRAM_MESSAGE_LIMIT,
) -> str:
    """Return ``text`` unchanged if it fits, else truncated with an ellipsis.

    The primary defence against long replies is the model's own
    ``max_output_tokens`` cap; this is the belt-and-suspenders guard so a send
    can never fail on length regardless of what the model returns.
    """
    if len(text) <= limit:
        return text
    return text[: limit - len(_ELLIPSIS)].rstrip() + _ELLIPSIS
