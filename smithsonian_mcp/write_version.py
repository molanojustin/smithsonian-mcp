"""
Script to write the version from package.json to smithsonian_mcp/_version.py
"""

import json
import pathlib

# Read version from package.json with explicit encoding
package_json_path = pathlib.Path("package.json")
version = json.loads(package_json_path.read_text(encoding="utf-8"))["version"]

# Define the content of _version.py with a proper module docstring
VERSION_FILE_CONTENT = f'''"""Auto-generated file. Do not edit manually.

This file defines the __version__ variable for the smithsonian_mcp package.
"""

__version__ = "{version}"
'''

# Write the version to _version.py with utf-8 encoding
version_file_path = pathlib.Path("smithsonian_mcp/_version.py")
version_file_path.write_text(VERSION_FILE_CONTENT, encoding="utf-8")
