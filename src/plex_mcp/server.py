"""FastMCP server instance, lifespan, and write-guard."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP

from .auth import get_or_create_client_id, load_cached_token
from .client import PlexClient
from .config import Settings, load_settings


@dataclass
class AppContext:
    client: PlexClient
    settings: Settings


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Create PlexClient from cached token (auth already done in __main__)."""
    settings = load_settings()
    client_id = get_or_create_client_id(settings.client_id_path)
    token = load_cached_token(settings.token_path)
    if not token:
        raise RuntimeError("No cached token found. Run `plex-mcp` interactively first.")
    client = PlexClient(settings.plex_url, token, client_id, token_path=settings.token_path)
    try:
        yield AppContext(client=client, settings=settings)
    finally:
        await client.close()


mcp = FastMCP("Plex MCP Server", lifespan=app_lifespan)


def get_ctx(ctx) -> AppContext:
    """Extract AppContext from the MCP request context."""
    return ctx.request_context.lifespan_context


def require_write(ctx) -> None:
    """Raise ValueError if the server is in read-only mode."""
    app = get_ctx(ctx)
    if app.settings.read_only:
        raise ValueError(
            "This operation requires write access. "
            "Set PLEX_READ_ONLY=false in your .env to enable write operations."
        )


# Import tools after mcp is defined to avoid circular imports
from . import tools  # noqa: E402, F401
