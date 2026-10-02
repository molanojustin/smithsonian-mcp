# Smithsonian MCP Server - Troubleshooting Guide

This guide covers common problems with the Smithsonian Open Access MCP server and how to fix them.

## Contents

- [API key and rate limits](#api-key-and-rate-limits)
- [Searches](#searches)
- [Upgrading from 1.x](#upgrading-from-1x)
- [Setup and connection](#setup-and-connection)
- [HTTP mode](#http-mode)
- [mcpo](#mcpo)
- [Diagnostic commands](#diagnostic-commands)
- [Environment variables](#environment-variables)
- [Platform notes](#platform-notes)
- [Getting help](#getting-help)

## API key and rate limits

### API key rejected or missing

The server exits at startup with "API key not configured", or tools fail with "The Smithsonian API rejected the API key".

- Get a free key from [api.data.gov/signup](https://api.data.gov/signup/).
- Set `SMITHSONIAN_API_KEY` in the `env` block of your MCP client configuration. When you run the server from a clone, it can also come from `.env` in the project root: `SMITHSONIAN_API_KEY=your_key_here`, with no quotes or spaces. A key in the client's `env` block takes precedence.
- Restart the MCP client after changing the key.
- Check the key with `smithsonian-mcp --test` (npm install) or `uv run smithsonian-mcp --test` (local clone).

### Rate limit exceeded (HTTP 429)

Tools fail with "The Smithsonian API rate limit for this API key was reached".

api.data.gov allows 1,000 requests per hour for each API key, counted over a rolling hour. Past the limit the API answers HTTP 429, and the response's `Retry-After` header gives the number of seconds to wait.

- Wait for the time in `Retry-After`, then try again. Retrying sooner gets another 429.
- Each tool call makes one or a few requests, and everything that uses the key shares the limit: several MCP clients, an mcpo service, scripts and the live tests.
- To see how many requests remain, read the `X-RateLimit-Remaining` header of any response. This makes one request:

```bash
curl -s -o /dev/null -D - -H "X-Api-Key: $SMITHSONIAN_API_KEY" \
  "https://api.si.edu/openaccess/api/v1.0/terms/unit_code" | grep -i ratelimit
```

`list_museums` caches the unit list for the life of the server, and `get_collection_stats` caches its counts for 6 hours per museum, so repeating them costs no further requests.

### The API is not responding

Tools fail with "The Smithsonian API is not responding right now". The request timed out or the API returned a server error. Try again in a few minutes.

## Searches

### The query was rejected

The error says "The Smithsonian API rejected this query text; rephrase it with plain keywords".

A firewall in front of the API blocks query text that looks like SQL, HTML or script tags, or file paths, such as `' OR 1=1 --`, `<script>` or `../`. This is not an API key problem. Search again with plain keywords.

### A search returns nothing

An empty result carries a `note` that explains it. Common causes:

- Every word in `query` must match, so a full question or sentence usually finds nothing, or a few objects that miss the point. Results for a query with a question mark or five or more terms carry a `note` that says so. Use 1 to 4 distinctive keywords, `OR` for alternatives, `maker` for names, and filters such as `museum` and `on_view`. See [Search tips](README.md#search-tips).
- The filters match nothing together. With no `query`, the note lists the filters that were applied, with their values as the server read them, so drop one or broaden it. `maker` matches a full name or a surname; a given name on its own, such as "Winslow", does not match "Homer, Winslow".
- The `offset` is past the last result. The note gives the number of results; start again from `offset=0` or follow `next_offset`.

Some searches return an error instead:

- 14 units, such as the Archives of American Art, publish only archive records, which object searches do not return. An object search limited to one of them returns an error that says to search again with `record_type="archives"`; `list_museums` shows each unit's `record_types`.
- A museum name the server does not recognize returns an error with examples of accepted names, and leaving `museum` out searches every museum. `list_museums` shows every code and its aliases. "Smithsonian" on its own is not an error: it means every museum.
- Years must be from 1000 to 2999, as numbers or as decades such as `"1860s"`. Other values, such as 500 or "the sixties", return an error that names the accepted forms.

### An on-view search at Natural History is empty

`search_objects(on_view=true, museum="Natural History")` always returns nothing. The National Museum of Natural History publishes no exhibit data to Open Access, so the API cannot tell which of its objects are on display. This is a gap in the data, not a server fault, and the result's `note` says so. For the same reason an on-view search without a museum never includes Natural History objects, and its `note` says that too. Check the museum's website for current exhibits.

### Objects come back without images

Some museums show images on their own websites under usage conditions that Open Access does not publish. The Elmo puppet at American History is an example: its record has no images, so results for it have no `thumbnail_url` or `images` field. Some records, notably at American History, also match `has_images=true` without carrying image URLs. Other museums, such as Asian Art and Cooper Hewitt, publish images with many of their records.

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

In stdio mode the server exits when its input closes, so started from a script or service with no MCP client attached it ends at once. That is expected: MCP clients start it themselves. To run it as a standalone server, use `smithsonian-mcp --transport http` (see [HTTP mode](#http-mode)).

Versions before 2.0 also exited at once when started with `python -m smithsonian_mcp.server`; use the `smithsonian-mcp` command.

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

- A service must run the server in HTTP mode. In stdio mode it exits when no MCP client is attached, so the service restarts it in a loop. The setup scripts install services with `--transport http --host 127.0.0.1 --port 8000`; services installed by earlier versions of the scripts lack these arguments, so run the setup script again or add them to the unit, plist or service command line. MCP clients such as Claude Desktop start their own stdio server and do not need a service.
- If the log says the address is already in use, another program (mcpo defaults to port 8000 too) holds the port. Change `--port` in the service definition.
- The service reads the API key from `.env` in the project root. Check that the file sets `SMITHSONIAN_API_KEY` and that the user the service runs as can read it; the setup scripts make it readable by your user only.
- Run `uv run python scripts/verify-setup.py` for diagnostics.
- Check the logs:
  - Linux: `journalctl --user -u smithsonian-mcp`
  - macOS: `~/Library/Logs/com.smithsonian.mcp.log` (the server logs to stderr, and the job sends both output streams to this file)
- Check that the package and its dependencies are installed: `uv sync`.

## HTTP mode

`smithsonian-mcp --transport http` serves MCP at `http://127.0.0.1:8000/mcp`. `--host` and `--port`, or `MCP_HOST` and `MCP_PORT`, change the address. See [HTTP transport](README.md#http-transport).

### The server does not start in HTTP mode

- "address already in use": another program holds the port. Pick another with `--port`, or find it with `lsof -i :8000` (macOS/Linux) or `Get-NetTCPConnection -LocalPort 8000` (Windows).
- "MCP_TRANSPORT must be one of stdio, http" or "MCP_PORT: invalid port": fix the environment variable or the `.env` entry, or override it with `--transport` or `--port`.

### A client cannot connect

- Use the full endpoint URL, including the `/mcp` path, and a client that supports the streamable HTTP transport. Plain HTTP requests such as a browser visit get an error status rather than a page.
- By default the server listens on `127.0.0.1` only, so other machines cannot reach it. To accept remote connections, start it with `--host 0.0.0.0`, and control access in front of it: the endpoint has no authentication and uses your API key.
- "421 Misdirected Request": the request's `Host` header is not an allowed name, which protects against DNS rebinding. The allowed names are `localhost`, `127.0.0.1`, `::1` and the `--host` address, plus the address the connection arrived on. If clients reach the server by another name (a reverse proxy's upstream name, a LAN host name, a container name), add it with `--allowed-hosts` or `MCP_ALLOWED_HOSTS`, for example `MCP_ALLOWED_HOSTS=localhost,127.0.0.1,::1,mcp.example.org`.
- "403 Forbidden Origin": the request comes from a web page on another site. MCP clients that are not browsers send no `Origin` header.
- A server that an MCP client starts itself, such as a Claude Desktop entry, must stay in stdio mode. If its `env` block or `.env` sets `MCP_TRANSPORT=http`, the client finds an HTTP server instead of a stdio one and the connection fails. Add `--transport stdio` to the entry's `args`, as the configurations in the README and those written by the setup scripts do.

### HTTP mode in Docker

The container speaks stdio unless `MCP_TRANSPORT=http` is set, and its port must be published:

```bash
docker run --rm -e SMITHSONIAN_API_KEY -e MCP_TRANSPORT=http -p 127.0.0.1:8000:8000 smithsonian-mcp
```

The endpoint has no authentication, so keep the `127.0.0.1:` prefix unless something else controls access: anyone who can reach the port spends your API key's quota. The image sets `MCP_HOST=0.0.0.0`, because a server listening on 127.0.0.1 inside the container cannot be reached through a published port, and `MCP_ALLOWED_HOSTS=localhost,127.0.0.1,::1`. Requests that name the container by another host name get 421 until that name is added to `MCP_ALLOWED_HOSTS`. Stop the container with Ctrl+C or `docker stop`.

## mcpo

### ModuleNotFoundError: No module named 'smithsonian_mcp'

mcpo cannot find the Smithsonian MCP module. To fix it:

1. Use the absolute path to the installed command in your mcpo configuration:

```json
{
  "command": "/full/path/to/your/project/.venv/bin/smithsonian-mcp",
  "args": ["--transport", "stdio"]
}
```

Or use the Python interpreter with the module entry point:

```json
{
  "command": "/full/path/to/your/project/.venv/bin/python",
  "args": ["-m", "smithsonian_mcp.main", "--transport", "stdio"],
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

For a server running in HTTP mode:

```bash
npx @modelcontextprotocol/inspector --cli http://127.0.0.1:8000/mcp --transport http --method tools/list
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
| `MCP_TRANSPORT` | `stdio` | `stdio`, or `http` for streamable HTTP. `--transport` takes precedence. |
| `MCP_HOST` | `127.0.0.1` | Address to listen on in HTTP mode. `--host` takes precedence. |
| `MCP_PORT` | `8000` | Port to listen on in HTTP mode. `--port` takes precedence. |
| `MCP_ALLOWED_HOSTS` | `localhost,127.0.0.1,::1` and `MCP_HOST` | `Host` header names accepted in HTTP mode, comma-separated. `--allowed-hosts` takes precedence. |

To set a variable for a terminal session:

```bash
# Linux/macOS
export LOG_LEVEL=DEBUG

# Windows PowerShell
$env:LOG_LEVEL = "DEBUG"
```

## Platform notes

### Linux

- Services run under user systemd (`systemctl --user`) and serve HTTP at `http://127.0.0.1:8000/mcp`.
- Unit files: `~/.config/systemd/user/`
- Logs: `journalctl --user -u smithsonian-mcp`

### macOS

- Services run under launchd and serve HTTP at `http://127.0.0.1:8000/mcp`.
- Agent files: `~/Library/LaunchAgents/`
- Logs: `~/Library/Logs/com.smithsonian.mcp.log` (stdout and stderr)

### Windows

- Setup uses a PowerShell script. Run it from the project root with `config\setup.ps1`.
- The installed command is `.venv\Scripts\smithsonian-mcp.exe`.

## Getting help

1. Run the verification script: `uv run python scripts/verify-setup.py`
2. Search the [GitHub issues](https://github.com/molanojustin/smithsonian-mcp/issues).
3. Read [README.md](README.md) for setup and the tool reference, and [CHANGELOG.md](CHANGELOG.md) for what changed between versions.
