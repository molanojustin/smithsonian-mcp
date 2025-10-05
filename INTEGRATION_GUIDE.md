# Claude Desktop & VS Code Integration Guide

Quick setup guide for integrating the Smithsonian MCP Server.

## Setup Checklist

- [ ] Get API key from api.data.gov
- [ ] Install Python dependencies  
- [ ] Copy `.env.example` to `.env` and configure API key
- [ ] Configure Claude Desktop
- [ ] Test integration

## Claude Desktop Integration

### Step 1: Get Your API Key

1. Sign up at [api.data.gov/signup](https://api.data.gov/signup/)
2. No special permissions needed
3. Save your API key

### Step 2: Configure Claude Desktop

**Config File Locations:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "python",
      "args": ["-m", "smithsonian_mcp.server"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_api_key_here",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

*Or copy the provided `claude-desktop-config.json` and update the API key*

### Step 3: Test Integration

Ask Claude these questions:
1. "What Smithsonian museums are available?"
2. "Search for dinosaur fossils"
3. "Find American paintings from the 1800s"

## VS Code Integration

1. **Open Workspace**: `code smithsonian-mcp-workspace.code-workspace`
2. **Install Dependencies**: Use "Install Dependencies" task
3. **Configure Environment**: Copy `.env.example` to `.env` and set API key
4. **Run Server**: Use "Start MCP Server" task
5. **Test**: Use "Test MCP Server" task to verify API connection
6. **Debug**: Use F5 to debug the server or "Debug with MCP Inspector" task

## mcpo Integration (Advanced)

**mcpo** (MCP Orchestrator) converts multiple MCP servers into HTTP/OpenAPI endpoints, perfect for combining services into a single systemd deployment.

### When to Use mcpo

- **Multiple MCP Services**: Combine Smithsonian with other MCP servers (memory, time, filesystem, etc.)
- **HTTP API Access**: Need REST/OpenAPI endpoints instead of stdio communication
- **Centralized Management**: Single service managing multiple MCP capabilities
- **Production Deployment**: Better suited for production environments than individual stdio services

### Setup Steps

#### 1. Install mcpo
```bash
# Using pip
pip install mcpo

# Or using uvx (recommended)
uvx mcpo --help
```

#### 2. Create mcpo Configuration
Create `mcpo-config.json`:

```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "python",
      "args": ["-m", "smithsonian_mcp.server"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_api_key_here",
        "LOG_LEVEL": "INFO"
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

#### 3. Test mcpo Configuration
```bash
# Test with hot-reload for development
mcpo --config mcpo-config.json --port 8000 --hot-reload

# Test endpoints in another terminal:
curl http://localhost:8000/smithsonian_open_access/search_collections
curl http://localhost:8000/memory/search
curl http://localhost:8000/time/get_current_time

# View auto-generated API docs
open http://localhost:8000/docs
```

#### 4. Production Deployment (systemd)

Create `/etc/systemd/system/mcpo.service`:

```ini
[Unit]
Description=MCP Orchestrator Service
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/your/project
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/mcpo --config /path/to/mcpo-config.json --port 8000
Restart=always
RestartSec=10
EnvironmentFile=/path/to/.env

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable mcpo
sudo systemctl start mcpo
sudo systemctl status mcpo
```

#### 5. Claude Desktop Integration (Optional)

If you still want Claude Desktop access alongside HTTP endpoints, configure it to use mcpo:

```json
{
  "mcpServers": {
    "mcpo_orchestrator": {
      "command": "mcpo",
      "args": ["--config", "/path/to/mcpo-config.json"],
      "env": {
        "MCP_API_KEY": "your_secret_key"
      }
    }
  }
}
```

### mcpo vs Direct Integration

| Feature | Direct MCP | mcpo Integration |
|---------|------------|------------------|
| **Setup** | Simple, single service | More complex, requires config |
| **Performance** | Lower overhead | HTTP overhead, but more scalable |
| **Access** | Claude Desktop only | Any HTTP client |
| **Monitoring** | Limited | Full HTTP monitoring/logging |
| **Security** | Environment variables | API keys, HTTP auth |
| **Production** | Challenging | Production-ready |

### Troubleshooting mcpo

**"mcpo command not found"**
```bash
# Ensure mcpo is installed and in PATH
which mcpo
pip install mcpo
```

**"ModuleNotFoundError: No module named 'smithsonian_mcp'"**
This is the most common issue - mcpo can't find the Smithsonian MCP module:

```bash
# 1. Check your mcpo config uses absolute paths
cat mcpo-config.json | grep "command"

# 2. Verify the Python executable exists
ls -la /path/to/your/project/.venv/bin/python

# 3. Test the module import directly
/path/to/your/project/.venv/bin/python -c "import smithsonian_mcp; print('Module found')"

# 4. Regenerate config with correct paths
./setup.sh  # Choose "y" when asked about mcpo configuration
```

**"Server failed to start"**
```bash
# Check mcpo logs with verbose output
mcpo --config mcpo-config.json --port 8000 --verbose

# Verify individual MCP servers work
python -m smithsonian_mcp.server --test

# Check API key is valid
python examples/test-api-connection.py
```

**"Connection closed" or "ExceptionGroup" errors**
- Ensure API key is set correctly in mcpo config environment
- Check that PYTHONPATH includes your project directory
- Verify all dependencies are installed in the virtual environment

**"Endpoint not accessible"**
```bash
# Check if service is running
curl http://localhost:8000/docs

# Test specific endpoint
curl http://localhost:8000/smithsonian_open_access/search_collections

# Verify systemd service
sudo journalctl -u mcpo -f
```

**"Port 8000 already in use"**
```bash
# Find what's using the port
sudo lsof -i :8000
# Or use different port
mcpo --config mcpo-config.json --port 8001
```

## Testing

### Quick Test
Run the test script:
```bash
python examples/test-api-connection.py
```

### VS Code Tasks
- **Test MCP Server**: Tests API connection and basic functionality
- **Run Tests**: Executes the pytest test suite
- **Format Code**: Formats code with Black
- **Lint Code**: Runs Pylint for code quality

### Environment Setup
Ensure your `.env` file contains:
```bash
SMITHSONIAN_API_KEY=your_actual_api_key_here
SERVER_NAME=Smithsonian Open Access
LOG_LEVEL=INFO
```

## Troubleshooting

**"MCP Server not found"**
- Check Python path in configuration
- Verify API key is set
- Restart Claude Desktop

**"API Key Invalid"**  
- Verify key from api.data.gov
- Check environment variable spelling

For detailed instructions, see the full documentation files.
