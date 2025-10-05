# Claude Desktop & VS Code Integration Guide

Quick setup guide for integrating the Smithsonian MCP Server.

## Setup Checklist

- [ ] Get API key from api.data.gov
- [ ] Install Python dependencies  
- [ ] Copy `.env.example` to `.env` and configure API key
- [ ] Configure Claude Desktop
- [ ] Test integration

## Claude Desktop Integration

### Step 1: Get Your API Key

1. Sign up at [api.data.gov/signup](https://api.data.gov/signup/)
2. No special permissions needed
3. Save your API key

### Step 2: Configure Claude Desktop

**Config File Locations:**
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "smithsonian_open_access": {
      "command": "python",
      "args": ["-m", "smithsonian_mcp.server"],
      "env": {
        "SMITHSONIAN_API_KEY": "your_api_key_here",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

*Or copy the provided `claude-desktop-config.json` and update the API key*

### Step 3: Test Integration

Ask Claude these questions:
1. "What Smithsonian museums are available?"
2. "Search for dinosaur fossils"
3. "Find American paintings from the 1800s"

## VS Code Integration

1. **Open Workspace**: `code smithsonian-mcp-workspace.code-workspace`
2. **Install Dependencies**: Use "Install Dependencies" task
3. **Configure Environment**: Copy `.env.example` to `.env` and set API key
4. **Run Server**: Use "Start MCP Server" task
5. **Test**: Use "Test MCP Server" task to verify API connection
6. **Debug**: Use F5 to debug the server or "Debug with MCP Inspector" task

## Testing

### Quick Test
Run the test script:
```bash
python examples/test-api-connection.py
```

### VS Code Tasks
- **Test MCP Server**: Tests API connection and basic functionality
- **Run Tests**: Executes the pytest test suite
- **Format Code**: Formats code with Black
- **Lint Code**: Runs Pylint for code quality

### Environment Setup
Ensure your `.env` file contains:
```bash
SMITHSONIAN_API_KEY=your_actual_api_key_here
SERVER_NAME=Smithsonian Open Access
LOG_LEVEL=INFO
```

## Troubleshooting

**"MCP Server not found"**
- Check Python path in configuration
- Verify API key is set
- Restart Claude Desktop

**"API Key Invalid"**  
- Verify key from api.data.gov
- Check environment variable spelling

For detailed instructions, see the full documentation files.
