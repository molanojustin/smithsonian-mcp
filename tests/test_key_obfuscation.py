"""
Test to ensure keys gets masked in logs
"""

import asyncio
import unittest
from unittest.mock import patch, AsyncMock

from smithsonian_mcp.api_client import SmithsonianAPIClient

class TestKeyObfuscation(unittest.TestCase):
    def setUp(self):
        self.client = SmithsonianAPIClient()
        self.client.api_key = "test_api_key"

    def test_api_key_not_logged(self):
        test_params = {
            "q": "test_query",
            "unit_code": "ABCdefG",
            "maker": "RuPaul_Charles",
            "start": 0,
            "rows": 10,
        }

        # Setup fake session so we don't need a real connection
        self.client.session = AsyncMock()
        self.client.session.get.side_effect = Exception("Fake API error")

        with patch('smithsonian_mcp.api_client.logger') as mock_logger:
            try:
                asyncio.run(self.client._make_request(
                    endpoint="test",
                    params=test_params
                ))
            except Exception:
                pass  # expected error so we can test logging

            # Ensure logger was called
            self.assertTrue(mock_logger.debug.called)

            # Extract full formatted log message
            log_args = mock_logger.debug.call_args
            log_format_string = log_args[0][0]
            log_params = log_args[0][1:]
            logged_message = log_format_string % log_params

            print("Logged message:", logged_message)

            self.assertNotIn("test_api_key", logged_message)
            self.assertIn("api_key=%2A%2A%2A%2A", logged_message)  # Ensure api_key is masked
