"""
Executor Agent - Runs workflow.md with scoped tools from tools.json
Simplified from task_agent - no UI, no dynamic discovery, fixed tool set.
"""

import os
import sys
import json
import logging
import asyncio
import inspect
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import CLAUDE_MODEL

from .models import (
    ExecutionTrace, StepExecution, ClarificationRequest,
    SessionStatus, ActionStatus, ToolConfig, TokenBudget
)

# Only show warnings by default (can be overridden)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for colored terminal output - Purple/Magenta theme for Executor"""
    # Main executor color - purple/magenta theme (distinct from Main Agent's cyan/yellow)
    EXECUTOR = '\033[35m'  # Magenta (dark purple)
    EXECUTOR_BRIGHT = '\033[95m'  # Bright magenta
    HEADER = '\033[95m'    # Bright magenta for headers
    SUCCESS = '\033[92m'   # Green (shared - universal success color)
    WARNING = '\033[94m'   # Blue (different from Main Agent's yellow)
    FAIL = '\033[91m'      # Red (shared - universal error color)
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RESET = '\033[0m'      # Reset to default
    
    @staticmethod
    def executor(text):
        """Wrap text in executor color (magenta)"""
        return f"{Colors.EXECUTOR}{text}{Colors.RESET}"
    
    @staticmethod
    def success(text):
        """Wrap text in success color (green - shared)"""
        return f"{Colors.SUCCESS}{text}{Colors.RESET}"
    
    @staticmethod
    def error(text):
        """Wrap text in error color (red - shared)"""
        return f"{Colors.FAIL}{text}{Colors.RESET}"
    
    @staticmethod
    def warning(text):
        """Wrap text in warning color (blue)"""
        return f"{Colors.WARNING}{text}{Colors.RESET}"
    
    @staticmethod
    def header(text):
        """Wrap text in header color (bright magenta + bold)"""
        return f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.RESET}"


class ExecutorAgent:
    """
    Executor Agent: Runs workflow.md files with validation.
    Tools are provided via tools.json - no dynamic discovery.
    """
    
    def __init__(
        self,
        tool_executor,  # Injected tool executor (will use MCPToolExecutor)
        model: str = None,
        verbose: bool = False  # Enable verbose output for dev mode
    ):
        self.tool_executor = tool_executor
        self.model = model or CLAUDE_MODEL
        self.verbose = verbose
        
        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=api_key)
        self.current_trace: Optional[ExecutionTrace] = None
        self.input_data: Optional[str] = None  # Will be set by execute_workflow
    
    def _convert_tools_to_anthropic_format(self, tools_config: ToolConfig) -> List[Dict[str, Any]]:
        """
        Convert MCP tools from tools.json to Anthropic's native tool format.
        
        Args:
            tools_config: Tool configuration from tools.json
        
        Returns:
            List of tool definitions in Anthropic format
        """
        anthropic_tools = []
        
        for tool in tools_config.tools:
            # Get schema from tool if available, otherwise use generic object
            input_schema = tool.get("input_schema", {
                "type": "object",
                "properties": {},
                "required": []
            })
            
            anthropic_tools.append({
                "name": f"{tool['server']}__{tool['tool']}",  # Unique name: server__tool
                "description": tool.get("description", f"Execute {tool['tool']} on {tool['server']}"),
                "input_schema": input_schema
            })
        
        # Add special control tools
        anthropic_tools.append({
            "name": "request_clarification",
            "description": "Request clarification from the user when you need more information to proceed",
            "input_schema": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user"
                    },
                    "context": {
                        "type": "string",
                        "description": "Why you need this information"
                    }
                },
                "required": ["question", "context"]
            }
        })
        
        anthropic_tools.append({
            "name": "mark_workflow_complete",
            "description": "Mark the workflow as complete when all steps are done and validated",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of what was accomplished"
                    }
                },
                "required": ["summary"]
            }
        })
        
        return anthropic_tools
    
    async def execute_workflow(
        self,
        workflow_path: str,
        tools_config: ToolConfig,
        workflow_content: Optional[str] = None,
        input_data: Optional[str] = None,
        previous_trace: Optional[Dict] = None
    ) -> ExecutionTrace:
        """
        Execute a workflow with scoped tools, optionally resuming from previous state.
        
        Args:
            workflow_path: Path to workflow.md file
            tools_config: Tool configuration from tools.json
            workflow_content: Optional pre-loaded workflow content (the workflow.md instructions)
            input_data: Optional input data/variables for the workflow (values to use)
            previous_trace: Optional previous execution trace to resume from
        
        Returns:
            ExecutionTrace with complete execution log
        """
        logger.info(f"Starting workflow execution: {workflow_path}")
        
        # Read workflow if not provided
        if workflow_content is None:
            with open(workflow_path, 'r') as f:
                workflow_content = f.read()
        
        # Initialize or restore trace and conversation history
        if previous_trace:
            # Resume from previous execution
            session_id = previous_trace.get("session_id", f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            # Restore message history
            raw_history = previous_trace.get("message_history", [])
            
            # IMPORTANT: Validate and clean message history
            # Remove any assistant messages with tool_use blocks that don't have ALL corresponding tool_results
            # This can happen if the session was saved right after a tool call but before adding the result
            cleaned_history = []
            skip_next_user = False
            
            for i, msg in enumerate(raw_history):
                # Skip user messages that were marked for removal
                if skip_next_user and msg.get("role") == "user":
                    skip_next_user = False
                    logger.warning(f"Removing orphaned user message at index {i}")
                    continue
                
                if msg.get("role") == "assistant":
                    # Check if this assistant message has tool_use blocks
                    content = msg.get("content", [])
                    if not isinstance(content, list):
                        # Old format or plain text - safe to keep
                        cleaned_history.append(msg)
                        continue
                    
                    # Extract all tool_use IDs from this assistant message
                    tool_use_ids = set()
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_use_ids.add(block.get("id"))
                    
                    if tool_use_ids:
                        # This assistant message has tool calls - verify ALL have results
                        if i + 1 < len(raw_history):
                            next_msg = raw_history[i + 1]
                            if next_msg.get("role") == "user":
                                next_content = next_msg.get("content", [])
                                if isinstance(next_content, list):
                                    # Extract all tool_result IDs
                                    tool_result_ids = set()
                                    for block in next_content:
                                        if isinstance(block, dict) and block.get("type") == "tool_result":
                                            tool_result_ids.add(block.get("tool_use_id"))
                                    
                                    # Check if ALL tool_use IDs have corresponding results
                                    if tool_use_ids.issubset(tool_result_ids):
                                        # All tool calls have results - keep both messages
                                        cleaned_history.append(msg)
                                        continue
                        
                        # Missing tool results - remove this assistant message
                        # and mark the next user message for removal if it exists
                        logger.warning(f"Removing incomplete assistant message at index {i} "
                                     f"(has {len(tool_use_ids)} tool_use blocks without complete tool_results)")
                        skip_next_user = True
                        continue
                    
                cleaned_history.append(msg)
            
            self.message_history = cleaned_history
            
            if len(cleaned_history) < len(raw_history):
                removed_count = len(raw_history) - len(cleaned_history)
                logger.warning(f"Cleaned message history: {len(raw_history)} -> {len(cleaned_history)} messages "
                             f"({removed_count} messages removed due to incomplete tool calls)")
                print(Colors.warning(f"⚠️  Cleaned up {removed_count} incomplete messages from saved session"))
            
            # Restore trace with previous steps
            self.current_trace = ExecutionTrace(
                workflow_path=workflow_path,
                session_id=session_id,
                start_time=previous_trace.get("start_time", datetime.now().isoformat()),
                status=SessionStatus.ACTIVE,
            )
            
            # Deserialize and restore previous steps
            for step_data in previous_trace.get("steps", []):
                step = StepExecution(
                    step_number=step_data["step_number"],
                    description=step_data.get("description", ""),
                    status=ActionStatus(step_data["status"]),
                    timestamp=step_data.get("timestamp", datetime.now().isoformat()),
                    reasoning=step_data.get("reasoning"),
                    tool_calls=step_data.get("tool_calls", []),
                    result=step_data.get("result"),
                    error=step_data.get("error")
                )
                self.current_trace.steps.append(step)
            
            # Restore clarification requests
            for cr_data in previous_trace.get("clarification_requests", []):
                cr = ClarificationRequest(
                    question=cr_data["question"],
                    context=cr_data.get("context", ""),
                    step_number=cr_data.get("step_number", 0)
                )
                self.current_trace.clarification_requests.append(cr)
            
            # Restore metadata
            self.input_data = previous_trace.get("input_data")
            starting_step = len(self.current_trace.steps) + 1
            
            print(Colors.header(f"\n{'='*80}"))
            print(Colors.header(f"🔄 EXECUTOR AGENT: RESUMING WORKFLOW EXECUTION"))
            print(Colors.header(f"{'='*80}"))
            print(Colors.executor(f"📁 Workflow: {workflow_path}"))
            print(Colors.executor(f"🔧 Tools: {len(tools_config.tools)} available"))
            print(Colors.executor(f"📂 Session: {session_id}"))
            print(Colors.executor(f"📊 Previous steps: {len(self.current_trace.steps)} completed"))
            print(Colors.executor(f"🎯 Resuming from step: {starting_step}"))
            if self.message_history:
                print(Colors.executor(f"💬 Conversation history: {len(self.message_history)} messages restored"))
            print(Colors.header(f"{'='*80}\n"))
            
        else:
            # Start fresh execution
            session_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.message_history = []  # Clear history for new execution
            
            self.current_trace = ExecutionTrace(
                workflow_path=workflow_path,
                session_id=session_id,
                start_time=datetime.now().isoformat(),
                status=SessionStatus.ACTIVE,
            )
            
            # Store input data for use in prompts
            self.input_data = input_data
            starting_step = 1
            
            # Always show execution start for new execution
            print(Colors.header(f"\n{'='*80}"))
            print(Colors.header(f"🚀 EXECUTOR AGENT: STARTING WORKFLOW EXECUTION"))
            print(Colors.header(f"{'='*80}"))
            print(Colors.executor(f"📁 Workflow: {workflow_path}"))
            print(Colors.executor(f"🔧 Tools: {len(tools_config.tools)} available"))
            if input_data:
                print(Colors.executor(f"📥 Input data provided: {len(input_data)} characters"))
            print(Colors.header(f"{'='*80}\n"))
        
        # Main execution loop
        step_number = starting_step
        max_steps = 50  # Safety limit
        budget = TokenBudget(max_tokens=180000)
        
        # If resuming, restore token budget (approximate based on message history)
        if previous_trace and self.message_history:
            # Estimate tokens used from previous messages
            estimated_tokens = sum(
                len(str(msg.get("content", ""))) // 4  # Rough estimate: 4 chars per token
                for msg in self.message_history
            )
            budget.used_tokens = estimated_tokens
            print(Colors.executor(f"📊 Token budget restored: ~{estimated_tokens} tokens used previously\n"))
        
        while step_number <= max_steps and not budget.exceeded:
            logger.info(f"Executing step {step_number}")
            
            # Always show step progress
            print(Colors.executor(f"\n{'─'*80}"))
            print(Colors.executor(f"📝 STEP {step_number}: Evaluating next action..."))
            print(Colors.executor(f"{'─'*80}"))
            
            # Call LLM to decide next action (now with streaming and real-time output)
            # Pass is_resuming=True only for the very first step after resume
            is_first_resumed_step = (previous_trace is not None and step_number == starting_step)
            evaluation = self._evaluate_next_step(
                workflow_content,
                tools_config,  # Pass tools_config instead of formatted string
                budget,
                is_resuming=is_first_resumed_step
            )
            
            # Check if goal achieved
            if evaluation.get("goal_achieved", False):
                logger.info("Workflow goal achieved")
                print(Colors.success(f"\n{'='*80}"))
                print(Colors.success(f"✅ EXECUTOR AGENT: WORKFLOW COMPLETE!"))
                print(Colors.success(f"{'='*80}"))
                print(Colors.success(f"📊 Summary: {evaluation.get('reasoning', 'Workflow completed successfully')}"))
                print(Colors.success(f"{'='*80}\n"))
                self.current_trace.status = SessionStatus.COMPLETED
                self.current_trace.final_summary = evaluation.get("reasoning", "Workflow completed successfully")
                break
            
            # Check for clarification request
            clarification = evaluation.get("clarification_request")
            if clarification:
                logger.info(f"Executor needs clarification: {clarification.get('question')}")
                print(Colors.warning(f"\n❓ EXECUTOR: CLARIFICATION NEEDED"))
                print(Colors.warning(f"   Question: {clarification.get('question')}"))
                print(Colors.warning(f"   Context: {clarification.get('context')}"))
                self.current_trace.clarification_requests.append(
                    ClarificationRequest(
                        question=clarification.get("question", ""),
                        context=clarification.get("context", ""),
                        step_number=step_number
                    )
                )
                self.current_trace.status = SessionStatus.NEEDS_CLARIFICATION
                break
            
            # Execute proposed action
            action = evaluation.get("next_action")
            if not action:
                logger.warning("No action proposed")
                print(Colors.error(f"\n❌ EXECUTOR ERROR: No action proposed by LLM"))
                self.current_trace.status = SessionStatus.FAILED
                self.current_trace.final_summary = evaluation.get("reasoning", "No action could be determined")
                break
            
            # Execute the action - always show what we're doing
            print(Colors.executor(f"\n🔧 Executing action:"))
            print(Colors.executor(f"   Tool: {action.get('tool_server')}/{action.get('tool_name')}"))
            desc = action.get('description', '')
            if desc and len(desc) > 150:
                desc = desc[:150] + "..."
            if desc:
                print(Colors.executor(f"   Description: {desc}"))
            params_str = json.dumps(action.get('parameters', {}), indent=2)
            if len(params_str) > 300:
                params_str = params_str[:300] + "..."
            print(Colors.executor(f"   Parameters: {params_str}"))
            
            step_exec = await self._execute_step(
                step_number,
                action,
                evaluation.get("reasoning", ""),
                budget
            )
            
            # Add tool result to message history for proper conversation continuity
            # This is critical for session restoration - ensures tool_use blocks have corresponding tool_result blocks
            tool_use_id = action.get("tool_use_id")
            if tool_use_id:
                # Format the result for Claude API
                if step_exec.status == ActionStatus.COMPLETED:
                    result_content = json.dumps(step_exec.result) if step_exec.result else "Success"
                else:
                    result_content = f"Error: {step_exec.error}" if step_exec.error else "Failed"
                
                self.message_history.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result_content
                    }]
                })
            
            # Always show step results
            status_icon = {
                ActionStatus.COMPLETED: "✅",
                ActionStatus.FAILED: "❌",
                ActionStatus.PENDING: "⏳",
                ActionStatus.SKIPPED: "⊘"
            }.get(step_exec.status, "❓")
            
            # Use different color based on status
            if step_exec.status == ActionStatus.COMPLETED:
                status_msg = Colors.success(f"\n{status_icon} Step {step_number} Status: {step_exec.status.value}")
            elif step_exec.status == ActionStatus.FAILED:
                status_msg = Colors.error(f"\n{status_icon} Step {step_number} Status: {step_exec.status.value}")
            else:
                status_msg = Colors.executor(f"\n{status_icon} Step {step_number} Status: {step_exec.status.value}")
            print(status_msg)
            
            if step_exec.result:
                result_str = json.dumps(step_exec.result, indent=2)
                if len(result_str) > 500:
                    result_str = result_str[:500] + "..."
                print(Colors.executor(f"   Result: {result_str}"))
            
            if step_exec.error:
                print(Colors.error(f"   ❌ Error: {step_exec.error}"))
            
            if step_exec.validation_results:
                print(Colors.executor(f"   Validations:"))
                for v in step_exec.validation_results:
                    v_icon = "✅" if v.get("passed") else "❌"
                    if v.get("passed"):
                        print(Colors.success(f"     {v_icon} {v.get('check')}: {v.get('message')}"))
                    else:
                        print(Colors.error(f"     {v_icon} {v.get('check')}: {v.get('message')}"))
            
            self.current_trace.steps.append(step_exec)
            
            # Check if step failed critically
            if step_exec.status == ActionStatus.FAILED:
                logger.error(f"Step {step_number} failed: {step_exec.error}")
                print(Colors.error(f"\n{'='*80}"))
                print(Colors.error(f"❌ EXECUTOR: WORKFLOW FAILED AT STEP {step_number}"))
                print(Colors.error(f"{'='*80}"))
                print(Colors.error(f"Error: {step_exec.error}"))
                print(Colors.error(f"{'='*80}\n"))
                self.current_trace.status = SessionStatus.FAILED
                self.current_trace.final_summary = f"Failed at step {step_number}: {step_exec.error}"
                break
            
            step_number += 1
        
        # Handle timeout
        if step_number > max_steps:
            logger.warning(f"Reached max steps limit: {max_steps}")
            print(Colors.warning(f"\n{'='*80}"))
            print(Colors.warning(f"⚠️  EXECUTOR: WORKFLOW TIMEOUT - Exceeded max steps ({max_steps})"))
            print(Colors.warning(f"{'='*80}\n"))
            self.current_trace.status = SessionStatus.FAILED
            self.current_trace.final_summary = f"Exceeded maximum steps ({max_steps})"
        
        if budget.exceeded:
            logger.warning("Token budget exceeded")
            print(Colors.warning(f"\n{'='*80}"))
            print(Colors.warning(f"⚠️  EXECUTOR: TOKEN BUDGET EXCEEDED"))
            print(Colors.warning(f"{'='*80}\n"))
            self.current_trace.status = SessionStatus.FAILED
            self.current_trace.final_summary = "Token budget exceeded"
        
        # Finalize trace
        self.current_trace.end_time = datetime.now().isoformat()
        
        logger.info(f"Workflow execution complete. Status: {self.current_trace.status.value}")
        
        # Always show final summary
        completed = sum(1 for s in self.current_trace.steps if s.status == ActionStatus.COMPLETED)
        failed = sum(1 for s in self.current_trace.steps if s.status == ActionStatus.FAILED)
        
        print(Colors.header(f"\n{'='*80}"))
        print(Colors.header(f"🏁 EXECUTOR AGENT: EXECUTION COMPLETE"))
        print(Colors.header(f"{'='*80}"))
        print(Colors.executor(f"Status: {self.current_trace.status.value}"))
        print(Colors.executor(f"Total Steps: {len(self.current_trace.steps)}"))
        print(Colors.success(f"Completed: {completed}"))
        if failed > 0:
            print(Colors.error(f"Failed: {failed}"))
        else:
            print(Colors.executor(f"Failed: {failed}"))
        if self.current_trace.final_summary:
            summary = self.current_trace.final_summary
            if len(summary) > 200:
                summary = summary[:200] + "..."
            print(Colors.executor(f"Summary: {summary}"))
        print(Colors.header(f"{'='*80}\n"))
        
        return self.current_trace
    
    def _evaluate_next_step(
        self,
        workflow_content: str,
        tools_config: ToolConfig,
        budget: TokenBudget,
        is_resuming: bool = False
    ) -> Dict[str, Any]:
        """
        Ask LLM what to do next based on workflow and execution so far.
        Uses native Claude API with tool calling (streaming for visibility).
        
        Args:
            workflow_content: The workflow markdown content
            tools_config: Tool configuration
            budget: Token budget tracker
            is_resuming: Whether we're resuming from a previous session
        """
        # Convert tools to Anthropic format
        anthropic_tools = self._convert_tools_to_anthropic_format(tools_config)
        
        # Build system prompt with input data if provided
        system_prompt_parts = [
            "You are an executor agent. Your job is to execute a workflow step-by-step.",
            "",
            "WORKFLOW TO EXECUTE:",
            "---",
            workflow_content,
            "---"
        ]
        
        # Add input data section if provided
        if self.input_data:
            system_prompt_parts.extend([
                "",
                "INPUT DATA FOR THIS WORKFLOW:",
                "---",
                self.input_data,
                "---",
                "",
                "Use the input data above to fill in any variables or parameters needed by the workflow."
            ])
        
        system_prompt_parts.extend([
            "",
            "EXECUTION RULES:",
            "1. Read the workflow carefully and execute it step by step",
            "2. For each step, use ONE tool call to execute the action",
            "3. Use the INPUT DATA to provide actual values when the workflow references variables",
            "4. After each tool call, assess if the result matches the workflow's validation criteria",
            "5. If you need clarification from the user, use request_clarification tool",
            "6. When all steps are complete and validated, use mark_workflow_complete tool",
            "",
            "IMPORTANT:",
            "- Execute steps sequentially - one step at a time",
            "- ALWAYS explain your reasoning before calling a tool",
            "- Use actual values from INPUT DATA section when workflow mentions variables",
            "- Validate results according to the Validation section in workflow",
            "- If stuck or need user input, call request_clarification",
            "",
            "ABOUT TOOL RESULTS:",
            "- Your conversation history contains FULL tool_use and tool_result blocks with complete details",
            "- The execution summary may show truncated results for brevity",
            "- If you see '[truncated - see conversation history for full result]', check the actual tool_result block in the conversation",
            "- Error messages are NEVER truncated - you always see the complete error details"
        ])
        
        system_prompt = "\n".join(system_prompt_parts)

        # Build messages based on whether we're resuming or starting fresh
        if is_resuming and self.message_history:
            # Resuming: Use the full conversation history + a continuation message
            history_str = self._format_execution_history()
            continuation_msg = f"""Continue workflow execution.

EXECUTION SUMMARY (overview of completed steps):
{history_str}

Note: This is a summary. Full tool results are in the conversation history above. 
If you need complete details from any step, refer to the tool_result blocks in the conversation.

---

Based on the conversation history and execution so far, what should we do next?

Explain your reasoning, then call the appropriate tool."""
            
            messages = self.message_history + [{"role": "user", "content": continuation_msg}]
        else:
            # Fresh start: Build initial user message
            history_str = self._format_execution_history()
            user_message = f"""EXECUTION SUMMARY:
{history_str}

---

Based on the workflow above and execution so far, what should we do next?

Explain your reasoning, then call the appropriate tool."""
            
            messages = [{"role": "user", "content": user_message}]

        # Use streaming API with tools
        print(Colors.executor("\n💭 Executor reasoning..."))
        
        response_text = ""
        tool_uses = []
        
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=8000,
                temperature=0.1,
                system=system_prompt,
                messages=messages,
                tools=anthropic_tools
            ) as stream:
                for event in stream:
                    if event.type == "content_block_start":
                        if hasattr(event, 'content_block') and event.content_block.type == "text":
                            pass  # Text block starting
                    elif event.type == "content_block_delta":
                        if hasattr(event, 'delta'):
                            if event.delta.type == "text_delta":
                                # Print reasoning in real-time
                                text = event.delta.text
                                print(Colors.executor(text), end="", flush=True)
                                response_text += text
                            elif event.delta.type == "input_json_delta":
                                # Tool input being streamed
                                pass
                
            # Get final message
            final_message = stream.get_final_message()
            
            # Save user message to history (the last message in our messages list)
            if not is_resuming:
                # Fresh execution - save the user message we just created
                self.message_history.append(messages[0])
            else:
                # Resuming - save the continuation message
                self.message_history.append(messages[-1])
            
            # Save assistant response to history
            assistant_content = []
            for block in final_message.content:
                if hasattr(block, 'text'):
                    assistant_content.append({"type": "text", "text": block.text})
                elif hasattr(block, 'type') and block.type == 'tool_use':
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
            
            self.message_history.append({
                "role": "assistant",
                "content": assistant_content
            })
            
            # Extract tool uses
            for block in final_message.content:
                if block.type == "tool_use":
                    tool_uses.append(block)
            
            # Track tokens
            if hasattr(final_message, 'usage'):
                budget.add_tokens(final_message.usage.input_tokens + final_message.usage.output_tokens)
        
        except Exception as e:
            logger.error(f"Error in evaluate_next_step: {e}")
            raise
        
        print()  # New line after reasoning
        
        # Process tool calls
        if not tool_uses:
            # No tool call - might be just thinking
            return {
                "reasoning": response_text,
                "goal_achieved": False,
                "next_action": None,
                "clarification_request": None
            }
        
        # Handle tool calls
        tool_use = tool_uses[0]  # Take first tool call
        tool_name = tool_use.name
        tool_input = tool_use.input
        
        # Check for special control tools
        if tool_name == "request_clarification":
            return {
                "reasoning": response_text,
                "goal_achieved": False,
                "next_action": None,
                "clarification_request": {
                    "question": tool_input.get("question", ""),
                    "context": tool_input.get("context", "")
                }
            }
        
        elif tool_name == "mark_workflow_complete":
            return {
                "reasoning": tool_input.get("summary", response_text),
                "goal_achieved": True,
                "next_action": None,
                "clarification_request": None
            }
        
        else:
            # Regular MCP tool call - parse server__tool format
            if "__" in tool_name:
                server, tool = tool_name.split("__", 1)
                return {
                    "reasoning": response_text,
                    "goal_achieved": False,
                    "next_action": {
                        "tool_server": server,
                        "tool_name": tool,
                        "parameters": tool_input,
                        "description": response_text[:200] if response_text else f"Execute {tool}",
                        "validation_checks": [],
                        "tool_use_id": tool_use.id  # Save tool_use id for adding tool_result later
                    },
                    "clarification_request": None
                }
            else:
                raise ValueError(f"Invalid tool name format: {tool_name}")
    
    async def _execute_step(
        self,
        step_number: int,
        action: Dict[str, Any],
        reasoning: str,
        budget: TokenBudget
    ) -> StepExecution:
        """Execute a single workflow step with validation"""
        tool_server = action.get("tool_server", "")
        tool_name = action.get("tool_name", "")
        parameters = action.get("parameters", {})
        description = action.get("description", f"Step {step_number}")
        validation_checks = action.get("validation_checks", [])
        
        step_exec = StepExecution(
            step_number=step_number,
            description=description,
            status=ActionStatus.PENDING,
            timestamp=datetime.now().isoformat(),
            reasoning=reasoning,
            tool_calls=[{
                "server": tool_server,
                "tool": tool_name,
                "parameters": parameters
            }]
        )
        
        try:
            # Execute tool via injected executor
            logger.info(f"Calling tool: {tool_server}/{tool_name}")
            print(Colors.executor(f"   ⚙️  Calling MCP tool..."))
            
            # Handle both async and sync tool executors
            import asyncio
            import inspect
            if inspect.iscoroutinefunction(self.tool_executor.execute_tool):
                result = await self.tool_executor.execute_tool(
                    server=tool_server,
                    tool=tool_name,
                    parameters=parameters
                )
            else:
                result = self.tool_executor.execute_tool(
                    server=tool_server,
                    tool=tool_name,
                    parameters=parameters
                )
            
            print(Colors.executor(f"   ✓ Tool execution returned"))
            
            step_exec.result = result
            
            # Validate result if checks provided
            if validation_checks and result:
                validation_results = self._run_validations(result, validation_checks)
                step_exec.validation_results = validation_results
                
                # Check if any validation failed
                failed_validations = [v for v in validation_results if not v.get("passed", False)]
                if failed_validations:
                    step_exec.status = ActionStatus.FAILED
                    step_exec.error = f"Validation failed: {failed_validations[0].get('message')}"
                else:
                    step_exec.status = ActionStatus.COMPLETED
            else:
                # No validation or no result
                step_exec.status = ActionStatus.COMPLETED
            
            logger.info(f"Step {step_number} completed with status: {step_exec.status.value}")
            
        except Exception as e:
            logger.error(f"Step {step_number} failed: {e}", exc_info=True)
            step_exec.status = ActionStatus.FAILED
            step_exec.error = str(e)
        
        return step_exec
    
    def _run_validations(
        self,
        result: Any,
        validation_checks: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Run validation checks on step result.
        Validation checks are natural language descriptions from workflow.
        """
        validation_results = []
        
        # For now, simple heuristic-based validation
        # In the future, could ask LLM to validate
        for check in validation_checks:
            check_lower = check.lower()
            passed = False
            message = ""
            
            # Simple pattern matching
            if "exist" in check_lower or "present" in check_lower:
                passed = result is not None
                message = f"Result exists: {passed}"
            
            elif "success" in check_lower:
                if isinstance(result, dict):
                    passed = result.get("success", False)
                    message = f"Success field: {passed}"
                else:
                    passed = True
                    message = "Result returned (assumed success)"
            
            else:
                # Generic check - assume passed if we got a result
                passed = True
                message = f"Generic check passed (got result)"
            
            validation_results.append({
                "check": check,
                "passed": passed,
                "message": message
            })
        
        return validation_results
    
    def _format_execution_history(self) -> str:
        """Format current execution trace for LLM context"""
        if not self.current_trace or not self.current_trace.steps:
            return "No steps executed yet."
        
        lines = []
        for step in self.current_trace.steps:
            status_icon = {
                ActionStatus.COMPLETED: "✓",
                ActionStatus.FAILED: "✗",
                ActionStatus.PENDING: "◌",
                ActionStatus.SKIPPED: "⊘"
            }.get(step.status, "?")
            
            lines.append(f"{status_icon} Step {step.step_number}: {step.description}")
            
            if step.tool_calls:
                tool_call = step.tool_calls[0]
                lines.append(f"   Tool: {tool_call.get('server')}/{tool_call.get('tool')}")
                lines.append(f"   Params: {json.dumps(tool_call.get('parameters', {}))}")
            
            if step.result:
                result_str = json.dumps(step.result)
                
                # CRITICAL: Never truncate errors - they contain essential debugging information
                if step.status == ActionStatus.FAILED or "error" in step.result or not step.result.get("success", True):
                    lines.append(f"   Result: {result_str}")  # Full error, no truncation
                
                # For success results, use smart truncation
                elif len(result_str) > 1000:
                    # Truncate but hint where to find full details
                    lines.append(f"   Result: {result_str[:1000]}... [truncated - see conversation history for full result]")
                else:
                    lines.append(f"   Result: {result_str}")
            
            if step.error:
                lines.append(f"   Error: {step.error}")
            
            if step.validation_results:
                lines.append(f"   Validations:")
                for v in step.validation_results:
                    v_icon = "✓" if v.get("passed") else "✗"
                    lines.append(f"     {v_icon} {v.get('check')}: {v.get('message')}")
            
            lines.append("")
        
        return "\n".join(lines)


async def execute_workflow_from_files(
    workflow_path: str,
    tools_path: str,
    tool_executor,
    input_data: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to execute workflow from file paths.
    
    Args:
        workflow_path: Path to workflow.md
        tools_path: Path to tools.json  
        tool_executor: Tool executor instance (e.g., MCPToolExecutor)
        input_data: Optional input data/variables for the workflow
    
    Returns:
        Execution trace as JSON dict
    """
    # Load tools config
    with open(tools_path, 'r') as f:
        tools_data = json.load(f)
    tools_config = ToolConfig.from_json(tools_data)
    
    # Create and run executor
    executor = ExecutorAgent(tool_executor=tool_executor)
    trace = await executor.execute_workflow(
        workflow_path, 
        tools_config,
        input_data=input_data
    )
    
    return trace.to_json()
