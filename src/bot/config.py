"""Runtime settings, loaded from environment variables / ``.env``."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Repository root — the directory that contains ``src/`` and ``config/``.
#: Used to anchor relative paths so the bot works regardless of the cwd it
#: was launched from. This file lives at ``<root>/src/bot/config.py``, so the
#: root is three parents up.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

_TELEGRAM_TOKEN_RE = re.compile(r"^\d{6,}:[A-Za-z0-9_-]{30,}$")
_MIN_GEMINI_KEY_LENGTH = 30
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class Settings(BaseSettings):
    """Strongly-typed runtime configuration.

    Instantiate once at startup and pass the instance down — there is no
    process-wide singleton so tests can build fresh instances per case.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    bot_token: SecretStr = Field(
        ...,
        alias="BOT_TOKEN",
        description="Telegram bot token from @BotFather (``<id>:<secret>``).",
    )
    gemini_api_key: SecretStr = Field(
        ...,
        alias="GEMINI_API_KEY",
        description="Google AI Studio API key.",
    )
    gemini_model: str = Field("gemini-2.5-flash", alias="GEMINI_MODEL", min_length=1)
    gemini_max_output_tokens: int = Field(
        400,
        alias="GEMINI_MAX_OUTPUT_TOKENS",
        ge=1,
        le=8192,
        description=(
            "Hard cap on the model's reply length (tokens). ~400 ≈ a few short "
            "paragraphs; stops a user coaxing a huge, costly answer."
        ),
    )
    persona_path: Path = Field(
        Path("config/persona/vynnychanka.md"),
        alias="PERSONA_PATH",
        description="Path to the active persona (system prompt) file.",
    )
    messages_path: Path = Field(Path("config/messages.toml"), alias="MESSAGES_PATH")
    max_user_text_length: int = Field(
        4000,
        alias="MAX_USER_TEXT_LENGTH",
        ge=1,
        le=4096,
        description="Reject incoming messages longer than this (code points).",
    )
    drop_pending_updates: bool = Field(
        True,
        alias="DROP_PENDING_UPDATES",
        description=(
            "If true, messages queued at Telegram during downtime are discarded "
            "at startup. Set to false to process the backlog instead."
        ),
    )
    # Rate-limit defaults below are SEED VALUES based on a hobby-scale bot
    # (one Galician group, a few active people). For larger / paid deployments
    # measure real traffic and tune from data, not from this comment.
    rate_limit_user_capacity: int = Field(
        5,
        alias="RATE_LIMIT_USER_CAPACITY",
        ge=1,
        le=100,
        description="Per-user burst limit (tokens). Seed: 5.",
    )
    rate_limit_user_refill_per_minute: float = Field(
        6.0,
        alias="RATE_LIMIT_USER_REFILL_PER_MINUTE",
        gt=0,
        le=600,
        description="Sustained per-user rate, tokens/min. Seed: 6 (≈1 per 10s).",
    )
    rate_limit_chat_capacity: int = Field(
        10,
        alias="RATE_LIMIT_CHAT_CAPACITY",
        ge=1,
        le=500,
        description="Per-chat burst limit (tokens). Seed: 10 (≈2× user cap).",
    )
    rate_limit_chat_refill_per_minute: float = Field(
        15.0,
        alias="RATE_LIMIT_CHAT_REFILL_PER_MINUTE",
        gt=0,
        le=3000,
        description="Sustained per-chat rate, tokens/min. Seed: 15 (≈2.5× user).",
    )
    rate_limit_notice_per_minute: float = Field(
        1.0,
        alias="RATE_LIMIT_NOTICE_PER_MINUTE",
        gt=0,
        le=60,
        description=(
            "How often a single user may receive the rate-limit reply. "
            "Stops 'slow down' from flooding faster than the user."
        ),
    )
    rate_limit_bucket_max_keys: int = Field(
        10_000,
        alias="RATE_LIMIT_BUCKET_MAX_KEYS",
        ge=100,
        le=10_000_000,
        description="LRU cap on the number of tracked users/chats per limiter.",
    )
    # NoDecode: stop pydantic-settings from JSON-parsing the raw env string for
    # this complex-typed field. Without it, `ADMIN_USER_IDS=42,99` (or an empty
    # value) is fed to json.loads and blows up before our validator can run.
    # With it, the raw string reaches ``_parse_admin_ids`` below, which handles
    # both the CSV form and the empty case.
    admin_user_ids: Annotated[frozenset[int], NoDecode] = Field(
        default_factory=frozenset,
        alias="ADMIN_USER_IDS",
        description=(
            "Comma-separated Telegram user IDs allowed to run admin commands "
            "(e.g. /setprompt). Empty disables all admin commands."
        ),
    )
    persona_archive_dir: Path = Field(
        Path("config/persona/archive"),
        alias="PERSONA_ARCHIVE_DIR",
        description="Directory where previous persona versions are snapshotted.",
    )
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    @field_validator("bot_token", mode="before")
    @classmethod
    def _validate_bot_token(cls, value: object) -> str:
        token = str(value)
        if not _TELEGRAM_TOKEN_RE.fullmatch(token):
            # Don't echo the value back — it's a secret even when invalid.
            raise ValueError(
                "bot_token does not look like a Telegram bot token "
                "(expected '<digits>:<>=30-char-secret>')"
            )
        return token

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _validate_gemini_api_key(cls, value: object) -> str:
        key = str(value)
        if len(key) < _MIN_GEMINI_KEY_LENGTH:
            raise ValueError(
                f"gemini_api_key must be at least {_MIN_GEMINI_KEY_LENGTH} characters"
            )
        return key

    @field_validator(
        "persona_path",
        "messages_path",
        "persona_archive_dir",
        mode="after",
    )
    @classmethod
    def _anchor_to_project_root(cls, value: Path) -> Path:
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def _parse_admin_ids(cls, value: object) -> frozenset[int]:
        if value is None or value == "":
            return frozenset()
        if isinstance(value, (list, tuple, set, frozenset)):
            return frozenset(int(x) for x in value)
        if isinstance(value, str):
            return frozenset(
                int(part.strip()) for part in value.split(",") if part.strip()
            )
        raise ValueError(f"unsupported admin_user_ids value: {value!r}")

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> str:
        upper = str(value).upper()
        if upper not in _VALID_LOG_LEVELS:
            raise ValueError(
                f"log_level must be one of {sorted(_VALID_LOG_LEVELS)}, got {value!r}"
            )
        return upper
