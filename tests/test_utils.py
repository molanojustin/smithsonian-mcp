"""
Tests for the utils module.
"""

import logging
from unittest.mock import MagicMock

import pytest

from smithsonian_mcp.utils import mask_api_key, resolve_museum_code

def test_mask_api_key():
    """Test that the API key is masked."""
    params = {"api_key": "12345"}
    masked_params = mask_api_key(params)
    assert masked_params["api_key"] == "****"

def test_mask_api_key_no_key():
    """Test that the params are not changed if there is no API key."""
    params = {"foo": "bar"}
    masked_params = mask_api_key(params)
    assert masked_params == params


def test_resolve_museum_code_exact_match():
    """Test exact matches from MUSEUM_MAP."""
    assert resolve_museum_code("asian art") == "FSG"
    assert resolve_museum_code("american art") == "SAAM"
    assert resolve_museum_code("natural history") == "NMNH"


def test_resolve_museum_code_case_insensitive():
    """Test case insensitive matching."""
    assert resolve_museum_code("ASIAN ART") == "FSG"
    assert resolve_museum_code("Asian Art") == "FSG"


def test_resolve_museum_code_with_prefixes():
    """Test matching with common prefixes removed."""
    assert resolve_museum_code("Smithsonian Asian Art Museum") == "FSG"
    assert resolve_museum_code("National Museum of Natural History") == "NMNH"
    assert resolve_museum_code("Smithsonian American Art Museum") == "SAAM"


def test_resolve_museum_code_partial_match():
    """Test partial matching when input contains map key."""
    assert resolve_museum_code("Asian Art Museum") == "FSG"
    assert resolve_museum_code("American Art Museum") == "SAAM"


def test_resolve_museum_code_direct_codes():
    """Test direct museum code matching."""
    assert resolve_museum_code("SAAM") == "SAAM"
    assert resolve_museum_code("FSG") == "FSG"
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
    assert resolve_museum_code("  asian art  ") == "FSG"

    # Should handle museum name variations
    assert resolve_museum_code("Freer and Sackler") == "FSG"
    assert resolve_museum_code("Cooper Hewitt") == "CHNDM"


def test_resolve_museum_code_expanded_map():
    """Test the expanded MUSEUM_MAP with full museum names."""
    # Full Smithsonian museum names
    assert resolve_museum_code("Smithsonian Asian Art Museum") == "FSG"
    assert resolve_museum_code("Smithsonian American Art Museum") == "SAAM"
    assert resolve_museum_code("Smithsonian Natural History Museum") == "NMNH"
    assert resolve_museum_code("National Museum of Asian Art") == "FSG"
    assert resolve_museum_code("Freer and Sackler Galleries") == "FSG"
    assert resolve_museum_code("Hirshhorn Museum and Sculpture Garden") == "HMSG"
    assert resolve_museum_code("National Museum of African American History and Culture") == "NMAAHC"


@pytest.mark.asyncio
async def test_construct_url_from_record_id():
    """Test URL construction from record_id."""
    from smithsonian_mcp.utils import construct_url_from_record_id
    from unittest.mock import patch, AsyncMock

    # Test with valid record_id - NMAH
    url = await construct_url_from_record_id("nmah_1448973")
    assert url == "https://americanhistory.si.edu/collections/object/nmah_1448973"

    # Test FSG (uses accession identifier)
    url = await construct_url_from_record_id("fsg_F1900.47")
    assert url == "https://asia.si.edu/object/F1900.47"

    # Test museums that construct URLs directly (record_ID and accession identifiers with plain base_url)
    test_cases = [
        ("nmaahc_2022.91.10ab", "https://nmaahc.si.edu/object/nmaahc_2022.91.10ab"),
        ("nmnhmineralsciences_17183750", "https://naturalhistory.si.edu/object/nmnhmineralsciences_17183750"),
        ("nmnhpaleobiology_17134484", "https://naturalhistory.si.edu/object/nmnhpaleobiology_17134484"),
        ("nmnhanthropology_8352715", "https://naturalhistory.si.edu/object/nmnhanthropology_8352715"),
        ("nmnheducation_10841904", "https://naturalhistory.si.edu/object/nmnheducation_10841904"),
        ("nmnhinvertebratezoology_14688577", "https://naturalhistory.si.edu/object/nmnhinvertebratezoology_14688577"),
        ("npg_NPG.2002.184", "https://npg.si.edu/object/npg_NPG.2002.184"),
        ("npm_0.293996.232", "https://postalmuseum.si.edu/object/npm_0.293996.232"),
        ("siris_arc_403511", "https://siarchives.si.edu/collections/siris_arc_403511"),
    ]

    for record_id, expected_url in test_cases:
        url = await construct_url_from_record_id(record_id)
        assert url == expected_url, f"Failed for {record_id}: expected {expected_url}, got {url}"

    # Test museums that require API data (guid, record_link, url, idsId, or template variables in base_url)
    api_required_cases = [
        "saam_30913",                    # uses {record_link} in base_url
        "nasm_nv913e903df",              # uses {record_link} in base_url
        "hmsg_66.1608",                  # uses url identifier
        "nmafa_ys7a3f230ba",             # uses {guid} in base_url
        "nmai_ws69d7d97b6",              # uses {record_link} in base_url
        "acm_dl8b7ab6959",               # uses {guid} in base_url
        "nzp_20190815_002RP",            # uses idsId identifier
        "chndm_33665",                   # uses {record_link} in base_url
        "nmnhbirds_352f6df2a",           # uses {guid} in base_url
        "nmnhbotany_32cbf4c79",          # uses {guid} in base_url
        "nmnhento_339e344dc",            # uses {guid} in base_url
        "nmnhfishes_3ccbe2c66",          # uses {guid} in base_url
        "nmnhherps_359523727",           # uses {guid} in base_url
        "nmnhmammals_30b523759",         # uses {guid} in base_url
    ]

    # Mock the API fallback to return None
    with patch('smithsonian_mcp.utils._get_url_from_api_record_id', return_value=None):
        for record_id in api_required_cases:
            url = await construct_url_from_record_id(record_id)
            # With mocked API returning None, these should return None
            assert url is None, f"Expected None for API-required museum {record_id}, got {url}"

    # Test with invalid record_id (no underscore)
    url = await construct_url_from_record_id("invalid")
    assert url is None

    # Test with empty record_id
    url = await construct_url_from_record_id("")
    assert url is None

    # Test with None
    url = await construct_url_from_record_id(None)
    assert url is None

    # Test unknown museum (should fall back to API, mocked to return None)
    with patch('smithsonian_mcp.utils._get_url_from_api_record_id', return_value=None):
        url = await construct_url_from_record_id("unknown_123")
        assert url is None


@pytest.mark.asyncio
async def test_bert_puppet_parsing():
    """Test parsing of bert puppet response to validate record_id extraction."""
    import json
    from smithsonian_mcp.api_client import SmithsonianAPIClient
    from smithsonian_mcp.api_client import create_client

    # Load the bert puppet response
    with open("tests/bert_puppet_response.json", "r") as f:
        response_data = json.load(f)

    # Parse the object
    client = SmithsonianAPIClient()
    obj = client._parse_object_data(response_data["response"])

    # Validate the parsed data
    assert obj.id == "ld1-1643398912743-1643398933001-0"
    assert obj.record_id == "nmah_1448973"
    assert obj.title == "Bert Puppet"
    assert obj.unit_code == "NMAH"

    # Test URL construction from record_id
    from smithsonian_mcp.utils import construct_url_from_record_id
    url = await construct_url_from_record_id(obj.record_id)
    assert url == "https://americanhistory.si.edu/collections/object/nmah_1448973"

    # Test museum website lookup
    client = await create_client()
    units = await client.get_units()
    nmah_unit = next((u for u in units if u.code == "NMAH"), None)
    assert nmah_unit is not None
    assert str(nmah_unit.website) == "https://americanhistory.si.edu/"
    await client.disconnect()
