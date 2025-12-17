"""
Executor Agent - Runs workflow.md with scoped tools from tools.json
Simplified from task_agent - no UI, no dynamic discovery, fixed tool set.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from anthropic import Anthropic

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


class ExecutorAgent:
    """
    Executor Agent: Runs workflow.md files with validation.
    Tools are provided via tools.json - no dynamic discovery.
    """
    
    def __init__(
        self,
        tool_executor,  # Injected tool executor (will use ToolRegistryClient)
        model: str = "claude-sonnet-4-20250514"
    ):
        self.tool_executor = tool_executor
        self.model = model
        
        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = Anthropic(api_key=api_key)
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
    
    def execute_workflow(
        self,
        workflow_path: str,
        tools_config: ToolConfig,
        workflow_content: Optional[str] = None
    ) -> ExecutionTrace:
        """
        Execute a workflow with scoped tools.
        
        Args:
            workflow_path: Path to workflow.md file
            tools_config: Tool configuration from tools.json
            workflow_content: Optional pre-loaded workflow content
        
        Returns:
            ExecutionTrace with complete execution log
        """
        logger.info(f"Starting workflow execution: {workflow_path}")
        
        # Read workflow if not provided
        if workflow_content is None:
            with open(workflow_path, 'r') as f:
                workflow_content = f.read()
        
        # Initialize trace
        session_id = f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_trace = ExecutionTrace(
            workflow_path=workflow_path,
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            status=SessionStatus.ACTIVE,
        )
        
        # Format available tools for LLM
        tools_context = self._format_tools_context(tools_config)
        
        # Main execution loop
        step_number = 1
        max_steps = 50  # Safety limit
        budget = TokenBudget(max_tokens=180000)
        
        while step_number <= max_steps and not budget.exceeded:
            logger.info(f"Executing step {step_number}")
            
            # Call LLM to decide next action
            evaluation = self._evaluate_next_step(
                workflow_content,
                tools_context,
                budget
            )
            
            # Check if goal achieved
            if evaluation.get("goal_achieved", False):
                logger.info("Workflow goal achieved")
                self.current_trace.status = SessionStatus.COMPLETED
                self.current_trace.final_summary = evaluation.get("reasoning", "Workflow completed successfully")
                break
            
            # Check for clarification request
            clarification = evaluation.get("clarification_request")
            if clarification:
                logger.info(f"Executor needs clarification: {clarification.get('question')}")
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
                self.current_trace.status = SessionStatus.FAILED
                self.current_trace.final_summary = evaluation.get("reasoning", "No action could be determined")
                break
            
            # Execute the action
            step_exec = self._execute_step(
                step_number,
                action,
                evaluation.get("reasoning", ""),
                budget
            )
            
            self.current_trace.steps.append(step_exec)
            
            # Check if step failed critically
            if step_exec.status == ActionStatus.FAILED:
                logger.error(f"Step {step_number} failed: {step_exec.error}")
                self.current_trace.status = SessionStatus.FAILED
                self.current_trace.final_summary = f"Failed at step {step_number}: {step_exec.error}"
                break
            
            step_number += 1
        
        # Handle timeout
        if step_number > max_steps:
            logger.warning(f"Reached max steps limit: {max_steps}")
            self.current_trace.status = SessionStatus.FAILED
            self.current_trace.final_summary = f"Exceeded maximum steps ({max_steps})"
        
        if budget.exceeded:
            logger.warning("Token budget exceeded")
            self.current_trace.status = SessionStatus.FAILED
            self.current_trace.final_summary = "Token budget exceeded"
        
        # Finalize trace
        self.current_trace.end_time = datetime.now().isoformat()
        
        logger.info(f"Workflow execution complete. Status: {self.current_trace.status.value}")
        return self.current_trace
    
    def _format_tools_context(self, tools_config: ToolConfig) -> str:
        """Format available tools for LLM context"""
        lines = ["AVAILABLE TOOLS (fixed set from tools.json):"]
        lines.append("")
        
        for tool in tools_config.tools:
            server = tool.get("server", "unknown")
            tool_name = tool.get("tool", "unknown")
            desc = tool.get("description", "No description")
            lines.append(f"- {server}/{tool_name}")
            lines.append(f"  Description: {desc}")
            
            # Note: Full tool details would be fetched from tool_executor
            # For now, we'll rely on the LLM's knowledge + description
        
        return "\n".join(lines)
    
    def _evaluate_next_step(
        self,
        workflow_content: str,
        tools_context: str,
        budget: TokenBudget
    ) -> Dict[str, Any]:
        """
        Ask LLM what to do next based on workflow and execution so far.
        """
        # Format execution history
        history_str = self._format_execution_history()
        
        system_prompt = f"""You are an executor agent. Your job is to execute a workflow step-by-step.

WORKFLOW TO EXECUTE:
---
{workflow_content}
---

{tools_context}

EXECUTION RULES:
1. Read the workflow carefully and execute it step by step
2. For each step, propose ONE tool call to execute
3. After each tool call, validate the result according to validation criteria in the workflow
4. If validation fails, note it and continue (unless critical)
5. If you need clarification from the user, request it
6. When all steps are complete and validated, mark goal_achieved as true

IMPORTANT:
- Only use tools listed in AVAILABLE TOOLS above
- Follow the workflow instructions precisely
- Execute steps sequentially - one step at a time
- Validate results according to the Validation section in workflow
- If stuck or need user input, ask for clarification"""

        user_message = f"""EXECUTION HISTORY SO FAR:
{history_str}

---

Based on the workflow above and execution so far, what should we do next?

Respond with JSON:
{{
    "goal_achieved": true/false,
    "reasoning": "Current analysis and next step plan...",
    
    // EITHER propose an action:
    "next_action": {{
        "tool_server": "server_name",
        "tool_name": "function_name",
        "parameters": {{...}},
        "description": "What this step accomplishes",
        "validation_checks": ["check 1", "check 2"]  // From workflow validation section
    }} or null,
    
    // OR ask for clarification:
    "clarification_request": {{
        "question": "What information do you need?",
        "context": "Why you need it"
    }} or null
}}"""

        response, tokens, input_tokens = self._call_claude(system_prompt, user_message)
        budget.add_tokens(tokens)
        
        return self._parse_json_response(response)
    
    def _execute_step(
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
            result = self.tool_executor.execute_tool(
                server=tool_server,
                tool=tool_name,
                parameters=parameters
            )
            
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
                if len(result_str) > 200:
                    result_str = result_str[:200] + "..."
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
    
    def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1
    ) -> Tuple[str, int, int]:
        """Make a call to Claude API. Returns (response, total_tokens, input_tokens)."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8000,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            total_tokens = input_tokens + output_tokens
            logger.info(f"Claude API call: {input_tokens} in, {output_tokens} out")
            
            return response.content[0].text, total_tokens, input_tokens
            
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            raise
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Claude's response, handling markdown code blocks."""
        response = response.strip()
        
        # Extract from markdown code blocks
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end != -1:
                response = response[start:end].strip()
        elif "```" in response:
            parts = response.split("```")
            for part in parts[1:]:
                if "{" in part:
                    response = part.strip()
                    break
        
        # Find JSON object
        start_idx = response.find('{')
        if start_idx == -1:
            raise ValueError("No JSON object found in response")
        
        # Find matching closing brace
        brace_count = 0
        end_idx = start_idx
        for i, char in enumerate(response[start_idx:], start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        json_str = response[start_idx:end_idx]
        return json.loads(json_str)


def execute_workflow_from_files(
    workflow_path: str,
    tools_path: str,
    tool_executor
) -> Dict[str, Any]:
    """
    Convenience function to execute workflow from file paths.
    
    Args:
        workflow_path: Path to workflow.md
        tools_path: Path to tools.json  
        tool_executor: Tool executor instance (e.g., ToolRegistryClient)
    
    Returns:
        Execution trace as JSON dict
    """
    # Load tools config
    with open(tools_path, 'r') as f:
        tools_data = json.load(f)
    tools_config = ToolConfig.from_json(tools_data)
    
    # Create and run executor
    executor = ExecutorAgent(tool_executor=tool_executor)
    trace = executor.execute_workflow(workflow_path, tools_config)
    
    return trace.to_json()
