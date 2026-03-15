# Plex MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that exposes your Plex Media Server as a set of tools for AI assistants like Claude. Browse libraries, search media, manage playlists and collections, and view playback history — all through natural language.

## Features

- **22 tools** covering libraries, search, playback, playlists, and collections
- **Interactive Plex OAuth** — browser-based PIN authentication, no manual token wrangling
- **Automatic token renewal** — proactively refreshes tokens before they expire
- **Read-only mode** (default) — safe browsing with opt-in write access
- **Multiple transports** — stdio, SSE, and streamable HTTP

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for dependency management
- A running Plex Media Server

## Quick Start

```bash
# Clone the repo
git clone <repo-url> plex_mcp
cd plex_mcp

# Configure
cp .env.example .env
# Edit .env and set PLEX_URL to your server (e.g. http://localhost:32400)

# Run (first launch opens browser for Plex auth)
uv run plex-mcp
```

On the first run, your browser will open to authorize the app with Plex. Once approved, the token is cached locally in `.plex_token` and reused on subsequent launches.

## Configuration

Configuration is done through environment variables (via `.env` file) and/or CLI flags. CLI flags take precedence over environment variables.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PLEX_URL` | *(required)* | Base URL of your Plex Media Server |
| `PLEX_READ_ONLY` | `true` | Set to `false` to enable write operations |
| `PLEX_TRANSPORT` | `stdio` | MCP transport: `stdio`, `sse`, or `streamable-http` |

### CLI Options

```
usage: plex-mcp [-h] [--transport {stdio,sse,streamable-http}]
                [--read-only | --no-read-only]

options:
  -h, --help            show this help message and exit
  --transport {stdio,sse,streamable-http}
                        MCP transport (default: stdio, or set PLEX_TRANSPORT)
  --read-only, --no-read-only
                        Enable/disable read-only mode (default: true, or set PLEX_READ_ONLY)
```

### Examples

```bash
# Default: stdio transport, read-only
uv run plex-mcp

# SSE transport with write access
uv run plex-mcp --transport sse --no-read-only

# Streamable HTTP transport
uv run plex-mcp --transport streamable-http
```

## Using with Claude Code

Add the server to your Claude Code MCP configuration (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "plex": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/plex_mcp", "plex-mcp"],
      "env": {
        "PLEX_URL": "http://localhost:32400"
      }
    }
  }
}
```

## Tools

### Library (read)

| Tool | Description |
|---|---|
| `get_server_info` | Get Plex server name, version, and platform info |
| `list_libraries` | List all libraries (sections) on the server |
| `browse_library` | Browse items in a library section with pagination |
| `get_metadata` | Get detailed metadata for an item by its ratingKey |
| `get_children` | Get children of an item (e.g., seasons of a show) |
| `get_grandchildren` | Get grandchildren of an item (e.g., episodes of a show) |

### Search (read)

| Tool | Description |
|---|---|
| `search` | Search across all libraries for movies, shows, music, etc. |

### Playback (read + write)

| Tool | Description |
|---|---|
| `get_active_sessions` | Get currently active playback sessions |
| `get_history` | Get playback history with pagination |
| `mark_played` | Mark an item as played *(write)* |
| `mark_unplayed` | Mark an item as unplayed *(write)* |

### Playlists (read + write)

| Tool | Description |
|---|---|
| `list_playlists` | List all playlists |
| `get_playlist_items` | Get items in a playlist |
| `create_playlist` | Create a new playlist *(write)* |
| `edit_playlist` | Edit a playlist's title/summary *(write)* |
| `delete_playlist` | Delete a playlist *(write)* |
| `add_playlist_items` | Add items to a playlist *(write)* |
| `remove_playlist_items` | Remove items from a playlist *(write)* |

### Collections (read + write)

| Tool | Description |
|---|---|
| `list_collections` | List all collections in a library section |
| `create_collection` | Create a new collection *(write)* |
| `edit_collection` | Edit a collection's title/summary *(write)* |
| `delete_collection` | Delete a collection *(write)* |

Tools marked *(write)* require `PLEX_READ_ONLY=false` or `--no-read-only`.

## Authentication

### How It Works

1. **First run**: The server generates a unique client ID (saved to `.plex_client_id`), then starts a Plex PIN-based OAuth flow — your browser opens to `app.plex.tv` where you approve access. The returned token is cached to `.plex_token`.
2. **Subsequent runs**: The cached token is validated against `plex.tv` and reused if still valid.
3. **Token renewal**: Plex tokens expire every 7 days. The server proactively renews tokens by checking with `plex.tv` once per day during normal operation — no user interaction required.

### Files

| File | Purpose |
|---|---|
| `.plex_token` | Cached authentication token |
| `.plex_client_id` | Persistent client identifier (UUID) |

Both files are in `.gitignore` and should never be committed.

## Architecture

```
src/plex_mcp/
├── __main__.py      # CLI entry point: parse args, auth, start server
├── auth.py          # PIN-based OAuth flow, token caching/validation
├── config.py        # Environment/CLI settings
├── client.py        # Async Plex API wrapper (httpx) with token renewal
├── server.py        # FastMCP instance, lifespan, write-guard
└── tools/
    ├── library.py   # Server info, library browsing, metadata
    ├── search.py    # Cross-library search
    ├── playback.py  # Sessions, history, scrobble
    ├── playlists.py # Playlist CRUD
    └── collections.py # Collection CRUD
```

### Design Decisions

- **Auth before stdio**: Interactive PIN flow runs in `__main__` before `mcp.run()` claims stdout. All auth output goes to stderr.
- **Proactive token renewal**: The client checks token freshness on every request (with a 24-hour cooldown) rather than waiting for a 401, since expired Plex tokens cannot be renewed.
- **Response shaping**: API responses are simplified to essential fields (`title`, `year`, `rating`, `summary`, `ratingKey`, `type`, etc.) to reduce token usage in LLM contexts.
- **Write guard**: Write tools call `require_write()` which raises a clear error when `read_only=True`, converted to a tool error by the MCP SDK.

## License

MIT
