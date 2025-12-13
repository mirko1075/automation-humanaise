# app/__init__.py

"""
App package initialization.

Expose package version constant so other modules and scripts can read
the application version programmatically (e.g. `from app import __version__`).

The package reads the top-level `VERSION` file at import time when available
so releases can be bumped by editing a single file. If the `VERSION` file
is missing, a sensible default is used.
"""

from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_version_file = _root / "VERSION"
if _version_file.exists():
	__version__ = _version_file.read_text(encoding="utf-8").strip()
else:
	__version__ = "0.0.0"

