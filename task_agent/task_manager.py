"""
Task Manager for tracking and persisting task execution state.
Handles task list operations and file-based persistence.
"""

import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from models import Task, TaskSession, TaskStatus, TextSpan, generate_id


class TaskManager:
    """
    Manages task sessions and provides persistence to disk.
    """
    
    def __init__(self, storage_dir: str = "./task_data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[TaskSession] = None
    
    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.storage_dir / f"session_{session_id}.json"
    
    def create_session(self, original_text: str) -> TaskSession:
        """
        Create a new task session from the original text.
        Tasks will be added later by the AI agent.
        """
        session = TaskSession(
            id=generate_id(),
            original_text=original_text,
            tasks=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        self.current_session = session
        self.save_session(session)
        return session
    
    def save_session(self, session: Optional[TaskSession] = None) -> bool:
        """Save a session to disk."""
        session = session or self.current_session
        if not session:
            return False
        
        try:
            session.updated_at = datetime.now()
            path = self._get_session_path(session.id)
            with open(path, 'w') as f:
                json.dump(session.to_dict(), f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
    
    def load_session(self, session_id: str) -> Optional[TaskSession]:
        """Load a session from disk."""
        try:
            path = self._get_session_path(session_id)
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                data = json.load(f)
            
            session = TaskSession.from_dict(data)
            self.current_session = session
            return session
        except Exception as e:
            print(f"Error loading session: {e}")
            return None
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions with basic info."""
        sessions = []
        for path in self.storage_dir.glob("session_*.json"):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                sessions.append({
                    "id": data["id"],
                    "created_at": data["created_at"],
                    "task_count": len(data.get("tasks", [])),
                    "preview": data["original_text"][:100] + "..." if len(data["original_text"]) > 100 else data["original_text"]
                })
            except Exception as e:
                print(f"Error reading session file {path}: {e}")
        
        # Sort by creation date, newest first
        sessions.sort(key=lambda x: x["created_at"], reverse=True)
        return sessions
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session from disk."""
        try:
            path = self._get_session_path(session_id)
            if path.exists():
                os.remove(path)
            if self.current_session and self.current_session.id == session_id:
                self.current_session = None
            return True
        except Exception as e:
            print(f"Error deleting session: {e}")
            return False
    
    # Task operations
    
    def add_task(
        self,
        title: str,
        description: str,
        text_span: Optional[TextSpan] = None,
        order: Optional[int] = None
    ) -> Optional[Task]:
        """Add a new task to the current session."""
        if not self.current_session:
            return None
        
        if order is None:
            order = len(self.current_session.tasks)
        
        task = Task(
            id=generate_id(),
            title=title,
            description=description,
            text_span=text_span,
            order=order,
            status=TaskStatus.PENDING
        )
        
        self.current_session.tasks.append(task)
        self.save_session()
        return task
    
    def add_tasks_batch(self, tasks_data: List[Dict[str, Any]]) -> List[Task]:
        """
        Add multiple tasks at once.
        
        Args:
            tasks_data: List of dicts with keys: title, description, 
                       text_span (optional dict with start, end, text)
        """
        if not self.current_session:
            return []
        
        tasks = []
        for i, data in enumerate(tasks_data):
            text_span = None
            if data.get("text_span"):
                ts = data["text_span"]
                text_span = TextSpan(
                    start=ts["start"],
                    end=ts["end"],
                    text=ts["text"]
                )
            
            task = Task(
                id=generate_id(),
                title=data["title"],
                description=data.get("description", ""),
                text_span=text_span,
                order=len(self.current_session.tasks) + i,
                status=TaskStatus.PENDING
            )
            tasks.append(task)
        
        self.current_session.tasks.extend(tasks)
        self.save_session()
        return tasks
    
    def update_task(self, task_id: str, **updates) -> Optional[Task]:
        """Update a task's properties."""
        if not self.current_session:
            return None
        
        for task in self.current_session.tasks:
            if task.id == task_id:
                for key, value in updates.items():
                    if hasattr(task, key):
                        setattr(task, key, value)
                self.save_session()
                return task
        return None
    
    def update_task_status(
        self, 
        task_id: str, 
        status: TaskStatus,
        result: Optional[str] = None,
        error: Optional[str] = None
    ) -> Optional[Task]:
        """Update a task's execution status."""
        if not self.current_session:
            return None
        
        for task in self.current_session.tasks:
            if task.id == task_id:
                task.status = status
                if status == TaskStatus.COMPLETED:
                    task.executed_at = datetime.now()
                    task.result = result
                elif status == TaskStatus.FAILED:
                    task.executed_at = datetime.now()
                    task.error = error
                self.save_session()
                return task
        return None
    
    def set_task_tool_info(
        self,
        task_id: str,
        tool_name: str,
        tool_params: Dict[str, Any]
    ) -> Optional[Task]:
        """Set the tool information for a task."""
        if not self.current_session:
            return None
        
        for task in self.current_session.tasks:
            if task.id == task_id:
                task.tool_used = tool_name
                task.tool_params = tool_params
                self.save_session()
                return task
        return None
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the current session."""
        if not self.current_session:
            return False
        
        original_len = len(self.current_session.tasks)
        self.current_session.tasks = [
            t for t in self.current_session.tasks if t.id != task_id
        ]
        
        if len(self.current_session.tasks) < original_len:
            # Re-order remaining tasks
            for i, task in enumerate(self.current_session.tasks):
                task.order = i
            self.save_session()
            return True
        return False
    
    def reorder_task(self, task_id: str, new_order: int) -> bool:
        """Move a task to a new position in the order."""
        if not self.current_session:
            return False
        
        task_to_move = None
        for task in self.current_session.tasks:
            if task.id == task_id:
                task_to_move = task
                break
        
        if not task_to_move:
            return False
        
        # Remove and reinsert at new position
        self.current_session.tasks.remove(task_to_move)
        self.current_session.tasks.insert(new_order, task_to_move)
        
        # Update all orders
        for i, task in enumerate(self.current_session.tasks):
            task.order = i
        
        self.save_session()
        return True
    
    def insert_task_after(
        self,
        after_task_id: str,
        title: str,
        description: str
    ) -> Optional[Task]:
        """Insert a new task after a specific task (for dynamic task updates)."""
        if not self.current_session:
            return None
        
        insert_index = None
        for i, task in enumerate(self.current_session.tasks):
            if task.id == after_task_id:
                insert_index = i + 1
                break
        
        if insert_index is None:
            return None
        
        new_task = Task(
            id=generate_id(),
            title=title,
            description=description,
            order=insert_index,
            status=TaskStatus.PENDING
        )
        
        self.current_session.tasks.insert(insert_index, new_task)
        
        # Update orders for all tasks after insertion
        for i, task in enumerate(self.current_session.tasks):
            task.order = i
        
        self.save_session()
        return new_task
    
    def add_agent_note(self, note: str) -> None:
        """Add a note from the agent (reasoning, observations, etc.)."""
        if self.current_session:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.current_session.agent_notes.append(f"[{timestamp}] {note}")
            self.save_session()
    
    def get_task_by_id(self, task_id: str) -> Optional[Task]:
        """Get a specific task by ID."""
        if not self.current_session:
            return None
        
        for task in self.current_session.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_current_task(self) -> Optional[Task]:
        """Get the currently active task."""
        if self.current_session:
            return self.current_session.get_current_task()
        return None
    
    def get_next_task(self) -> Optional[Task]:
        """Get the next pending task."""
        if self.current_session:
            return self.current_session.get_next_pending_task()
        return None
    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks in the current session."""
        if self.current_session:
            return sorted(self.current_session.tasks, key=lambda t: t.order)
        return []
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of the current execution state."""
        if not self.current_session:
            return {"error": "No active session"}
        
        progress = self.current_session.get_progress()
        current = self.get_current_task()
        next_task = self.get_next_task()
        
        return {
            "session_id": self.current_session.id,
            "progress": progress,
            "current_task": current.to_dict() if current else None,
            "next_task": next_task.to_dict() if next_task else None,
            "is_complete": progress["pending"] == 0 and progress["in_progress"] == 0
        }


# Global instance for easy access
_task_manager: Optional[TaskManager] = None


def get_task_manager(storage_dir: str = "./task_data") -> TaskManager:
    """Get or create the global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager(storage_dir)
    return _task_manager

