"""Settings loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Settings:
    plex_url: str
    read_only: bool = True
    token_path: Path = field(default_factory=lambda: Path(".plex_token"))
    client_id_path: Path = field(default_factory=lambda: Path(".plex_client_id"))


def load_settings() -> Settings:
    """Load settings from environment variables (with .env support)."""
    load_dotenv()

    plex_url = os.environ.get("PLEX_URL", "").rstrip("/")
    if not plex_url:
        raise RuntimeError(
            "PLEX_URL is not set. Copy .env.example to .env and configure it."
        )

    read_only = os.environ.get("PLEX_READ_ONLY", "true").lower() in ("true", "1", "yes")

    return Settings(plex_url=plex_url, read_only=read_only)
