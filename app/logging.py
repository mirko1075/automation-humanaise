"""
Central logging configuration for the application and workers.

Provides `configure_logging()` to be called once at process start.
Respects `LOG_LEVEL` environment variable (default INFO) and ensures
logs are emitted to stdout in the required format.

This module intentionally uses only the standard `logging` library.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Optional


def configure_logging(level_name: Optional[str] = None) -> None:
    """
    Configure root logging for the process.

    Args:
        level_name: Optional override for the logging level name (e.g. 'DEBUG').
    """
    level_str = level_name or os.environ.get("LOG_LEVEL", "INFO")
    level = getattr(logging, level_str.upper(), logging.INFO)

    fmt = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    # Use basicConfig with force to ensure single-source configuration
    # and that handlers write to stdout (suitable for Render and local).
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Ensure common server loggers propagate to root and respect level
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "gunicorn.error", "gunicorn.access"):
        lg = logging.getLogger(logger_name)
        lg.propagate = True
        lg.setLevel(level)

    # Optionally expose the root logger for callers
    logging.getLogger().debug("Logging configured", extra={"level": level_str})
