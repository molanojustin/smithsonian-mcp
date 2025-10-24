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
    "sculture garden": "HMSG",
    "cooper hewitt": "CHNDM",
    "design": "CHNDM",
    "african american history": "NMAAHC",
    "freer": "FSG",
    "sackler": "FSG",
    "renwick": "SAAM",
    "postal": "NPM",
    "zoo": "NZP",
    "smithsonian archives": "SIA",
    "anacostia": "ACM",
    "american art archives": "AAA",
    # Additional common variations for better matching
    "smithsonian asian art": "FSG",
    "smithsonian asian art museum": "FSG",
    "national museum of asian art": "FSG",
    "freer and sackler galleries": "FSG",
    "freer gallery": "FSG",
    "sackler gallery": "FSG",
    "smithsonian american art": "SAAM",
    "smithsonian american art museum": "SAAM",
    "national museum of american art": "SAAM",
    "renwick gallery": "SAAM",
    "smithsonian natural history": "NMNH",
    "smithsonian natural history museum": "NMNH",
    "national museum of natural history": "NMNH",
    "smithsonian air and space": "NASM",
    "smithsonian air and space museum": "NASM",
    "national air and space museum": "NASM",
    "smithsonian portrait gallery": "NPG",
    "national portrait gallery": "NPG",
    "smithsonian african art": "NMAfA",
    "smithsonian african art museum": "NMAfA",
    "national museum of african art": "NMAfA",
    "smithsonian hirshhorn": "HMSG",
    "hirshhorn museum": "HMSG",
    "hirshhorn museum and sculpture garden": "HMSG",
    "sculpture garden": "HMSG",
    "smithsonian cooper hewitt": "CHNDM",
    "cooper hewitt museum": "CHNDM",
    "smithsonian design museum": "CHNDM",
    "smithsonian african american history": "NMAAHC",
    "smithsonian african american history museum": "NMAAHC",
    "national museum of african american history and culture": "NMAAHC",
    "smithsonian postal": "NPM",
    "smithsonian postal museum": "NPM",
    "national postal museum": "NPM",
    "smithsonian zoo": "NZP",
    "national zoo": "NZP",
    "smithsonian national zoo": "NZP",
    "smithsonian anacostia": "ACM",
    "anacostia community museum": "ACM",
    "smithsonian archives": "SIA",
    "smithsonian institution archives": "SIA",
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

# Backward compatibility imports - these have been moved to museum_data.py
# Import them here for backward compatibility
try:
    from .museum_data import (
        MUSEUM_OBJECT_TYPES,
        get_museum_object_types,
        museum_has_object_type
    )
except ImportError:
    # Fallback if museum_data.py doesn't exist
    MUSEUM_OBJECT_TYPES = {}
    def get_museum_object_types(museum_code: str) -> List[str]:
        return []
    def museum_has_object_type(museum_code: str, object_type: str) -> bool:
        return False

