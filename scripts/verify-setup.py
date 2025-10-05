#!/usr/bin/env python3
"""
Smithsonian MCP Setup Verification Script

This script verifies that the Smithsonian MCP server is properly configured
and can connect to the API. It provides detailed diagnostics for troubleshooting.
"""

import sys
import os
import json
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from smithsonian_mcp.config import Config
    from smithsonian_mcp.api_client import create_client
except ImportError as e:
    print(f"❌ Failed to import Smithsonian MCP modules: {e}")
    print("   Make sure you're running this script from the project root directory")
    print("   and that dependencies are installed: pip install -r requirements.txt")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def success(message: str) -> None:
    print(f"{Colors.GREEN}✓{Colors.END} {message}")


def warning(message: str) -> None:
    print(f"{Colors.YELLOW}⚠{Colors.END} {message}")


def error(message: str) -> None:
    print(f"{Colors.RED}❌{Colors.END} {message}")


def info(message: str) -> None:
    print(f"{Colors.BLUE}ℹ{Colors.END} {message}")


def header(message: str) -> None:
    print(f"\n{Colors.BOLD}{message}{Colors.END}")
    print("=" * len(message))


def check_python_version() -> Tuple[bool, str]:
    """Check Python version compatibility"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        return False, f"Python {version.major}.{version.minor}.{version.micro} (requires 3.10+)"
    return True, f"Python {version.major}.{version.minor}.{version.micro}"


def check_virtual_environment() -> Tuple[bool, str]:
    """Check if running in a virtual environment"""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return True, f"Virtual environment: {sys.prefix}"
    return False, "Not running in a virtual environment"


def check_dependencies() -> Tuple[bool, List[str]]:
    """Check if required dependencies are installed"""
    requirements_file = project_root / "requirements.txt"
    if not requirements_file.exists():
        return False, ["requirements.txt not found"]

    missing = []
    try:
        with open(requirements_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    package = line.split('>=')[0].split('==')[0].split('<=')[0]
                    try:
                        # Handle special cases for package names
                        import_name = package.replace('-', '_')
                        if package == 'python-decouple':
                            import_name = 'decouple'
                        __import__(import_name)
                    except ImportError:
                        missing.append(package)
    except Exception as e:
        return False, [f"Failed to read requirements.txt: {e}"]

    return len(missing) == 0, missing


def check_api_key() -> Tuple[bool, str]:
    """Check API key configuration"""
    try:
        api_key = Config.API_KEY
        if not api_key or api_key == "your_api_key_here":
            return False, "No API key configured"
        return True, "API key found"
    except Exception as e:
        return False, f"API key check failed: {e}"


def test_api_connection() -> Tuple[bool, str]:
    """Test actual API connection"""
    try:
        import asyncio
        import httpx
        
        async def test_connection():
            # Simple test using httpx directly
            headers = {}
            if Config.API_KEY:
                headers["X-Api-Key"] = Config.API_KEY
            
            async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                # Use search endpoint with a simple query to test API connectivity
                response = await client.get("https://api.si.edu/openaccess/api/v1.0/search?q=test&rows=1")
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict) and 'response' in data and 'rows' in data['response']:
                        return True, f"Successfully connected, API is responding"
                    else:
                        return True, "Successfully connected, API is responding"
                else:
                    return False, f"API returned status {response.status_code}"
        
        result = asyncio.run(test_connection())
        return result
    except Exception as e:
        return False, f"API connection failed: {e}"


def check_mcp_server() -> Tuple[bool, str]:
    """Test MCP server startup"""
    try:
        # Try to import the server module
        from smithsonian_mcp.server import server_lifespan, ServerContext
        return True, "MCP server module imports successfully"
    except Exception as e:
        return False, f"MCP server import failed: {e}"


def check_claude_desktop_config() -> Tuple[bool, str]:
    """Check Claude Desktop configuration"""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        config_path = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    elif system == "Linux":
        config_path = Path.home() / ".config/Claude/claude_desktop_config.json"
    elif system == "Windows":
        config_path = Path(os.environ.get("APPDATA", "")) / "Claude/claude_desktop_config.json"
    else:
        return False, f"Unsupported platform: {system}"

    if not config_path.exists():
        return False, f"Claude Desktop config not found at {config_path}"

    try:
        with open(config_path) as f:
            config = json.load(f)
        
        if "mcpServers" not in config:
            return False, "No mcpServers section in Claude Desktop config"
        
        if "smithsonian_open_access" not in config["mcpServers"]:
            return False, "smithsonian_open_access not configured in Claude Desktop"
        
        server_config = config["mcpServers"]["smithsonian_open_access"]
        if "command" not in server_config:
            return False, "No command specified for smithsonian_open_access"
        
        return True, f"Claude Desktop config found at {config_path}"
    except Exception as e:
        return False, f"Failed to read Claude Desktop config: {e}"


def check_service_status() -> Tuple[bool, str]:
    """Check system service status"""
    system = platform.system()
    service_name = "smithsonian-mcp"
    
    try:
        if system == "Linux":
            # Check systemd service
            result = subprocess.run(
                ["systemctl", "--user", "is-active", service_name],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return True, f"Service {service_name} is active"
            else:
                return False, f"Service {service_name} is not active or not installed"
        
        elif system == "Darwin":
            # Check launchd service
            result = subprocess.run(
                ["launchctl", "list", "com.smithsonian.mcp"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return True, "Launchd service is loaded"
            else:
                return False, "Launchd service is not loaded"
        
        elif system == "Windows":
            # Check Windows service
            result = subprocess.run(
                ["sc", "query", "SmithsonianMCP"],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return True, "Windows service is installed"
            else:
                return False, "Windows service is not installed"
        
        else:
            return False, f"Service check not implemented for {system}"
    
    except FileNotFoundError:
        return False, f"Service management commands not available on {system}"
    except Exception as e:
        return False, f"Service check failed: {e}"


def run_diagnostics() -> Dict[str, Tuple[bool, str]]:
    """Run all diagnostic checks"""
    diagnostics = {}
    
    header("Environment Checks")
    diagnostics["python_version"] = check_python_version()
    success(diagnostics["python_version"][1])
    
    venv_ok, venv_msg = check_virtual_environment()
    diagnostics["virtual_env"] = (venv_ok, venv_msg)
    if venv_ok:
        success(venv_msg)
    else:
        warning(venv_msg)
    
    header("Dependency Checks")
    deps_ok, deps_msg = check_dependencies()
    diagnostics["dependencies"] = (deps_ok, ", ".join(deps_msg) if isinstance(deps_msg, list) else deps_msg)
    if deps_ok:
        success("All dependencies installed")
    else:
        error(f"Missing dependencies: {diagnostics['dependencies'][1]}")
    
    header("API Configuration")
    api_ok, api_msg = check_api_key()
    diagnostics["api_key"] = (api_ok, api_msg)
    if api_ok:
        success(api_msg)
    else:
        error(api_msg)
    
    if api_ok:
        conn_ok, conn_msg = test_api_connection()
        diagnostics["api_connection"] = (conn_ok, conn_msg)
        if conn_ok:
            success(conn_msg)
        else:
            error(conn_msg)
    
    header("MCP Server")
    mcp_ok, mcp_msg = check_mcp_server()
    diagnostics["mcp_server"] = (mcp_ok, mcp_msg)
    if mcp_ok:
        success(mcp_msg)
    else:
        error(mcp_msg)
    
    header("Integration Checks")
    claude_ok, claude_msg = check_claude_desktop_config()
    diagnostics["claude_config"] = (claude_ok, claude_msg)
    if claude_ok:
        success(claude_msg)
    else:
        warning(claude_msg)
    
    service_ok, service_msg = check_service_status()
    diagnostics["service_status"] = (service_ok, service_msg)
    if service_ok:
        success(service_msg)
    else:
        info(service_msg)
    
    return diagnostics


def provide_suggestions(diagnostics: Dict[str, Tuple[bool, str]]) -> None:
    """Provide troubleshooting suggestions based on diagnostics"""
    header("Troubleshooting Suggestions")
    
    if not diagnostics["python_version"][0]:
        info("• Install Python 3.10 or higher from python.org")
    
    if not diagnostics["virtual_env"][0]:
        info("• Activate virtual environment: source .venv/bin/activate (Linux/macOS) or .\\venv\\Scripts\\Activate.ps1 (Windows)")
    
    if not diagnostics["dependencies"][0]:
        info("• Install dependencies: pip install -r requirements.txt")
    
    if not diagnostics["api_key"][0]:
        info("• Get API key from https://api.data.gov/signup/")
        info("• Add it to .env file: SMITHSONIAN_API_KEY=your_key_here")
    
    if diagnostics["api_key"][0] and not diagnostics["api_connection"][0]:
        info("• Check your internet connection")
        info("• Verify your API key is valid")
        info("• Check if api.data.gov is accessible")
    
    if not diagnostics["mcp_server"][0]:
        info("• Check that all dependencies are installed")
        info("• Verify the project structure is intact")
    
    if not diagnostics["claude_config"][0]:
        info("• Run setup script to configure Claude Desktop automatically")
        info("• Or manually copy claude-desktop-config.json to Claude's config directory")
    
    if not diagnostics["service_status"][0]:
        info("• Run setup script to install as a service")
        info("• Or start manually: python -m smithsonian_mcp.server")


def main():
    """Main verification function"""
    print(f"{Colors.BOLD}Smithsonian MCP Setup Verification{Colors.END}")
    print("=" * 40)
    
    # Change to project directory
    os.chdir(project_root)
    
    # Run diagnostics
    diagnostics = run_diagnostics()
    
    # Calculate overall status
    critical_checks = ["python_version", "dependencies", "api_key", "mcp_server"]
    all_critical_ok = all(diagnostics[check][0] for check in critical_checks)
    
    # Provide suggestions
    provide_suggestions(diagnostics)
    
    # Final summary
    header("Summary")
    if all_critical_ok:
        success("🎉 All critical checks passed! Your setup should work correctly.")
        info("Next steps:")
        info("• Restart Claude Desktop if configured")
        info("• Test by asking Claude: 'What Smithsonian museums are available?'")
    else:
        error("Some critical checks failed. Please follow the suggestions above.")
    
    # Exit with appropriate code
    sys.exit(0 if all_critical_ok else 1)


if __name__ == "__main__":
    main()