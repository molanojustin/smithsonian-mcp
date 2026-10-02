"""
Constants and static mappings used by the MCP server.

Unit codes were checked against ``GET /terms/unit_code`` of the Smithsonian Open
Access API. Codes in ``ARCHIVAL_UNIT_CODES`` only publish archival records, which
the object search used by this server does not return.
"""

from typing import Dict, FrozenSet, List, Tuple

# Pseudo unit code covering every National Museum of Natural History department.
# The index has no NMNH records of its own; searches use the wildcard NMNH*.
NMNH_AGGREGATE_CODE = "NMNH"

NMNH_SUB_UNIT_CODES: List[str] = [
    "NMNHANTHRO",
    "NMNHBIRDS",
    "NMNHBOTANY",
    "NMNHEDUCATION",
    "NMNHENTO",
    "NMNHFISHES",
    "NMNHHERPS",
    "NMNHINV",
    "NMNHMAMMALS",
    "NMNHMINSCI",
    "NMNHPALEO",
]

# Unit codes returned by GET /terms/unit_code. Used when the endpoint is unavailable.
KNOWN_UNIT_CODES: List[str] = [
    "AAA",
    "AAG",
    "ACAH",
    "ACM",
    "ACMA",
    "CFCHFOLKLIFE",
    "CHNDM",
    "CHSDM",
    "EEPA",
    "FBR",
    "FSA",
    "HAC",
    "HMSG",
    "HSFA",
    "NAA",
    "NASM",
    "NASMAC",
    "NMAA",
    "NMAAHC",
    "NMAH",
    "NMAI",
    "NMAIA",
    "NMAfA",
    *NMNH_SUB_UNIT_CODES,
    "NPG",
    "NPM",
    "NPMA",
    "NZP",
    "OCIO_DPO3D",
    "OFEO-SG",
    "SAAM",
    "SAAMPAIK",
    "SI",
    "SIA",
    "SIL",
    "SILAF",
    "SILNMAHTL",
    "SLA_SRO",
]

# Units that only publish archival records (row_group "archives"), so object
# searches return nothing for them; archive searches do.
ARCHIVAL_UNIT_CODES: FrozenSet[str] = frozenset(
    {
        "AAA",
        "AAG",
        "ACAH",
        "ACMA",
        "CHSDM",
        "EEPA",
        "FSA",
        "HSFA",
        "NAA",
        "NASMAC",
        "NMAIA",
        "NPMA",
        "SAAMPAIK",
        "SI",
    }
)

# Units that publish archive records as well as objects (row_group "archives"
# counts checked in October 2026: SIA 863,592, CFCHFOLKLIFE 73,400, NMAAHC
# 16,427, SAAM 2,788, NPG 701, SIL 554). To refresh this and
# ARCHIVAL_UNIT_CODES, count each code from GET /terms/unit_code twice with
# GET /search?q=unit_code:<code>&rows=0, once with row_group=archives: codes with
# both counts above zero belong here, codes with archive records only above.
MIXED_UNIT_CODES: FrozenSet[str] = frozenset(
    {"CFCHFOLKLIFE", "NMAAHC", "NPG", "SAAM", "SIA", "SIL"}
)

# Legacy or informal codes that users pass but the index does not use.
# "FSG" (Freer|Sackler) records are indexed under NMAA today.
UNIT_CODE_ALIASES: Dict[str, str] = {
    "FSG": "NMAA",
    "F|S": "NMAA",
    "FREER": "NMAA",
    "SACKLER": "NMAA",
}

# Codes accepted as search filters: the indexed codes plus the NMNH aggregate.
VALID_MUSEUM_CODES: List[str] = [NMNH_AGGREGATE_CODE, *KNOWN_UNIT_CODES]

# Display name and location of each unit.
UNIT_INFO: Dict[str, Dict[str, str]] = {
    "AAA": {
        "name": "Archives of American Art",
        "location": "Washington, DC",
    },
    "AAG": {
        "name": "Archives of American Gardens",
        "location": "Washington, DC",
    },
    "ACAH": {
        "name": "Archives Center, National Museum of American History",
        "location": "Washington, DC",
    },
    "ACM": {
        "name": "Anacostia Community Museum",
        "location": "Washington, DC",
    },
    "ACMA": {
        "name": "Anacostia Community Museum Archives",
        "location": "Washington, DC",
    },
    "CFCHFOLKLIFE": {
        "name": "Ralph Rinzler Folklife Archives and Collections",
        "location": "Washington, DC",
    },
    "CHNDM": {
        "name": "Cooper Hewitt, Smithsonian Design Museum",
        "location": "New York, NY",
    },
    "CHSDM": {
        "name": "Cooper Hewitt, Smithsonian Design Museum Archives",
        "location": "New York, NY",
    },
    "EEPA": {
        "name": "Eliot Elisofon Photographic Archives",
        "location": "Washington, DC",
    },
    "FBR": {
        "name": "Smithsonian Field Book Project",
        "location": "Washington, DC",
    },
    "FSA": {
        "name": "National Museum of Asian Art Archives",
        "location": "Washington, DC",
    },
    "HAC": {
        "name": "Smithsonian Gardens, Horticultural Artifacts Collection",
        "location": "Washington, DC",
    },
    "HMSG": {
        "name": "Hirshhorn Museum and Sculpture Garden",
        "location": "Washington, DC",
    },
    "HSFA": {
        "name": "Human Studies Film Archives",
        "location": "Suitland, MD",
    },
    "NAA": {
        "name": "National Anthropological Archives",
        "location": "Suitland, MD",
    },
    "NASM": {
        "name": "National Air and Space Museum",
        "location": "Washington, DC and Chantilly, VA",
    },
    "NASMAC": {
        "name": "National Air and Space Museum Archives",
        "location": "Chantilly, VA",
    },
    "NMAA": {
        "name": "National Museum of Asian Art",
        "location": "Washington, DC",
    },
    "NMAAHC": {
        "name": "National Museum of African American History and Culture",
        "location": "Washington, DC",
    },
    "NMAH": {
        "name": "National Museum of American History",
        "location": "Washington, DC",
    },
    "NMAI": {
        "name": "National Museum of the American Indian",
        "location": "Washington, DC and New York, NY",
    },
    "NMAIA": {
        "name": "National Museum of the American Indian Archives",
        "location": "Suitland, MD",
    },
    "NMAfA": {
        "name": "National Museum of African Art",
        "location": "Washington, DC",
    },
    NMNH_AGGREGATE_CODE: {
        "name": "National Museum of Natural History",
        "location": "Washington, DC",
    },
    "NMNHANTHRO": {
        "name": "National Museum of Natural History, Anthropology",
        "location": "Washington, DC",
    },
    "NMNHBIRDS": {
        "name": "National Museum of Natural History, Birds",
        "location": "Washington, DC",
    },
    "NMNHBOTANY": {
        "name": "National Museum of Natural History, Botany",
        "location": "Washington, DC",
    },
    "NMNHEDUCATION": {
        "name": "National Museum of Natural History, Education and Outreach",
        "location": "Washington, DC",
    },
    "NMNHENTO": {
        "name": "National Museum of Natural History, Entomology",
        "location": "Washington, DC",
    },
    "NMNHFISHES": {
        "name": "National Museum of Natural History, Fishes",
        "location": "Washington, DC",
    },
    "NMNHHERPS": {
        "name": "National Museum of Natural History, Amphibians and Reptiles",
        "location": "Washington, DC",
    },
    "NMNHINV": {
        "name": "National Museum of Natural History, Invertebrate Zoology",
        "location": "Washington, DC",
    },
    "NMNHMAMMALS": {
        "name": "National Museum of Natural History, Mammals",
        "location": "Washington, DC",
    },
    "NMNHMINSCI": {
        "name": "National Museum of Natural History, Mineral Sciences",
        "location": "Washington, DC",
    },
    "NMNHPALEO": {
        "name": "National Museum of Natural History, Paleobiology",
        "location": "Washington, DC",
    },
    "NPG": {
        "name": "National Portrait Gallery",
        "location": "Washington, DC",
    },
    "NPM": {
        "name": "National Postal Museum",
        "location": "Washington, DC",
    },
    "NPMA": {
        "name": "National Postal Museum Archives",
        "location": "Washington, DC",
    },
    "NZP": {
        "name": "Smithsonian's National Zoo and Conservation Biology Institute",
        "location": "Washington, DC",
    },
    "OCIO_DPO3D": {
        "name": "Smithsonian Digitization Program Office, 3D",
        "location": "Washington, DC",
    },
    "OFEO-SG": {
        "name": "Smithsonian Gardens",
        "location": "Washington, DC",
    },
    "SAAM": {
        "name": "Smithsonian American Art Museum",
        "location": "Washington, DC",
    },
    "SAAMPAIK": {
        "name": "Smithsonian American Art Museum, Nam June Paik Archive",
        "location": "Washington, DC",
    },
    "SI": {
        "name": "Smithsonian Institution",
        "location": "Washington, DC",
    },
    "SIA": {
        "name": "Smithsonian Institution Archives",
        "location": "Washington, DC",
    },
    "SIL": {
        "name": "Smithsonian Libraries",
        "location": "Washington, DC",
    },
    "SILAF": {
        "name": "Smithsonian Libraries, Art and Artist Files",
        "location": "Washington, DC",
    },
    "SILNMAHTL": {
        "name": "Smithsonian Libraries, Trade Literature",
        "location": "Washington, DC",
    },
    "SLA_SRO": {
        "name": "Smithsonian Libraries and Archives, Research Online",
        "location": "Washington, DC",
    },
}

# Exhibition building codes seen in onPhysicalExhibit records (October 2026),
# with the building's name and place. Rooms are reported separately. To refresh,
# page through GET /search?q=onPhysicalExhibit:"Yes"&rows=1000 (start=0, 1000,
# ...) and collect the distinct "building" values of
# content.indexedStructured.exhibition.
EXHIBITION_BUILDINGS: Dict[str, Tuple[str, str]] = {
    "ACM": ("Anacostia Community Museum", "Washington, DC"),
    "CHNDM": ("Cooper Hewitt, Smithsonian Design Museum", "New York, NY"),
    "Freer": (
        "Freer Gallery of Art, National Museum of Asian Art",
        "Washington, DC",
    ),
    "HAZY": (
        "Steven F. Udvar-Hazy Center, National Air and Space Museum",
        "Chantilly, VA",
    ),
    "HMSG": ("Hirshhorn Museum and Sculpture Garden", "Washington, DC"),
    "NASM": ("National Air and Space Museum", "Washington, DC"),
    "NMAAHC": (
        "National Museum of African American History and Culture",
        "Washington, DC",
    ),
    "NMAfA": ("National Museum of African Art", "Washington, DC"),
    "NMAH": ("National Museum of American History", "Washington, DC"),
    "NMAI DC": ("National Museum of the American Indian", "Washington, DC"),
    "NMAI NY": (
        "National Museum of the American Indian, George Gustav Heye Center",
        "New York, NY",
    ),
    "NMNH": ("National Museum of Natural History", "Washington, DC"),
    "NPG": ("National Portrait Gallery", "Washington, DC"),
    "NPM": ("National Postal Museum", "Washington, DC"),
    "Quadrangle": ("Smithsonian Quadrangle", "Washington, DC"),
    "Renwick": ("Renwick Gallery, Smithsonian American Art Museum", "Washington, DC"),
    "Sackler": (
        "Arthur M. Sackler Gallery, National Museum of Asian Art",
        "Washington, DC",
    ),
    "SAAM": ("Smithsonian American Art Museum", "Washington, DC"),
}

# Museum names (lowercase) mapped to unit codes, used by resolve_museum_code.
MUSEUM_MAP: Dict[str, str] = {
    "american history": "NMAH",
    "american history museum": "NMAH",
    "national museum of american history": "NMAH",
    "ahm": "NMAH",  # Common wrong abbreviation for American History Museum
    "natural history": "NMNH",
    "natural history museum": "NMNH",
    "smithsonian natural history": "NMNH",
    "smithsonian natural history museum": "NMNH",
    "national museum of natural history": "NMNH",
    "american art": "SAAM",
    "smithsonian american art": "SAAM",
    "smithsonian american art museum": "SAAM",
    "national museum of american art": "SAAM",
    "renwick": "SAAM",
    "renwick gallery": "SAAM",
    "american indian": "NMAI",
    "national museum of the american indian": "NMAI",
    "air and space": "NASM",
    "smithsonian air and space": "NASM",
    "smithsonian air and space museum": "NASM",
    "national air and space museum": "NASM",
    "udvar hazy": "NASM",
    "udvar-hazy": "NASM",
    "asian art": "NMAA",
    "smithsonian asian art": "NMAA",
    "smithsonian asian art museum": "NMAA",
    "national museum of asian art": "NMAA",
    "freer": "NMAA",
    "sackler": "NMAA",
    "freer gallery": "NMAA",
    "freer gallery of art": "NMAA",
    "sackler gallery": "NMAA",
    "arthur m sackler gallery": "NMAA",
    "freer and sackler": "NMAA",
    "freer and sackler galleries": "NMAA",
    "freer sackler": "NMAA",
    "portrait gallery": "NPG",
    "smithsonian portrait gallery": "NPG",
    "national portrait gallery": "NPG",
    "african art": "NMAfA",
    "smithsonian african art": "NMAfA",
    "smithsonian african art museum": "NMAfA",
    "national museum of african art": "NMAfA",
    "hirshhorn": "HMSG",
    "smithsonian hirshhorn": "HMSG",
    "hirshhorn museum": "HMSG",
    "hirshhorn museum and sculpture garden": "HMSG",
    "sculpture garden": "HMSG",
    "sculture garden": "HMSG",
    "cooper hewitt": "CHNDM",
    "cooper-hewitt": "CHNDM",
    "smithsonian cooper hewitt": "CHNDM",
    "cooper hewitt museum": "CHNDM",
    "smithsonian design museum": "CHNDM",
    "design": "CHNDM",
    "african american museum": "NMAAHC",
    "african american history museum": "NMAAHC",
    "museum of african american history": "NMAAHC",
    "african american history": "NMAAHC",
    "african american history and culture": "NMAAHC",
    "smithsonian african american history": "NMAAHC",
    "smithsonian african american history museum": "NMAAHC",
    "national museum of african american history and culture": "NMAAHC",
    "postal": "NPM",
    "postal museum": "NPM",
    "smithsonian postal": "NPM",
    "smithsonian postal museum": "NPM",
    "national postal museum": "NPM",
    "zoo": "NZP",
    "national zoo": "NZP",
    "smithsonian zoo": "NZP",
    "smithsonian national zoo": "NZP",
    "anacostia": "ACM",
    "smithsonian anacostia": "ACM",
    "anacostia community museum": "ACM",
    "smithsonian archives": "SIA",
    "smithsonian institution archives": "SIA",
    "archives of american art": "AAA",
    "smithsonian libraries": "SIL",
    "smithsonian gardens": "OFEO-SG",
    "folklife": "CFCHFOLKLIFE",
    "field book project": "FBR",
    "national anthropological archives": "NAA",
    # National Museum of Natural History departments
    "minerals": "NMNHMINSCI",
    "mineral": "NMNHMINSCI",
    "mineral sciences": "NMNHMINSCI",
    "dinosaur": "NMNHPALEO",
    "paleontology": "NMNHPALEO",
    "paleobiology": "NMNHPALEO",
    "anthropology": "NMNHANTHRO",
    "birds": "NMNHBIRDS",
    "botany": "NMNHBOTANY",
    "botony": "NMNHBOTANY",
    "plants": "NMNHBOTANY",
    "education": "NMNHEDUCATION",
    "entomology": "NMNHENTO",
    "insects": "NMNHENTO",
    "fish": "NMNHFISHES",
    "fishes": "NMNHFISHES",
    "herpetology": "NMNHHERPS",
    "reptiles": "NMNHHERPS",
    "amphibians": "NMNHHERPS",
    "invertebrate": "NMNHINV",
    "invertebrate zoology": "NMNHINV",
    "mammal": "NMNHMAMMALS",
    "mammals": "NMNHMAMMALS",
}

# Object counts suggested by the exhibition_planning prompt for each size.
SIZE_GUIDELINES: Dict[str, str] = {
    "small": "15-25 objects",
    "medium": "30-50 objects",
    "large": "60+ objects",
}

# Object page URLs that follow from the record_ID (or the accession number after
# its prefix) alone, by museum code; used by utils.record_page_url. Pages of other
# museums need record data, such as record_link or guid.
MUSEUM_URL_PATTERNS: Dict[str, Dict[str, str]] = {
    "NMAH": {
        "base_url": "https://americanhistory.si.edu",
        "path_template": "/collections/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://americanhistory.si.edu/collections/object/nmah_1448973",
    },
    "FSG": {
        "base_url": "https://asia.si.edu",
        "path_template": "/object/{accession}",
        "identifier": "accession",
        "example": "https://asia.si.edu/object/F1900.47/",
    },
    "NMAAHC": {
        "base_url": "https://nmaahc.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://nmaahc.si.edu/object/nmaahc_2022.91.10ab",
    },
    "NMNHMINSCI": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnhmineralsciences_17183750",
    },
    "NMNHPALEO": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnhpaleobiology_17134484",
    },
    "NMNHANTHRO": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnhanthropology_8352715",
    },
    "NMNHEDUCATION": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnheducation_10841904",
    },
    "NMNHINV": {
        "base_url": "https://naturalhistory.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://naturalhistory.si.edu/object/nmnhinvertebratezoology_14688577",
    },
    "NPG": {
        "base_url": "https://npg.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://npg.si.edu/object/npg_NPG.2002.184",
    },
    "SIA": {
        "base_url": "https://siarchives.si.edu",
        "path_template": "/collections/{record_ID}",
        "identifier": "record_ID",
        "example": "https://siarchives.si.edu/collections/siris_arc_403511",
    },
    "NPM": {
        "base_url": "https://postalmuseum.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://postalmuseum.si.edu/object/npm_0.293996.232",
    },
}
# Asian Art records keep the "fsg_" record_ID prefix, so NMAA shares the pattern.
MUSEUM_URL_PATTERNS["NMAA"] = MUSEUM_URL_PATTERNS["FSG"]
