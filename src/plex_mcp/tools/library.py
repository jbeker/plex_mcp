"""Server info, library browsing, and metadata tools."""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import debug_tool, get_ctx


@debug_tool()
async def get_server_info(ctx: Context) -> dict:
    """Get Plex server name, version, and platform info."""
    return await get_ctx(ctx).client.get_server_info()


@debug_tool()
async def list_libraries(ctx: Context) -> list[dict]:
    """List all libraries (sections) on the Plex server."""
    return await get_ctx(ctx).client.list_libraries()


@debug_tool()
async def browse_library(
    ctx: Context, section_id: str, offset: int = 0, limit: int = 50
) -> dict:
    """Browse items in a library section. Returns paginated results with totalSize, offset, and items."""
    return await get_ctx(ctx).client.browse_library(section_id, offset, limit)


@debug_tool()
async def get_metadata(ctx: Context, rating_key: str) -> dict:
    """Get detailed metadata for a specific item by its ratingKey."""
    return await get_ctx(ctx).client.get_metadata(rating_key)


@debug_tool()
async def get_children(ctx: Context, rating_key: str) -> list[dict]:
    """Get children of an item (e.g., seasons of a show, tracks of an album)."""
    return await get_ctx(ctx).client.get_children(rating_key)


@debug_tool()
async def get_grandchildren(ctx: Context, rating_key: str) -> list[dict]:
    """Get grandchildren of an item (e.g., episodes of a show)."""
    return await get_ctx(ctx).client.get_grandchildren(rating_key)
