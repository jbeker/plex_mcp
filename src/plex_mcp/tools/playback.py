"""Playback session and history tools."""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import get_ctx, mcp, require_write


@mcp.tool()
async def get_active_sessions(ctx: Context) -> list[dict]:
    """Get currently active playback sessions on the Plex server."""
    return await get_ctx(ctx).client.get_active_sessions()


@mcp.tool()
async def get_history(ctx: Context, offset: int = 0, limit: int = 50) -> dict:
    """Get playback history. Returns paginated results with totalSize, offset, and items."""
    return await get_ctx(ctx).client.get_history(offset, limit)


@mcp.tool()
async def mark_played(ctx: Context, rating_key: str) -> str:
    """Mark an item as played (scrobble). Requires write access."""
    require_write(ctx)
    await get_ctx(ctx).client.mark_played(rating_key)
    return f"Marked {rating_key} as played."


@mcp.tool()
async def mark_unplayed(ctx: Context, rating_key: str) -> str:
    """Mark an item as unplayed (unscrobble). Requires write access."""
    require_write(ctx)
    await get_ctx(ctx).client.mark_unplayed(rating_key)
    return f"Marked {rating_key} as unplayed."
