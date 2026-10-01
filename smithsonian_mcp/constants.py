"""
Constants and static mappings used by the MCP server.

Unit codes were checked against ``GET /terms/unit_code`` of the Smithsonian Open
Access API. Codes in ``ARCHIVAL_UNIT_CODES`` only publish archival records, which
the object search used by this server does not return.
"""

from typing import Dict, FrozenSet, List

from . import __version__

SERVER_VERSION = __version__

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
# searches return nothing for them.
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

# Display information for each unit: name, description, website, location.
UNIT_INFO: Dict[str, Dict[str, str]] = {
    "AAA": {
        "name": "Archives of American Art",
        "description": "Papers and records documenting the visual arts in America",
        "website": "https://www.aaa.si.edu/",
        "location": "Washington, DC",
    },
    "AAG": {
        "name": "Archives of American Gardens",
        "description": "Records and images of American gardens, Smithsonian Gardens",
        "website": "https://gardens.si.edu/",
        "location": "Washington, DC",
    },
    "ACAH": {
        "name": "Archives Center, National Museum of American History",
        "description": "Archival collections of the National Museum of American History",
        "website": "https://americanhistory.si.edu/",
        "location": "Washington, DC",
    },
    "ACM": {
        "name": "Anacostia Community Museum",
        "description": "Community history and culture of Washington, DC",
        "website": "https://anacostia.si.edu/",
        "location": "Washington, DC",
    },
    "ACMA": {
        "name": "Anacostia Community Museum Archives",
        "description": "Archival collections of the Anacostia Community Museum",
        "website": "https://anacostia.si.edu/",
        "location": "Washington, DC",
    },
    "CFCHFOLKLIFE": {
        "name": "Ralph Rinzler Folklife Archives and Collections",
        "description": "Center for Folklife and Cultural Heritage collections",
        "website": "https://folklife.si.edu/",
        "location": "Washington, DC",
    },
    "CHNDM": {
        "name": "Cooper Hewitt, Smithsonian Design Museum",
        "description": "Historic and contemporary design",
        "website": "https://www.cooperhewitt.org/",
        "location": "New York, NY",
    },
    "CHSDM": {
        "name": "Cooper Hewitt, Smithsonian Design Museum Archives",
        "description": "Archival collections of Cooper Hewitt",
        "website": "https://www.cooperhewitt.org/",
        "location": "New York, NY",
    },
    "EEPA": {
        "name": "Eliot Elisofon Photographic Archives",
        "description": "Photographic archives of the National Museum of African Art",
        "website": "https://africa.si.edu/",
        "location": "Washington, DC",
    },
    "FBR": {
        "name": "Smithsonian Field Book Project",
        "description": "Field books and notes from scientific expeditions",
        "website": "https://www.si.edu/",
        "location": "Washington, DC",
    },
    "FSA": {
        "name": "National Museum of Asian Art Archives",
        "description": "Archival collections of the National Museum of Asian Art",
        "website": "https://asia.si.edu/",
        "location": "Washington, DC",
    },
    "HAC": {
        "name": "Smithsonian Gardens, Horticultural Artifacts Collection",
        "description": "Garden and floral artifacts",
        "website": "https://gardens.si.edu/",
        "location": "Washington, DC",
    },
    "HMSG": {
        "name": "Hirshhorn Museum and Sculpture Garden",
        "description": "Modern and contemporary art",
        "website": "https://hirshhorn.si.edu/",
        "location": "Washington, DC",
    },
    "HSFA": {
        "name": "Human Studies Film Archives",
        "description": "Ethnographic film and video archives",
        "website": "https://anthropology.si.edu/",
        "location": "Suitland, MD",
    },
    "NAA": {
        "name": "National Anthropological Archives",
        "description": "Anthropological papers, photographs and records",
        "website": "https://anthropology.si.edu/",
        "location": "Suitland, MD",
    },
    "NASM": {
        "name": "National Air and Space Museum",
        "description": "Aviation and space exploration",
        "website": "https://airandspace.si.edu/",
        "location": "Washington, DC and Chantilly, VA",
    },
    "NASMAC": {
        "name": "National Air and Space Museum Archives",
        "description": "Archival collections of the National Air and Space Museum",
        "website": "https://airandspace.si.edu/",
        "location": "Chantilly, VA",
    },
    "NMAA": {
        "name": "National Museum of Asian Art",
        "description": "Asian art (Freer Gallery of Art and Arthur M. Sackler Gallery)",
        "website": "https://asia.si.edu/",
        "location": "Washington, DC",
    },
    "NMAAHC": {
        "name": "National Museum of African American History and Culture",
        "description": "African American history and culture",
        "website": "https://nmaahc.si.edu/",
        "location": "Washington, DC",
    },
    "NMAH": {
        "name": "National Museum of American History",
        "description": "American history museum",
        "website": "https://americanhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMAI": {
        "name": "National Museum of the American Indian",
        "description": "Native American art, history and culture",
        "website": "https://americanindian.si.edu/",
        "location": "Washington, DC and New York, NY",
    },
    "NMAIA": {
        "name": "National Museum of the American Indian Archives",
        "description": "Archival collections of the National Museum of the American Indian",
        "website": "https://americanindian.si.edu/",
        "location": "Suitland, MD",
    },
    "NMAfA": {
        "name": "National Museum of African Art",
        "description": "Traditional and contemporary African art",
        "website": "https://africa.si.edu/",
        "location": "Washington, DC",
    },
    NMNH_AGGREGATE_CODE: {
        "name": "National Museum of Natural History",
        "description": "All Natural History departments; searches cover every NMNH unit",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHANTHRO": {
        "name": "National Museum of Natural History, Anthropology",
        "description": "Anthropology department",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHBIRDS": {
        "name": "National Museum of Natural History, Birds",
        "description": "Vertebrate Zoology, Birds division",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHBOTANY": {
        "name": "National Museum of Natural History, Botany",
        "description": "Botany department (US National Herbarium)",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHEDUCATION": {
        "name": "National Museum of Natural History, Education and Outreach",
        "description": "Education and outreach collections",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHENTO": {
        "name": "National Museum of Natural History, Entomology",
        "description": "Entomology department",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHFISHES": {
        "name": "National Museum of Natural History, Fishes",
        "description": "Vertebrate Zoology, Fishes division",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHHERPS": {
        "name": "National Museum of Natural History, Amphibians and Reptiles",
        "description": "Vertebrate Zoology, Herpetology division",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHINV": {
        "name": "National Museum of Natural History, Invertebrate Zoology",
        "description": "Invertebrate Zoology department",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHMAMMALS": {
        "name": "National Museum of Natural History, Mammals",
        "description": "Vertebrate Zoology, Mammals division",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHMINSCI": {
        "name": "National Museum of Natural History, Mineral Sciences",
        "description": "Minerals, gems, rocks and meteorites",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NMNHPALEO": {
        "name": "National Museum of Natural History, Paleobiology",
        "description": "Fossils, including dinosaurs",
        "website": "https://naturalhistory.si.edu/",
        "location": "Washington, DC",
    },
    "NPG": {
        "name": "National Portrait Gallery",
        "description": "Portraits of notable Americans",
        "website": "https://npg.si.edu/",
        "location": "Washington, DC",
    },
    "NPM": {
        "name": "National Postal Museum",
        "description": "Postal history and philately",
        "website": "https://postalmuseum.si.edu/",
        "location": "Washington, DC",
    },
    "NPMA": {
        "name": "National Postal Museum Archives",
        "description": "Archival collections of the National Postal Museum",
        "website": "https://postalmuseum.si.edu/",
        "location": "Washington, DC",
    },
    "NZP": {
        "name": "Smithsonian's National Zoo and Conservation Biology Institute",
        "description": "National Zoo",
        "website": "https://nationalzoo.si.edu/",
        "location": "Washington, DC",
    },
    "OCIO_DPO3D": {
        "name": "Smithsonian Digitization Program Office, 3D",
        "description": "3D digitized objects from several units",
        "website": "https://3d.si.edu/",
        "location": "Washington, DC",
    },
    "OFEO-SG": {
        "name": "Smithsonian Gardens",
        "description": "Living plant collections, including the orchid collection",
        "website": "https://gardens.si.edu/",
        "location": "Washington, DC",
    },
    "SAAM": {
        "name": "Smithsonian American Art Museum",
        "description": "American art, including the Renwick Gallery",
        "website": "https://americanart.si.edu/",
        "location": "Washington, DC",
    },
    "SAAMPAIK": {
        "name": "Smithsonian American Art Museum, Nam June Paik Archive",
        "description": "Nam June Paik papers, Research and Scholars Center",
        "website": "https://americanart.si.edu/",
        "location": "Washington, DC",
    },
    "SI": {
        "name": "Smithsonian Institution",
        "description": "Institution-wide archival records",
        "website": "https://www.si.edu/",
        "location": "Washington, DC",
    },
    "SIA": {
        "name": "Smithsonian Institution Archives",
        "description": "Records of the Smithsonian Institution",
        "website": "https://siarchives.si.edu/",
        "location": "Washington, DC",
    },
    "SIL": {
        "name": "Smithsonian Libraries",
        "description": "Books, trade literature and library collections",
        "website": "https://library.si.edu/",
        "location": "Washington, DC",
    },
    "SILAF": {
        "name": "Smithsonian Libraries, Art and Artist Files",
        "description": "Art and artist vertical files",
        "website": "https://library.si.edu/",
        "location": "Washington, DC",
    },
    "SILNMAHTL": {
        "name": "Smithsonian Libraries, Trade Literature",
        "description": "Trade catalogs at the American History Museum Library",
        "website": "https://library.si.edu/",
        "location": "Washington, DC",
    },
    "SLA_SRO": {
        "name": "Smithsonian Libraries and Archives, Research Online",
        "description": "Publications by Smithsonian researchers",
        "website": "https://library.si.edu/",
        "location": "Washington, DC",
    },
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
    "SAAM": {
        "base_url": "{record_link}",  # uses americanart.si.edu, but record_link has full link
        "path_template": "",
        "identifier": "record_link",
        "example": "https://americanart.si.edu/collections/search/artwork/?id=30913",
    },
    "NASM": {
        "base_url": "{record_link}",  # uses n2t link that redirects to the actual link
        "path_template": "",
        "identifier": "record_link",
        "example": "http://n2t.net/ark:/65665/nv913e903df-63e7-4cad-aa80-ca3dfda681a4",
    },
    "NPG": {
        "base_url": "https://npg.si.edu",
        "path_template": "/object/{record_ID}",
        "identifier": "record_ID",
        "example": "https://npg.si.edu/object/npg_NPG.2002.184",
    },
    "HMSG": {
        "base_url": "https://hirshhorn.si.edu",
        "path_template": "/collection/artwork/?edanUrl={url}",
        "identifier": "url",
        "example": "https://hirshhorn.si.edu/collection/artwork/?edanUrl=edanmdm:hmsg_66.1608",
    },
    "NMAfA": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/ys7a3f230ba-972a-4ddf-82be-269516cb20ed",
    },
    "NMAI": {
        "base_url": "{record_link}",  # uses americanindian.si.edu, but record_link has full link
        "path_template": "",
        "identifier": "record_link",
        "example": "http://n2t.net/ark:/65665/ws69d7d97b6-84fc-4f08-883e-ecc2ee0e38c7",
    },
    "ACM": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/dl8b7ab6959-5362-49e1-84a3-f8dbd0c3e2e0",
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
    "NZP": {
        "base_url": "https://ids.si.edu",
        "path_template": "/ids/deliveryService?id={idsId}",
        "identifier": "idsId",
        "example": "https://ids.si.edu/ids/deliveryService?id=NZP-20190815_002RP",
    },
    "CHNDM": {
        "base_url": "{record_link}",
        "path_template": "",
        "identifier": "record_link",
        "example": "https://collection.cooperhewitt.org/view/objects/asitem/id/33665",
    },
    "NMNHBIRDS": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/352f6df2a-7cf0-42ad-b9ad-dbaaff2bbc25",
    },
    "NMNHBOTANY": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/32cbf4c79-da2d-4333-81db-ae926c2bd536",
    },
    "NMNHENTO": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/339e344dc-c269-435f-99ef-d009f12fd5d5",
    },
    "NMNHFISHES": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/3ccbe2c66-aa94-4570-88b1-44896089cfa1",
    },
    "NMNHHERPS": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/359523727-cb45-403c-bb71-e3c31b743355",
    },
    "NMNHMAMMALS": {
        "base_url": "{guid}",
        "path_template": "",
        "identifier": "guid",
        "example": "http://n2t.net/ark:/65665/30b523759-352a-478c-b8ed-62dc1b38dd6f",
    },
}
# Asian Art records keep the "fsg_" record_ID prefix, so NMAA shares the pattern.
MUSEUM_URL_PATTERNS["NMAA"] = MUSEUM_URL_PATTERNS["FSG"]
