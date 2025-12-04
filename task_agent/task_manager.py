"""
Backwards compatibility module.
Re-exports from session_manager for existing code.
"""

from session_manager import (
    SessionManager,
    SessionManager as TaskManager,
    get_session_manager,
    get_session_manager as get_task_manager,
)

__all__ = [
    "SessionManager",
    "TaskManager",
    "get_session_manager",
    "get_task_manager",
]
