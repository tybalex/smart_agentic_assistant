"""
Data models for the Continuous Planning Agent system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())[:8]


class StepStatus(Enum):
    """Status of a plan step."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class SessionStatus(Enum):
    """Status of the overall session."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"
    BUDGET_EXCEEDED = "budget_exceeded"


@dataclass
class TextSpan:
    """
    Represents a span of text in the original input.
    Used for mapping plan steps back to source text for highlighting.
    """
    start: int  # Start character index
    end: int    # End character index
    text: str   # The actual text content
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextSpan":
        return cls(
            start=data["start"],
            end=data["end"],
            text=data["text"]
        )


@dataclass
class Goal:
    """
    The original user objective - immutable throughout the session.
    This is what the agent should never lose sight of.
    """
    id: str
    original_text: str
    text_spans: List[TextSpan] = field(default_factory=list)  # For highlighting different parts
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "original_text": self.original_text,
            "text_spans": [ts.to_dict() for ts in self.text_spans],
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        return cls(
            id=data["id"],
            original_text=data["original_text"],
            text_spans=[TextSpan.from_dict(ts) for ts in data.get("text_spans", [])],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        )


@dataclass
class PlanStep:
    """A single step in the plan."""
    id: str
    description: str
    status: StepStatus = StepStatus.PLANNED
    text_span: Optional[TextSpan] = None  # Links to original goal text
    result: Optional[str] = None
    error: Optional[str] = None
    tool_used: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "text_span": self.text_span.to_dict() if self.text_span else None,
            "result": self.result,
            "error": self.error,
            "tool_used": self.tool_used,
            "tool_params": self.tool_params
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanStep":
        return cls(
            id=data["id"],
            description=data["description"],
            status=StepStatus(data["status"]),
            text_span=TextSpan.from_dict(data["text_span"]) if data.get("text_span") else None,
            result=data.get("result"),
            error=data.get("error"),
            tool_used=data.get("tool_used"),
            tool_params=data.get("tool_params")
        )


@dataclass
class Plan:
    """
    Current plan - can change each turn.
    The agent updates this based on progress and new information.
    """
    steps: List[PlanStep] = field(default_factory=list)
    reasoning: str = ""  # Why this plan
    confidence: float = 0.5  # 0-1, how confident agent is
    last_updated: datetime = field(default_factory=datetime.now)
    
    def get_current_step(self) -> Optional[PlanStep]:
        """Get the step currently in progress."""
        for step in self.steps:
            if step.status == StepStatus.IN_PROGRESS:
                return step
        return None
    
    def get_next_planned_step(self) -> Optional[PlanStep]:
        """Get the next planned (not yet started) step."""
        for step in self.steps:
            if step.status == StepStatus.PLANNED:
                return step
        return None
    
    def get_completed_steps(self) -> List[PlanStep]:
        """Get all completed steps."""
        return [s for s in self.steps if s.status == StepStatus.COMPLETED]
    
    def get_progress(self) -> Dict[str, int]:
        """Get plan progress statistics."""
        stats = {
            "total": len(self.steps),
            "completed": 0,
            "planned": 0,
            "in_progress": 0,
            "failed": 0,
            "skipped": 0
        }
        for step in self.steps:
            if step.status == StepStatus.COMPLETED:
                stats["completed"] += 1
            elif step.status == StepStatus.PLANNED:
                stats["planned"] += 1
            elif step.status == StepStatus.IN_PROGRESS:
                stats["in_progress"] += 1
            elif step.status == StepStatus.FAILED:
                stats["failed"] += 1
            elif step.status == StepStatus.SKIPPED:
                stats["skipped"] += 1
        return stats
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "last_updated": self.last_updated.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Plan":
        return cls(
            steps=[PlanStep.from_dict(s) for s in data.get("steps", [])],
            reasoning=data.get("reasoning", ""),
            confidence=data.get("confidence", 0.5),
            last_updated=datetime.fromisoformat(data["last_updated"]) if data.get("last_updated") else datetime.now()
        )


@dataclass
class AgentState:
    """
    Agent's current understanding - updated each turn.
    This captures what the agent knows about the situation.
    """
    summary: str = ""  # What the agent understands about current situation
    completed_objectives: List[str] = field(default_factory=list)  # Which parts of the goal are done
    blockers: List[str] = field(default_factory=list)  # Any issues encountered
    context: Dict[str, Any] = field(default_factory=dict)  # Relevant data from previous actions
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "completed_objectives": self.completed_objectives,
            "blockers": self.blockers,
            "context": self.context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        return cls(
            summary=data.get("summary", ""),
            completed_objectives=data.get("completed_objectives", []),
            blockers=data.get("blockers", []),
            context=data.get("context", {})
        )


@dataclass
class Action:
    """The single action proposed for the current turn."""
    id: str
    plan_step_id: str  # Which plan step this fulfills
    tool_category: str
    tool_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""  # Why this action now
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "plan_step_id": self.plan_step_id,
            "tool_category": self.tool_category,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "reasoning": self.reasoning
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        return cls(
            id=data["id"],
            plan_step_id=data["plan_step_id"],
            tool_category=data["tool_category"],
            tool_name=data["tool_name"],
            parameters=data.get("parameters", {}),
            reasoning=data.get("reasoning", "")
        )


@dataclass
class ClarificationQuestion:
    """A question the agent asks the user for clarification."""
    id: str
    question: str  # The question text
    context: str  # Why the agent is asking
    options: List[str] = field(default_factory=list)  # Optional: suggested answers
    related_step_id: Optional[str] = None  # Which plan step this relates to
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "context": self.context,
            "options": self.options,
            "related_step_id": self.related_step_id,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClarificationQuestion":
        return cls(
            id=data["id"],
            question=data["question"],
            context=data.get("context", ""),
            options=data.get("options", []),
            related_step_id=data.get("related_step_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        )


@dataclass
class ClarificationAnswer:
    """User's answer to a clarification question."""
    question_id: str
    answer: str
    answered_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "answer": self.answer,
            "answered_at": self.answered_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClarificationAnswer":
        return cls(
            question_id=data["question_id"],
            answer=data["answer"],
            answered_at=datetime.fromisoformat(data["answered_at"]) if data.get("answered_at") else datetime.now()
        )


@dataclass
class ClarificationEntry:
    """A Q&A pair in the session history."""
    turn: int
    question: ClarificationQuestion
    answer: ClarificationAnswer
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "question": self.question.to_dict(),
            "answer": self.answer.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClarificationEntry":
        return cls(
            turn=data["turn"],
            question=ClarificationQuestion.from_dict(data["question"]),
            answer=ClarificationAnswer.from_dict(data["answer"])
        )


@dataclass
class RejectionFeedback:
    """User's rejection of a proposed action with feedback."""
    id: str
    rejected_action: Action  # The action that was rejected
    feedback: str  # User's instructions/reason
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rejected_action": self.rejected_action.to_dict(),
            "feedback": self.feedback,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RejectionFeedback":
        return cls(
            id=data["id"],
            rejected_action=Action.from_dict(data["rejected_action"]),
            feedback=data["feedback"],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        )


@dataclass
class RejectionEntry:
    """A rejection record in the session history."""
    turn: int
    rejection: RejectionFeedback
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "rejection": self.rejection.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RejectionEntry":
        return cls(
            turn=data["turn"],
            rejection=RejectionFeedback.from_dict(data["rejection"])
        )


@dataclass
class HistoryEntry:
    """A single entry in the execution history."""
    turn: int
    action: Action
    result: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn": self.turn,
            "action": self.action.to_dict(),
            "result": self.result,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        return cls(
            turn=data["turn"],
            action=Action.from_dict(data["action"]),
            result=data["result"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now()
        )


@dataclass
class HistorySummary:
    """Summarized history when full history gets too long."""
    summary_text: str
    turns_covered: int  # How many turns this summary covers
    key_results: List[str] = field(default_factory=list)  # Important outcomes
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_text": self.summary_text,
            "turns_covered": self.turns_covered,
            "key_results": self.key_results,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistorySummary":
        return cls(
            summary_text=data["summary_text"],
            turns_covered=data["turns_covered"],
            key_results=data.get("key_results", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now()
        )


@dataclass
class TokenBudget:
    """Track costs and prevent runaway execution."""
    max_tokens: int = 150000  # Maximum tokens to use
    used_tokens: int = 0
    max_turns: int = 50  # Maximum turns allowed
    current_turn: int = 0
    
    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.used_tokens)
    
    @property
    def remaining_turns(self) -> int:
        return max(0, self.max_turns - self.current_turn)
    
    @property
    def exceeded(self) -> bool:
        return self.used_tokens >= self.max_tokens or self.current_turn >= self.max_turns
    
    @property
    def token_percentage(self) -> float:
        return (self.used_tokens / self.max_tokens) * 100 if self.max_tokens > 0 else 0
    
    @property
    def turn_percentage(self) -> float:
        return (self.current_turn / self.max_turns) * 100 if self.max_turns > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_tokens": self.max_tokens,
            "used_tokens": self.used_tokens,
            "max_turns": self.max_turns,
            "current_turn": self.current_turn
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenBudget":
        return cls(
            max_tokens=data.get("max_tokens", 50000),
            used_tokens=data.get("used_tokens", 0),
            max_turns=data.get("max_turns", 20),
            current_turn=data.get("current_turn", 0)
        )


@dataclass
class Session:
    """Complete session state - the main container for all agent state."""
    id: str
    goal: Goal
    state: AgentState = field(default_factory=AgentState)
    plan: Plan = field(default_factory=Plan)
    history: List[HistoryEntry] = field(default_factory=list)
    history_summaries: List[HistorySummary] = field(default_factory=list)  # Compressed old history
    clarifications: List[ClarificationEntry] = field(default_factory=list)  # Q&A history
    rejections: List[RejectionEntry] = field(default_factory=list)  # Rejected actions with feedback
    budget: TokenBudget = field(default_factory=TokenBudget)
    status: SessionStatus = SessionStatus.ACTIVE
    agent_notes: List[str] = field(default_factory=list)  # Agent observations
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def get_progress(self) -> Dict[str, Any]:
        """Get overall session progress."""
        plan_progress = self.plan.get_progress()
        return {
            **plan_progress,
            "turn": self.budget.current_turn,
            "max_turns": self.budget.max_turns,
            "tokens_used": self.budget.used_tokens,
            "tokens_max": self.budget.max_tokens,
            "status": self.status.value
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal.to_dict(),
            "state": self.state.to_dict(),
            "plan": self.plan.to_dict(),
            "history": [h.to_dict() for h in self.history],
            "history_summaries": [hs.to_dict() for hs in self.history_summaries],
            "clarifications": [c.to_dict() for c in self.clarifications],
            "rejections": [r.to_dict() for r in self.rejections],
            "budget": self.budget.to_dict(),
            "status": self.status.value,
            "agent_notes": self.agent_notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        return cls(
            id=data["id"],
            goal=Goal.from_dict(data["goal"]),
            state=AgentState.from_dict(data.get("state", {})),
            plan=Plan.from_dict(data.get("plan", {})),
            history=[HistoryEntry.from_dict(h) for h in data.get("history", [])],
            history_summaries=[HistorySummary.from_dict(hs) for hs in data.get("history_summaries", [])],
            clarifications=[ClarificationEntry.from_dict(c) for c in data.get("clarifications", [])],
            rejections=[RejectionEntry.from_dict(r) for r in data.get("rejections", [])],
            budget=TokenBudget.from_dict(data.get("budget", {})),
            status=SessionStatus(data.get("status", "active")),
            agent_notes=data.get("agent_notes", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now()
        )


@dataclass
class TurnResult:
    """Result of a single turn in the planning loop."""
    # Status options: "awaiting_approval", "needs_clarification", "completed", "budget_exceeded", "aborted", "no_action"
    status: str
    session: Optional[Session] = None
    proposed_action: Optional[Action] = None
    clarification_question: Optional[ClarificationQuestion] = None  # NEW: question for user
    reasoning: str = ""
    goal_achieved: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "session": self.session.to_dict() if self.session else None,
            "proposed_action": self.proposed_action.to_dict() if self.proposed_action else None,
            "clarification_question": self.clarification_question.to_dict() if self.clarification_question else None,
            "reasoning": self.reasoning,
            "goal_achieved": self.goal_achieved,
            "error": self.error
        }


@dataclass
class ExecutionResult:
    """Result of executing an action."""
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    tokens_used: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "tokens_used": self.tokens_used
        }


@dataclass 
class ToolInfo:
    """Information about an available tool from the registry."""
    name: str
    category: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "parameters": self.parameters
        }


# Legacy compatibility - keep old imports working
Task = PlanStep  # Alias for backwards compatibility
TaskStatus = StepStatus  # Alias for backwards compatibility
TaskSession = Session  # Alias for backwards compatibility
