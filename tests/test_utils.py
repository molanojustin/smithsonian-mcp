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
