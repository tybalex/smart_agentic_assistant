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

from constants import CLAUDE_MODEL, MAX_ITERATIONS, MAX_TOKEN_BUDGET

from .models import (
    ExecutionTrace, ActionExecution,
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
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=self.api_key)
        self.current_trace: Optional[ExecutionTrace] = None
    
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
        
        # Add special control tools for workflow lifecycle management
        anthropic_tools.extend([
            {
                "name": "mark_workflow_complete",
                "description": """Call this when ALL workflow steps are successfully completed and validated.
                
This signals SUCCESS and ends execution. Use when:
- All required workflow steps have been executed
- All validations passed
- No errors or blockers remain
- The workflow goals are fully achieved

Provide a clear summary of what was accomplished.""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {
                            "type": "string",
                            "description": "Concise summary of accomplished tasks (e.g., 'Created 3 accounts, sent 5 invitations, validated all members')"
                        }
                    },
                    "required": ["summary"]
                }
            },
            {
                "name": "request_user_input",
                "description": """Call this when you need information or a decision from the user to proceed.
Use when:
- You need clarification about ambiguous workflow instructions
- You need user to provide missing data/parameters
- You need user to make a choice between multiple valid options
- External manual action is required before you can continue

IMPORTANT: Before calling this tool, explain your question/need in your reasoning. 
The user will see your last message, so make it clear what you need.""",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "mark_workflow_blocked",
                "description": """Call this when the workflow CANNOT proceed due to an unrecoverable error or blocker.
This signals FAILURE and ends execution. Use when:
- A critical tool/API is unavailable or broken
- Required data is missing and cannot be obtained
- Workflow has logical errors that prevent execution
- You've exhausted all recovery options

Do NOT use for temporary issues or things that need user input (use request_user_input instead).""",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Clear explanation of why the workflow is blocked and cannot proceed"
                        }
                    },
                    "required": ["reason"]
                }
            }
        ])
        
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
            
            # Deserialize and restore previous actions
            for action_data in previous_trace.get("actions", []):
                action = ActionExecution(
                    action_number=action_data["action_number"],
                    description=action_data.get("description", ""),
                    status=ActionStatus(action_data["status"]),
                    timestamp=action_data.get("timestamp", datetime.now().isoformat()),
                    reasoning=action_data.get("reasoning"),
                    tool_calls=action_data.get("tool_calls", []),
                    result=action_data.get("result"),
                    error=action_data.get("error")
                )
                self.current_trace.actions.append(action)
            
            # If resuming with new input_data, inject it as a user message
            # The executor will naturally see this and determine how to proceed
            if input_data:
                logger.info(f"Resuming session with new input_data: {input_data[:100]}...")
                print(Colors.success(f"📝 Injecting user input into conversation..."))
                self.message_history.append({
                    "role": "user",
                    "content": input_data
                })
            
            starting_action = len(self.current_trace.actions) + 1
            
            print(Colors.header(f"\n{'='*80}"))
            print(Colors.header(f"🔄 EXECUTOR AGENT: RESUMING WORKFLOW EXECUTION"))
            print(Colors.header(f"{'='*80}"))
            print(Colors.executor(f"📁 Workflow: {workflow_path}"))
            print(Colors.executor(f"🔧 Tools: {len(tools_config.tools)} available"))
            print(Colors.executor(f"📂 Session: {session_id}"))
            print(Colors.executor(f"📊 Previous actions: {len(self.current_trace.actions)} completed"))
            print(Colors.executor(f"🎯 Resuming from action: {starting_action}"))
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
            
            # If input_data provided for initial execution, inject as first user message
            if input_data:
                logger.info(f"Starting workflow with input_data: {input_data[:100]}...")
                print(Colors.success(f"📝 Initial input data provided"))
                self.message_history.append({
                    "role": "user",
                    "content": input_data
                })
            
            starting_action = 1
            
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
        action_number = starting_action
        max_actions = MAX_ITERATIONS  # Safety limit (renamed from max_steps to avoid confusion with workflow steps)
        budget = TokenBudget(max_tokens=MAX_TOKEN_BUDGET)
        
        # If resuming, restore token budget (approximate based on message history)
        if previous_trace and self.message_history:
            # Estimate tokens used from previous messages
            estimated_tokens = sum(
                len(str(msg.get("content", ""))) // 4  # Rough estimate: 4 chars per token
                for msg in self.message_history
            )
            budget.used_tokens = estimated_tokens
            print(Colors.executor(f"📊 Token budget restored: ~{estimated_tokens} tokens used previously\n"))
        
        while action_number <= max_actions and not budget.exceeded:
            logger.info(f"Executing action {action_number}")
            
            # Always show action progress
            print(Colors.executor(f"\n{'─'*80}"))
            print(Colors.executor(f"📝 ACTION {action_number}: Evaluating next action..."))
            print(Colors.executor(f"{'─'*80}"))
            
            # Call LLM to decide next action (now with streaming and real-time output)
            # Pass is_resuming=True only for the very first action after resume
            is_first_resumed_action = (previous_trace is not None and action_number == starting_action)
            evaluation = self._evaluate_next_action(
                workflow_content,
                tools_config,  # Pass tools_config instead of formatted string
                budget,
                is_resuming=is_first_resumed_action
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
            
            # Check if executor needs user input
            if evaluation.get("needs_user_input", False):
                logger.info("Executor requested user input")
                print(Colors.warning(f"\n❓ EXECUTOR: WAITING FOR USER INPUT"))
                print(Colors.warning(f"   The executor has paused and needs user input to proceed."))
                print(Colors.warning(f"   Check the executor's last message for details on what is needed."))
                print(Colors.warning(f"{'─'*80}\n"))
                self.current_trace.status = SessionStatus.WAITING_FOR_INPUT
                break
            
            # Check if workflow is blocked
            if evaluation.get("workflow_blocked"):
                reason = evaluation.get("workflow_blocked", "Unknown blocker")
                logger.error(f"Workflow blocked: {reason}")
                print(Colors.error(f"\n❌ EXECUTOR: WORKFLOW BLOCKED"))
                print(Colors.error(f"   Reason: {reason}"))
                print(Colors.error(f"{'─'*80}\n"))
                self.current_trace.status = SessionStatus.FAILED
                self.current_trace.final_summary = f"Workflow blocked: {reason}"
                break
            
            # Check if executor stopped naturally (edge case - no tool call)
            if evaluation.get("awaiting_response", False):
                logger.info("Executor stopped naturally without calling completion tool")
                print(Colors.warning(f"\n⏸️  EXECUTOR: STOPPED WITH MESSAGE"))
                print(Colors.warning(f"   The executor stopped without calling a completion tool."))
                print(Colors.warning(f"   Returning control to Main Agent for review."))
                print(Colors.warning(f"{'─'*80}\n"))
                self.current_trace.status = SessionStatus.AWAITING_RESPONSE
                self.current_trace.final_summary = evaluation.get("reasoning", "Executor stopped naturally")
                break
            
            # Execute proposed actions (may be multiple tool calls in one response)
            actions = evaluation.get("next_actions", [])
            if not actions:
                logger.warning("No actions proposed")
                print(Colors.error(f"\n❌ EXECUTOR ERROR: No actions proposed by LLM"))
                self.current_trace.status = SessionStatus.FAILED
                self.current_trace.final_summary = evaluation.get("reasoning", "No action could be determined")
                break
            
            # Execute all actions and collect results
            tool_results_content = []  # Collect all tool results for a single user message
            actions_executed = []
            has_failure = False
            
            for i, action in enumerate(actions):
                # Show what we're doing
                if len(actions) > 1:
                    print(Colors.executor(f"\n🔧 Executing action {action_number} (batch {i+1}/{len(actions)}):"))
                else:
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
                
                # Execute the action
                action_exec = await self._execute_action(
                    action_number,
                    action,
                    evaluation.get("reasoning", ""),
                    budget
                )
                
                # Collect tool result for message history
                tool_use_id = action.get("tool_use_id")
                if tool_use_id:
                    # Format the result for Claude API
                    if action_exec.status == ActionStatus.COMPLETED:
                        result_content = json.dumps(action_exec.result) if action_exec.result else "Success"
                    else:
                        result_content = f"Error: {action_exec.error}" if action_exec.error else "Failed"
                    
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result_content
                    })
                
                # Always show action results
                status_icon = {
                    ActionStatus.COMPLETED: "✅",
                    ActionStatus.FAILED: "❌",
                    ActionStatus.PENDING: "⏳",
                    ActionStatus.SKIPPED: "⊘"
                }.get(action_exec.status, "❓")
                
                # Use different color based on status
                if action_exec.status == ActionStatus.COMPLETED:
                    status_msg = Colors.success(f"\n{status_icon} Action {action_number} Status: {action_exec.status.value}")
                elif action_exec.status == ActionStatus.FAILED:
                    status_msg = Colors.error(f"\n{status_icon} Action {action_number} Status: {action_exec.status.value}")
                else:
                    status_msg = Colors.executor(f"\n{status_icon} Action {action_number} Status: {action_exec.status.value}")
                print(status_msg)
                
                if action_exec.result:
                    result_str = json.dumps(action_exec.result, indent=2)
                    if len(result_str) > 500:
                        result_str = result_str[:500] + "..."
                    print(Colors.executor(f"   Result: {result_str}"))
                
                if action_exec.error:
                    print(Colors.error(f"   ❌ Error: {action_exec.error}"))
                
                if action_exec.validation_results:
                    print(Colors.executor(f"   Validations:"))
                    for v in action_exec.validation_results:
                        v_icon = "✅" if v.get("passed") else "❌"
                        if v.get("passed"):
                            print(Colors.success(f"     {v_icon} {v.get('check')}: {v.get('message')}"))
                        else:
                            print(Colors.error(f"     {v_icon} {v.get('check')}: {v.get('message')}"))
                
                self.current_trace.actions.append(action_exec)
                actions_executed.append(action_exec)
                
                # Check if action failed critically
                if action_exec.status == ActionStatus.FAILED:
                    has_failure = True
                    logger.error(f"Action {action_number} failed: {action_exec.error}")
                
                action_number += 1
            
            # Add ALL tool results in a single user message (required by Claude API)
            if tool_results_content:
                self.message_history.append({
                    "role": "user",
                    "content": tool_results_content
                })
            
            # If any action failed, stop execution
            if has_failure:
                failed_action = [a for a in actions_executed if a.status == ActionStatus.FAILED][0]
                print(Colors.error(f"\n{'='*80}"))
                print(Colors.error(f"❌ EXECUTOR: WORKFLOW FAILED AT ACTION {failed_action.action_number}"))
                print(Colors.error(f"{'='*80}"))
                print(Colors.error(f"Error: {failed_action.error}"))
                print(Colors.error(f"{'='*80}\n"))
                self.current_trace.status = SessionStatus.FAILED
                self.current_trace.final_summary = f"Failed at action {failed_action.action_number}: {failed_action.error}"
                break
        
        # Handle timeout
        if action_number > max_actions:
            logger.warning(f"Reached max actions limit: {max_actions}")
            print(Colors.warning(f"\n{'='*80}"))
            print(Colors.warning(f"⚠️  EXECUTOR: WORKFLOW TIMEOUT - Exceeded max actions ({max_actions})"))
            print(Colors.warning(f"{'='*80}\n"))
            self.current_trace.status = SessionStatus.FAILED
            self.current_trace.final_summary = f"Exceeded maximum actions ({max_actions})"
        
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
        completed = sum(1 for a in self.current_trace.actions if a.status == ActionStatus.COMPLETED)
        failed = sum(1 for a in self.current_trace.actions if a.status == ActionStatus.FAILED)
        
        print(Colors.header(f"\n{'='*80}"))
        print(Colors.header(f"🏁 EXECUTOR AGENT: EXECUTION COMPLETE"))
        print(Colors.header(f"{'='*80}"))
        print(Colors.executor(f"Status: {self.current_trace.status.value}"))
        print(Colors.executor(f"Total Actions: {len(self.current_trace.actions)}"))
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
    
    def _evaluate_next_action(
        self,
        workflow_content: str,
        tools_config: ToolConfig,
        budget: TokenBudget,
        is_resuming: bool = False
    ) -> Dict[str, Any]:
        """
        Ask LLM what action to take next based on workflow and execution so far.
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
            "You are an executor agent. Your job is to execute a workflow by taking actions (tool calls) to complete each workflow step.",
            "",
            "TERMINOLOGY:",
            "- **Workflow Steps** = High-level phases defined in the workflow (e.g., 'Step 1: Salesforce Operations')",
            "- **Executor Actions** = Individual tool calls you make (e.g., 'Action 1: Query Salesforce', 'Action 2: Create account')",
            "- You may take multiple actions to complete one workflow step",
            "",
            "WORKFLOW TO EXECUTE:",
            "---",
            workflow_content,
            "---"
        ]
        
        system_prompt_parts.extend([
            "",
            "EXECUTION RULES:",
            "1. Read the workflow carefully and work through each workflow step",
            "2. For each action, use ONE tool call to perform the operation",
            "3. The user may provide input data (parameters, context, or clarification responses) via messages",
            "4. Use any user-provided data to fill in variables or parameters needed by the workflow",
            "5. After each tool call, assess if the result matches the workflow's validation criteria",
            "6. If you need clarification from the user, use request_user_input tool",
            "7. When all workflow steps are complete and validated, use mark_workflow_complete tool",
            "",
            "IMPORTANT:",
            "- Work through workflow steps sequentially",
            "- ALWAYS explain your reasoning before calling a tool",
            "- Use actual values from user messages when workflow mentions variables or parameters",
            "- When you request user input and the user responds, determine if the response answers your question(s)",
            "- Validate results according to the Validation section in workflow",
            "- If stuck or need user input, call request_user_input",
            "",
            "ABOUT TOOL RESULTS:",
            "- Your conversation history contains FULL tool_use and tool_result blocks with complete details",
            "- The execution summary may show truncated results for brevity",
            "- If you see '[truncated - see conversation history for full result]', check the actual tool_result block in the conversation",
            "- Error messages are NEVER truncated - you always see the complete error details"
        ])
        
        system_prompt = "\n".join(system_prompt_parts)

        # Build messages based on whether we're resuming or starting fresh
        if is_resuming and len(self.message_history) > 1:  # More than just initial input
            # Resuming: Use the full conversation history + a continuation message
            history_str = self._format_execution_history()
            continuation_msg = f"""Continue workflow execution.

EXECUTION SUMMARY (overview of completed actions):
{history_str}

Note: This is a summary. Full tool results are in the conversation history above. 
If you need complete details from any action, refer to the tool_result blocks in the conversation.

If the user provided new input above (e.g., clarification response), evaluate whether it answers any outstanding questions you had.

---

Based on the conversation history and execution so far, what should we do next?

Explain your reasoning, then call the appropriate tool."""
            
            messages = self.message_history + [{"role": "user", "content": continuation_msg}]
        else:
            # Fresh start or first action: Use message history (may include initial input_data) + prompt
            history_str = self._format_execution_history()
            user_message = f"""EXECUTION SUMMARY:
{history_str}

---

Based on the workflow above and execution so far, what should we do next?

If the user provided input data above, use it to fill in any variables or parameters the workflow needs.

Explain your reasoning, then call the appropriate tool."""
            
            # Include any existing message history (e.g., initial input_data user message)
            messages = self.message_history + [{"role": "user", "content": user_message}]

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
            # Whether fresh execution or resuming, we always append the last message (the new user prompt)
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
            # No tool call - executor stopped without explicit completion tool
            # This is the edge case: return "awaiting_response" signal
            return {
                "reasoning": response_text,
                "goal_achieved": False,
                "next_actions": [],
                "awaiting_response": True  # Signal that executor stopped naturally
            }
        
        # Handle tool calls - now supporting multiple tool calls
        # First, scan ALL tools to check if any are special control tools
        # Control tools take priority and should be used alone
        control_tool = None
        control_tool_input = None
        
        for tool_use in tool_uses:
            if tool_use.name in ["request_user_input", "mark_workflow_complete", "mark_workflow_blocked"]:
                control_tool = tool_use.name
                control_tool_input = tool_use.input
                break  # Found a control tool, prioritize it
        
        # If we found a control tool, handle it (ignoring any other tools)
        if control_tool == "request_user_input":
            # Executor needs user input - pause execution
            logger.info("Control tool detected: request_user_input")
            if len(tool_uses) > 1:
                logger.warning(f"Multiple tools called but request_user_input takes priority. Ignoring {len(tool_uses) - 1} other tools.")
            return {
                "reasoning": response_text,
                "goal_achieved": False,
                "next_actions": [],
                "needs_user_input": True
            }
        
        elif control_tool == "mark_workflow_complete":
            # Workflow successfully completed
            logger.info("Control tool detected: mark_workflow_complete")
            if len(tool_uses) > 1:
                logger.warning(f"Multiple tools called but mark_workflow_complete takes priority. Ignoring {len(tool_uses) - 1} other tools.")
            return {
                "reasoning": control_tool_input.get("summary", response_text),
                "goal_achieved": True,
                "next_actions": []
            }
        
        elif control_tool == "mark_workflow_blocked":
            # Workflow is blocked and cannot proceed
            logger.info("Control tool detected: mark_workflow_blocked")
            if len(tool_uses) > 1:
                logger.warning(f"Multiple tools called but mark_workflow_blocked takes priority. Ignoring {len(tool_uses) - 1} other tools.")
            return {
                "reasoning": response_text,
                "goal_achieved": False,
                "next_actions": [],
                "workflow_blocked": control_tool_input.get("reason", "Workflow blocked")
            }
        
        # No control tools found - process all regular MCP tool calls
        next_actions = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input
            
            # Parse server__tool format
            if "__" in tool_name:
                server, tool = tool_name.split("__", 1)
                next_actions.append({
                    "tool_server": server,
                    "tool_name": tool,
                    "parameters": tool_input,
                    "description": response_text[:200] if response_text else f"Execute {tool}",
                    "validation_checks": [],
                    "tool_use_id": tool_use.id  # Save tool_use id for adding tool_result later
                })
            else:
                raise ValueError(f"Invalid tool name format: {tool_name}")
        
        if len(next_actions) > 1:
            logger.info(f"Processing batch of {len(next_actions)} tool calls")
        
        return {
            "reasoning": response_text,
            "goal_achieved": False,
            "next_actions": next_actions,  # Return list of actions
            "awaiting_response": False  # Not awaiting response for regular tool calls
        }
    
    async def _execute_action(
        self,
        action_number: int,
        action: Dict[str, Any],
        reasoning: str,
        budget: TokenBudget
    ) -> ActionExecution:
        """Execute a single workflow action (one tool call) with validation"""
        tool_server = action.get("tool_server", "")
        tool_name = action.get("tool_name", "")
        parameters = action.get("parameters", {})
        description = action.get("description", f"Action {action_number}")
        validation_checks = action.get("validation_checks", [])
        
        action_exec = ActionExecution(
            action_number=action_number,
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
            
            action_exec.result = result
            
            # Validate result if checks provided
            if validation_checks and result:
                validation_results = self._run_validations(result, validation_checks)
                action_exec.validation_results = validation_results
                
                # Check if any validation failed
                failed_validations = [v for v in validation_results if not v.get("passed", False)]
                if failed_validations:
                    action_exec.status = ActionStatus.FAILED
                    action_exec.error = f"Validation failed: {failed_validations[0].get('message')}"
                else:
                    action_exec.status = ActionStatus.COMPLETED
            else:
                # No validation or no result
                action_exec.status = ActionStatus.COMPLETED
            
            logger.info(f"Action {action_number} completed with status: {action_exec.status.value}")
            
        except Exception as e:
            logger.error(f"Action {action_number} failed: {e}", exc_info=True)
            action_exec.status = ActionStatus.FAILED
            action_exec.error = str(e)
        
        return action_exec
    
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
        """Format current execution trace for LLM context (summary of completed actions)"""
        if not self.current_trace or not self.current_trace.actions:
            return "No actions executed yet."
        
        lines = []
        for action in self.current_trace.actions:
            status_icon = {
                ActionStatus.COMPLETED: "✓",
                ActionStatus.FAILED: "✗",
                ActionStatus.PENDING: "◌",
                ActionStatus.SKIPPED: "⊘"
            }.get(action.status, "?")
            
            lines.append(f"{status_icon} Action {action.action_number}: {action.description}")
            
            if action.tool_calls:
                tool_call = action.tool_calls[0]
                lines.append(f"   Tool: {tool_call.get('server')}/{tool_call.get('tool')}")
                lines.append(f"   Params: {json.dumps(tool_call.get('parameters', {}))}")
            
            if action.result:
                result_str = json.dumps(action.result)
                
                # CRITICAL: Never truncate errors - they contain essential debugging information
                if action.status == ActionStatus.FAILED or "error" in action.result or not action.result.get("success", True):
                    lines.append(f"   Result: {result_str}")  # Full error, no truncation
                
                # For success results, use smart truncation
                elif len(result_str) > 1000:
                    # Truncate but hint where to find full details
                    lines.append(f"   Result: {result_str[:1000]}... [truncated - see conversation history for full result]")
                else:
                    lines.append(f"   Result: {result_str}")
            
            if action.error:
                lines.append(f"   Error: {action.error}")
            
            if action.validation_results:
                lines.append(f"   Validations:")
                for v in action.validation_results:
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
