"""
Executor Agent Data Models
Simplified from task_agent - focused on workflow execution only.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SessionStatus(str, Enum):
    """Status of an execution session"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_CLARIFICATION = "needs_clarification"


class ActionStatus(str, Enum):
    """Status of an action execution"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ValidationCheck:
    """A validation check for a workflow step"""
    description: str
    field: Optional[str] = None  # Field to check in result
    expected_value: Optional[Any] = None
    check_type: str = "exists"  # exists, equals, contains, custom


@dataclass
class WorkflowStep:
    """A step in the workflow"""
    step_number: int
    description: str
    validations: List[ValidationCheck] = field(default_factory=list)
    requires_human_approval: bool = False


@dataclass
class StepExecution:
    """Record of a single step execution"""
    step_number: int
    description: str
    status: ActionStatus
    timestamp: str
    reasoning: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    validation_results: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ClarificationRequest:
    """A request for clarification from the executor"""
    question: str
    context: str
    step_number: Optional[int] = None


@dataclass
class ExecutionTrace:
    """Complete trace of workflow execution"""
    workflow_path: str
    session_id: str
    start_time: str
    status: SessionStatus
    end_time: Optional[str] = None
    steps: List[StepExecution] = field(default_factory=list)
    clarification_requests: List[ClarificationRequest] = field(default_factory=list)
    final_summary: Optional[str] = None
    
    def to_json(self) -> Dict[str, Any]:
        """Convert trace to JSON format"""
        return {
            "workflow_path": self.workflow_path,
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status.value,
            "steps": [
                {
                    "step_number": step.step_number,
                    "description": step.description,
                    "status": step.status.value,
                    "timestamp": step.timestamp,
                    "reasoning": step.reasoning,
                    "tool_calls": step.tool_calls,
                    "result": step.result,
                    "error": step.error,
                    "validation_results": step.validation_results,
                }
                for step in self.steps
            ],
            "clarification_requests": [
                {
                    "question": req.question,
                    "context": req.context,
                    "step_number": req.step_number,
                }
                for req in self.clarification_requests
            ],
            "final_summary": self.final_summary,
        }


@dataclass
class ToolConfig:
    """Configuration for available tools"""
    mcp_servers: List[str]
    tools: List[Dict[str, str]] = field(default_factory=list)
    version: str = "1.0"
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "ToolConfig":
        """Create from JSON data"""
        return cls(
            mcp_servers=data.get("mcp_servers", []),
            tools=data.get("tools", []),
            version=data.get("version", "1.0"),
        )


@dataclass
class TokenBudget:
    """Token budget tracking for execution"""
    max_tokens: int = 180000
    used_tokens: int = 0
    
    @property
    def exceeded(self) -> bool:
        """Check if budget exceeded"""
        return self.used_tokens >= self.max_tokens
    
    def add_tokens(self, tokens: int):
        """Add tokens to used count"""
        self.used_tokens += tokens
