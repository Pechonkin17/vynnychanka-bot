"""One-shot logging configuration."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str) -> None:
    """Configure the root logger to write a single-line format to stdout.

    Safe to call more than once: subsequent calls are no-ops, so importing
    this module from tests will not duplicate handlers.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())

    # aiogram is chatty at INFO; downgrade its event loop noise.
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
