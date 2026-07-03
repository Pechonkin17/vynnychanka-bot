"""Typed keys for aiogram's workflow-data container.

aiogram passes whatever you stash in ``Dispatcher[key]`` as a keyword argument
to handlers and filters. The keys are stringly-typed, so a typo is only caught
at runtime. Concentrating the keys here gives us one place to grep and one
place to keep names in sync with handler signatures.
"""

from typing import Final

#: Key under which the :class:`~brain.contract.ChatBackend` is registered.
#: Handlers receive it as the ``backend`` keyword argument.
BACKEND: Final[str] = "backend"

#: Key under which :class:`~bot.telegram.identity.BotIdentity` is registered.
#: Handlers and filters receive it as the ``identity`` keyword argument.
IDENTITY: Final[str] = "identity"

#: Key under which :class:`~bot.messages.Messages` is registered.
#: Handlers receive it as the ``messages`` keyword argument.
MESSAGES: Final[str] = "messages"

#: Key under which :class:`~bot.limits.InputLimits` is registered.
#: Handlers receive it as the ``limits`` keyword argument.
LIMITS: Final[str] = "limits"

#: Key under which :class:`~brain.persona.PersonaStore` is registered.
#: Admin handlers receive it as the ``persona_store`` kwarg.
PERSONA_STORE: Final[str] = "persona_store"
