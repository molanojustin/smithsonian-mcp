"""Smoke test an MCP stdio entry point.

Usage:
    python .github/scripts/stdio_smoke.py <command> [args...]

Starts the command, performs an MCP initialize handshake followed by
tools/list, then closes stdin and waits for the process to exit. The test
fails if:

- the server does not answer either request within RESPONSE_TIMEOUT_SECONDS,
- tools/list returns no tools,
- anything written to stdout is not a JSON-RPC 2.0 message (stdout is
  reserved for the protocol in stdio mode),
- the server does not exit within EXIT_TIMEOUT_SECONDS after stdin closes,
  or exits with a non-zero code.

Only the standard library is used, so this runs on a bare CI Python. The
server's stderr is passed through for debugging.
"""

import json
import queue
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

# Generous, because the first start may install dependencies.
RESPONSE_TIMEOUT_SECONDS = 300
EXIT_TIMEOUT_SECONDS = 60


class SmokeTestFailure(Exception):
    """Raised when the server under test misbehaves."""


def _reader(stream: Any, lines: "queue.Queue[Optional[bytes]]") -> None:
    """Forward stdout lines from the child into a queue until EOF."""
    for raw in iter(stream.readline, b""):
        lines.put(raw)
    lines.put(None)


def _send(proc: subprocess.Popen, message: Dict[str, Any]) -> None:
    """Write one JSON-RPC message to the child's stdin."""
    proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    proc.stdin.flush()


def _wait_for_id(
    lines: "queue.Queue[Optional[bytes]]", seen: List[bytes], request_id: int
) -> Dict[str, Any]:
    """Collect stdout lines until the response with the given id arrives."""
    while True:
        try:
            raw = lines.get(timeout=RESPONSE_TIMEOUT_SECONDS)
        except queue.Empty as exc:
            raise SmokeTestFailure(
                f"no response to id {request_id} within {RESPONSE_TIMEOUT_SECONDS}s"
            ) from exc
        if raw is None:
            lines.put(None)  # keep the end-of-output marker for _drain()
            raise SmokeTestFailure(f"server closed stdout before answering id {request_id}")
        seen.append(raw)
        try:
            message = json.loads(raw)
        except ValueError:
            continue
        if isinstance(message, dict) and message.get("id") == request_id:
            return message


def _drain(lines: "queue.Queue[Optional[bytes]]", seen: List[bytes]) -> None:
    """Collect any remaining stdout lines after the child has exited."""
    while True:
        try:
            raw = lines.get(timeout=10)
        except queue.Empty:
            return
        if raw is None:
            return
        seen.append(raw)


def _stray_lines(seen: List[bytes]) -> List[bytes]:
    """Return stdout lines that are not JSON-RPC 2.0 messages."""
    stray = []
    for raw in seen:
        try:
            message = json.loads(raw)
        except ValueError:
            stray.append(raw)
            continue
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            stray.append(raw)
    return stray


def _handshake(
    proc: subprocess.Popen, lines: "queue.Queue[Optional[bytes]]", seen: List[bytes]
) -> Dict[str, Any]:
    """Run initialize and tools/list, returning a summary of the results."""
    _send(
        proc,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "ci-smoke-test", "version": "0"},
            },
        },
    )
    init = _wait_for_id(lines, seen, 1)
    if "result" not in init:
        raise SmokeTestFailure(f"initialize returned an error: {init.get('error')}")

    _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools_response = _wait_for_id(lines, seen, 2)
    if "result" not in tools_response:
        raise SmokeTestFailure(f"tools/list returned an error: {tools_response.get('error')}")

    return {
        "server": init["result"].get("serverInfo", {}),
        "protocol": init["result"].get("protocolVersion"),
        "tools": tools_response["result"].get("tools", []),
    }


def main() -> int:
    """Run the smoke test and return a process exit code."""
    command = sys.argv[1:]
    if not command:
        print(__doc__, file=sys.stderr)
        return 2

    proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    lines: "queue.Queue[Optional[bytes]]" = queue.Queue()
    threading.Thread(target=_reader, args=(proc.stdout, lines), daemon=True).start()
    seen: List[bytes] = []
    failures: List[str] = []

    try:
        result = _handshake(proc, lines, seen)
    except (SmokeTestFailure, OSError) as exc:
        proc.kill()
        proc.wait()
        _drain(lines, seen)
        for raw in _stray_lines(seen)[:5]:
            print(f"  stray stdout: {raw[:200]!r}")
        print(f"FAIL: {exc}")
        return 1

    proc.stdin.close()
    try:
        exit_code: Optional[int] = proc.wait(timeout=EXIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        exit_code = None
        failures.append(f"server did not exit within {EXIT_TIMEOUT_SECONDS}s after stdin closed")
    _drain(lines, seen)

    stray = _stray_lines(seen)
    server = result["server"]
    print(f"server: {server.get('name')} {server.get('version')}")
    print(f"protocol: {result['protocol']}")
    print(f"tools: {len(result['tools'])}")
    print(f"stdout lines: {len(seen)}, non-JSON-RPC lines: {len(stray)}")
    print(f"exit code after stdin closed: {'timeout' if exit_code is None else exit_code}")
    for raw in stray[:5]:
        print(f"  stray stdout: {raw[:200]!r}")

    if stray:
        failures.append("non-JSON-RPC output on stdout")
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
