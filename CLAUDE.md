# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation & Code Style Guidelines

**IMPORTANT: Follow these guidelines strictly:**
- Never use emojis anywhere in the codebase or documentation
- Never use highlighting flags like `**NEW**`, `**UPDATED**`, `**BETA**`, etc. in documentation, comments, or code
- Keep documentation clean, professional, and factual
- Focus on technical accuracy over decorative elements
- Use plain text for emphasis where needed, but avoid unnecessary markup

## Architecture Overview

This is a **Model Context Protocol (MCP) server** for the **Smithsonian Institution's Open Access collections**. The codebase has a multi-layer architecture:

- **Node.js wrapper** (bin/smithsonian-mcp.js): Provides npm/npx installation, automatic Python dependency management, and cross-platform execution
- **Python MCP server** (smithsonian_mcp/server.py): Core FastMCP server with 14 tools for Smithsonian data access
- **API client** (smithsonian_mcp/api_client.py): Handles communication with Smithsonian's API endpoints
- **Data models** (smithsonian_mcp/models.py): Pydantic schemas for Smithsonian objects, search results, and metadata
- **Configuration system** (smithsonian_mcp/config.py): Environment-based configuration with validation

## Development Commands

### Python Dependencies
- Install: `pip install -r requirements.txt`
- Virtual environment: `python3 -m venv .venv`
- Development setup script: `./setup.sh` (full automation)

### Testing & Quality
- Run all tests: `pytest tests/`
- Run specific test file: `pytest tests/test_basic.py -v`
- Run on-view functionality tests: `pytest tests/test_on_view.py -v`
- API connection test: `python examples/test-api-connection.py`
- Formatting: `black smithsonian_mcp/`
- Linting: `pylint smithsonian_mcp/`
- Verify setup: `python scripts/verify-setup.py`

### Package & Distribution
- npm test (pre-publish): `node bin/smithsonian-mcp.js --test`
- npm version bump: Automatically updates git tags and publishes
- Build verification: `npm run test` before publishing

## Key Files & Modules

### Core MCP Functionality
- smithsonian_mcp/server.py: Main MCP server with 12 tools including search, object details, museum info, and on-view status checking
- smithsonian_mcp/api_client.py: Async HTTP client for Smithsonian API endpoints with error handling and rate limiting
- smithsonian_mcp/models.py: Complete Pydantic models for all Smithsonian data structures

### Configuration & Setup
- bin/smithsonian-mcp.js: Node.js entry point that manages Python dependencies and execution
- setup.sh / setup.ps1: Automated setup scripts for different platforms
- config.py: Centralized configuration with environment variable support

### Testing & Examples
- tests/test_basic.py: Core functionality tests
- tests/test_on_view.py: Exhibition status verification tests
- examples/test-api-connection.py: API connectivity verification

## Development Workflow

### Getting Started
1. Run `./setup.sh` for complete environment setup (includes API key validation, service installation options, **Claude Desktop** config)
2. Test API connection: `python examples/test-api-connection.py`
3. Verify MCP server startup: `python -m smithsonian_mcp.server --test`

### Integration Testing
- **Claude Desktop**: Configure via `claude_desktop_config.json` (automatically created by setup.sh)
- **mcpo orchestration**: Use `mcpo-config.json` for multi-MCP server setups
- **VS Code**: Open `.vscode/smithsonian-mcp-workspace.code-workspace`

### Service Management
- **Systemd (Linux)**: `systemctl --user start/stop/status smithsonian-mcp`
- **Launchd (macOS)**: `launchctl load/unload ~/Library/LaunchAgents/com.smithsonian.mcp.plist`

## API & Functionality

### Available MCP Tools
- `simple_explore` - Smart diverse sampling across museums and object types (recommended for basic discovery)
- `continue_explore` - Get more results about the same topic while avoiding duplicates
- `search_collections`: Advanced search with filters (query, unit code, object type, materials, etc.) - Returns max 1000 results per call
- `get_object_details`: Full metadata for specific objects
- `search_by_unit`: Museum-focused searches - Returns max 1000 results per call
- `get_smithsonian_units`: List of all museums
- `get_collection_statistics`: Overview metrics
- `get_objects_on_view`: Currently exhibited objects - Returns max 1000 results per call
- `find_on_view_items`: Comprehensive on-view search with automatic pagination (searches up to 10,000 results across multiple API calls)
- `check_object_on_view`: Individual object exhibition status
- Context tools: `get_*_context` versions return formatted context strings for AI assistants

### Smithsonian API Integration
- Uses official Smithsonian Open Access API (api.si.edu)
- Requires free API key from api.data.gov
- Handles pagination, rate limiting, and error responses
- Supports advanced filtering and metadata enrichment

### Data Features
- 3M+ digitized objects across 19 museums
- CC0 licensed public domain content
- High-resolution images and 3D models
- Exhibition status tracking
- Comprehensive metadata (creators, dates, materials, geographic context)

## Troubleshooting

### Common Issues
- API key validation: Get new key from api.data.gov/signup if invalid
- Python module import: Ensure virtual environment is activated
- mcpo integration: Verify paths in mcpo-config.json are absolute
- Service startup: Check logs for authentication/connection errors

### Debug Mode
Set `LOG_LEVEL=DEBUG` in environment for verbose logging

### Performance Considerations
- Enable caching: `ENABLE_CACHE=true` (default)
- Adjust rate limits via `DEFAULT_RATE_LIMIT` (default: 60/minute)
- Consider object image file sizes (up to 50MB/server default)
- Pagination limits: Most search tools return max 1000 results per call. Use `find_on_view_items` for comprehensive searches up to 10,000 results

### Model Compatibility
For best results with less capable models:
- Use `simple_explore` instead of `search_collections` for basic searches
- The simple tools include automatic fallback behavior and clearer error messages
- Museum name mapping supports common names like "asian art", "american history", etc.
- Results indicate when more content is available through `continue_explore`

## Contributing Guidelines

### Code Standards
- Use Black for formatting
- Pylint for linting (strict requirements)
- Complete type hints on all public functions
- Pydantic models with validation
- Async/await patterns for I/O operations

### Testing Requirements
- Unit tests for all core functions
- Integration tests for API interactions
- API key validation tests
- Cross-platform compatibility testing

### Documentation Updates
- Update README.md for user-facing changes
- Update docstrings for public APIs
- Update setup instructions for new platforms
- Consider impact on integration guides

## Version Release Process

1. Run full test suite
2. Update version in package.json
3. Run `npm version patch/minor/major` (handles git tagging and pushing)
4. GitHub Actions publishes to npm registry
5. Wait for `latest` tag update on npm

## Future Development

### Priority Features (from codebase)
- Multi-modal content search (text, image, 3D) - Current search is text-only
- Batch processing for large collections - Improve performance for bulk operations
- Search result ranking improvements - Better relevancy scoring for complex queries

### Integration Improvements
- Web dashboard for MCP server monitoring and administration
- Enhanced mcpo orchestration support for multi-MCP deployments
- REST API bridge for non-MCP clients 