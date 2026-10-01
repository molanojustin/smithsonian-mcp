"""Smoke test an MCP stdio entry point.

Usage:
    python .github/scripts/stdio_smoke.py <command> [args...]

Starts the command, performs an MCP initialize handshake followed by
tools/list, then closes stdin and waits for the process to exit. The test
fails if the server does not answer, returns no tools, or writes anything to
stdout that is not a JSON-RPC 2.0 message (stdout is reserved for the protocol
in stdio mode).

Only the standard library is used, so this runs on a bare CI Python. The
server's stderr is passed through for debugging.
"""

import json
import queue
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

TIMEOUT_SECONDS = 300


def _reader(stream: Any, lines: "queue.Queue[Optional[bytes]]") -> None:
    """Forward stdout lines from the child into a queue until EOF."""
    for raw in iter(stream.readline, b""):
        lines.put(raw)
    lines.put(None)


def _send(proc: subprocess.Popen, message: Dict[str, Any]) -> None:
    proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
    proc.stdin.flush()


def _wait_for_id(
    lines: "queue.Queue[Optional[bytes]]", seen: List[bytes], request_id: int
) -> Dict[str, Any]:
    """Collect stdout lines until the response with the given id arrives."""
    while True:
        raw = lines.get(timeout=TIMEOUT_SECONDS)
        if raw is None:
            raise SystemExit(f"FAIL: server closed stdout before answering id {request_id}")
        seen.append(raw)
        try:
            message = json.loads(raw)
        except ValueError:
            continue
        if isinstance(message, dict) and message.get("id") == request_id:
            return message


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
        print(f"FAIL: initialize returned an error: {init.get('error')}")
        return 1
    server = init["result"].get("serverInfo", {})

    _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
    _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    tools_response = _wait_for_id(lines, seen, 2)
    tools = tools_response.get("result", {}).get("tools", [])

    proc.stdin.close()
    try:
        exit_code = proc.wait(timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        exit_code = proc.wait()
    while True:
        try:
            raw = lines.get(timeout=10)
        except queue.Empty:
            break
        if raw is None:
            break
        seen.append(raw)

    stray = []
    for raw in seen:
        try:
            message = json.loads(raw)
        except ValueError:
            stray.append(raw)
            continue
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            stray.append(raw)

    print(f"server: {server.get('name')} {server.get('version')}")
    print(f"protocol: {init['result'].get('protocolVersion')}")
    print(f"tools: {len(tools)}")
    print(f"stdout lines: {len(seen)}, non-JSON-RPC lines: {len(stray)}")
    print(f"exit code after stdin closed: {exit_code}")
    for raw in stray[:5]:
        print(f"  stray stdout: {raw[:200]!r}")

    if stray or not tools:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
