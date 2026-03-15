"""Playlist CRUD tools."""

from __future__ import annotations

from mcp.server.fastmcp import Context

from ..server import get_ctx, mcp, require_write


@mcp.tool()
async def list_playlists(ctx: Context) -> list[dict]:
    """List all playlists on the Plex server."""
    return await get_ctx(ctx).client.list_playlists()


@mcp.tool()
async def get_playlist_items(ctx: Context, playlist_id: str) -> list[dict]:
    """Get items in a playlist."""
    return await get_ctx(ctx).client.get_playlist_items(playlist_id)


@mcp.tool()
async def create_playlist(
    ctx: Context, title: str, playlist_type: str, uri: str
) -> dict:
    """Create a new playlist. Requires write access.

    Args:
        title: Playlist name.
        playlist_type: Type of playlist (audio, video, photo).
        uri: URI of initial items (e.g. server://machine-id/com.plexapp.plugins.library/library/metadata/123).
    """
    require_write(ctx)
    return await get_ctx(ctx).client.create_playlist(title, playlist_type, uri)


@mcp.tool()
async def edit_playlist(
    ctx: Context,
    playlist_id: str,
    title: str | None = None,
    summary: str | None = None,
) -> str:
    """Edit a playlist's title and/or summary. Requires write access."""
    require_write(ctx)
    await get_ctx(ctx).client.edit_playlist(playlist_id, title=title, summary=summary)
    return f"Playlist {playlist_id} updated."


@mcp.tool()
async def delete_playlist(ctx: Context, playlist_id: str) -> str:
    """Delete a playlist. Requires write access."""
    require_write(ctx)
    await get_ctx(ctx).client.delete_playlist(playlist_id)
    return f"Playlist {playlist_id} deleted."


@mcp.tool()
async def add_playlist_items(ctx: Context, playlist_id: str, uri: str) -> str:
    """Add items to a playlist. Requires write access.

    Args:
        playlist_id: The playlist's ratingKey.
        uri: URI of items to add.
    """
    require_write(ctx)
    await get_ctx(ctx).client.add_playlist_items(playlist_id, uri)
    return f"Items added to playlist {playlist_id}."


@mcp.tool()
async def remove_playlist_items(ctx: Context, playlist_id: str, uri: str) -> str:
    """Remove items from a playlist. Requires write access.

    Args:
        playlist_id: The playlist's ratingKey.
        uri: URI of items to remove.
    """
    require_write(ctx)
    await get_ctx(ctx).client.remove_playlist_items(playlist_id, uri)
    return f"Items removed from playlist {playlist_id}."
