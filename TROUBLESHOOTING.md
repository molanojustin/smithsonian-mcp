# Smithsonian MCP Server - Troubleshooting Guide

This guide covers common problems with the Smithsonian Open Access MCP server and how to fix them.

## Contents

- [API key and rate limits](#api-key-and-rate-limits)
- [Searches](#searches)
- [Upgrading from 1.x](#upgrading-from-1x)
- [Setup and connection](#setup-and-connection)
- [mcpo](#mcpo)
- [Diagnostic commands](#diagnostic-commands)
- [Environment variables](#environment-variables)
- [Platform notes](#platform-notes)
- [Getting help](#getting-help)

## API key and rate limits

### API key rejected or missing

The server exits at startup with "API key not configured", or requests fail with "The API key was rejected".

- Get a free key from [api.data.gov/signup](https://api.data.gov/signup/).
- Set `SMITHSONIAN_API_KEY` in the `env` block of your MCP client configuration. When you run the server from a clone, it can also come from `.env` in the project root: `SMITHSONIAN_API_KEY=your_key_here`, with no quotes or spaces. A key in the client's `env` block takes precedence.
- Restart the MCP client after changing the key.
- Check the key with `smithsonian-mcp --test` (npm install) or `uv run smithsonian-mcp --test` (local clone).

### Rate limit exceeded (HTTP 429)

api.data.gov allows 1,000 requests per hour for each API key, counted over a rolling hour. Past the limit the API answers HTTP 429, and the response's `Retry-After` header gives the number of seconds to wait.

- Wait for the time in `Retry-After`, then try again. Retrying sooner gets another 429.
- Each tool call makes one or a few requests, and everything that uses the key shares the limit: several MCP clients, an mcpo service, scripts and the live tests.
- To see how many requests remain, read the `X-RateLimit-Remaining` header of any response. This makes one request:

```bash
curl -s -o /dev/null -D - -H "X-Api-Key: $SMITHSONIAN_API_KEY" \
  "https://api.si.edu/openaccess/api/v1.0/terms/unit_code" | grep -i ratelimit
```

## Searches

### The query was rejected

The error says "The Smithsonian API rejected this query text; rephrase it with plain keywords".

A firewall in front of the API blocks query text that looks like SQL, HTML or script tags, or file paths, such as `' OR 1=1 --`, `<script>` or `../`. This is not an API key problem. Search again with plain keywords.

### A search returns nothing

- Every word in `query` must match, so a full question or sentence usually finds nothing. Use 1 to 4 distinctive keywords, `OR` for alternatives, and `maker` for names. See [Search tips](README.md#search-tips).
- 14 units, such as the Archives of American Art, publish only archival records, which object searches do not return. `list_museums` marks them.
- A museum name the server does not recognize returns an error that lists the known names. `list_museums` shows every name and code.
- Dates must be years from 1000 to 2999. Other values, such as "19th century", return an error that names the accepted format.

### An on-view search at Natural History is empty

`search_objects(on_view=true, museum="Natural History")` always returns nothing. The National Museum of Natural History publishes no exhibit data to Open Access, so the API cannot tell which of its objects are on display. This is a gap in the data, not a server fault, and the result's `note` says so. Check the museum's website for current exhibits.

### Objects come back without images

Some museums show images on their own websites under usage conditions that Open Access does not publish. The Elmo puppet at American History is an example: its record has no images, so `thumbnail_url` is `null` and `images` is empty. Some records, notably at American History, also match `has_images=true` without carrying image URLs. Other museums, such as Asian Art and Cooper Hewitt, publish images with many of their records.

## Upgrading from 1.x

### My old tool names stopped working

Version 2.0 replaced the 28 tools of 1.x with 5, so a call such as `get_object_details` or `get_objects_on_view` fails with an unknown tool error. The [migration table](README.md#removed-tools) lists the replacement for each old tool. Update saved prompts, scripts and mcpo endpoint URLs to match.

If you cannot migrate yet, you can pin 1.2.9, for example with `npx -y @molanojustin/smithsonian-mcp@1.2.9` or by appending `@v1.2.9` to the uvx `--from` URL. Version 1.2.9 has the bugs listed in the [changelog](CHANGELOG.md), including search filters that are ignored and an API key that can appear in logs.

### The new tools do not appear

The client is still running a 1.x build. Listing the tools (see [Diagnostic commands](#diagnostic-commands)) shows 28 tools instead of 5.

- uvx caches builds. Run `uvx --refresh --from git+https://github.com/molanojustin/smithsonian-mcp smithsonian-mcp` once in a terminal, then restart the client.
- With npx, check that the configuration does not pin an old version.
- With a local clone, pull the latest changes and run `uv sync`.

## Setup and connection

### Claude Desktop does not connect

- Restart Claude Desktop after changing its configuration.
- Check that the configuration file is valid JSON and contains correct paths.
- Claude Desktop starts the server itself; you do not need to run it separately.
- If the log says `uvx`, `uv` or `npx` was not found, use the absolute path to the command (`which uvx` on macOS/Linux, `where uvx` on Windows).
- Check that the server starts from a terminal with the same command and arguments as in the configuration, for example `uvx --from git+https://github.com/molanojustin/smithsonian-mcp smithsonian-mcp`. It should start and wait for input; press Ctrl+C to stop it.

### The server starts and exits immediately

Versions before 2.0 exited at once when started with `python -m smithsonian_mcp.server`; use the `smithsonian-mcp` command.

### The client reports invalid JSON or fails during the handshake

In stdio mode, stdout carries only MCP messages. Wrapper scripts or shell profiles that print to stdout corrupt the stream; send any diagnostics to stderr.

### Module import errors

- Install the package into the project environment: `uv sync` (or `pip install -e .` in a virtual environment).
- Point MCP clients at the installed `smithsonian-mcp` command, or use `uv --directory /path/to/smithsonian-mcp run smithsonian-mcp`.
- Check Python path settings in your configuration.

### Python environment issues

- Run commands through the project environment: `uv run <command>`, or activate it with `source .venv/bin/activate` (Linux/macOS) or `.\.venv\Scripts\Activate.ps1` (Windows).
- Check the Python version: `uv run python --version` (must be 3.10 or newer).
- Reinstall dependencies and the package: `uv sync`.

### A background service fails to start or keeps restarting

- The server uses the stdio transport and exits when no MCP client is attached, so a background service restarts repeatedly. MCP clients such as Claude Desktop start the server themselves. For a long-running HTTP service, run the server behind mcpo (see [README.md](README.md#mcpo-integration-mcp-orchestrator)).
- Run `uv run python scripts/verify-setup.py` for diagnostics.
- Check the logs:
  - Linux: `journalctl --user -u smithsonian-mcp`
  - macOS: `~/Library/Logs/com.smithsonian.mcp.log`
- Check that the package and its dependencies are installed: `uv sync`.

## mcpo

### ModuleNotFoundError: No module named 'smithsonian_mcp'

mcpo cannot find the Smithsonian MCP module. To fix it:

1. Use the absolute path to the installed command in your mcpo configuration:

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

2. Check the paths:

```bash
# Check that the Python executable exists
ls -la /path/to/your/project/.venv/bin/python

# Test the module import
/path/to/your/project/.venv/bin/python -c "import smithsonian_mcp; print('OK')"
```

3. Regenerate the configuration with the setup script:

```bash
config/setup.sh  # Writes mcpo-config.json in the project root with correct paths
```

### Connection closed errors

- Check that the API key is valid and set in the environment.
- Check that the virtual environment has all dependencies installed.
- Check the API connection: `uv run python examples/test-api-connection.py`.
- Check that the server starts: `uv run smithsonian-mcp` should start and wait for input (Ctrl+C to stop).

### Port 8000 already in use

```bash
# Check what is using the port
lsof -i :8000
# Or use a different port
mcpo --config mcpo-config.json --port 8001
```

## Diagnostic commands

Test the API connection:

```bash
uv run python examples/test-api-connection.py
```

List the server's tools through the MCP Inspector CLI. A 2.0 build lists five tools:

```bash
npx @modelcontextprotocol/inspector --cli .venv/bin/smithsonian-mcp --method tools/list
```

Verify the complete setup:

```bash
uv run python scripts/verify-setup.py
```

Check the service status:

```bash
# Linux
systemctl --user status smithsonian-mcp

# macOS
launchctl list | grep com.smithsonian.mcp

# Windows PowerShell
Get-Service SmithsonianMCP
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SMITHSONIAN_API_KEY` | none | API key from api.data.gov. Required. |
| `LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING` or `ERROR`. Logs go to stderr. |
| `SERVER_NAME` | `Smithsonian Open Access` | Server name reported to MCP clients. |

To set a variable for a terminal session:

```bash
# Linux/macOS
export LOG_LEVEL=DEBUG

# Windows PowerShell
$env:LOG_LEVEL = "DEBUG"
```

## Platform notes

### Linux

- Services run under user systemd (`systemctl --user`).
- Unit files: `~/.config/systemd/user/`
- Logs: `journalctl --user -u smithsonian-mcp`

### macOS

- Services run under launchd.
- Agent files: `~/Library/LaunchAgents/`
- Logs: `~/Library/Logs/com.smithsonian.mcp.log`

### Windows

- Setup uses a PowerShell script. Run it from the project root with `config\setup.ps1`.
- The installed command is `.venv\Scripts\smithsonian-mcp.exe`.

## Getting help

1. Run the verification script: `uv run python scripts/verify-setup.py`
2. Search the [GitHub issues](https://github.com/molanojustin/smithsonian-mcp/issues).
3. Read [README.md](README.md) for setup and the tool reference, and [CHANGELOG.md](CHANGELOG.md) for what changed between versions.
