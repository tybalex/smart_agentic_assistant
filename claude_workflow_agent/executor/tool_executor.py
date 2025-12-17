"""
Scoped Tool Executor - Only executes tools from tools.json
No dynamic discovery - fixed tool set.
"""

import logging
from typing import Dict, Any, Set
from .models import ToolConfig

logger = logging.getLogger(__name__)


class ScopedToolExecutor:
    """
    Tool executor that only allows execution of tools specified in tools.json.
    Wraps the underlying tool registry client with access control.
    """
    
    def __init__(self, tool_client, tools_config: ToolConfig):
        """
        Initialize with tool client and allowed tools config.
        
        Args:
            tool_client: Underlying ToolRegistryClient instance
            tools_config: ToolConfig from tools.json defining allowed tools
        """
        self.tool_client = tool_client
        self.tools_config = tools_config
        
        # Build lookup of allowed tools: "server/tool" -> tool config
        self.allowed_tools: Dict[str, Dict[str, str]] = {}
        for tool in tools_config.tools:
            key = f"{tool['server']}/{tool['tool']}"
            self.allowed_tools[key] = tool
        
        logger.info(f"Initialized with {len(self.allowed_tools)} allowed tools from {len(tools_config.mcp_servers)} MCP servers")
    
    def execute_tool(
        self,
        server: str,
        tool: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool if it's in the allowed list.
        
        Args:
            server: MCP server name (category in registry)
            tool: Tool name
            parameters: Tool parameters
        
        Returns:
            Execution result or error if tool not allowed
        """
        tool_key = f"{server}/{tool}"
        
        # Check if tool is allowed
        if tool_key not in self.allowed_tools:
            logger.error(f"Tool not allowed: {tool_key}")
            logger.error(f"Allowed tools: {list(self.allowed_tools.keys())}")
            return {
                "success": False,
                "error": f"Tool '{tool_key}' not in allowed tools list. Available: {list(self.allowed_tools.keys())}"
            }
        
        # Execute via underlying client
        # Note: registry uses "category" which maps to MCP server name
        logger.info(f"Executing allowed tool: {tool_key}")
        return self.tool_client.execute_function(
            category=server,
            function_name=tool,
            params=parameters
        )
    
    def get_allowed_tools_summary(self) -> str:
        """Get formatted summary of allowed tools for LLM context"""
        lines = [f"SCOPED TOOLS ({len(self.allowed_tools)} tools from tools.json):"]
        lines.append("")
        
        # Group by server
        by_server: Dict[str, List[Dict[str, str]]] = {}
        for tool_key, tool_config in self.allowed_tools.items():
            server = tool_config.get("server", "unknown")
            if server not in by_server:
                by_server[server] = []
            by_server[server].append(tool_config)
        
        # Format by server
        for server in sorted(by_server.keys()):
            lines.append(f"[{server}]")
            for tool_config in by_server[server]:
                tool_name = tool_config.get("tool", "unknown")
                desc = tool_config.get("description", "No description")
                lines.append(f"  - {tool_name}: {desc}")
            lines.append("")
        
        lines.append("NOTE: These are the ONLY tools you can use. No other tools are available.")
        return "\n".join(lines)
