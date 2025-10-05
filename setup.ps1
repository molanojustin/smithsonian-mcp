# Smithsonian MCP Server Setup Script (PowerShell)
# This script automates the setup process for Claude Desktop and VS Code integration on Windows

param(
    [string]$ApiKey = "",
    [switch]$SkipTests = $false,
    [switch]$Verbose = $false
)

# Error handling
$ErrorActionPreference = "Stop"

# Colors for output
function Write-Success { param([string]$Message) Write-Host "✓ $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message) Write-Host "⚠ $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message) Write-Host "✗ $Message" -ForegroundColor Red }
function Write-Info { param([string]$Message) Write-Host "ℹ $Message" -ForegroundColor Blue }

Write-Host "Smithsonian MCP Server Setup" -ForegroundColor Blue
Write-Host "==================================" -ForegroundColor Blue
Write-Host ""

# Check if Python is installed
function Test-Python {
    Write-Info "Checking Python installation..."

    $pythonCommands = @("python", "python3", "py")
    $pythonCmd = $null

    foreach ($cmd in $pythonCommands) {
        try {
            $version = & $cmd --version 2>$null
            if ($version -match "Python (\d+\.\d+\.\d+)") {
                $pythonCmd = $cmd
                Write-Success "Found Python $($matches[1]) using command '$cmd'"
                break
            }
        }
        catch {
            # Command not found, try next
        }
    }

    if (-not $pythonCmd) {
        Write-Error "Python not found. Please install Python 3.10 or later from python.org"
        exit 1
    }

    return $pythonCmd
}

# Create virtual environment
function New-VirtualEnvironment {
    param([string]$PythonCmd)

    Write-Info "Creating virtual environment..."

    if (-not (Test-Path "venv")) {
        & $PythonCmd -m venv venv
        Write-Success "Virtual environment created"
    }
    else {
        Write-Warning "Virtual environment already exists"
    }

    # Activate virtual environment
    $activateScript = ".\venv\Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        & $activateScript
        Write-Success "Virtual environment activated"
    }
    else {
        Write-Error "Failed to find virtual environment activation script"
        exit 1
    }
}

# Install dependencies
function Install-Dependencies {
    Write-Info "Installing Python dependencies..."

    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt

    Write-Success "Dependencies installed"
}

# Get API key from user
function Get-ApiKey {
    param([string]$ProvidedKey)

    if ($ProvidedKey) {
        return $ProvidedKey
    }

    Write-Host ""
    Write-Info "API Key Setup"
    Write-Host "You need an API key from api.data.gov to access Smithsonian data."
    Write-Host "If you don't have one yet:"
    Write-Host "1. Visit: https://api.data.gov/signup/"
    Write-Host "2. Sign up for free (no special permissions needed)"
    Write-Host "3. Copy your API key"
    Write-Host ""

    $key = Read-Host "Enter your API key (or press Enter to set it later)"

    if ($key) {
        "SMITHSONIAN_API_KEY=$key" | Out-File -FilePath ".env" -Encoding UTF8
        Write-Success "API key saved to .env file"
        return $key
    }
    else {
        Write-Warning "API key not set. You'll need to configure it manually later."
        return $null
    }
}

# Setup Claude Desktop configuration
function Set-ClaudeDesktop {
    param([string]$ApiKey)

    Write-Info "Setting up Claude Desktop integration..."

    $claudeConfigDir = "$env:APPDATA\Claude"
    $claudeConfigFile = "$claudeConfigDir\claude_desktop_config.json"

    Write-Info "Claude config path: $claudeConfigFile"

    # Create Claude config directory if it doesn't exist
    if (-not (Test-Path $claudeConfigDir)) {
        New-Item -ItemType Directory -Path $claudeConfigDir -Force | Out-Null
    }

    # Copy configuration file
    Copy-Item "claude-desktop-config.json" $claudeConfigFile

    Write-Success "Claude Desktop configuration created"
    Write-Warning "You need to restart Claude Desktop for changes to take effect"
}

# Test the installation
function Test-Installation {
    param([string]$ApiKey, [bool]$SkipTests)

    if ($SkipTests) {
        Write-Warning "Skipping installation tests"
        return
    }

    Write-Info "Testing installation..."

    try {
        python examples/test-api-connection.py 2>$null
        Write-Success "API connectivity test passed"
    }
    catch {
        Write-Warning "API connectivity test failed - check your API key"
    }

    Write-Success "Installation test complete"
}

# Main installation function
function Start-Installation {
    try {
        Write-Host "Starting automated setup..." -ForegroundColor Blue
        Write-Host ""

        # Check if we're in the right directory
        if (-not (Test-Path "requirements.txt")) {
            Write-Error "requirements.txt not found. Please run this script from the project root directory."
            exit 1
        }

        $pythonCmd = Test-Python
        New-VirtualEnvironment -PythonCmd $pythonCmd
        Install-Dependencies
        $apiKey = Get-ApiKey -ProvidedKey $ApiKey
        Set-ClaudeDesktop -ApiKey $apiKey
        Test-Installation -ApiKey $apiKey -SkipTests $SkipTests

        Write-Host ""
        Write-Host "Setup Complete!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Next steps:"
        Write-Host "1. If you didn't set an API key, edit .env and add: SMITHSONIAN_API_KEY=your_key"
        Write-Host "2. Restart Claude Desktop to load the MCP server"
        Write-Host "3. Open VS Code with: code smithsonian-mcp-workspace.code-workspace"
        Write-Host "4. Test the integration by asking Claude about Smithsonian collections"
        Write-Host ""
        Write-Host "Quick test commands:"
        Write-Host "• python examples/test-api-connection.py"
        Write-Host "• python -m smithsonian_mcp.server"
    }
    catch {
        Write-Error "Setup failed: $($_.Exception.Message)"
        Write-Host "Please check the error message above and try again." -ForegroundColor Yellow
        exit 1
    }
}

# Run the installation
Start-Installation
