"""
Tool functions available to Main Agent
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.mcp_registry import create_registry_from_config
from executor.executor_agent import ExecutorAgent
from executor.models import ToolConfig, ExecutionTrace


# Global registry cache (initialized once per session)
_registry_cache = None
_discovered_tools_cache = None


async def discover_tools() -> Dict[str, Any]:
    """
    Discover all available MCP tools from configured servers.
    
    Returns:
        Dict with: {
            "success": bool,
            "servers": List[str],
            "tools": List[{server, tool, description}],
            "total": int
        }
    """
    global _registry_cache, _discovered_tools_cache
    
    try:
        # Use cached if available
        if _discovered_tools_cache:
            return _discovered_tools_cache
        
        # Create registry if needed
        if not _registry_cache:
            _registry_cache = await create_registry_from_config()
        
        # Discover all tools
        tools_by_server = await _registry_cache.discover_all_tools()
        
        # Flatten to simple list
        all_tools = []
        for server, tools in tools_by_server.items():
            for tool in tools:
                all_tools.append({
                    "server": server,
                    "tool": tool["tool"],
                    "description": tool["description"]
                })
        
        result = {
            "success": True,
            "servers": list(tools_by_server.keys()),
            "tools": all_tools,
            "total": len(all_tools)
        }
        
        # Cache for session
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


def select_tools(workflow_path: str, tool_list: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Select tools for workflow and save to tools.json in same directory.
    
    Args:
        workflow_path: Path to workflow.md
        tool_list: List of {server, tool} dicts to include
    
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
        
        # Create tools.json format
        tools_config = {
            "mcp_servers": servers,
            "tools": [
                {
                    "server": t["server"],
                    "tool": t["tool"],
                    "description": t.get("description", "")
                }
                for t in tool_list
            ],
            "version": "1.0"
        }
        
        # Save file
        with open(tools_path, 'w') as f:
            json.dump(tools_config, f, indent=2)
        
        return {
            "success": True,
            "tools_path": str(tools_path.absolute()),
            "selected_count": len(tool_list),
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
        
        # Create and run executor
        print("⏳ Executing workflow with Executor Agent...")
        executor = ExecutorAgent(tool_executor=mock_executor)
        trace = executor.execute_workflow(
            workflow_path=str(workflow_file),
            tools_config=tools_config,
            workflow_content=workflow_content
        )
        print("✅ Workflow execution completed")
        
        # Check if execution was successful
        from executor.models import SessionStatus
        success = trace.status == SessionStatus.COMPLETED
        
        # Build result with meaningful information
        result = {
            "success": success,
            "status": trace.status.value,
            "session_id": trace.session_id,
            "total_steps": len(trace.steps),
            "completed_steps": sum(1 for s in trace.steps if s.success),
            "failed_steps": sum(1 for s in trace.steps if not s.success),
            "total_tokens": trace.total_tokens_used,
            "error_message": trace.error_message if trace.error_message else None,
            "trace_summary": f"Executed {len(trace.steps)} steps, {sum(1 for s in trace.steps if s.success)} succeeded"
        }
        
        # Include full trace in result for detailed inspection
        if not success:
            result["details"] = "Workflow execution incomplete or failed. Check error_message and failed_steps."
            # Include last few steps for debugging
            if trace.steps:
                result["last_steps"] = [
                    {
                        "step": s.step_number,
                        "description": s.description[:100] if s.description else "N/A",
                        "success": s.success,
                        "error": s.error_message
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
        directory: Directory to search (default: ./workflows)
    
    Returns:
        Dict with: {success: bool, workflows: List[{path, name, directory}]}
    """
    try:
        if directory is None:
            directory = "./workflows"
        
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


# Tool registry for Main Agent
AVAILABLE_TOOLS = {
    "discover_tools": {
        "function": discover_tools,
        "description": "Discover all available MCP tools from configured servers",
        "parameters": {}
    },
    "read_workflow": {
        "function": read_workflow,
        "description": "Read a workflow.md file",
        "parameters": {
            "path": "Path to workflow.md file"
        }
    },
    "write_workflow": {
        "function": write_workflow,
        "description": "Write/update a workflow.md file in a subdirectory",
        "parameters": {
            "path": "Path like './workflows/my_workflow' (will create workflow.md inside)",
            "content": "Workflow content in markdown"
        }
    },
    "select_tools": {
        "function": select_tools,
        "description": "Select tools for workflow and generate tools.json",
        "parameters": {
            "workflow_path": "Path to workflow.md",
            "tool_list": "List of {server, tool} dicts"
        }
    },
    "execute_workflow": {
        "function": execute_workflow,
        "description": "Execute workflow and return detailed execution status (success/fail, step counts, errors)",
        "parameters": {
            "workflow_path": "Path to workflow.md file (e.g., './workflows/my_workflow/workflow.md')"
        }
    },
    "list_workflows": {
        "function": list_workflows,
        "description": "List existing workflows in directory",
        "parameters": {
            "directory": "Directory to search (optional, default: ./workflows)"
        }
    }
}
