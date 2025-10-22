"""
Museum-specific data and helper functions for the Smithsonian MCP server.

This module contains cached museum object types and utility functions
for working with museum collections.
"""

from typing import Dict, List

# Museum-specific object types discovered from Smithsonian Open Access API
# These represent the actual object types available in each museum's collections
MUSEUM_OBJECT_TYPES: Dict[str, List[str]] = {
    "SAAM": [
        "decorative arts", "decorative arts-ceramic", "decorative arts-fiber",
        "decorative arts-furniture", "decorative arts-glass", "decorative arts-jewelry",
        "drawing", "graphic arts", "graphic arts-mechanical reproduction",
        "graphic arts-print", "other", "painting", "photography",
        "photography-photoprint", "sculpture", "sculpture-relief"
    ],
    "NASM": [
        "avionics-autopilots", "avionics-communication",
        "avionics-electronic/satellite navigation", "awards-certificates",
        "awards-medals & ribbons", "craft-aircraft", "craft-aircraft parts",
        "craft-balloon", "craft-miscellaneous", "craft-missile & rocket parts",
        "craft-missiles & rockets", "equipment-breathing devices",
        "equipment-miscellaneous", "equipment-parachutes", "equipment-photographic",
        "equipment-scientific devices", "equipment-test", "instruments-engine & fuel",
        "instruments-flight management", "instruments-miscellaneous",
        "instruments-navigational", "instruments-scientific", "instruments-test",
        "literature and research-letters (archives)", "memorabilia",
        "memorabilia-events", "memorabilia-people", "models-aircraft",
        "models-crewed spacecraft & parts", "models-miscellaneous",
        "models-recognition", "models-uncrewed spacecraft & parts",
        "personal equipment-accessories", "personal equipment-communications gear",
        "personal equipment-helmets & headwear", "personal equipment-medical",
        "personal equipment-uniforms: military", "propulsion-accessories (to an engine)",
        "propulsion-components (engine parts)", "propulsion-reciprocating & rotary",
        "propulsion-rocket engines", "propulsion-turbines (jet)", "spacecraft-crewed",
        "spacecraft-crewed-special/commemorative", "spacecraft-crewed-test vehicles",
        "spacecraft-uncrewed", "spacecraft-uncrewed-communications",
        "spacecraft-uncrewed-test vehicles"
    ],
    "NMAH": [
        "?", "amulet", "badge", "barrel, pistol", "bayonet, sword", "bicycle",
        "book", "bowl, tea", "broadside", "bumper sticker", "button",
        "cabinet card", "camera", "cannon", "carbine", "card, football",
        "cartoon", "cartridge", "cathode ray tube", "certificate", "certified proof",
        "coin", "comic", "compote", "decoration, holiday", "diathermy machine",
        "documentation", "doll", "drawings", "dress, 2-piece",
        "electro-magnetic machine", "electronic payment terminal", "ephemera",
        "face, mold, plaster", "figurine", "film reel", "filters, gas",
        "fire mark", "flask, slender", "gelatin silver print", "geometric model",
        "goblet", "gun part", "haemacytometer", "harmonica", "insignia",
        "insulator", "invitation", "jar", "lace", "leggings, pair of",
        "letter", "lithograph", "master disc", "matrices, set of",
        "matrices, type of", "medal", "microcomputer component", "mold, pipe",
        "mug", "music chart", "needle making machine", "note", "opener, can",
        "pamphlet", "paper money", "part, saddle", "pattern", "pendant",
        "phonograph repeater", "pin", "pistol", "pitcher", "placecards",
        "platinum print", "platter", "portfolio", "poster", "poster, summer olympics",
        "print", "proof page, skateboarding", "real photo postcard", "roll",
        "scissors", "script", "sewing machine patent model", "sheet music",
        "ship hull construction, patent model", "shotgun", "shunt, galvanometer",
        "spectrophotometer", "spoon", "stereograph", "stylus, glass", "teapot",
        "telegraph muirhead recorder suspension", "tripod", "trophy",
        "trunk, metal", "twister, thread", "vase", "view-master reel",
        "vitamin product", "watch movement", "whisk", "women's leggings",
        "wood type, batch of"
    ],
    "CHNDM": [
        "albums (bound) & books", "animals", "architecture", "architecture, interiors",
        "bound print", "ceramics", "containers", "costume & accessories", "cutlery",
        "decorative arts", "embroidery & stitching", "figures", "furniture",
        "glasswares", "graphic design", "interiors", "jewelry", "lace", "landscapes",
        "lighting", "metalwork", "mural designs", "nature studies", "ornament",
        "print", "printed, dyed & painted textiles", "sample books", "seascapes",
        "textile designs", "theater", "tiles", "toys & games", "transportation",
        "trimmings", "wallcoverings", "wallpaper designs", "wood engraving. vignette.",
        "woven textiles"
    ],
    # Note: NMNH, NPG, AAA, and other museums returned 0 objects in our sampling
    # They may have different object types or require different sampling strategies
}

# Helper function to get object types for a museum
def get_museum_object_types(museum_code: str) -> List[str]:
    """
    Get the known object types for a specific museum.

    Args:
        museum_code: The museum code (e.g., 'SAAM', 'NASM')

    Returns:
        List of object types available in that museum, or empty list if unknown
    """
    return MUSEUM_OBJECT_TYPES.get(museum_code.upper(), [])

# Helper function to check if a museum has a specific object type
def museum_has_object_type(museum_code: str, object_type: str) -> bool:
    """
    Check if a museum has a specific object type.

    Args:
        museum_code: The museum code (e.g., 'SAAM', 'NASM')
        object_type: The object type to check for

    Returns:
        True if the museum has this object type, False otherwise
    """
    museum_types = get_museum_object_types(museum_code)
    return object_type.lower().strip() in [t.lower().strip() for t in museum_types]