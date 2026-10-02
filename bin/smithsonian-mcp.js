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
const os = require('os');
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

/**
 * Per-user cache directory for the current OS.
 * @returns {string}
 */
function userCacheDir() {
  const home = os.homedir();
  if (process.platform === 'win32') {
    return process.env.LOCALAPPDATA || path.join(home, 'AppData', 'Local');
  }
  if (process.platform === 'darwin') {
    return path.join(home, 'Library', 'Caches');
  }
  return process.env.XDG_CACHE_HOME || path.join(home, '.cache');
}

class SmithsonianMCPServer {
  constructor() {
    this.packagePath = path.resolve(__dirname, '..');
    this.version = require(path.join(this.packagePath, 'package.json')).version;
    this.process = null;

    // Where the Python environment lives:
    //
    // - Development checkout (the package directory is a git checkout, for
    //   example `npm start` or `npm link`): keep uv's default `.venv` in the
    //   checkout with an editable install, so it is the same environment that
    //   `uv sync --group dev` manages for development.
    // - Installed package (npx cache or a global install, which may sit under a
    //   root-owned prefix): the package directory is treated as read-only and
    //   the environment goes in a per-user cache directory, one per package
    //   version so an upgrade never reuses a stale environment. The package is
    //   installed non-editable, so the environment does not depend on where
    //   npm unpacked this copy.
    //
    // An explicit UV_PROJECT_ENVIRONMENT in the caller's environment wins.
    this.devCheckout = fs.existsSync(path.join(this.packagePath, '.git'));
    this.uvEnv = { ...process.env };
    if (!this.devCheckout && !process.env.UV_PROJECT_ENVIRONMENT) {
      this.uvEnv.UV_PROJECT_ENVIRONMENT = path.join(
        userCacheDir(),
        'smithsonian-mcp',
        `venv-${this.version}`
      );
    }
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
   * --no-dev skips development tools. In a development checkout, --inexact
   * leaves extra packages alone so the checkout keeps its dev tools; an
   * installed package gets an exact, non-editable sync into its own
   * environment (see the constructor). The child's stdout is redirected to our
   * stderr to keep stdout clean.
   */
  syncDependencies() {
    return new Promise((resolve, reject) => {
      const envDir = this.uvEnv.UV_PROJECT_ENVIRONMENT || path.join(this.packagePath, '.venv');
      log(`Syncing Python dependencies with uv into ${envDir}...`);

      const syncArgs = this.devCheckout
        ? ['sync', '--frozen', '--no-dev', '--inexact']
        : ['sync', '--frozen', '--no-dev', '--no-editable'];

      const sync = spawn('uv', syncArgs, {
        stdio: ['ignore', 2, 2],
        cwd: this.packagePath,
        env: this.uvEnv
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
      env: this.uvEnv
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

      log('Starting MCP server...');
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
  --help, -h                 Show this help message
  --version, -v              Show version information
  --test                     Run API connection test
  --transport {stdio,http}   Serve MCP over stdio (default) or streamable HTTP
  --host HOST                Address to listen on in HTTP mode (default: 127.0.0.1)
  --port PORT                Port to listen on in HTTP mode (default: 8000)
  --allowed-hosts NAMES      Host header names accepted in HTTP mode, comma-separated
                             (default: localhost, 127.0.0.1, ::1 and the --host address)

Requirements:
  uv             Fast Python package manager (https://docs.astral.sh/uv/)
                 Install with: curl -LsSf https://astral.sh/uv/install.sh | sh
                 uv downloads a compatible Python (3.10 or newer) if needed.

Environment Variables:
  SMITHSONIAN_API_KEY    Your Smithsonian API key (required)
                         Get it from: https://api.data.gov/signup/
  MCP_TRANSPORT          Default for --transport
  MCP_HOST, MCP_PORT     Defaults for --host and --port
  MCP_ALLOWED_HOSTS      Default for --allowed-hosts

Examples:
  # Start the MCP server (stdio transport)
  smithsonian-mcp

  # Serve streamable HTTP at http://127.0.0.1:8000/mcp
  smithsonian-mcp --transport http

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
    console.log(`@molanojustin/smithsonian-mcp v${this.version}`);
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
