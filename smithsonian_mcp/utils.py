"""
Utility functions for the Smithsonian MCP server.
"""

from typing import Dict, Any

def mask_api_key(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Masks the API key in a dictionary of parameters.

    Args:
        params: A dictionary of parameters.

    Returns:
        A new dictionary with the API key masked.
    """
    if "api_key" in params:
        masked_params = params.copy()
        masked_params["api_key"] = "****"
        return masked_params
    return params
