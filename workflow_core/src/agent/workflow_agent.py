"""
Workflow Agent

An AI agent that masters workflows through tool use.
The agent can create, modify, test, and improve workflows autonomously.
"""

import json
import os
from typing import List, Dict, Any, Optional
from anthropic import Anthropic

from .tools import WorkflowTools, TOOL_DEFINITIONS
from .prompts import AGENT_SYSTEM_PROMPT


class WorkflowAgent:
    """
    An agentic workflow assistant powered by Claude.
    
    The agent has access to tools and decides how to accomplish the user's goals.
    Instead of calling specific methods like generate_workflow(), the user just
    talks to the agent naturally and it figures out what tools to use.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-5-20250929",  # Use latest Claude Sonnet
        workspace_dir: str = "."
    ):
        """
        Initialize the workflow agent.
        
        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)
            model: Model to use
            workspace_dir: Directory where workflow files are saved
        """
        self.client = Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            timeout=600.0
        )
        self.model = model
        self.tools = WorkflowTools(workspace_dir)
        self.conversation_history: List[Dict[str, Any]] = []
    
    def chat(self, user_message: str, max_turns: int = 50) -> str:
        """
        Send a message to the agent and get a response.
        
        The agent will use tools as needed to accomplish the task.
        
        Args:
            user_message: What the user wants
            max_turns: Maximum number of tool-use turns (prevents infinite loops)
        
        Returns:
            The agent's final response
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        turn_count = 0
        
        while turn_count < max_turns:
            turn_count += 1
            
            # Call Claude with tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=64000,
                system=AGENT_SYSTEM_PROMPT,
                messages=self.conversation_history,
                tools=TOOL_DEFINITIONS
            )
            
            # Add assistant response to history
            assistant_message = {
                "role": "assistant",
                "content": response.content
            }
            self.conversation_history.append(assistant_message)
            
            # Check if we need to process tool calls
            if response.stop_reason == "tool_use":
                # Process all tool calls
                tool_results = []
                
                for content_block in response.content:
                    if content_block.type == "tool_use":
                        tool_name = content_block.name
                        tool_input = content_block.input
                        tool_use_id = content_block.id
                        
                        print(f"🔧 Agent using tool: {tool_name}")
                        
                        # Execute the tool
                        result = self._execute_tool(tool_name, tool_input)
                        
                        # Convert result to JSON-safe format
                        try:
                            result_json = json.dumps(result)
                        except TypeError as e:
                            # Handle non-serializable objects
                            print(f"Tool returned non-serializable result: {str(result)}")
                            result_json = json.dumps({
                                "status": "error",
                                "message": f"Tool returned non-serializable result: {str(e)}",
                                "result_str": str(result)
                            })
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": result_json
                        })
                
                # Add tool results to conversation
                if tool_results:
                    self.conversation_history.append({
                        "role": "user",
                        "content": tool_results
                    })
                    # Continue the loop to get the next response
                    continue
            
            # If we got here, the agent is done (no more tools to use)
            # Extract the text response
            final_text = ""
            for content_block in response.content:
                if hasattr(content_block, "text"):
                    final_text += content_block.text
            
            return final_text
        
        return "⚠️ Agent reached maximum tool use turns. Try breaking your request into smaller steps."
    
    def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return its result"""
        try:
            # Get the tool method
            tool_method = getattr(self.tools, tool_name)
            
            # Call it with the input
            result = tool_method(**tool_input)
            
            return result
            
        except AttributeError:
            return {
                "status": "error",
                "message": f"Tool '{tool_name}' not found"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Tool execution failed: {str(e)}"
            }
    
    def reset_conversation(self):
        """Reset conversation history (start fresh)"""
        self.conversation_history = []
        print("🔄 Conversation reset")
    
    def get_current_workflow(self):
        """Get the current workflow the agent is working with"""
        return self.tools.current_workflow
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the conversation so far"""
        summary = []
        for msg in self.conversation_history:
            if msg["role"] == "user":
                if isinstance(msg["content"], str):
                    summary.append(f"User: {msg['content'][:100]}...")
                else:
                    summary.append("User: [tool results]")
            else:
                # Extract text from assistant message
                text = ""
                if isinstance(msg["content"], list):
                    for block in msg["content"]:
                        if hasattr(block, "text"):
                            text += block.text[:100]
                        elif isinstance(block, dict) and "text" in block:
                            text += block["text"][:100]
                if text:
                    summary.append(f"Assistant: {text}...")
        
        return "\n".join(summary)
