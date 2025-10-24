"""
Tests for the utils module.
"""

import logging
from unittest.mock import MagicMock

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


def test_construct_url_from_record_id():
    """Test URL construction from record_id."""
    from smithsonian_mcp.utils import construct_url_from_record_id

    # Test with valid record_id
    url = construct_url_from_record_id("nmah_1448973")
    assert url == "https://americanhistory.si.edu/collections/object/nmah_1448973"

    # Test with invalid record_id (no underscore)
    url = construct_url_from_record_id("invalid")
    assert url is None

    # Test with empty record_id
    url = construct_url_from_record_id("")
    assert url is None

    # Test with None
    url = construct_url_from_record_id(None)
    assert url is None


def test_bert_puppet_parsing():
    """Test parsing of bert puppet response to validate record_id extraction."""
    import json
    from smithsonian_mcp.api_client import SmithsonianAPIClient

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
    url = construct_url_from_record_id(obj.record_id)
    assert url == "https://americanhistory.si.edu/collections/object/nmah_1448973"

    # Test museum website lookup
    import asyncio
    from smithsonian_mcp.api_client import create_client

    async def test_museum_website():
        client = await create_client()
        units = await client.get_units()
        nmah_unit = next((u for u in units if u.code == "NMAH"), None)
        assert nmah_unit is not None
        assert str(nmah_unit.website) == "https://americanhistory.si.edu/"
        await client.disconnect()

    # Run the async test
    asyncio.run(test_museum_website())
