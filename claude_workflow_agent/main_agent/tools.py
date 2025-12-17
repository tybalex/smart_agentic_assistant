"""
Tool functions available to Main Agent
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import MCP_TOOL_CALL_TIMEOUT, DEFAULT_WORKFLOWS_DIR, WORKFLOW_FILENAME
from tools.mcp_registry import create_registry_from_config
from executor.executor_agent import ExecutorAgent
from executor.models import ToolConfig, ExecutionTrace


# Global registry cache (initialized once per session)
_registry_cache = None
_discovered_tools_cache = None


async def discover_mcp_tools() -> Dict[str, Any]:
    """
    Discover all available MCP tools from configured MCP servers.
    Uses in-memory cache within the same session to avoid redundant calls.
    
    Returns:
        Dict with: {
            "success": bool,
            "servers": List[str],
            "tools": List[{server, tool, description, input_schema, output_schema}],
            "total": int
        }
    """
    global _registry_cache, _discovered_tools_cache
    
    try:
        # Use in-memory cache if available (within same session)
        if _discovered_tools_cache:
            return _discovered_tools_cache
        
        # Need to discover - create registry if needed
        print("🔍 Discovering MCP tools...")
        if not _registry_cache:
            _registry_cache = await create_registry_from_config()
        
        # Discover all tools
        tools_by_server = await _registry_cache.discover_all_tools()
        
        # Flatten to simple list with ALL fields including schemas
        all_tools = []
        for server, tools in tools_by_server.items():
            for tool in tools:
                all_tools.append({
                    "server": server,
                    "tool": tool["tool"],
                    "description": tool["description"],
                    "input_schema": tool.get("input_schema"),
                    "output_schema": tool.get("output_schema")
                })
        
        result = {
            "success": True,
            "servers": list(tools_by_server.keys()),
            "tools": all_tools,
            "total": len(all_tools)
        }
        
        # Cache for session (in-memory only)
        _discovered_tools_cache = result
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def read_workflow(path: str) -> Dict[str, Any]:
    """
    Read a workflow.md file.
    
    Args:
        path: Path to workflow.md file
    
    Returns:
        Dict with: {success: bool, content: str}
    """
    try:
        file_path = Path(path)
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File not found: {path}"
            }
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        return {
            "success": True,
            "content": content,
            "path": str(file_path.absolute())
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def write_workflow(path: str, content: str) -> Dict[str, Any]:
    """
    Write/update a workflow.md file.
    Ensures workflows are in subdirectories with standard name.
    
    Args:
        path: Path like "./workflows/my_workflow" or "./workflows/my_workflow/workflow.md"
        content: Workflow content
    
    Returns:
        Dict with: {success: bool, path: str, directory: str}
    """
    try:
        file_path = Path(path)
        
        # Normalize path: ensure it ends with /workflow.md in a subdirectory
        if file_path.suffix != '.md':
            # Path is directory-like, add workflow.md
            file_path = file_path / "workflow.md"
        elif file_path.name != "workflow.md":
            # Path is a .md file but not named workflow.md
            # Put it in a subdirectory with that name
            workflow_dir = file_path.parent / file_path.stem
            file_path = workflow_dir / "workflow.md"
        
        # Create directory
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(file_path, 'w') as f:
            f.write(content)
        
        return {
            "success": True,
            "path": str(file_path.absolute()),
            "directory": str(file_path.parent.absolute()),
            "message": "Workflow saved successfully"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def run_mcp_tool(server: str, tool: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run an MCP tool directly to test it or use it.
    Useful for testing tools before creating workflows.
    
    Args:
        server: MCP server name (e.g., "slack", "salesforce")
        tool: Tool name (e.g., "send_message", "query")
        parameters: Tool parameters as dict
    
    Returns:
        Dict with: {success: bool, result: Any, error: str (if failed)}
    """
    global _registry_cache
    
    try:
        # Create registry if needed
        if not _registry_cache:
            print("📦 Creating MCP registry...")
            _registry_cache = await create_registry_from_config()
        
        # Execute the tool with timeout
        print(f"🔧 Executing MCP tool: {server}/{tool}...")
        
        import asyncio
        import traceback
        try:
            result = await asyncio.wait_for(
                _registry_cache.call_tool(
                    server_name=server,
                    tool_name=tool,
                    arguments=parameters
                ),
                timeout=MCP_TOOL_CALL_TIMEOUT
            )
            
            print(f"✅ Tool executed successfully")
            return {
                "success": True,
                "result": result
            }
            
        except asyncio.TimeoutError:
            print(f"⏱️  Tool execution timed out after 30 seconds")
            return {
                "success": False,
                "error": "Tool execution timed out. The MCP server may be slow or unavailable."
            }
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            
            # If the error message already contains our friendly error format, use it
            if "⚠️  MCP Server Format Error:" in error_msg:
                print(f"❌ {error_msg[:150]}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Check if it's a known issue
            if "ValidationError" in error_type or "pydantic" in error_msg.lower() or "CallToolResult" in error_msg:
                print(f"❌ MCP server format error")
                return {
                    "success": False,
                    "error": f"⚠️  MCP Server Format Error: The '{server}' server returned data in an unexpected format. This is a bug in the MCP server, not your code."
                }
            
            # Generic error - show concise info
            print(f"❌ Error: {error_type}: {error_msg[:100]}")
            return {
                "success": False,
                "error": f"{error_type}: {error_msg[:300]}"
            }
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Tool execution failed: {error_msg[:200]}")
        return {
            "success": False,
            "error": error_msg
        }


def select_mcp_tools(workflow_path: str, tool_list: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Select MCP tools for workflow and save to tools.json in same directory.
    Fetches complete tool information (description, input_schema, output_schema) from MCP registry.
    
    Args:
        workflow_path: Path to workflow.md
        tool_list: List of {server, tool} dicts to include (MCP tools)
                   Optional: can include "description", "input_schema", "output_schema"
    
    Returns:
        Dict with: {success: bool, tools_path: str, selected_count: int}
    """
    try:
        workflow_file = Path(workflow_path)
        
        # Ensure workflow_file is absolute
        if not workflow_file.is_absolute():
            workflow_file = workflow_file.resolve()
        
        # tools.json goes in same directory as workflow.md
        tools_path = workflow_file.parent / "tools.json"
        
        # Get unique servers
        servers = list(set(t["server"] for t in tool_list))
        
        # ALWAYS use discovered tools cache for complete tool information
        # tool_list should just be {"server": "x", "tool": "y"}
        if not _discovered_tools_cache or not _discovered_tools_cache.get("tools"):
            print("⚠️  Warning: No discovered tools cache available.")
            print("   Call discover_mcp_tools() first to get complete tool information.")
            print("   Continuing with minimal tool definitions...")
            
            # No cache - create minimal tool definitions
            enriched_tools = [
                {
                    "server": t["server"],
                    "tool": t["tool"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema"),
                }
                for t in tool_list
            ]
        else:
            # Build lookup map of (server, tool) -> full tool info from cache
            tool_info_map = {}
            for tool_info in _discovered_tools_cache["tools"]:
                key = (tool_info["server"], tool_info["tool"])
                tool_info_map[key] = tool_info
            
            # Get complete info for each requested tool from cache
            enriched_tools = []
            missing_tools = []
            
            for t in tool_list:
                key = (t["server"], t["tool"])
                cached_info = tool_info_map.get(key)
                
                if not cached_info:
                    # Tool not found in discovery - warn but include it
                    missing_tools.append(f"{t['server']}/{t['tool']}")
                    enriched_tool = {
                        "server": t["server"],
                        "tool": t["tool"],
                        "description": "",
                        "input_schema": None
                    }
                else:
                    # Use complete info from discovery cache
                    enriched_tool = {
                        "server": cached_info["server"],
                        "tool": cached_info["tool"],
                        "description": cached_info.get("description", ""),
                        "input_schema": cached_info.get("input_schema"),
                    }
                    
                    # Only include output_schema if present
                    if cached_info.get("output_schema"):
                        enriched_tool["output_schema"] = cached_info["output_schema"]
                
                enriched_tools.append(enriched_tool)
            
            # Report results
            found_count = len(enriched_tools) - len(missing_tools)
            print(f"✅ Enriched {found_count}/{len(enriched_tools)} tools with complete schemas from cache")
            
            if missing_tools:
                print(f"⚠️  Warning: {len(missing_tools)} tool(s) not found in discovery:")
                for tool in missing_tools:
                    print(f"   - {tool}")
                print("   These tools will have null schemas. Verify tool names are correct.")
        
        # Create tools.json format
        tools_config = {
            "mcp_servers": servers,
            "tools": enriched_tools,
            "version": "1.0"
        }
        
        # Save file
        with open(tools_path, 'w') as f:
            json.dump(tools_config, f, indent=2)
        
        return {
            "success": True,
            "tools_path": str(tools_path.absolute()),
            "selected_count": len(enriched_tools),
            "servers": servers
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def execute_workflow(workflow_path: str) -> Dict[str, Any]:
    """
    Execute workflow with Executor Agent.
    
    Args:
        workflow_path: Path to workflow.md file
    
    Returns:
        Dict with execution trace data
    """
    try:
        workflow_file = Path(workflow_path)
        tools_path = workflow_file.parent / "tools.json"
        
        if not workflow_file.exists():
            return {
                "success": False,
                "error": f"Workflow not found: {workflow_path}"
            }
        
        if not tools_path.exists():
            return {
                "success": False,
                "error": f"tools.json not found at {tools_path}. Call select_tools() first."
            }
        
        # Load workflow and tools
        with open(workflow_file, 'r') as f:
            workflow_content = f.read()
        
        with open(tools_path, 'r') as f:
            tools_data = json.load(f)
        
        tools_config = ToolConfig.from_json(tools_data)
        
        # Create mock tool executor for now
        # TODO: Replace with real MCP tool executor
        from executor.executor_agent import ExecutorAgent
        
        # For now, use a mock executor
        class MockExecutor:
            def execute_tool(self, server, tool, parameters):
                return {
                    "success": True,
                    "message": f"Mock execution: {server}/{tool}"
                }
        
        mock_executor = MockExecutor()
        
        # Check if dev mode is enabled (verbose output)
        import os
        dev_mode = os.environ.get("DEV_MODE", "").lower() in ("true", "1", "yes")
        
        # Create and run executor
        if not dev_mode:
            print("⏳ Executing workflow with Executor Agent...")
        executor = ExecutorAgent(tool_executor=mock_executor, verbose=dev_mode)
        trace = executor.execute_workflow(
            workflow_path=str(workflow_file),
            tools_config=tools_config,
            workflow_content=workflow_content
        )
        if not dev_mode:
            print("✅ Workflow execution completed")
        
        # Check if execution was successful
        from executor.models import SessionStatus, ActionStatus
        success = trace.status == SessionStatus.COMPLETED
        
        # Build result with meaningful information
        completed_steps = sum(1 for s in trace.steps if s.status == ActionStatus.COMPLETED)
        failed_steps = sum(1 for s in trace.steps if s.status == ActionStatus.FAILED)
        
        result = {
            "success": success,
            "status": trace.status.value,
            "session_id": trace.session_id,
            "total_steps": len(trace.steps),
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "trace_summary": f"Executed {len(trace.steps)} steps, {completed_steps} succeeded"
        }
        
        # Include full trace in result for detailed inspection
        if not success:
            result["details"] = "Workflow execution incomplete or failed. Check failed_steps."
            # Include last few steps for debugging
            if trace.steps:
                result["last_steps"] = [
                    {
                        "step": s.step_number,
                        "description": s.description[:100] if s.description else "N/A",
                        "status": s.status.value,
                        "error": s.error
                    }
                    for s in trace.steps[-3:]  # Last 3 steps
                ]
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": str(e.__traceback__)
        }


def list_workflows(directory: str = None) -> Dict[str, Any]:
    """
    List existing workflows in directory.
    Looks for subdirectories containing workflow.md files.
    
    Args:
        directory: Directory to search (default: from constants.DEFAULT_WORKFLOWS_DIR)
    
    Returns:
        Dict with: {success: bool, workflows: List[{path, name, directory}]}
    """
    try:
        if directory is None:
            directory = DEFAULT_WORKFLOWS_DIR
        
        dir_path = Path(directory)
        
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "workflows": [],
                "count": 0,
                "message": f"Created workflows directory: {dir_path}"
            }
        
        # Find all workflow.md files in subdirectories
        workflows = []
        for wf in dir_path.rglob("workflow.md"):
            # Only include if it's in a subdirectory (not root)
            if wf.parent != dir_path:
                workflows.append({
                    "path": str(wf.absolute()),
                    "name": wf.parent.name,
                    "directory": str(wf.parent.absolute())
                })
        
        return {
            "success": True,
            "workflows": workflows,
            "count": len(workflows)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Tool registry for Main Agent (function mapping)
AVAILABLE_TOOLS = {
    "discover_mcp_tools": discover_mcp_tools,
    "run_mcp_tool": run_mcp_tool,
    "read_workflow": read_workflow,
    "write_workflow": write_workflow,
    "select_mcp_tools": select_mcp_tools,
    "execute_workflow": execute_workflow,
    "list_workflows": list_workflows
}

# Anthropic-format tool definitions for API
ANTHROPIC_TOOLS = [
    {
        "name": "discover_mcp_tools",
        "description": "Discover all available MCP tools from configured MCP servers. Returns list of {server, tool, description}.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "run_mcp_tool",
        "description": "Run an MCP tool directly to test it or execute it. Useful for testing MCP tools before building workflows. IMPORTANT: Use EXACT tool names from discover_mcp_tools results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "MCP server name (e.g., 'slack', 'salesforce', 'google-groups'). Must match server name from discovery."
                },
                "tool": {
                    "type": "string",
                    "description": "EXACT tool name from discovery (e.g., 'send_message', 'list_google_groups', 'list_channels'). Do not abbreviate or guess - use exact name from discover_mcp_tools."
                },
                "parameters": {
                    "type": "object",
                    "description": "Tool parameters as key-value pairs"
                }
            },
            "required": ["server", "tool", "parameters"]
        }
    },
    {
        "name": "read_workflow",
        "description": "Read a workflow.md file and return its contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to workflow.md file"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_workflow",
        "description": "Write/update a workflow.md file in a subdirectory. Creates the directory structure automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path like './workflows/my_workflow' (will create workflow.md inside)"
                },
                "content": {
                    "type": "string",
                    "description": "Workflow content in markdown format"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "select_mcp_tools",
        "description": "Select MCP tools for workflow and generate tools.json. CRITICAL: You MUST call discover_mcp_tools() FIRST to see available tools. NEVER GUESS tool names - only use EXACT names from discovery results. The function will warn you if tool names don't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_path": {
                    "type": "string",
                    "description": "Path to workflow.md file"
                },
                "tool_list": {
                    "type": "array",
                    "description": "List of MCP tool objects with EXACT server and tool names from discovery. Example: for sending Slack messages, use 'send_message' NOT 'send_slack_message' or other variations. Check the CURRENT SESSION STATE section for available tools.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "server": {"type": "string", "description": "EXACT MCP server name from discovery (e.g., 'slack', 'salesforce', 'google-groups')"},
                            "tool": {"type": "string", "description": "EXACT MCP tool name from discovery (e.g., 'send_message', 'email_message', 'add_group_member'). DO NOT abbreviate, guess, or modify tool names."}
                        },
                        "required": ["server", "tool"]
                    }
                }
            },
            "required": ["workflow_path", "tool_list"]
        }
    },
    {
        "name": "execute_workflow",
        "description": "Execute workflow with Executor Agent and return detailed execution results including status, step counts, and any errors.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_path": {
                    "type": "string",
                    "description": "Path to workflow.md file (e.g., './workflows/my_workflow/workflow.md')"
                }
            },
            "required": ["workflow_path"]
        }
    },
    {
        "name": "list_workflows",
        "description": "List existing workflows in a directory. Returns workflow names, paths, and directories.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to search (optional, defaults to './workflows')"
                }
            },
            "required": []
        }
    }
]
