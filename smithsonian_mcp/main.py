"""
Smithsonian Open Access MCP Main Entry Point

``main()`` is the canonical entry function, used by ``python -m smithsonian_mcp``,
``python -m smithsonian_mcp.main``, ``python -m smithsonian_mcp.server`` and the
console script. Logging is configured only here, and always to stderr, because
stdout carries the MCP stdio protocol.
"""

import argparse
import asyncio
import logging
import sys
from typing import List, Optional, Sequence

from . import __version__
from .app import mcp
from .config import Config

# Import modules to register tools, resources and prompts with the mcp instance
from . import tools, resources, prompts

logger = logging.getLogger(__name__)

# Keep the registration imports referenced for linters
_ = [tools, resources, prompts]

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

# Third-party loggers that log every request URL at INFO
QUIET_LOGGERS = ("httpx", "httpcore")


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


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    """
    Parse command line arguments, ignoring unknown ones for compatibility.

    Args:
        argv: Arguments without the program name, or None for ``sys.argv[1:]``.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(
        prog="smithsonian-mcp",
        description="Smithsonian Open Access MCP server (stdio transport).",
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
    return args


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


def main(argv: Optional[List[str]] = None) -> None:
    """
    Run the MCP server over stdio.

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

    # The banner is noise on stderr for a stdio server
    mcp.run(show_banner=False)


if __name__ == "__main__":
    main()
