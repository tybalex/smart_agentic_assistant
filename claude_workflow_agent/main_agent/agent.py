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
    CLAUDE_MODEL,
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
    
    def __init__(self, model: str = None, dev_mode: bool = False):
        """Initialize Main Agent"""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=api_key)
        self.model = model or CLAUDE_MODEL
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
    
    def _requires_approval(self, tool_name: str) -> bool:
        """
        Check if a tool requires user approval before execution.
        
        Read/list operations auto-execute for better UX.
        Write/action operations require approval.
        """
        # Tools that auto-execute (read/list operations)
        AUTO_EXECUTE_TOOLS = {
            "list_mcp_servers",
            "list_mcp_tools",
            "read_workflow",
            "list_workflows",
            "list_executor_sessions",
            "inspect_executor_session"  # Returns summary only, not full history
        }
        
        return tool_name not in AUTO_EXECUTE_TOOLS
    
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
            
            # Split tools into auto-execute and needs-approval
            auto_execute = []
            needs_approval = []
            
            for tool_use in tool_uses:
                if self._requires_approval(tool_use.name):
                    needs_approval.append(tool_use)
                else:
                    auto_execute.append(tool_use)
            
            # Auto-execute read/list tools
            if auto_execute:
                # Add assistant message to conversation
                messages.append({
                    "role": "assistant",
                    "content": assistant_content
                })
                
                # CRITICAL: Save assistant message with tool_use blocks to session
                self.session.add_assistant_message(
                    content=assistant_content  # Contains tool_use blocks
                )
                
                # Execute auto tools and collect results
                tool_results_content = []
                executed_tools = []
                executed_results = []
                
                for tool_use in auto_execute:
                    # Show in dev mode
                    if self.dev_mode:
                        self._print_dev_tool_call({
                            "tool": tool_use.name,
                            "arguments": tool_use.input,
                            "id": tool_use.id
                        })
                    
                    # Execute tool
                    result = await self._execute_tool(tool_use.name, tool_use.input)
                    
                    # Show result in dev mode
                    if self.dev_mode:
                        self._print_dev_tool_result(tool_use.name, result)
                    
                    executed_tools.append({
                        "tool": tool_use.name,
                        "arguments": tool_use.input,
                        "id": tool_use.id
                    })
                    executed_results.append(result)
                    
                    # Format for API
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result)
                    })
                
                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results_content
                })
                
                # CRITICAL: Save user message with tool_result blocks to session
                self.session.add_user_message(
                    content=tool_results_content  # Contains tool_result blocks
                )
                
                # If there are tools needing approval, store state and return them
                if needs_approval:
                    # Store the state but with only approval-required tools
                    approval_assistant_content = []
                    for block in assistant_content:
                        if block.type == "text":
                            approval_assistant_content.append(block)
                        elif block.type == "tool_use" and any(t.id == block.id for t in needs_approval):
                            approval_assistant_content.append(block)
                    
                    self.session.pending_assistant_content = approval_assistant_content
                    
                    # Format tool calls for approval
                    tool_calls = []
                    for tool_use in needs_approval:
                        tool_calls.append({
                            "tool": tool_use.name,
                            "arguments": tool_use.input,
                            "id": tool_use.id
                        })
                    
                    return {
                        "type": "tool_calls",
                        "content": text_content,
                        "tool_calls": tool_calls
                    }
                
                # All tools were auto-executed, continue conversation
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
                    next_response = stream.get_final_message()
                
                # Process the next response recursively
                # Check if it has more tool calls
                if next_response.stop_reason == "tool_use":
                    # Extract and handle new tool calls
                    new_text = ""
                    new_tool_uses = []
                    new_assistant_content = []
                    
                    for block in next_response.content:
                        if block.type == "text":
                            new_text += block.text
                            new_assistant_content.append(block)
                        elif block.type == "tool_use":
                            new_tool_uses.append(block)
                            new_assistant_content.append(block)
                    
                    # Check if any need approval
                    new_needs_approval = [t for t in new_tool_uses if self._requires_approval(t.name)]
                    
                    if new_needs_approval:
                        self.session.pending_assistant_content = new_assistant_content
                        
                        tool_calls = []
                        for tool_use in new_needs_approval:
                            tool_calls.append({
                                "tool": tool_use.name,
                                "arguments": tool_use.input,
                                "id": tool_use.id
                            })
                        
                        # Note: Auto-executed tools were already saved to session above (lines 156 & 202)
                        # The new assistant message with approval-required tools will be saved when user approves
                        
                        return {
                            "type": "tool_calls",
                            "content": new_text,
                            "tool_calls": tool_calls
                        }
                    
                    # More auto tools - would need recursive handling
                    # For simplicity, fall through to text response
                
                # Final text response
                response_text = ""
                for block in next_response.content:
                    if block.type == "text":
                        response_text = block.text
                        break
                
                # Save final assistant text response to session
                # Note: Auto-executed tool_use and tool_result blocks were already saved above
                self.session.add_assistant_message(
                    content=response_text
                )
                
                return {
                    "type": "text",
                    "content": response_text
                }
            
            else:
                # Only approval-required tools
                # Format tool calls for approval
                tool_calls = []
                for tool_use in needs_approval:
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
        
        # Add the assistant message with tool uses to both API messages and session
        messages.append({
            "role": "assistant",
            "content": self.session.pending_assistant_content
        })
        
        # CRITICAL: Save assistant message with tool_use blocks to session
        self.session.add_assistant_message(
            content=self.session.pending_assistant_content  # Contains tool_use blocks
        )
        
        # Execute approved tools and format results
        tool_results_content = []
        executed_tools = []
        executed_results = []
        
        # First, add any auto-executed tool results from the same response
        if hasattr(self.session, 'pending_auto_results') and self.session.pending_auto_results:
            tool_results_content.extend(self.session.pending_auto_results)
            self.session.pending_auto_results = None  # Clear after using
        
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
        
        # CRITICAL: Save user message with tool_result blocks to session
        self.session.add_user_message(
            content=tool_results_content  # Contains tool_result blocks
        )
        
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
            
            # Split tools into auto-execute and needs-approval
            auto_execute = []
            needs_approval = []
            
            for tool_use in tool_uses:
                if self._requires_approval(tool_use.name):
                    needs_approval.append(tool_use)
                else:
                    auto_execute.append(tool_use)
            
            # If no auto-execute tools, just return approval-required ones
            if not auto_execute:
                # Format tool calls for approval
                tool_calls = []
                for tool_use in needs_approval:
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
            
            # If there are tools needing approval along with auto-execute tools
            # Execute auto tools first, store results, then return approval-required ones
            if needs_approval:
                # Execute auto tools first (without adding to messages yet)
                auto_tool_results = []
                for tool_use in auto_execute:
                    if self.dev_mode:
                        self._print_dev_tool_call({
                            "tool": tool_use.name,
                            "arguments": tool_use.input,
                            "id": tool_use.id
                        })
                    
                    result = await self._execute_tool(tool_use.name, tool_use.input)
                    
                    if self.dev_mode:
                        self._print_dev_tool_result(tool_use.name, result)
                    
                    auto_tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result)
                    })
                
                # Store FULL assistant content (including both auto and approval tools)
                # This will be added to messages when user approves
                self.session.pending_assistant_content = assistant_content
                self.session.pending_auto_results = auto_tool_results if auto_tool_results else None
                
                # Format tool calls for approval (only approval-required ones)
                tool_calls = []
                for tool_use in needs_approval:
                    tool_calls.append({
                        "tool": tool_use.name,
                        "arguments": tool_use.input,
                        "id": tool_use.id
                    })
                
                # Return for approval
                return {
                    "type": "tool_calls",
                    "content": text_content,
                    "tool_calls": tool_calls
                }
            
            # Only auto-execute tools - execute them automatically
            # Build new messages with assistant response
            messages.append({
                "role": "assistant",
                "content": assistant_content
            })
            
            # Execute auto tools
            auto_tool_results = []
            for tool_use in auto_execute:
                if self.dev_mode:
                    self._print_dev_tool_call({
                        "tool": tool_use.name,
                        "arguments": tool_use.input,
                        "id": tool_use.id
                    })
                
                result = await self._execute_tool(tool_use.name, tool_use.input)
                
                if self.dev_mode:
                    self._print_dev_tool_result(tool_use.name, result)
                
                auto_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": json.dumps(result)
                })
            
            # Add results to messages
            messages.append({
                "role": "user",
                "content": auto_tool_results
            })
            
            # Continue conversation
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
                final_response = stream.get_final_message()
            
            # Process final response (might have more tool calls)
            if final_response.stop_reason == "tool_use":
                # More tool calls - extract and check for approval
                new_text = ""
                new_tool_uses = []
                new_assistant_content = []
                
                for block in final_response.content:
                    if block.type == "text":
                        new_text += block.text
                        new_assistant_content.append(block)
                    elif block.type == "tool_use":
                        new_tool_uses.append(block)
                        new_assistant_content.append(block)
                
                # Check which need approval
                new_needs_approval = [t for t in new_tool_uses if self._requires_approval(t.name)]
                
                if new_needs_approval:
                    self.session.pending_assistant_content = new_assistant_content
                    
                    tool_calls = []
                    for tool_use in new_needs_approval:
                        tool_calls.append({
                            "tool": tool_use.name,
                            "arguments": tool_use.input,
                            "id": tool_use.id
                        })
                    
                    # Note: Tool_use and tool_result blocks were already saved above (lines 369 & 432)
                    # The new assistant message with approval-required tools will be saved when user approves
                    
                    return {
                        "type": "tool_calls",
                        "content": new_text,
                        "tool_calls": tool_calls
                    }
            
            # Final text response
            response_text = ""
            for block in final_response.content:
                if block.type == "text":
                    response_text = block.text
                    break
            
            # Save final assistant text response to session
            # Note: Tool_use and tool_result blocks were already saved above
            self.session.add_assistant_message(
                content=response_text
            )
            
            return {
                "type": "text",
                "content": response_text
            }
        
        else:
            # Final response
            response_text = ""
            for block in response.content:
                if block.type == "text":
                    response_text = block.text
                    break
            
            # Save final assistant text response to session
            # Note: Tool_use and tool_result blocks were already saved above
            self.session.add_assistant_message(
                content=response_text
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
        
        # MCP Tools discovered - Show actual list of available tools
        if self.session.available_tools:
            tools_list = self.session.available_tools.get('tools', [])
            lines.append(f"   Total: {len(tools_list)} tools from {len(self.session.available_tools.get('servers', []))} servers\n")
            
            # Group tools by server for easy reference
            lines.append("### AVAILABLE MCP TOOLS (use EXACT names when calling select_mcp_tools):\n")
            
            tools_by_server = {}
            for tool in tools_list:
                server = tool['server']
                if server not in tools_by_server:
                    tools_by_server[server] = []
                tools_by_server[server].append(tool['tool'])
            
            for server in sorted(tools_by_server.keys()):
                tool_names = sorted(tools_by_server[server])
                lines.append(f"**{server}** ({len(tool_names)} tools):")
                # Show tools in a compact format
                lines.append(f"  {', '.join(tool_names)}")
                lines.append("")
        else:
            lines.append("❌ MCP tools not yet listed - call list_mcp_tools() FIRST before select_mcp_tools()")
            lines.append("   You MUST list tools to know what tools exist - DO NOT GUESS tool names!\n")
        
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
                if tool_name == "list_mcp_tools":
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
