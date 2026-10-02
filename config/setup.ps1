# Smithsonian MCP Server Setup Script (PowerShell)
# This script automates the setup process for Claude Desktop and VS Code integration on Windows

param(
    [string]$ApiKey = "",
    [switch]$SkipTests = $false,
    [switch]$Verbose = $false
)

# Error handling
$ErrorActionPreference = "Stop"

# Change to project root directory (parent of this script's directory)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Join-Path $scriptDir "..")
$projectDir = (Get-Location).Path

# Virtual environment and the console script installed into it
$venvDir = ".venv"
$venvPython = Join-Path $projectDir "$venvDir\Scripts\python.exe"
$serverExe = Join-Path $projectDir "$venvDir\Scripts\smithsonian-mcp.exe"

# The service serves streamable HTTP; a stdio server with no client attached
# would exit at once.
$servicePort = 8000
$serviceArgs = "--transport http --host 127.0.0.1 --port $servicePort"
$serviceUrl = "http://127.0.0.1:$servicePort/mcp"

# Output helpers
function Write-Success { param([string]$Message) Write-Host "[OK] $Message" -ForegroundColor Green }
function Write-Warning { param([string]$Message) Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Write-Error { param([string]$Message) Write-Host "[ERROR] $Message" -ForegroundColor Red }
function Write-Info { param([string]$Message) Write-Host "[INFO] $Message" -ForegroundColor Blue }

# Write text as UTF-8 without a byte order mark. Out-File -Encoding UTF8 adds a
# BOM in Windows PowerShell 5.1, which breaks JSON and .env parsers.
function Write-Utf8File {
    param([string]$Path, [string]$Content)
    $fullPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    [System.IO.File]::WriteAllText($fullPath, $Content, (New-Object System.Text.UTF8Encoding($false)))
}

# Read a file as UTF-8. Get-Content in Windows PowerShell 5.1 reads files
# without a BOM using the ANSI code page, which corrupts non-ASCII text on a
# round trip. A leading BOM, if present, is detected and removed.
function Read-Utf8File {
    param([string]$Path)
    $fullPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    return [System.IO.File]::ReadAllText($fullPath, (New-Object System.Text.UTF8Encoding($false)))
}

# Read a file as UTF-8 and return its lines, without a trailing empty line.
function Read-Utf8Lines {
    param([string]$Path)
    $text = (Read-Utf8File -Path $Path) -replace "[\r\n]+\z", ""
    if (-not $text) {
        return @()
    }
    return @($text -split "\r?\n")
}

Write-Host "Smithsonian MCP Server Setup" -ForegroundColor Blue
Write-Host "==================================" -ForegroundColor Blue
Write-Host ""

# Find a Python 3.10+ interpreter (only needed when uv is not installed)
function Test-Python {
    Write-Info "Checking Python installation..."

    $pythonCommands = @("python", "python3", "py")

    foreach ($cmd in $pythonCommands) {
        try {
            $version = & $cmd --version 2>$null
            if ($version -match "Python (\d+)\.(\d+)\.(\d+)") {
                if ([int]$matches[1] -eq 3 -and [int]$matches[2] -ge 10) {
                    Write-Success "Found Python $($matches[1]).$($matches[2]).$($matches[3]) using command '$cmd'"
                    return $cmd
                }
                Write-Warning "Python $($matches[1]).$($matches[2]) from '$cmd' is too old"
            }
        }
        catch {
            # Command not found, try next
        }
    }

    Write-Error "Python 3.10 or later not found. Install it from python.org, or install uv."
    exit 1
}

# Create the virtual environment and install dependencies plus the package
function Install-Dependencies {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Write-Info "uv found. Installing locked dependencies into $venvDir with uv sync..."
        & uv sync --group dev
        if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
    }
    else {
        Write-Info "uv not found. Falling back to python -m venv and pip."
        $pythonCmd = Test-Python

        if (-not (Test-Path $venvDir)) {
            Write-Info "Creating virtual environment..."
            & $pythonCmd -m venv $venvDir
            if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment" }
            Write-Success "Virtual environment created"
        }
        else {
            Write-Warning "Virtual environment already exists"
        }

        Write-Info "Installing Python dependencies..."
        & $venvPython -m pip install --upgrade pip
        & $venvPython -m pip install -r config/requirements.txt
        if ($LASTEXITCODE -ne 0) { throw "Failed to install config/requirements.txt" }
        & $venvPython -m pip install -e .
        if ($LASTEXITCODE -ne 0) { throw "Failed to install the smithsonian-mcp package" }
    }

    Write-Success "Dependencies installed"
}

# Validate API key against the live API.
# The key is passed through an environment variable and an HTTP header, never
# on a command line or in a URL.
function Test-ApiKey {
    param([string]$Key)

    if (-not $Key -or $Key -eq "your_api_key_here") {
        return $false
    }

    Write-Info "Validating API key..."
    $validator = @'
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
    print(f"API key validation failed: {exc}")
    sys.exit(1)

if response.status_code == 200:
    print("API key is valid")
    sys.exit(0)

print(f"API returned status {response.status_code}")
sys.exit(1)
'@

    $previousKey = $env:SMITHSONIAN_API_KEY
    try {
        $env:SMITHSONIAN_API_KEY = $Key
        $validator | & $venvPython - | Out-Host
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
    finally {
        $env:SMITHSONIAN_API_KEY = $previousKey
    }
}

# Store the API key in .env, keeping any other settings already in the file
function Set-EnvApiKey {
    param([string]$Key)

    $lines = @()
    if (Test-Path ".env") {
        $lines = @(Read-Utf8Lines -Path ".env")
    }

    $found = $false
    $updated = @()
    foreach ($line in $lines) {
        if ($line -match "^SMITHSONIAN_API_KEY=") {
            $updated += "SMITHSONIAN_API_KEY=$Key"
            $found = $true
        }
        else {
            $updated += $line
        }
    }
    if (-not $found) {
        $updated += "SMITHSONIAN_API_KEY=$Key"
    }

    Write-Utf8File -Path ".env" -Content (($updated -join "`n") + "`n")
}

# Get API key from the parameter or the user, with validation
function Get-ApiKey {
    param([string]$ProvidedKey)

    if ($ProvidedKey) {
        if (Test-ApiKey -Key $ProvidedKey) {
            Set-EnvApiKey -Key $ProvidedKey
            Write-Success "API key validated and saved to .env file"
            return $ProvidedKey
        }
        Write-Warning "Provided API key is invalid."
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

        if (Test-ApiKey -Key $key) {
            Set-EnvApiKey -Key $key
            Write-Success "API key validated and saved to .env file"
            return $key
        }
        Write-Error "Invalid API key. Please try again or press Enter to skip."
    }
}

# Setup Windows service
function Set-WindowsService {
    Write-Info "Setting up Windows service..."
    Write-Warning "smithsonian-mcp is a console program, not a native Windows service."
    Write-Warning "Start-Service fails unless it is wrapped by a service host such as NSSM."

    $serviceName = "SmithsonianMCP"

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
        $serviceExists = Get-Service -Name $serviceName -ErrorAction SilentlyContinue

        if ($serviceExists) {
            Write-Warning "Service $serviceName already exists. Updating..."
            Stop-Service -Name $serviceName -Force
            & sc.exe delete $serviceName | Out-Null
        }

        New-Service -Name $serviceName -DisplayName "Smithsonian MCP Server" -BinaryPathName "`"$serverExe`" $serviceArgs" -StartupType Manual | Out-Null
        Write-Success "Windows service '$serviceName' registered"
        Write-Info "It serves MCP over streamable HTTP at $serviceUrl"
        Write-Info "Start the service with: Start-Service $serviceName"
        Write-Info "Stop the service with: Stop-Service $serviceName"
    }
    catch {
        Write-Error "Failed to install Windows service: $($_.Exception.Message)"
        Write-Info "You can run the server manually with: $serverExe $serviceArgs"
    }
}

# Add this server to the Claude Desktop config, preserving existing entries
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

    # Load and back up any existing config
    $config = $null
    if (Test-Path $claudeConfigFile) {
        $backupFile = "$claudeConfigFile.backup.$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item $claudeConfigFile $backupFile
        Write-Info "Backed up existing Claude Desktop config."

        $raw = Read-Utf8File -Path $claudeConfigFile
        if ($raw -and $raw.Trim()) {
            try {
                $config = $raw | ConvertFrom-Json
            }
            catch {
                Write-Error "$claudeConfigFile is not valid JSON: $($_.Exception.Message)"
                Write-Error "Fix the file or add the server entry by hand. The file was not changed."
                return
            }
        }
    }
    if (-not $config) {
        $config = New-Object PSObject
    }
    if (-not ($config.PSObject.Properties.Name -contains "mcpServers")) {
        $config | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value (New-Object PSObject)
    }

    # Use the absolute path to the console script installed in the virtual environment
    $entry = [PSCustomObject]@{
        command = $serverExe
        args    = @()
        env     = [PSCustomObject]@{
            SMITHSONIAN_API_KEY = $ApiKey
            LOG_LEVEL           = "INFO"
        }
    }
    $config.mcpServers | Add-Member -MemberType NoteProperty -Name "smithsonian_open_access" -Value $entry -Force

    Write-Utf8File -Path $claudeConfigFile -Content ($config | ConvertTo-Json -Depth 10)

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

# Write mcpo-config.json from the example with local paths and the API key.
# The example under examples\ is left untouched.
function Set-McpoConfig {
    param([string]$ApiKey)

    Write-Info "Setting up mcpo configuration..."

    $exampleFile = "examples/mcpo-config.json"
    $configFile = "mcpo-config.json"

    if (-not (Test-Path $exampleFile)) {
        Write-Warning "$exampleFile not found. Skipping mcpo setup."
        return $false
    }

    if (-not $ApiKey) {
        Write-Warning "No API key available. Skipping mcpo setup."
        return $false
    }

    # Paths are inserted into JSON strings, so backslashes must be escaped
    $jsonPython = $venvPython.Replace('\', '\\')
    $jsonProject = $projectDir.Replace('\', '\\')

    $configContent = Read-Utf8File -Path $exampleFile
    $configContent = $configContent.Replace("/path/to/your/project/.venv/bin/python", $jsonPython)
    $configContent = $configContent.Replace("/path/to/your/project", $jsonProject)
    $configContent = $configContent.Replace("your_api_key_here", $ApiKey)

    Write-Utf8File -Path $configFile -Content $configContent
    Write-Success "mcpo configuration written to: $projectDir\$configFile"
    Write-Warning "It contains your API key. Do not commit it."
    Write-Info "Python path set to: $venvPython"
    Write-Info "You can start mcpo with: mcpo --config $configFile --port 8000"
    return $true
}

# Run health check
function Invoke-HealthCheck {
    Write-Info "Running health check..."

    # Test API connection
    & $venvPython examples/test-api-connection.py | Out-Host
    if ($LASTEXITCODE -eq 0) {
        Write-Success "API connection test passed"
    }
    else {
        Write-Error "API connection test failed"
        return $false
    }

    # Start the server with an empty stdin: it should start, read end of input,
    # and exit cleanly. A missing API key or import error exits non-zero.
    $emptyInput = New-TemporaryFile
    $stdoutFile = New-TemporaryFile
    $stderrFile = New-TemporaryFile
    try {
        $process = Start-Process -FilePath $serverExe -NoNewWindow -PassThru `
            -RedirectStandardInput $emptyInput.FullName `
            -RedirectStandardOutput $stdoutFile.FullName `
            -RedirectStandardError $stderrFile.FullName
        $null = $process.Handle  # keeps ExitCode available after the process exits
        if ($process.WaitForExit(60000) -and $process.ExitCode -eq 0) {
            Write-Success "MCP server startup test passed"
        }
        else {
            if (-not $process.HasExited) {
                Stop-Process -Id $process.Id -Force
            }
            Write-Warning "MCP server startup test failed. Run $serverExe to see the error."
        }
    }
    catch {
        Write-Warning "MCP server startup test failed: $($_.Exception.Message)"
    }
    finally {
        Remove-Item $emptyInput.FullName, $stdoutFile.FullName, $stderrFile.FullName -ErrorAction SilentlyContinue
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
        if (-not (Test-Path "pyproject.toml")) {
            Write-Error "pyproject.toml not found. Please run this script from the project checkout."
            exit 1
        }

        Install-Dependencies

        # Setup .env file
        if (-not (Test-Path ".env")) {
            if (Test-Path ".env.example") {
                Copy-Item ".env.example" ".env"
                Write-Info "Created .env from .env.example"
            }
            else {
                Write-Utf8File -Path ".env" -Content "SMITHSONIAN_API_KEY=your_api_key_here`n"
            }
        }

        # Check for existing API key
        $existingKey = $null
        if (Test-Path ".env") {
            $keyLine = Read-Utf8Lines -Path ".env" | Where-Object { $_ -match "^SMITHSONIAN_API_KEY=" } | Select-Object -First 1
            if ($keyLine) {
                $existingKey = $keyLine -replace "^SMITHSONIAN_API_KEY=", ""
            }
        }

        if ($existingKey -and $existingKey -ne "your_api_key_here" -and (Test-ApiKey -Key $existingKey)) {
            $apiKey = $existingKey
            Write-Success "Using existing valid API key from .env file."
        }
        else {
            $apiKey = Get-ApiKey -ProvidedKey $ApiKey
        }

        # Check for mcpo and offer setup
        if (Test-McpoAvailable) {
            Write-Success "mcpo detected on your system."
            $setupMcpo = Read-Host "Do you want to create an mcpo configuration file? (y/N)"
            if ($setupMcpo -match '^[Yy]') {
                $null = Set-McpoConfig -ApiKey $apiKey
            }
        }
        else {
            Write-Info "mcpo not found. For multi-MCP orchestration, install with: uvx mcpo"
        }

        # Setup Windows service
        Write-Info "Note: MCP clients such as Claude Desktop start their own stdio server on"
        Write-Info "demand, so most users do not need a background service. The service runs"
        Write-Info "the server in HTTP mode at $serviceUrl for clients that connect over HTTP."
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
        if ($SkipTests) {
            Write-Warning "Skipping health check (-SkipTests)"
        }
        else {
            $runCheck = Read-Host "Do you want to run a health check? (Y/n)"
            if ($runCheck -notmatch '^[Nn]') {
                $null = Invoke-HealthCheck
            }
        }

        Write-Host ""
        Write-Host "Setup Complete!" -ForegroundColor Green
        Write-Host ""
        if ($apiKey) {
            Write-Success "API key configured and validated"
        }
        else {
            Write-Warning "Edit .env and add your API key from https://api.data.gov/signup/"
        }
        Write-Success "Dependencies installed in $venvDir"
        Write-Host ""
        Write-Host "Usage:"
        Write-Host "  Activate environment: .\$venvDir\Scripts\Activate.ps1"
        Write-Host "  Test connection: python examples/test-api-connection.py"
        Write-Host "  Run server (stdio): $serverExe"
        Write-Host "  Run server (HTTP): $serverExe --transport http"
        if (Get-Service -Name "SmithsonianMCP" -ErrorAction SilentlyContinue) {
            Write-Host "  Manage service: Start-Service SmithsonianMCP / Stop-Service SmithsonianMCP"
        }
        Write-Host ""
        Write-Host "For troubleshooting, see TROUBLESHOOTING.md or run: python scripts\verify-setup.py"
    }
    catch {
        Write-Error "Setup failed: $($_.Exception.Message)"
        Write-Host "Please check the error message above and try again." -ForegroundColor Yellow
        exit 1
    }
}

# Run the installation
Start-Installation
