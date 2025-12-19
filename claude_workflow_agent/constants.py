"""
Global constants for Claude Workflow Agent

Centralizes all magic numbers and configuration values for easy maintenance.
"""

# =============================================================================
# AGENT CONFIGURATION
# =============================================================================

# Model Configuration
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"  # Model for both Main Agent and Executor Agent

# Main Agent
MAX_TOOL_ROUNDS = 20  # Maximum number of tool call rounds per agent turn
MAX_TOKENS_PER_REQUEST = 32000  # Maximum tokens for Claude API requests (streaming enabled)
AGENT_TEMPERATURE = 0.1  # Temperature for agent responses (low for consistency)

# Executor Agent
MAX_ITERATIONS = 100  # Maximum workflow execution iterations
MAX_TOKEN_BUDGET = 10000000  # Maximum token budget for workflow execution


# =============================================================================
# DISPLAY & UI
# =============================================================================

# Tool result display truncation
TOOL_RESULT_SHORT_DISPLAY_LENGTH = 100  # For tool calls display
TOOL_RESULT_FULL_DISPLAY_LENGTH = 1000  # For detailed results display


# =============================================================================
# MCP TOOL EXECUTION
# =============================================================================

# Timeouts (in seconds)
MCP_TOOL_CALL_TIMEOUT = 30.0  # Timeout for individual MCP tool calls
MCP_OAUTH_CALLBACK_TIMEOUT = 60  # Timeout for OAuth callback wait
MCP_OAUTH_CALLBACK_TIMEOUT_DISCOVERY = 120  # Longer timeout during discovery
MCP_SESSION_CALLBACK_TIMEOUT = 300  # Maximum callback server wait time

# HTTP Client
MCP_HTTP_CLIENT_TIMEOUT = 30.0  # HTTP client timeout for MCP connections
MCP_HTTP_CLIENT_TIMEOUT_DISCOVERY = 60.0  # Longer timeout during discovery

# Callback Server
CALLBACK_SERVER_JOIN_TIMEOUT = 1  # Thread join timeout when stopping server

# OAuth Token Management  
TOKEN_EXPIRATION_BUFFER = 300  # Refresh tokens 5 minutes (300s) before expiry


# =============================================================================
# FILE PATHS
# =============================================================================

DEFAULT_WORKFLOWS_DIR = "./workflows"  # Default directory for workflows
WORKFLOW_FILENAME = "workflow.md"  # Standard workflow filename
TOOLS_CONFIG_FILENAME = "tools.json"  # Tools configuration filename
MCP_TOKENS_DIR = ".mcp_tokens"  # Directory for OAuth token storage


# =============================================================================
# ANSI COLOR CODES (for dev mode)
# =============================================================================

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_TOOL_CALL = "\033[94m"  # Blue
COLOR_SUCCESS = "\033[92m"  # Green
COLOR_ERROR = "\033[91m"  # Red
COLOR_RESULT = "\033[90m"  # Gray
