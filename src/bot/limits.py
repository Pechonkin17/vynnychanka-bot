"""Input-validation policy injected into handlers via DI.

Kept as a tiny dataclass — separate from :class:`~bot.config.Settings` so
handlers receive only what they need (no secrets, no paths).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InputLimits:
    """Constraints applied to incoming user messages before they reach the AI."""

    max_user_text_length: int

    def is_too_long(self, text: str) -> bool:
        """Return True iff ``text`` exceeds :attr:`max_user_text_length`."""
        return len(text) > self.max_user_text_length
