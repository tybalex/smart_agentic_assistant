"""
Continuous Planning Agent powered by Claude.
Implements an adaptive planning loop that re-evaluates and updates plans each turn.
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from anthropic import Anthropic

from models import (
    Session, Goal, AgentState, Plan, PlanStep, Action,
    HistoryEntry, HistorySummary, TokenBudget, TurnResult, ExecutionResult,
    SessionStatus, StepStatus, TextSpan, generate_id,
    ClarificationQuestion, ClarificationAnswer, ClarificationEntry,
    RejectionFeedback, RejectionEntry
)
from session_manager import SessionManager
from tool_client import ToolRegistryClient
from constant import DEFAULT_MODEL, DEFAULT_TOOL_REGISTRY_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContinuousPlanningAgent:
    """
    AI Agent that continuously evaluates, plans, and executes.
    Each turn: Evaluate state → Update plan → Propose action → Execute with approval.
    """
    
    def __init__(
        self,
        session_manager: SessionManager,
        tool_client: ToolRegistryClient,
        model: str = DEFAULT_MODEL
    ):
        self.session_manager = session_manager
        self.tool_client = tool_client
        self.model = model
        
        # Check for API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.error("ANTHROPIC_API_KEY environment variable is not set!")
            logger.error("Please set it with: export ANTHROPIC_API_KEY='your-key-here'")
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Please set it before running the agent."
            )
        
        logger.info(f"Initializing Anthropic client with model: {model}")
        logger.info(f"API key found: {api_key[:8]}...{api_key[-4:]}")
        self.client = Anthropic(api_key=api_key)
        
        # Cache available tools
        self._tools_cache: Optional[str] = None
        # _tools_list removed - agent discovers tools on-demand via registry meta-tools
        self._available_categories: set = set()
        self._available_tools: Dict[str, bool] = {}
        
        # History summarization threshold
        self.max_history_entries = 10
        self.summarize_after = 7
    
    @property
    def current_session(self) -> Optional[Session]:
        return self.session_manager.current_session
    
    def _get_tools_context(self) -> str:
        """
        Get formatted context about available tools for the agent prompt.
        The agent only sees a lightweight summary, NOT all function definitions.
        
        Refreshes from registry every turn to get current state.
        """
        logger.info("Refreshing tools context from registry...")
        self._tools_cache = self.tool_client.get_tools_summary()
        
        # Also refresh validation cache (list of valid tool names)
        self._available_categories = set(self.tool_client.list_categories())
        self._available_tools = {}
        for cat in self._available_categories:
            funcs = self.tool_client.get_functions_by_category(cat)
            for func in funcs:
                if isinstance(func, str):
                    self._available_tools[f"{cat}/{func}"] = True
                else:
                    self._available_tools[f"{cat}/{func.get('name', '')}"] = True
        
        logger.info(f"Registry: {len(self._available_tools)} tools across {len(self._available_categories)} categories")
        return self._tools_cache
    
    def _validate_tool(self, category: str, tool_name: str) -> Tuple[bool, str]:
        """
        Validate that a tool exists in the registry.
        Returns (is_valid, error_message).
        """
        # Registry meta-tools are always valid
        if category == "registry" and tool_name in ["registry_search", "registry_list_category", "registry_get_function"]:
            return True, ""
        
        # Ensure tools are loaded
        self._get_tools_context()
        
        tool_key = f"{category}/{tool_name}"
        
        if category not in self._available_categories:
            return False, f"Category '{category}' does not exist in tool registry. Available categories: {list(self._available_categories)}"
        
        if tool_key not in self._available_tools:
            available_in_cat = [k.split('/')[1] for k in self._available_tools if k.startswith(f"{category}/")]
            return False, f"Tool '{tool_name}' does not exist in category '{category}'. Available tools: {available_in_cat}"
        
        return True, ""
    
    def _call_claude(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1
    ) -> Tuple[str, int]:
        """Make a call to Claude API. Returns (response, tokens_used)."""
        logger.info(f"Calling Claude API (model: {self.model})")
        logger.debug(f"System prompt length: {len(system_prompt)} chars")
        logger.debug(f"User message length: {len(user_message)} chars")
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=8192,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            
            # Estimate token usage
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            logger.info(f"Claude response received. Tokens used: {tokens_used}")
            
            return response.content[0].text, tokens_used
        except Exception as e:
            logger.error(f"Error calling Claude API: {e}")
            raise
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from Claude's response, handling markdown code blocks and extra text."""
        original_response = response  # Keep for debugging
        response = response.strip()
        
        # Log raw response for debugging
        logger.debug(f"Raw response to parse (first 500 chars): {response[:500]}")
        
        # Handle markdown code blocks - extract content between ```json and ```
        if "```json" in response:
            # Find the JSON block
            start = response.find("```json")
            if start != -1:
                start += len("```json")
                end = response.find("```", start)
                if end != -1:
                    response = response[start:end].strip()
                else:
                    response = response[start:].strip()
        elif "```" in response:
            # Generic code block - find content between first ``` and next ```
            parts = response.split("```")
            for part in parts[1:]:  # Skip anything before first ```
                # Remove language tag if present (e.g., "json\n")
                if part.strip().startswith("json"):
                    part = part.strip()[4:].strip()
                elif "\n" in part:
                    # Check if first line is a language tag
                    first_line, rest = part.split("\n", 1)
                    if first_line.strip().isalpha() and len(first_line.strip()) < 15:
                        part = rest
                if "{" in part:
                    response = part.strip()
                    break
        
        response = response.strip()
        
        # Try direct parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON object - find matching braces
        start_idx = response.find('{')
        if start_idx == -1:
            # Last resort: search in original response for any JSON object
            start_idx = original_response.find('{')
            if start_idx != -1:
                response = original_response[start_idx:]
            else:
                logger.error(f"No JSON object found in response. Full response: {original_response[:1000]}")
                raise json.JSONDecodeError("No JSON object found", response, 0)
        
        # Find the matching closing brace
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
    
    # ===================
    # Session Initialization
    # ===================
    
    def start_session(
        self,
        goal_text: str,
        max_tokens: int = 50000,
        max_turns: int = 20
    ) -> Session:
        """
        Start a new session with the user's goal.
        Creates initial plan and state.
        """
        # Create the session
        session = self.session_manager.create_session(
            goal_text=goal_text,
            max_tokens=max_tokens,
            max_turns=max_turns
        )
        
        # Generate initial plan and text spans
        self._generate_initial_plan(goal_text)
        
        self.session_manager.add_agent_note(
            f"Session started. Goal: {goal_text[:100]}..."
        )
        
        return session
    
    def _generate_initial_plan(self, goal_text: str) -> None:
        """Generate the initial plan and identify text spans."""
        logger.info("Generating initial plan...")
        logger.info(f"Goal: {goal_text[:100]}...")
        
        tools_context = self._get_tools_context()
        logger.debug(f"Tools context loaded: {len(tools_context)} chars")
        
        system_prompt = f"""You are a planning assistant. Your job is to create an initial plan for achieving the user's goal.

AVAILABLE TOOLS (from tool registry):
{tools_context}

CRITICAL CONSTRAINTS:
- You can ONLY use tools listed above from the tool registry
- DO NOT make up or invent tools that are not in the list
- DO NOT suggest making HTTP requests or API calls directly
- DO NOT suggest using any external services not in the tool registry
- If a required capability is not available in the tools, note it as a blocker

INSTRUCTIONS:
1. Break down the goal into actionable steps that can be accomplished with the AVAILABLE TOOLS ONLY
2. For each step, identify the EXACT text span in the original goal that it corresponds to
3. Order steps logically (dependencies first)
4. If a step cannot be done with available tools, mark it clearly and explain why

Your response must be valid JSON:
{{
    "state_summary": "Initial understanding of the goal...",
    "plan": [
        {{
            "description": "What this step accomplishes",
            "text_span": {{
                "start": <start char index>,
                "end": <end char index>,
                "text": "<exact text from goal>"
            }}
        }},
        ...
    ],
    "reasoning": "Why this plan makes sense...",
    "confidence": 0.0-1.0
}}

Only respond with JSON, no additional text."""

        user_message = f"""Create a plan for this goal:

---
{goal_text}
---

Remember to identify exact text spans for each step."""

        try:
            response, tokens = self._call_claude(system_prompt, user_message)
            self.session_manager.add_tokens_used(tokens)
            logger.info(f"Initial plan response received")
            
            data = self._parse_json_response(response)
            logger.info(f"Parsed plan with {len(data.get('plan', []))} steps")
            
            # Update state
            state = AgentState(
                summary=data.get("state_summary", "Analyzing goal..."),
                completed_objectives=[],
                blockers=[],
                context={}
            )
            self.session_manager.update_state(state)
            
            # Create plan
            self.session_manager.set_plan_from_data(
                plan_data=data.get("plan", []),
                reasoning=data.get("reasoning", ""),
                confidence=data.get("confidence", 0.5)
            )
            logger.info("Initial plan created successfully")
            
        except Exception as e:
            logger.error(f"Error generating initial plan: {e}", exc_info=True)
            # Create a basic single-step plan
            self.session_manager.set_plan_from_data(
                plan_data=[{"description": f"Complete: {goal_text[:100]}"}],
                reasoning="Fallback plan due to parsing error",
                confidence=0.3
            )
    
    # ===================
    # Main Planning Loop
    # ===================
    
    def run_turn(self) -> TurnResult:
        """
        Execute one turn of the continuous planning loop.
        
        1. Check budget
        2. Summarize history if needed
        3. Evaluate current state and update plan
        4. Auto-execute registry discovery tools (no approval needed)
        5. Propose next action (requires user approval)
        
        Returns TurnResult with proposed action for user approval.
        Registry tool calls are auto-executed and don't count as turns.
        """
        session = self.current_session
        if not session:
            return TurnResult(status="error", error="No active session")
        
        # Check budget
        if session.budget.exceeded:
            self.session_manager.set_session_status(SessionStatus.BUDGET_EXCEEDED)
            return TurnResult(
                status="budget_exceeded",
                session=session,
                error="Token or turn budget exceeded"
            )
        
        # Summarize history if needed
        if len(session.history) >= self.summarize_after:
            self._summarize_history()
        
        # Registry results from auto-executed discovery calls
        registry_results: List[Dict[str, Any]] = []
        max_registry_calls = 10  # Prevent infinite loops
        
        while len(registry_results) < max_registry_calls:
            # Evaluate and plan (pass registry results if any)
            evaluation = self._evaluate_and_plan(registry_results=registry_results)
            
            # Check if goal is achieved
            if evaluation.get("goal_achieved", False):
                self.session_manager.set_session_status(SessionStatus.COMPLETED)
                self.session_manager.add_agent_note("Goal achieved!")
                return TurnResult(
                    status="completed",
                    session=self.current_session,
                    goal_achieved=True,
                    reasoning=evaluation.get("reasoning", "All objectives completed.")
                )
            
            # Check for clarification question
            clarification_data = evaluation.get("clarification_question")
            if clarification_data and isinstance(clarification_data, dict) and clarification_data.get("question"):
                question = ClarificationQuestion(
                    id=generate_id(),
                    question=clarification_data.get("question", ""),
                    context=clarification_data.get("context", ""),
                    options=clarification_data.get("options", []),
                    related_step_id=clarification_data.get("related_step_id")
                )
                logger.info(f"Agent asking clarification: {question.question[:50]}...")
                return TurnResult(
                    status="needs_clarification",
                    session=self.current_session,
                    clarification_question=question,
                    reasoning=evaluation.get("reasoning", "Need more information to proceed.")
                )
            
            # Get proposed action
            action_data = evaluation.get("next_action")
            if not action_data:
                return TurnResult(
                    status="no_action",
                    session=self.current_session,
                    reasoning=evaluation.get("reasoning", "No suitable action available."),
                    error=evaluation.get("blocker")
                )
            
            # Check if this is a registry discovery tool - auto-execute!
            tool_category = action_data.get("tool_category", "")
            tool_name = action_data.get("tool_name", "")
            
            if tool_category == "registry" and tool_name in ["registry_search", "registry_list_category", "registry_get_function"]:
                # Auto-execute registry tool (no approval needed, doesn't count as turn)
                logger.info(f"Auto-executing registry tool: {tool_name}")
                result = self._execute_registry_tool(tool_name, action_data.get("parameters", {}))
                
                registry_results.append({
                    "tool": tool_name,
                    "params": action_data.get("parameters", {}),
                    "result": result
                })
                logger.info(f"Registry call #{len(registry_results)} completed, continuing evaluation...")
                continue  # Loop back to evaluate with new info
            
            # Non-registry action - return for user approval
            action = Action(
                id=generate_id(),
                plan_step_id=action_data.get("plan_step_id", ""),
                tool_category=tool_category,
                tool_name=tool_name,
                parameters=action_data.get("parameters", {}),
                reasoning=action_data.get("reasoning", evaluation.get("reasoning", ""))
            )
            
            return TurnResult(
                status="awaiting_approval",
                session=self.current_session,
                proposed_action=action,
                reasoning=evaluation.get("reasoning", "")
            )
        
        # Safety: too many registry calls
        logger.warning(f"Max registry calls ({max_registry_calls}) reached")
        return TurnResult(
            status="error",
            session=self.current_session,
            error=f"Agent made too many registry discovery calls ({max_registry_calls}). May be stuck in a loop."
        )
    
    def _evaluate_and_plan(self, registry_results: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Core evaluation: assess current state, update plan, propose action.
        
        Args:
            registry_results: Results from auto-executed registry discovery calls (if any)
        """
        logger.info("Starting evaluation and planning...")
        
        session = self.current_session
        if not session:
            logger.error("No active session for evaluation")
            return {"goal_achieved": False, "error": "No session"}
        
        logger.info(f"Session: {session.id}, Turn: {session.budget.current_turn}")
        tools_context = self._get_tools_context()
        
        # Format current plan
        plan_str = self._format_plan(session.plan)
        
        # Format history
        history_str = self._format_history(session.history, session.history_summaries)
        
        # Include clarifications and rejections in context
        clarifications_str = self._format_clarifications(session.clarifications)
        rejections_str = self._format_rejections(session.rejections)
        
        # Format registry discovery results (from auto-executed calls this turn)
        registry_str = self._format_registry_results(registry_results or [])
        
        system_prompt = f"""You are a continuous planning agent. Each turn, you evaluate the situation and decide the next action OR ask the user a clarification question.

AVAILABLE TOOLS (from tool registry):
{tools_context}

CRITICAL CONSTRAINTS - YOU MUST FOLLOW THESE:
- You can ONLY use tools listed above from the tool registry
- DO NOT make up, invent, or hallucinate tools that are not in the list above
- DO NOT suggest making direct HTTP requests, API calls, or web requests
- DO NOT suggest using external services, websites, or APIs not in the tool registry
- If the next step requires a capability not in the available tools, set "next_action" to null and explain in "blockers"
- Every tool_category and tool_name you propose MUST exist in the AVAILABLE TOOLS list above
- PARAMETER NAMES MUST MATCH EXACTLY as shown in the tool registry (e.g., if registry shows "data", use "data" NOT "fields")

REGISTRY DISCOVERY TOOLS (auto-executed, no approval needed):
- registry/registry_search: Search for functions by keyword - USE THIS to find functions
- registry/registry_list_category: List all functions in a category
- registry/registry_get_function: Get full details of a specific function (ALWAYS use before calling a function!)
These tools are executed automatically without user approval. Use them freely to discover what functions are available and their exact parameter names BEFORE proposing an actual action.

YOUR RESPONSIBILITIES:
1. Evaluate progress toward the goal
2. Update the plan if needed (add/remove/reorder steps)
3. DECIDE: Either propose ONE action OR ask a clarification question
   - Propose an ACTION if you have enough information to proceed confidently
   - Ask a CLARIFICATION QUESTION if:
     * Information is ambiguous or incomplete
     * Multiple valid interpretations exist
     * Making an assumption could lead to wrong results
     * User preferences are needed for a decision
4. If the goal is fully achieved, indicate so
5. If stuck due to missing tools, explain clearly

IMPORTANT:
- Never lose sight of the original goal
- Use results from previous actions to inform decisions
- If stuck, explain what's blocking progress
- Use EXACT parameter names as listed in AVAILABLE TOOLS - do not rename or remap parameters
- ONLY use tools that exist in the registry - verify before proposing
- WHEN UNCERTAIN, ASK - don't make assumptions that could waste time or cause errors"""

        user_message = f"""GOAL (your primary objective):
{session.goal.original_text}

CURRENT STATE:
{session.state.summary}
Completed: {json.dumps(session.state.completed_objectives)}
Blockers: {json.dumps(session.state.blockers)}

CURRENT PLAN:
{plan_str}

EXECUTION HISTORY:
{history_str}

PREVIOUS CLARIFICATIONS (user answered questions):
{clarifications_str}

REJECTED ACTIONS (user rejected with feedback - DO NOT repeat these mistakes):
{rejections_str}

REGISTRY DISCOVERY RESULTS (from auto-executed calls this turn):
{registry_str}

---

Evaluate the situation and respond with JSON:
{{
    "goal_achieved": true/false,
    "state_summary": "Updated understanding of the situation...",
    "completed_objectives": ["objective 1", ...],
    "blockers": ["any issues..."],
    "plan_updates": {{
        "add_steps": [{{"description": "...", "after_step_id": "..." or null}}],
        "remove_step_ids": ["step_id", ...],
        "update_steps": [{{"step_id": "...", "new_description": "..."}}]
    }},
    
    // CHOOSE ONE: Either "next_action" OR "clarification_question", NOT BOTH
    
    "next_action": {{
        "plan_step_id": "which step this fulfills",
        "tool_category": "category",
        "tool_name": "function_name",
        "parameters": {{...use EXACT parameter names from tool registry...}},
        "reasoning": "why this action now"
    }} or null if asking question or goal achieved or stuck,
    
    "clarification_question": {{
        "question": "What specific information do you need?",
        "context": "Why you need this information",
        "options": ["Option A", "Option B"] or [],
        "related_step_id": "step_id this relates to" or null
    }} or null if taking action,
    
    "reasoning": "overall analysis..."
}}

REMINDER: 
- When specifying "parameters", use the EXACT parameter names shown in AVAILABLE TOOLS.
- If you need clarification from the user, set "next_action" to null and provide "clarification_question".
- If you have enough info to proceed, set "clarification_question" to null and provide "next_action".
- Don't ask unnecessary questions - only ask when genuinely uncertain about something important.
- If the user's answer to a previous clarification is itself a question or challenge, you should ask another clarification question to address their concern.
- ALWAYS respond with valid JSON - never respond with plain text."""

        try:
            response, tokens = self._call_claude(system_prompt, user_message)
            self.session_manager.add_tokens_used(tokens)
            logger.info("Evaluation response received")
            
            data = self._parse_json_response(response)
            logger.info(f"Goal achieved: {data.get('goal_achieved', False)}")
            next_action = data.get('next_action') or {}  # Handle explicit null
            logger.debug(f"Next action: {next_action.get('tool_name', 'None')}")
            
            # Update state
            new_state = AgentState(
                summary=data.get("state_summary", session.state.summary),
                completed_objectives=data.get("completed_objectives", session.state.completed_objectives),
                blockers=data.get("blockers", []),
                context=session.state.context
            )
            self.session_manager.update_state(new_state)
            
            # Apply plan updates
            self._apply_plan_updates(data.get("plan_updates", {}))
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing evaluation response: {e}")
            # Log the raw response that failed to parse
            raw_resp = "N/A"
            try:
                raw_resp = response[:1000] if response else "EMPTY RESPONSE"
                logger.error(f"Raw response that failed to parse: {raw_resp}")
            except:
                logger.error("Could not log raw response")
            
            # Return error but keep going - maybe Claude responded conversationally
            return {
                "goal_achieved": False,
                "error": f"AI response was not valid JSON. Claude said: '{raw_resp[:200]}...'",
                "reasoning": "The AI responded conversationally instead of JSON. Please try again."
            }
        except Exception as e:
            logger.error(f"Error in evaluation: {e}", exc_info=True)
            return {
                "goal_achieved": False,
                "error": str(e),
                "reasoning": f"Error during evaluation: {e}"
            }
    
    def _apply_plan_updates(self, updates: Dict[str, Any]) -> None:
        """Apply plan updates from evaluation."""
        if not updates:
            return
        
        # Remove steps
        for step_id in updates.get("remove_step_ids", []):
            self.session_manager.remove_plan_step(step_id)
        
        # Update steps
        for update in updates.get("update_steps", []):
            step_id = update.get("step_id")
            if step_id:
                for step in self.current_session.plan.steps:
                    if step.id == step_id:
                        step.description = update.get("new_description", step.description)
                        break
        
        # Add steps
        for new_step in updates.get("add_steps", []):
            self.session_manager.add_plan_step(
                description=new_step.get("description", ""),
                after_step_id=new_step.get("after_step_id")
            )
        
        self.session_manager.save_session()
    
    def _format_plan(self, plan: Plan) -> str:
        """Format plan for prompt."""
        if not plan.steps:
            return "No plan yet."
        
        lines = []
        for i, step in enumerate(plan.steps):
            status_icon = {
                StepStatus.PLANNED: "⬜",
                StepStatus.IN_PROGRESS: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️"
            }.get(step.status, "⬜")
            
            line = f"{i+1}. [{step.id}] {status_icon} {step.description}"
            if step.result:
                line += f"\n   Result: {step.result[:100]}..."
            if step.error:
                line += f"\n   Error: {step.error}"
            lines.append(line)
        
        return "\n".join(lines)
    
    def _format_history(
        self,
        history: List[HistoryEntry],
        summaries: List[HistorySummary]
    ) -> str:
        """Format execution history for prompt."""
        parts = []
        
        # Include summaries of older history
        for summary in summaries:
            parts.append(f"[Summary of turns 1-{summary.turns_covered}]")
            parts.append(summary.summary_text)
            parts.append("")
        
        # Include recent history
        for entry in history[-5:]:  # Last 5 entries
            parts.append(f"Turn {entry.turn}: {entry.action.tool_category}/{entry.action.tool_name}")
            parts.append(f"  Params: {json.dumps(entry.action.parameters)}")
            if entry.result.get("success"):
                result_str = json.dumps(entry.result.get("result", {}))
                if len(result_str) > 200:
                    result_str = result_str[:200] + "..."
                parts.append(f"  Result: {result_str}")
            else:
                parts.append(f"  Error: {entry.result.get('error', 'Unknown')}")
            parts.append("")
        
        return "\n".join(parts) if parts else "No history yet."
    
    def _format_clarifications(self, clarifications: List[ClarificationEntry]) -> str:
        """Format clarification Q&A history for prompt."""
        if not clarifications:
            return "No previous clarifications."
        
        parts = []
        for entry in clarifications[-5:]:  # Last 5 Q&As
            parts.append(f"Q (Turn {entry.turn}): {entry.question.question}")
            if entry.question.options:
                parts.append(f"  Options given: {entry.question.options}")
            parts.append(f"A: {entry.answer.answer}")
            parts.append("")
        
        return "\n".join(parts)
    
    def _format_rejections(self, rejections: List[RejectionEntry]) -> str:
        """Format rejection feedback history for prompt."""
        if not rejections:
            return "No previous rejections."
        
        parts = []
        for entry in rejections[-3:]:  # Last 3 rejections
            action = entry.rejection.rejected_action
            parts.append(f"Turn {entry.turn}: User REJECTED action {action.tool_category}/{action.tool_name}")
            parts.append(f"  User's feedback: {entry.rejection.feedback}")
            parts.append("")
        
        return "\n".join(parts)
    
    def _format_registry_results(self, registry_results: List[Dict[str, Any]]) -> str:
        """Format auto-executed registry discovery results for prompt."""
        if not registry_results:
            return "No registry calls made this turn. Use registry tools to discover available functions."
        
        parts = []
        for i, call in enumerate(registry_results, 1):
            tool = call.get("tool", "unknown")
            params = call.get("params", {})
            result = call.get("result", {})
            
            parts.append(f"Call #{i}: {tool}({json.dumps(params)})")
            
            if result.get("success"):
                result_data = result.get("result", {})
                
                # Format search results more concisely
                if tool == "registry_search" and "results" in result_data:
                    functions = result_data.get("results", [])
                    total = result_data.get("total", len(functions))
                    parts.append(f"  Found {total} functions:")
                    # Show up to 15 results with key info
                    for func in functions[:15]:
                        name = func.get("name", "?")
                        desc = func.get("description", "")[:60]
                        cat = func.get("category", "?")
                        parts.append(f"    - {cat}/{name}: {desc}")
                    if total > 15:
                        parts.append(f"    ... and {total - 15} more")
                
                # Format category listing concisely
                elif tool == "registry_list_category" and "functions" in result_data:
                    functions = result_data.get("functions", [])
                    total = result_data.get("total", len(functions))
                    parts.append(f"  Category has {total} functions:")
                    for func in functions[:15]:
                        name = func.get("name", "?")
                        desc = func.get("description", "")[:60]
                        parts.append(f"    - {name}: {desc}")
                    if total > 15:
                        parts.append(f"    ... and {total - 15} more")
                
                # Format single function details fully (this is what agent needs)
                elif tool == "registry_get_function":
                    parts.append(f"  Function details:")
                    parts.append(f"    Name: {result_data.get('name')}")
                    parts.append(f"    Category: {result_data.get('category')}")
                    parts.append(f"    Description: {result_data.get('description')}")
                    params_info = result_data.get("parameters", {})
                    if params_info:
                        parts.append(f"    Parameters:")
                        for pname, pinfo in params_info.items():
                            ptype = pinfo.get("type", "any") if isinstance(pinfo, dict) else "any"
                            required = pinfo.get("required", False) if isinstance(pinfo, dict) else False
                            default = pinfo.get("default") if isinstance(pinfo, dict) else None
                            req_str = " (REQUIRED)" if required else f" (optional, default={default})"
                            parts.append(f"      - {pname}: {ptype}{req_str}")
                
                else:
                    # Generic formatting for other results
                    result_str = json.dumps(result_data, indent=2)
                    if len(result_str) > 1000:
                        result_str = result_str[:1000] + "\n... (truncated)"
                    parts.append(f"  Result: {result_str}")
            else:
                parts.append(f"  Error: {result.get('error', 'Unknown error')}")
            parts.append("")
        
        return "\n".join(parts)
    
    # ===================
    # Action Execution
    # ===================
    
    def _execute_registry_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a registry meta-tool (search, list_category, get_function).
        These tools help the agent discover available functions without loading all of them.
        """
        logger.info(f"Executing registry meta-tool: {tool_name} with params: {parameters}")
        
        if tool_name == "registry_search":
            q = parameters.get("q", "")
            if not q:
                return {"success": False, "error": "Missing required parameter 'q' for registry_search"}
            return self.tool_client.registry_search(q)
        
        elif tool_name == "registry_list_category":
            category = parameters.get("category", "")
            if not category:
                return {"success": False, "error": "Missing required parameter 'category' for registry_list_category"}
            return self.tool_client.registry_list_category(category)
        
        elif tool_name == "registry_get_function":
            function_name = parameters.get("function_name", "")
            if not function_name:
                return {"success": False, "error": "Missing required parameter 'function_name' for registry_get_function"}
            return self.tool_client.registry_get_function(function_name)
        
        else:
            return {"success": False, "error": f"Unknown registry tool: {tool_name}"}
    
    def execute_action(self, action: Action) -> ExecutionResult:
        """
        Execute an approved action and update session state.
        Validates that the tool exists in the registry before execution.
        """
        session = self.current_session
        if not session:
            return ExecutionResult(success=False, error="No active session")
        
        # IMPORTANT: Validate that the tool exists in the registry
        is_valid, error_msg = self._validate_tool(action.tool_category, action.tool_name)
        if not is_valid:
            logger.error(f"Tool validation failed: {error_msg}")
            # Update step status to failed
            if action.plan_step_id:
                self.session_manager.update_step_status(
                    action.plan_step_id,
                    StepStatus.FAILED,
                    error=f"Invalid tool: {error_msg}"
                )
            return ExecutionResult(
                success=False, 
                error=f"Tool validation failed: {error_msg}. Only tools from the registry can be used."
            )
        
        logger.info(f"Executing validated tool: {action.tool_category}/{action.tool_name}")
        
        # Mark the corresponding plan step as in progress
        if action.plan_step_id:
            self.session_manager.update_step_status(
                action.plan_step_id,
                StepStatus.IN_PROGRESS,
                tool_used=f"{action.tool_category}/{action.tool_name}",
                tool_params=action.parameters
            )
        
        # Handle registry meta-tools specially
        if action.tool_category == "registry":
            result = self._execute_registry_tool(action.tool_name, action.parameters)
        else:
            # Execute the tool via registry API
            result = self.tool_client.execute_function(
                action.tool_category,
                action.tool_name,
                action.parameters
            )
        
        # Update plan step status based on result
        if action.plan_step_id:
            if result.get("success"):
                result_str = json.dumps(result.get("result", {}))
                self.session_manager.update_step_status(
                    action.plan_step_id,
                    StepStatus.COMPLETED,
                    result=result_str
                )
            else:
                self.session_manager.update_step_status(
                    action.plan_step_id,
                    StepStatus.FAILED,
                    error=result.get("error", "Unknown error")
                )
        
        # Add to history
        self.session_manager.add_history_entry(action, result)
        
        # Increment turn counter
        self.session_manager.increment_turn()
        
        # Estimate tokens for the result (rough estimate)
        result_tokens = len(json.dumps(result)) // 4
        self.session_manager.add_tokens_used(result_tokens)
        
        return ExecutionResult(
            success=result.get("success", False),
            data=result,
            error=result.get("error"),
            tokens_used=result_tokens
        )
    
    def skip_action(self, action: Action) -> None:
        """Mark the action's plan step as skipped."""
        if action.plan_step_id:
            self.session_manager.update_step_status(
                action.plan_step_id,
                StepStatus.SKIPPED
            )
        self.session_manager.add_agent_note(f"Action skipped: {action.tool_name}")
        self.session_manager.increment_turn()
    
    # ===================
    # Clarification Handling
    # ===================
    
    def provide_clarification(
        self,
        question: ClarificationQuestion,
        answer: str
    ) -> None:
        """
        Process user's answer to a clarification question.
        Stores the Q&A in session history for future reference.
        """
        session = self.current_session
        if not session:
            logger.error("No active session for clarification")
            return
        
        # Create answer object
        clarification_answer = ClarificationAnswer(
            question_id=question.id,
            answer=answer
        )
        
        # Store in session
        self.session_manager.add_clarification(question, clarification_answer)
        
        # Log it
        logger.info(f"Clarification received - Q: {question.question[:50]}... A: {answer[:50]}...")
        self.session_manager.add_agent_note(
            f"User clarification: '{question.question[:30]}...' -> '{answer[:50]}...'"
        )
        
        # Increment turn for the clarification exchange
        self.session_manager.increment_turn()
    
    def reject_action(self, action: Action, feedback: str) -> None:
        """
        Process user's rejection of a proposed action with feedback.
        Stores the rejection for the agent to consider in the next turn.
        """
        session = self.current_session
        if not session:
            logger.error("No active session for rejection")
            return
        
        # Create rejection feedback object
        rejection = RejectionFeedback(
            id=generate_id(),
            rejected_action=action,
            feedback=feedback
        )
        
        # Store in session
        self.session_manager.add_rejection(rejection)
        
        # Mark the step as needing revision (back to planned)
        if action.plan_step_id:
            self.session_manager.update_step_status(
                action.plan_step_id,
                StepStatus.PLANNED  # Reset to planned so agent can retry
            )
        
        # Log it
        logger.info(f"Action rejected - {action.tool_name}: {feedback[:50]}...")
        self.session_manager.add_agent_note(
            f"User rejected '{action.tool_name}': {feedback[:50]}..."
        )
        
        # Increment turn
        self.session_manager.increment_turn()
    
    # ===================
    # History Summarization
    # ===================
    
    def _summarize_history(self) -> None:
        """Summarize old history to manage context length."""
        session = self.current_session
        if not session or len(session.history) < self.summarize_after:
            return
        
        # Get entries to summarize (all but the last few)
        entries_to_summarize = session.history[:-3]
        if not entries_to_summarize:
            return
        
        # Format for summarization
        history_text = []
        for entry in entries_to_summarize:
            history_text.append(
                f"Turn {entry.turn}: {entry.action.tool_name} -> "
                f"{'Success' if entry.result.get('success') else 'Failed'}"
            )
        
        system_prompt = """You are a summarization assistant. Summarize the execution history concisely.
Focus on:
1. What actions were taken
2. Key results and outcomes
3. Any failures or issues encountered

Keep it brief but capture essential information for continuing the task."""

        user_message = f"""Summarize this execution history:

{chr(10).join(history_text)}

Respond with JSON:
{{
    "summary": "Concise summary...",
    "key_results": ["result 1", "result 2", ...]
}}"""

        try:
            response, tokens = self._call_claude(system_prompt, user_message, temperature=0.2)
            self.session_manager.add_tokens_used(tokens)
            
            data = self._parse_json_response(response)
            
            summary = HistorySummary(
                summary_text=data.get("summary", "Previous actions completed."),
                turns_covered=len(entries_to_summarize),
                key_results=data.get("key_results", []),
                created_at=datetime.now()
            )
            
            self.session_manager.add_history_summary(summary)
            self.session_manager.clear_old_history(keep_recent=3)
            
        except Exception as e:
            print(f"Error summarizing history: {e}")
    
    # ===================
    # Utility Methods
    # ===================
    
    def get_action_explanation(self, action: Action) -> str:
        """Generate a human-readable explanation of the proposed action."""
        if not action:
            return "No action proposed."
        
        params_str = "\n".join([
            f"  - {k}: {v}" for k, v in action.parameters.items()
        ]) if action.parameters else "  None"
        
        return f"""🔧 **Proposed Action**

**Tool:** {action.tool_category}/{action.tool_name}

**Parameters:**
{params_str}

**Reasoning:** {action.reasoning}"""
    
    def abort_session(self) -> None:
        """Abort the current session."""
        self.session_manager.abort_session()
        self.session_manager.add_agent_note("Session aborted by user.")
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """Load an existing session."""
        return self.session_manager.load_session(session_id)


def create_agent(
    storage_dir: str = "./task_data",
    tool_api_url: str = DEFAULT_TOOL_REGISTRY_URL
) -> ContinuousPlanningAgent:
    """Factory function to create a fully configured agent."""
    session_manager = SessionManager(storage_dir)
    tool_client = ToolRegistryClient(tool_api_url)
    return ContinuousPlanningAgent(session_manager, tool_client)


# Backwards compatibility
TaskAgent = ContinuousPlanningAgent
