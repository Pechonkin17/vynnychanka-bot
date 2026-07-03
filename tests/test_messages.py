"""Tests for the messages catalogue loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.messages import MessagesFileError, load_messages

_GOOD = """
[errors]
generation_failed = "fail"
internal_error = "boom"
message_too_long = "shorter"
rate_limit_user = "you, slow down"
rate_limit_chat = "chat, slow down"
prompt_empty = "empty"
prompt_too_long = "too long {max}"
prompt_corrupt_archive = "corrupt"

[commands]
start = "hi"
help = "help"
admin_only = "no"
setprompt_usage = "usage"
setprompt_ok = "ok {archive}"
currentprompt_header = "current:"
promptversions_empty = "empty"
promptversions_header = "header"
promptversions_footer = "footer"
rollback_usage = "rb usage"
rollback_unknown = "unknown"
rollback_ok = "ok {restored} {archived}"
"""


def test_loads_all_fields(tmp_path: Path):
    f = tmp_path / "m.toml"
    f.write_text(_GOOD, encoding="utf-8")
    m = load_messages(f)
    assert m.errors.generation_failed == "fail"
    assert m.errors.internal_error == "boom"
    assert m.errors.message_too_long == "shorter"
    assert m.errors.rate_limit_user == "you, slow down"
    assert m.errors.rate_limit_chat == "chat, slow down"
    assert m.errors.prompt_empty == "empty"
    assert m.errors.prompt_too_long == "too long {max}"
    assert m.errors.prompt_corrupt_archive == "corrupt"
    assert m.commands.start == "hi"
    assert m.commands.help == "help"
    assert m.commands.admin_only == "no"
    assert m.commands.setprompt_usage == "usage"
    assert m.commands.setprompt_ok == "ok {archive}"
    assert m.commands.currentprompt_header == "current:"
    assert m.commands.promptversions_empty == "empty"
    assert m.commands.promptversions_header == "header"
    assert m.commands.promptversions_footer == "footer"
    assert m.commands.rollback_usage == "rb usage"
    assert m.commands.rollback_unknown == "unknown"
    assert m.commands.rollback_ok == "ok {restored} {archived}"


def test_missing_key_fails_loud(tmp_path: Path):
    f = tmp_path / "m.toml"
    f.write_text(
        """
[errors]
generation_failed = "fail"
internal_error = "boom"
message_too_long = "shorter"
rate_limit_user = "you, slow down"
rate_limit_chat = "chat, slow down"
prompt_empty = "e"
prompt_too_long = "t {max}"
prompt_corrupt_archive = "c"
[commands]
start = "hi"
admin_only = "no"
setprompt_usage = "usage"
setprompt_ok = "ok {archive}"
currentprompt_header = "current:"
promptversions_empty = "empty"
promptversions_header = "header"
promptversions_footer = "footer"
rollback_usage = "rb usage"
rollback_unknown = "unknown"
rollback_ok = "ok {restored} {archived}"
""",
        encoding="utf-8",
    )
    with pytest.raises(MessagesFileError, match="commands.*help"):
        load_messages(f)


def test_empty_string_fails(tmp_path: Path):
    f = tmp_path / "m.toml"
    f.write_text(_GOOD.replace('"fail"', '"   "'), encoding="utf-8")
    with pytest.raises(MessagesFileError):
        load_messages(f)


def test_non_string_fails(tmp_path: Path):
    f = tmp_path / "m.toml"
    f.write_text(_GOOD.replace('"fail"', "42"), encoding="utf-8")
    with pytest.raises(MessagesFileError):
        load_messages(f)


def test_malformed_toml_fails(tmp_path: Path):
    f = tmp_path / "m.toml"
    f.write_text("this is = not valid = toml", encoding="utf-8")
    with pytest.raises(MessagesFileError):
        load_messages(f)


def test_missing_file_raises_filenotfound(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_messages(tmp_path / "missing.toml")


def test_default_messages_file_is_valid():
    """The shipped config/messages.toml must always load."""
    repo_root = Path(__file__).resolve().parent.parent
    m = load_messages(repo_root / "config" / "messages.toml")
    assert m.errors.generation_failed
    assert m.errors.internal_error
    assert m.errors.message_too_long
    assert m.errors.rate_limit_user
    assert m.errors.rate_limit_chat
    assert m.errors.prompt_empty
    assert m.errors.prompt_too_long
    assert m.errors.prompt_corrupt_archive
    assert m.commands.start
    assert m.commands.help
    assert m.commands.admin_only
    assert m.commands.setprompt_usage
    assert m.commands.setprompt_ok
    assert m.commands.currentprompt_header
    assert m.commands.promptversions_empty
    assert m.commands.promptversions_header
    assert m.commands.promptversions_footer
    assert m.commands.rollback_usage
    assert m.commands.rollback_unknown
    assert m.commands.rollback_ok
