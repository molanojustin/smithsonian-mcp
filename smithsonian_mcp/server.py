"""
Backward-compatible module entry point.

``python -m smithsonian_mcp.server`` starts the same server as
``python -m smithsonian_mcp`` and the ``smithsonian-mcp`` command. The server
lifespan lives in ``context``, next to the shared API client it manages.
"""

from .main import main

if __name__ == "__main__":
    main()
