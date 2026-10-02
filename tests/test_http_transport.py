"""
Tests for the transport options: argument parsing, the HTTP wiring of main()
and a streamable HTTP server started as a subprocess.
"""

import asyncio
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

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


@pytest.fixture
def transport_env(monkeypatch):
    """Set the MCP_* settings, as if read from the environment."""

    def apply(transport="stdio", host="127.0.0.1", port="8000"):
        monkeypatch.setattr(Config, "MCP_TRANSPORT", transport)
        monkeypatch.setattr(Config, "MCP_HOST", host)
        monkeypatch.setattr(Config, "MCP_PORT", port)

    apply()
    return apply


class TestArguments:
    """--transport, --host and --port, and their environment defaults."""

    def test_defaults_are_stdio_on_localhost(self, transport_env):
        args = main_module._parse_args([])
        assert (args.transport, args.host, args.port) == ("stdio", "127.0.0.1", 8000)

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
        transport_env(transport="http", host="0.0.0.0", port="8123")
        args = main_module._parse_args(
            ["--transport", "stdio", "--host", "localhost", "--port", "9002"]
        )
        assert (args.transport, args.host, args.port) == ("stdio", "localhost", 9002)

    def test_empty_environment_values_use_defaults(self, transport_env):
        transport_env(transport="", host=" ", port="")
        args = main_module._parse_args([])
        assert (args.transport, args.host, args.port) == ("stdio", "127.0.0.1", 8000)

    @pytest.mark.parametrize(
        "argv",
        [
            ["--transport", "sse"],
            ["--port", "http"],
            ["--port", "0"],
            ["--port", "65536"],
        ],
    )
    def test_invalid_flags_exit_with_usage_error(self, transport_env, argv, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main_module._parse_args(argv)
        assert excinfo.value.code == 2
        assert "usage:" in capsys.readouterr().err

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
        assert kwargs["host_origin_protection"] == "auto"
        # Uvicorn logs through the stderr handler instead of its own config
        assert kwargs["uvicorn_config"] == {"log_config": None}

    # Python 3.11+ ends an interrupted event loop with KeyboardInterrupt; 3.10
    # cancels its main task instead
    @pytest.mark.parametrize("interrupt", [KeyboardInterrupt, asyncio.CancelledError])
    def test_interrupt_ends_http_mode_cleanly(self, runs, monkeypatch, interrupt):
        def interrupted(**kwargs):
            raise interrupt

        monkeypatch.setattr(main_module.mcp, "run", interrupted)
        main_module.main(["--transport", "http"])  # returns instead of raising


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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


@pytest.mark.asyncio
@pytest.mark.parametrize("configure", ["flags", "environment"])
async def test_http_server_lists_tools(configure, tmp_path):
    """A server started with --transport http answers MCP over HTTP."""
    from fastmcp import Client

    port = _free_port()
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("SMITHSONIAN", "MCP_", "FASTMCP_"))
    }
    env["SMITHSONIAN_API_KEY"] = "placeholder-key-for-http-test"
    args = [sys.executable, "-m", "smithsonian_mcp"]
    if configure == "flags":
        args += ["--transport", "http", "--port", str(port)]
    else:
        env.update({"MCP_TRANSPORT": "http", "MCP_PORT": str(port)})

    stdout_path = tmp_path / "stdout"
    stderr_path = tmp_path / "stderr"
    with open(stdout_path, "wb") as stdout, open(stderr_path, "wb") as stderr:
        proc = subprocess.Popen(
            args, cwd=REPO_ROOT, env=env, stdout=stdout, stderr=stderr
        )
        try:
            _wait_for_port(port, proc)
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                tools = await client.list_tools()
            # A request naming another host is refused (DNS rebinding guard)
            with httpx.Client(trust_env=False, timeout=10) as http:
                foreign = http.post(
                    f"http://127.0.0.1:{port}/mcp",
                    headers={"Host": "attacker.example"},
                    json={},
                )
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT if os.name != "nt" else signal.SIGTERM)
            exit_code = proc.wait(timeout=30)

    assert {tool.name for tool in tools} == TOOL_NAMES
    assert foreign.status_code == 421
    if os.name != "nt":
        assert exit_code == 0
    # Logs go to stderr; stdout stays empty in HTTP mode too
    assert stdout_path.read_bytes() == b""
    log = stderr_path.read_text()
    assert f"http://127.0.0.1:{port}" in log
    assert "placeholder-key-for-http-test" not in log
