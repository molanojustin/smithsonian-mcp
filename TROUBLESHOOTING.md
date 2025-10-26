# Smithsonian MCP Server - Troubleshooting Guide

This guide covers common issues and solutions for the Smithsonian Open Access MCP Server.

## Common Issues

### API Key Problems

**"API key validation failed"**

- Get a free key from [api.data.gov/signup](https://api.data.gov/signup/)
- Ensure no extra spaces in your API key
- Check that `.env` file contains: `SMITHSONIAN_API_KEY=your_key_here`

**Steps to verify your API key:**
1. Visit [api.data.gov/signup](https://api.data.gov/signup/)
2. Sign up for a free account
3. Copy the API key exactly as provided
4. Add it to your `.env` file without quotes or spaces

### Search Filter Errors

**"HTTP 400 error ... indexed_structured_data.name"**

- Older builds sent maker filters to a non-existent field (`indexed_structured_data.name`)
- The Smithsonian API expects maker facets under `indexedStructured.name`
- Upgrade to the latest server build so the corrected facet name is used automatically
- Re-run your maker search; the API should now accept the corrected filter

### Understanding Museum Collections and Object Types

**"What types of objects are available in each museum?"**

The Smithsonian Open Access API provides access to diverse collections across all Smithsonian museums, with each institution having unique object types. Use the discovery tools to explore what's available:

1. **Discover museum collections**: Use `get_museum_collection_types()` to see what types of objects each museum has in their Open Access collections
2. **Check specific object types**: Use `check_museum_has_object_type(museum_code, object_type)` to verify if a museum has specific types like "paintings", "aircraft", or "historical artifacts"
3. **Understand museum focus**: Each museum's collection reflects its institutional mission:
   - **SAAM**: American art and decorative arts
   - **NASM**: Aviation and space artifacts
   - **NMAH**: American history and technology
   - **CHNDM**: Design and decorative arts

**Example workflow:**
- First: Call `get_museum_collection_types()` to discover available object types across museums
- Then: Use `check_museum_has_object_type("NASM", "aircraft")` to verify aviation artifacts
- Finally: Search with informed expectations based on each museum's collection focus

### Service Startup Issues

**"Service failed to start"**

- Run `python scripts/verify-setup.py` for diagnostics
- Check logs:
  - Linux: `journalctl --user -u smithsonian-mcp`
  - macOS: `~/Library/Logs/com.smithsonian.mcp.log`
- Ensure virtual environment is activated
- Verify all dependencies are installed: `uv pip install -r config/requirements.txt`

**Python environment issues:**
- Activate virtual environment: `source .venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\Activate.ps1` (Windows)
- Check Python version: `python --version` (must be 3.10+)
- Reinstall dependencies: `uv pip install -r config/requirements.txt`

### Claude Desktop Connection Issues

**"Claude Desktop not connecting"**

- Restart Claude Desktop after configuration
- Check Claude Desktop config file exists and contains correct paths
- Verify MCP server is running: `python -m smithsonian_mcp.server`
- Check that the config file is properly formatted JSON

### Module Import Errors

**"Module import errors"**

- Activate virtual environment: `source .venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\Activate.ps1` (Windows)
- Reinstall dependencies: `uv pip install -r config/requirements.txt`
- Check Python path issues in your configuration

### mcpo-Specific Issues

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
config/setup.sh  # Will create examples/mcpo-config.json with correct paths
```

**"Connection closed" errors with mcpo**

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

## Getting Help

1. **Run verification script**: `python scripts/verify-setup.py`
2. **Review [GitHub Issues](https://github.com/molanojustin/smithsonian-mcp/issues)**
3. **Check the documentation**:
   - This troubleshooting guide
   - [README.md](README.md) for setup instructions

## Diagnostic Commands

**Test API connection:**
```bash
python examples/test-api-connection.py
```

**Test MCP server:**
```bash
python -m smithsonian_mcp.server --test
```

**Verify complete setup:**
```bash
python scripts/verify-setup.py
```

**Check service status:**
```bash
# Linux
systemctl --user status smithsonian-mcp

# macOS
launchctl list | grep com.smithsonian.mcp

# Windows PowerShell
Get-Service SmithsonianMCP
```

## Environment Variables

**For debugging:**
- `LOG_LEVEL=DEBUG` - Enable verbose logging
- `ENABLE_CACHE=true` - Caching (default: true)
- `DEFAULT_RATE_LIMIT=60` - Requests/minute (default: 60)

**To set environment variables:**
```bash
# Linux/macOS
export LOG_LEVEL=DEBUG

# Windows PowerShell
$env:LOG_LEVEL = "DEBUG"
```

## Platform-Specific Notes

### Linux
- Services run under user systemd (`systemctl --user`)
- Config files: `~/.config/systemd/user/`
- Logs: `journalctl --user -u smithsonian-mcp`

### macOS
- Uses launchd for services
- Config files: `~/Library/LaunchAgents/`
- Logs: `~/Library/Logs/com.smithsonian.mcp.log`

### Windows
- PowerShell script for setup
- Services managed through PowerShell
- Run setup with: `.\setup.ps1`
