#!/bin/bash
# This script sets up the development environment for the Smithsonian MCP server.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Constants ---
VENV_DIR=".venv"
PYTHON_EXEC="$VENV_DIR/bin/python"
PIP_EXEC="$VENV_DIR/bin/pip"
REQUIREMENTS_FILE="requirements.txt"

# --- Functions ---

# Function to print messages
info() {
    echo "INFO: $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Main Script ---

# 1. Check for Python 3
if ! command_exists python3; then
    info "Python 3 is not installed. Please install it to continue."
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
    info "Warning: '$REQUIREMENTS_FILE' not found. Skipping dependency installation."
fi

# 4. Setup .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        info "Creating .env from .env.example..."
        cp .env.example .env
        info ".env created from .env.example. Please update it with your actual API key from https://api.data.gov/signup/"
    else
        info "Warning: No .env.example found. Please create .env with your API key."
    fi
else
    info ".env file already exists."
fi

info "Setup complete!"
info ""
info "Next steps:"
info "1. Edit .env and add your API key from https://api.data.gov/signup/"
info "2. Test the connection: python examples/test-api-connection.py"
info "3. To activate the virtual environment, run: source $VENV_DIR/bin/activate"
