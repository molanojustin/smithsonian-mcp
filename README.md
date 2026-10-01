# Smithsonian Open Access MCP Server

[![npm version](https://badge.fury.io/js/%40molanojustin%2Fsmithsonian-mcp.svg)](https://badge.fury.io/js/%40molanojustin%2Fsmithsonian-mcp)
[![NPM Downloads](https://img.shields.io/npm/dm/%40molanojustin%2Fsmithsonian-mcp)](https://www.npmjs.com/package/@molanojustin%2Fsmithsonian-mcp)
[![Docker](https://img.shields.io/docker/pulls/justinmol/smithsonian-mcp?logo=docker&label=Docker)](https://hub.docker.com/r/justinmol/smithsonian-mcp)

A **Model Context Protocol (MCP)** server that provides AI assistants with access to the **Smithsonian Institution's Open Access collections**. This server allows AI tools like Claude Desktop to search, explore, and analyze over 3 million collection objects from America's national museums.

## Quick Start

You need:

- A free API key from [api.data.gov/signup](https://api.data.gov/signup/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/). uv downloads a compatible Python (3.10 or newer) if one is not already installed.

The server speaks MCP over stdio. MCP clients such as Claude Desktop start it on demand; you do not run it in the background yourself.

### Claude Desktop with uvx (recommended)

Add this to `claude_desktop_config.json`. It installs and runs the server straight from the GitHub repository, with no clone or virtual environment to manage:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/molanojustin/smithsonian-mcp",
        "smithsonian-mcp"
      ],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

Restart Claude Desktop, then ask "What Smithsonian museums are available?"

Notes:

- The package is not published on PyPI, so `--from` points uvx at the GitHub repository. Append `@<tag or commit>` to the URL to pin a version.
- uvx caches the build. To pick up newer commits, run `uvx --refresh --from git+https://github.com/molanojustin/smithsonian-mcp smithsonian-mcp` once in a terminal.
- If Claude Desktop reports that `uvx` cannot be found, use its absolute path as the `command` (`which uvx` on macOS/Linux, `where uvx` on Windows).

### Other ways to run the server

All of these start the same `smithsonian-mcp` command and take the API key from the same `env` block.

#### npm/npx

The npm package is a small Node.js wrapper that uses uv to install the Python dependencies on first start. It requires Node.js 16 or newer and uv:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "npx",
      "args": ["-y", "@molanojustin/smithsonian-mcp"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

You can also install it globally with `npm install -g @molanojustin/smithsonian-mcp` and run `smithsonian-mcp`. Run `smithsonian-mcp --test` to check your API key and connection.

The wrapper keeps the Python environment in a per-user cache directory, one per package version: `~/Library/Caches/smithsonian-mcp` on macOS, `~/.cache/smithsonian-mcp` (or `$XDG_CACHE_HOME`) on Linux, and `%LOCALAPPDATA%\smithsonian-mcp` on Windows. Set `UV_PROJECT_ENVIRONMENT` to use a different location. Older versions' environments there can be deleted safely.

#### From a local clone

```bash
git clone https://github.com/molanojustin/smithsonian-mcp.git
cd smithsonian-mcp
uv sync
```

`uv sync` creates `.venv` from `uv.lock` and installs the `smithsonian-mcp` command into it. Point Claude Desktop at the clone:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/smithsonian-mcp", "run", "smithsonian-mcp"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

Alternatively, use the installed command directly as `"command": "/absolute/path/to/smithsonian-mcp/.venv/bin/smithsonian-mcp"` (on Windows, `.venv\Scripts\smithsonian-mcp.exe`) with no `args`.

#### Python virtual environment without uv

Requires Python 3.10 or newer:

```bash
git clone https://github.com/molanojustin/smithsonian-mcp.git
cd smithsonian-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
```

Then use `/absolute/path/to/smithsonian-mcp/.venv/bin/smithsonian-mcp` as the `command`. This installs the newest compatible dependencies rather than the versions pinned in `uv.lock`.

#### Docker

Build the image from a clone. The `-i` flag keeps stdin open for the stdio transport, and `-e SMITHSONIAN_API_KEY` passes the key from the `env` block into the container:

```bash
docker build -t smithsonian-mcp .
```

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-e", "SMITHSONIAN_API_KEY", "smithsonian-mcp"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

### Automated Setup Scripts

For a local clone, the setup scripts install dependencies (with `uv sync` when uv is available, otherwise a Python 3.10+ virtual environment and pip), validate your API key and save it to `.env`, and can optionally add the server to your Claude Desktop config, generate an mcpo config and run a health check.

**macOS/Linux:**

```bash
chmod +x config/setup.sh
config/setup.sh
```

**Windows:**

```powershell
config\setup.ps1
```

### API Key in `.env`

When you run the server from a clone, it also reads `SMITHSONIAN_API_KEY` from a `.env` file in the project root. Copy `.env.example` to `.env` and set your key. A key set in the MCP client's `env` block takes precedence.

### Verify Setup

Check an installation from a clone:

```bash
uv run python examples/test-api-connection.py
uv run python scripts/verify-setup.py
```

## Features

### Core Functionality

- **Search Collections**: 3+ million objects across 24 Smithsonian museums
- **Object Details**: Complete metadata, descriptions, and provenance
- **On-View Status** - Find objects currently on physical exhibit
- **Image Access**: High-resolution images (CC0 licensed when available)
- **Museum Information**: Browse all Smithsonian institutions
- **Collection Statistics**: Comprehensive metrics with per-museum breakdowns (sampling-based estimates)

### AI Integration

- **16 MCP Tools**: Smart discovery, comprehensive search, museum-specific queries, exhibition status, contextual data access, and proactive collection type discovery
- **Proactive Discovery**: New tools help AI assistants understand API scope and available object types before searching, preventing confusion about archival vs. museum materials
- **Smart Context**: Contextual data sources for AI assistants including enhanced statistics
- **Rich Metadata**: Complete object information and exhibition details
- **Exhibition Planning** - Tools to find and explore currently exhibited objects
- **Collection Analytics**: Per-museum statistics with sampling-based accuracy
- **Multi-Model Compatible**: Works well with both advanced and simpler AI models through simplified tool interfaces

### URL Validation & Anti-Guessing
- **Easiest Solution**: Use `search_and_get_first_url()` for one-step search + validated URL retrieval
- **Mandatory Tool Usage**: LLM must use `get_object_url()` tool for any URL retrieval - manual construction fails due to case sensitivity
- **Flexible Identifiers**: Supports Accession Numbers (F1900.47), Record IDs (fsg_F1900.47), and Internal IDs (ld1-...)
- **URL Validation**: Automatically selects authoritative record_link over API identifiers, handles case sensitivity

## Integration

### Claude Desktop

See [Quick Start](#quick-start) for Claude Desktop configurations using uvx, npm/npx, a local clone, a virtual environment or Docker. A ready-to-copy example is in `examples/claude-desktop-config.json`.

### mcpo Integration (MCP Orchestrator)

**mcpo** is an MCP orchestrator that converts multiple MCP servers into OpenAPI/HTTP endpoints, ideal for combining multiple services into a single systemd service.

#### Installation

```bash
# Install mcpo as a uv tool
uv tool install mcpo

# Or run it without installing
uvx mcpo --help
```

#### Configuration

Copy `examples/mcpo-config.json` to `mcpo-config.json` in the project root and fill in your paths and API key, or let `config/setup.sh` generate it. The generated file contains your API key, so do not commit it. A minimal configuration:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/molanojustin/smithsonian-mcp",
        "smithsonian-mcp"
      ],
      "env": {
        "SMITHSONIAN_API_KEY": "your_api_key_here"
      }
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "time": {
      "command": "uvx",
      "args": ["mcp-server-time", "--local-timezone=America/New_York"]
    }
  }
}
```

#### Running with mcpo

```bash
# Start mcpo with hot-reload
mcpo --config mcpo-config.json --port 8000 --hot-reload

# With API key authentication
mcpo --config mcpo-config.json --port 8000 --api-key "your_secret_key"

# Access endpoints:
# - Smithsonian: http://localhost:8000/smithsonian_open_access
# - Memory: http://localhost:8000/memory
# - Time: http://localhost:8000/time
# - API docs: http://localhost:8000/docs
```

#### Systemd Service

Create `/etc/systemd/system/mcpo.service`:

```ini
[Unit]
Description=MCP Orchestrator Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/your/config
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/mcpo --config mcpo-config.json --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl enable mcpo
sudo systemctl start mcpo
sudo systemctl status mcpo
```

#### Troubleshooting mcpo

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed mcpo troubleshooting, including:
- ModuleNotFoundError solutions
- Connection closed errors
- Port conflicts
- Path configuration issues

### VS Code

Open the clone with `code .`. After `uv sync --group dev`, `.vscode/tasks.json` provides tasks to start the server, run the tests, format and lint the code, and open the MCP Inspector, and `.vscode/launch.json` provides debugger configurations for the server and the tests.

## Available Data

- **19 Museums**: NMNH, NPG, SAAM, NASM, NMAH, and more
- **3+ Million Objects**: Digitized collection items
- **CC0 Content**: Public domain materials for commercial use
- **Rich Metadata**: Creators, dates, materials, dimensions
- **High-Resolution Images**: Professional photography

### Data Accuracy & Sampling

Collection statistics for objects with images use **sampling methodology** to provide accurate estimates:

- **Sample Size**: Up to 1000 objects per query for statistical significance
- **Methodology**: Counts actual returned objects instead of relying on potentially buggy API totals
- **Coverage**: Includes per-museum breakdowns with individual sampling for each institution
- **Transparency**: All sampled counts are clearly marked as "(est.)" in outputs

This approach ensures reliable metrics while respecting API rate limits and avoiding the Smithsonian API's rowCount filtering bug.

### Current API Limitations

**Image URLs Not Available**: The Smithsonian Open Access API currently does not provide image URLs or media data in detailed content responses. While the search API can filter objects by media type (e.g., `online_media_type:Images`), the actual image URLs are not included in the detailed object data returned by the content API. This appears to be a change in the API since the available documentation was published.

- Objects will show as having 0 images even when filtered for image content
- Image statistics are estimates based on search filtering, not actual media availability
- The system gracefully handles this limitation and continues to provide all other metadata

**API Scope: Diverse Museum Collections**: The Smithsonian Open Access API provides access to diverse collections across 24 Smithsonian museums, with each museum having distinct object types reflecting their unique focus areas. The discovery tools now correctly identify museum-specific collections with comprehensive object type intelligence gathered through systematic sampling.

- **SAAM** (American Art): Paintings, decorative arts, sculptures, drawings
- **NASM** (Air & Space): Aircraft, avionics, spacecraft, aviation equipment
- **NMAH** (American History): Historical artifacts, inventions, cultural objects
- **CHNDM** (Design Museum): Design objects, textiles, furniture, graphics
- Use discovery tools (`get_museum_collection_types`, `check_museum_has_object_type`) to explore available collections
- Each museum's collection reflects its institutional mission and expertise

## MCP Tools

### Search & Discovery

- `simple_explore` - Smart diverse sampling across museums and object types (recommended for general discovery)
- `continue_explore` - Get more results about the same topic while avoiding duplicates
- `search_collections` - Advanced search with filters (prioritizes museum-specific results when unit_code specified)
- `search_and_get_first_url` - **Easiest option**: Search and get validated URL in one step (prevents manual URL construction)
- `get_object_details` - Detailed object information
- `get_object_url` - Get validated object URLs with flexible identifier support (MANDATORY: never construct URLs manually)
- `search_by_unit` - Museum-specific searches
- `get_objects_on_view` - Find objects currently on physical exhibit
- `check_object_on_view` - Check if a specific object is on display
- `get_museum_collection_types` - Get comprehensive list of object types available in each museum (based on systematic collection sampling)
- `check_museum_has_object_type` - Check if a specific museum has objects of a particular type (e.g., paintings, sculptures)

### Information & Context

- `get_smithsonian_units` - List all museums
- `get_collection_statistics` - Collection metrics with per-museum breakdowns
- `get_search_context` - Get search results as context data
- `get_object_context` - Get detailed object information as context
- `get_units_context` - Get list of units as context data
- `get_stats_context` - Get collection statistics as context (includes sampling-based estimates)
- `get_on_view_context` - Get currently exhibited objects as context

## Use Cases

### Research & Education

- **Scholarly Research**: Multi-step academic investigation
- **Lesson Planning**: Educational content creation
- **Object Analysis**: In-depth cultural object study
- **URL Retrieval**: Get validated object web page URLs (with anti-guessing protection)

### Curation & Exhibition

- **Exhibition Planning**: Thematic object selection and visitor planning
- **Visit Planning**: Find what's currently on display before visiting
- **Exhibition Research**: Study current exhibition trends and displays
- **Collection Development**: Gap analysis and acquisition
- **Digital Humanities**: Large-scale analysis projects

### Development

- **Cultural Apps**: Applications using museum data
- **Educational Tools**: Interactive learning platforms
- **API Integration**: Professional development workflows

## Requirements

### For uvx or a local clone:

- [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs Python 3.10 or newer if needed
- API key from [api.data.gov](https://api.data.gov/signup/) (free)
- Internet connection for API access

### For npm/npx installation:

- Node.js 16.0 or higher
- uv (the wrapper uses it to install the Python dependencies)
- API key from [api.data.gov](https://api.data.gov/signup/) (free)
- Internet connection for API access

### For a virtual environment without uv:

- Python 3.10 or higher (CI tests 3.10 through 3.14)
- API key from [api.data.gov](https://api.data.gov/signup/) (free)
- Internet connection for API access

## Testing

### Using npm/npx:

```bash
# Test API connection
smithsonian-mcp --test

# Run MCP server
smithsonian-mcp

# Show help
smithsonian-mcp --help
```

### From a local clone:

```bash
# Install runtime and development dependencies
uv sync --group dev

# Test API connection
uv run python examples/test-api-connection.py

# Run MCP server (stdio; normally your MCP client starts it)
uv run smithsonian-mcp

# Explore the server interactively with the MCP Inspector
npx @modelcontextprotocol/inspector .venv/bin/smithsonian-mcp

# Run test suite
uv run pytest tests/

# Run on-view functionality tests
uv run pytest tests/test_on_view.py -v

# Run basic tests
uv run pytest tests/test_basic.py -v

# Verify complete setup
uv run python scripts/verify-setup.py
```

## Service Management

The setup scripts can register the server as a background service. Because the server uses the stdio transport, it exits as soon as no client is attached, so a standalone service is rarely useful. To expose the tools as a long-running HTTP service, run them behind [mcpo](#mcpo-integration-mcp-orchestrator) instead.

### Linux (systemd)

```bash
# Start service
systemctl --user start smithsonian-mcp

# Stop service
systemctl --user stop smithsonian-mcp

# Check status
systemctl --user status smithsonian-mcp

# Enable on boot
systemctl --user enable smithsonian-mcp
```

### macOS (launchd)

```bash
# Load service
launchctl load ~/Library/LaunchAgents/com.smithsonian.mcp.plist

# Unload service
launchctl unload ~/Library/LaunchAgents/com.smithsonian.mcp.plist

# Check status
launchctl list | grep com.smithsonian.mcp
```

### Windows

```powershell
# Start service
Start-Service SmithsonianMCP

# Stop service
Stop-Service SmithsonianMCP

# Check status
Get-Service SmithsonianMCP
```

## Troubleshooting

For detailed troubleshooting guidance, including:
- Common setup issues
- Service startup problems
- API key validation
- Claude Desktop connection issues
- Module import errors
- Platform-specific problems

Please refer to [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Documentation

### Available Documentation

- **[README.md](README.md)** - Main setup and usage guide (this file)
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Comprehensive troubleshooting and common issues
- **Examples** - Real-world usage scenarios in `examples/` directory
- **Scripts** - Setup and utility scripts in `scripts/` directory

### Key Reference
- **API Reference**: Complete tool and resource documentation in this README
- **Deployment Guide**: Production deployment options included in setup instructions
- **Integration Guide**: Claude Desktop and mcpo setup instructions in this README

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- **Smithsonian Institution** for Open Access collections
- **api.data.gov** for API infrastructure
- **FastMCP** team for the MCP framework
- **Model Context Protocol** community
