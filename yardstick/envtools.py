"""Central .env loader. Use this everywhere instead of calling load_dotenv directly.

`override=True` makes the repo's .env authoritative over any variable already
exported in the shell, important because a stale value in ~/.zshrc (e.g. an old
GROQ_API_KEY) otherwise silently wins and causes confusing auth failures.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = REPO_ROOT / ".env"


def load_env() -> None:
    """Load REPO_ROOT/.env, overriding any pre-existing shell environment values."""
    load_dotenv(ENV_PATH, override=True)


def first_line(exc: BaseException) -> str:
    """First line of an exception message, or the type name if the message is empty.
    Avoids `str(e).splitlines()[0]` crashing on exceptions with no message (e.g. IndexError)."""
    s = str(exc).strip()
    return s.splitlines()[0] if s else type(exc).__name__


def require(name: str) -> str:
    """Return an env var's value or raise a clear error if missing."""
    load_env()
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"{name} is not set. Add it to {ENV_PATH} "
            f"(copy .env.example if needed) and try again."
        )
    return val
