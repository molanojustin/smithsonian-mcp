"""
Tests for the utils module.
"""

import pytest

from smithsonian_mcp.utils import resolve_museum_code


def test_resolve_museum_code_exact_match():
    """Test exact matches from MUSEUM_MAP."""
    assert resolve_museum_code("asian art") == "NMAA"
    assert resolve_museum_code("american art") == "SAAM"
    assert resolve_museum_code("natural history") == "NMNH"


def test_resolve_museum_code_case_insensitive():
    """Test case insensitive matching."""
    assert resolve_museum_code("ASIAN ART") == "NMAA"
    assert resolve_museum_code("Asian Art") == "NMAA"


def test_resolve_museum_code_with_prefixes():
    """Test matching with common prefixes removed."""
    assert resolve_museum_code("Smithsonian Asian Art Museum") == "NMAA"
    assert resolve_museum_code("National Museum of Natural History") == "NMNH"
    assert resolve_museum_code("Smithsonian American Art Museum") == "SAAM"


def test_resolve_museum_code_partial_match():
    """Test partial matching when input contains map key."""
    assert resolve_museum_code("Asian Art Museum") == "NMAA"
    assert resolve_museum_code("American Art Museum") == "SAAM"


def test_resolve_museum_code_direct_codes():
    """Test direct museum code matching."""
    assert resolve_museum_code("SAAM") == "SAAM"
    assert resolve_museum_code("FSG") == "NMAA"  # legacy Freer|Sackler code
    assert resolve_museum_code("NMNH") == "NMNH"


def test_resolve_museum_code_word_overlap():
    """Test word-based matching for significant overlap."""
    assert resolve_museum_code("Hirshhorn Museum") == "HMSG"
    assert resolve_museum_code("Portrait Gallery") == "NPG"


def test_resolve_museum_code_no_match():
    """Test that invalid museum names return None."""
    assert resolve_museum_code("Invalid Museum") is None
    assert resolve_museum_code("") is None
    assert resolve_museum_code("   ") is None


def test_resolve_museum_code_edge_cases():
    """Test edge cases and variations."""
    # Should handle extra spaces
    assert resolve_museum_code("  asian art  ") == "NMAA"

    # Should handle museum name variations
    assert resolve_museum_code("Freer and Sackler") == "NMAA"
    assert resolve_museum_code("Cooper Hewitt") == "CHNDM"


def test_resolve_museum_code_expanded_map():
    """Test the expanded MUSEUM_MAP with full museum names."""
    # Full Smithsonian museum names
    assert resolve_museum_code("Smithsonian Asian Art Museum") == "NMAA"
    assert resolve_museum_code("Smithsonian American Art Museum") == "SAAM"
    assert resolve_museum_code("Smithsonian Natural History Museum") == "NMNH"
    assert resolve_museum_code("National Museum of Asian Art") == "NMAA"
    assert resolve_museum_code("Freer and Sackler Galleries") == "NMAA"
    assert resolve_museum_code("Hirshhorn Museum and Sculpture Garden") == "HMSG"
    assert (
        resolve_museum_code("National Museum of African American History and Culture")
        == "NMAAHC"
    )


def test_resolve_museum_code_unit_code_fixes():
    """Real index codes: NMAA for Asian Art, NMNH aggregate, NMAH, case-insensitive."""
    assert resolve_museum_code("Freer") == "NMAA"
    assert resolve_museum_code("Sackler") == "NMAA"
    assert resolve_museum_code("fsg") == "NMAA"
    assert resolve_museum_code("NMAA") == "NMAA"
    assert resolve_museum_code("American History") == "NMAH"
    assert (
        resolve_museum_code("Smithsonian's National Museum of American History")
        == "NMAH"
    )
    assert resolve_museum_code("Natural History") == "NMNH"
    assert resolve_museum_code("nmnh") == "NMNH"
    assert resolve_museum_code("nmafa") == "NMAfA"
    assert resolve_museum_code("NMAFA") == "NMAfA"
    assert resolve_museum_code("nmnhpaleo") == "NMNHPALEO"


def test_resolve_museum_code_prefers_longest_match():
    """Longer names win over shorter names they contain."""
    assert resolve_museum_code("African American History Museum") == "NMAAHC"
    assert resolve_museum_code("Air & Space Museum") == "NASM"
    assert resolve_museum_code("The Hirshhorn") == "HMSG"
    assert resolve_museum_code("Asian") == "NMAA"


def test_normalize_unit_code_and_query_clause():
    """Unit codes map to the clauses the search index understands."""
    from smithsonian_mcp.query import unit_code_query_clause
    from smithsonian_mcp.utils import normalize_unit_code

    assert normalize_unit_code("FSG") == "NMAA"
    assert normalize_unit_code("nmafa") == "NMAfA"
    assert normalize_unit_code("  ") is None
    assert unit_code_query_clause("NMAH") == "unit_code:NMAH"
    assert unit_code_query_clause("NMNH") == "unit_code:NMNH*"
    assert unit_code_query_clause("nmnh") == "unit_code:NMNH*"
    assert unit_code_query_clause("FSG") == "unit_code:NMAA"
    assert unit_code_query_clause("OFEO-SG") == 'unit_code:"OFEO-SG"'
    assert unit_code_query_clause("NMNHP*") == "unit_code:NMNHP*"
    assert unit_code_query_clause('X" OR unit_code:"Y') == (
        r'unit_code:"X\" OR unit_code:\"Y"'
    )
    assert unit_code_query_clause(None) is None


def test_constants_unit_codes():
    """Constants list the real codes, without duplicates or dead codes."""
    from smithsonian_mcp.constants import (
        KNOWN_UNIT_CODES,
        MUSEUM_MAP,
        UNIT_INFO,
        VALID_MUSEUM_CODES,
    )

    assert len(KNOWN_UNIT_CODES) == len(set(KNOWN_UNIT_CODES)) == 48
    assert "FSG" not in VALID_MUSEUM_CODES
    assert "NMAA" in VALID_MUSEUM_CODES and "NMNH" in VALID_MUSEUM_CODES
    assert set(VALID_MUSEUM_CODES) <= set(UNIT_INFO)
    assert set(MUSEUM_MAP.values()) <= set(VALID_MUSEUM_CODES)


def test_clean_text_strips_html():
    """Titles with markup are cleaned for display."""
    from smithsonian_mcp.utils import clean_text

    assert clean_text("<i>The Muppets</i> Lunch Box") == "The Muppets Lunch Box"
    assert clean_text("<I>Bouquet holder</I>,  tripod") == "Bouquet holder, tripod"
    assert clean_text("Fish &amp; Chips &lt;3") == "Fish & Chips <3"
    assert clean_text("a < b and c > d") == "a < b and c > d"
    assert clean_text(None) is None


def test_record_page_url_patterns():
    """Museums whose page URL follows from the record_id get a URL; others None."""
    from smithsonian_mcp.utils import record_page_url

    assert (
        record_page_url("nmah_1448973")
        == "https://americanhistory.si.edu/collections/object/nmah_1448973"
    )
    # Asian Art uses the accession number after the fsg_ prefix
    assert record_page_url("fsg_F1900.47") == "https://asia.si.edu/object/F1900.47"

    test_cases = [
        ("nmaahc_2022.91.10ab", "https://nmaahc.si.edu/object/nmaahc_2022.91.10ab"),
        (
            "nmnhmineralsciences_17183750",
            "https://naturalhistory.si.edu/object/nmnhmineralsciences_17183750",
        ),
        (
            "nmnhpaleobiology_17134484",
            "https://naturalhistory.si.edu/object/nmnhpaleobiology_17134484",
        ),
        (
            "nmnhanthropology_8352715",
            "https://naturalhistory.si.edu/object/nmnhanthropology_8352715",
        ),
        (
            "nmnheducation_10841904",
            "https://naturalhistory.si.edu/object/nmnheducation_10841904",
        ),
        (
            "nmnhinvertebratezoology_14688577",
            "https://naturalhistory.si.edu/object/nmnhinvertebratezoology_14688577",
        ),
        ("npg_NPG.2002.184", "https://npg.si.edu/object/npg_NPG.2002.184"),
        ("npm_0.293996.232", "https://postalmuseum.si.edu/object/npm_0.293996.232"),
        ("siris_arc_403511", "https://siarchives.si.edu/collections/siris_arc_403511"),
    ]
    for record_id, expected_url in test_cases:
        assert record_page_url(record_id) == expected_url, record_id

    # Pages of these museums need record data (record_link, guid, EDAN URL or
    # IDS id), so no URL is built from the record_id
    needs_record_data = [
        "saam_30913",
        "nasm_nv913e903df",
        "hmsg_66.1608",
        "nmafa_ys7a3f230ba",
        "nmai_ws69d7d97b6",
        "acm_dl8b7ab6959",
        "nzp_20190815_002RP",
        "chndm_33665",
        "nmnhbirds_352f6df2a",
        "nmnhbotany_32cbf4c79",
        "nmnhento_339e344dc",
        "nmnhfishes_3ccbe2c66",
        "nmnhherps_359523727",
        "nmnhmammals_30b523759",
        "unknown_123",
    ]
    for record_id in needs_record_data:
        assert record_page_url(record_id) is None, record_id

    for record_id in ("invalid", "", None):
        assert record_page_url(record_id) is None


def test_bert_puppet_parsing():
    """Test parsing of bert puppet response to validate record_id extraction."""
    import json

    from smithsonian_mcp.parsing import parse_object_data
    from smithsonian_mcp.utils import record_page_url

    # Load the bert puppet response
    with open("tests/bert_puppet_response.json", "r", encoding="utf-8") as f:
        response_data = json.load(f)

    obj = parse_object_data(response_data["response"])

    assert obj.id == "ld1-1643398912743-1643398933001-0"
    assert obj.record_id == "nmah_1448973"
    assert obj.title == "Bert Puppet"
    assert obj.unit_code == "NMAH"
    assert (
        record_page_url(obj.record_id)
        == "https://americanhistory.si.edu/collections/object/nmah_1448973"
    )


@pytest.mark.parametrize(
    "record_id, expected",
    [
        (
            "nmah_1444757",
            "https://americanhistory.si.edu/collections/object/nmah_1444757",
        ),
        ("fsg_F1900.47", "https://asia.si.edu/object/F1900.47"),
        ("siris_arc_403511", "https://siarchives.si.edu/collections/siris_arc_403511"),
        ("npg_NPG.71.26", "https://npg.si.edu/object/npg_NPG.71.26"),
        ("npm_1992.2037.1", "https://postalmuseum.si.edu/object/npm_1992.2037.1"),
        ("nmaahc_2013.215.4", "https://nmaahc.si.edu/object/nmaahc_2013.215.4"),
        (
            "nmnhpaleobiology_3526550",
            "https://naturalhistory.si.edu/object/nmnhpaleobiology_3526550",
        ),
        ("saam_1983.95.90", None),  # needs record_link
        ("nmafa_2005-6-55", None),  # needs guid
        ("unknown_1", None),
        ("nounderscore", None),
        (None, None),
    ],
)
def test_record_page_url_needs_no_request(record_id, expected):
    """Pattern URLs are built from the record_id alone, or not at all."""
    from smithsonian_mcp.utils import record_page_url

    assert record_page_url(record_id) == expected


@pytest.mark.parametrize(
    "record_id, unit_code, expected",
    [
        (
            "siris_arc_367768",
            "SIA",
            "https://siarchives.si.edu/collections/siris_arc_367768",
        ),
        # Folklife records share SIRIS ids but have no Archives page (404)
        ("siris_arc_336210", "CFCHFOLKLIFE", None),
        (
            "nmah_1444757",
            "NMAH",
            "https://americanhistory.si.edu/collections/object/nmah_1444757",
        ),
    ],
)
def test_siris_archive_pages_belong_to_sia_only(record_id, unit_code, expected):
    """Only SIA records get siarchives.si.edu pages."""
    from smithsonian_mcp.utils import record_page_url

    assert record_page_url(record_id, unit_code) == expected


@pytest.mark.parametrize(
    "name, code",
    [
        ("American History", "NMAH"),
        ("American History museum", "NMAH"),
        ("Smithsonian National Museum of American History", "NMAH"),
        ("nmah", "NMAH"),
        ("Natural History", "NMNH"),
        ("National Museum of Natural History", "NMNH"),
        ("Natural History museum in DC", "NMNH"),
        ("NMNHPALEO", "NMNHPALEO"),
        ("Asian art museum", "NMAA"),
        ("Freer Gallery of Art", "NMAA"),
        ("FSG", "NMAA"),
        ("African Art", "NMAfA"),
        ("Museum of African Art", "NMAfA"),
        ("nmafa", "NMAfA"),
        ("African American Museum", "NMAAHC"),
        ("African American History Museum", "NMAAHC"),
        ("National Museum of African American History and Culture", "NMAAHC"),
        ("American Art", "SAAM"),
        ("Renwick Gallery", "SAAM"),
        ("Air and Space", "NASM"),
        ("Udvar-Hazy Center", "NASM"),
        ("Portrait Gallery", "NPG"),
        ("Hirshhorn", "HMSG"),
        ("Cooper Hewitt", "CHNDM"),
        ("American Indian Museum", "NMAI"),
        ("Postal Museum", "NPM"),
        ("National Zoo", "NZP"),
        ("Archives of American Art", "AAA"),
        ("Smithsonian Institution Archives", "SIA"),
        ("Anacostia", "ACM"),
        ("Louvre", None),
        ("Museum of Modern Art", None),
        ("Metropolitan Museum of Art", None),
        ("American Museum", None),  # ambiguous: only generic words
    ],
)
def test_museum_resolution_matrix(name, code):
    """Every informative word must match; generic-only names do not resolve."""
    assert resolve_museum_code(name) == code
