"""Tests for PersonaStore — verifies archive rotation and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.persona import (
    EmptyPromptError,
    InvalidArchiveEncodingError,
    PersonaStore,
    PromptTooLongError,
    UnknownArchiveError,
    _archive_sort_key,
    _atomic_write_text,
)


def _make(tmp_path: Path, initial: str = "first") -> PersonaStore:
    active = tmp_path / "persona.md"
    active.write_text(initial, encoding="utf-8")
    archive = tmp_path / "archive"
    return PersonaStore(active_path=active, archive_dir=archive)


def test_loads_initial_text(tmp_path: Path):
    store = _make(tmp_path, initial="hello world")
    assert store.text == "hello world"


def test_update_archives_old_and_writes_new(tmp_path: Path):
    store = _make(tmp_path, initial="version one")

    archive_path = store.update("version two", author_id=42)

    assert store.text == "version two"
    assert (tmp_path / "persona.md").read_text(encoding="utf-8") == "version two"
    assert archive_path.exists()
    assert archive_path.read_text(encoding="utf-8") == "version one"
    assert archive_path.parent == tmp_path / "archive"


def test_multiple_updates_create_distinct_archives(tmp_path: Path):
    store = _make(tmp_path, initial="v1")
    a = store.update("v2", author_id=1)
    b = store.update("v3", author_id=1)
    c = store.update("v4", author_id=1)
    assert {a, b, c} == set([a, b, c])  # all distinct
    assert a.read_text(encoding="utf-8") == "v1"
    assert b.read_text(encoding="utf-8") == "v2"
    assert c.read_text(encoding="utf-8") == "v3"
    assert store.text == "v4"


def test_update_rejects_empty(tmp_path: Path):
    store = _make(tmp_path)
    with pytest.raises(EmptyPromptError):
        store.update("   \n\t  ", author_id=1)
    # Active file untouched.
    assert store.text == "first"


def test_update_rejects_over_max(tmp_path: Path):
    store = _make(tmp_path)
    with pytest.raises(PromptTooLongError) as exc_info:
        store.update("x" * (PersonaStore.MAX_LENGTH + 1), author_id=1)
    assert exc_info.value.limit == PersonaStore.MAX_LENGTH


def test_update_strips_whitespace(tmp_path: Path):
    store = _make(tmp_path)
    store.update("  padded body  \n", author_id=1)
    assert store.text == "padded body"


def test_archive_dir_created_lazily(tmp_path: Path):
    store = _make(tmp_path)
    archive_dir = tmp_path / "archive"
    assert not archive_dir.exists()
    store.update("anything", author_id=1)
    assert archive_dir.is_dir()


# --- list_archives ----------------------------------------------------------


def test_list_archives_empty_when_no_archive_dir(tmp_path: Path):
    store = _make(tmp_path)
    assert store.list_archives() == []


def test_list_archives_newest_first(tmp_path: Path):
    store = _make(tmp_path, initial="v1")
    store.update("v2", author_id=1)
    store.update("v3", author_id=1)
    store.update("v4", author_id=1)
    archives = store.list_archives()
    assert len(archives) == 3
    # Archive filenames are ISO timestamps → lexicographic == chronological,
    # and reverse=True puts newest first.
    assert archives == sorted(archives, key=lambda p: p.name, reverse=True)


def test_list_archives_chronological_within_same_second(tmp_path: Path):
    """Regression: same-second updates must still list newest-first.

    Two rapid updates that fall in the same wall-clock second land in
    differently-named archives that MUST sort chronologically.
    """
    store = _make(tmp_path, initial="v1")
    a = store.update("v2", author_id=1)  # archives v1
    b = store.update("v3", author_id=1)  # archives v2
    c = store.update("v4", author_id=1)  # archives v3

    archives = store.list_archives()
    assert archives == [c, b, a]  # newest-first

    # Sanity: contents match the version that WAS archived.
    assert a.read_text(encoding="utf-8") == "v1"
    assert b.read_text(encoding="utf-8") == "v2"
    assert c.read_text(encoding="utf-8") == "v3"


def test_list_archives_respects_limit(tmp_path: Path):
    store = _make(tmp_path, initial="v1")
    for i in range(2, 6):
        store.update(f"v{i}", author_id=1)
    assert len(store.list_archives()) == 4
    assert len(store.list_archives(limit=2)) == 2


def test_list_archives_ignores_unrelated_files(tmp_path: Path):
    store = _make(tmp_path, initial="v1")
    store.update("v2", author_id=1)
    (tmp_path / "archive" / "stray.txt").write_text("garbage", encoding="utf-8")
    (tmp_path / "archive" / "system-bogus.txt").write_text(
        "wrong extension", encoding="utf-8",
    )
    archives = store.list_archives()
    assert all(p.name.startswith("system-") and p.name.endswith(".md") for p in archives)


# --- rollback ---------------------------------------------------------------


def test_rollback_restores_content_and_archives_current(tmp_path: Path):
    store = _make(tmp_path, initial="v1")
    archive_v1 = store.update("v2", author_id=1)
    # Now active=v2, archive contains v1.

    archived_current, restored_from = store.rollback(archive_v1.name, author_id=99)

    assert store.text == "v1"
    assert (tmp_path / "persona.md").read_text(encoding="utf-8") == "v1"
    assert restored_from == archive_v1
    # The outgoing v2 must now exist as a fresh archive.
    assert archived_current.read_text(encoding="utf-8") == "v2"
    assert archived_current != archive_v1


def test_rollback_rejects_unknown_name(tmp_path: Path):
    store = _make(tmp_path)
    with pytest.raises(UnknownArchiveError):
        store.rollback("system-9999.md", author_id=1)


def test_rollback_blocks_path_traversal(tmp_path: Path):
    store = _make(tmp_path, initial="v1")
    store.update("v2", author_id=1)
    with pytest.raises(UnknownArchiveError):
        store.rollback("../persona.md", author_id=1)


def test_rollback_rejects_empty_archive(tmp_path: Path):
    store = _make(tmp_path, initial="v1")
    store.update("v2", author_id=1)
    archives = store.list_archives()
    archives[0].write_text("   ", encoding="utf-8")
    with pytest.raises(EmptyPromptError):
        store.rollback(archives[0].name, author_id=1)


def test_rollback_rejects_non_utf8_archive(tmp_path: Path):
    """Corrupt archive (invalid UTF-8) must raise a typed error, not crash."""
    store = _make(tmp_path, initial="v1")
    store.update("v2", author_id=1)
    archives = store.list_archives()
    # Write invalid UTF-8 (lone surrogate / invalid continuation byte).
    archives[0].write_bytes(b"\xff\xfe\xfd not valid utf-8")
    with pytest.raises(InvalidArchiveEncodingError) as exc_info:
        store.rollback(archives[0].name, author_id=1)
    assert exc_info.value.name == archives[0].name
    # Active prompt must NOT have changed.
    assert store.text == "v2"


# --- atomic write -----------------------------------------------------------


def test_atomic_write_replaces_file_contents(tmp_path: Path):
    target = tmp_path / "x.md"
    target.write_text("old", encoding="utf-8")
    _atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_write_leaves_no_tempfile(tmp_path: Path):
    target = tmp_path / "x.md"
    _atomic_write_text(target, "content")
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_atomic_write_preserves_old_on_simulated_crash(tmp_path: Path, monkeypatch):
    """If os.replace fails, the active file is untouched AND the tempfile
    is cleaned up (so the next call doesn't see a stale .tmp)."""
    from brain import persona as persona_mod

    target = tmp_path / "x.md"
    target.write_text("old", encoding="utf-8")

    def boom(*_a, **_kw):
        raise RuntimeError("simulated kernel hiccup")

    monkeypatch.setattr(persona_mod.os, "replace", boom)
    with pytest.raises(RuntimeError):
        _atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "old"
    assert not (tmp_path / "x.md.tmp").exists()


# --- archive sort key (parsed, robust against runaway counter) ---------------


def test_archive_sort_key_parses_filename():
    p = Path("system-20260630T103725Z_0042.md")
    assert _archive_sort_key(p) == ("20260630T103725Z", 42)


def test_archive_sort_key_orders_correctly_beyond_zero_pad_width():
    """Regression: lexicographic '_999' < '_1000', but parsed sort works."""
    names = [
        "system-20260630T103725Z_0009.md",
        "system-20260630T103725Z_0010.md",
        "system-20260630T103725Z_0999.md",
        "system-20260630T103725Z_1000.md",
        "system-20260630T103725Z_9999.md",
    ]
    paths = [Path(n) for n in names]
    # Sort ASCENDING — parsed key gives chronological order.
    sorted_paths = sorted(paths, key=_archive_sort_key)
    assert [p.name for p in sorted_paths] == names


def test_archive_sort_key_handles_malformed_name():
    p = Path("system-garbage.md")
    # Just confirm it doesn't blow up.
    _archive_sort_key(p)
