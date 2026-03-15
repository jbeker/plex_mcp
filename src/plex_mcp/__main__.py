"""Entry point: authenticate interactively, then start the MCP server."""

import argparse

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
        "--read-only",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable read-only mode (default: true, or set PLEX_READ_ONLY env var)",
    )
    args = parser.parse_args()

    settings = load_settings()

    # CLI args override env vars
    if args.transport is not None:
        settings.transport = args.transport
    if args.read_only is not None:
        settings.read_only = args.read_only

    ensure_authenticated(settings)
    # Import server after auth so stdout is free for interactive prompts
    from .server import mcp

    mcp.run(transport=settings.transport)


if __name__ == "__main__":
    main()
