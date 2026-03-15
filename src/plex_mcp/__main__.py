"""Entry point: authenticate interactively, then start the MCP server."""

import argparse
import logging
import sys

from .auth import ensure_authenticated
from .config import VALID_TRANSPORTS, load_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Plex MCP Server")
    parser.add_argument(
        "--transport",
        choices=VALID_TRANSPORTS,
        default=None,
        help="MCP transport (default: stdio, or set PLEX_TRANSPORT env var)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to for HTTP transports (default: 127.0.0.1, or set PLEX_HOST env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to for HTTP transports (default: 8000, or set PLEX_PORT env var)",
    )
    parser.add_argument(
        "--read-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable read-only mode (default: true, or set PLEX_READ_ONLY env var)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=None,
        help="Enable debug logging of API calls (default: false, or set PLEX_DEBUG env var)",
    )
    args = parser.parse_args()

    settings = load_settings()

    # CLI args override env vars
    if args.transport is not None:
        settings.transport = args.transport
    if args.host is not None:
        settings.host = args.host
    if args.port is not None:
        settings.port = args.port
    if args.read_only is not None:
        settings.read_only = args.read_only
    if args.debug is not None:
        settings.debug = args.debug

    if settings.debug:
        plex_logger = logging.getLogger("plex_mcp")
        plex_logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(message)s"))
        plex_logger.addHandler(handler)
        plex_logger.propagate = False

    ensure_authenticated(settings)
    # Import and create server after auth so stdout is free for interactive prompts
    from .server import create_mcp

    server = create_mcp(host=settings.host, port=settings.port)
    server.run(transport=settings.transport)


if __name__ == "__main__":
    main()
