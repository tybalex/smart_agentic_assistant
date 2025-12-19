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
    WAITING_FOR_INPUT = "waiting_for_input"  # Executor called request_user_input() - needs user to provide input/decision
    AWAITING_RESPONSE = "awaiting_response"  # Executor stopped with message but didn't call explicit completion tool


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
class ActionExecution:
    """Record of a single executor action execution (one tool call)"""
    action_number: int  # Renamed from step_number to avoid confusion with workflow steps
    description: str
    status: ActionStatus
    timestamp: str
    reasoning: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Any] = None
    error: Optional[str] = None
    validation_results: List[Dict[str, Any]] = field(default_factory=list)


# The executor's last message contains any questions/context naturally


@dataclass
class ExecutionTrace:
    """Complete trace of workflow execution"""
    workflow_path: str
    session_id: str
    start_time: str
    status: SessionStatus
    end_time: Optional[str] = None
    actions: List[ActionExecution] = field(default_factory=list)  # Renamed from steps
    final_summary: Optional[str] = None
    
    def to_json(self) -> Dict[str, Any]:
        """Convert trace to JSON format"""
        return {
            "workflow_path": self.workflow_path,
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status.value,
            "actions": [
                {
                    "action_number": action.action_number,
                    "description": action.description,
                    "status": action.status.value,
                    "timestamp": action.timestamp,
                    "reasoning": action.reasoning,
                    "tool_calls": action.tool_calls,
                    "result": action.result,
                    "error": action.error,
                    "validation_results": action.validation_results,
                }
                for action in self.actions
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
