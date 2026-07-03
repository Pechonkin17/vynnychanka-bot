"""Loader for the user-facing message catalogue.

All canned replies live in ``config/messages.toml``. Loading is eager and
strict: every documented key MUST be present at startup, so a typo in the file
fails the process immediately instead of surprising a user later.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorMessages:
    """Strings shown to users when something goes wrong."""

    generation_failed: str
    internal_error: str
    message_too_long: str
    rate_limit_user: str
    rate_limit_chat: str
    prompt_empty: str
    prompt_too_long: str           # supports ``{max}`` placeholder
    prompt_corrupt_archive: str


@dataclass(frozen=True, slots=True)
class CommandMessages:
    """Replies to slash commands."""

    start: str
    help: str
    admin_only: str
    setprompt_usage: str
    setprompt_ok: str
    currentprompt_header: str
    promptversions_empty: str
    promptversions_header: str
    promptversions_footer: str
    rollback_usage: str
    rollback_unknown: str
    rollback_ok: str


@dataclass(frozen=True, slots=True)
class Messages:
    """Top-level container for the whole catalogue."""

    errors: ErrorMessages
    commands: CommandMessages


class MessagesFileError(ValueError):
    """Raised when ``messages.toml`` is malformed or missing required keys."""


def load_messages(path: Path) -> Messages:
    """Parse ``path`` (TOML) into a :class:`Messages` instance.

    :raises FileNotFoundError: if the file does not exist.
    :raises MessagesFileError: if the file is malformed or any required key
        is missing / not a string.
    """
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise MessagesFileError(f"{path} is not valid TOML: {exc}") from exc

    return Messages(
        errors=ErrorMessages(
            generation_failed=_require_str(raw, "errors", "generation_failed", path),
            internal_error=_require_str(raw, "errors", "internal_error", path),
            message_too_long=_require_str(raw, "errors", "message_too_long", path),
            rate_limit_user=_require_str(raw, "errors", "rate_limit_user", path),
            rate_limit_chat=_require_str(raw, "errors", "rate_limit_chat", path),
            prompt_empty=_require_str(raw, "errors", "prompt_empty", path),
            prompt_too_long=_require_str(raw, "errors", "prompt_too_long", path),
            prompt_corrupt_archive=_require_str(
                raw, "errors", "prompt_corrupt_archive", path,
            ),
        ),
        commands=CommandMessages(
            start=_require_str(raw, "commands", "start", path),
            help=_require_str(raw, "commands", "help", path),
            admin_only=_require_str(raw, "commands", "admin_only", path),
            setprompt_usage=_require_str(raw, "commands", "setprompt_usage", path),
            setprompt_ok=_require_str(raw, "commands", "setprompt_ok", path),
            currentprompt_header=_require_str(
                raw, "commands", "currentprompt_header", path,
            ),
            promptversions_empty=_require_str(
                raw, "commands", "promptversions_empty", path,
            ),
            promptversions_header=_require_str(
                raw, "commands", "promptversions_header", path,
            ),
            promptversions_footer=_require_str(
                raw, "commands", "promptversions_footer", path,
            ),
            rollback_usage=_require_str(raw, "commands", "rollback_usage", path),
            rollback_unknown=_require_str(
                raw, "commands", "rollback_unknown", path,
            ),
            rollback_ok=_require_str(raw, "commands", "rollback_ok", path),
        ),
    )


def _require_str(raw: dict[str, Any], section: str, key: str, path: Path) -> str:
    value = raw.get(section, {}).get(key)
    if not isinstance(value, str) or not value.strip():
        raise MessagesFileError(
            f"{path}: [{section}].{key} must be a non-empty string"
        )
    return value
