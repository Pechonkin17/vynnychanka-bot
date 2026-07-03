"""Admin-only commands: live-edit the clone's persona (system prompt).

All commands here are restricted to private DMs with the bot (so an admin's
screen-share during a group chat doesn't leak the persona) AND to user IDs
listed in :envvar:`ADMIN_USER_IDS`. A non-admin who knows the command name
gets a polite refusal instead of silence — silence would be confusing in DM.

This is the "configure the clone from my own Telegram account" surface: send
``/setprompt <text>`` from an admin account and the clone's behaviour changes
immediately, no restart, with every previous version archived.
"""

from __future__ import annotations

import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message

from bot.filters.admin import AdminFilter
from bot.messages import Messages
from brain.persona import (
    EmptyPromptError,
    InvalidArchiveEncodingError,
    PersonaStore,
    PromptTooLongError,
    UnknownArchiveError,
)

logger = logging.getLogger(__name__)

#: How many archives /promptversions shows at most.
_MAX_VERSIONS_SHOWN = 30
#: First-line snippet width per archive in /promptversions.
_SNIPPET_WIDTH = 80
#: If the active persona exceeds this, /currentprompt sends it as a file
#: instead of trying to fit it into a single Telegram reply (~4096 chars).
_INLINE_PROMPT_THRESHOLD = 3500


def build_admin_router(admin_filter: AdminFilter) -> Router:
    """Construct the admin router with the supplied allow-list bound in."""
    router = Router(name="admin")
    router.message.filter(F.chat.type == ChatType.PRIVATE)

    @router.message(Command("setprompt"), admin_filter)
    async def on_setprompt(
        message: Message,
        command: CommandObject,
        persona_store: PersonaStore,
        messages: Messages,
    ) -> None:
        body = (command.args or "").strip()
        if not body:
            await message.reply(messages.commands.setprompt_usage)
            return
        try:
            archive_path = persona_store.update(
                body,
                author_id=_author_id(message),
            )
        except EmptyPromptError:
            await message.reply(messages.errors.prompt_empty)
            return
        except PromptTooLongError as exc:
            await message.reply(messages.errors.prompt_too_long.format(max=exc.limit))
            return
        await message.reply(
            messages.commands.setprompt_ok.format(archive=archive_path.name)
        )

    @router.message(Command("currentprompt"), admin_filter)
    async def on_currentprompt(
        message: Message,
        persona_store: PersonaStore,
        messages: Messages,
    ) -> None:
        text = persona_store.text
        header = messages.commands.currentprompt_header
        if len(text) <= _INLINE_PROMPT_THRESHOLD:
            await message.reply(header)
            await message.reply(text)
            return
        document = BufferedInputFile(
            text.encode("utf-8"),
            filename="persona-current.md",
        )
        await message.reply_document(document, caption=header)

    @router.message(Command("promptversions"), admin_filter)
    async def on_promptversions(
        message: Message,
        persona_store: PersonaStore,
        messages: Messages,
    ) -> None:
        all_archives = persona_store.list_archives()
        if not all_archives:
            await message.reply(messages.commands.promptversions_empty)
            return
        shown = all_archives[:_MAX_VERSIONS_SHOWN]
        lines = [messages.commands.promptversions_header]
        for path in shown:
            lines.append(f"• {path.name}")
            snippet = _read_first_line(path, _SNIPPET_WIDTH)
            if snippet:
                lines.append(f"  └ {snippet}")
        if len(all_archives) > _MAX_VERSIONS_SHOWN:
            lines.append(f"(ще {len(all_archives) - _MAX_VERSIONS_SHOWN} не показую)")
        lines.append("")
        lines.append(messages.commands.promptversions_footer)
        await message.reply("\n".join(lines))

    @router.message(Command("rollback"), admin_filter)
    async def on_rollback(
        message: Message,
        command: CommandObject,
        persona_store: PersonaStore,
        messages: Messages,
    ) -> None:
        arg = (command.args or "").strip()
        if not arg:
            await message.reply(messages.commands.rollback_usage)
            return
        target = _resolve_rollback_target(arg, persona_store)
        if target is None:
            await message.reply(messages.commands.rollback_unknown)
            return
        try:
            archived, restored = persona_store.rollback(
                target,
                author_id=_author_id(message),
            )
        except UnknownArchiveError:
            await message.reply(messages.commands.rollback_unknown)
            return
        except InvalidArchiveEncodingError:
            await message.reply(messages.errors.prompt_corrupt_archive)
            return
        except EmptyPromptError:
            await message.reply(messages.errors.prompt_empty)
            return
        except PromptTooLongError as exc:
            await message.reply(messages.errors.prompt_too_long.format(max=exc.limit))
            return
        await message.reply(
            messages.commands.rollback_ok.format(
                restored=restored.name,
                archived=archived.name,
            )
        )

    # Catch-alls for non-admins. Registered AFTER the admin-gated handlers
    # so authorized admins still hit those first.
    @router.message(
        Command(commands=["setprompt", "currentprompt", "promptversions", "rollback"])
    )
    async def on_admin_only(message: Message, messages: Messages) -> None:
        await message.reply(messages.commands.admin_only)

    return router


def _author_id(message: Message) -> int:
    """Pull the author id; the admin filter guarantees ``from_user`` exists."""
    assert message.from_user is not None  # admin_filter already verified
    return message.from_user.id


def _resolve_rollback_target(arg: str, store: PersonaStore) -> str | None:
    """Resolve ``arg`` to an archive filename.

    Supports three shorthands plus literal filename:
      * ``latest``  — newest archive
      * ``oldest``  — earliest archive
      * ``N``       — 1-indexed position from newest (1 == latest)
      * anything else — passed through as a filename for the store to check
    """
    archives = store.list_archives()
    if not archives:
        return None
    lowered = arg.lower()
    if lowered == "latest":
        return archives[0].name
    if lowered == "oldest":
        return archives[-1].name
    if arg.isdigit():
        index = int(arg) - 1
        if 0 <= index < len(archives):
            return archives[index].name
        return None
    return arg


def _read_first_line(path: Path, width: int) -> str:
    """Return the file's first non-empty line trimmed to ``width`` chars.

    Errors (missing file, decode failure) yield an empty string — caller may
    skip the snippet rather than show a misleading one.
    """
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if line:
                    return line[:width] + ("…" if len(line) > width else "")
        return ""
    except (OSError, UnicodeDecodeError):
        return ""
