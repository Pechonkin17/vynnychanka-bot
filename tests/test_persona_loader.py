"""Tests for the persona loader (brain.persona.load_persona)."""

from __future__ import annotations

from pathlib import Path

import pytest

from brain.persona import load_persona


def test_loads_and_strips_whitespace(tmp_path: Path):
    f = tmp_path / "p.md"
    f.write_text("  hello  \n", encoding="utf-8")
    assert load_persona(f) == "hello"


def test_raises_on_empty_file(tmp_path: Path):
    f = tmp_path / "p.md"
    f.write_text("   \n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_persona(f)


def test_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_persona(tmp_path / "missing.md")
