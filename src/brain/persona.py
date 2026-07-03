"""The clone's persona: its live system prompt plus a versioned on-disk archive.

The persona *is* the system prompt — the text that makes the bot behave like
"Vynnychanka". Admins live-edit it through Telegram (see
``bot.handlers.admin``); every edit is snapshotted so nothing is ever lost.

The *active* persona lives at ``active_path`` (e.g.
``config/persona/vynnychanka.md``). Every update snapshots the outgoing text
into ``archive_dir`` with a UTC-timestamped filename, then atomically replaces
the active file with the new text. Old versions are kept forever — no
automatic pruning.

Atomicity:
  * The new active content is written to a tempfile, fsync'd, then renamed
    over the active file with :func:`os.replace`. A crash mid-write cannot
    leave the active file partial or empty.
  * The OUTGOING persona is archived BEFORE the atomic rename. A crash
    between the archive and the rename leaves the active file unchanged
    and the archive intact (cosmetically duplicated on retry; never lost).

Concurrency: safe under a single asyncio event loop (no awaits inside any
method). Not safe across processes — only one bot instance should write to
the same persona directory.

Errors all derive from :class:`PersonaStoreError` and inherit from
:class:`ValueError`, so callers that catch ``ValueError`` keep working but
new callers can route on specific subclasses.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

#: Archive snapshots keep the ``system-*`` prefix — they are point-in-time
#: copies of the system prompt, independent of the active file's name.
_ARCHIVE_GLOB = "system-*.md"


def load_persona(path: Path) -> str:
    """Read and return the trimmed contents of the persona file.

    :raises FileNotFoundError: if the file does not exist.
    :raises ValueError: if the file is empty after trimming whitespace.
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Persona file at {path} is empty")
    return text


class PersonaStoreError(ValueError):
    """Base class for persona-store validation failures."""


class EmptyPromptError(PersonaStoreError):
    """Raised when a candidate persona is empty after trimming."""


class PromptTooLongError(PersonaStoreError):
    """Raised when a candidate persona exceeds :attr:`PersonaStore.MAX_LENGTH`."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"persona must be at most {limit} characters")
        self.limit = limit


class UnknownArchiveError(PersonaStoreError):
    """Raised when a requested archive filename can't be found."""

    def __init__(self, name: str) -> None:
        super().__init__(f"unknown archive: {name}")
        self.name = name


class InvalidArchiveEncodingError(PersonaStoreError):
    """Raised when an archive can't be decoded as UTF-8."""

    def __init__(self, name: str) -> None:
        super().__init__(f"archive {name} is not valid UTF-8")
        self.name = name


class PersonaStore:
    """Owner of the live persona and its on-disk archive."""

    MAX_LENGTH = 8000  # generous; Telegram input is capped at 4096 anyway

    def __init__(self, active_path: Path, archive_dir: Path) -> None:
        self._active_path = active_path
        self._archive_dir = archive_dir
        self._text = load_persona(active_path)

    @property
    def text(self) -> str:
        """The currently active persona (already trimmed)."""
        return self._text

    def list_archives(self, *, limit: int | None = None) -> list[Path]:
        """Return archive snapshots sorted newest-first.

        Order is determined by parsing ``(timestamp, counter)`` out of the
        filename, so it survives a runaway counter (e.g. >9999 archives in
        one second) without depending on zero-pad width.
        """
        if not self._archive_dir.is_dir():
            return []
        archives = sorted(
            self._archive_dir.glob(_ARCHIVE_GLOB),
            key=_archive_sort_key,
            reverse=True,
        )
        return archives[:limit] if limit is not None else archives

    def rollback(self, archive_name: str, *, author_id: int) -> tuple[Path, Path]:
        """Restore the content of ``archive_name`` as the active persona.

        The current active persona is archived first (so a rollback is itself
        undoable).

        :returns: ``(archived_current, restored_from)`` — the path the old
            active was snapshotted to, and the archive that was restored.
        :raises UnknownArchiveError: if the name isn't a real archive file or
            points outside the archive directory.
        :raises InvalidArchiveEncodingError: if the archive isn't UTF-8.
        :raises EmptyPromptError / PromptTooLongError: if the archive's
            content fails validation (e.g. archive was corrupted to empty).
        """
        candidate = self._resolve_archive(archive_name)
        try:
            content = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise InvalidArchiveEncodingError(candidate.name) from exc
        archived_current = self.update(content, author_id=author_id)
        logger.info(
            "Rolled back to %s by user=%s (current archived as %s)",
            candidate.name,
            author_id,
            archived_current.name,
        )
        return archived_current, candidate

    def update(self, new_text: str, *, author_id: int) -> Path:
        """Snapshot the outgoing persona, atomically swap the active file.

        :returns: filesystem path to the archived snapshot of the OLD persona.
        :raises EmptyPromptError: if ``new_text`` is empty after trimming.
        :raises PromptTooLongError: if ``new_text`` exceeds :attr:`MAX_LENGTH`.
        """
        cleaned = new_text.strip()
        if not cleaned:
            raise EmptyPromptError("persona must not be empty")
        if len(cleaned) > self.MAX_LENGTH:
            raise PromptTooLongError(self.MAX_LENGTH)

        self._archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = self._archive_path()
        archive_path.write_text(self._text, encoding="utf-8")
        _atomic_write_text(self._active_path, cleaned)
        self._text = cleaned

        logger.info(
            "Persona updated by user=%s (archive=%s, length=%d)",
            author_id,
            archive_path.name,
            len(cleaned),
        )
        return archive_path

    def _resolve_archive(self, name: str) -> Path:
        """Validate ``name`` and return the absolute archive path, or raise."""
        # Block path traversal: the candidate must resolve to a real file
        # *inside* archive_dir, regardless of what tricks the input plays.
        candidate = (self._archive_dir / name).resolve()
        try:
            candidate.relative_to(self._archive_dir.resolve())
        except ValueError:
            raise UnknownArchiveError(name) from None
        if not candidate.is_file():
            raise UnknownArchiveError(name)
        return candidate

    def _archive_path(self) -> Path:
        # Always include a counter. Combined with parsed-key sort, this
        # gives correct chronological ordering even when many updates land
        # in the same wall-clock second.
        ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        counter = 1
        while True:
            candidate = self._archive_dir / f"system-{ts}_{counter:04d}.md"
            if not candidate.exists():
                return candidate
            counter += 1


def _atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically and durably.

    A crash mid-write leaves ``path`` either unchanged or fully replaced;
    never empty or partial. Tempfile is cleaned up on any failure so the
    next call doesn't see (or overwrite) a stale tempfile from last time.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _archive_sort_key(path: Path) -> tuple[str, int]:
    """Parse ``system-{ts}_{counter}.md`` into ``(ts, counter)`` for sorting.

    Returns a fallback key for malformed names so the sort never blows up.
    """
    stem = path.stem  # 'system-{ts}_{counter}'
    if not stem.startswith("system-"):
        return (stem, 0)
    rest = stem[len("system-") :]
    ts, _, counter_str = rest.rpartition("_")
    if not ts or not counter_str:
        return (rest, 0)
    try:
        return (ts, int(counter_str))
    except ValueError:
        return (rest, 0)
