"""Async Plex API wrapper using httpx."""

from __future__ import annotations

import json
import logging
import platform
import sys
import time
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("plex_mcp")


class PlexAuthError(Exception):
    """Raised on 401 Unauthorized from Plex."""


class PlexNotFoundError(Exception):
    """Raised on 404 Not Found from Plex."""


RENEWAL_COOLDOWN = 86400  # 24 hours — don't attempt renewal more than once/day


class PlexClient:
    """Thin async wrapper around the Plex HTTP API."""

    def __init__(
        self,
        base_url: str,
        token: str,
        client_id: str,
        token_path: Path | None = None,
        debug: bool = False,
    ) -> None:
        self._base_url = base_url
        self._token = token
        self._client_id = client_id
        self._token_path = token_path
        self._debug = debug
        self._last_renewal_attempt: float = 0
        self._client = self._build_client(token)

    def _plex_headers(self, token: str) -> dict[str, str]:
        return {
            "X-Plex-Token": token,
            "X-Plex-Client-Identifier": self._client_id,
            "X-Plex-Product": "Plex MCP Server",
            "X-Plex-Version": "0.1.0",
            "X-Plex-Platform": platform.system(),
            "X-Plex-Platform-Version": platform.release(),
            "X-Plex-Device": platform.system(),
            "X-Plex-Device-Name": platform.node(),
            "Accept": "application/json",
        }

    def _build_client(self, token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._plex_headers(token),
            timeout=30,
        )

    async def close(self) -> None:
        await self._client.aclose()

    # ── Token renewal ──────────────────────────────────────────────

    async def _try_renew_token(self) -> bool:
        """Attempt to refresh the token via plex.tv (at most once/day).

        Plex tokens can be refreshed by simply hitting the user endpoint —
        plex.tv returns a fresh token in the response when the existing one
        is still within its renewal window.
        """
        now = time.time()
        if now - self._last_renewal_attempt < RENEWAL_COOLDOWN:
            return False
        self._last_renewal_attempt = now

        try:
            resp = await self._client.get(
                "https://plex.tv/api/v2/user",
                headers=self._plex_headers(self._token),
            )
            if resp.status_code != 200:
                return False

            data = resp.json()
            new_token = data.get("authToken")
            if new_token and new_token != self._token:
                self._token = new_token
                await self._client.aclose()
                self._client = self._build_client(new_token)
                if self._token_path:
                    self._token_path.write_text(new_token)
                print("Plex token renewed automatically.", file=sys.stderr)
                return True
        except httpx.HTTPError:
            pass
        return False

    # ── Low-level request ──────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> Any:
        # Proactively renew token if it's been 24+ hours since last check
        await self._try_renew_token()

        if self._debug:
            logger.debug(">>> %s %s", method, path)
            if params:
                logger.debug("    params: %s", json.dumps(params, default=str))
            if data:
                logger.debug("    data: %s", json.dumps(data, default=str))

        resp = await self._client.request(method, path, params=params, data=data)

        if self._debug:
            logger.debug("<<< %s %s (status %d, %d bytes)", method, path, resp.status_code, len(resp.content))
            if resp.content:
                try:
                    logger.debug("    response: %s", json.dumps(resp.json(), indent=2, default=str))
                except Exception:
                    logger.debug("    response: (non-JSON) %s", resp.text[:500])

        if resp.status_code == 401:
            raise PlexAuthError(
                "Plex token is no longer valid. Please restart the server to re-authenticate."
            )
        if resp.status_code == 404:
            raise PlexNotFoundError(f"Not found: {path}")
        resp.raise_for_status()
        if not resp.content:
            return {}
        return resp.json()

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _container(data: dict) -> list[dict]:
        """Extract the Metadata array from a Plex MediaContainer response."""
        mc = data.get("MediaContainer", {})
        return mc.get("Metadata", mc.get("Hub", mc.get("Directory", [])))

    @staticmethod
    def _simplify_item(item: dict) -> dict:
        """Return a small dict with the most useful fields."""
        result: dict[str, Any] = {}
        for key in (
            "ratingKey",
            "key",
            "title",
            "type",
            "year",
            "summary",
            "contentRating",
            "rating",
            "audienceRating",
            "duration",
            "addedAt",
            "parentTitle",
            "grandparentTitle",
            "index",
            "parentIndex",
            "viewCount",
            "lastViewedAt",
            "thumb",
            "art",
            "playlistType",
            "smart",
            "leafCount",
        ):
            if key in item:
                result[key] = item[key]
        return result

    # ── Server ─────────────────────────────────────────────────────

    async def get_server_info(self) -> dict:
        data = await self._request("GET", "/")
        mc = data.get("MediaContainer", {})
        return {
            "name": mc.get("friendlyName"),
            "version": mc.get("version"),
            "platform": mc.get("platform"),
            "machineIdentifier": mc.get("machineIdentifier"),
            "myPlexUsername": mc.get("myPlexUsername"),
        }

    # ── Libraries ──────────────────────────────────────────────────

    async def list_libraries(self) -> list[dict]:
        data = await self._request("GET", "/library/sections")
        dirs = data.get("MediaContainer", {}).get("Directory", [])
        return [
            {
                "key": d["key"],
                "title": d["title"],
                "type": d["type"],
                "agent": d.get("agent"),
                "scanner": d.get("scanner"),
            }
            for d in dirs
        ]

    async def browse_library(
        self, section_id: str, offset: int = 0, limit: int = 50
    ) -> dict:
        data = await self._request(
            "GET",
            f"/library/sections/{section_id}/all",
            params={
                "X-Plex-Container-Start": offset,
                "X-Plex-Container-Size": limit,
            },
        )
        mc = data.get("MediaContainer", {})
        return {
            "totalSize": mc.get("totalSize", 0),
            "offset": mc.get("offset", offset),
            "items": [self._simplify_item(m) for m in mc.get("Metadata", [])],
        }

    async def get_metadata(self, rating_key: str) -> dict:
        data = await self._request("GET", f"/library/metadata/{rating_key}")
        items = self._container(data)
        if items:
            return self._simplify_item(items[0])
        return {}

    async def get_children(self, rating_key: str) -> list[dict]:
        data = await self._request("GET", f"/library/metadata/{rating_key}/children")
        return [self._simplify_item(m) for m in self._container(data)]

    async def get_grandchildren(self, rating_key: str) -> list[dict]:
        data = await self._request(
            "GET", f"/library/metadata/{rating_key}/grandchildren"
        )
        return [self._simplify_item(m) for m in self._container(data)]

    # ── Search ─────────────────────────────────────────────────────

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        data = await self._request(
            "GET",
            "/hubs/search",
            params={"query": query, "limit": limit},
        )
        hubs = data.get("MediaContainer", {}).get("Hub", [])
        results: list[dict] = []
        for hub in hubs:
            for item in hub.get("Metadata", []):
                results.append(self._simplify_item(item))
        return results

    # ── Playback / History ─────────────────────────────────────────

    async def get_active_sessions(self) -> list[dict]:
        data = await self._request("GET", "/status/sessions")
        return [self._simplify_item(m) for m in self._container(data)]

    async def get_history(self, offset: int = 0, limit: int = 50) -> dict:
        data = await self._request(
            "GET",
            "/status/sessions/history/all",
            params={
                "X-Plex-Container-Start": offset,
                "X-Plex-Container-Size": limit,
            },
        )
        mc = data.get("MediaContainer", {})
        return {
            "totalSize": mc.get("totalSize", 0),
            "offset": mc.get("offset", offset),
            "items": [self._simplify_item(m) for m in mc.get("Metadata", [])],
        }

    async def mark_played(self, rating_key: str) -> None:
        await self._request(
            "GET", "/:/scrobble", params={"identifier": "com.plexapp.plugins.library", "key": rating_key}
        )

    async def mark_unplayed(self, rating_key: str) -> None:
        await self._request(
            "GET", "/:/unscrobble", params={"identifier": "com.plexapp.plugins.library", "key": rating_key}
        )

    # ── Playlists ──────────────────────────────────────────────────

    async def list_playlists(self) -> list[dict]:
        data = await self._request("GET", "/playlists")
        return [self._simplify_item(m) for m in self._container(data)]

    async def get_playlist_items(self, playlist_id: str) -> list[dict]:
        data = await self._request("GET", f"/playlists/{playlist_id}/items")
        return [self._simplify_item(m) for m in self._container(data)]

    async def create_playlist(
        self, title: str, playlist_type: str, uri: str
    ) -> dict:
        data = await self._request(
            "POST",
            "/playlists",
            params={
                "title": title,
                "type": playlist_type,
                "smart": "0",
                "uri": uri,
            },
        )
        items = self._container(data)
        return self._simplify_item(items[0]) if items else {}

    async def edit_playlist(
        self,
        playlist_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
    ) -> None:
        params: dict[str, str] = {}
        if title is not None:
            params["title"] = title
        if summary is not None:
            params["summary"] = summary
        if params:
            await self._request("PUT", f"/playlists/{playlist_id}", params=params)

    async def delete_playlist(self, playlist_id: str) -> None:
        await self._request("DELETE", f"/playlists/{playlist_id}")

    async def add_playlist_items(self, playlist_id: str, uri: str) -> None:
        await self._request(
            "PUT", f"/playlists/{playlist_id}/items", params={"uri": uri}
        )

    async def remove_playlist_items(self, playlist_id: str, uri: str) -> None:
        await self._request(
            "DELETE", f"/playlists/{playlist_id}/items", params={"uri": uri}
        )

    # ── Collections ────────────────────────────────────────────────

    async def list_collections(self, section_id: str) -> list[dict]:
        data = await self._request(
            "GET", f"/library/sections/{section_id}/collections"
        )
        return [self._simplify_item(m) for m in self._container(data)]

    async def create_collection(
        self, title: str, section_id: str, rating_keys: list[str]
    ) -> dict:
        machine_id = (await self.get_server_info())["machineIdentifier"]
        uri = f"server://{machine_id}/com.plexapp.plugins.library/library/metadata/{','.join(rating_keys)}"
        data = await self._request(
            "POST",
            "/library/collections",
            params={
                "title": title,
                "smart": "0",
                "sectionId": section_id,
                "type": "1",
                "uri": uri,
            },
        )
        items = self._container(data)
        return self._simplify_item(items[0]) if items else {}

    async def edit_collection(
        self,
        collection_id: str,
        *,
        title: str | None = None,
        summary: str | None = None,
    ) -> None:
        params: dict[str, str] = {}
        if title is not None:
            params["title"] = title
        if summary is not None:
            params["summary"] = summary
        if params:
            await self._request(
                "PUT", f"/library/collections/{collection_id}", params=params
            )

    async def delete_collection(self, collection_id: str) -> None:
        await self._request("DELETE", f"/library/collections/{collection_id}")
