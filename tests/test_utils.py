"""
Tests for the utils module.
"""

import logging
from unittest.mock import MagicMock

from smithsonian_mcp.utils import mask_api_key

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
