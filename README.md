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
chmod +x setup.sh
./setup.sh
```

**Windows:**

```powershell
.\setup.ps1
```

### Option 3: Manual Setup

1. **Get API Key**: [api.data.gov/signup](https://api.data.gov/signup/) (free)
2. **Install**: `pip install -r requirements.txt`
3. **Configure**: Copy `.env.example` to `.env` and set your API key
4. **Test**: `python examples/test-api-connection.py`

### Verify Setup

Run the verification script to check your installation:

```bash
python scripts/verify-setup.py
```

## Features

### Core Functionality

- **Search Collections**: 3+ million objects across 19 Smithsonian museums
- **Object Details**: Complete metadata, descriptions, and provenance
- **On-View Status**: ⭐ **NEW** - Find objects currently on physical exhibit
- **Image Access**: High-resolution images (CC0 licensed when available)
- **3D Models**: Interactive 3D content where available
- **Museum Information**: Browse all Smithsonian institutions

### AI Integration

- **12 MCP Tools**: Search, filter, retrieve collection data, check exhibition status, and get context
- **Smart Context**: Contextual data sources for AI assistants
- **Rich Metadata**: Complete object information and exhibition details
- **Exhibition Planning**: ⭐ **NEW** - Tools to find and explore currently exhibited objects

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

_Or copy the provided `claude-desktop-config.json` and update the API key_

2. **Test**: Ask Claude "What Smithsonian museums are available?"

### mcpo Integration (MCP Orchestrator)

**mcpo** is an MCP orchestrator that converts multiple MCP servers into OpenAPI/HTTP endpoints, ideal for combining multiple services into a single systemd service.

#### Installation

```bash
# Install mcpo
pip install mcpo

# Or using uvx
uvx mcpo --help
```

#### Configuration

Create a `mcpo-config.json` file:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "python",
      "args": ["-m", "smithsonian_mcp.server"],
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

**"ModuleNotFoundError: No module named 'smithsonian_mcp'"**
This occurs when mcpo can't find the Smithsonian MCP module. Fix by:

1. **Use absolute Python path** in your mcpo config:

```json
{
  "command": "/full/path/to/your/project/.venv/bin/python",
  "env": {
    "PYTHONPATH": "/full/path/to/your/project"
  }
}
```

2. **Verify paths**:

```bash
# Check Python executable exists
ls -la /path/to/your/project/.venv/bin/python

# Test module import
/path/to/your/project/.venv/bin/python -c "import smithsonian_mcp; print('OK')"
```

3. **Regenerate config** with setup script:

```bash
./setup.sh  # Will create mcpo-config.json with correct paths
```

**"Connection closed" errors**

- Ensure API key is valid and set in environment
- Check that the virtual environment has all dependencies installed
- Verify the MCP server can start manually: `python -m smithsonian_mcp.server --test`

**"Port 8000 already in use"**

```bash
# Check what's using the port
lsof -i :8000
# Or use different port
mcpo --config mcpo-config.json --port 8001
```

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
- **3D Models**: Interactive digital assets

## MCP Tools

### Search & Discovery

- `search_collections` - Advanced search with filters (now includes `on_view` parameter)
- `get_object_details` - Detailed object information
- `search_by_unit` - Museum-specific searches
- ⭐ `get_objects_on_view` - **NEW** - Find objects currently on physical exhibit
- ⭐ `check_object_on_view` - **NEW** - Check if a specific object is on display

### Information & Context

- `get_smithsonian_units` - List all museums
- `get_collection_statistics` - Collection metrics
- `get_search_context` - Get search results as context data
- `get_object_context` - Get detailed object information as context
- `get_units_context` - Get list of units as context data
- `get_stats_context` - Get collection statistics as context
- ⭐ `get_on_view_context` - **NEW** - Get currently exhibited objects as context

## New: On-View Functionality 🎨

### What's New in Phase 1

The MCP server now includes comprehensive support for finding objects currently on physical exhibit at Smithsonian museums. This is a priority feature aligned with the Smithsonian's official API documentation.

### Key Features

- **Find Exhibited Objects**: Search for objects currently on display
- **Check Exhibition Status**: Verify if specific objects are on view
- **Filter by Museum**: Find what's on display at specific Smithsonian units
- **Exhibition Details**: Access exhibition title and location information
- **Combined Filters**: Mix on-view status with other search criteria

### Usage Examples

**Find all objects currently on view:**
```python
# Ask Claude:
"What objects are currently on physical exhibit at the Smithsonian?"

# Or with filters:
"Show me paintings currently on display at the National Portrait Gallery"
```

**Check if a specific object is on view:**
```python
# Ask Claude:
"Is object edanmdm-nmah_1234567 currently on display?"
```

**Combine with other filters:**
```python
# Ask Claude:
"Find CC0 licensed objects currently on view with high-resolution images"
```

### Tool Details

#### `get_objects_on_view`
Find objects currently on physical exhibit.

**Parameters:**
- `unit_code` (optional): Filter by Smithsonian unit (e.g., "NMNH", "NPG")
- `limit`: Maximum results (default: 20, max: 100)
- `offset`: Pagination offset

**Returns:** Search results containing objects currently on exhibit

#### `check_object_on_view`
Check if a specific object is currently on display.

**Parameters:**
- `object_id`: Unique identifier for the object

**Returns:** Object details including exhibition status

#### `search_collections` (enhanced)
Now includes `on_view` parameter for filtering.

**New Parameter:**
- `on_view` (boolean): Filter objects by exhibition status
  - `True`: Only objects currently on display
  - `False`: Only objects not on display
  - `None`: No filter (default)

### Implementation Notes

This feature is based on the Smithsonian's `onPhysicalExhibit` metadata field, which indicates whether an object is currently accessible to the public in a physical exhibition. The implementation includes:

- Full API alignment with EDAN metadata model v1.09
- Fielded search support using `onPhysicalExhibit:"Yes"` queries
- Comprehensive test coverage (15 unit tests)
- Exhibition metadata extraction (title, location)

## Use Cases

### Research & Education

- **Scholarly Research**: Multi-step academic investigation
- **Lesson Planning**: Educational content creation
- **Object Analysis**: In-depth cultural object study

### Curation & Exhibition

- **Exhibition Planning**: Thematic object selection and visitor planning
- **Visit Planning**: ⭐ **NEW** - Find what's currently on display before visiting
- **Exhibition Research**: ⭐ **NEW** - Study current exhibition trends and displays
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

### Common Issues

**"API key validation failed"**

- Get a free key from [api.data.gov/signup](https://api.data.gov/signup/)
- Ensure no extra spaces in your API key
- Check that `.env` file contains: `SMITHSONIAN_API_KEY=your_key_here`

**"Service failed to start"**

- Run `python scripts/verify-setup.py` for diagnostics
- Check logs: `journalctl --user -u smithsonian-mcp` (Linux) or `~/Library/Logs/com.smithsonian.mcp.log` (macOS)
- Ensure virtual environment is activated

**"Claude Desktop not connecting"**

- Restart Claude Desktop after configuration
- Check Claude Desktop config file exists and contains correct paths
- Verify MCP server is running: `python -m smithsonian_mcp.server`

**"Module import errors"**

- Activate virtual environment: `source .venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\Activate.ps1` (Windows)
- Reinstall dependencies: `pip install -r requirements.txt`

### Getting Help

1. Run verification script: `python scripts/verify-setup.py`
2. Check the [Integration Guide](INTEGRATION_GUIDE.md)
3. Review [GitHub Issues](https://github.com/molanojustin/smithsonian-mcp/issues)

## Documentation

- **Integration Guide**: Claude Desktop and VS Code setup
- **API Reference**: Complete tool and resource documentation
- **Examples**: Real-world usage scenarios
- **Deployment Guide**: Production deployment options

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
