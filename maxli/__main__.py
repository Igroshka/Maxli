"""Точка входа: ``python -m maxli``."""

from __future__ import annotations

import sys

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MIN_PYTHON = (3, 10)

if sys.version_info < MIN_PYTHON:
    print(
        f"Maxli requires Python {'.'.join(map(str, MIN_PYTHON))} or newer, "
        f"you have {sys.version.split()[0]}"
    )
    sys.exit(1)

try:
    import pymax  # noqa: F401
except ImportError:
    print("PyMax is not installed. Run: pip install -U maxapi-python")
    sys.exit(1)

from .main import maxli  # noqa: E402

if __name__ == "__main__":
    maxli.main()
