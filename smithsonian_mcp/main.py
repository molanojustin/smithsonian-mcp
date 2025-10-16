"""
Smithsonian Open Access MCP Main Entry Point
"""

import logging
import sys

from .app import mcp
from .config import Config

# Import modules to register tools and prompts
from . import tools, resources, prompts

# Configure logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Load tools, resources, and prompts
# The decorators in the imported modules will register them with the mcp instance
# The following line is needed to avoid flake8 errors
_ = [tools, resources, prompts]


def main():
    """Server startup logic"""
    logger.info("Starting %s v%s", Config.SERVER_NAME, Config.SERVER_VERSION)

    # Check for API key
    if not Config.validate_api_key():
        logger.error(
            "API key not configured. Set SMITHSONIAN_API_KEY environment variable. "
            "Get your key from https://api.data.gov/signup/"
        )
        sys.exit(1)

    # Run the MCP server
    mcp.run()


if __name__ == "__main__":
    main()
