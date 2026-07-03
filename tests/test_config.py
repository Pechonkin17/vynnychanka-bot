"""Tests for Settings validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from bot.config import PROJECT_ROOT, Settings

_VALID_TOKEN = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
_VALID_GEMINI_KEY = "AIzaXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"  # 39 chars


def _settings(**overrides: object) -> Settings:
    defaults = dict(
        BOT_TOKEN=_VALID_TOKEN,
        GEMINI_API_KEY=_VALID_GEMINI_KEY,
    )
    defaults.update(overrides)  # type: ignore[arg-type]
    return Settings(_env_file=None, **defaults)  # type: ignore[call-arg]


# --- log_level ---------------------------------------------------------------


def test_log_level_defaults_to_info():
    assert _settings().log_level == "INFO"


def test_log_level_is_uppercased():
    assert _settings(LOG_LEVEL="debug").log_level == "DEBUG"


def test_log_level_rejects_bogus_value():
    with pytest.raises(ValidationError, match="log_level"):
        _settings(LOG_LEVEL="BOGUS")


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_log_level_accepts_each_canonical(level: str):
    assert _settings(LOG_LEVEL=level).log_level == level


# --- bot_token ---------------------------------------------------------------


def test_bot_token_accepts_valid():
    s = _settings()
    assert s.bot_token.get_secret_value() == _VALID_TOKEN


@pytest.mark.parametrize(
    "bad_token",
    [
        "short",  # nowhere near the right shape
        "1234567890",  # numeric only, no colon
        "abcdef:ghijklmnopqrstuvwxyz1234567890",  # non-numeric id
        "123:short",  # secret too short
        "12345:" + "A" * 30,  # id too short
    ],
)
def test_bot_token_rejects_malformed(bad_token: str):
    with pytest.raises(ValidationError):
        _settings(BOT_TOKEN=bad_token)


# --- gemini_api_key ----------------------------------------------------------


def test_gemini_api_key_rejects_short_value():
    with pytest.raises(ValidationError):
        _settings(GEMINI_API_KEY="short")


# --- max_user_text_length ----------------------------------------------------


def test_max_user_text_length_defaults_to_4000():
    assert _settings().max_user_text_length == 4000


def test_gemini_max_output_tokens_default_and_bounds():
    assert _settings().gemini_max_output_tokens == 400
    with pytest.raises(ValidationError):
        _settings(GEMINI_MAX_OUTPUT_TOKENS=0)
    with pytest.raises(ValidationError):
        _settings(GEMINI_MAX_OUTPUT_TOKENS=99999)


def test_max_user_text_length_rejects_zero():
    with pytest.raises(ValidationError):
        _settings(MAX_USER_TEXT_LENGTH=0)


def test_max_user_text_length_rejects_over_telegram_limit():
    with pytest.raises(ValidationError):
        _settings(MAX_USER_TEXT_LENGTH=5000)


# --- path resolution ---------------------------------------------------------


def test_relative_paths_anchored_to_project_root():
    s = _settings(
        PERSONA_PATH="config/persona/vynnychanka.md",
        MESSAGES_PATH="config/messages.toml",
    )
    assert s.persona_path == (PROJECT_ROOT / "config/persona/vynnychanka.md").resolve()
    assert s.messages_path == (PROJECT_ROOT / "config/messages.toml").resolve()
    assert s.persona_path.is_absolute()
    assert s.messages_path.is_absolute()


def test_absolute_path_preserved(tmp_path: Path):
    f = tmp_path / "elsewhere.md"
    f.write_text("x", encoding="utf-8")
    s = _settings(PERSONA_PATH=str(f))
    assert s.persona_path == f


# --- drop_pending_updates ----------------------------------------------------


def test_drop_pending_updates_defaults_to_true():
    assert _settings().drop_pending_updates is True


@pytest.mark.parametrize("truthy", ["true", "True", "1", "yes", "on"])
def test_drop_pending_updates_truthy_values(truthy: str):
    assert _settings(DROP_PENDING_UPDATES=truthy).drop_pending_updates is True


@pytest.mark.parametrize("falsy", ["false", "False", "0", "no", "off"])
def test_drop_pending_updates_falsy_values(falsy: str):
    assert _settings(DROP_PENDING_UPDATES=falsy).drop_pending_updates is False


def test_drop_pending_updates_rejects_garbage():
    with pytest.raises(ValidationError):
        _settings(DROP_PENDING_UPDATES="maybe")


# --- rate limiter ------------------------------------------------------------


def test_rate_limit_defaults():
    s = _settings()
    assert s.rate_limit_user_capacity == 5
    assert s.rate_limit_user_refill_per_minute == 6.0
    assert s.rate_limit_chat_capacity == 10
    assert s.rate_limit_chat_refill_per_minute == 15.0
    assert s.rate_limit_notice_per_minute == 1.0
    assert s.rate_limit_bucket_max_keys == 10_000


def test_rate_limit_notice_must_be_positive():
    with pytest.raises(ValidationError):
        _settings(RATE_LIMIT_NOTICE_PER_MINUTE=0)


def test_rate_limit_notice_rejects_excessive():
    with pytest.raises(ValidationError):
        _settings(RATE_LIMIT_NOTICE_PER_MINUTE=1000)


def test_rate_limit_bucket_max_keys_too_small():
    with pytest.raises(ValidationError):
        _settings(RATE_LIMIT_BUCKET_MAX_KEYS=1)


# --- admin user IDs ----------------------------------------------------------


def test_admin_user_ids_default_empty():
    assert _settings().admin_user_ids == frozenset()


def test_admin_user_ids_parses_csv():
    s = _settings(ADMIN_USER_IDS="42,  99, 1001")
    assert s.admin_user_ids == frozenset({42, 99, 1001})


def test_admin_user_ids_accepts_empty_string():
    s = _settings(ADMIN_USER_IDS="")
    assert s.admin_user_ids == frozenset()


def test_admin_user_ids_rejects_non_integer():
    with pytest.raises(ValidationError):
        _settings(ADMIN_USER_IDS="42,abc")


def test_admin_user_ids_dedupes():
    s = _settings(ADMIN_USER_IDS="7,7,7,8")
    assert s.admin_user_ids == frozenset({7, 8})


def test_admin_user_ids_parsed_from_dotenv_csv(tmp_path: Path):
    """Regression: frozenset field must load from a real .env (dotenv source),
    not just from init kwargs. Without NoDecode this raised a SettingsError."""
    env = tmp_path / ".env"
    env.write_text(
        f"BOT_TOKEN={_VALID_TOKEN}\n"
        f"GEMINI_API_KEY={_VALID_GEMINI_KEY}\n"
        "ADMIN_USER_IDS=42,99\n",
        encoding="utf-8",
    )
    s = Settings(_env_file=str(env))  # type: ignore[call-arg]
    assert s.admin_user_ids == frozenset({42, 99})


def test_admin_user_ids_empty_in_dotenv(tmp_path: Path):
    """Regression: an empty ADMIN_USER_IDS= line in .env must yield an empty
    set, not crash json.loads('')."""
    env = tmp_path / ".env"
    env.write_text(
        f"BOT_TOKEN={_VALID_TOKEN}\n"
        f"GEMINI_API_KEY={_VALID_GEMINI_KEY}\n"
        "ADMIN_USER_IDS=\n",
        encoding="utf-8",
    )
    s = Settings(_env_file=str(env))  # type: ignore[call-arg]
    assert s.admin_user_ids == frozenset()


# --- persona archive dir -----------------------------------------------------


def test_persona_archive_dir_anchored_to_project_root():
    s = _settings()
    assert s.persona_archive_dir.is_absolute()
    assert s.persona_archive_dir == (PROJECT_ROOT / "config/persona/archive").resolve()


@pytest.mark.parametrize(
    "key",
    ["RATE_LIMIT_USER_CAPACITY", "RATE_LIMIT_CHAT_CAPACITY"],
)
def test_rate_limit_capacity_rejects_zero(key: str):
    with pytest.raises(ValidationError):
        _settings(**{key: 0})


@pytest.mark.parametrize(
    "key,bad",
    [
        ("RATE_LIMIT_USER_CAPACITY", 10_000),
        ("RATE_LIMIT_CHAT_CAPACITY", 100_000),
    ],
)
def test_rate_limit_capacity_rejects_excessive(key: str, bad: int):
    with pytest.raises(ValidationError):
        _settings(**{key: bad})


@pytest.mark.parametrize(
    "key",
    ["RATE_LIMIT_USER_REFILL_PER_MINUTE", "RATE_LIMIT_CHAT_REFILL_PER_MINUTE"],
)
def test_rate_limit_refill_must_be_positive(key: str):
    with pytest.raises(ValidationError):
        _settings(**{key: 0})


@pytest.mark.parametrize(
    "key,bad",
    [
        ("RATE_LIMIT_USER_REFILL_PER_MINUTE", 10_000),
        ("RATE_LIMIT_CHAT_REFILL_PER_MINUTE", 100_000),
    ],
)
def test_rate_limit_refill_rejects_excessive(key: str, bad: int):
    with pytest.raises(ValidationError):
        _settings(**{key: bad})
