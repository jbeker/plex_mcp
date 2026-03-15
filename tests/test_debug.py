"""Tests that --debug flag propagates from create_mcp through lifespan to client."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from plex_mcp.client import PlexClient
from plex_mcp.config import Settings


def _make_settings(debug: bool = True) -> Settings:
    return Settings(
        plex_url="http://fake-plex:32400",
        debug=debug,
        token_path=Path("/tmp/fake_plex_token"),
        client_id_path=Path("/tmp/fake_plex_client_id"),
    )


# ── 1. create_mcp stores settings ──────────────────────────────────────


def test_create_mcp_stores_settings():
    """create_mcp() must store the Settings object in the module-level _settings."""
    settings = _make_settings(debug=True)

    with patch("plex_mcp.server.mcp", None):
        from plex_mcp.server import create_mcp, _settings as _before  # noqa: F811

        server = create_mcp(settings)

        # Re-import to see updated module-level value
        import plex_mcp.server as srv

        assert srv._settings is settings
        assert srv._settings.debug is True
        assert server is not None


# ── 2. Lifespan uses stored settings (debug=True) ──────────────────────


@pytest.mark.anyio
async def test_lifespan_uses_stored_settings():
    """app_lifespan must use _settings (not load_settings), passing debug to PlexClient."""
    settings = _make_settings(debug=True)

    import plex_mcp.server as srv

    srv._settings = settings

    with (
        patch("plex_mcp.server.load_cached_token", return_value="fake-token"),
        patch("plex_mcp.server.get_or_create_client_id", return_value="fake-client-id"),
    ):
        fake_server = AsyncMock()
        async with srv.app_lifespan(fake_server) as ctx:
            assert ctx.settings is settings
            assert ctx.settings.debug is True
            assert ctx.client._debug is True


@pytest.mark.anyio
async def test_lifespan_falls_back_to_load_settings():
    """When _settings is None, lifespan falls back to load_settings()."""
    import plex_mcp.server as srv

    srv._settings = None

    fallback = _make_settings(debug=False)

    with (
        patch("plex_mcp.server.load_settings", return_value=fallback),
        patch("plex_mcp.server.load_cached_token", return_value="fake-token"),
        patch("plex_mcp.server.get_or_create_client_id", return_value="fake-client-id"),
    ):
        fake_server = AsyncMock()
        async with srv.app_lifespan(fake_server) as ctx:
            assert ctx.settings is fallback
            assert ctx.settings.debug is False
            assert ctx.client._debug is False


# ── 3. PlexClient._request logs when debug=True ────────────────────────


@pytest.mark.anyio
async def test_client_request_logs_when_debug(caplog):
    """PlexClient._request should emit debug logs when _debug=True."""
    client = PlexClient(
        "http://fake-plex:32400",
        "fake-token",
        "fake-client-id",
        debug=True,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"MediaContainer": {}}'
    mock_resp.json.return_value = {"MediaContainer": {}}

    with (
        patch.object(client._client, "request", return_value=mock_resp),
        patch.object(client, "_try_renew_token", return_value=False),
        caplog.at_level(logging.DEBUG, logger="plex_mcp"),
    ):
        await client._request("GET", "/library/sections")

    assert any(">>> GET" in msg for msg in caplog.messages)
    assert any("<<< GET" in msg for msg in caplog.messages)


@pytest.mark.anyio
async def test_client_request_silent_when_no_debug(caplog):
    """PlexClient._request should NOT emit debug logs when _debug=False."""
    client = PlexClient(
        "http://fake-plex:32400",
        "fake-token",
        "fake-client-id",
        debug=False,
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b'{"MediaContainer": {}}'
    mock_resp.json.return_value = {"MediaContainer": {}}

    with (
        patch.object(client._client, "request", return_value=mock_resp),
        patch.object(client, "_try_renew_token", return_value=False),
        caplog.at_level(logging.DEBUG, logger="plex_mcp"),
    ):
        await client._request("GET", "/library/sections")

    assert not any(">>> GET" in msg for msg in caplog.messages)
    assert not any("<<< GET" in msg for msg in caplog.messages)


# ── 4. _debug_wrap logs tool calls when debug=True ─────────────────────


@pytest.mark.anyio
async def test_debug_wrap_logs_tool_call(caplog):
    """_debug_wrap should log TOOL CALL/RESULT when settings.debug=True."""
    from plex_mcp.server import AppContext, _debug_wrap

    from mcp.server.fastmcp import Context

    settings = _make_settings(debug=True)
    client = AsyncMock()
    app_ctx = AppContext(client=client, settings=settings)

    async def my_tool(ctx: Context, name: str) -> str:
        return f"hello {name}"

    wrapped = _debug_wrap(my_tool)

    # Build a mock Context whose request_context.lifespan_context returns app_ctx
    mock_ctx = AsyncMock(spec=Context)
    mock_ctx.request_context = AsyncMock()
    mock_ctx.request_context.lifespan_context = app_ctx

    with caplog.at_level(logging.DEBUG, logger="plex_mcp"):
        result = await wrapped(mock_ctx, name="world")

    assert result == "hello world"
    assert any("TOOL CALL >>>" in msg for msg in caplog.messages)
    assert any("TOOL RESULT <<<" in msg for msg in caplog.messages)


@pytest.mark.anyio
async def test_debug_wrap_silent_when_no_debug(caplog):
    """_debug_wrap should NOT log when settings.debug=False."""
    from plex_mcp.server import AppContext, _debug_wrap

    from mcp.server.fastmcp import Context

    settings = _make_settings(debug=False)
    client = AsyncMock()
    app_ctx = AppContext(client=client, settings=settings)

    async def my_tool(ctx: Context, name: str) -> str:
        return f"hello {name}"

    wrapped = _debug_wrap(my_tool)

    mock_ctx = AsyncMock(spec=Context)
    mock_ctx.request_context = AsyncMock()
    mock_ctx.request_context.lifespan_context = app_ctx

    with caplog.at_level(logging.DEBUG, logger="plex_mcp"):
        result = await wrapped(mock_ctx, name="world")

    assert result == "hello world"
    assert not any("TOOL CALL >>>" in msg for msg in caplog.messages)
    assert not any("TOOL RESULT <<<" in msg for msg in caplog.messages)
