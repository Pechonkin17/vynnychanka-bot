"""Outbound-message helpers for Telegram's hard limits.

Telegram rejects any ``sendMessage`` whose text exceeds 4096 UTF-16 code
units with ``message is too long``. A reply that trips this raises inside the
handler and the user sees nothing, so we clip defensively before sending.
"""

from __future__ import annotations

#: Telegram's maximum message length, in UTF-16 code units. A send above this
#: fails. Telegram counts length in UTF-16 units, not Python code points, so a
#: reply full of emoji (each 2 units) can breach the limit well before
#: ``len(text)`` would suggest.
TELEGRAM_MESSAGE_LIMIT = 4096

_ELLIPSIS = "…"  # U+2026: a single UTF-16 code unit
_UTF16 = "utf-16-le"


def _utf16_len(text: str) -> int:
    """Length of ``text`` in UTF-16 code units — what Telegram actually counts."""
    return len(text.encode(_UTF16)) // 2


def clip_to_telegram_limit(
    text: str,
    *,
    limit: int = TELEGRAM_MESSAGE_LIMIT,
) -> str:
    """Return ``text`` unchanged if it fits, else truncated with an ellipsis.

    Length is measured in UTF-16 code units (as Telegram does), so the guard
    holds even for emoji-heavy replies. The primary defence against long
    replies is the model's own ``max_output_tokens`` cap; this is the
    belt-and-suspenders guard so a send can never fail on length regardless of
    what the model returns.
    """
    if _utf16_len(text) <= limit:
        return text
    # Cut on a UTF-16 code-unit boundary, reserving one unit for the ellipsis.
    # ``errors="ignore"`` drops a trailing lone surrogate if the cut lands in
    # the middle of a surrogate pair (a non-BMP char), so we never emit a
    # broken character.
    cut = (limit - 1) * 2
    clipped = text.encode(_UTF16)[:cut].decode(_UTF16, errors="ignore").rstrip()
    return clipped + _ELLIPSIS
