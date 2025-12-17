"""
Main Agent - Conversational workflow development assistant
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from anthropic import Anthropic

from .prompts import MAIN_AGENT_SYSTEM_PROMPT
from .session import WorkflowSession, Message
from .tools import AVAILABLE_TOOLS, ANTHROPIC_TOOLS

# Suppress verbose httpx logging
logging.getLogger("httpx").setLevel(logging.ERROR)


class MainAgent:
    """
    Main Agent helps users write and improve workflows through conversation.
    Similar to Claude Code, but for workflows instead of code.
    """
    
    def __init__(self, model: str = "claude-sonnet-4-20250514", dev_mode: bool = False):
        """Initialize Main Agent"""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.session: Optional[WorkflowSession] = None
        self.dev_mode = dev_mode
        
        # Color codes for dev mode
        self.COLOR_TOOL = '\033[96m'      # Cyan
        self.COLOR_RESULT = '\033[93m'    # Yellow
        self.COLOR_SUCCESS = '\033[92m'   # Green
        self.COLOR_ERROR = '\033[91m'     # Red
        self.COLOR_RESET = '\033[0m'      # Reset
        self.COLOR_BOLD = '\033[1m'       # Bold
    
    def start_session(self, workflow_name: str) -> WorkflowSession:
        """Start a new workflow development session"""
        self.session = WorkflowSession(workflow_name=workflow_name)
        return self.session
    
    async def chat(self, user_message: str) -> str:
        """
        Process user message and respond using native Anthropic tool calling.
        May call tools autonomously to accomplish tasks.
        
        Args:
            user_message: User's input
        
        Returns:
            Assistant's response
        """
        if not self.session:
            self.start_session("default")
        
        # Add user message to session
        self.session.add_user_message(user_message)
        
        # Build conversation context
        messages = self.session.get_conversation_context()
        
        # Add session context to help agent avoid redundant actions
        session_context = self._format_session_context()
        system_prompt = MAIN_AGENT_SYSTEM_PROMPT + "\n\n" + session_context
        
        # Track tool calls and results
        response_text = ""
        tool_calls_made = []
        tool_results = []
        
        # Allow multiple tool calls in a row
        max_tool_rounds = 5
        for round_num in range(max_tool_rounds):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                temperature=0.1,
                system=system_prompt,
                messages=messages,
                tools=ANTHROPIC_TOOLS  # Native tool calling!
            )
            
            # Debug in dev mode
            if self.dev_mode:
                print(f"\n{self.COLOR_TOOL}📝 Stop Reason: {response.stop_reason}{self.COLOR_RESET}")
            
            # Check if model wants to use tools
            if response.stop_reason == "tool_use":
                # Extract all tool uses from response
                assistant_content = []
                tool_uses = []
                
                for block in response.content:
                    if block.type == "text":
                        assistant_content.append(block)
                    elif block.type == "tool_use":
                        tool_uses.append(block)
                        assistant_content.append(block)
                
                # Execute each tool
                tool_results_content = []
                for tool_use in tool_uses:
                    tool_call = {
                        "tool": tool_use.name,
                        "arguments": tool_use.input,
                        "id": tool_use.id
                    }
                    
                    # Show tool call in dev mode
                    if self.dev_mode:
                        self._print_dev_tool_call(tool_call)
                    else:
                        # In non-dev mode, show simple message for long-running tools
                        if tool_call["tool"] == "execute_workflow":
                            print()
                            print("🔄 Executing workflow (this may take a moment)...")
                    
                    # Execute tool
                    result = await self._execute_tool(
                        tool_call["tool"],
                        tool_call.get("arguments", {})
                    )
                    
                    # Show result in dev mode
                    if self.dev_mode:
                        self._print_dev_tool_result(tool_call["tool"], result)
                    
                    tool_calls_made.append(tool_call)
                    tool_results.append(result)
                    
                    # Format tool result for API
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result)
                    })
                
                # Add assistant message with tool uses
                messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })
                
                # Add tool results
                messages.append({
                    "role": "user",
                    "content": tool_results_content
                })
                
                # Continue loop to let agent use the results
                continue
            
            else:
                # Final response - extract text
                for block in response.content:
                    if block.type == "text":
                        response_text = block.text
                        break
                break
        
        # Save assistant message with tool calls/results
        self.session.add_assistant_message(
            content=response_text,
            tool_calls=tool_calls_made,
            tool_results=tool_results
        )
        
        return response_text
    
    
    def _format_session_context(self) -> str:
        """Format current session state to help agent avoid redundant actions"""
        if not self.session:
            return ""
        
        lines = ["## CURRENT SESSION STATE\n"]
        
        # MCP Tools discovered
        if self.session.available_tools:
            lines.append("✅ MCP tools already discovered - DON'T call discover_mcp_tools() again!")
            lines.append(f"   Available: {len(self.session.available_tools.get('tools', []))} MCP tools")
        else:
            lines.append("❌ MCP tools not yet discovered - call discover_mcp_tools() first")
        
        # Workflow path
        if self.session.workflow_path:
            lines.append(f"✅ Workflow exists: {self.session.workflow_path}")
        else:
            lines.append("❌ No workflow created yet")
        
        # MCP Tools selected
        if self.session.selected_tools:
            lines.append(f"✅ MCP tools selected: {len(self.session.selected_tools)} tools")
        else:
            lines.append("❌ No MCP tools selected yet")
        
        # Executions
        if self.session.execution_attempts:
            last = self.session.get_last_execution()
            lines.append(f"📊 Executions: {len(self.session.execution_attempts)}, Last status: {last.status}")
        
        lines.append("")
        return "\n".join(lines)
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool function and update session state"""
        if tool_name not in AVAILABLE_TOOLS:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
        
        try:
            tool_func = AVAILABLE_TOOLS[tool_name]
            
            # Filter arguments to only include what the function accepts
            import inspect
            sig = inspect.signature(tool_func)
            valid_params = set(sig.parameters.keys())
            
            # Filter arguments to only valid parameters
            filtered_args = {k: v for k, v in arguments.items() if k in valid_params}
            
            # Check if async
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**filtered_args)
            else:
                result = tool_func(**filtered_args)
            
            # Update session state based on tool results
            if self.session and result.get("success"):
                if tool_name == "discover_mcp_tools":
                    self.session.available_tools = result
                elif tool_name == "write_workflow":
                    self.session.workflow_path = result.get("path")
                elif tool_name == "select_mcp_tools":
                    self.session.selected_tools = arguments.get("tool_list", [])
                    self.session.tools_path = result.get("tools_path")
                elif tool_name == "execute_workflow":
                    self.session.add_execution_attempt(
                        status=result.get("status", "unknown"),
                        trace=result
                    )
            
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_session_summary(self) -> str:
        """Get current session summary"""
        if not self.session:
            return "No active session"
        return self.session.summary()
    
    def _print_dev_tool_call(self, tool_call: Dict[str, Any]):
        """Print tool call in dev mode with colors"""
        print()
        print(f"{self.COLOR_BOLD}{self.COLOR_TOOL}🔧 Tool Call:{self.COLOR_RESET}")
        print(f"{self.COLOR_TOOL}   Tool: {tool_call['tool']}{self.COLOR_RESET}")
        
        if tool_call.get('arguments'):
            print(f"{self.COLOR_TOOL}   Arguments:{self.COLOR_RESET}")
            for key, value in tool_call['arguments'].items():
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                print(f"{self.COLOR_TOOL}     {key}: {value_str}{self.COLOR_RESET}")
        print()
    
    def _print_dev_tool_result(self, tool_name: str, result: Dict[str, Any]):
        """Print tool result in dev mode with colors"""
        success = result.get("success", False)
        color = self.COLOR_SUCCESS if success else self.COLOR_ERROR
        status = "✅ Success" if success else "❌ Failed"
        
        print(f"{self.COLOR_BOLD}{color}📊 Tool Result ({tool_name}): {status}{self.COLOR_RESET}")
        
        # Show key result fields
        if "error" in result:
            print(f"{self.COLOR_ERROR}   Error: {result['error']}{self.COLOR_RESET}")
        
        # Show other interesting fields (skip internal ones)
        skip_keys = {"success", "error", "trace", "content"}
        for key, value in result.items():
            if key not in skip_keys:
                value_str = str(value)
                if len(value_str) > 150:
                    value_str = value_str[:150] + "..."
                print(f"{color}   {key}: {value_str}{self.COLOR_RESET}")
        
        print(f"{self.COLOR_RESULT}{'─' * 80}{self.COLOR_RESET}")
        print()
