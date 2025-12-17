"""
MCP Server Configuration
Reads all MCP server URLs from .env file dynamically
"""

import os
from pathlib import Path
from typing import Dict
from dotenv import dotenv_values

# Load .env from claude_workflow_agent directory
env_path = Path(__file__).parent.parent / ".env"

# Load all values from .env
env_vars = dotenv_values(dotenv_path=env_path)

# Filter for MCP server URLs (anything that looks like a URL)
# Users can name servers anything they want in .env
MCP_SERVERS: Dict[str, str] = {}

for key, value in env_vars.items():
    if value and isinstance(value, str):
        # Check if it looks like an MCP server URL
        if value.startswith("http://") or value.startswith("https://"):
            # Use the env var name (converted to lowercase) as server name
            server_name = key.lower().replace("mcp_url_", "").replace("_", "-")
            MCP_SERVERS[server_name] = value


def get_all_servers() -> Dict[str, str]:
    """
    Get all configured MCP servers.
    
    Returns:
        Dict mapping server name to URL
    """
    return MCP_SERVERS


def get_server_url(server_name: str) -> str:
    """
    Get URL for a specific server.
    
    Args:
        server_name: Name of the server
        
    Returns:
        Server URL or empty string if not found
    """
    return MCP_SERVERS.get(server_name, "")
