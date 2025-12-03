"""
AI Agent powered by Claude Sonnet 4.5.
Handles task parsing, planning, and execution.
"""

import os
import json
from typing import List, Dict, Any, Optional, Tuple
from anthropic import Anthropic

from models import Task, TaskSession, TaskStatus, TextSpan, generate_id
from task_manager import TaskManager
from tool_client import ToolRegistryClient


class TaskAgent:
    """
    AI Agent that parses user text into tasks and executes them.
    Uses Claude Sonnet 4.5 for intelligence.
    """
    
    def __init__(
        self,
        task_manager: TaskManager,
        tool_client: ToolRegistryClient,
        model: str = "claude-sonnet-4-5-20250929"
    ):
        self.task_manager = task_manager
        self.tool_client = tool_client
        self.model = model
        self.client = Anthropic()  # Uses ANTHROPIC_API_KEY env var
        
        # Cache available tools
        self._tools_cache: Optional[str] = None
        self._tools_list: Optional[List[Dict]] = None
        
        # Conversation history for maintaining context across task executions
        self._conversation_history: List[Dict[str, str]] = []
        self._system_prompt: Optional[str] = None
    
    def _get_tools_context(self) -> str:
        """Get formatted context about available tools."""
        if self._tools_cache is None:
            self._tools_cache = self.tool_client.get_tools_summary()
            self._tools_list = self.tool_client.list_all_functions()
        return self._tools_cache
    
    def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3
    ) -> str:
        """Make a single call to Claude API (stateless)."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )
        return response.content[0].text
    
    def _call_claude_with_history(
        self,
        user_message: str,
        temperature: float = 0.3
    ) -> str:
        """
        Make a call to Claude using conversation history.
        Maintains context across multiple task executions.
        """
        # Add the new user message to history
        self._conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=temperature,
            system=self._system_prompt,
            messages=self._conversation_history
        )
        
        assistant_message = response.content[0].text
        
        # Add assistant response to history
        self._conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })
        
        return assistant_message
    
    def _init_conversation(self, original_text: str, tasks: List[Task]) -> None:
        """Initialize the conversation context for task execution."""
        tools_context = self._get_tools_context()
        
        task_list = "\n".join([
            f"{i+1}. [{t.id}] {t.title}: {t.description}"
            for i, t in enumerate(tasks)
        ])
        
        self._system_prompt = f"""You are an intelligent task execution agent. You help users accomplish tasks by selecting and using available tools.

AVAILABLE TOOLS:
{tools_context}

ORIGINAL USER REQUEST:
{original_text}

EXTRACTED TASKS:
{task_list}

YOUR RESPONSIBILITIES:
1. For each task, determine the best tool to use and its parameters
2. Remember the results of previous tasks - they may be needed for subsequent tasks
3. If a task depends on a previous result, use that result appropriately
4. If no suitable tool exists, explain what could be done alternatively
5. Be precise with parameter values based on the context

When planning a task, respond with a JSON object:
{{
  "can_execute": true/false,
  "tool_category": "<category>",
  "tool_name": "<name>",
  "parameters": {{}},
  "reasoning": "<explanation>",
  "alternative_approach": "<if cannot execute>"
}}

When reviewing progress, respond with a JSON object:
{{
  "updates_needed": true/false,
  "reasoning": "<analysis>",
  "new_tasks": [],
  "tasks_to_remove": [],
  "tasks_to_modify": [],
  "agent_note": "<observations>"
}}"""
        
        # Clear and initialize conversation history
        self._conversation_history = []
    
    def _add_execution_result_to_history(self, task: Task, result: Dict[str, Any]) -> None:
        """Add task execution result to conversation history."""
        if result.get("success"):
            result_summary = json.dumps(result.get("result", {}), indent=2)
            message = f"""TASK COMPLETED: {task.title}
Tool used: {task.tool_used}
Parameters: {json.dumps(task.tool_params, indent=2) if task.tool_params else 'None'}
Result:
{result_summary}"""
        else:
            message = f"""TASK FAILED: {task.title}
Error: {result.get('error', 'Unknown error')}"""
        
        # Add as a "user" message to inform the assistant of results
        self._conversation_history.append({
            "role": "user",
            "content": message
        })
        # Add acknowledgment to keep conversation valid
        self._conversation_history.append({
            "role": "assistant",
            "content": f"Understood. Task '{task.title}' {'completed successfully' if result.get('success') else 'failed'}. I will take this into account for subsequent tasks."
        })
    
    def parse_tasks_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse user input text to extract tasks with their text spans.
        Returns a list of task dictionaries ready to be added to the session.
        """
        tools_context = self._get_tools_context()
        
        system_prompt = f"""You are a task parsing assistant. Your job is to analyze user input text and extract actionable tasks.

You have access to the following tools that can be used to execute tasks:
{tools_context}

IMPORTANT GUIDELINES:
1. Extract tasks that can be accomplished using the available tools
2. For each task, identify the EXACT text span in the original input
3. Break down complex requests into smaller, actionable steps if needed
4. Consider the logical order of tasks (dependencies)
5. Be practical - if no tool can handle a part of the request, note it but still create a task

Your response must be a valid JSON array with the following structure:
[
  {{
    "title": "Short task title",
    "description": "Detailed description of what needs to be done",
    "text_span": {{
      "start": <start character index in original text>,
      "end": <end character index in original text>,
      "text": "<exact text from original that this task corresponds to>"
    }},
    "suggested_tool": "<tool name if you know which tool to use, or null>",
    "suggested_category": "<tool category if known, or null>"
  }},
  ...
]

Only respond with the JSON array, no additional text."""

        user_message = f"""Please analyze the following text and extract all tasks:

---
{text}
---

Remember to:
1. Identify the exact character positions for each task's text span
2. Order tasks logically
3. Be specific in descriptions
4. Suggest tools when possible"""

        try:
            response = self._call_claude(system_prompt, user_message)
            # Clean up response - remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]
            response = response.strip()
            
            tasks = json.loads(response)
            return tasks
        except json.JSONDecodeError as e:
            print(f"Error parsing Claude response as JSON: {e}")
            print(f"Raw response: {response}")
            return []
        except Exception as e:
            print(f"Error calling Claude: {e}")
            return []
    
    def plan_task_execution(self, task: Task) -> Dict[str, Any]:
        """
        Plan how to execute a specific task.
        Returns tool selection and parameters.
        Uses conversation history to maintain context from previous tasks.
        """
        user_message = f"""PLAN NEXT TASK:

Task ID: {task.id}
Title: {task.title}
Description: {task.description}
Original text: {task.text_span.text if task.text_span else 'N/A'}

Based on the available tools and any previous task results, what tool should be used and with what parameters?

Respond with ONLY a JSON object (no markdown, no explanation):
{{"can_execute": true/false, "tool_category": "...", "tool_name": "...", "parameters": {{}}, "reasoning": "...", "alternative_approach": "..."}}"""

        try:
            # Use conversation history if initialized, otherwise fall back to single call
            if self._system_prompt:
                response = self._call_claude_with_history(user_message)
            else:
                # Fallback for cases where conversation isn't initialized
                response = self._call_claude_fallback(task)
            
            # Clean up response
            response = response.strip()
            if response.startswith("```"):
                lines = response.split("\n")
                response = "\n".join(lines[1:])
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]
            response = response.strip()
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            print(f"Error parsing response as JSON: {e}")
            print(f"Raw response: {response}")
            return {
                "can_execute": False,
                "reasoning": f"Error parsing AI response: {str(e)}",
                "alternative_approach": "Manual intervention may be needed"
            }
        except Exception as e:
            print(f"Error planning task execution: {e}")
            return {
                "can_execute": False,
                "reasoning": f"Error during planning: {str(e)}",
                "alternative_approach": "Manual intervention may be needed"
            }
    
    def _call_claude_fallback(self, task: Task) -> str:
        """Fallback method when conversation history isn't available."""
        tools_context = self._get_tools_context()
        
        # Get execution history for context
        completed_tasks = self.task_manager.get_all_tasks()
        history_context = ""
        if completed_tasks:
            history_parts = []
            for t in completed_tasks:
                if t.status == TaskStatus.COMPLETED:
                    result_preview = (t.result[:200] + "...") if t.result and len(t.result) > 200 else (t.result or 'Completed')
                    history_parts.append(f"- {t.title}:\n  Result: {result_preview}")
                elif t.status == TaskStatus.FAILED:
                    history_parts.append(f"- {t.title}: FAILED - {t.error}")
            if history_parts:
                history_context = "PREVIOUSLY EXECUTED TASKS:\n" + "\n".join(history_parts)
        
        system_prompt = f"""You are a task execution planner. Select the best tool for the task.

Available tools:
{tools_context}

{history_context}

Respond with ONLY a JSON object:
{{"can_execute": true/false, "tool_category": "...", "tool_name": "...", "parameters": {{}}, "reasoning": "...", "alternative_approach": "..."}}"""

        user_message = f"""Plan execution for:
Title: {task.title}
Description: {task.description}
Original text: {task.text_span.text if task.text_span else 'N/A'}"""

        return self._call_claude(system_prompt, user_message)
    
    def execute_task(self, task: Task, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task based on the execution plan.
        """
        if not plan.get("can_execute", False):
            return {
                "success": False,
                "error": plan.get("reasoning", "Cannot execute this task"),
                "suggestion": plan.get("alternative_approach")
            }
        
        category = plan.get("tool_category")
        tool_name = plan.get("tool_name")
        parameters = plan.get("parameters", {})
        
        if not category or not tool_name:
            return {
                "success": False,
                "error": "Missing tool category or name in execution plan"
            }
        
        # Update task with tool info
        self.task_manager.set_task_tool_info(task.id, f"{category}/{tool_name}", parameters)
        
        # Execute the tool
        result = self.tool_client.execute_function(category, tool_name, parameters)
        
        return result
    
    def review_and_update_tasks(self) -> Dict[str, Any]:
        """
        Review current progress and determine if task list needs updates.
        Called after each task execution.
        """
        session = self.task_manager.current_session
        if not session:
            return {"updates_needed": False}
        
        completed = [t for t in session.tasks if t.status == TaskStatus.COMPLETED]
        pending = [t for t in session.tasks if t.status == TaskStatus.PENDING]
        failed = [t for t in session.tasks if t.status == TaskStatus.FAILED]
        
        # Build context for review
        completed_summary = "\n".join([
            f"- {t.title}: {t.result or 'Done'}" for t in completed
        ]) or "None"
        
        pending_summary = "\n".join([
            f"- {t.title}: {t.description}" for t in pending
        ]) or "None"
        
        failed_summary = "\n".join([
            f"- {t.title}: {t.error}" for t in failed
        ]) or "None"
        
        system_prompt = """You are a task review assistant. Your job is to review the current progress and determine if the task list needs updates.

Consider:
1. Are there any tasks that need to be added based on completed work?
2. Are there any pending tasks that should be removed or modified?
3. Should the order of remaining tasks change?
4. Are there any failed tasks that need a different approach?

Your response must be a valid JSON object:
{
  "updates_needed": true/false,
  "reasoning": "<your analysis>",
  "new_tasks": [{"title": "...", "description": "...", "insert_after_task_id": "..." or null}],
  "tasks_to_remove": ["task_id1", ...],
  "tasks_to_modify": [{"task_id": "...", "new_title": "...", "new_description": "..."}],
  "agent_note": "<any observations or recommendations for the user>"
}

Only respond with the JSON object, no additional text."""

        user_message = f"""Please review the current task execution progress:

ORIGINAL TEXT:
{session.original_text}

COMPLETED TASKS:
{completed_summary}

PENDING TASKS:
{pending_summary}

FAILED TASKS:
{failed_summary}

Should the task list be updated?"""

        try:
            response = self._call_claude(system_prompt, user_message)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1]
            if response.endswith("```"):
                response = response.rsplit("```", 1)[0]
            response = response.strip()
            
            review_result = json.loads(response)
            
            # Apply updates if needed
            if review_result.get("updates_needed"):
                self._apply_task_updates(review_result)
            
            # Add agent note
            if review_result.get("agent_note"):
                self.task_manager.add_agent_note(review_result["agent_note"])
            
            return review_result
        except Exception as e:
            print(f"Error during task review: {e}")
            return {"updates_needed": False, "error": str(e)}
    
    def _apply_task_updates(self, review_result: Dict[str, Any]) -> None:
        """Apply the updates from task review."""
        # Remove tasks
        for task_id in review_result.get("tasks_to_remove", []):
            self.task_manager.remove_task(task_id)
        
        # Modify tasks
        for mod in review_result.get("tasks_to_modify", []):
            updates = {}
            if mod.get("new_title"):
                updates["title"] = mod["new_title"]
            if mod.get("new_description"):
                updates["description"] = mod["new_description"]
            if updates:
                self.task_manager.update_task(mod["task_id"], **updates)
        
        # Add new tasks
        for new_task in review_result.get("new_tasks", []):
            if new_task.get("insert_after_task_id"):
                self.task_manager.insert_task_after(
                    new_task["insert_after_task_id"],
                    new_task["title"],
                    new_task["description"]
                )
            else:
                self.task_manager.add_task(
                    new_task["title"],
                    new_task["description"]
                )
    
    def get_task_explanation(self, task: Task, plan: Dict[str, Any]) -> str:
        """
        Generate a human-readable explanation of what will be done for a task.
        Used for the confirmation step.
        """
        if not plan.get("can_execute"):
            return f"""⚠️ **Cannot Execute Automatically**

**Task:** {task.title}

**Reason:** {plan.get('reasoning', 'No suitable tool available')}

**Suggestion:** {plan.get('alternative_approach', 'Manual intervention may be needed')}"""
        
        tool_name = plan.get("tool_name", "Unknown")
        category = plan.get("tool_category", "Unknown")
        params = plan.get("parameters", {})
        reasoning = plan.get("reasoning", "")
        
        params_str = "\n".join([f"  - {k}: {v}" for k, v in params.items()]) if params else "  None"
        
        return f"""🔧 **Ready to Execute**

**Task:** {task.title}

**Tool:** {category}/{tool_name}

**Parameters:**
{params_str}

**Reasoning:** {reasoning}"""
    
    def initialize_session(self, text: str) -> Tuple[TaskSession, List[Task]]:
        """
        Initialize a new session from user text.
        Parses the text and creates tasks.
        Sets up conversation context for maintaining state across executions.
        """
        # Create session
        session = self.task_manager.create_session(text)
        
        # Parse tasks from text
        parsed_tasks = self.parse_tasks_from_text(text)
        
        # Add tasks to session
        tasks = self.task_manager.add_tasks_batch(parsed_tasks)
        
        # Initialize conversation context for task execution
        # This allows the agent to remember previous task results
        self._init_conversation(text, tasks)
        
        self.task_manager.add_agent_note(
            f"Session initialized with {len(tasks)} tasks extracted from user input."
        )
        
        return session, tasks
    
    def process_next_task(self) -> Optional[Dict[str, Any]]:
        """
        Get the next task and prepare it for execution.
        Returns task info and execution plan for user confirmation.
        """
        task = self.task_manager.get_next_task()
        if not task:
            return None
        
        # Update status to in progress
        self.task_manager.update_task_status(task.id, TaskStatus.AWAITING_CONFIRMATION)
        
        # Plan execution
        plan = self.plan_task_execution(task)
        
        # Generate explanation
        explanation = self.get_task_explanation(task, plan)
        
        return {
            "task": task,
            "plan": plan,
            "explanation": explanation
        }
    
    def confirm_and_execute(self, task_id: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task after user confirmation.
        Results are added to conversation history for context in subsequent tasks.
        """
        task = self.task_manager.get_task_by_id(task_id)
        if not task:
            return {"success": False, "error": "Task not found"}
        
        # Update status
        self.task_manager.update_task_status(task.id, TaskStatus.IN_PROGRESS)
        
        # Execute
        result = self.execute_task(task, plan)
        
        # Update status based on result
        if result.get("success"):
            result_str = json.dumps(result.get("result", {}), indent=2)
            self.task_manager.update_task_status(
                task.id, 
                TaskStatus.COMPLETED,
                result=result_str
            )
        else:
            self.task_manager.update_task_status(
                task.id,
                TaskStatus.FAILED,
                error=result.get("error", "Unknown error")
            )
        
        # Add execution result to conversation history
        # This allows subsequent tasks to reference this result
        self._add_execution_result_to_history(task, result)
        
        # Review and potentially update task list
        review = self.review_and_update_tasks()
        
        return {
            "execution_result": result,
            "review": review
        }
    
    def skip_task(self, task_id: str) -> bool:
        """Mark a task as skipped."""
        task = self.task_manager.update_task_status(task_id, TaskStatus.SKIPPED)
        if task:
            self.task_manager.add_agent_note(f"Task '{task.title}' was skipped by user.")
            # Add skip info to conversation history
            if self._system_prompt:
                self._conversation_history.append({
                    "role": "user",
                    "content": f"TASK SKIPPED: {task.title} - User chose to skip this task."
                })
                self._conversation_history.append({
                    "role": "assistant", 
                    "content": f"Noted. Task '{task.title}' was skipped. Moving to the next task."
                })
            return True
        return False
    
    def restore_session_context(self) -> None:
        """
        Restore conversation context when loading an existing session.
        Rebuilds context from completed tasks.
        """
        session = self.task_manager.current_session
        if not session:
            return
        
        tasks = self.task_manager.get_all_tasks()
        
        # Initialize with current tasks
        self._init_conversation(session.original_text, tasks)
        
        # Replay completed task results into conversation history
        for task in tasks:
            if task.status == TaskStatus.COMPLETED and task.result:
                self._conversation_history.append({
                    "role": "user",
                    "content": f"TASK COMPLETED: {task.title}\nResult: {task.result}"
                })
                self._conversation_history.append({
                    "role": "assistant",
                    "content": f"Understood. Task '{task.title}' was previously completed."
                })
            elif task.status == TaskStatus.FAILED and task.error:
                self._conversation_history.append({
                    "role": "user",
                    "content": f"TASK FAILED: {task.title}\nError: {task.error}"
                })
                self._conversation_history.append({
                    "role": "assistant",
                    "content": f"Noted. Task '{task.title}' previously failed."
                })
            elif task.status == TaskStatus.SKIPPED:
                self._conversation_history.append({
                    "role": "user",
                    "content": f"TASK SKIPPED: {task.title}"
                })
                self._conversation_history.append({
                    "role": "assistant",
                    "content": f"Noted. Task '{task.title}' was skipped."
                })


def create_agent(
    storage_dir: str = "./task_data",
    tool_api_url: str = "http://localhost:9999"
) -> TaskAgent:
    """Factory function to create a fully configured agent."""
    task_manager = TaskManager(storage_dir)
    tool_client = ToolRegistryClient(tool_api_url)
    return TaskAgent(task_manager, tool_client)

