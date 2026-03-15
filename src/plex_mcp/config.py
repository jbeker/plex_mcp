"""Settings loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


VALID_TRANSPORTS = ("stdio", "sse", "streamable-http")


@dataclass
class Settings:
    plex_url: str
    read_only: bool = True
    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000
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

    transport = os.environ.get("PLEX_TRANSPORT", "stdio").lower()
    if transport not in VALID_TRANSPORTS:
        raise RuntimeError(
            f"Invalid PLEX_TRANSPORT={transport!r}. Must be one of: {', '.join(VALID_TRANSPORTS)}"
        )

    host = os.environ.get("PLEX_HOST", "127.0.0.1")
    port = int(os.environ.get("PLEX_PORT", "8000"))

    return Settings(
        plex_url=plex_url,
        read_only=read_only,
        transport=transport,
        host=host,
        port=port,
    )
