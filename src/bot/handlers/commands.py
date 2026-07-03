"""``/start`` and ``/help`` — minimal courtesy commands."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.messages import Messages

commands_router = Router(name="commands")


@commands_router.message(CommandStart())
async def on_start(message: Message, messages: Messages) -> None:
    await message.answer(messages.commands.start)


@commands_router.message(Command("help"))
async def on_help(message: Message, messages: Messages) -> None:
    await message.answer(messages.commands.help)
