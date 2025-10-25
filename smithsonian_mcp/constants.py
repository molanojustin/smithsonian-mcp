"""
Constants and static mappings used by the MCP server.
"""

from typing import Dict, List
from ._version import __version__

SERVER_VERSION = __version__

MUSEUM_MAP: Dict[str, str] = {
    "american history": "NMAH",
    "ahm": "NMAH",  # Common wrong abbreviation for American History Museum
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
    "minerals": "NMNHMINSCI",
    "mineral": "NMNHMINSCI",
    "dinosaur": "NMNHPALEO",
    "paleontology": "NMNHPALEO",
    "anthropology": "NMNHANTHRO",
    "birds": "NMNHBIRDS",
    "botony": "NMNHBOTANY",
    "plants": "NMNHBOTANY",
    "education": "NMNHEDUCATION",
    "entomology": "NMNHENTO",
    "fish": "NMNHFISHES",
    "fishes": "NMNHFISHES",
    "herpetology": "NMNHHERPS",
    "invertebrate": "NMNHINV",
    "mammal": "NMNHMAMMALS",
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
    "NMNHMINSCI",
    "NMNHPALEO",
    "NMNHANTHRO",
    "NMNHBIRDS",
    "NMNHBOTANY",
    "NMNHEDUCATION",
    "NMNHENTO",
    "NMNHFISHES",
    "NMNHHERPS",
    "NMNHINV",
    "NMNHMAMMALS",
]

SIZE_GUIDELINES: Dict[str, str] = {
    "small": "15-25 objects",
    "medium": "30-50 objects",
    "large": "60+ objects",
}

# URL construction patterns for different Smithsonian museums
# Each museum may have different URL formats and identifier requirements

MUSEUM_URL_PATTERNS: Dict[str, Dict[str, str]] = {
    "NMAH": {
        "base_url": "https://americanhistory.si.edu",
        "path_template": "/collections/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://americanhistory.si.edu/collections/object/nmah_1448973"
    },
    "FSG": {
        "base_url": "https://asia.si.edu",
        "path_template": "/object/{accession}",
        "identifier": "accession",
        "example": "https://asia.si.edu/object/F1900.47/"
    },
    "NMAAHC": {
        "base_url": "https://nmaahc.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://nmaahc.si.edu/object/nmaahc_2022.91.10ab"
    },
    "NMNHMINSCI": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example":"https://naturalhistory.si.edu/object/nmnhmineralsciences_17183750"
    },
    "NMNHPALEO": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnhpaleobiology_17134484"
    },
    "NMNHANTHRO": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnhanthropology_8352715"
    },
    "NMNHEDUCATION": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnheducation_10841904"
    },
    "NMNHINV": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnhinvertebratezoology_14688577"
    },
    "SAAM": {
        "base_url": "{record_link}", # uses americanart.si.edu, but record_link has full link
        "path_template": "",
        "identifier": "record_link",
        "example": "https://americanart.si.edu/collections/search/artwork/?id=30913"
    },
    "NASM": { 
        "base_url": "{record_link}", # uses n2t link that redirects to the actual link
        "path_template": "",
        "identifier": "record_link",
        "example": "http://n2t.net/ark:/65665/nv913e903df-63e7-4cad-aa80-ca3dfda681a4"
    },
    "NPG": {
        "base_url": "https://npg.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://npg.si.edu/object/npg_NPG.2002.184"
    },
    "HMSG": {
        "base_url": "https://hirshhorn.si.edu",
        "path_template": "/collection/artwork/?edanUrl={url}",
        "identifier": "url",
        "example": "https://hirshhorn.si.edu/collection/artwork/?edanUrl=edanmdm:hmsg_66.1608"
    },
    "NMAfA": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/ys7a3f230ba-972a-4ddf-82be-269516cb20ed"
    },
    "NMAI": {
        "base_url": "{record_link}", # uses americanindian.si.edu, but record_link has full link
        "path_template": "",
        "identifier": "record_link",
        "example": "http://n2t.net/ark:/65665/ws69d7d97b6-84fc-4f08-883e-ecc2ee0e38c7"
    },
    "ACM": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/dl8b7ab6959-5362-49e1-84a3-f8dbd0c3e2e0"
    },
    "SIA": {
        "base_url" : "https://siarchives.si.edu",
        "path_template": "/collections/{record_ID}",
        "identifier": "record_ID",
        "example": "https://siarchives.si.edu/collections/siris_arc_403511"
    },
    "NPM": {
        "base_url": "https://postalmuseum.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://postalmuseum.si.edu/object/npm_0.293996.232"
    },
    "NZP": {
        "base_url": "https://ids.si.edu",
        "path_template": "/ids/deliveryService?id={idsId}",
        "identifier": "idsId",
        "example": "https://ids.si.edu/ids/deliveryService?id=NZP-20190815_002RP"
    },
    "CHNDM": {
        "base_url": "{record_link}",
        "path_template": "",
        "identifier": "record_link",
        "example": "https://collection.cooperhewitt.org/view/objects/asitem/id/33665"
    },
    "NMNHBIRDS": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/352f6df2a-7cf0-42ad-b9ad-dbaaff2bbc25"
    },
    "NMNHBOTANY": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/32cbf4c79-da2d-4333-81db-ae926c2bd536"
    },
    "NMNHENTO": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/339e344dc-c269-435f-99ef-d009f12fd5d5"
    },
    "NMNHFISHES": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/3ccbe2c66-aa94-4570-88b1-44896089cfa1"
    },
    "NMNHHERPS": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/359523727-cb45-403c-bb71-e3c31b743355"
    },
    "NMNHMAMMALS": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/30b523759-352a-478c-b8ed-62dc1b38dd6f"
    }
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

