# Smithsonian Open Access MCP Server

A **Model Context Protocol (MCP)** server that provides AI assistants with access to the **Smithsonian Institution's Open Access collections**. This server allows AI tools like Claude Desktop to search, explore, and analyze over 3 million collection objects from America's national museums.

## Quick Start

### Automated Setup (Recommended)

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

### Manual Setup

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
- **Image Access**: High-resolution images (CC0 licensed when available)
- **3D Models**: Interactive 3D content where available
- **Museum Information**: Browse all Smithsonian institutions

### AI Integration
- **9 MCP Tools**: Search, filter, retrieve collection data, and get context
- **Smart Context**: Contextual data sources for AI assistants  
- **Rich Metadata**: Complete object information and statistics

## Integration

### Claude Desktop

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

*Or copy the provided `claude-desktop-config.json` and update the API key*

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

### VS Code

1. **Open Workspace**: `code smithsonian-mcp-workspace.code-workspace`
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
- `search_collections` - Advanced search with filters
- `get_object_details` - Detailed object information
- `search_by_unit` - Museum-specific searches

### Information & Context
- `get_smithsonian_units` - List all museums
- `get_collection_statistics` - Collection metrics
- `get_search_context` - Get search results as context data
- `get_object_context` - Get detailed object information as context
- `get_units_context` - Get list of units as context data
- `get_stats_context` - Get collection statistics as context

## Use Cases

### Research & Education
- **Scholarly Research**: Multi-step academic investigation
- **Lesson Planning**: Educational content creation
- **Object Analysis**: In-depth cultural object study

### Curation & Exhibition
- **Exhibition Planning**: Thematic object selection
- **Collection Development**: Gap analysis and acquisition
- **Digital Humanities**: Large-scale analysis projects

### Development
- **Cultural Apps**: Applications using museum data
- **Educational Tools**: Interactive learning platforms
- **API Integration**: Professional development workflows

## Requirements

- Python 3.10 or higher
- API key from [api.data.gov](https://api.data.gov/signup/) (free)
- Internet connection for API access

## Testing

```bash
# Test API connection
python examples/test-api-connection.py

# Run MCP server
python -m smithsonian_mcp.server

# Run test suite
pytest tests/

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
