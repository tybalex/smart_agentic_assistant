"""
MCP Tool Registry - Connects to MCP servers and discovers tools
Main Agent uses this to discover tools and select which ones to give to Executor
"""

import asyncio
import os
import threading
import time
import webbrowser
import logging
from typing import Dict, List, Any, Optional
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import httpx
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

# Suppress verbose logging from httpx and mcp
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("mcp").setLevel(logging.ERROR)
logging.getLogger("mcp.client").setLevel(logging.ERROR)
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)


# ==================== OAuth Support ====================

class InMemoryTokenStorage(TokenStorage):
    """In-memory token storage for OAuth"""
    
    def __init__(self):
        self._tokens: OAuthToken | None = None
        self._client_info: OAuthClientInformationFull | None = None
    
    async def get_tokens(self) -> OAuthToken | None:
        return self._tokens
    
    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens
    
    async def get_client_info(self) -> OAuthClientInformationFull | None:
        return self._client_info
    
    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._client_info = client_info


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback"""
    
    def __init__(self, request, client_address, server, callback_data):
        self.callback_data = callback_data
        super().__init__(request, client_address, server)
    
    def do_GET(self):
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        
        if "code" in query_params:
            self.callback_data["authorization_code"] = query_params["code"][0]
            self.callback_data["state"] = query_params.get("state", [None])[0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authorization Successful!</h1><p>You can close this window.</p></body></html>")
        elif "error" in query_params:
            self.callback_data["error"] = query_params["error"][0]
            self.send_response(400)
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logs


class CallbackServer:
    """OAuth callback server"""
    
    def __init__(self, port=3030):
        self.port = port
        self.server = None
        self.thread = None
        self.callback_data = {"authorization_code": None, "state": None, "error": None}
    
    def _create_handler_with_data(self):
        callback_data = self.callback_data
        class DataCallbackHandler(CallbackHandler):
            def __init__(self, request, client_address, server):
                super().__init__(request, client_address, server, callback_data)
        return DataCallbackHandler
    
    def start(self):
        handler_class = self._create_handler_with_data()
        self.server = HTTPServer(("localhost", self.port), handler_class)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
    
    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)
    
    def wait_for_callback(self, timeout=300):
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.callback_data["authorization_code"]:
                return self.callback_data["authorization_code"]
            elif self.callback_data["error"]:
                raise Exception(f"OAuth error: {self.callback_data['error']}")
            time.sleep(0.1)
        raise Exception("Timeout waiting for OAuth callback")
    
    def get_state(self):
        return self.callback_data["state"]


# ==================== MCP Tool Registry ====================

class MCPToolRegistry:
    """
    Registry for MCP tools across multiple servers.
    Main Agent uses this to discover tools and select which ones to give to Executor.
    """
    
    def __init__(self, server_configs: Dict[str, str]):
        """
        Initialize registry with MCP server configurations.
        
        Args:
            server_configs: Dict mapping server name to URL
                           e.g., {"slack": "https://...", "gmail": "https://..."}
        """
        self.server_configs = server_configs
        self.tools_by_server: Dict[str, List[Dict[str, Any]]] = {}
        self._token_storage: Dict[str, InMemoryTokenStorage] = {}  # Reuse OAuth tokens
    
    async def connect_and_discover(self, server_name: str, server_url: str) -> List[Dict[str, Any]]:
        """
        Connect to MCP server with OAuth and discover tools immediately.
        Must be done in one go because session closes when context exits.
        
        Returns:
            List of discovered tools
        """
        print(f"  🔗 Connecting to {server_name}...", end=" ", flush=True)
        
        # Start OAuth callback server
        callback_server = CallbackServer(port=3030)
        callback_server.start()
        
        async def callback_handler() -> tuple[str, str | None]:
            try:
                auth_code = callback_server.wait_for_callback(timeout=300)
                return auth_code, callback_server.get_state()
            finally:
                callback_server.stop()
        
        async def redirect_handler(authorization_url: str) -> None:
            # Silently open browser - user will see it open
            webbrowser.open(authorization_url)
        
        # Reuse or create token storage
        if server_name not in self._token_storage:
            self._token_storage[server_name] = InMemoryTokenStorage()
        
        storage = self._token_storage[server_name]
        
        # OAuth client setup
        client_metadata = OAuthClientMetadata.model_validate({
            "client_name": "Claude Workflow Agent",
            "redirect_uris": ["http://localhost:3030/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        })
        
        oauth_auth = OAuthClientProvider(
            server_url=server_url.replace("/mcp", ""),
            client_metadata=client_metadata,
            storage=storage,
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
        )
        
        # Connect with streamable HTTP and discover tools immediately
        tools = []
        async with httpx.AsyncClient(auth=oauth_auth, follow_redirects=True) as custom_client:
            async with streamable_http_client(
                url=server_url,
                http_client=custom_client,
            ) as (read_stream, write_stream, get_session_id):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # List tools while session is open
                    tools_response = await session.list_tools()
                    
                    for tool in tools_response.tools:
                        tools.append({
                            "server": server_name,
                            "tool": tool.name,
                            "description": tool.description or "",
                            "input_schema": tool.inputSchema,
                            "output_schema": getattr(tool, 'outputSchema', None)
                        })
                    
                    print(f"✅ {len(tools)} tools")
        
        # Store tools (after all contexts have closed)
        self.tools_by_server[server_name] = tools
        return tools
    
    async def discover_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        Discover all available tools from a server.
        
        Returns:
            List of tool metadata dicts with: name, description, inputSchema
        """
        # Check if already discovered
        if server_name in self.tools_by_server:
            return self.tools_by_server[server_name]
        
        # Get server URL
        server_url = self.server_configs.get(server_name)
        if not server_url:
            raise ValueError(f"Unknown server: {server_name}")
        
        # Connect and discover in one go
        tools = await self.connect_and_discover(server_name, server_url)
        return tools
    
    async def discover_all_tools(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Discover tools from all configured servers.
        
        Returns:
            Dict mapping server name to list of tools
        """
        print(f"🔍 Discovering tools from {len(self.server_configs)} servers...")
        print(f"   (This will open browsers for OAuth authorization)")
        print()
        
        for server_name, server_url in self.server_configs.items():
            try:
                await self.discover_tools(server_name)
            except Exception as e:
                print(f"⚠️  Failed to discover tools from {server_name}: {e}")
                self.tools_by_server[server_name] = []
        
        # Summary
        print()
        for server_name, tools in self.tools_by_server.items():
            print(f"  ✅ {server_name}: {len(tools)} tools")
        
        total_tools = sum(len(tools) for tools in self.tools_by_server.values())
        print()
        print(f"✅ Total: {total_tools} tools from {len(self.tools_by_server)} servers")
        
        return self.tools_by_server
    
    def get_all_tools_summary(self) -> str:
        """
        Get formatted summary of all discovered tools for Main Agent.
        
        Returns:
            Human-readable summary string
        """
        lines = ["AVAILABLE TOOLS FROM MCP SERVERS:", ""]
        
        for server_name, tools in self.tools_by_server.items():
            lines.append(f"[{server_name}] ({len(tools)} tools)")
            for tool in tools:
                lines.append(f"  - {tool['tool']}: {tool['description'][:80]}")
            lines.append("")
        
        return "\n".join(lines)
    
    def filter_tools_by_names(
        self,
        selected_tools: List[tuple[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Filter tools by (server, tool_name) pairs for Executor.
        
        Args:
            selected_tools: List of (server_name, tool_name) tuples
        
        Returns:
            List of tool configs for tools.json format
        """
        selected = []
        
        for server_name, tool_name in selected_tools:
            if server_name not in self.tools_by_server:
                print(f"⚠️  Warning: Server {server_name} not found")
                continue
            
            for tool in self.tools_by_server[server_name]:
                if tool['tool'] == tool_name:
                    selected.append({
                        "server": server_name,
                        "tool": tool_name,
                        "description": tool['description']
                    })
                    break
        
        print(f"✅ Selected {len(selected)} tools for Executor")
        return selected
    
    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """
        Call a tool on a specific server.
        Reconnects each time (sessions don't persist).
        
        Args:
            server_name: Name of MCP server
            tool_name: Name of tool to call
            arguments: Tool arguments
        
        Returns:
            Tool result
        """
        server_url = self.server_configs.get(server_name)
        if not server_url:
            raise ValueError(f"Unknown server: {server_name}")
        
        # Reuse token storage if available (avoids re-auth)
        if server_name not in self._token_storage:
            self._token_storage[server_name] = InMemoryTokenStorage()
        
        storage = self._token_storage[server_name]
        
        # OAuth setup (will reuse tokens if available)
        client_metadata = OAuthClientMetadata.model_validate({
            "client_name": "Claude Workflow Agent",
            "redirect_uris": ["http://localhost:3030/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        })
        
        oauth_auth = OAuthClientProvider(
            server_url=server_url.replace("/mcp", ""),
            client_metadata=client_metadata,
            storage=storage,
            redirect_handler=lambda url: None,  # No browser needed if tokens cached
            callback_handler=None,
        )
        
        # Connect and call tool
        async with httpx.AsyncClient(auth=oauth_auth, follow_redirects=True) as http_client:
            async with streamable_http_client(
                url=server_url,
                http_client=http_client,
            ) as (read_stream, write_stream, get_session_id):
                session = ClientSession(read_stream, write_stream)
                await session.initialize()
                
                # Call tool
                result = await session.call_tool(tool_name, arguments)
                
                # Parse result
                if hasattr(result, 'content'):
                    contents = []
                    for content in result.content:
                        if content.type == "text":
                            contents.append(content.text)
                        else:
                            contents.append(str(content))
                    return {"success": True, "result": "\n".join(contents)}
                else:
                    return {"success": True, "result": str(result)}


# ==================== Tool Executor Adapter ====================

class MCPToolExecutor:
    """
    Adapter that wraps MCPToolRegistry for use by Executor Agent.
    Only allows execution of tools that were selected by Main Agent.
    """
    
    def __init__(self, registry: MCPToolRegistry, allowed_tools: List[Dict[str, str]]):
        """
        Initialize with registry and allowed tools.
        
        Args:
            registry: MCPToolRegistry instance
            allowed_tools: List of allowed tool dicts with server/tool/description
        """
        self.registry = registry
        self.allowed_tools_set = {
            (tool['server'], tool['tool']) for tool in allowed_tools
        }
        print(f"🔒 MCPToolExecutor initialized with {len(self.allowed_tools_set)} allowed tools")
    
    async def execute_tool(
        self,
        server: str,
        tool: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute tool if it's in allowed list.
        
        Returns:
            Tool result or error
        """
        # Check if tool is allowed
        if (server, tool) not in self.allowed_tools_set:
            return {
                "success": False,
                "error": f"Tool {server}/{tool} not in allowed tools list"
            }
        
        # Execute via registry
        try:
            return await self.registry.call_tool(server, tool, parameters)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# ==================== Helper Functions ====================

async def create_registry_from_config() -> MCPToolRegistry:
    """
    Create MCPToolRegistry from config.py servers.
    Automatically loads all MCP servers defined in .env file.
    
    Returns:
        Initialized MCPToolRegistry
    """
    # Handle both relative and absolute imports
    try:
        from . import config
    except ImportError:
        import config
    
    # Get all servers from .env
    server_configs = config.get_all_servers()
    
    if not server_configs:
        raise ValueError(
            "No MCP servers found in .env file! "
            "Add servers like: MY_SERVER=https://..."
        )
    
    registry = MCPToolRegistry(server_configs)
    return registry
