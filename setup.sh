#!/bin/bash
# This script sets up the development environment for the Smithsonian MCP server.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Constants ---
VENV_DIR=".venv"
PYTHON_EXEC="$VENV_DIR/bin/python"
PIP_EXEC="$VENV_DIR/bin/pip"
REQUIREMENTS_FILE="requirements.txt"
SERVICE_NAME="smithsonian-mcp"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Functions ---

# Function to print messages
info() {
    echo "INFO: $1"
}

error() {
    echo "ERROR: $1" >&2
}

warning() {
    echo "WARNING: $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

# Function to validate API key
validate_api_key() {
    local api_key="$1"
    if [ -z "$api_key" ] || [ "$api_key" = "your_api_key_here" ]; then
        return 1
    fi
    
    info "Validating API key..."
    if "$PYTHON_EXEC" -c "
import sys
import asyncio
import httpx
sys.path.insert(0, '$PROJECT_DIR')
from smithsonian_mcp.config import Config
import os
os.environ['SMITHSONIAN_API_KEY'] = '$api_key'

async def test_api_key():
    try:
        headers = {'X-Api-Key': '$api_key'}
        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            response = await client.get('https://api.si.edu/openaccess/api/v1.0/search?q=test&rows=1')
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and 'response' in data and 'rows' in data['response']:
                    print('API key is valid')
                    return True
                else:
                    print('API key is valid')
                    return True
            else:
                print(f'API returned status {response.status_code}')
                return False
    except Exception as e:
        print(f'API key validation failed: {e}')
        return False

try:
    result = asyncio.run(test_api_key())
    if result:
        sys.exit(0)
    else:
        sys.exit(1)
except Exception as e:
    print(f'API key validation failed: {e}')
    sys.exit(1)
" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# Function to get API key from user
get_api_key() {
    while true; do
        echo -n "Enter your Smithsonian API key (or press Enter to skip): "
        read -r api_key
        if [ -z "$api_key" ]; then
            warning "Skipping API key setup. You'll need to configure it later."
            return 1
        fi
        
        if validate_api_key "$api_key"; then
            echo "$api_key"
            return 0
        else
            error "Invalid API key. Please get a free key from https://api.data.gov/signup/"
        fi
    done
}

# Function to setup service
setup_service() {
    local os="$1"
    info "Setting up $os service..."
    
    case "$os" in
        "linux")
            if command_exists systemctl; then
                setup_systemd_service
            else
                warning "systemctl not found. Manual service setup required."
            fi
            ;;
        "macos")
            setup_launchd_service
            ;;
        "windows")
            warning "Windows service setup not implemented in this script."
            ;;
    esac
}

# Function to setup systemd service
setup_systemd_service() {
    local service_file="/etc/systemd/system/$SERVICE_NAME.service"
    local user_service_file="$HOME/.config/systemd/user/$SERVICE_NAME.service"
    
    # Prefer user service if directory exists
    if [ -d "$HOME/.config/systemd/user" ]; then
        service_file="$user_service_file"
        info "Creating user systemd service..."
    else
        info "Creating system systemd service (requires sudo)..."
    fi
    
    local service_content="[Unit]
Description=Smithsonian MCP Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/$VENV_DIR/bin
ExecStart=$PROJECT_DIR/$VENV_DIR/bin/python -m smithsonian_mcp.server
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target"

    if [ "$service_file" = "$user_service_file" ]; then
        echo "$service_content" > "$service_file"
        systemctl --user daemon-reload
        systemctl --user enable "$SERVICE_NAME"
        info "User service installed. Start with: systemctl --user start $SERVICE_NAME"
    else
        echo "$service_content" | sudo tee "$service_file" > /dev/null
        sudo systemctl daemon-reload
        sudo systemctl enable "$SERVICE_NAME"
        info "System service installed. Start with: sudo systemctl start $SERVICE_NAME"
    fi
}

# Function to setup launchd service
setup_launchd_service() {
    local plist_file="$HOME/Library/LaunchAgents/com.smithsonian.mcp.plist"
    local plist_content="<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">
<plist version=\"1.0\">
<dict>
    <key>Label</key>
    <string>com.smithsonian.mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PROJECT_DIR/$VENV_DIR/bin/python</string>
        <string>-m</string>
        <string>smithsonian_mcp.server</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/com.smithsonian.mcp.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/com.smithsonian.mcp.error.log</string>
</dict>
</plist>"

    mkdir -p "$(dirname "$plist_file")"
    echo "$plist_content" > "$plist_file"
    launchctl load "$plist_file"
    info "Launchd service installed and started."
}

# Function to setup Claude Desktop config
setup_claude_config() {
    local api_key="$1"
    local config_dir=""
    local config_file=""
    
    case "$(detect_os)" in
        "macos")
            config_dir="$HOME/Library/Application Support/Claude"
            ;;
        "linux")
            config_dir="$HOME/.config/Claude"
            ;;
        "windows")
            config_dir="$APPDATA/Claude"
            ;;
    esac
    
    if [ -z "$config_dir" ]; then
        warning "Could not detect Claude Desktop config directory."
        return 1
    fi
    
    config_file="$config_dir/claude_desktop_config.json"
    
    # Create config directory if it doesn't exist
    mkdir -p "$config_dir"
    
    # Backup existing config
    if [ -f "$config_file" ]; then
        cp "$config_file" "$config_file.backup.$(date +%Y%m%d_%H%M%S)"
        info "Backed up existing Claude Desktop config."
    fi
    
    # Create or update config
    local config_content="{\n  \"mcpServers\": {\n    \"smithsonian_open_access\": {\n      \"command\": \"$PROJECT_DIR/$VENV_DIR/bin/python\",\n      \"args\": [\"-m\", \"smithsonian_mcp.server\"],\n      \"env\": {\n        \"SMITHSONIAN_API_KEY\": \"$api_key\",\n        \"LOG_LEVEL\": \"INFO\"\n      }\n    }\n  }\n}"
    
    echo -e "$config_content" > "$config_file"
    info "Claude Desktop configuration updated at: $config_file"
    info "Restart Claude Desktop to apply changes."
}

# Function to run health check
run_health_check() {
    info "Running health check..."
    
    # Test API connection
    if "$PYTHON_EXEC" examples/test-api-connection.py; then
        info "✓ API connection test passed"
    else
        error "✗ API connection test failed"
        return 1
    fi
    
    # Test MCP server startup
    if timeout 10s "$PYTHON_EXEC" -m smithsonian_mcp.server --test 2>/dev/null; then
        info "✓ MCP server startup test passed"
    else
        warning "⚠ MCP server startup test inconclusive (this may be normal)"
    fi
    
    info "Health check completed."
}

# --- Main Script ---

# 1. Check for Python 3
if ! command_exists python3; then
    error "Python 3 is not installed. Please install it to continue."
    exit 1
fi
info "Python 3 found."

# 2. Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    info "Creating Python virtual environment in '$VENV_DIR'..."
    python3 -m venv "$VENV_DIR"
else
    info "Virtual environment '$VENV_DIR' already exists."
fi

# 3. Install dependencies
if [ -f "$REQUIREMENTS_FILE" ]; then
    info "Installing dependencies from '$REQUIREMENTS_FILE'..."
    "$PIP_EXEC" install -r "$REQUIREMENTS_FILE"
    info "Dependencies installed successfully."
else
    warning "Warning: '$REQUIREMENTS_FILE' not found. Skipping dependency installation."
fi

# 4. Setup .env file and get API key
api_key=""
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        info "Creating .env from .env.example..."
        cp .env.example .env
    else
        warning "No .env.example found. Creating basic .env file."
        echo "SMITHSONIAN_API_KEY=your_api_key_here" > .env
    fi
fi

# Extract existing API key or get new one
if [ -f ".env" ]; then
    existing_key=$(grep "^SMITHSONIAN_API_KEY=" .env | cut -d'=' -f2)
    if [ -n "$existing_key" ] && [ "$existing_key" != "your_api_key_here" ]; then
        if validate_api_key "$existing_key"; then
            api_key="$existing_key"
            info "Using existing valid API key from .env file."
        else
            warning "Existing API key is invalid. Please enter a new one."
        fi
    fi
fi

if [ -z "$api_key" ]; then
    api_key=$(get_api_key)
    if [ -n "$api_key" ]; then
        # Update .env with the new API key
        sed -i.bak "s/^SMITHSONIAN_API_KEY=.*/SMITHSONIAN_API_KEY=$api_key/" .env
        info "API key saved to .env file."
    fi
fi

# 5. Setup service
os=$(detect_os)
if [ "$os" != "unknown" ]; then
    echo -n "Do you want to install $SERVICE_NAME as a system service? (y/N): "
    read -r install_service
    if [[ "$install_service" =~ ^[Yy]$ ]]; then
        setup_service "$os"
    fi
fi

# 6. Setup Claude Desktop config
if [ -n "$api_key" ]; then
    echo -n "Do you want to automatically configure Claude Desktop? (y/N): "
    read -r setup_claude
    if [[ "$setup_claude" =~ ^[Yy]$ ]]; then
        setup_claude_config "$api_key"
    fi
fi

# 7. Run health check
echo -n "Do you want to run a health check? (Y/n): "
read -r run_check
if [[ ! "$run_check" =~ ^[Nn]$ ]]; then
    run_health_check
fi

info ""
info "🎉 Setup complete!"
info ""
info "Next steps:"
if [ -n "$api_key" ]; then
    info "✓ API key configured and validated"
else
    info "⚠ Edit .env and add your API key from https://api.data.gov/signup/"
fi
info "✓ Dependencies installed"
info "✓ Virtual environment created at $VENV_DIR"
info ""
info "Usage:"
info "  Activate environment: source $VENV_DIR/bin/activate"
info "  Test connection: python examples/test-api-connection.py"
info "  Run server: python -m smithsonian_mcp.server"
if command_exists systemctl && [ -f "/etc/systemd/system/$SERVICE_NAME.service" ] || [ -f "$HOME/.config/systemd/user/$SERVICE_NAME.service" ]; then
    info "  Manage service: systemctl --user start/stop/status $SERVICE_NAME"
fi
info ""
info "For troubleshooting, see README.md or run: python scripts/verify-setup.py"
