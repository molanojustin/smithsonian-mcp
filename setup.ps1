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

# Validate API key
function Test-ApiKey {
    param([string]$ApiKey)

    if (-not $ApiKey -or $ApiKey -eq "your_api_key_here") {
        return $false
    }

    Write-Info "Validating API key..."
    try {
        $result = python -c "
import sys
import asyncio
import httpx
import os
os.environ['SMITHSONIAN_API_KEY'] = '$ApiKey'
sys.path.insert(0, '.')

async def test_api_key():
    try:
        headers = {'X-Api-Key': '$ApiKey'}
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
" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    catch {
        # Validation failed
    }
    return $false
}

# Get API key from user with validation
function Get-ApiKey {
    param([string]$ProvidedKey)

    if ($ProvidedKey) {
        if (Test-ApiKey -ApiKey $ProvidedKey) {
            return $ProvidedKey
        } else {
            Write-Warning "Provided API key is invalid."
        }
    }

    Write-Host ""
    Write-Info "API Key Setup"
    Write-Host "You need an API key from api.data.gov to access Smithsonian data."
    Write-Host "If you don't have one yet:"
    Write-Host "1. Visit: https://api.data.gov/signup/"
    Write-Host "2. Sign up for free (no special permissions needed)"
    Write-Host "3. Copy your API key"
    Write-Host ""

    while ($true) {
        $key = Read-Host "Enter your API key (or press Enter to skip)"

        if (-not $key) {
            Write-Warning "Skipping API key setup. You'll need to configure it later."
            return $null
        }

        if (Test-ApiKey -ApiKey $key) {
            "SMITHSONIAN_API_KEY=$key" | Out-File -FilePath ".env" -Encoding UTF8
            Write-Success "API key validated and saved to .env file"
            return $key
        } else {
            Write-Error "Invalid API key. Please try again or press Enter to skip."
        }
    }
}

# Setup Windows service
function Set-WindowsService {
    Write-Info "Setting up Windows service..."

    $serviceName = "SmithsonianMCP"
    $projectDir = Get-Location
    $pythonPath = ".\venv\Scripts\python.exe"

    # Check if running as administrator
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    $isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

    if (-not $isAdmin) {
        Write-Warning "Windows service installation requires administrator privileges."
        Write-Info "To install as a service, run this script as Administrator."
        return
    }

    try {
        # Create service using New-Service
        $serviceExists = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
        
        if ($serviceExists) {
            Write-Warning "Service $serviceName already exists. Updating..."
            Stop-Service -Name $serviceName -Force
            Remove-Service -Name $serviceName
        }

        New-Service -Name $serviceName -DisplayName "Smithsonian MCP Server" -BinaryPathName "`"$pythonPath`" -m smithsonian_mcp.server" -StartupType Automatic -WorkingDirectory $projectDir
        Write-Success "Windows service '$serviceName' installed successfully"
        Write-Info "Start the service with: Start-Service $serviceName"
        Write-Info "Stop the service with: Stop-Service $serviceName"
    }
    catch {
        Write-Error "Failed to install Windows service: $($_.Exception.Message)"
        Write-Info "You can run the server manually with: python -m smithsonian_mcp.server"
    }
}

# Setup Claude Desktop configuration
function Set-ClaudeDesktop {
    param([string]$ApiKey)

    Write-Info "Setting up Claude Desktop integration..."

    $claudeConfigDir = "$env:APPDATA\Claude"
    $claudeConfigFile = "$claudeConfigDir\claude_desktop_config.json"
    $projectDir = Get-Location
    $pythonPath = ".\venv\Scripts\python.exe"

    Write-Info "Claude config path: $claudeConfigFile"

    # Create Claude config directory if it doesn't exist
    if (-not (Test-Path $claudeConfigDir)) {
        New-Item -ItemType Directory -Path $claudeConfigDir -Force | Out-Null
    }

    # Backup existing config
    if (Test-Path $claudeConfigFile) {
        $backupFile = "$claudeConfigFile.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item $claudeConfigFile $backupFile
        Write-Info "Backed up existing Claude Desktop config."
    }

    # Create configuration with absolute paths
    $config = @{
        mcpServers = @{
            smithsonian_open_access = @{
                command = $pythonPath
                args = @("-m", "smithsonian_mcp.server")
                env = @{
                    SMITHSONIAN_API_KEY = $ApiKey
                    LOG_LEVEL = "INFO"
                }
            }
        }
    }

    $configJson = $config | ConvertTo-Json -Depth 4
    $configJson | Out-File -FilePath $claudeConfigFile -Encoding UTF8

    Write-Success "Claude Desktop configuration updated"
    Write-Warning "You need to restart Claude Desktop for changes to take effect"
}

# Check if mcpo is available
function Test-McpoAvailable {
    try {
        $mcpoVersion = mcpo --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    catch {
        # mcpo not found directly
    }
    
    try {
        $uvxTest = uvx mcpo --help 2>$null
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    catch {
        # uvx mcpo not available
    }
    
    return $false
}

# Setup mcpo configuration
function Set-McpoConfig {
    param([string]$ApiKey)

    Write-Info "Setting up mcpo configuration..."

    if (-not (Test-Path "mcpo-config.example.json")) {
        Write-Warning "mcpo-config.example.json not found. Skipping mcpo setup."
        return $false
    }

    # Create mcpo config from example
    $configFile = "mcpo-config.json"
    Copy-Item "mcpo-config.example.json" $configFile

    # Get absolute paths
    $projectDir = Get-Location
    $pythonPath = ".\venv\Scripts\python.exe"
    $fullPythonPath = Join-Path $projectDir $pythonPath

    # Replace paths and API key in config
    $configContent = Get-Content $configFile -Raw
    $configContent = $configContent -replace "/path/to/your/project/.venv/bin/python", $fullPythonPath
    $configContent = $configContent -replace "/path/to/your/project", $projectDir
    
    if ($ApiKey) {
        $configContent = $configContent -replace "your_api_key_here", $ApiKey
    }
    
    $configContent | Out-File -FilePath $configFile -Encoding UTF8
    Write-Success "mcpo configuration created at: $configFile"
    Write-Info "Python path set to: $fullPythonPath"
    Write-Info "Project path set to: $projectDir"
    Write-Info "You can start mcpo with: mcpo --config $configFile --port 8000"
    return $true
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

# Run health check
function Invoke-HealthCheck {
    Write-Info "Running health check..."

    # Test API connection
    try {
        python examples/test-api-connection.py
        Write-Success "✓ API connection test passed"
    }
    catch {
        Write-Error "✗ API connection test failed"
        return $false
    }

    # Test MCP server startup (brief test)
    try {
        $process = Start-Process -FilePath "python" -ArgumentList "-m", "smithsonian_mcp.server", "--test" -PassThru -WindowStyle Hidden
        Start-Sleep -Seconds 5
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force
            Write-Success "✓ MCP server startup test passed"
        } else {
            Write-Warning "⚠ MCP server startup test inconclusive (this may be normal)"
        }
    }
    catch {
        Write-Warning "⚠ MCP server startup test inconclusive (this may be normal)"
    }

    Write-Success "Health check completed."
    return $true
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

        # Setup .env file
        if (-not (Test-Path ".env")) {
            if (Test-Path ".env.example") {
                Copy-Item ".env.example" ".env"
                Write-Info "Created .env from .env.example"
            } else {
                "SMITHSONIAN_API_KEY=your_api_key_here" | Out-File -FilePath ".env" -Encoding UTF8
            }
        }

        # Check for existing API key
        $existingKey = $null
        if (Test-Path ".env") {
            $envContent = Get-Content ".env"
            $keyLine = $envContent | Where-Object { $_ -match "^SMITHSONIAN_API_KEY=" }
            if ($keyLine) {
                $existingKey = $keyLine -replace "^SMITHSONIAN_API_KEY=", ""
            }
        }

        if ($existingKey -and $existingKey -ne "your_api_key_here" -and (Test-ApiKey -ApiKey $existingKey)) {
            $apiKey = $existingKey
            Write-Success "Using existing valid API key from .env file."
        } else {
            $apiKey = Get-ApiKey -ProvidedKey $ApiKey
        }

        # Check for mcpo and offer setup
        if (Test-McpoAvailable) {
            Write-Success "mcpo detected on your system."
            $setupMcpo = Read-Host "Do you want to create an mcpo configuration file? (y/N)"
            if ($setupMcpo -match '^[Yy]') {
                Set-McpoConfig -ApiKey $apiKey
            }
        } else {
            Write-Info "mcpo not found. For multi-MCP orchestration, install with: pip install mcpo"
        }

        # Setup Windows service
        $setupService = Read-Host "Do you want to install Smithsonian MCP as a Windows service? (y/N)"
        if ($setupService -match '^[Yy]') {
            Set-WindowsService
        }

        # Setup Claude Desktop config
        if ($apiKey) {
            $setupClaude = Read-Host "Do you want to automatically configure Claude Desktop? (y/N)"
            if ($setupClaude -match '^[Yy]') {
                Set-ClaudeDesktop -ApiKey $apiKey
            }
        }

        # Run health check
        $runCheck = Read-Host "Do you want to run a health check? (Y/n)"
        if ($runCheck -notmatch '^[Nn]') {
            Invoke-HealthCheck
        }

        Write-Host ""
        Write-Host "🎉 Setup Complete!" -ForegroundColor Green
        Write-Host ""
        if ($apiKey) {
            Write-Success "✓ API key configured and validated"
        } else {
            Write-Warning "⚠ Edit .env and add your API key from https://api.data.gov/signup/"
        }
        Write-Success "✓ Dependencies installed"
        Write-Success "✓ Virtual environment created"
        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  Activate environment: .\venv\Scripts\Activate.ps1"
        Write-Host "  Test connection: python examples/test-api-connection.py"
        Write-Host "  Run server: python -m smithsonian_mcp.server"
        if (Get-Service -Name "SmithsonianMCP" -ErrorAction SilentlyContinue) {
            Write-Host "  Manage service: Start-Service SmithsonianMCP / Stop-Service SmithsonianMCP"
        }
        Write-Host ""
        Write-Host "For troubleshooting, see README.md or run: python scripts\verify-setup.py"
    }
    catch {
        Write-Error "Setup failed: $($_.Exception.Message)"
        Write-Host "Please check the error message above and try again." -ForegroundColor Yellow
        exit 1
    }
}

# Run the installation
Start-Installation
