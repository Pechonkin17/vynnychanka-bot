#!/bin/sh
# Seed the persona volume on first run.
#
# config/persona is a Docker VOLUME (runtime state). A named volume is populated
# from the image only the first time it is created; a *bind mount* to an empty
# host directory is never populated at all — and then PersonaStore crashes at
# startup because the active persona file is missing. To make both cases work,
# we copy a pristine default into place if (and only if) no active persona
# exists yet. An existing persona (live edits, archive) is never touched.
set -e

PERSONA_FILE="${PERSONA_PATH:-config/persona/vynnychanka.md}"
case "$PERSONA_FILE" in
    /*) target="$PERSONA_FILE" ;;
    *)  target="/app/$PERSONA_FILE" ;;
esac

if [ ! -f "$target" ]; then
    echo "[entrypoint] no persona at $target — seeding baked-in default"
    mkdir -p "$(dirname "$target")"
    cp /app/persona-default.md "$target" || echo "[entrypoint] WARN: could not seed persona (is the volume writable by uid 1000?)"
fi

exec "$@"