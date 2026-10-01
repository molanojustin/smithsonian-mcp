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

**"Service failed to start" or keeps restarting**

- The server uses the stdio transport and exits when no MCP client is attached, so a background service restarts repeatedly. MCP clients such as Claude Desktop start the server themselves. For a long-running HTTP service, run the server behind mcpo (see README.md).
- Run `uv run python scripts/verify-setup.py` for diagnostics
- Check logs:
  - Linux: `journalctl --user -u smithsonian-mcp`
  - macOS: `~/Library/Logs/com.smithsonian.mcp.log`
- Verify the package and its dependencies are installed: `uv sync`

**Python environment issues:**
- Run commands through the project environment: `uv run <command>`, or activate it with `source .venv/bin/activate` (Linux/macOS) or `.\.venv\Scripts\Activate.ps1` (Windows)
- Check Python version: `uv run python --version` (must be 3.10+)
- Reinstall dependencies and the package: `uv sync`

### Claude Desktop Connection Issues

**"Claude Desktop not connecting"**

- Restart Claude Desktop after configuration
- Check Claude Desktop config file exists and contains correct paths
- Claude Desktop starts the server itself; you do not need to run it separately
- If the log says `uvx`, `uv` or `npx` was not found, use the absolute path to the command (`which uvx` on macOS/Linux, `where uvx` on Windows)
- Check that the server starts from a terminal with the same command and arguments as in the config, for example `uvx --from git+https://github.com/molanojustin/smithsonian-mcp smithsonian-mcp`. It should start and wait for input; press Ctrl+C to stop it
- Check that the config file is properly formatted JSON

**Server starts and exits immediately with no error**

- In older versions, `python -m smithsonian_mcp.server` exited immediately without serving. Use the `smithsonian-mcp` command (or `python -m smithsonian_mcp.main`) instead

**Client reports invalid JSON or fails during the handshake**

- In stdio mode, stdout carries only MCP messages. Wrapper scripts or shell profiles that print to stdout corrupt the stream; send any diagnostics to stderr

### Module Import Errors

**"Module import errors"**

- Install the package into the project environment: `uv sync` (or `pip install -e .` in a virtual environment)
- Point MCP clients at the installed `smithsonian-mcp` command, or use `uv --directory /path/to/smithsonian-mcp run smithsonian-mcp`
- Check Python path issues in your configuration

### mcpo-Specific Issues

**"ModuleNotFoundError: No module named 'smithsonian_mcp'"**

This occurs when mcpo can't find the Smithsonian MCP module. Fix by:

1. **Use the absolute path to the installed command** in your mcpo config:

```json
{
  "command": "/full/path/to/your/project/.venv/bin/smithsonian-mcp",
  "args": []
}
```

Or use the Python interpreter with the module entry point:

```json
{
  "command": "/full/path/to/your/project/.venv/bin/python",
  "args": ["-m", "smithsonian_mcp.main"],
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
config/setup.sh  # Writes mcpo-config.json in the project root with correct paths
```

**"Connection closed" errors with mcpo**

- Ensure API key is valid and set in environment
- Check that the virtual environment has all dependencies installed
- Verify the API connection: `uv run python examples/test-api-connection.py`
- Verify the server starts: `uv run smithsonian-mcp` should start and wait for input (Ctrl+C to stop)

**"Port 8000 already in use"**

```bash
# Check what's using the port
lsof -i :8000
# Or use different port
mcpo --config mcpo-config.json --port 8001
```

## Getting Help

1. **Run verification script**: `uv run python scripts/verify-setup.py`
2. **Review [GitHub Issues](https://github.com/molanojustin/smithsonian-mcp/issues)**
3. **Check the documentation**:
   - This troubleshooting guide
   - [README.md](README.md) for setup instructions

## Diagnostic Commands

**Test API connection:**
```bash
uv run python examples/test-api-connection.py
```

**Test MCP server:**
```bash
# Lists the server's tools through the MCP Inspector CLI
npx @modelcontextprotocol/inspector --cli .venv/bin/smithsonian-mcp --method tools/list
```

**Verify complete setup:**
```bash
uv run python scripts/verify-setup.py
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
- The installed command is `.venv\Scripts\smithsonian-mcp.exe`
- Run setup from the project root with: `config\setup.ps1`
