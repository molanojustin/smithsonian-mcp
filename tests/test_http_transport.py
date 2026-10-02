"""
Tests for the transport options: argument parsing, the HTTP wiring of main()
and streamable HTTP servers started as subprocesses.
"""

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional

import httpx
import pytest

from smithsonian_mcp import main as main_module
from smithsonian_mcp.config import Config

pytest.importorskip("pytest_asyncio")

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL_NAMES = {
    "search_objects",
    "get_object",
    "list_museums",
    "explore_topic",
    "get_collection_stats",
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
# Host headers a DNS rebinding attack would send
REBINDING_HOSTS = [
    "attacker.example",
    "127.0.0.1.nip.io",
    "7f000001.c0a80001.rbndr.us",
    "localhost.attacker.example",
    "0.0.0.0",
    "127.0.0.2",
]


@pytest.fixture
def transport_env(monkeypatch):
    """Set the MCP_* settings, as if read from the environment."""

    def apply(transport="stdio", host="127.0.0.1", port="8000", allowed_hosts=""):
        monkeypatch.setattr(Config, "MCP_TRANSPORT", transport)
        monkeypatch.setattr(Config, "MCP_HOST", host)
        monkeypatch.setattr(Config, "MCP_PORT", port)
        monkeypatch.setattr(Config, "MCP_ALLOWED_HOSTS", allowed_hosts)

    apply()
    return apply


class TestArguments:
    """--transport, --host, --port and --allowed-hosts, and their defaults."""

    def test_defaults_are_stdio_on_localhost(self, transport_env):
        args = main_module._parse_args([])
        assert (args.transport, args.host, args.port) == ("stdio", "127.0.0.1", 8000)
        assert args.allowed_hosts == ["localhost", "127.0.0.1", "::1"]

    def test_flags(self, transport_env):
        args = main_module._parse_args(
            ["--transport", "http", "--host", "0.0.0.0", "--port", "9001"]
        )
        assert (args.transport, args.host, args.port) == ("http", "0.0.0.0", 9001)

    def test_environment(self, transport_env):
        transport_env(transport=" HTTP ", host="0.0.0.0", port="8123")
        args = main_module._parse_args([])
        assert (args.transport, args.host, args.port) == ("http", "0.0.0.0", 8123)

    def test_flags_override_environment(self, transport_env):
        transport_env(
            transport="http", host="0.0.0.0", port="8123", allowed_hosts="a.example"
        )
        args = main_module._parse_args(
            [
                "--transport",
                "stdio",
                "--host",
                "localhost",
                "--port",
                "9002",
                "--allowed-hosts",
                "b.example",
            ]
        )
        assert (args.transport, args.host, args.port) == ("stdio", "localhost", 9002)
        assert args.allowed_hosts == ["b.example"]

    def test_empty_environment_values_use_defaults(self, transport_env):
        transport_env(transport="", host=" ", port="", allowed_hosts=" , ")
        args = main_module._parse_args([])
        assert (args.transport, args.host, args.port) == ("stdio", "127.0.0.1", 8000)
        assert args.allowed_hosts == ["localhost", "127.0.0.1", "::1"]

    @pytest.mark.parametrize(
        "host, allowed",
        [
            # Every interface names no host: only the loopback names
            ("0.0.0.0", ["localhost", "127.0.0.1", "::1"]),
            ("::", ["localhost", "127.0.0.1", "::1"]),
            ("127.0.0.1", ["localhost", "127.0.0.1", "::1"]),
            ("192.168.1.20", ["localhost", "127.0.0.1", "::1", "192.168.1.20"]),
            ("mcp.internal", ["localhost", "127.0.0.1", "::1", "mcp.internal"]),
        ],
    )
    def test_default_allowed_hosts_follow_the_listening_address(
        self, transport_env, host, allowed
    ):
        args = main_module._parse_args(["--host", host])
        assert args.allowed_hosts == allowed

    def test_allowed_hosts_from_environment(self, transport_env):
        transport_env(host="0.0.0.0", allowed_hosts="mcp.example.org, 10.0.0.5 ,")
        args = main_module._parse_args([])
        assert args.allowed_hosts == ["mcp.example.org", "10.0.0.5"]

    @pytest.mark.parametrize(
        "argv, message",
        [
            (["--transport", "sse"], "invalid choice"),
            (["--port", "http"], "invalid port"),
            (["--port", "0"], "not in 1-65535"),
            (["--port", "65536"], "not in 1-65535"),
            # An empty address would listen on every interface
            (["--host", ""], "--host must not be empty"),
            (["--host", "  "], "--host must not be empty"),
            (["--allowed-hosts", " , "], "--allowed-hosts must name at least one"),
        ],
    )
    def test_invalid_flags_exit_with_usage_error(
        self, transport_env, argv, message, capsys
    ):
        with pytest.raises(SystemExit) as excinfo:
            main_module._parse_args(argv)
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "usage:" in err and message in err

    @pytest.mark.parametrize(
        "setting, message",
        [
            ({"transport": "sse"}, "MCP_TRANSPORT must be one of stdio, http"),
            ({"port": "eighty"}, "MCP_PORT: invalid port 'eighty'"),
            ({"port": "70000"}, "MCP_PORT: port 70000 is not in 1-65535"),
        ],
    )
    def test_invalid_environment_exits_with_usage_error(
        self, transport_env, setting, message, capsys
    ):
        transport_env(**setting)
        with pytest.raises(SystemExit) as excinfo:
            main_module._parse_args([])
        assert excinfo.value.code == 2
        assert message in capsys.readouterr().err

    def test_unknown_arguments_are_still_ignored(self, transport_env):
        args = main_module._parse_args(["--transport", "http", "--legacy-flag"])
        assert args.transport == "http"
        assert args.unknown == ["--legacy-flag"]


class TestMainWiring:
    """main() hands the chosen transport to FastMCP."""

    @pytest.fixture
    def runs(self, monkeypatch, transport_env):
        calls = []
        monkeypatch.setattr(main_module, "configure_logging", lambda: None)
        monkeypatch.setattr(Config, "API_KEY", "placeholder")
        monkeypatch.setattr(
            main_module.mcp, "run", lambda **kwargs: calls.append(kwargs)
        )
        # Keep the test process's own SIGTERM handler
        monkeypatch.setattr(main_module.signal, "signal", lambda *args: None)
        return calls

    def test_stdio_is_the_default(self, runs):
        main_module.main([])
        assert runs == [{"transport": "stdio", "show_banner": False}]

    def test_http_mode(self, runs):
        main_module.main(["--transport", "http", "--port", "9003"])
        assert len(runs) == 1
        kwargs = runs[0]
        assert kwargs["transport"] == "http"
        assert (kwargs["host"], kwargs["port"], kwargs["path"]) == (
            "127.0.0.1",
            9003,
            "/mcp",
        )
        assert kwargs["show_banner"] is False
        # Host headers are checked on every listening address, from an allowlist
        assert kwargs["host_origin_protection"] is True
        assert kwargs["allowed_hosts"] == ["localhost", "127.0.0.1", "::1"]
        # No sessions are kept between requests
        assert kwargs["stateless_http"] is True
        # Uvicorn logs through the stderr handler instead of its own config
        assert kwargs["uvicorn_config"] == {"log_config": None}

    def test_http_mode_on_every_interface_still_checks_hosts(self, runs):
        main_module.main(["--transport", "http", "--host", "0.0.0.0"])
        assert runs[0]["host"] == "0.0.0.0"
        assert runs[0]["host_origin_protection"] is True
        assert runs[0]["allowed_hosts"] == ["localhost", "127.0.0.1", "::1"]

    # Python 3.11+ ends an interrupted event loop with KeyboardInterrupt; 3.10
    # cancels its main task instead
    @pytest.mark.parametrize("interrupt", [KeyboardInterrupt, asyncio.CancelledError])
    @pytest.mark.parametrize("transport", ["http", "stdio"])
    def test_interrupt_ends_cleanly(self, runs, monkeypatch, interrupt, transport):
        def interrupted(**kwargs):
            raise interrupt

        monkeypatch.setattr(main_module.mcp, "run", interrupted)
        main_module.main(["--transport", transport])  # returns instead of raising


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _local_address() -> Optional[str]:
    """
    A non-loopback IPv4 address of this machine that reaches a 0.0.0.0 listener.

    Returns None when there is none, or when a sandbox or firewall blocks
    connections to it; the caller then tests through loopback only.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            # Picks the outgoing interface; no packet is sent
            sock.connect(("10.255.255.255", 1))
            address = sock.getsockname()[0]
        except OSError:
            return None
    if address.startswith("127.") or address == "0.0.0.0":
        return None
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("0.0.0.0", 0))
        listener.listen()
        listener.settimeout(2)

        def greet() -> None:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            with conn:
                conn.sendall(b"ok")

        greeter = threading.Thread(target=greet, daemon=True)
        greeter.start()
        try:
            # A proxy in front of the network can accept the connection itself,
            # so only a reply from the listener counts
            with socket.create_connection(
                (address, listener.getsockname()[1]), timeout=2
            ) as conn:
                reply = conn.recv(2)
        except OSError:
            reply = b""
        greeter.join(3)
    return address if reply == b"ok" else None


def _wait_for_port(port: int, proc: subprocess.Popen, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise AssertionError(f"server exited early with code {proc.returncode}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"server did not listen on port {port}")


def _server_env(extra: Optional[dict] = None) -> dict:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SMITHSONIAN", "MCP_", "FASTMCP_"))
    }
    env["SMITHSONIAN_API_KEY"] = "placeholder-key-for-http-test"
    env.update(extra or {})
    return env


@contextmanager
def _http_server(args: List[str], env: dict, port: int, tmp_path: Path) -> Iterator:
    """Run the server as a subprocess; yields the process, then stops it."""
    stdout_path = tmp_path / "stdout"
    stderr_path = tmp_path / "stderr"
    with open(stdout_path, "wb") as stdout, open(stderr_path, "wb") as stderr:
        proc = subprocess.Popen(
            [sys.executable, "-m", "smithsonian_mcp", *args],
            cwd=REPO_ROOT,
            env=env,
            stdout=stdout,
            stderr=stderr,
        )
        try:
            _wait_for_port(port, proc)
            yield proc
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT if os.name != "nt" else signal.SIGTERM)
            proc.wait(timeout=30)
    proc.stdout_bytes = stdout_path.read_bytes()
    proc.stderr_text = stderr_path.read_text()


def _initialize(address: str, port: int, host_header: str, **headers) -> httpx.Response:
    with httpx.Client(trust_env=False, timeout=10) as http:
        return http.post(
            f"http://{address}:{port}/mcp",
            headers={**MCP_HEADERS, "Host": host_header, **headers},
            content=json.dumps(INITIALIZE),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("configure", ["flags", "environment"])
async def test_http_server_lists_tools(configure, tmp_path):
    """A server started with --transport http answers MCP over HTTP."""
    from fastmcp import Client

    port = _free_port()
    if configure == "flags":
        args, env = ["--transport", "http", "--port", str(port)], _server_env()
    else:
        args = []
        env = _server_env({"MCP_TRANSPORT": "http", "MCP_PORT": str(port)})

    with _http_server(args, env, port, tmp_path) as proc:
        async with Client(f"http://127.0.0.1:{port}/mcp") as client:
            tools = await client.list_tools()
        initialized = _initialize("127.0.0.1", port, f"127.0.0.1:{port}")
        # A request naming another host is refused (DNS rebinding guard)
        foreign = _initialize("127.0.0.1", port, "attacker.example")

    assert {tool.name for tool in tools} == TOOL_NAMES
    assert initialized.status_code == 200
    # Stateless: no session is created, so none is left to free
    assert "mcp-session-id" not in initialized.headers
    assert foreign.status_code == 421
    if os.name != "nt":
        assert proc.returncode == 0
    # Logs go to stderr; stdout stays empty in HTTP mode too
    assert proc.stdout_bytes == b""
    assert f"http://127.0.0.1:{port}" in proc.stderr_text
    assert "placeholder-key-for-http-test" not in proc.stderr_text


def test_every_interface_refuses_rebinding_hosts(tmp_path):
    """Listening on 0.0.0.0, foreign Host and Origin headers are still refused."""
    port = _free_port()
    address = _local_address()
    args = ["--transport", "http", "--host", "0.0.0.0", "--port", str(port)]
    with _http_server(args, _server_env(), port, tmp_path):
        loopback = {
            host: _initialize("127.0.0.1", port, f"{host}:{port}").status_code
            for host in ["127.0.0.1", "localhost", *REBINDING_HOSTS]
        }
        origin = _initialize(
            "127.0.0.1",
            port,
            f"127.0.0.1:{port}",
            Origin="http://attacker.example",
        ).status_code
        external = {}
        if address:
            # Through a non-loopback interface, as a container's published port
            external = {
                host: _initialize(address, port, f"{host}:{port}").status_code
                for host in [address, *REBINDING_HOSTS]
            }

    assert loopback["127.0.0.1"] == loopback["localhost"] == 200
    assert {loopback[host] for host in REBINDING_HOSTS} == {421}
    assert origin == 403
    if address:
        # The address the connection arrived on is accepted, names are not
        assert external.pop(address) == 200
        assert set(external.values()) == {421}
