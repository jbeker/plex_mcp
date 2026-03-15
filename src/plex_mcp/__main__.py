"""Entry point: authenticate interactively, then start the MCP server."""

from .auth import ensure_authenticated
from .config import load_settings


def main() -> None:
    settings = load_settings()
    ensure_authenticated(settings)
    # Import server after auth so stdout is free for interactive prompts
    from .server import mcp

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
