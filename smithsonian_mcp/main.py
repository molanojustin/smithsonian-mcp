"""
Smithsonian Open Access MCP Main Entry Point

``main()`` is the canonical entry function, used by ``python -m smithsonian_mcp``,
``python -m smithsonian_mcp.main``, ``python -m smithsonian_mcp.server`` and the
console script. It serves MCP over stdio by default, or over streamable HTTP
with ``--transport http``. Logging is configured only here, and always to stderr,
because stdout carries the MCP stdio protocol.
"""

import argparse
import asyncio
import logging
import signal
import sys
from typing import List, Optional, Sequence

from . import __version__
from .app import mcp
from .config import Config

logger = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Third-party loggers that log every request URL at INFO
QUIET_LOGGERS = ("httpx", "httpcore")

TRANSPORTS = ("stdio", "http")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
# Path of the MCP endpoint in HTTP mode
HTTP_PATH = "/mcp"
# Host header values accepted in HTTP mode unless MCP_ALLOWED_HOSTS says
# otherwise. A specific listening address is added to them.
DEFAULT_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "::1")
# Listening addresses that mean every interface and name no host.
_ANY_ADDRESS = frozenset({"0.0.0.0", "::", "[::]"})


def configure_logging(level: Optional[str] = None) -> None:
    """
    Configure process logging to stderr.

    Args:
        level: Level name (DEBUG, INFO, ...). Defaults to ``Config.LOG_LEVEL``;
            unknown names fall back to INFO.
    """
    name = (level or Config.LOG_LEVEL or "INFO").strip().upper()
    numeric = logging.getLevelName(name)
    if not isinstance(numeric, int):
        numeric = logging.INFO
    logging.basicConfig(level=numeric, stream=sys.stderr, format=LOG_FORMAT, force=True)
    for noisy in QUIET_LOGGERS:
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _port(value: str) -> int:
    """
    Parse a TCP port number.

    Args:
        value: Port as text.

    Returns:
        int: The port, from 1 to 65535.

    Raises:
        argparse.ArgumentTypeError: If the value is not a valid port.
    """
    try:
        port = int(str(value).strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid port {value!r}") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"port {port} is not in 1-65535")
    return port


def _host_list(value: str) -> List[str]:
    """
    Split a comma-separated list of host names.

    Args:
        value: Names such as "localhost, mcp.example.org".

    Returns:
        List[str]: The names, without blanks.
    """
    return [name.strip() for name in value.split(",") if name.strip()]


def allowed_hosts_for(host: str, configured: Optional[List[str]] = None) -> List[str]:
    """
    Host header values that HTTP mode accepts.

    Requests naming any other host are refused, which blocks DNS rebinding from
    web pages whatever address the server listens on.

    Args:
        host: The listening address.
        configured: Names from --allowed-hosts or MCP_ALLOWED_HOSTS, if any.

    Returns:
        List[str]: The configured names, or localhost, 127.0.0.1 and ::1 plus
        the listening address unless it is 0.0.0.0 or ::.
    """
    if configured:
        return list(configured)
    hosts = list(DEFAULT_ALLOWED_HOSTS)
    if host not in _ANY_ADDRESS and host not in hosts:
        hosts.append(host)
    return hosts


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """
    Parse command line arguments, ignoring unknown ones for compatibility.

    ``--transport``, ``--host``, ``--port`` and ``--allowed-hosts`` default to
    ``MCP_TRANSPORT``, ``MCP_HOST``, ``MCP_PORT`` and ``MCP_ALLOWED_HOSTS``, then
    to stdio, 127.0.0.1, 8000 and the names from ``allowed_hosts_for``. Invalid
    values exit with status 2, whether they come from a flag or the environment.

    Args:
        argv: Arguments without the program name, or None for ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments with transport, host, port and
        allowed_hosts set.
    """
    parser = argparse.ArgumentParser(
        prog="smithsonian-mcp",
        description=(
            "Smithsonian Open Access MCP server. Serves MCP over stdio by "
            "default, or over streamable HTTP at http://HOST:PORT/mcp with "
            "--transport http."
        ),
    )
    parser.add_argument(
        "--transport",
        choices=TRANSPORTS,
        help="stdio or http (default: $MCP_TRANSPORT, else stdio)",
    )
    parser.add_argument(
        "--host",
        help=f"address to listen on in HTTP mode (default: $MCP_HOST, else {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=_port,
        help=f"port to listen on in HTTP mode (default: $MCP_PORT, else {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--allowed-hosts",
        metavar="NAMES",
        help=(
            "comma-separated Host header names accepted in HTTP mode (default: "
            "$MCP_ALLOWED_HOSTS, else localhost, 127.0.0.1, ::1 and the --host "
            "address)"
        ),
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="check the configuration and API access, then exit",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    args, unknown = parser.parse_known_args(argv)
    if unknown:
        args.unknown = unknown
    _apply_settings(parser, args)
    return args


def _apply_settings(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """
    Fill transport options not given as flags from the environment and defaults.

    A blank environment value counts as unset; a blank --host or --allowed-hosts
    is an error, because an empty listening address means every interface.

    Args:
        parser: The parser, for reporting invalid values.
        args: Parsed arguments, updated in place.
    """
    if args.transport is None:
        transport = (Config.MCP_TRANSPORT or "").strip().lower() or "stdio"
        if transport not in TRANSPORTS:
            parser.error(
                f"MCP_TRANSPORT must be one of {', '.join(TRANSPORTS)}, "
                f"not {transport!r}"
            )
        args.transport = transport

    if args.host is not None:
        args.host = args.host.strip()
        if not args.host:
            parser.error("--host must not be empty; use 0.0.0.0 for every interface")
    else:
        args.host = (Config.MCP_HOST or "").strip() or DEFAULT_HOST

    if args.port is None:
        port = (Config.MCP_PORT or "").strip()
        try:
            args.port = _port(port) if port else DEFAULT_PORT
        except argparse.ArgumentTypeError as exc:
            parser.error(f"MCP_PORT: {exc}")

    if args.allowed_hosts is not None:
        configured = _host_list(args.allowed_hosts)
        if not configured:
            parser.error("--allowed-hosts must name at least one host")
    else:
        configured = _host_list(Config.MCP_ALLOWED_HOSTS or "")
    args.allowed_hosts = allowed_hosts_for(args.host, configured)


async def _self_test() -> int:
    """
    Verify that tools are registered and the API answers with the configured key.

    Returns:
        int: Process exit code (0 on success).
    """
    # pylint: disable=import-outside-toplevel
    from .api_client import create_client
    from .models import APIError

    tool_count = len(await mcp.list_tools())
    client = await create_client()
    try:
        total = await client.count_matches("*")
    except APIError as exc:
        logger.error("Self-test failed: API request error: %s", exc)
        return 1
    finally:
        await client.disconnect()

    logger.info(
        "Self-test passed: %d tools registered, %d searchable records",
        tool_count,
        total,
    )
    return 0


def _serve_http(host: str, port: int, allowed_hosts: List[str]) -> None:
    """
    Serve MCP over streamable HTTP until interrupted.

    Uvicorn's own log configuration is not applied, so its server and access
    logs go through the stderr handler set up by ``configure_logging``.

    Requests whose Host header is not in ``allowed_hosts`` (or the address the
    connection arrived on) get 421, and requests from another site's Origin get
    403, on any listening address. This blocks DNS rebinding from web pages.

    The server is stateless: every request is handled on its own and no MCP
    session is kept, so memory does not grow with the number of clients that
    connect. The tools only answer requests; none sends notifications, progress
    or sampling requests that would need a session.

    Uvicorn shuts down gracefully on SIGINT and SIGTERM and then raises the
    signal again. Both end here as KeyboardInterrupt, or on Python 3.10 as the
    cancellation of the event loop's main task, so the lifespan closes the API
    client and the process exits with status 0.

    Args:
        host: Address to listen on.
        port: Port to listen on.
        allowed_hosts: Host header values to accept.
    """
    logger.info("Accepting Host headers: %s", ", ".join(allowed_hosts))
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        mcp.run(
            transport="http",
            host=host,
            port=port,
            path=HTTP_PATH,
            show_banner=False,
            stateless_http=True,
            host_origin_protection=True,
            allowed_hosts=allowed_hosts,
            uvicorn_config={"log_config": None},
        )
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("HTTP server stopped")


def main(argv: Optional[List[str]] = None) -> None:
    """
    Run the MCP server over stdio or streamable HTTP.

    Args:
        argv: Command line arguments, defaulting to ``sys.argv[1:]``.
    """
    args = _parse_args(argv)
    configure_logging()
    if getattr(args, "unknown", None):
        logger.warning("Ignoring unknown arguments: %s", " ".join(args.unknown))

    logger.info("Starting %s v%s", Config.SERVER_NAME, Config.SERVER_VERSION)

    if not Config.validate_api_key():
        logger.error(
            "API key not configured. Set SMITHSONIAN_API_KEY environment variable. "
            "Get your key from https://api.data.gov/signup/"
        )
        sys.exit(1)

    if args.test:
        sys.exit(asyncio.run(_self_test()))

    if args.transport == "http":
        _serve_http(args.host, args.port, args.allowed_hosts)
    else:
        # The banner is noise on stderr for a stdio server
        mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
