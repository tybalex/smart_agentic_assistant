"""
Workflow Session Management
"""

import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import MAX_ITERATIONS


@dataclass
class Message:
    """A message in the conversation"""
    role: str  # "user" or "assistant"
    content: Any  # Can be string (simple text) or list of content blocks (with tool_use/tool_result)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    # Note: tool_calls and tool_results are now embedded in content blocks for proper API format
    # These fields are kept for backward compatibility but deprecated
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutionAttempt:
    """Record of a workflow execution attempt"""
    attempt_number: int
    timestamp: str
    status: str  # "completed", "failed", "needs_clarification"
    trace: Dict[str, Any]
    improvements_made: Optional[str] = None


@dataclass
class WorkflowSession:
    """
    Manages a workflow development session.
    Tracks conversation, executions, and iterations.
    """
    workflow_name: str
    workflow_path: Optional[str] = None
    tools_path: Optional[str] = None
    
    # Conversation history
    messages: List[Message] = field(default_factory=list)
    
    # Execution history
    execution_attempts: List[ExecutionAttempt] = field(default_factory=list)
    
    # Discovered tools (cached for session)
    available_tools: Optional[Dict[str, Any]] = None
    selected_tools: List[Dict[str, str]] = field(default_factory=list)
    
    # Tool approval workflow
    pending_assistant_content: Optional[List[Any]] = None  # Stores assistant message blocks awaiting tool execution
    pending_auto_results: Optional[List[Dict[str, Any]]] = None  # Stores auto-executed tool results to include with approved tools
    
    # Session metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    iteration_count: int = 0
    max_iterations: int = MAX_ITERATIONS
    
    def add_user_message(self, content: Any):
        """
        Add user message to conversation.
        
        Args:
            content: Either string (simple text) or list of content blocks (with tool_result blocks)
        """
        self.messages.append(Message(
            role="user",
            content=content
        ))
    
    def add_assistant_message(
        self,
        content: Any,
        tool_calls: List[Dict[str, Any]] = None,
        tool_results: List[Dict[str, Any]] = None
    ):
        """
        Add assistant message to conversation.
        
        Args:
            content: Either string (simple text) or list of content blocks (with tool_use blocks)
            tool_calls: DEPRECATED - kept for backward compatibility
            tool_results: DEPRECATED - kept for backward compatibility
        """
        self.messages.append(Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls or [],
            tool_results=tool_results or []
        ))
    
    def add_execution_attempt(
        self,
        status: str,
        trace: Dict[str, Any],
        improvements: Optional[str] = None
    ):
        """Record an execution attempt"""
        self.iteration_count += 1
        self.execution_attempts.append(ExecutionAttempt(
            attempt_number=self.iteration_count,
            timestamp=datetime.now().isoformat(),
            status=status,
            trace=trace,
            improvements_made=improvements
        ))
    
    def get_last_execution(self) -> Optional[ExecutionAttempt]:
        """Get most recent execution attempt"""
        if not self.execution_attempts:
            return None
        return self.execution_attempts[-1]
    
    def is_workflow_ready(self) -> bool:
        """Check if workflow is ready (successfully executed)"""
        last = self.get_last_execution()
        return last is not None and last.status == "completed"
    
    def can_iterate(self) -> bool:
        """Check if we can do more iterations"""
        return self.iteration_count < self.max_iterations
    
    def get_conversation_context(self) -> List[Dict[str, Any]]:
        """
        Get conversation history in Claude API format.
        
        Returns:
            List of {role, content} dicts where content can be:
            - string (simple text message)
            - list of content blocks (with tool_use/tool_result blocks)
        """
        context = []
        for msg in self.messages:
            context.append({
                "role": msg.role,
                "content": msg.content  # Already in proper format (string or list of blocks)
            })
        return context
    
    def summary(self) -> str:
        """Get session summary"""
        lines = [
            f"Workflow: {self.workflow_name}",
            f"Path: {self.workflow_path or 'Not created yet'}",
            f"Iterations: {self.iteration_count}/{self.max_iterations}",
            f"Messages: {len(self.messages)}",
        ]
        
        if self.execution_attempts:
            last = self.get_last_execution()
            lines.append(f"Last execution: {last.status}")
        
        if self.is_workflow_ready():
            lines.append("Status: ✅ Ready")
        elif not self.can_iterate():
            lines.append("Status: ⚠️  Max iterations reached")
        else:
            lines.append("Status: 🔄 In progress")
        
        return "\n".join(lines)
