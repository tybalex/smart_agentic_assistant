"""
Main Agent - Conversational workflow development assistant
"""

import os
import json
import asyncio
import logging
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from anthropic import Anthropic

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import (
    MAX_TOOL_ROUNDS,
    MAX_TOKENS_PER_REQUEST,
    AGENT_TEMPERATURE,
    TOOL_RESULT_SHORT_DISPLAY_LENGTH,
    TOOL_RESULT_FULL_DISPLAY_LENGTH
)
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
    
    async def chat(self, user_message: str) -> Dict[str, Any]:
        """
        Process user message and respond using native Anthropic tool calling.
        Returns either a text response OR tool calls pending approval.
        
        Args:
            user_message: User's input
        
        Returns:
            Dict with either:
            - {"type": "text", "content": str} - Final text response
            - {"type": "tool_calls", "content": str, "tool_calls": [...], "assistant_content": [...]} - Tool calls awaiting approval
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
        
        # Use streaming for large token requests
        with self.client.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS_PER_REQUEST,
            temperature=AGENT_TEMPERATURE,
            system=system_prompt,
            messages=messages,
            tools=ANTHROPIC_TOOLS,
        ) as stream:
            response = stream.get_final_message()
        
        # Debug in dev mode
        if self.dev_mode:
            print(f"\n{self.COLOR_TOOL}📝 Stop Reason: {response.stop_reason}{self.COLOR_RESET}")
        
        # Check if model wants to use tools
        if response.stop_reason == "tool_use":
            # Extract text and tool uses from response
            text_content = ""
            tool_uses = []
            assistant_content = []
            
            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                    assistant_content.append(block)
                elif block.type == "tool_use":
                    tool_uses.append(block)
                    assistant_content.append(block)
            
            # Format tool calls for approval
            tool_calls = []
            for tool_use in tool_uses:
                tool_calls.append({
                    "tool": tool_use.name,
                    "arguments": tool_use.input,
                    "id": tool_use.id
                })
            
            # Store the assistant content in session for later continuation
            self.session.pending_assistant_content = assistant_content
            
            # Return tool calls for approval
            return {
                "type": "tool_calls",
                "content": text_content,
                "tool_calls": tool_calls
            }
        
        else:
            # Final text response
            response_text = ""
            for block in response.content:
                if block.type == "text":
                    response_text = block.text
                    break
            
            # Save assistant message
            self.session.add_assistant_message(
                content=response_text,
                tool_calls=[],
                tool_results=[]
            )
            
            return {
                "type": "text",
                "content": response_text
            }
    
    async def continue_with_tool_results(self, approved_tools: List[Dict[str, Any]], rejected_tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Continue conversation after user approves/rejects tool calls.
        
        Args:
            approved_tools: List of tool calls that were approved (with "tool", "arguments", "id")
            rejected_tools: List of tool calls that were rejected (with "tool", "arguments", "id", "feedback")
        
        Returns:
            Dict like chat() - either text response or more tool calls
        """
        if not self.session.pending_assistant_content:
            return {
                "type": "text",
                "content": "Error: No pending tool calls to process."
            }
        
        # Build conversation context
        messages = self.session.get_conversation_context()
        
        # Add the assistant message with tool uses
        messages.append({
            "role": "assistant",
            "content": self.session.pending_assistant_content
        })
        
        # Execute approved tools and format results
        tool_results_content = []
        executed_tools = []
        executed_results = []
        
        for tool_call in approved_tools:
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
            
            executed_tools.append(tool_call)
            executed_results.append(result)
            
            # Format for API
            tool_results_content.append({
                "type": "tool_result",
                "tool_use_id": tool_call["id"],
                "content": json.dumps(result)
            })
        
        # Add rejection messages for rejected tools
        for tool_call in rejected_tools:
            feedback = tool_call.get("feedback", "User rejected this tool call")
            tool_results_content.append({
                "type": "tool_result",
                "tool_use_id": tool_call["id"],
                "content": json.dumps({
                    "success": False,
                    "error": f"Tool call rejected by user: {feedback}"
                }),
                "is_error": True
            })
        
        # Add tool results to messages
        messages.append({
            "role": "user",
            "content": tool_results_content
        })
        
        # Clear pending state
        self.session.pending_assistant_content = None
        
        # Get next response from model
        session_context = self._format_session_context()
        system_prompt = MAIN_AGENT_SYSTEM_PROMPT + "\n\n" + session_context
        
        with self.client.messages.stream(
            model=self.model,
            max_tokens=MAX_TOKENS_PER_REQUEST,
            temperature=AGENT_TEMPERATURE,
            system=system_prompt,
            messages=messages,
            tools=ANTHROPIC_TOOLS,
        ) as stream:
            response = stream.get_final_message()
        
        # Check if model wants more tools
        if response.stop_reason == "tool_use":
            # Extract text and tool uses
            text_content = ""
            tool_uses = []
            assistant_content = []
            
            for block in response.content:
                if block.type == "text":
                    text_content += block.text
                    assistant_content.append(block)
                elif block.type == "tool_use":
                    tool_uses.append(block)
                    assistant_content.append(block)
            
            # Format tool calls
            tool_calls = []
            for tool_use in tool_uses:
                tool_calls.append({
                    "tool": tool_use.name,
                    "arguments": tool_use.input,
                    "id": tool_use.id
                })
            
            # Store pending state
            self.session.pending_assistant_content = assistant_content
            
            # Return for approval
            return {
                "type": "tool_calls",
                "content": text_content,
                "tool_calls": tool_calls
            }
        
        else:
            # Final response
            response_text = ""
            for block in response.content:
                if block.type == "text":
                    response_text = block.text
                    break
            
            # Save to session
            self.session.add_assistant_message(
                content=response_text,
                tool_calls=executed_tools,
                tool_results=executed_results
            )
            
            return {
                "type": "text",
                "content": response_text
            }
    
    
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
                if len(value_str) > TOOL_RESULT_SHORT_DISPLAY_LENGTH:
                    value_str = value_str[:TOOL_RESULT_SHORT_DISPLAY_LENGTH] + "..."
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
                if len(value_str) > TOOL_RESULT_FULL_DISPLAY_LENGTH:
                    value_str = value_str[:TOOL_RESULT_FULL_DISPLAY_LENGTH] + "..."
                print(f"{color}   {key}: {value_str}{self.COLOR_RESET}")
        
        print(f"{self.COLOR_RESULT}{'─' * 80}{self.COLOR_RESET}")
        print()
