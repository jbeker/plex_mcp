"""FastMCP server instance, lifespan, and write-guard."""

from __future__ import annotations

import functools
import inspect
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import Context, FastMCP

from .auth import get_or_create_client_id, load_cached_token
from .client import PlexClient
from .config import Settings, load_settings

logger = logging.getLogger("plex_mcp")


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
    client = PlexClient(
        settings.plex_url, token, client_id,
        token_path=settings.token_path,
        debug=settings.debug,
    )
    try:
        yield AppContext(client=client, settings=settings)
    finally:
        await client.close()


def create_mcp(host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    """Create and return a configured FastMCP instance."""
    server = FastMCP("Plex MCP Server", lifespan=app_lifespan, host=host, port=port)

    # Register tools by importing the tools package.
    # Tools reference `mcp` via get_mcp(), so set the module-level
    # reference before importing.
    global mcp
    mcp = server
    from . import tools  # noqa: F401

    return server


# Module-level reference used by tool modules — set by create_mcp()
mcp: FastMCP = None  # type: ignore[assignment]


def get_mcp() -> FastMCP:
    """Get the active FastMCP instance (for use by tool modules)."""
    if mcp is None:
        raise RuntimeError("MCP server not initialized. Call create_mcp() first.")
    return mcp


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


def _debug_wrap(fn):
    """Wrap a tool function to log its call arguments and return value."""
    sig = inspect.signature(fn)
    param_names = [
        name for name, p in sig.parameters.items()
        if p.annotation is not Context and name not in ("ctx", "context")
    ]

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        # Extract the context to check debug setting
        ctx = None
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        for name, val in bound.arguments.items():
            if isinstance(val, Context):
                ctx = val
                break

        debug = False
        if ctx:
            try:
                debug = get_ctx(ctx).settings.debug
            except Exception:
                pass

        if not debug:
            return await fn(*args, **kwargs)

        # Log tool call with arguments
        call_args = {
            name: bound.arguments[name]
            for name in param_names
            if name in bound.arguments
        }
        logger.debug(
            "TOOL CALL >>> %s(%s)",
            fn.__name__,
            json.dumps(call_args, indent=2, default=str),
        )

        try:
            result = await fn(*args, **kwargs)
        except Exception as exc:
            logger.debug(
                "TOOL ERROR <<< %s: %s: %s",
                fn.__name__,
                type(exc).__name__,
                exc,
            )
            raise

        logger.debug(
            "TOOL RESULT <<< %s -> %s",
            fn.__name__,
            json.dumps(result, indent=2, default=str),
        )
        return result

    return wrapper


def debug_tool(**tool_kwargs):
    """Register a tool on the MCP server with debug logging wrapped around it."""
    def decorator(fn):
        wrapped = _debug_wrap(fn)
        return mcp.tool(**tool_kwargs)(wrapped)
    return decorator
