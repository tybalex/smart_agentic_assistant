"""
Streamlit UI for the Continuous Planning Agent.
Provides goal input, plan visualization, state tracking, and execution controls.
"""

import streamlit as st
import json
from typing import Optional, Dict, Any, List

from models import (
    Session, StepStatus, PlanStep, Action, SessionStatus, Plan
)
from agent import ContinuousPlanningAgent, create_agent
from session_manager import SessionManager
from tool_client import ToolRegistryClient


# Page configuration
st.set_page_config(
    page_title="Continuous Planning Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* Main container styling */
    .main-header {
        font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    
    .sub-header {
        color: #6b7280;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* Goal box */
    .goal-box {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
    }
    
    .goal-label {
        color: #a5b4fc;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .goal-text {
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 1rem;
        line-height: 1.8;
        color: #e2e8f0;
        white-space: pre-wrap;
    }
    
    /* Text highlighting */
    .span-completed {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 500;
    }
    
    .span-current {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 600;
        animation: pulse 2s infinite;
    }
    
    .span-pending {
        background: rgba(99, 102, 241, 0.3);
        color: #a5b4fc;
        padding: 2px 6px;
        border-radius: 4px;
    }
    
    .span-failed {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        text-decoration: line-through;
    }
    
    .span-skipped {
        background: #4b5563;
        color: #9ca3af;
        padding: 2px 6px;
        border-radius: 4px;
        text-decoration: line-through;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }
    
    /* State card */
    .state-card {
        background: #f8fafc;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #e2e8f0;
    }
    
    .state-label {
        color: #64748b;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
    }
    
    .state-content {
        color: #1e293b;
        font-size: 0.9rem;
    }
    
    /* Plan step styling */
    .plan-step {
        background: #ffffff;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        border-left: 4px solid #e2e8f0;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .plan-step:hover {
        transform: translateX(4px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    .plan-step.completed {
        border-left-color: #10b981;
        background: #f0fdf4;
    }
    
    .plan-step.in-progress {
        border-left-color: #f59e0b;
        background: #fffbeb;
    }
    
    .plan-step.failed {
        border-left-color: #ef4444;
        background: #fef2f2;
    }
    
    .plan-step.skipped {
        border-left-color: #6b7280;
        background: #f9fafb;
        opacity: 0.7;
    }
    
    .step-description {
        font-weight: 500;
        color: #1f2937;
    }
    
    .step-result {
        font-size: 0.8rem;
        color: #6b7280;
        margin-top: 0.25rem;
    }
    
    /* Action card */
    .action-card {
        background: linear-gradient(135deg, #fefce8 0%, #fef9c3 100%);
        border: 2px solid #eab308;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .action-label {
        color: #854d0e;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.75rem;
    }
    
    .action-tool {
        font-family: 'Monaco', 'Menlo', monospace;
        background: #ffffff;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        margin-bottom: 0.75rem;
        color: #1f2937;
    }
    
    .action-reasoning {
        color: #713f12;
        font-size: 0.9rem;
        font-style: italic;
    }
    
    /* Budget indicator */
    .budget-container {
        background: #f1f5f9;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .budget-bar {
        height: 8px;
        background: #e2e8f0;
        border-radius: 4px;
        overflow: hidden;
        margin: 0.5rem 0;
    }
    
    .budget-fill {
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
    }
    
    .budget-fill.safe {
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
    }
    
    .budget-fill.warning {
        background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
    }
    
    .budget-fill.danger {
        background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
    }
    
    .budget-text {
        font-size: 0.8rem;
        color: #64748b;
    }
    
    /* Agent notes */
    .agent-note {
        background: #eff6ff;
        border-left: 4px solid #3b82f6;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.875rem;
        color: #1e40af;
    }
    
    /* Health indicator */
    .health-indicator {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    .health-healthy {
        background: #d1fae5;
        color: #065f46;
    }
    
    .health-unhealthy {
        background: #fee2e2;
        color: #991b1b;
    }
    
    /* History entry */
    .history-entry {
        background: #f8fafc;
        border-radius: 8px;
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        border: 1px solid #e2e8f0;
    }
    
    .history-turn {
        font-weight: 600;
        color: #6366f1;
        font-size: 0.8rem;
    }
    
    .history-action {
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 0.85rem;
        color: #1f2937;
    }
    
    .history-result {
        font-size: 0.8rem;
        color: #6b7280;
        margin-top: 0.25rem;
    }
    
    /* Plan header */
    .plan-header {
        background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
        border: 1px solid #c7d2fe;
    }
    
    .plan-title {
        font-weight: 700;
        color: #4338ca;
        font-size: 1rem;
        margin-bottom: 0.5rem;
    }
    
    .plan-meta {
        font-size: 0.8rem;
        color: #6366f1;
    }
    
    .plan-reasoning {
        background: #f8fafc;
        border-radius: 8px;
        padding: 0.75rem;
        margin-top: 0.75rem;
        font-size: 0.85rem;
        color: #475569;
        font-style: italic;
        border-left: 3px solid #6366f1;
    }
    
    .plan-confidence {
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }
    
    .confidence-high {
        background: #d1fae5;
        color: #065f46;
    }
    
    .confidence-medium {
        background: #fef3c7;
        color: #92400e;
    }
    
    .confidence-low {
        background: #fee2e2;
        color: #991b1b;
    }
    
    .plan-updated-badge {
        display: inline-block;
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        animation: pulse 2s infinite;
        margin-left: 0.5rem;
    }
    
    .turn-indicator {
        background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        text-align: center;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize Streamlit session state variables."""
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "current_session" not in st.session_state:
        st.session_state.current_session = None
    if "turn_result" not in st.session_state:
        st.session_state.turn_result = None
    if "input_text" not in st.session_state:
        st.session_state.input_text = ""


def get_agent() -> ContinuousPlanningAgent:
    """Get or create the agent instance."""
    if st.session_state.agent is None:
        st.session_state.agent = create_agent()
    return st.session_state.agent


def render_highlighted_goal(goal_text: str, steps: List[PlanStep]) -> str:
    """Render the goal text with highlighting based on step status."""
    if not steps:
        return f'<div class="goal-text">{goal_text}</div>'
    
    # Build spans with their status
    spans = []
    for step in steps:
        if step.text_span:
            spans.append({
                "start": step.text_span.start,
                "end": step.text_span.end,
                "status": step.status,
                "step_id": step.id
            })
    
    # Sort by start position
    spans.sort(key=lambda x: x["start"])
    
    # Build highlighted HTML
    result = []
    last_end = 0
    
    for span in spans:
        # Add unhighlighted text before this span
        if span["start"] > last_end:
            result.append(goal_text[last_end:span["start"]])
        
        # Determine CSS class
        status = span["status"]
        if status == StepStatus.COMPLETED:
            css_class = "span-completed"
        elif status == StepStatus.IN_PROGRESS:
            css_class = "span-current"
        elif status == StepStatus.FAILED:
            css_class = "span-failed"
        elif status == StepStatus.SKIPPED:
            css_class = "span-skipped"
        else:
            css_class = "span-pending"
        
        span_text = goal_text[span["start"]:span["end"]]
        result.append(f'<span class="{css_class}">{span_text}</span>')
        last_end = span["end"]
    
    # Add remaining text
    if last_end < len(goal_text):
        result.append(goal_text[last_end:])
    
    highlighted = "".join(result)
    return f'<div class="goal-text">{highlighted}</div>'


def render_plan_step(step: PlanStep) -> str:
    """Render a single plan step."""
    status_class = {
        StepStatus.COMPLETED: "completed",
        StepStatus.IN_PROGRESS: "in-progress",
        StepStatus.FAILED: "failed",
        StepStatus.SKIPPED: "skipped",
        StepStatus.PLANNED: ""
    }.get(step.status, "")
    
    status_icon = {
        StepStatus.COMPLETED: "✅",
        StepStatus.IN_PROGRESS: "🔄",
        StepStatus.FAILED: "❌",
        StepStatus.SKIPPED: "⏭️",
        StepStatus.PLANNED: "⬜"
    }.get(step.status, "⬜")
    
    result_html = ""
    if step.result:
        result_preview = step.result[:100] + "..." if len(step.result) > 100 else step.result
        result_html = f'<div class="step-result">Result: {result_preview}</div>'
    elif step.error:
        result_html = f'<div class="step-result" style="color: #dc2626;">Error: {step.error}</div>'
    
    return f"""
    <div class="plan-step {status_class}">
        <div class="step-description">{status_icon} {step.description}</div>
        {result_html}
    </div>
    """


def render_budget(session: Session) -> str:
    """Render the budget indicators."""
    budget = session.budget
    
    # Token budget
    token_pct = budget.token_percentage
    token_class = "safe" if token_pct < 60 else ("warning" if token_pct < 85 else "danger")
    
    # Turn budget
    turn_pct = budget.turn_percentage
    turn_class = "safe" if turn_pct < 60 else ("warning" if turn_pct < 85 else "danger")
    
    return f"""
    <div class="budget-container">
        <div class="budget-text">
            <strong>💰 Budget</strong>
        </div>
        <div style="margin-top: 0.5rem;">
            <div class="budget-text">Turns: {budget.current_turn}/{budget.max_turns}</div>
            <div class="budget-bar">
                <div class="budget-fill {turn_class}" style="width: {turn_pct}%"></div>
            </div>
        </div>
        <div style="margin-top: 0.5rem;">
            <div class="budget-text">Tokens: {budget.used_tokens:,}/{budget.max_tokens:,}</div>
            <div class="budget-bar">
                <div class="budget-fill {token_class}" style="width: {token_pct}%"></div>
            </div>
        </div>
    </div>
    """


def render_action_card(action: Action) -> str:
    """Render the proposed action card."""
    params_html = "<br>".join([
        f"&nbsp;&nbsp;{k}: {json.dumps(v)}" for k, v in action.parameters.items()
    ]) if action.parameters else "&nbsp;&nbsp;(none)"
    
    return f"""
    <div class="action-card">
        <div class="action-label">🎬 Proposed Action</div>
        <div class="action-tool">
            <strong>Tool:</strong> {action.tool_category}/{action.tool_name}<br>
            <strong>Parameters:</strong><br>{params_html}
        </div>
        <div class="action-reasoning">
            <strong>Reasoning:</strong> {action.reasoning}
        </div>
    </div>
    """


def main():
    """Main application entry point."""
    init_session_state()
    
    # Header
    st.markdown('<div class="main-header">🤖 Continuous Planning Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Adaptive planning with step-by-step execution</div>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        
        # Tool API Status
        tool_client = ToolRegistryClient()
        health = tool_client.health_check()
        
        if health["status"] == "healthy":
            st.markdown(
                '<div class="health-indicator health-healthy">🟢 Tool API Connected</div>',
                unsafe_allow_html=True
            )
            if "info" in health:
                st.caption(f"Functions: {health['info'].get('total_functions', 'N/A')}")
        else:
            st.markdown(
                '<div class="health-indicator health-unhealthy">🔴 Tool API Offline</div>',
                unsafe_allow_html=True
            )
            st.error(f"Error: {health.get('error', 'Unknown')}")
        
        st.divider()
        
        # Session management
        st.markdown("### 📁 Sessions")
        
        agent = get_agent()
        sessions = agent.session_manager.list_sessions()
        
        if sessions:
            session_options = {
                s["id"]: f"{s['id']} (Turn {s['turn']}) - {s['preview'][:25]}..."
                for s in sessions
            }
            selected_session = st.selectbox(
                "Load existing session",
                options=[""] + list(session_options.keys()),
                format_func=lambda x: "Select..." if x == "" else session_options.get(x, x)
            )
            
            if selected_session and st.button("Load Session"):
                session = agent.load_session(selected_session)
                if session:
                    st.session_state.current_session = session
                    st.session_state.turn_result = None
                    st.rerun()
        else:
            st.caption("No saved sessions")
        
        st.divider()
        
        # Budget settings (for new sessions)
        st.markdown("### 💰 Budget Settings")
        max_turns = st.slider("Max Turns", 10, 100, 50)
        max_tokens = st.slider("Max Tokens (K)", 50, 300, 150) * 1000
        
        st.divider()
        
        # Legend
        st.markdown("### 🎨 Legend")
        st.markdown("""
        <div style="font-size: 0.875rem;">
            <span class="span-completed">Completed</span><br><br>
            <span class="span-current">In Progress</span><br><br>
            <span class="span-pending">Planned</span><br><br>
            <span class="span-failed">Failed</span><br><br>
            <span class="span-skipped">Skipped</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Main content
    agent = get_agent()
    session = st.session_state.current_session or agent.current_session
    
    if session is None:
        # No active session - show input
        st.markdown("### 🎯 Enter Your Goal")
        
        input_text = st.text_area(
            "What do you want to accomplish?",
            value=st.session_state.input_text,
            height=150,
            placeholder="Describe your goal...\n\nExample:\nI need to search for weather in San Francisco, calculate the wind chill factor, and summarize the results."
        )
        
        if st.button("🚀 Start Planning", type="primary", use_container_width=True):
            if input_text.strip():
                with st.spinner("Analyzing goal and creating initial plan..."):
                    session = agent.start_session(
                        goal_text=input_text,
                        max_tokens=max_tokens,
                        max_turns=max_turns
                    )
                    st.session_state.current_session = session
                    st.session_state.input_text = input_text
                st.rerun()
            else:
                st.warning("Please enter a goal first.")
    
    else:
        # Active session - show visualization and controls
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # Goal section
            st.markdown("### 🎯 Goal")
            steps = session.plan.steps
            highlighted = render_highlighted_goal(session.goal.original_text, steps)
            st.markdown(f"""
            <div class="goal-box">
                <div class="goal-label">Your Objective</div>
                {highlighted}
            </div>
            """, unsafe_allow_html=True)
            
            # State section
            st.markdown("### 📊 Current State")
            st.markdown(f"""
            <div class="state-card">
                <div class="state-label">Agent's Understanding</div>
                <div class="state-content">{session.state.summary or "Analyzing..."}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if session.state.completed_objectives:
                st.markdown("**Completed:**")
                for obj in session.state.completed_objectives:
                    st.markdown(f"- ✅ {obj}")
            
            if session.state.blockers:
                st.markdown("**Blockers:**")
                for blocker in session.state.blockers:
                    st.markdown(f"- ⚠️ {blocker}")
            
            # Budget
            st.markdown(render_budget(session), unsafe_allow_html=True)
        
        with col2:
            # Turn indicator
            st.markdown(f"""
            <div class="turn-indicator">
                🔄 Turn {session.budget.current_turn} / {session.budget.max_turns}
            </div>
            """, unsafe_allow_html=True)
            
            # Plan section with header
            plan = session.plan
            confidence_class = "high" if plan.confidence >= 0.7 else ("medium" if plan.confidence >= 0.4 else "low")
            confidence_label = "High" if plan.confidence >= 0.7 else ("Medium" if plan.confidence >= 0.4 else "Low")
            
            # Check if we just updated the plan (turn result exists)
            plan_updated = st.session_state.turn_result is not None
            updated_badge = '<span class="plan-updated-badge">UPDATED</span>' if plan_updated else ''
            
            st.markdown(f"""
            <div class="plan-header">
                <div class="plan-title">
                    📋 Current Plan {updated_badge}
                    <span class="plan-confidence confidence-{confidence_class}">
                        {confidence_label} Confidence ({plan.confidence:.0%})
                    </span>
                </div>
                <div class="plan-meta">
                    {len(plan.steps)} steps • Last updated: {plan.last_updated.strftime("%H:%M:%S") if plan.last_updated else "N/A"}
                </div>
                {f'<div class="plan-reasoning">💭 {plan.reasoning}</div>' if plan.reasoning else ''}
            </div>
            """, unsafe_allow_html=True)
            
            # Plan steps with progress summary
            if steps:
                # Calculate progress
                progress = plan.get_progress()
                completed = progress["completed"]
                total = progress["total"]
                failed = progress["failed"]
                skipped = progress["skipped"]
                
                # Progress bar
                progress_pct = ((completed + skipped) / total * 100) if total > 0 else 0
                failed_span = f'<span style="color: #dc2626;">❌ {failed} failed</span>' if failed > 0 else ''
                st.markdown(f"""<div style="margin-bottom: 1rem;">
<div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #64748b; margin-bottom: 0.25rem;">
<span>✅ {completed} completed</span>
<span>⬜ {progress["planned"]} remaining</span>
{failed_span}
</div>
<div style="height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden;">
<div style="height: 100%; width: {progress_pct}%; background: linear-gradient(90deg, #10b981 0%, #059669 100%); border-radius: 3px;"></div>
</div>
</div>""", unsafe_allow_html=True)
                
                # Find current step index for "NEXT" indicator
                current_idx = None
                for i, step in enumerate(steps):
                    if step.status == StepStatus.IN_PROGRESS:
                        current_idx = i
                        break
                    elif step.status == StepStatus.PLANNED and current_idx is None:
                        # First planned step is next
                        current_idx = i
                
                for i, step in enumerate(steps):
                    step_html = render_plan_step(step)
                    # Add "NEXT" indicator
                    if i == current_idx and step.status == StepStatus.PLANNED:
                        step_html = step_html.replace(
                            '</div>\n    </div>',
                            '<div style="font-size: 0.75rem; color: #f59e0b; margin-top: 0.25rem;">⬅️ NEXT</div></div>\n    </div>'
                        )
                    st.markdown(step_html, unsafe_allow_html=True)
            else:
                st.info("No plan yet.")
            
            st.divider()
            
            # Execution section
            st.markdown("### 🎮 Execution")
            
            # Check session status
            if session.status == SessionStatus.COMPLETED:
                st.success("🎉 Goal achieved!")
                if st.button("🔄 New Session"):
                    st.session_state.current_session = None
                    st.session_state.turn_result = None
                    st.rerun()
            
            elif session.status == SessionStatus.BUDGET_EXCEEDED:
                st.error("💸 Budget exceeded!")
                if st.button("🔄 New Session"):
                    st.session_state.current_session = None
                    st.session_state.turn_result = None
                    st.rerun()
            
            elif session.status == SessionStatus.ABORTED:
                st.warning("🛑 Session aborted.")
                if st.button("🔄 New Session"):
                    st.session_state.current_session = None
                    st.session_state.turn_result = None
                    st.rerun()
            
            else:
                # Get or show turn result
                turn_result = st.session_state.turn_result
                
                if turn_result is None:
                    # Run a turn to get proposed action
                    if st.button("▶️ Next Turn", type="primary", use_container_width=True):
                        with st.spinner("Evaluating and planning..."):
                            turn_result = agent.run_turn()
                            st.session_state.turn_result = turn_result
                            st.session_state.current_session = agent.current_session
                        st.rerun()
                
                else:
                    # Show turn result
                    if turn_result.status == "completed":
                        st.success("🎉 Goal achieved!")
                        st.markdown(f"**Reasoning:** {turn_result.reasoning}")
                        st.session_state.turn_result = None
                        st.session_state.current_session = agent.current_session
                        st.rerun()
                    
                    elif turn_result.status == "awaiting_approval":
                        action = turn_result.proposed_action
                        
                        # Show agent's overall reasoning for this turn
                        if turn_result.reasoning:
                            st.markdown(f"""
                            <div class="state-card" style="border-left: 4px solid #6366f1;">
                                <div class="state-label">🧠 Agent's Analysis (Turn {session.budget.current_turn})</div>
                                <div class="state-content">{turn_result.reasoning}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        st.markdown(render_action_card(action), unsafe_allow_html=True)
                        
                        col_approve, col_skip, col_abort = st.columns(3)
                        
                        with col_approve:
                            if st.button("✅ Approve", type="primary", use_container_width=True):
                                with st.spinner("Executing..."):
                                    result = agent.execute_action(action)
                                
                                st.session_state.turn_result = None
                                st.session_state.current_session = agent.current_session
                                
                                if result.success:
                                    st.toast("Action completed successfully!", icon="✅")
                                else:
                                    st.toast(f"Action failed: {result.error}", icon="❌")
                                
                                st.rerun()
                        
                        with col_skip:
                            if st.button("⏭️ Skip", use_container_width=True):
                                agent.skip_action(action)
                                st.session_state.turn_result = None
                                st.session_state.current_session = agent.current_session
                                st.rerun()
                        
                        with col_abort:
                            if st.button("🛑 Abort", use_container_width=True):
                                agent.abort_session()
                                st.session_state.turn_result = None
                                st.session_state.current_session = agent.current_session
                                st.rerun()
                    
                    elif turn_result.status == "no_action":
                        st.warning("No action available")
                        st.markdown(f"**Reasoning:** {turn_result.reasoning}")
                        if turn_result.error:
                            st.error(f"**Issue:** {turn_result.error}")
                        
                        if st.button("🔄 Try Again"):
                            st.session_state.turn_result = None
                            st.rerun()
                    
                    elif turn_result.status == "budget_exceeded":
                        st.error("💸 Budget exceeded!")
                        st.session_state.turn_result = None
                        st.session_state.current_session = agent.current_session
                        st.rerun()
            
            # History section
            if session.history:
                st.divider()
                st.markdown("### 📜 Recent History")
                
                for entry in reversed(session.history[-3:]):
                    status = "✅" if entry.result.get("success") else "❌"
                    st.markdown(f"""
                    <div class="history-entry">
                        <div class="history-turn">Turn {entry.turn}</div>
                        <div class="history-action">{status} {entry.action.tool_category}/{entry.action.tool_name}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Agent notes
            if session.agent_notes:
                st.divider()
                st.markdown("### 🤖 Agent Notes")
                for note in session.agent_notes[-3:]:
                    st.markdown(f'<div class="agent-note">{note}</div>', unsafe_allow_html=True)
        
        # New session button at bottom
        st.divider()
        if st.button("🔄 Start New Session", use_container_width=True):
            st.session_state.current_session = None
            st.session_state.turn_result = None
            agent.session_manager.current_session = None
            st.rerun()


if __name__ == "__main__":
    main()
