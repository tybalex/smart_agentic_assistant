"""
Streamlit UI for the Smart Agent.
Provides goal input, plan visualization, state tracking, and execution controls.
"""

import streamlit as st
import json
import html
from typing import Optional, Dict, Any, List

from models import (
    Session, StepStatus, PlanStep, Action, SessionStatus, Plan,
    ClarificationQuestion, ClarificationAnswer, CompletedAction,
    BatchAction, FailureStrategy, generate_id
)
from agent import ContinuousPlanningAgent, create_agent
from session_manager import SessionManager
from tool_client import ToolRegistryClient
from constant import CONTEXT_WINDOW_LIMIT


# Page configuration
st.set_page_config(
    page_title="Smart Agent",
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
        max-height: 400px;
        overflow-y: auto;
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
    
    /* Clarification card */
    .clarification-card {
        background: linear-gradient(135deg, #ede9fe 0%, #ddd6fe 100%);
        border: 2px solid #8b5cf6;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    .clarification-label {
        color: #5b21b6;
        font-size: 0.875rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.75rem;
    }
    
    .clarification-question {
        font-size: 1.1rem;
        color: #1f2937;
        background: #ffffff;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 0.75rem;
        border-left: 3px solid #8b5cf6;
    }
    
    .clarification-context {
        color: #6b21a8;
        font-size: 0.9rem;
        font-style: italic;
        margin-bottom: 0.75rem;
    }
    
    .clarification-options {
        background: #f5f3ff;
        padding: 0.75rem;
        border-radius: 6px;
        margin-bottom: 0.5rem;
    }
    
    .clarification-option {
        display: inline-block;
        background: #8b5cf6;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.85rem;
        margin: 0.25rem;
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
    
    /* Plan steps container with scroll */
    .plan-steps-container {
        max-height: 500px;
        overflow-y: auto;
        margin-bottom: 1rem;
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
    if "show_rejection_input" not in st.session_state:
        st.session_state.show_rejection_input = False


def get_agent() -> ContinuousPlanningAgent:
    """Get or create the agent instance."""
    if st.session_state.agent is None:
        st.session_state.agent = create_agent()
    return st.session_state.agent


def render_plan_step(step: PlanStep) -> str:
    """Render a single plan step."""
    import html
    
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
    
    # HTML escape dynamic content to prevent breaking the HTML
    escaped_description = html.escape(step.description)
    
    result_html = ""
    if step.result:
        result_preview = step.result[:100] + "..." if len(step.result) > 100 else step.result
        escaped_result = html.escape(result_preview)
        result_html = f'<div class="step-result">Result: {escaped_result}</div>'
    elif step.error:
        escaped_error = html.escape(step.error)
        result_html = f'<div class="step-result" style="color: #dc2626;">Error: {escaped_error}</div>'
    
    # Return HTML without extra indentation/whitespace
    return f'<div class="plan-step {status_class}"><div class="step-description">{status_icon} {escaped_description}</div>{result_html}</div>'


def render_budget(session: Session) -> str:
    """Render the budget indicators."""
    budget = session.budget
    
    # Context window (fixed 200K limit)
    context_pct = budget.context_percentage
    context_class = "safe" if context_pct < 60 else ("warning" if context_pct < 85 else "danger")
    
    # Total token budget
    token_pct = budget.token_percentage
    token_class = "safe" if token_pct < 60 else ("warning" if token_pct < 85 else "danger")
    
    return f"""
    <div class="budget-container">
        <div class="budget-text">
            <strong>💰 Budget</strong>
        </div>
        <div style="margin-top: 0.5rem;">
            <div class="budget-text">Turns: {budget.current_turn}</div>
        </div>
        <div style="margin-top: 0.5rem;">
            <div class="budget-text">💬 Context: {budget.current_context_tokens:,} / {CONTEXT_WINDOW_LIMIT:,} tokens</div>
            <div class="budget-bar">
                <div class="budget-fill {context_class}" style="width: {context_pct}%"></div>
            </div>
        </div>
        <div style="margin-top: 0.5rem;">
            <div class="budget-text">💰 Total Used: {budget.used_tokens:,} / {budget.max_tokens:,} tokens</div>
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


def render_batch_card(batch: BatchAction) -> str:
    """Render a batch of proposed actions."""
    # Format strategy with explanation
    strategy_icon = "🔄" if batch.failure_strategy == FailureStrategy.CONTINUE else "⏹️"
    strategy_text = "Continue on error" if batch.failure_strategy == FailureStrategy.CONTINUE else "Stop on first error"
    strategy_color = "#10b981" if batch.failure_strategy == FailureStrategy.CONTINUE else "#f59e0b"
    
    # Render each action in the batch
    actions_html = []
    for i, action in enumerate(batch.actions, 1):
        params_html = "<br>".join([
            f"&nbsp;&nbsp;&nbsp;&nbsp;{k}: {json.dumps(v)}" for k, v in action.parameters.items()
        ]) if action.parameters else "&nbsp;&nbsp;&nbsp;&nbsp;(none)"
        
        actions_html.append(f'<div style="background: #f8fafc; border-left: 3px solid #3b82f6; padding: 0.75rem; margin-bottom: 0.5rem; border-radius: 0.375rem;">' +
            f'<div style="font-weight: 600; color: #1e293b; margin-bottom: 0.25rem;">Action {i}/{len(batch.actions)}</div>' +
            f'<div style="color: #475569; font-size: 0.875rem;"><strong>Tool:</strong> {action.tool_category}/{action.tool_name}<br><strong>Parameters:</strong><br>{params_html}</div>' +
            (f'<div style="color: #64748b; font-size: 0.8125rem; margin-top: 0.25rem; font-style: italic;">{action.reasoning}</div>' if action.reasoning else '') +
            '</div>')
    
    return f"""
    <div class="action-card" style="border-left: 4px solid #8b5cf6;">
        <div class="action-label">🎬 Proposed Batch Actions ({len(batch.actions)} actions)</div>
        <div style="background: {strategy_color}15; border-radius: 0.375rem; padding: 0.5rem; margin-bottom: 0.75rem;">
            <div style="color: {strategy_color}; font-weight: 500; font-size: 0.875rem;">
                {strategy_icon} Strategy: {strategy_text}
            </div>
        </div>
        <div class="action-reasoning" style="margin-bottom: 0.75rem;">
            <strong>Batch Reasoning:</strong> {batch.reasoning}
        </div>
        <div style="max-height: 400px; overflow-y: auto;">
            {''.join(actions_html)}
        </div>
    </div>
    """


def render_clarification_card(question: ClarificationQuestion) -> str:
    """Render the clarification question card."""
    options_html = ""
    if question.options:
        options_items = "".join([
            f'<span class="clarification-option">{opt}</span>' for opt in question.options
        ])
        options_html = f'<div class="clarification-options"><strong>Suggested options:</strong><br>{options_items}</div>'
    
    context_html = ""
    if question.context:
        context_html = f'<div class="clarification-context"><strong>Why I\'m asking:</strong> {question.context}</div>'
    
    return f'<div class="clarification-card"><div class="clarification-label">❓ Clarification Needed</div><div class="clarification-question">{question.question}</div>{context_html}{options_html}</div>'


def main():
    """Main application entry point."""
    init_session_state()
    
    # Header
    st.markdown('<div class="main-header">🤖 Smart Agent</div>', unsafe_allow_html=True)
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
        max_tokens = st.slider("Max Total Tokens (K)", 100, 10000, 10000) * 1000
        st.caption(f"💬 Context tracks current prompt size (fixed {CONTEXT_WINDOW_LIMIT:,} limit)")
        st.caption("💰 Total tracks cumulative token spend across all turns")
        
        st.divider()
    
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
            placeholder="Describe your goal...\n\nExample:\nI need to search for weather in San Francisco, calculate the wind chill factor, and summarize the results.",
            key="goal_input"
        )
        
        if st.button("🚀 Start Planning", type="primary", use_container_width=True):
            if input_text.strip():
                with st.spinner("Analyzing goal and creating initial plan..."):
                    session = agent.start_session(
                        goal_text=input_text,
                        max_tokens=max_tokens
                    )
                    st.session_state.current_session = session
                    st.session_state.input_text = ""  # Clear after starting session
                st.rerun()
            else:
                st.warning("Please enter a goal first.")
    
    else:
        # Active session - show visualization and controls
        col1, col2 = st.columns([3, 2])
        
        with col1:
            # Goal section
            st.markdown("### 🎯 Goal")
            st.markdown(f"""
            <div class="goal-box">
                <div class="goal-label">Your Objective</div>
                <div class="goal-text">{html.escape(session.goal.original_text)}</div>
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
            # Execution section with turn counter (at top for easy access)
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0;">🎮 Execution</h3>
                <span style="color: #64748b; font-size: 1.3rem; font-weight: 600;">Turn {session.budget.current_turn}</span>
            </div>
            """, unsafe_allow_html=True)
            
            # Check session status
            if session.status == SessionStatus.COMPLETED:
                # Celebration!
                st.balloons()
                
                # Prominent success card
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                            color: white; 
                            padding: 2rem; 
                            border-radius: 1rem; 
                            box-shadow: 0 10px 40px rgba(16, 185, 129, 0.3);
                            margin-bottom: 1.5rem;">
                    <div style="font-size: 3rem; text-align: center; margin-bottom: 0.5rem;">🎉</div>
                    <div style="font-size: 1.75rem; font-weight: bold; text-align: center; margin-bottom: 0.5rem;">
                        Goal Achieved!
                    </div>
                    <div style="text-align: center; opacity: 0.95; font-size: 1.1rem;">
                        Mission accomplished in {session.budget.current_turn} turns
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Show summary stats
                completed_count = len(session.completed_actions)
                token_pct = (session.budget.used_tokens / session.budget.max_tokens * 100) if session.budget.max_tokens > 0 else 0
                
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("✅ Actions", completed_count)
                with col_stat2:
                    st.metric("🔄 Turns", session.budget.current_turn)
                with col_stat3:
                    st.metric("💬 Tokens", f"{token_pct:.0f}%")
                
                # Show completed objectives
                if session.state.completed_objectives:
                    st.markdown("### 🎯 What We Accomplished")
                    for obj in session.state.completed_objectives[:8]:  # Show first 8
                        st.markdown(f"✓ {obj}")
                    if len(session.state.completed_objectives) > 8:
                        st.caption(f"...and {len(session.state.completed_objectives) - 8} more")
                
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🔄 Start New Session", type="primary", use_container_width=True):
                    st.session_state.current_session = None
                    st.session_state.turn_result = None
                    st.session_state.input_text = ""
                    st.rerun()
            
            elif session.status == SessionStatus.BUDGET_EXCEEDED:
                st.error("💸 Budget exceeded!")
                if st.button("🔄 New Session"):
                    st.session_state.current_session = None
                    st.session_state.turn_result = None
                    st.session_state.input_text = ""
                    st.rerun()
            
            elif session.status == SessionStatus.ABORTED:
                st.warning("🛑 Session aborted.")
                if st.button("🔄 New Session"):
                    st.session_state.current_session = None
                    st.session_state.turn_result = None
                    st.session_state.input_text = ""
                    st.rerun()
            
            else:
                # Get or show turn result
                turn_result = st.session_state.turn_result
                
                if turn_result is None:
                    # Run a turn to get proposed action
                    if st.button("▶️ Next Turn", type="primary", use_container_width=True, key="execute_next_turn"):
                        with st.spinner("Evaluating and planning..."):
                            turn_result = agent.run_turn()
                            st.session_state.turn_result = turn_result
                            st.session_state.current_session = agent.current_session
                        st.rerun()
                
                else:
                    # Show turn result
                    # Defensive check for turn_result validity
                    if not hasattr(turn_result, 'status') or turn_result.status is None:
                        st.error("⚠️ Invalid turn result - clearing and retrying")
                        st.session_state.turn_result = None
                        st.rerun()
                    
                    elif turn_result.status == "completed":
                        # Agent believes goal is achieved - ask user to confirm
                        
                        # Show agent's reasoning
                        st.markdown(f"""
                        <div class="state-card" style="border-left: 4px solid #10b981;">
                            <div class="state-label">✅ Agent Assessment (Turn {session.budget.current_turn})</div>
                            <div class="state-content">{turn_result.reasoning}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Show what was completed
                        if session.state.completed_objectives:
                            st.markdown("### 🎯 Completed Objectives")
                            for obj in session.state.completed_objectives[:8]:
                                st.markdown(f"✓ {obj}")
                            if len(session.state.completed_objectives) > 8:
                                st.caption(f"...and {len(session.state.completed_objectives) - 8} more")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Confirmation prompt
                        st.markdown("""
                        <div style="background: #fef3c7; 
                                    border-left: 4px solid #f59e0b; 
                                    padding: 1.25rem; 
                                    border-radius: 0.5rem; 
                                    margin-bottom: 1rem;">
                            <div style="color: #92400e; font-weight: 600; font-size: 1.1rem; margin-bottom: 0.5rem;">
                                🤔 Do you agree the goal is achieved?
                            </div>
                            <div style="color: #78350f; font-size: 0.95rem;">
                                The agent believes all objectives have been completed. Please confirm or provide feedback if more work is needed.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Check if we're showing feedback input
                        if st.session_state.get('show_completion_feedback', False):
                            st.markdown("**✏️ What else needs to be done?**")
                            completion_feedback = st.text_area(
                                "Please describe what's missing or what should be done differently:",
                                key="completion_feedback",
                                placeholder="e.g., 'We still need to test the deployment' or 'The email template needs revision'",
                                height=120
                            )
                            
                            col_submit_fb, col_cancel_fb = st.columns(2)
                            
                            with col_submit_fb:
                                if st.button("📤 Submit Feedback", type="primary", use_container_width=True, disabled=not completion_feedback, key="submit_completion_feedback"):
                                    if completion_feedback:
                                        # Add feedback as a clarification answer saying goal NOT complete
                                        from models import ClarificationQuestion, ClarificationAnswer
                                        feedback_question = ClarificationQuestion(
                                            question="Is the goal achieved?",
                                            context="Agent believes goal is complete but needs user confirmation",
                                            options=[]
                                        )
                                        feedback_answer = ClarificationAnswer(
                                            answer=f"No, not yet. {completion_feedback}"
                                        )
                                        agent.provide_clarification(feedback_question, feedback_answer.answer)
                                        
                                        st.session_state.turn_result = None
                                        st.session_state.current_session = agent.current_session
                                        st.session_state.show_completion_feedback = False
                                        st.toast("Feedback submitted! Agent will continue...", icon="🔄")
                                        st.rerun()
                            
                            with col_cancel_fb:
                                if st.button("❌ Cancel", use_container_width=True, key="cancel_completion_feedback"):
                                    st.session_state.show_completion_feedback = False
                                    st.rerun()
                        
                        else:
                            # Show confirmation buttons
                            col_yes, col_no = st.columns(2)
                            
                            with col_yes:
                                if st.button("✅ Yes, Goal Achieved!", type="primary", use_container_width=True, key="confirm_goal_achieved"):
                                    # Mark session as completed and show celebration
                                    agent.session_manager.complete_session()
                                    st.session_state.turn_result = None
                                    st.session_state.current_session = agent.current_session
                                    st.rerun()
                            
                            with col_no:
                                if st.button("✏️ No, Provide Feedback", use_container_width=True, key="provide_completion_feedback"):
                                    st.session_state.show_completion_feedback = True
                                    st.rerun()
                    
                    elif turn_result.status == "awaiting_approval":
                        # Check if this is a batch or single action
                        is_batch = turn_result.proposed_batch is not None
                        action = turn_result.proposed_action
                        
                        # Normalize to always have a batch (for unified execution API)
                        if is_batch:
                            batch = turn_result.proposed_batch
                        else:
                            # Create a single-action batch for unified API
                            batch = BatchAction(
                                id=generate_id(),
                                actions=[action],
                                failure_strategy=FailureStrategy.STOP_ON_ERROR,
                                reasoning=""
                            )
                        
                        # Show agent's overall reasoning for this turn
                        if turn_result.reasoning:
                            st.markdown(f"""
                            <div class="state-card" style="border-left: 4px solid #6366f1;">
                                <div class="state-label">🧠 Agent's Analysis (Turn {session.budget.current_turn})</div>
                                <div class="state-content">{turn_result.reasoning}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # Display batch or single action
                        if is_batch:
                            st.markdown(render_batch_card(batch), unsafe_allow_html=True)
                        else:
                            st.markdown(render_action_card(action), unsafe_allow_html=True)
                        
                        # Check if we're in rejection mode
                        if st.session_state.get('show_rejection_input', False):
                            # Show rejection feedback input
                            st.markdown("---")
                            st.markdown("**✏️ Provide feedback for the agent:**")
                            rejection_feedback = st.text_area(
                                "What should the agent do instead?",
                                key="rejection_feedback",
                                placeholder="e.g., 'Use email instead of Slack' or 'The parameters are wrong - use X instead of Y'",
                                height=100
                            )
                            
                            col_submit_rej, col_cancel_rej = st.columns(2)
                            
                            with col_submit_rej:
                                if st.button("📤 Submit Feedback", type="primary", use_container_width=True, disabled=not rejection_feedback, key="submit_rejection_feedback"):
                                    if rejection_feedback:
                                        # Handle batch vs single action rejection
                                        if is_batch:
                                            # For batches, skip all actions and provide feedback as clarification
                                            for act in batch.actions:
                                                agent.skip_action(act)
                                            # Provide feedback as a clarification to guide next steps
                                            from models import ClarificationQuestion, ClarificationAnswer
                                            feedback_question = ClarificationQuestion(
                                                question="How should I adjust the proposed batch?",
                                                context=f"User rejected batch of {len(batch.actions)} actions",
                                                options=[]
                                            )
                                            agent.provide_clarification(feedback_question, rejection_feedback)
                                        else:
                                            # Single action - use reject_action
                                            agent.reject_action(action, rejection_feedback)
                                        
                                        st.session_state.turn_result = None
                                        st.session_state.current_session = agent.current_session
                                        st.session_state.show_rejection_input = False
                                        st.toast("Feedback submitted! Agent will adjust...", icon="✏️")
                                        st.rerun()
                            
                            with col_cancel_rej:
                                if st.button("❌ Cancel", use_container_width=True, key="cancel_rejection_feedback"):
                                    st.session_state.show_rejection_input = False
                                    st.rerun()
                        else:
                            # Show normal action buttons
                            col_approve, col_reject, col_skip, col_abort = st.columns(4)
                            
                            with col_approve:
                                if st.button("✅ Approve", type="primary", use_container_width=True, key="approve_action"):
                                    with st.spinner("Executing..."):
                                        # Always use execute_batch (handles both single and multiple actions)
                                        batch_result = agent.execute_batch(batch)
                                        success_msg = f"{batch_result.success_count}/{len(batch_result.results)} succeeded"
                                        if batch_result.overall_success:
                                            st.toast(f"Batch completed! {success_msg}", icon="✅")
                                        else:
                                            st.toast(f"Batch partial success: {success_msg}", icon="⚠️")
                                    
                                    st.session_state.turn_result = None
                                    st.session_state.current_session = agent.current_session
                                    st.rerun()
                            
                            with col_reject:
                                if st.button("✏️ Reject with Feedback", use_container_width=True, key="show_rejection_input"):
                                    st.session_state.show_rejection_input = True
                                    st.rerun()
                            
                            with col_skip:
                                if st.button("⏭️ Skip", use_container_width=True, key="skip_action"):
                                    # Handle batch vs single action skip
                                    if is_batch:
                                        # Skip all actions in batch
                                        for act in batch.actions:
                                            agent.skip_action(act)
                                    else:
                                        agent.skip_action(action)
                                    st.session_state.turn_result = None
                                    st.session_state.current_session = agent.current_session
                                    st.rerun()
                            
                            with col_abort:
                                if st.button("🛑 Abort", use_container_width=True, key="abort_session"):
                                    agent.abort_session()
                                    st.session_state.turn_result = None
                                    st.session_state.current_session = agent.current_session
                                    st.rerun()
                    
                    elif turn_result.status == "needs_clarification":
                        question = turn_result.clarification_question
                        
                        # Show agent's reasoning
                        if turn_result.reasoning:
                            st.markdown(f"""
                            <div class="state-card" style="border-left: 4px solid #8b5cf6;">
                                <div class="state-label">🧠 Agent's Analysis (Turn {session.budget.current_turn})</div>
                                <div class="state-content">{turn_result.reasoning}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        # Show clarification card
                        st.markdown(render_clarification_card(question), unsafe_allow_html=True)
                        
                        # Answer input
                        if question.options:
                            # If options provided, show as radio buttons
                            selected_option = st.radio(
                                "Select your answer:",
                                options=question.options + ["Other (type below)"],
                                key="clarification_radio"
                            )
                            
                            # Always show text input for additional details
                            text_placeholder = "Type your answer..." if selected_option == "Other (type below)" else "Provide additional details for your selected option..."
                            text_input = st.text_input(
                                "Additional details:" if selected_option != "Other (type below)" else "Your answer:",
                                key="clarification_text_with_options",
                                placeholder=text_placeholder
                            )
                            
                            # Combine selection with text if provided
                            if selected_option == "Other (type below)":
                                answer = text_input
                            else:
                                # If text is provided, combine it with the selected option
                                answer = f"{selected_option}\n{text_input}" if text_input else selected_option
                        else:
                            # Free text input
                            answer = st.text_area(
                                "Your answer:",
                                key="clarification_text",
                                placeholder="Type your answer...",
                                height=100
                            )
                        
                        col_submit, col_skip_q, col_abort_q = st.columns(3)
                        
                        with col_submit:
                            if st.button("📤 Submit Answer", type="primary", use_container_width=True, disabled=not answer):
                                if answer:
                                    agent.provide_clarification(question, answer)
                                    st.session_state.turn_result = None
                                    st.session_state.current_session = agent.current_session
                                    st.toast("Answer submitted! Agent will continue...", icon="✅")
                                    st.rerun()
                        
                        with col_skip_q:
                            if st.button("⏭️ Skip Question", use_container_width=True):
                                # Submit "No answer provided" and continue
                                agent.provide_clarification(question, "[User skipped this question]")
                                st.session_state.turn_result = None
                                st.session_state.current_session = agent.current_session
                                st.rerun()
                        
                        with col_abort_q:
                            if st.button("🛑 Abort Session", use_container_width=True):
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
                    
                    elif turn_result.status == "error":
                        st.error("❌ Agent Error")
                        st.markdown(f"**Reasoning:** {turn_result.reasoning}")
                        if turn_result.error:
                            st.code(turn_result.error, language=None)
                        
                        col_retry, col_abort_err = st.columns(2)
                        with col_retry:
                            if st.button("🔄 Try Again", type="primary", use_container_width=True, key="retry_after_error"):
                                st.session_state.turn_result = None
                                st.rerun()
                        with col_abort_err:
                            if st.button("🛑 Abort Session", use_container_width=True, key="abort_after_error"):
                                agent.abort_session()
                                st.session_state.turn_result = None
                                st.session_state.current_session = agent.current_session
                                st.rerun()
                    
                    else:
                        # Unexpected status - clear and retry
                        st.error(f"⚠️ Unexpected turn status: {turn_result.status}")
                        st.markdown(f"**Reasoning:** {turn_result.reasoning if hasattr(turn_result, 'reasoning') else 'N/A'}")
                        if st.button("🔄 Clear and Retry", key="clear_unexpected_status"):
                            st.session_state.turn_result = None
                            st.rerun()
            
            st.divider()
            
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
                    📋 Upcoming Tasks {updated_badge}
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
            steps = plan.steps
            if steps:
                # Calculate progress
                progress = plan.get_progress()
                completed = progress["completed"]
                total = progress["total"]
                failed = progress["failed"]
                skipped = progress["skipped"]
                
                # Progress bar (outside scrollable container)
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
                
                # Build all plan steps HTML in one string
                all_steps_html = []
                for i, step in enumerate(steps):
                    step_html = render_plan_step(step)
                    # Add "NEXT" indicator
                    if i == current_idx and step.status == StepStatus.PLANNED:
                        step_html = step_html.replace(
                            '</div>\n    </div>',
                            '<div style="font-size: 0.75rem; color: #f59e0b; margin-top: 0.25rem;">⬅️ NEXT</div></div>\n    </div>'
                        )
                    all_steps_html.append(step_html)
                
                # Render all steps in scrollable container with a single markdown call
                full_html = '<div class="plan-steps-container">' + ''.join(all_steps_html) + '</div>'
                st.markdown(full_html, unsafe_allow_html=True)
            else:
                st.info("No plan yet.")
            
            # Completed actions section
            if session.completed_actions:
                st.divider()
                st.markdown("### ✅ Completed Actions")
                
                for ca in reversed(session.completed_actions[-10:]):  # Show last 10
                    # Show tool info and description
                    tool_info = f"{ca.tool_category}/{ca.tool_name}"
                    st.markdown(f"""
                    <div class="history-entry" style="border-left: 3px solid #10b981;">
                        <div class="history-turn">Turn {ca.turn}</div>
                        <div style="color: #059669; font-weight: 600; margin-bottom: 0.25rem;">{html.escape(tool_info)}</div>
                        <div style="color: #374151; font-size: 0.9rem;">{html.escape(ca.description)}</div>
                        <div style="color: #64748b; margin-top: 0.25rem; font-size: 0.875rem;">✓ {html.escape(ca.result_summary)}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
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
            
            # Clarification history
            if session.clarifications:
                st.divider()
                st.markdown("### 💬 Clarifications")
                
                for entry in reversed(session.clarifications[-3:]):
                    st.markdown(f"""
                    <div class="history-entry" style="border-left: 3px solid #8b5cf6;">
                        <div class="history-turn">Turn {entry.turn}</div>
                        <div style="color: #5b21b6; font-weight: 500;">Q: {entry.question.question[:80]}{'...' if len(entry.question.question) > 80 else ''}</div>
                        <div style="color: #059669; margin-top: 0.25rem;">A: {entry.answer.answer[:80]}{'...' if len(entry.answer.answer) > 80 else ''}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Rejection history
            if session.rejections:
                st.divider()
                st.markdown("### ✏️ Rejections")
                
                for entry in reversed(session.rejections[-3:]):
                    action = entry.rejection.rejected_action
                    st.markdown(f"""
                    <div class="history-entry" style="border-left: 3px solid #f59e0b;">
                        <div class="history-turn">Turn {entry.turn}</div>
                        <div style="color: #b45309; font-weight: 500;">Rejected: {action.tool_category}/{action.tool_name}</div>
                        <div style="color: #1f2937; margin-top: 0.25rem;">Feedback: {entry.rejection.feedback[:80]}{'...' if len(entry.rejection.feedback) > 80 else ''}</div>
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
            st.session_state.input_text = ""
            agent.session_manager.current_session = None
            st.rerun()


if __name__ == "__main__":
    main()
