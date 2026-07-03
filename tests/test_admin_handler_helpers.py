"""Tests for the small helpers used by bot.handlers.admin.

Not a full handler integration test — those would require simulating aiogram
plumbing. These cover the standalone functions that decide what a command
should do.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from bot.handlers.admin import _read_first_line, _resolve_rollback_target
from brain.persona import PersonaStore


def _store(tmp_path: Path) -> PersonaStore:
    (tmp_path / "persona.md").write_text("v1", encoding="utf-8")
    s = PersonaStore(active_path=tmp_path / "persona.md", archive_dir=tmp_path / "archive")
    for i in range(2, 5):  # creates 3 archives
        s.update(f"v{i}", author_id=1)
    return s


# --- _resolve_rollback_target ------------------------------------------------


def test_resolve_latest_returns_newest_archive(tmp_path: Path):
    s = _store(tmp_path)
    archives = s.list_archives()
    assert _resolve_rollback_target("latest", s) == archives[0].name


def test_resolve_oldest_returns_earliest_archive(tmp_path: Path):
    s = _store(tmp_path)
    archives = s.list_archives()
    assert _resolve_rollback_target("oldest", s) == archives[-1].name


def test_resolve_is_case_insensitive_for_shortcuts(tmp_path: Path):
    s = _store(tmp_path)
    assert _resolve_rollback_target("LATEST", s) == _resolve_rollback_target("latest", s)


@pytest.mark.parametrize("n,index", [(1, 0), (2, 1), (3, 2)])
def test_resolve_integer_picks_by_position(tmp_path: Path, n: int, index: int):
    s = _store(tmp_path)
    archives = s.list_archives()
    assert _resolve_rollback_target(str(n), s) == archives[index].name


def test_resolve_integer_out_of_range_returns_none(tmp_path: Path):
    s = _store(tmp_path)
    assert _resolve_rollback_target("99", s) is None
    assert _resolve_rollback_target("0", s) is None  # 1-indexed


def test_resolve_passes_unknown_filename_through(tmp_path: Path):
    s = _store(tmp_path)
    # Non-shortcut, non-digit text is returned as-is so the store can
    # reject it with UnknownArchiveError.
    assert _resolve_rollback_target("system-bogus.md", s) == "system-bogus.md"


def test_resolve_returns_none_when_no_archives(tmp_path: Path):
    (tmp_path / "persona.md").write_text("only", encoding="utf-8")
    empty = PersonaStore(
        active_path=tmp_path / "persona.md", archive_dir=tmp_path / "archive",
    )
    assert _resolve_rollback_target("latest", empty) is None
    assert _resolve_rollback_target("1", empty) is None


# --- _read_first_line --------------------------------------------------------


def test_read_first_line_returns_first_non_empty_line(tmp_path: Path):
    p = tmp_path / "x.md"
    p.write_text("\n\n  hello world  \nsecond\n", encoding="utf-8")
    assert _read_first_line(p, width=80) == "hello world"


def test_read_first_line_truncates_with_ellipsis(tmp_path: Path):
    p = tmp_path / "x.md"
    p.write_text("a" * 200, encoding="utf-8")
    line = _read_first_line(p, width=10)
    assert line == "a" * 10 + "…"


def test_read_first_line_returns_empty_on_decode_failure(tmp_path: Path):
    p = tmp_path / "x.md"
    p.write_bytes(b"\xff\xfe not utf-8")
    assert _read_first_line(p, width=80) == ""


def test_read_first_line_returns_empty_on_missing_file(tmp_path: Path):
    assert _read_first_line(tmp_path / "missing.md", width=80) == ""


def test_read_first_line_returns_empty_for_blank_file(tmp_path: Path):
    p = tmp_path / "x.md"
    p.write_text("\n\n   \n\n", encoding="utf-8")
    assert _read_first_line(p, width=80) == ""
