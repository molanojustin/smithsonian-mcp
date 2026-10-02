"""Smoke test an MCP server in streamable HTTP mode.

Usage:
    python .github/scripts/http_smoke.py <command> [args...]

Every "{port}" in the arguments is replaced with a free local port, for example:

    python .github/scripts/http_smoke.py smithsonian-mcp --transport http --port {port}
    python .github/scripts/http_smoke.py docker run --rm -p 127.0.0.1:{port}:8000 \\
        -e MCP_TRANSPORT=http -e SMITHSONIAN_API_KEY smithsonian-mcp

Starts the command, waits for http://127.0.0.1:<port>/mcp to accept
connections, performs an MCP initialize handshake followed by tools/list, then
sends SIGINT and waits for the process to exit. The test fails if:

- the server does not accept connections within START_TIMEOUT_SECONDS,
- either request fails or tools/list returns no tools,
- the server writes anything to stdout (logs belong on stderr),
- the server does not exit within EXIT_TIMEOUT_SECONDS after SIGINT, or exits
  with a non-zero code.

Only the standard library is used, so this runs on a bare CI Python. The
server's stderr is passed through for debugging.
"""

import json
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# Generous, because a container or a first start can be slow.
START_TIMEOUT_SECONDS = 120
REQUEST_TIMEOUT_SECONDS = 60
EXIT_TIMEOUT_SECONDS = 60
PROTOCOL_VERSION = "2025-06-18"

# Talk to the local server directly, whatever proxy the environment configures.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class SmokeTestFailure(Exception):
    """Raised when the server under test misbehaves."""


def _free_port() -> int:
    """Return a TCP port on 127.0.0.1 that is free right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(url: str, proc: subprocess.Popen) -> None:
    """Wait until the endpoint answers HTTP, failing if the process exits."""
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise SmokeTestFailure(f"server exited with code {proc.returncode}")
        try:
            # Any HTTP answer, even an error status, means the server is up.
            with _OPENER.open(url, timeout=2):
                return
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise SmokeTestFailure(f"no answer from {url} within {START_TIMEOUT_SECONDS}s")


def _post(
    url: str, message: Dict[str, Any], session_id: Optional[str]
) -> Tuple[int, Dict[str, str], Optional[Dict[str, Any]]]:
    """
    POST one JSON-RPC message and return the status, headers and response.

    The response is read from a JSON body or from the data lines of a
    text/event-stream body. Notifications get no response.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": PROTOCOL_VERSION,
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(
        url, data=json.dumps(message).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with _OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as reply:
            status = reply.status
            reply_headers = {key.lower(): value for key, value in reply.headers.items()}
            body = reply.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise SmokeTestFailure(
            f"{message.get('method')} returned HTTP {exc.code}: {exc.read()[:200]!r}"
        ) from exc

    if "id" not in message:
        return status, reply_headers, None
    if reply_headers.get("content-type", "").startswith("text/event-stream"):
        for line in body.splitlines():
            if not line.startswith("data:"):
                continue
            data = json.loads(line[len("data:") :].strip())
            if isinstance(data, dict) and data.get("id") == message["id"]:
                return status, reply_headers, data
        raise SmokeTestFailure(f"no response to {message.get('method')} in the stream")
    return status, reply_headers, json.loads(body)


def _handshake(url: str) -> Dict[str, Any]:
    """Run initialize and tools/list, returning a summary of the results."""
    _, headers, init = _post(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "ci-http-smoke-test", "version": "0"},
            },
        },
        None,
    )
    if not init or "result" not in init:
        raise SmokeTestFailure(f"initialize returned an error: {init}")
    session_id = headers.get("mcp-session-id")

    _post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, session_id)
    _, _, tools_response = _post(
        url,
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        session_id,
    )
    if not tools_response or "result" not in tools_response:
        raise SmokeTestFailure(f"tools/list returned an error: {tools_response}")

    return {
        "server": init["result"].get("serverInfo", {}),
        "protocol": init["result"].get("protocolVersion"),
        "session": bool(session_id),
        "tools": tools_response["result"].get("tools", []),
    }


def _stop(proc: subprocess.Popen) -> Optional[int]:
    """Send SIGINT and wait for the process to exit; None on timeout."""
    proc.send_signal(signal.SIGINT)
    try:
        return proc.wait(timeout=EXIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        return None


def main() -> int:
    """Run the smoke test and return a process exit code."""
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    port = _free_port()
    command = [arg.replace("{port}", str(port)) for arg in sys.argv[1:]]
    url = f"http://127.0.0.1:{port}/mcp"
    print(f"command: {' '.join(command)}")

    with tempfile.TemporaryFile() as stdout_file:
        proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stdout_file)
        try:
            _wait_for_server(url, proc)
            result = _handshake(url)
        except (SmokeTestFailure, OSError, ValueError) as exc:
            if proc.poll() is None:
                _stop(proc)
            print(f"FAIL: {exc}")
            return 1
        exit_code = _stop(proc)
        stdout_file.seek(0)
        stdout = stdout_file.read()

    failures: List[str] = []
    if exit_code is None:
        failures.append(f"server did not exit within {EXIT_TIMEOUT_SECONDS}s")

    server = result["server"]
    print(f"server: {server.get('name')} {server.get('version')}")
    print(f"protocol: {result['protocol']}")
    print(f"session id: {'yes' if result['session'] else 'no'}")
    print(f"tools: {len(result['tools'])}")
    print(f"stdout bytes: {len(stdout)}")
    print(f"exit code after SIGINT: {'timeout' if exit_code is None else exit_code}")

    if stdout:
        print(f"  stdout: {stdout[:200]!r}")
        failures.append("output on stdout")
    if not result["tools"]:
        failures.append("tools/list returned no tools")
    if exit_code is not None and exit_code != 0:
        failures.append(f"server exited with code {exit_code}")

    if failures:
        print("FAIL: " + "; ".join(failures))
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
