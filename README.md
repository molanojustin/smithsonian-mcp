# Smithsonian Open Access MCP Server

[![npm version](https://badge.fury.io/js/%40molanojustin%2Fsmithsonian-mcp.svg)](https://badge.fury.io/js/%40molanojustin%2Fsmithsonian-mcp)
[![NPM Downloads](https://img.shields.io/npm/dm/%40molanojustin%2Fsmithsonian-mcp)](https://www.npmjs.com/package/@molanojustin%2Fsmithsonian-mcp)

A **Model Context Protocol (MCP)** server that provides AI assistants with access to the **Smithsonian Institution's Open Access collections**. This server allows AI tools like Claude Desktop to search, explore, and analyze over 3 million collection objects from America's national museums.

## Quick Start

### Option 1: npm/npx Installation (Easiest)

The npm package includes automatic Python dependency management and works across platforms:

```bash
# Install globally
npm install -g @molanojustin/smithsonian-mcp

# Or run directly with npx (no installation needed)
npx -y @molanojustin/smithsonian-mcp

# Set your API key
export SMITHSONIAN_API_KEY=your_key_here

# Start the server
smithsonian-mcp
```

### Option 2: Automated Setup (Recommended for Python users)

The enhanced setup script now includes:

- ✅ **API key validation** - Tests your key before saving
- ✅ **Service installation** - Auto-install as system service
- ✅ **Claude Desktop config** - Automatic configuration
- ✅ **Health checks** - Verify everything works
**macOS/Linux:**

```bash
chmod +x config/setup.sh
config/setup.sh
```

**Windows:**

```powershell
config\setup.ps1
```

### Option 3: Manual Setup

1. **Get API Key**: [api.data.gov/signup](https://api.data.gov/signup/) (free)
2. **Install**: `uv pip install -r config/requirements.txt`
3. **Configure**: Copy `.env.example` to `.env` and set your API key
4. **Test**: `python examples/test-api-connection.py`

### Verify Setup

Run the verification script to check your installation:

```bash
python scripts/verify-setup.py
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

## Integration

### Claude Desktop

#### Option 1: Using npm/npx (Recommended)

1. **Configure** (`claude_desktop_config.json`):

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

#### Option 2: Using Python installation

1. **Configure** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "python",
      "args": ["-m", "smithsonian_mcp.server"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_key_here"
      }
    }
  }
}
```

2. **Test**: Ask Claude "What Smithsonian museums are available?"

### mcpo Integration (MCP Orchestrator)

**mcpo** is an MCP orchestrator that converts multiple MCP servers into OpenAPI/HTTP endpoints, ideal for combining multiple services into a single systemd service.

#### Installation

```bash
# Install mcpo
uvx mcpo

# Or using uvx
uvx mcpo --help
```

#### Configuration

Create a `examples/mcpo-config.json` file:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "python",
      "args": ["-m", "smithsonian_mcp.main"],
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
mcpo --config examples/mcpo-config.json --port 8000 --hot-reload

# With API key authentication
mcpo --config examples/mcpo-config.json --port 8000 --api-key "your_secret_key"

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
ExecStart=/path/to/venv/bin/mcpo --config examples/mcpo-config.json --port 8000
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

1. **Open Workspace**: `code .vscode/smithsonian-mcp-workspace.code-workspace`
2. **Run Tasks**: Debug, test, and develop the MCP server
3. **Claude Code**: AI-assisted development with Smithsonian data

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

### Essential Tools (Use These First!)

- `get_object_url` - **REQUIRED** for all Smithsonian object URLs (use exact 'id' field from search results!)
- `search_collections` - Find objects across museums
- `get_object_details` - Get complete object information

### Search & Discovery

- `simple_explore` - Smart diverse sampling across museums and object types (recommended for general discovery)
- `continue_explore` - Get more results about the same topic while avoiding duplicates
- `search_collections` - Advanced search with filters (now includes `on_view` parameter)
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

### For npm/npx installation:

- Node.js 16.0 or higher
- Python 3.10 or higher (auto-detected and dependencies managed)
- API key from [api.data.gov](https://api.data.gov/signup/) (free)
- Internet connection for API access

### For Python installation:

- Python 3.10 or higher
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

### Using Python:

```bash
# Test API connection
python examples/test-api-connection.py

# Run MCP server
python -m smithsonian_mcp.server

# Run test suite
pytest tests/

# Run on-view functionality tests
pytest tests/test_on_view.py -v

# Run basic tests
pytest tests/test_basic.py -v

# Verify complete setup
python scripts/verify-setup.py

# VS Code Tasks (if using workspace)
# - Test MCP Server
# - Run Tests
# - Format Code
# - Lint Code
```

## Service Management

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
