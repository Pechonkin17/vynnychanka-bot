FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install from the project metadata (no separate requirements.txt). setuptools
# discovers packages under src/, so the sources must be present before install.
COPY pyproject.toml ./
COPY src/ ./src/
COPY config/ ./config/
RUN pip install .

# Ensure the persona archive directory exists and is writable by the bot user.
RUN mkdir -p /app/config/persona/archive

RUN useradd --create-home --uid 1000 bot \
 && chown -R bot:bot /app
USER bot

# The persona (active file + archive) is runtime state. Mount a host directory
# or a named volume here, or live edits via /setprompt and the entire archive
# WILL be lost on every container restart.
#   docker run -v vynnychanka_persona:/app/config/persona vynnychanka-bot
VOLUME ["/app/config/persona"]

CMD ["python", "-m", "bot.runtime"]
