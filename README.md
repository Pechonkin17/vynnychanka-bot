# vynnychanka-bot

Telegram group-chat AI clone ("Vynnychanka") powered by Google Gemini.

The codebase is split into two packages that meet at a single seam:

| Package      | Responsibility                                                        |
|--------------|-----------------------------------------------------------------------|
| `src/bot/`   | **Telegram transport** — aiogram routers, filters, throttling, config |
| `src/brain/` | **The AI clone** — persona (system prompt) + the model backend        |

`bot/` depends only on `brain.contract` (the `ChatBackend` protocol +
`ChatRequest`). It never imports a concrete model. That is what makes the AI
side swappable — Gemini today, a stateful LangGraph pipeline later — without
touching the Telegram side.

## Behaviour

The bot only replies to messages that **address it directly**:

- a message that **replies** to one of the bot's messages, or
- a message that **mentions** the bot via `@username` (or a text mention).

All other group traffic is ignored. The bot is **stateless** — each reply is
computed from the persona + that single message, with no memory of prior turns.

## Configuration

Two files control what the bot says — no code changes required:

| File                             | What lives there                                          |
|----------------------------------|-----------------------------------------------------------|
| `config/persona/vynnychanka.md`  | The **clone's** persona / system prompt.                  |
| `config/messages.toml`           | The bot's own canned replies — `/start`, `/help`, errors. |

`messages.toml` requires a restart. The persona does **not** — admins live-edit
it through Telegram (see *Admin commands*).

Runtime settings come from `.env` (see [`.env.example`](.env.example)):
`BOT_TOKEN`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `PERSONA_PATH`,
`PERSONA_ARCHIVE_DIR`, `MESSAGES_PATH`, `ADMIN_USER_IDS`,
`MAX_USER_TEXT_LENGTH`, `DROP_PENDING_UPDATES`, `RATE_LIMIT_*`, `LOG_LEVEL`.

## Admin commands (configure the clone from your own account)

Sent in a **private DM** with the bot, from a user id listed in
`ADMIN_USER_IDS`:

| Command                    | Effect                                            |
|----------------------------|---------------------------------------------------|
| `/setprompt <text>`        | Replace the persona live; old version archived.   |
| `/currentprompt`           | Show the active persona.                           |
| `/promptversions`          | List archived versions (newest first).            |
| `/rollback latest\|oldest\|N\|<file>` | Restore a previous persona version.    |

## Run

```bash
python -m venv .venv && . .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env    # then fill in BOT_TOKEN and GEMINI_API_KEY
python -m bot.runtime
```

## Test

```bash
pip install -e ".[dev]"
pytest
```

## Docker

```bash
docker build -t vynnychanka-bot .
docker run --env-file .env -v vynnychanka_persona:/app/config/persona vynnychanka-bot
```

## Project layout

```
config/persona/vynnychanka.md   the clone's persona (system prompt)
config/persona/archive/         versioned snapshots (runtime state)
config/messages.toml            the bot's own canned replies
src/bot/                        Telegram layer (transport)
  runtime.py                    entrypoint (lifecycle)
  app.py                        composition root (wires the object graph)
  config.py  messages.py  limits.py  di.py  ratelimit.py  logging_setup.py
  filters/  handlers/  middlewares/  telegram/
src/brain/                      AI layer (the clone)
  contract.py                   ChatBackend protocol + ChatRequest (the seam)
  persona.py                    live persona + versioned archive
  gemini.py                     Gemini implementation of ChatBackend
  retry.py                      exponential-backoff helper
  langgraph.py                  reserved seam for a future stateful backend
tests/                          unit tests
```

## License

Licensed under the [Apache License 2.0](LICENSE). You may use, modify, and
distribute this code, including commercially, provided you retain the copyright
notice and license. The software is provided "as is", without warranty.
