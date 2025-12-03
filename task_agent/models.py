"""
Data models for the Task Agent system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class TaskStatus(Enum):
    """Status of a task in the execution pipeline."""
    PENDING = "pending"           # Not yet started
    IN_PROGRESS = "in_progress"   # Currently being executed
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # Waiting for user to confirm
    COMPLETED = "completed"       # Successfully completed
    FAILED = "failed"             # Execution failed
    SKIPPED = "skipped"           # User skipped this task


@dataclass
class TextSpan:
    """
    Represents a span of text in the original input.
    Used for mapping tasks back to source text for highlighting.
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
class Task:
    """
    Represents a single task extracted from user input.
    """
    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    text_span: Optional[TextSpan] = None  # Link to original text
    order: int = 0  # Execution order
    result: Optional[str] = None  # Result after execution
    error: Optional[str] = None   # Error message if failed
    tool_used: Optional[str] = None  # Which tool was used
    tool_params: Optional[Dict[str, Any]] = None  # Parameters passed to tool
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "text_span": self.text_span.to_dict() if self.text_span else None,
            "order": self.order,
            "result": self.result,
            "error": self.error,
            "tool_used": self.tool_used,
            "tool_params": self.tool_params,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            status=TaskStatus(data["status"]),
            text_span=TextSpan.from_dict(data["text_span"]) if data.get("text_span") else None,
            order=data.get("order", 0),
            result=data.get("result"),
            error=data.get("error"),
            tool_used=data.get("tool_used"),
            tool_params=data.get("tool_params"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            executed_at=datetime.fromisoformat(data["executed_at"]) if data.get("executed_at") else None
        )


@dataclass
class TaskSession:
    """
    Represents a complete task session with original text and extracted tasks.
    """
    id: str
    original_text: str
    tasks: List[Task] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    agent_notes: List[str] = field(default_factory=list)  # Agent's reasoning/notes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "original_text": self.original_text,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "agent_notes": self.agent_notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskSession":
        return cls(
            id=data["id"],
            original_text=data["original_text"],
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(),
            agent_notes=data.get("agent_notes", [])
        )
    
    def get_current_task(self) -> Optional[Task]:
        """Get the current task being executed or awaiting confirmation."""
        for task in self.tasks:
            if task.status in [TaskStatus.IN_PROGRESS, TaskStatus.AWAITING_CONFIRMATION]:
                return task
        return None
    
    def get_next_pending_task(self) -> Optional[Task]:
        """Get the next pending task to execute."""
        pending = [t for t in self.tasks if t.status == TaskStatus.PENDING]
        if pending:
            return min(pending, key=lambda t: t.order)
        return None
    
    def get_completed_tasks(self) -> List[Task]:
        """Get all completed tasks."""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]
    
    def get_progress(self) -> Dict[str, int]:
        """Get task progress statistics."""
        stats = {
            "total": len(self.tasks),
            "completed": 0,
            "pending": 0,
            "in_progress": 0,
            "failed": 0,
            "skipped": 0
        }
        for task in self.tasks:
            if task.status == TaskStatus.COMPLETED:
                stats["completed"] += 1
            elif task.status == TaskStatus.PENDING:
                stats["pending"] += 1
            elif task.status in [TaskStatus.IN_PROGRESS, TaskStatus.AWAITING_CONFIRMATION]:
                stats["in_progress"] += 1
            elif task.status == TaskStatus.FAILED:
                stats["failed"] += 1
            elif task.status == TaskStatus.SKIPPED:
                stats["skipped"] += 1
        return stats


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


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())[:8]

