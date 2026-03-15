"""Search tools."""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import debug_tool, get_ctx


@debug_tool()
async def search(ctx: Context, query: str, limit: int = 10) -> list[dict]:
    """Search across all Plex libraries for movies, shows, music, etc."""
    return await get_ctx(ctx).client.search(query, limit)
