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


async def list_mcp_servers() -> Dict[str, Any]:
    """
    List all configured MCP servers.
    
    Returns:
        Dict with: {
            "success": bool,
            "servers": List[str],
            "total": int
        }
    """
    global _registry_cache, _discovered_tools_cache
    
    try:
        # Check cache first
        if _discovered_tools_cache:
            return {
                "success": True,
                "servers": _discovered_tools_cache["servers"],
                "total": len(_discovered_tools_cache["servers"])
            }
        
        # Need to discover - create registry if needed
        if not _registry_cache:
            _registry_cache = await create_registry_from_config()
        
        # Discover to get server list
        tools_by_server = await _registry_cache.discover_all_tools()
        servers = list(tools_by_server.keys())
        
        return {
            "success": True,
            "servers": servers,
            "total": len(servers)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def list_mcp_tools(server: str = None) -> Dict[str, Any]:
    """
    List MCP tools available to the Main Agent from configured MCP servers.
    
    Args:
        server: Optional server name to filter tools. If None/empty, returns all tools.
    
    IMPORTANT: This shows tools the Main Agent has access to from MCP servers.
    To see which tools a specific WORKFLOW is configured to use, read that workflow's 
    tools.json file instead (it's in the same directory as workflow.md).
    
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
        if not _discovered_tools_cache:
            # Need to discover - create registry if needed
            print("🔍 Listing MCP tools from all configured servers...")
            if not _registry_cache:
                _registry_cache = await create_registry_from_config()
            
            # Discover all tools
            tools_by_server = await _registry_cache.discover_all_tools()
        
            # Flatten to simple list with ALL fields including schemas
            all_tools = []
            for srv, tools in tools_by_server.items():
                for tool in tools:
                    all_tools.append({
                        "server": srv,
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
        
        # Filter by server if specified
        if server:
            cached_tools = _discovered_tools_cache["tools"]
            filtered_tools = [t for t in cached_tools if t["server"] == server]
            
            if not filtered_tools:
                return {
                    "success": False,
                    "error": f"Server '{server}' not found or has no tools. Available servers: {', '.join(_discovered_tools_cache['servers'])}"
                }
            
            return {
                "success": True,
                "servers": [server],
                "tools": filtered_tools,
                "total": len(filtered_tools)
            }
        
        # Return all tools
        return _discovered_tools_cache
        
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


async def list_executor_sessions(workflow_path: str) -> Dict[str, Any]:
    """
    List saved executor sessions for a workflow.
    
    Args:
        workflow_path: Path to workflow.md file
    
    Returns:
        Dict with session list and metadata
    """
    try:
        workflow_file = Path(workflow_path)
        if not workflow_file.exists():
            return {
                "success": False,
                "error": f"Workflow not found: {workflow_path}"
            }
        
        # Sessions stored in .sessions/ subdirectory
        sessions_dir = workflow_file.parent / ".sessions"
        
        if not sessions_dir.exists():
            return {
                "success": True,
                "sessions": [],
                "total": 0,
                "message": "No sessions saved yet"
            }
        
        # List all session files
        session_files = sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        sessions = []
        for session_file in session_files:
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                    sessions.append({
                        "session_id": session_data.get("session_id"),
                        "status": session_data.get("status"),
                        "timestamp": session_data.get("timestamp"),
                        "total_steps": len(session_data.get("steps", [])),
                        "completed_steps": sum(1 for s in session_data.get("steps", []) if s.get("status") == "completed"),
                        "needs_clarification": bool(session_data.get("clarification_requests"))
                    })
            except Exception as e:
                print(f"⚠️  Error reading session {session_file.name}: {e}")
                continue
        
        return {
            "success": True,
            "sessions": sessions,
            "total": len(sessions),
            "sessions_dir": str(sessions_dir)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def load_executor_session(workflow_path: str, session_id: str) -> Dict[str, Any]:
    """
    Load a saved executor session.
    
    Args:
        workflow_path: Path to workflow.md file
        session_id: Session ID to load
    
    Returns:
        Dict with full session data
    """
    try:
        workflow_file = Path(workflow_path)
        sessions_dir = workflow_file.parent / ".sessions"
        session_file = sessions_dir / f"{session_id}.json"
        
        if not session_file.exists():
            return {
                "success": False,
                "error": f"Session '{session_id}' not found. Use list_executor_sessions() to see available sessions."
            }
        
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        
        return {
            "success": True,
            **session_data
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def execute_workflow(workflow_path: str, input_data: str = None, resume_session_id: str = None) -> Dict[str, Any]:
    """
    Execute workflow with Executor Agent from scratch or resume a previous session.
    
    Args:
        workflow_path: Path to workflow.md file
        input_data: Optional input data/variables for the workflow (e.g., company details, IDs, etc.)
        resume_session_id: Optional session ID to resume. If provided, continues from previous state.
    
    Returns:
        Dict with execution trace data
    """
    global _registry_cache  # Need to declare global to modify it
    
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
        
        # Create real MCP tool executor with registry
        from executor.executor_agent import ExecutorAgent
        from tools.mcp_registry import MCPToolExecutor
        
        # Create registry if needed
        if not _registry_cache:
            print("📦 Creating MCP registry for executor...")
            _registry_cache = await create_registry_from_config()
        
        # Create MCP tool executor with allowed tools from tools.json
        mcp_executor = MCPToolExecutor(
            registry=_registry_cache,
            allowed_tools=tools_config.tools
        )
        
        # Load previous session if resuming
        previous_trace = None
        if resume_session_id:
            sessions_dir = workflow_file.parent / ".sessions"
            session_file = sessions_dir / f"{resume_session_id}.json"
            
            if session_file.exists():
                print(f"📂 Loading previous session: {resume_session_id}")
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                # Convert to ExecutionTrace object (simplified - would need proper deserialization)
                previous_trace = session_data
            else:
                print(f"⚠️  Session '{resume_session_id}' not found, starting from scratch")
        
        # Create and run executor (output is now always visible)
        executor = ExecutorAgent(tool_executor=mcp_executor, verbose=False)
        trace = await executor.execute_workflow(
            workflow_path=str(workflow_file),
            tools_config=tools_config,
            workflow_content=workflow_content,
            input_data=input_data,
            previous_trace=previous_trace if resume_session_id else None
        )
        
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
        
        # Include clarification requests if workflow needs input
        if trace.clarification_requests:
            result["clarification_requests"] = [
                {
                    "question": cr.question,
                    "context": cr.context,
                    "step_number": cr.step_number
                }
                for cr in trace.clarification_requests
            ]
        
        # Include final summary if available
        if trace.final_summary:
            result["final_summary"] = trace.final_summary
        
        # Include full step details (not truncated) for Main Agent to analyze
        if trace.steps:
            result["steps"] = [
                {
                    "step": s.step_number,
                    "description": s.description,  # Full description, not truncated
                    "status": s.status.value,
                    "reasoning": s.reasoning if hasattr(s, 'reasoning') else None,
                    "tool_calls": s.tool_calls if hasattr(s, 'tool_calls') else [],
                    "result": s.result if hasattr(s, 'result') else None,
                    "error": s.error
                }
                for s in trace.steps
            ]
        
        # Save session to workflow directory with full state for resume
        sessions_dir = workflow_file.parent / ".sessions"
        sessions_dir.mkdir(exist_ok=True)
        
        session_file = sessions_dir / f"{trace.session_id}.json"
        
        # Serialize steps with all details for proper restoration
        serialized_steps = []
        for step in trace.steps:
            serialized_steps.append({
                "step_number": step.step_number,
                "description": step.description,
                "status": step.status.value,
                "reasoning": step.reasoning if hasattr(step, 'reasoning') else None,
                "tool_calls": step.tool_calls if hasattr(step, 'tool_calls') else [],
                "result": step.result if hasattr(step, 'result') else None,
                "error": step.error,
                "timestamp": step.timestamp
            })
        
        # Serialize clarification requests
        serialized_clarifications = []
        for cr in trace.clarification_requests:
            serialized_clarifications.append({
                "question": cr.question,
                "context": cr.context,
                "step_number": cr.step_number
            })
        
        # Get message history from executor
        message_history = []
        if hasattr(executor, 'message_history'):
            # Serialize message history - handle both simple and complex content
            for msg in executor.message_history:
                serialized_msg = {"role": msg["role"]}
                content = msg["content"]
                
                # Handle different content types
                if isinstance(content, str):
                    serialized_msg["content"] = content
                elif isinstance(content, list):
                    # Content blocks (text + tool_use)
                    serialized_content = []
                    for block in content:
                        if isinstance(block, dict):
                            serialized_content.append(block)
                        elif hasattr(block, 'text'):
                            serialized_content.append({"type": "text", "text": block.text})
                        elif hasattr(block, 'type') and block.type == 'tool_use':
                            serialized_content.append({
                                "type": "tool_use",
                                "id": block.id,
                                "name": block.name,
                                "input": block.input
                            })
                    serialized_msg["content"] = serialized_content
                else:
                    serialized_msg["content"] = str(content)
                
                message_history.append(serialized_msg)
        
        session_data = {
            "session_id": trace.session_id,
            "status": trace.status.value,
            "timestamp": trace.timestamp,
            "start_time": trace.start_time if hasattr(trace, 'start_time') else trace.timestamp,
            "end_time": trace.end_time if hasattr(trace, 'end_time') else None,
            "workflow_path": str(workflow_file),
            "input_data": input_data,
            "steps": serialized_steps,
            "clarification_requests": serialized_clarifications,
            "final_summary": trace.final_summary if hasattr(trace, 'final_summary') else result.get("final_summary"),
            "completed_steps": result["completed_steps"],
            "failed_steps": result["failed_steps"],
            "total_steps": result["total_steps"],
            "message_history": message_history  # Full conversation history for resume
        }
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        print(f"💾 Session saved: {session_file}")
        print(f"   📊 Saved {len(serialized_steps)} steps, {len(message_history)} messages")
        result["session_file"] = str(session_file)
        
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
    "list_mcp_servers": list_mcp_servers,
    "list_mcp_tools": list_mcp_tools,
    "run_mcp_tool": run_mcp_tool,
    "read_workflow": read_workflow,
    "write_workflow": write_workflow,
    "select_mcp_tools": select_mcp_tools,
    "execute_workflow": execute_workflow,
    "list_executor_sessions": list_executor_sessions,
    "load_executor_session": load_executor_session,
    "list_workflows": list_workflows
}

# Anthropic-format tool definitions for API
ANTHROPIC_TOOLS = [
    {
        "name": "list_mcp_servers",
        "description": "List all configured MCP servers. Returns a list of server names that Main Agent can access. Use this before list_mcp_tools() to see what servers are available.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_mcp_tools",
        "description": "List MCP tools available to Main Agent from configured servers. Can optionally filter by server. IMPORTANT: This shows the catalog of tools Main Agent can access, NOT the tools a specific workflow uses. To see which tools a workflow is configured to use, read the workflow's tools.json file instead (same directory as workflow.md).",
        "input_schema": {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "Optional: Server name to filter tools (e.g., 'slack', 'salesforce'). If not provided, returns tools from all servers. Use list_mcp_servers() to see available servers."
                }
            },
            "required": []
        }
    },
    {
        "name": "run_mcp_tool",
        "description": "Run an MCP tool directly to test it or execute it. Useful for testing MCP tools before building workflows. IMPORTANT: Use EXACT tool names from list_mcp_tools results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "server": {
                    "type": "string",
                    "description": "MCP server name (e.g., 'slack', 'salesforce', 'google-groups'). Must match server name from discovery."
                },
                "tool": {
                    "type": "string",
                    "description": "EXACT tool name from discovery (e.g., 'send_message', 'list_google_groups', 'list_channels'). Do not abbreviate or guess - use exact name from list_mcp_tools."
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
        "description": "Execute workflow with Executor Agent from scratch or resume a previous session. Returns detailed execution results. Sessions are automatically saved to the workflow's .sessions/ directory for potential resume. Input data is optional, but if not provided, you should warn the user before executing the workflow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_path": {
                    "type": "string",
                    "description": "Path to workflow.md file (e.g., './workflows/my_workflow/workflow.md')"
                },
                "input_data": {
                    "type": "string",
                    "description": "Optional input data for the workflow. Can be structured data (JSON, key-value pairs) or free-form text with context/variables the workflow needs (e.g., company details, IDs, configuration). If the user provided input files with @, include that content here."
                },
                "resume_session_id": {
                    "type": "string",
                    "description": "Optional: Session ID to resume from a previous execution. Use list_executor_sessions() to see available sessions. If provided, continues from where that session left off."
                }
            },
            "required": ["workflow_path"]
        }
    },
    {
        "name": "list_executor_sessions",
        "description": "List saved executor sessions for a workflow. Shows session history including status, step counts, and whether clarification is needed. Use this to see what sessions can be resumed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_path": {
                    "type": "string",
                    "description": "Path to workflow.md file"
                }
            },
            "required": ["workflow_path"]
        }
    },
    {
        "name": "load_executor_session",
        "description": "Load full details of a saved executor session. Use this to inspect what happened in a previous execution, including all steps, results, errors, and clarification requests.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_path": {
                    "type": "string",
                    "description": "Path to workflow.md file"
                },
                "session_id": {
                    "type": "string",
                    "description": "Session ID to load (from list_executor_sessions)"
                }
            },
            "required": ["workflow_path", "session_id"]
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
