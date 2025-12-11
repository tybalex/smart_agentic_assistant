"""
Session Manager for the Continuous Planning Agent.
Handles session persistence and state management.
"""

import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from models import (
    Session, Goal, AgentState, Plan, PlanStep, Action,
    HistoryEntry, HistorySummary, TokenBudget,
    SessionStatus, StepStatus, TextSpan, generate_id,
    ClarificationQuestion, ClarificationAnswer, ClarificationEntry,
    RejectionFeedback, RejectionEntry
)


class SessionManager:
    """
    Manages agent sessions and provides persistence to disk.
    """
    
    def __init__(self, storage_dir: str = "./task_data"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: Optional[Session] = None
    
    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        return self.storage_dir / f"session_{session_id}.json"
    
    # ===================
    # Session CRUD
    # ===================
    
    def create_session(
        self,
        goal_text: str,
        max_tokens: int = 180000,
        max_turns: int = 999  # Not enforced, kept for backward compatibility
    ) -> Session:
        """
        Create a new session from user's goal text.
        """
        goal = Goal(
            id=generate_id(),
            original_text=goal_text,
            text_spans=[],
            created_at=datetime.now()
        )
        
        session = Session(
            id=generate_id(),
            goal=goal,
            state=AgentState(),
            plan=Plan(),
            history=[],
            history_summaries=[],
            budget=TokenBudget(
                max_tokens=max_tokens,
                max_turns=max_turns,
                used_tokens=0,
                current_turn=0
            ),
            status=SessionStatus.ACTIVE,
            agent_notes=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.current_session = session
        self.save_session()
        return session
    
    def save_session(self, session: Optional[Session] = None) -> bool:
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
    
    def load_session(self, session_id: str) -> Optional[Session]:
        """Load a session from disk."""
        try:
            path = self._get_session_path(session_id)
            if not path.exists():
                return None
            
            with open(path, 'r') as f:
                data = json.load(f)
            
            session = Session.from_dict(data)
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
                
                goal_text = data.get("goal", {}).get("original_text", "")
                sessions.append({
                    "id": data["id"],
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "status": data.get("status", "active"),
                    "turn": data.get("budget", {}).get("current_turn", 0),
                    "preview": goal_text[:100] + "..." if len(goal_text) > 100 else goal_text
                })
            except Exception as e:
                print(f"Error reading session file {path}: {e}")
        
        # Sort by update date, newest first
        sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
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
    
    # ===================
    # State Management
    # ===================
    
    def update_state(self, state: AgentState) -> None:
        """Update the agent's current state understanding."""
        if self.current_session:
            self.current_session.state = state
            self.save_session()
    
    def update_plan(self, plan: Plan) -> None:
        """Update the current plan."""
        if self.current_session:
            plan.last_updated = datetime.now()
            self.current_session.plan = plan
            self.save_session()
    
    def set_plan_from_data(self, plan_data: List[Dict[str, Any]], reasoning: str = "", confidence: float = 0.5) -> Plan:
        """Create and set a plan from parsed data."""
        if not self.current_session:
            return Plan()
        
        steps = []
        for i, step_data in enumerate(plan_data):
            text_span = None
            if step_data.get("text_span"):
                ts = step_data["text_span"]
                text_span = TextSpan(
                    start=ts["start"],
                    end=ts["end"],
                    text=ts["text"]
                )
            
            step = PlanStep(
                id=generate_id(),
                description=step_data.get("description", step_data.get("title", f"Step {i+1}")),
                status=StepStatus.PLANNED,
                text_span=text_span
            )
            steps.append(step)
        
        plan = Plan(
            steps=steps,
            reasoning=reasoning,
            confidence=confidence,
            last_updated=datetime.now()
        )
        
        self.current_session.plan = plan
        self.save_session()
        return plan
    
    def update_step_status(
        self,
        step_id: str,
        status: StepStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
        tool_used: Optional[str] = None,
        tool_params: Optional[Dict[str, Any]] = None
    ) -> Optional[PlanStep]:
        """Update a plan step's status."""
        if not self.current_session:
            return None
        
        for step in self.current_session.plan.steps:
            if step.id == step_id:
                step.status = status
                if result:
                    step.result = result
                if error:
                    step.error = error
                if tool_used:
                    step.tool_used = tool_used
                if tool_params:
                    step.tool_params = tool_params
                
                # Record completed steps in immutable log
                if status == StepStatus.COMPLETED:
                    from models import CompletedStep
                    completed_step = CompletedStep(
                        step_id=step.id,
                        description=step.description,
                        turn=self.current_session.budget.current_turn,
                        result_summary=result[:200] if result else "Success"
                    )
                    self.current_session.completed_steps.append(completed_step)
                
                self.save_session()
                return step
        return None
    
    def add_plan_step(self, description: str, after_step_id: Optional[str] = None) -> Optional[PlanStep]:
        """Add a new step to the plan."""
        if not self.current_session:
            return None
        
        new_step = PlanStep(
            id=generate_id(),
            description=description,
            status=StepStatus.PLANNED
        )
        
        if after_step_id:
            # Insert after specific step
            for i, step in enumerate(self.current_session.plan.steps):
                if step.id == after_step_id:
                    self.current_session.plan.steps.insert(i + 1, new_step)
                    break
            else:
                # Step not found, append to end
                self.current_session.plan.steps.append(new_step)
        else:
            self.current_session.plan.steps.append(new_step)
        
        self.current_session.plan.last_updated = datetime.now()
        self.save_session()
        return new_step
    
    def remove_plan_step(self, step_id: str) -> bool:
        """Remove a step from the plan."""
        if not self.current_session:
            return False
        
        original_len = len(self.current_session.plan.steps)
        self.current_session.plan.steps = [
            s for s in self.current_session.plan.steps if s.id != step_id
        ]
        
        if len(self.current_session.plan.steps) < original_len:
            self.current_session.plan.last_updated = datetime.now()
            self.save_session()
            return True
        return False
    
    # ===================
    # History Management
    # ===================
    
    def add_history_entry(self, action: Action, result: Dict[str, Any]) -> HistoryEntry:
        """Add an entry to execution history."""
        if not self.current_session:
            raise ValueError("No active session")
        
        entry = HistoryEntry(
            turn=self.current_session.budget.current_turn,
            action=action,
            result=result,
            timestamp=datetime.now()
        )
        
        self.current_session.history.append(entry)
        self.save_session()
        return entry
    
    def get_recent_history(self, n: int = 5) -> List[HistoryEntry]:
        """Get the N most recent history entries."""
        if not self.current_session:
            return []
        return self.current_session.history[-n:]
    
    def add_history_summary(self, summary: HistorySummary) -> None:
        """Add a compressed history summary."""
        if self.current_session:
            self.current_session.history_summaries.append(summary)
            self.save_session()
    
    def clear_old_history(self, keep_recent: int = 3) -> int:
        """Clear old history entries, keeping only the most recent ones."""
        if not self.current_session:
            return 0
        
        if len(self.current_session.history) <= keep_recent:
            return 0
        
        removed_count = len(self.current_session.history) - keep_recent
        self.current_session.history = self.current_session.history[-keep_recent:]
        self.save_session()
        return removed_count
    
    # ===================
    # Budget Management
    # ===================
    
    def increment_turn(self) -> int:
        """Increment the turn counter and return new value."""
        if not self.current_session:
            return 0
        
        self.current_session.budget.current_turn += 1
        self.save_session()
        return self.current_session.budget.current_turn
    
    def add_tokens_used(self, tokens: int) -> int:
        """Add to the token usage counter and return new total."""
        if not self.current_session:
            return 0
        
        self.current_session.budget.used_tokens += tokens
        self.save_session()
        return self.current_session.budget.used_tokens
    
    def update_context_tokens(self, context_tokens: int) -> None:
        """Update the current context size (most recent prompt's input tokens)."""
        if not self.current_session:
            return
        
        self.current_session.budget.current_context_tokens = context_tokens
        self.save_session()
    
    def is_budget_exceeded(self) -> bool:
        """Check if the budget has been exceeded."""
        if not self.current_session:
            return True
        return self.current_session.budget.exceeded
    
    # ===================
    # Goal Text Span Management
    # ===================
    
    def set_goal_text_spans(self, spans: List[Dict[str, Any]]) -> None:
        """Set text spans for the goal (for highlighting)."""
        if not self.current_session:
            return
        
        self.current_session.goal.text_spans = [
            TextSpan(
                start=s["start"],
                end=s["end"],
                text=s["text"]
            )
            for s in spans
        ]
        self.save_session()
    
    def update_text_span_for_step(self, step_id: str, span: TextSpan) -> None:
        """Update the text span for a specific plan step."""
        if not self.current_session:
            return
        
        for step in self.current_session.plan.steps:
            if step.id == step_id:
                step.text_span = span
                self.save_session()
                break
    
    # ===================
    # Session Status
    # ===================
    
    def set_session_status(self, status: SessionStatus) -> None:
        """Update the session status."""
        if self.current_session:
            self.current_session.status = status
            self.save_session()
    
    def complete_session(self) -> None:
        """Mark the session as completed."""
        self.set_session_status(SessionStatus.COMPLETED)
    
    def abort_session(self) -> None:
        """Mark the session as aborted."""
        self.set_session_status(SessionStatus.ABORTED)
    
    # ===================
    # Agent Notes
    # ===================
    
    def add_agent_note(self, note: str) -> None:
        """Add a note from the agent."""
        if self.current_session:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.current_session.agent_notes.append(f"[{timestamp}] {note}")
            self.save_session()
    
    # ===================
    # Clarification Management
    # ===================
    
    def add_clarification(
        self,
        question: ClarificationQuestion,
        answer: ClarificationAnswer
    ) -> ClarificationEntry:
        """Add a clarification Q&A pair to the session."""
        if not self.current_session:
            raise ValueError("No active session")
        
        entry = ClarificationEntry(
            turn=self.current_session.budget.current_turn,
            question=question,
            answer=answer
        )
        
        self.current_session.clarifications.append(entry)
        self.save_session()
        return entry
    
    def get_recent_clarifications(self, n: int = 5) -> List[ClarificationEntry]:
        """Get the N most recent clarification entries."""
        if not self.current_session:
            return []
        return self.current_session.clarifications[-n:]
    
    def get_all_clarifications(self) -> List[ClarificationEntry]:
        """Get all clarification entries."""
        if not self.current_session:
            return []
        return self.current_session.clarifications
    
    # ===================
    # Rejection Management
    # ===================
    
    def add_rejection(self, rejection: RejectionFeedback) -> RejectionEntry:
        """Add a rejection feedback entry to the session."""
        if not self.current_session:
            raise ValueError("No active session")
        
        entry = RejectionEntry(
            turn=self.current_session.budget.current_turn,
            rejection=rejection
        )
        
        self.current_session.rejections.append(entry)
        self.save_session()
        return entry
    
    def get_recent_rejections(self, n: int = 5) -> List[RejectionEntry]:
        """Get the N most recent rejection entries."""
        if not self.current_session:
            return []
        return self.current_session.rejections[-n:]
    
    def get_all_rejections(self) -> List[RejectionEntry]:
        """Get all rejection entries."""
        if not self.current_session:
            return []
        return self.current_session.rejections
    
    # ===================
    # Convenience Getters
    # ===================
    
    def get_current_step(self) -> Optional[PlanStep]:
        """Get the currently active step."""
        if self.current_session:
            return self.current_session.plan.get_current_step()
        return None
    
    def get_next_step(self) -> Optional[PlanStep]:
        """Get the next planned step."""
        if self.current_session:
            return self.current_session.plan.get_next_planned_step()
        return None
    
    def get_all_steps(self) -> List[PlanStep]:
        """Get all plan steps."""
        if self.current_session:
            return self.current_session.plan.steps
        return []
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of the current session state."""
        if not self.current_session:
            return {"error": "No active session"}
        
        progress = self.current_session.get_progress()
        current = self.get_current_step()
        next_step = self.get_next_step()
        
        return {
            "session_id": self.current_session.id,
            "status": self.current_session.status.value,
            "goal": self.current_session.goal.original_text[:200],
            "progress": progress,
            "current_step": current.to_dict() if current else None,
            "next_step": next_step.to_dict() if next_step else None,
            "state_summary": self.current_session.state.summary,
            "is_complete": progress["planned"] == 0 and progress["in_progress"] == 0,
            "budget_exceeded": self.current_session.budget.exceeded
        }


# Global instance for easy access
_session_manager: Optional[SessionManager] = None


def get_session_manager(storage_dir: str = "./task_data") -> SessionManager:
    """Get or create the global session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(storage_dir)
    return _session_manager


# Backwards compatibility alias
TaskManager = SessionManager
get_task_manager = get_session_manager

