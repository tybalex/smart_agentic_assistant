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
from .tools import AVAILABLE_TOOLS

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
        Process user message and respond.
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
        
        # Add tools description to system prompt
        tools_desc = self._format_tools_description()
        system_prompt = MAIN_AGENT_SYSTEM_PROMPT + "\n\n" + tools_desc
        
        # Call Claude
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
                messages=messages
            )
            
            assistant_text = response.content[0].text
            
            # Check if response contains JSON (tool call or message)
            parsed_response = self._parse_response(assistant_text)
            
            if parsed_response and parsed_response.get("action") == "call_tool":
                # Tool call - execute it
                tool_call = {
                    "tool": parsed_response.get("tool"),
                    "arguments": parsed_response.get("arguments", {})
                }
                
                # Show tool call in dev mode
                if self.dev_mode:
                    self._print_dev_tool_call(tool_call)
                else:
                    # In non-dev mode, show simple message for user feedback
                    # Especially important for long-running tools like execute_workflow
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
                
                # Add tool call and result to conversation
                # Use a description of the tool call as assistant message
                tool_call_desc = f"Calling tool: {tool_call['tool']}"
                tool_result_msg = f"Tool Result:\n{json.dumps(result, indent=2)}"
                
                messages.append({
                    "role": "assistant",
                    "content": tool_call_desc
                })
                messages.append({
                    "role": "user",
                    "content": tool_result_msg
                })
                
                # Continue loop to let agent use the result
                continue
            
            elif parsed_response and parsed_response.get("action") == "message":
                # Message response - extract content
                response_text = parsed_response.get("content", assistant_text)
                break
            
            else:
                # No structured response, return as-is
                response_text = assistant_text
                break
        
        # Save assistant message with tool calls/results
        self.session.add_assistant_message(
            content=response_text,
            tool_calls=tool_calls_made,
            tool_results=tool_results
        )
        
        return response_text
    
    def _format_tools_description(self) -> str:
        """Format available tools for system prompt"""
        lines = ["## AVAILABLE TOOLS\n"]
        for tool_name, tool_info in AVAILABLE_TOOLS.items():
            lines.append(f"### {tool_name}")
            lines.append(f"Description: {tool_info['description']}")
            if tool_info['parameters']:
                lines.append("Parameters:")
                for param, desc in tool_info['parameters'].items():
                    lines.append(f"  - {param}: {desc}")
            lines.append("")
        return "\n".join(lines)
    
    def _parse_response(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Parse structured JSON response from agent.
        Handles both tool calls and message responses.
        """
        try:
            # Remove markdown code blocks if present
            text = text.strip()
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                if end != -1:
                    text = text[start:end].strip()
            elif text.startswith("```") and text.endswith("```"):
                # Generic code block
                lines = text.split('\n')
                text = '\n'.join(lines[1:-1])
            
            # Try to find JSON in text
            start = text.find('{')
            if start == -1:
                return None
            
            # Find matching brace
            brace_count = 0
            end = start
            for i, char in enumerate(text[start:], start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end = i + 1
                        break
            
            json_str = text[start:end]
            data = json.loads(json_str)
            
            return data
            
        except Exception as e:
            # Not valid JSON, return None
            return None
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool function"""
        if tool_name not in AVAILABLE_TOOLS:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }
        
        try:
            tool_func = AVAILABLE_TOOLS[tool_name]["function"]
            
            # Check if async
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**arguments)
            else:
                result = tool_func(**arguments)
            
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
