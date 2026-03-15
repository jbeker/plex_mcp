"""Interactive PIN-based Plex OAuth authentication."""

from __future__ import annotations

import platform
import sys
import time
import uuid
import webbrowser
from pathlib import Path
from urllib.parse import quote

import httpx

from .config import Settings

PLEX_PRODUCT = "Plex MCP Server"
PLEX_VERSION = "0.1.0"
PLEX_TV_BASE = "https://plex.tv"
PIN_POLL_INTERVAL = 2  # seconds
PIN_TIMEOUT = 300  # 5 minutes


def _plex_headers(client_id: str, token: str | None = None) -> dict[str, str]:
    """Build the standard set of X-Plex-* headers that plex.tv expects."""
    headers = {
        "X-Plex-Client-Identifier": client_id,
        "X-Plex-Product": PLEX_PRODUCT,
        "X-Plex-Version": PLEX_VERSION,
        "X-Plex-Platform": platform.system(),
        "X-Plex-Platform-Version": platform.release(),
        "X-Plex-Device": platform.system(),
        "X-Plex-Device-Name": platform.node(),
        "Accept": "application/json",
    }
    if token:
        headers["X-Plex-Token"] = token
    return headers


def get_or_create_client_id(path: Path) -> str:
    """Load or generate and persist a client identifier."""
    if path.exists():
        client_id = path.read_text().strip()
        if client_id:
            return client_id
    client_id = str(uuid.uuid4())
    path.write_text(client_id)
    return client_id


def load_cached_token(path: Path) -> str | None:
    """Read token from cache file, or return None."""
    if path.exists():
        token = path.read_text().strip()
        if token:
            return token
    return None


def save_token(token: str, path: Path) -> None:
    """Persist token to cache file."""
    path.write_text(token)


def validate_token(token: str, client_id: str) -> bool:
    """Check whether a token is still valid against plex.tv."""
    try:
        resp = httpx.get(
            f"{PLEX_TV_BASE}/api/v2/user",
            headers=_plex_headers(client_id, token=token),
            timeout=10,
        )
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


def run_pin_auth_flow(client_id: str) -> str:
    """Run the Plex PIN-based OAuth flow interactively.

    All user-facing output goes to stderr (stdout is reserved for MCP stdio).
    """
    headers = _plex_headers(client_id)

    # Request a new PIN
    resp = httpx.post(
        f"{PLEX_TV_BASE}/api/v2/pins",
        headers=headers,
        data={"strong": "true"},
        timeout=10,
    )
    resp.raise_for_status()
    pin_data = resp.json()
    pin_id = pin_data["id"]
    pin_code = pin_data["code"]

    auth_url = (
        f"https://app.plex.tv/auth#?"
        f"clientID={client_id}"
        f"&code={pin_code}"
        f"&context%5Bdevice%5D%5Bproduct%5D={quote(PLEX_PRODUCT)}"
        f"&context%5Bdevice%5D%5Bversion%5D={PLEX_VERSION}"
        f"&context%5Bdevice%5D%5Bplatform%5D={quote(platform.system())}"
        f"&context%5Bdevice%5D%5BdeviceName%5D={quote(platform.node())}"
    )

    print(f"\nOpen this URL to authenticate:\n  {auth_url}\n", file=sys.stderr)
    webbrowser.open(auth_url)

    # Poll for completion
    deadline = time.time() + PIN_TIMEOUT
    while time.time() < deadline:
        time.sleep(PIN_POLL_INTERVAL)
        resp = httpx.get(
            f"{PLEX_TV_BASE}/api/v2/pins/{pin_id}",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        auth_token = data.get("authToken")
        if auth_token:
            print("Authentication successful!", file=sys.stderr)
            return auth_token

    raise TimeoutError("Plex authentication timed out after 5 minutes.")


def ensure_authenticated(settings: Settings) -> str:
    """Return a valid token — try cache first, then interactive flow."""
    client_id = get_or_create_client_id(settings.client_id_path)

    cached = load_cached_token(settings.token_path)
    if cached and validate_token(cached, client_id):
        print("Using cached Plex token.", file=sys.stderr)
        return cached

    print("No valid cached token found. Starting authentication…", file=sys.stderr)
    token = run_pin_auth_flow(client_id)
    save_token(token, settings.token_path)
    return token
