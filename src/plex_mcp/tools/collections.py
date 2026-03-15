"""Collection CRUD tools."""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import get_ctx, mcp, require_write


@mcp.tool()
async def list_collections(ctx: Context, section_id: str) -> list[dict]:
    """List all collections in a library section."""
    return await get_ctx(ctx).client.list_collections(section_id)


@mcp.tool()
async def create_collection(
    ctx: Context, title: str, section_id: str, rating_keys: list[str]
) -> dict:
    """Create a new collection. Requires write access.

    Args:
        title: Collection name.
        section_id: Library section ID.
        rating_keys: List of ratingKeys to include in the collection.
    """
    require_write(ctx)
    return await get_ctx(ctx).client.create_collection(title, section_id, rating_keys)


@mcp.tool()
async def edit_collection(
    ctx: Context,
    collection_id: str,
    title: str | None = None,
    summary: str | None = None,
) -> str:
    """Edit a collection's title and/or summary. Requires write access."""
    require_write(ctx)
    await get_ctx(ctx).client.edit_collection(
        collection_id, title=title, summary=summary
    )
    return f"Collection {collection_id} updated."


@mcp.tool()
async def delete_collection(ctx: Context, collection_id: str) -> str:
    """Delete a collection. Requires write access."""
    require_write(ctx)
    await get_ctx(ctx).client.delete_collection(collection_id)
    return f"Collection {collection_id} deleted."
