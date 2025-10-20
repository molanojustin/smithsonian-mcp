"""
Constants and static mappings used by the MCP server.
"""

from typing import Dict, List
from ._version import __version__

SERVER_VERSION = __version__

MUSEUM_MAP: Dict[str, str] = {
    "american history": "NMAH",
    "natural history": "NMNH",
    "american art": "SAAM",
    "american indian": "NMAI",
    "air and space": "NASM",
    "asian art": "FSG",
    "portrait gallery": "NPG",
    "african art": "NMAfA",
    "hirshhorn": "HMSG",
    "cooper hewitt": "CHNDM",
    "african american history": "NMAAHC",
    "freer": "FSG",
    "sackler": "FSG",
    "renwick": "SAAM",
    "postal": "NPM",
    "zoo": "NZP",
    "smithsonian archives": "SIA",
    "anacostia": "ACM",
    "american art archives": "AAA",
}

VALID_MUSEUM_CODES: List[str] = [
    "NMAH",
    "NMNH",
    "SAAM",
    "NASM",
    "NPG",
    "FSG",
    "HMSG",
    "NMAfA",
    "NMAI",
    "ACM",
    "NMAAHC",
    "SIA",
    "NPM",
    "NZP",
    "CHNDM",
    "AAA",
]

SIZE_GUIDELINES: Dict[str, str] = {
    "small": "15-25 objects",
    "medium": "30-50 objects",
    "large": "60+ objects",
}
