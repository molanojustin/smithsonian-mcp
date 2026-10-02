#!/bin/bash
# This script sets up the development environment for the Smithsonian MCP server.

# Exit immediately if a command exits with a non-zero status.
set -e

# Change to project root directory (parent of this script's directory)
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PROJECT_DIR="$(pwd)"

# --- Constants ---
VENV_DIR=".venv"
PYTHON_EXEC="$VENV_DIR/bin/python"
PIP_EXEC="$VENV_DIR/bin/pip"
# Console script installed into the virtual environment by this script
SERVER_EXEC="$PROJECT_DIR/$VENV_DIR/bin/smithsonian-mcp"
REQUIREMENTS_FILE="config/requirements.txt"
MCPO_EXAMPLE="examples/mcpo-config.json"
MCPO_CONFIG="mcpo-config.json"
SERVICE_NAME="smithsonian-mcp"
# The service serves streamable HTTP; a stdio server with no client attached
# would exit at once and be restarted in a loop.
SERVICE_PORT=8000
SERVICE_ARGS="--transport http --host 127.0.0.1 --port $SERVICE_PORT"
SERVICE_URL="http://127.0.0.1:$SERVICE_PORT/mcp"
# The launchd job writes its log (the server logs to stderr) to this file
LAUNCHD_LOG="$HOME/Library/Logs/com.smithsonian.mcp.log"
# How to manage the service installed by this run, for the closing summary
SERVICE_MANAGE=""

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

# Function to check that a Python interpreter is 3.10 or newer
python_is_supported() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null
}

# Function to check if mcpo is available
check_mcpo() {
    if command_exists mcpo; then
        return 0
    elif command_exists uvx; then
        # Check if mcpo can be run via uvx
        if uvx mcpo --help >/dev/null 2>&1; then
            return 0
        fi
    fi
    return 1
}

# Note: the optional setup steps below are called as `step || warning ...`.
# Bash disables `set -e` inside a function called that way, so each function
# checks its critical commands explicitly and returns 1 on failure.

# Function to write mcpo-config.json from the example with local paths and the API key.
# The example under examples/ is left untouched.
setup_mcpo_config() {
    local api_key="$1"
    info "Setting up mcpo configuration..."

    if [ ! -f "$MCPO_EXAMPLE" ]; then
        warning "$MCPO_EXAMPLE not found. Skipping mcpo setup."
        return 1
    fi

    if [ -z "$api_key" ]; then
        warning "No API key available. Skipping mcpo setup."
        return 1
    fi

    local python_path="$PROJECT_DIR/$VENV_DIR/bin/python"
    # The key goes through the environment, never a command line, and the file
    # is created with owner-only permissions before the key is written to it.
    if ! MCPO_EXAMPLE="$MCPO_EXAMPLE" MCPO_CONFIG="$MCPO_CONFIG" \
        PROJECT_DIR="$PROJECT_DIR" PYTHON_PATH="$python_path" \
        SMITHSONIAN_API_KEY="$api_key" "$PYTHON_EXEC" - <<'PY'
import json
import os
from pathlib import Path

replacements = [
    ("/path/to/your/project/.venv/bin/python", os.environ["PYTHON_PATH"]),
    ("/path/to/your/project", os.environ["PROJECT_DIR"]),
    ("your_api_key_here", os.environ["SMITHSONIAN_API_KEY"]),
]


def fill(value):
    if isinstance(value, str):
        for old, new in replacements:
            value = value.replace(old, new)
        return value
    if isinstance(value, list):
        return [fill(item) for item in value]
    if isinstance(value, dict):
        return {key: fill(item) for key, item in value.items()}
    return value


config = fill(json.loads(Path(os.environ["MCPO_EXAMPLE"]).read_text(encoding="utf-8")))
path = Path(os.environ["MCPO_CONFIG"])
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write(json.dumps(config, indent=2) + "\n")
os.chmod(path, 0o600)
PY
    then
        error "Could not write $MCPO_CONFIG."
        rm -f "$MCPO_CONFIG"
        return 1
    fi

    info "mcpo configuration written to: $PROJECT_DIR/$MCPO_CONFIG"
    info "It contains your API key. Do not commit it."
    info "Python path set to: $python_path"
    info "You can start mcpo with: mcpo --config $MCPO_CONFIG --port 8000"
    return 0
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

# Function to validate API key against the live API.
# The key is passed through the environment and an HTTP header, never on a
# command line or in a URL. All output goes to stderr so that callers can
# capture this function's stdout safely.
validate_api_key() {
    local api_key="$1"
    if [ -z "$api_key" ] || [ "$api_key" = "your_api_key_here" ]; then
        return 1
    fi

    info "Validating API key..." >&2
    if SMITHSONIAN_API_KEY="$api_key" "$PYTHON_EXEC" - <<'PY'
import os
import sys

import httpx

try:
    response = httpx.get(
        "https://api.si.edu/openaccess/api/v1.0/search",
        params={"q": "test", "rows": 1},
        headers={"X-Api-Key": os.environ["SMITHSONIAN_API_KEY"]},
        timeout=10.0,
    )
except httpx.HTTPError as exc:
    print(f"API key validation failed: {exc}", file=sys.stderr)
    sys.exit(1)

if response.status_code == 200:
    print("API key is valid", file=sys.stderr)
    sys.exit(0)

print(f"API returned status {response.status_code}", file=sys.stderr)
sys.exit(1)
PY
    then
        return 0
    else
        return 1
    fi
}

# Function to store the API key in .env, keeping its other settings.
# The key goes through the environment, never a command line, and .env is
# left readable by its owner only.
write_env_key() {
    local api_key="$1"
    SMITHSONIAN_API_KEY="$api_key" "$PYTHON_EXEC" - <<'PY'
import os
from pathlib import Path

path = Path(".env")
key = os.environ["SMITHSONIAN_API_KEY"]
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
updated = []
found = False
for line in lines:
    if line.startswith("SMITHSONIAN_API_KEY="):
        if not found:
            updated.append(f"SMITHSONIAN_API_KEY={key}")
        found = True
    else:
        updated.append(line)
if not found:
    updated.append(f"SMITHSONIAN_API_KEY={key}")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write("\n".join(updated) + "\n")
os.chmod(path, 0o600)
PY
}

# Function to get API key from user.
# Prompts and messages go to stderr; only the validated key is printed to stdout.
get_api_key() {
    local api_key
    while true; do
        printf "Enter your Smithsonian API key (or press Enter to skip): " >&2
        read -r api_key
        if [ -z "$api_key" ]; then
            warning "Skipping API key setup. You'll need to configure it later." >&2
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
                setup_systemd_service || return 1
            else
                warning "systemctl not found. Manual service setup required."
                return 1
            fi
            ;;
        "macos")
            setup_launchd_service || return 1
            ;;
        "windows")
            warning "Windows service setup not implemented in this script."
            return 1
            ;;
    esac
}

# Function to setup systemd service
setup_systemd_service() {
    local service_file="/etc/systemd/system/$SERVICE_NAME.service"
    local user_service_file="$HOME/.config/systemd/user/$SERVICE_NAME.service"
    # User units run as the user and start with the user's default target
    local user_line=""
    local wanted_by="default.target"

    # Prefer user service if directory exists
    if [ -d "$HOME/.config/systemd/user" ]; then
        service_file="$user_service_file"
        info "Creating user systemd service..."
    else
        info "Creating system systemd service (requires sudo)..."
        user_line="User=$USER
"
        wanted_by="multi-user.target"
    fi

    local service_content="[Unit]
Description=Smithsonian MCP Server (streamable HTTP at $SERVICE_URL)
After=network.target

[Service]
Type=simple
${user_line}WorkingDirectory=$PROJECT_DIR
Environment=\"PATH=$PROJECT_DIR/$VENV_DIR/bin\"
ExecStart=\"$SERVER_EXEC\" $SERVICE_ARGS
Restart=always
RestartSec=10

[Install]
WantedBy=$wanted_by"

    if [ "$service_file" = "$user_service_file" ]; then
        echo "$service_content" > "$service_file" \
            || { error "Could not write $service_file."; return 1; }
        systemctl --user daemon-reload \
            || { error "systemctl --user daemon-reload failed."; return 1; }
        systemctl --user enable "$SERVICE_NAME" \
            || { error "systemctl --user enable $SERVICE_NAME failed."; return 1; }
        # A service that is already running keeps its old arguments until restarted
        systemctl --user try-restart "$SERVICE_NAME" \
            || warning "Could not restart $SERVICE_NAME; restart it to apply the new settings."
        info "User service installed. Start with: systemctl --user start $SERVICE_NAME"
        SERVICE_MANAGE="systemctl --user start/stop/status $SERVICE_NAME"
        info "It serves MCP over streamable HTTP at $SERVICE_URL"
    else
        echo "$service_content" | sudo tee "$service_file" > /dev/null \
            || { error "Could not write $service_file."; return 1; }
        sudo systemctl daemon-reload \
            || { error "systemctl daemon-reload failed."; return 1; }
        sudo systemctl enable "$SERVICE_NAME" \
            || { error "systemctl enable $SERVICE_NAME failed."; return 1; }
        sudo systemctl try-restart "$SERVICE_NAME" \
            || warning "Could not restart $SERVICE_NAME; restart it to apply the new settings."
        info "System service installed. Start with: sudo systemctl start $SERVICE_NAME"
        SERVICE_MANAGE="sudo systemctl start/stop/status $SERVICE_NAME"
        info "It serves MCP over streamable HTTP at $SERVICE_URL"
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
        <string>$SERVER_EXEC</string>
        <string>--transport</string>
        <string>http</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>$SERVICE_PORT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LAUNCHD_LOG</string>
    <key>StandardErrorPath</key>
    <string>$LAUNCHD_LOG</string>
</dict>
</plist>"

    mkdir -p "$(dirname "$plist_file")" \
        || { error "Could not create $(dirname "$plist_file")."; return 1; }
    # A job loaded by an earlier run keeps its old arguments until it is unloaded
    if [ -f "$plist_file" ]; then
        launchctl unload "$plist_file" >/dev/null 2>&1 || true
    fi
    echo "$plist_content" > "$plist_file" \
        || { error "Could not write $plist_file."; return 1; }
    launchctl load "$plist_file" \
        || { error "launchctl load $plist_file failed."; return 1; }
    info "Launchd service installed and started."
    SERVICE_MANAGE="launchctl unload/load $plist_file"
    info "It serves MCP over streamable HTTP at $SERVICE_URL"
    info "Its log is $LAUNCHD_LOG"
}

# Function to add this server to the Claude Desktop config.
# Existing entries in the config file are preserved; a backup is written first.
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
    mkdir -p "$config_dir" \
        || { error "Could not create $config_dir."; return 1; }

    # Backup existing config
    if [ -f "$config_file" ]; then
        cp "$config_file" "$config_file.backup.$(date +%Y%m%d_%H%M%S)" \
            || { error "Could not back up $config_file."; return 1; }
        info "Backed up existing Claude Desktop config."
    fi

    # Merge the server entry into the existing config. On invalid JSON the
    # file is left unchanged and the step fails.
    if ! CONFIG_FILE="$config_file" SERVER_EXEC="$SERVER_EXEC" SMITHSONIAN_API_KEY="$api_key" \
        "$PYTHON_EXEC" - <<'PY'
import json
import os
import sys
from pathlib import Path

path = Path(os.environ["CONFIG_FILE"])
config = {}
if path.exists():
    text = path.read_text(encoding="utf-8-sig")
    if text.strip():
        try:
            config = json.loads(text)
        except ValueError as exc:
            print(f"ERROR: {path} is not valid JSON ({exc}).", file=sys.stderr)
            print("ERROR: Fix the file or add the server entry by hand.", file=sys.stderr)
            sys.exit(1)

servers = config.setdefault("mcpServers", {}) if isinstance(config, dict) else None
if not isinstance(servers, dict):
    print(f"ERROR: {path} does not contain a JSON object with an mcpServers object.", file=sys.stderr)
    sys.exit(1)

servers["smithsonian_open_access"] = {
    "command": os.environ["SERVER_EXEC"],
    # Explicit, so MCP_TRANSPORT in .env cannot switch the client's server to HTTP
    "args": ["--transport", "stdio"],
    "env": {
        "SMITHSONIAN_API_KEY": os.environ["SMITHSONIAN_API_KEY"],
        "LOG_LEVEL": "INFO",
    },
}
path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
    then
        return 1
    fi

    info "Claude Desktop configuration updated at: $config_file"
    info "Restart Claude Desktop to apply changes."
}

# Function to run health check
run_health_check() {
    info "Running health check..."

    # Test API connection
    if "$PYTHON_EXEC" examples/test-api-connection.py; then
        info "API connection test passed"
    else
        error "API connection test failed"
        return 1
    fi

    # Start the server with no client attached: it should start, read EOF on
    # stdin, and exit cleanly. A missing API key or import error exits non-zero.
    if "$SERVER_EXEC" --transport stdio < /dev/null > /dev/null 2>&1; then
        info "MCP server startup test passed"
    else
        error "MCP server failed to start. Run $SERVER_EXEC to see the error."
        return 1
    fi

    info "Health check completed."
}

# --- Main Script ---

# 1-3. Create the virtual environment and install dependencies plus the package
if command_exists uv; then
    info "uv found. Installing locked dependencies into '$VENV_DIR' with uv sync..."
    uv sync --group dev
    info "Dependencies installed successfully."
else
    info "uv not found. Falling back to python3 -m venv and pip."
    if ! command_exists python3; then
        error "Python 3 is not installed. Install Python 3.10 or newer, or install uv."
        exit 1
    fi
    if ! python_is_supported python3; then
        error "python3 is $(python3 --version 2>&1). Python 3.10 or newer is required."
        exit 1
    fi
    info "$(python3 --version) found."

    if [ ! -d "$VENV_DIR" ]; then
        info "Creating Python virtual environment in '$VENV_DIR'..."
        python3 -m venv "$VENV_DIR"
    else
        info "Virtual environment '$VENV_DIR' already exists."
    fi

    if [ -f "$REQUIREMENTS_FILE" ]; then
        info "Installing dependencies from '$REQUIREMENTS_FILE'..."
        "$PIP_EXEC" install -r "$REQUIREMENTS_FILE"
    else
        warning "'$REQUIREMENTS_FILE' not found. Installing runtime dependencies only."
    fi
    info "Installing the smithsonian-mcp package (editable)..."
    "$PIP_EXEC" install -e .
    info "Dependencies installed successfully."
fi

# 4. Setup .env file and get API key
api_key=""
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        info "Creating .env from .env.example..."
        (umask 077 && cp .env.example .env)
    else
        warning "No .env.example found. Creating basic .env file."
        (umask 077 && echo "SMITHSONIAN_API_KEY=your_api_key_here" > .env)
    fi
fi
# .env holds the API key, so only its owner may read it
chmod 600 .env

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
    api_key=$(get_api_key) || api_key=""
    if [ -n "$api_key" ]; then
        if write_env_key "$api_key"; then
            info "API key saved to .env file."
        else
            error "Could not save the API key to .env."
        fi
    fi
fi

# 5. Check for mcpo and offer setup
if check_mcpo; then
    info "mcpo detected on your system."
    echo -n "Do you want to create an mcpo configuration file? (y/N): "
    read -r setup_mcpo
    if [[ "$setup_mcpo" =~ ^[Yy]$ ]]; then
        setup_mcpo_config "$api_key" || warning "mcpo configuration did not complete."
    fi
else
    info "mcpo not found. For multi-MCP orchestration, install with: uvx mcpo"
fi

# 6. Setup service
os=$(detect_os)
if [ "$os" != "unknown" ]; then
    info "Note: MCP clients such as Claude Desktop start their own stdio server on"
    info "demand, so most users do not need a background service. The service runs"
    info "the server in HTTP mode at $SERVICE_URL for clients that connect over HTTP."
    echo -n "Do you want to install $SERVICE_NAME as a system service? (y/N): "
    read -r install_service
    if [[ "$install_service" =~ ^[Yy]$ ]]; then
        setup_service "$os" || warning "Service setup did not complete."
    fi
fi

# 7. Setup Claude Desktop config
if [ -n "$api_key" ]; then
    echo -n "Do you want to automatically configure Claude Desktop? (y/N): "
    read -r setup_claude
    if [[ "$setup_claude" =~ ^[Yy]$ ]]; then
        setup_claude_config "$api_key" || warning "Claude Desktop configuration did not complete."
    fi
fi

# 8. Run health check
echo -n "Do you want to run a health check? (Y/n): "
read -r run_check
if [[ ! "$run_check" =~ ^[Nn]$ ]]; then
    run_health_check || warning "Health check reported problems. See the messages above."
fi

info ""
info "Setup complete."
info ""
info "Next steps:"
if [ -n "$api_key" ]; then
    info "- API key configured and validated"
else
    info "- Edit .env and add your API key from https://api.data.gov/signup/"
fi
info "- Dependencies installed in $VENV_DIR"
info ""
info "Usage:"
info "  Activate environment: source $VENV_DIR/bin/activate"
info "  Test connection: python examples/test-api-connection.py"
info "  Run server (stdio): $SERVER_EXEC"
info "  Run server (HTTP): $SERVER_EXEC --transport http"
if [ -n "$SERVICE_MANAGE" ]; then
    info "  Manage service: $SERVICE_MANAGE"
elif [ -f "$HOME/.config/systemd/user/$SERVICE_NAME.service" ]; then
    info "  Manage service: systemctl --user start/stop/status $SERVICE_NAME"
elif command_exists systemctl && [ -f "/etc/systemd/system/$SERVICE_NAME.service" ]; then
    info "  Manage service: sudo systemctl start/stop/status $SERVICE_NAME"
elif [ -f "$HOME/Library/LaunchAgents/com.smithsonian.mcp.plist" ]; then
    info "  Manage service: launchctl unload/load ~/Library/LaunchAgents/com.smithsonian.mcp.plist"
fi
info ""
info "For troubleshooting, see TROUBLESHOOTING.md or run: python scripts/verify-setup.py"
