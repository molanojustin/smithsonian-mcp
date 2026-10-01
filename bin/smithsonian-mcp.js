#!/usr/bin/env node

/**
 * Smithsonian Open Access MCP Server - Node.js Wrapper
 *
 * This script provides a Node.js entry point for the Python-based MCP server,
 * enabling npm/npx installation and execution with uv for dependency management.
 *
 * The server speaks MCP over stdio, so stdout is reserved for JSON-RPC messages.
 * Every diagnostic message from this wrapper, and all output from `uv sync`, is
 * written to stderr.
 */

const { spawn } = require('cross-spawn');
const path = require('path');
const fs = require('fs');

// Load environment variables from a .env file in the current directory, if any.
// quiet/debug are set explicitly so dotenv never writes to the console.
require('dotenv').config({ quiet: true, debug: false });

// Console script defined in pyproject.toml ([project.scripts]).
const SERVER_COMMAND = 'smithsonian-mcp';

/**
 * Write a diagnostic line to stderr.
 * @param {string} [message]
 */
function log(message = '') {
  process.stderr.write(`${message}\n`);
}

class SmithsonianMCPServer {
  constructor() {
    this.packagePath = path.resolve(__dirname, '..');
    this.process = null;
  }

  /**
   * Check if uv is installed
   */
  checkUv() {
    const result = spawn.sync('uv', ['--version'], { stdio: 'pipe' });

    if (!result.error && result.status === 0) {
      log(`Found ${result.stdout.toString().trim()}`);
      return;
    }

    throw new Error(
      'uv not found. Please install uv first:\n' +
      '  macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh\n' +
      '  Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"\n' +
      '  Or visit: https://docs.astral.sh/uv/getting-started/installation/'
    );
  }

  /**
   * Ensure runtime dependencies are installed from uv.lock.
   *
   * --frozen installs exactly what uv.lock pins without re-resolving.
   * --no-dev skips development tools. --inexact leaves any extra packages in
   * an existing environment alone, so a developer checkout keeps its dev tools.
   * The child's stdout is redirected to our stderr to keep stdout clean.
   */
  syncDependencies() {
    return new Promise((resolve, reject) => {
      log('Syncing Python dependencies with uv...');

      const sync = spawn('uv', ['sync', '--frozen', '--no-dev', '--inexact'], {
        stdio: ['ignore', 2, 2],
        cwd: this.packagePath
      });

      sync.on('close', (code) => {
        if (code === 0) {
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
      log('');
      log('Error: SMITHSONIAN_API_KEY is not set');
      log('Get your free API key from: https://api.data.gov/signup/');
      log('Set it as an environment variable: SMITHSONIAN_API_KEY=your_key_here');
      log('Or create a .env file in the working directory with: SMITHSONIAN_API_KEY=your_key_here');
      log('');
      return false;
    }

    if (apiKey.length < 20) {
      log('');
      log('Error: SMITHSONIAN_API_KEY does not look valid');
      log('API keys from api.data.gov are at least 20 characters long');
      log('');
      return false;
    }

    return true;
  }

  /**
   * Run a command inside the uv-managed project environment and exit with its
   * exit code. The environment was already synced by syncDependencies(), so
   * --no-sync skips a second sync. stdin/stdout/stderr are inherited so the
   * MCP host talks to the Python server directly.
   * @param {string[]} command
   */
  runInProject(command) {
    this.process = spawn('uv', ['run', '--no-sync', ...command], {
      stdio: 'inherit',
      cwd: this.packagePath,
      env: process.env
    });

    this.process.on('close', (code, signal) => {
      if (signal) {
        log(`Process terminated by signal ${signal}`);
        process.exit(1);
      }
      process.exit(code === null ? 1 : code);
    });

    this.process.on('error', (error) => {
      log(`Failed to start process: ${error.message}`);
      process.exit(1);
    });

    const forward = (signal) => {
      if (this.process) {
        this.process.kill(signal);
      }
    };
    process.on('SIGINT', () => forward('SIGINT'));
    process.on('SIGTERM', () => forward('SIGTERM'));
  }

  /**
   * Start the MCP server
   */
  async start(args = []) {
    try {
      log('Smithsonian Open Access MCP Server');

      this.checkUv();
      await this.syncDependencies();

      if (!this.validateApiKey()) {
        process.exit(1);
      }

      log('Starting MCP server on stdio...');
      this.runInProject([SERVER_COMMAND, ...args]);
    } catch (error) {
      log(`Error starting MCP server: ${error.message}`);
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
                 uv downloads a compatible Python (3.10 or newer) if needed.

Environment Variables:
  SMITHSONIAN_API_KEY    Your Smithsonian API key (required)
                         Get it from: https://api.data.gov/signup/

Examples:
  # Start the MCP server (stdio transport)
  smithsonian-mcp

  # Test API connection
  smithsonian-mcp --test

  # Start with an explicit API key
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
      log('Testing Smithsonian API connection...');

      this.checkUv();
      await this.syncDependencies();

      if (!this.validateApiKey()) {
        process.exit(1);
      }

      const testScript = path.join(this.packagePath, 'examples', 'test-api-connection.py');

      if (!fs.existsSync(testScript)) {
        log(`Test script not found: ${testScript}`);
        process.exit(1);
      }

      this.runInProject(['python', testScript]);
    } catch (error) {
      log(`Error running test: ${error.message}`);
      process.exit(1);
    }
  }
}

// Main execution
async function main() {
  const args = process.argv.slice(2);
  const server = new SmithsonianMCPServer();

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

  await server.start(args);
}

process.on('uncaughtException', (error) => {
  log(`Uncaught exception: ${error.message}`);
  process.exit(1);
});

process.on('unhandledRejection', (reason) => {
  log(`Unhandled rejection: ${reason}`);
  process.exit(1);
});

main().catch((error) => {
  log(`Fatal error: ${error.message}`);
  process.exit(1);
});
