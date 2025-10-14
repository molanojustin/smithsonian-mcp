#!/usr/bin/env node

/**
 * Smithsonian Open Access MCP Server - Node.js Wrapper
 * 
 * This script provides a Node.js entry point for the Python-based MCP server,
 * enabling npm/npx installation and execution with uv for dependency management.
 */

const { spawn } = require('cross-spawn');
const path = require('path');
const fs = require('fs');

// Load environment variables from .env file if it exists
require('dotenv').config();

class SmithonianMCPServer {
  constructor() {
    this.packagePath = path.resolve(__dirname, '..');
    this.pythonModule = 'smithsonian_mcp.server';
    this.process = null;
  }

  /**
   * Check if uv is installed
   */
  async checkUv() {
    try {
      const result = spawn.sync('uv', ['--version'], { 
        stdio: 'pipe',
        shell: true 
      });
      
      if (result.status === 0) {
        const version = result.stdout.toString().trim();
        console.log(`Found uv: ${version}`);
        return true;
      }
    } catch (error) {
      // uv not found
    }

    throw new Error(
      'uv not found. Please install uv first:\n' +
      '  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n' +
      '  Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"\n' +
      '  Or visit: https://docs.astral.sh/uv/getting-started/installation/'
    );
  }

  /**
   * Ensure dependencies are synced
   */
  async syncDependencies() {
    return new Promise((resolve, reject) => {
      console.log('Syncing dependencies with uv...');
      
      const sync = spawn('uv', ['sync'], {
        stdio: 'inherit',
        cwd: this.packagePath
      });

      sync.on('close', (code) => {
        if (code === 0) {
          console.log('Dependencies synced successfully');
          resolve();
        } else {
          reject(new Error(`Failed to sync dependencies (exit code: ${code})`));
        }
      });

      sync.on('error', (error) => {
        reject(new Error(`Failed to sync dependencies: ${error.message}`));
      });
    });
  }

  /**
   * Validate API key
   */
  validateApiKey() {
    const apiKey = process.env.SMITHSONIAN_API_KEY;
    
    if (!apiKey) {
      console.log('\nWarning: Smithsonian API Key not found');
      console.log('Get your free API key from: https://api.data.gov/signup/');
      console.log('Set it as environment variable: SMITHSONIAN_API_KEY=your_key_here');
      console.log('Or create a .env file with: SMITHSONIAN_API_KEY=your_key_here\n');
      return false;
    }

    if (apiKey.length < 20) {
      console.log('\nWarning: Invalid API key format');
      console.log('API keys should be at least 20 characters long\n');
      return false;
    }

    return true;
  }

  /**
   * Start the MCP server
   */
  async start(args = []) {
    try {
      console.log('Smithsonian Open Access MCP Server');
      console.log('=====================================\n');

      // Check if uv is installed
      await this.checkUv();

      // Sync dependencies (uv will handle Python version and virtual environment)
      await this.syncDependencies();

      // Validate API key
      if (!this.validateApiKey()) {
        process.exit(1);
      }

      console.log('Starting MCP server...\n');

      // Start the Python MCP server using uv run
      // uv run will automatically use the project's Python version and virtual environment
      this.process = spawn('uv', ['run', 'python', '-m', this.pythonModule, ...args], {
        stdio: 'inherit',
        cwd: this.packagePath,
        env: process.env
      });

      this.process.on('close', (code) => {
        console.log(`\nMCP server exited with code ${code}`);
        process.exit(code);
      });

      this.process.on('error', (error) => {
        console.error('Failed to start MCP server:', error.message);
        process.exit(1);
      });

      // Handle graceful shutdown
      process.on('SIGINT', () => {
        console.log('\nShutting down MCP server...');
        if (this.process) {
          this.process.kill('SIGINT');
        }
      });

      process.on('SIGTERM', () => {
        console.log('\nShutting down MCP server...');
        if (this.process) {
          this.process.kill('SIGTERM');
        }
      });

    } catch (error) {
      console.error('Error starting MCP server:', error.message);
      process.exit(1);
    }
  }

  /**
   * Show help information
   */
  showHelp() {
    console.log(`
Smithsonian Open Access MCP Server

Usage:
  smithsonian-mcp [options]

Options:
  --help, -h     Show this help message
  --version, -v  Show version information
  --test         Run API connection test

Requirements:
  uv             Fast Python package manager (https://docs.astral.sh/uv/)
                 Install with: curl -LsSf https://astral.sh/uv/install.sh | sh

Environment Variables:
  SMITHSONIAN_API_KEY    Your Smithsonian API key (required)
                         Get it from: https://api.data.gov/signup/

Examples:
  # Start the MCP server
  smithsonian-mcp

  # Test API connection
  smithsonian-mcp --test

  # Start with custom API key
  SMITHSONIAN_API_KEY=your_key smithsonian-mcp

Configuration for Claude Desktop:
  Add this to your claude_desktop_config.json:

  {
    "mcpServers": {
      "smithsonian_open_access": {
        "command": "npx",
        "args": ["-y", "@molanojustin/smithsonian-mcp"],
        "env": {
          "SMITHSONIAN_API_KEY": "your_api_key_here"
        }
      }
    }
  }

For more information, visit: https://github.com/molanojustin/smithsonian-mcp
`);
  }

  /**
   * Show version information
   */
  showVersion() {
    const packageJson = require(path.join(this.packagePath, 'package.json'));
    console.log(`@molanojustin/smithsonian-mcp v${packageJson.version}`);
  }

  /**
   * Run API connection test
   */
  async runTest() {
    try {
      console.log('Testing Smithsonian API connection...\n');

      await this.checkUv();
      await this.syncDependencies();

      if (!this.validateApiKey()) {
        process.exit(1);
      }

      const testScript = path.join(this.packagePath, 'examples', 'test-api-connection.py');
      
      if (fs.existsSync(testScript)) {
        // Use uv run to execute the test script
        const testProcess = spawn('uv', ['run', 'python', testScript], {
          stdio: 'inherit',
          cwd: this.packagePath,
          env: process.env
        });

        testProcess.on('close', (code) => {
          process.exit(code);
        });

        testProcess.on('error', (error) => {
          console.error('Failed to run test:', error.message);
          process.exit(1);
        });
      } else {
        console.log('Test script not found');
        process.exit(1);
      }

    } catch (error) {
      console.error('Error running test:', error.message);
      process.exit(1);
    }
  }
}

// Main execution
async function main() {
  const args = process.argv.slice(2);
  const server = new SmithonianMCPServer();

  // Handle command line arguments
  if (args.includes('--help') || args.includes('-h')) {
    server.showHelp();
    return;
  }

  if (args.includes('--version') || args.includes('-v')) {
    server.showVersion();
    return;
  }

  if (args.includes('--test')) {
    await server.runTest();
    return;
  }

  // Start the server
  await server.start(args);
}

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error.message);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
  process.exit(1);
});

// Run main function
main().catch((error) => {
  console.error('Fatal error:', error.message);
  process.exit(1);
});
