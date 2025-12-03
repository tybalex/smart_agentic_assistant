"""
Streamlit UI for the Task Agent.
Provides text input, task visualization, and execution controls.
"""

import streamlit as st
import json
from typing import Optional, Dict, Any, List

from models import TaskStatus, Task
from agent import TaskAgent, create_agent
from task_manager import TaskManager
from tool_client import ToolRegistryClient


# Page configuration
st.set_page_config(
    page_title="Task Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for text highlighting and styling
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
    
    /* Text highlighting styles */
    .highlighted-text {
        font-family: 'Monaco', 'Menlo', monospace;
        font-size: 1rem;
        line-height: 1.8;
        padding: 1.5rem;
        background: #1a1a2e;
        border-radius: 12px;
        color: #e2e8f0;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    
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
    
    /* Task card styling */
    .task-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        border-left: 4px solid #6366f1;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .task-card:hover {
        transform: translateX(4px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    .task-card.completed {
        border-left-color: #10b981;
        background: #f0fdf4;
    }
    
    .task-card.current {
        border-left-color: #f59e0b;
        background: #fffbeb;
    }
    
    .task-card.failed {
        border-left-color: #ef4444;
        background: #fef2f2;
    }
    
    .task-card.skipped {
        border-left-color: #6b7280;
        background: #f9fafb;
        opacity: 0.7;
    }
    
    .task-title {
        font-weight: 600;
        font-size: 1rem;
        color: #1f2937;
        margin-bottom: 0.25rem;
    }
    
    .task-description {
        font-size: 0.875rem;
        color: #6b7280;
    }
    
    /* Progress bar */
    .progress-container {
        background: #e5e7eb;
        border-radius: 9999px;
        height: 8px;
        overflow: hidden;
        margin: 1rem 0;
    }
    
    .progress-bar {
        height: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        border-radius: 9999px;
        transition: width 0.5s ease;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .status-pending { background: #dbeafe; color: #1d4ed8; }
    .status-in-progress { background: #fef3c7; color: #b45309; }
    .status-completed { background: #d1fae5; color: #065f46; }
    .status-failed { background: #fee2e2; color: #991b1b; }
    .status-skipped { background: #f3f4f6; color: #4b5563; }
    
    /* Execution plan card */
    .plan-card {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    
    /* Agent notes */
    .agent-note {
        background: #fefce8;
        border-left: 4px solid #eab308;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
        font-size: 0.875rem;
        color: #713f12;
    }
    
    /* Tool health indicator */
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
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize Streamlit session state variables."""
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "current_session" not in st.session_state:
        st.session_state.current_session = None
    if "current_task_info" not in st.session_state:
        st.session_state.current_task_info = None
    if "execution_log" not in st.session_state:
        st.session_state.execution_log = []
    if "input_text" not in st.session_state:
        st.session_state.input_text = ""


def get_agent() -> TaskAgent:
    """Get or create the agent instance."""
    if st.session_state.agent is None:
        st.session_state.agent = create_agent()
    return st.session_state.agent


def render_highlighted_text(text: str, tasks: List[Task]) -> str:
    """
    Render the original text with highlighting based on task status.
    """
    if not tasks:
        return f'<div class="highlighted-text">{text}</div>'
    
    # Build a list of spans with their status
    spans = []
    for task in tasks:
        if task.text_span:
            spans.append({
                "start": task.text_span.start,
                "end": task.text_span.end,
                "status": task.status,
                "task_id": task.id
            })
    
    # Sort spans by start position
    spans.sort(key=lambda x: x["start"])
    
    # Build highlighted HTML
    result = []
    last_end = 0
    
    for span in spans:
        # Add unhighlighted text before this span
        if span["start"] > last_end:
            result.append(text[last_end:span["start"]])
        
        # Determine CSS class based on status
        status = span["status"]
        if status == TaskStatus.COMPLETED:
            css_class = "span-completed"
        elif status in [TaskStatus.IN_PROGRESS, TaskStatus.AWAITING_CONFIRMATION]:
            css_class = "span-current"
        elif status == TaskStatus.FAILED:
            css_class = "span-failed"
        elif status == TaskStatus.SKIPPED:
            css_class = "span-skipped"
        else:
            css_class = "span-pending"
        
        # Add highlighted span
        span_text = text[span["start"]:span["end"]]
        result.append(f'<span class="{css_class}">{span_text}</span>')
        
        last_end = span["end"]
    
    # Add remaining text
    if last_end < len(text):
        result.append(text[last_end:])
    
    highlighted = "".join(result)
    return f'<div class="highlighted-text">{highlighted}</div>'


def render_task_card(task: Task, is_current: bool = False) -> str:
    """Render a task as a styled card."""
    status_class = ""
    if task.status == TaskStatus.COMPLETED:
        status_class = "completed"
        status_icon = "✅"
    elif task.status in [TaskStatus.IN_PROGRESS, TaskStatus.AWAITING_CONFIRMATION]:
        status_class = "current"
        status_icon = "🔄"
    elif task.status == TaskStatus.FAILED:
        status_class = "failed"
        status_icon = "❌"
    elif task.status == TaskStatus.SKIPPED:
        status_class = "skipped"
        status_icon = "⏭️"
    else:
        status_icon = "⏳"
    
    return f"""
    <div class="task-card {status_class}">
        <div class="task-title">{status_icon} {task.title}</div>
        <div class="task-description">{task.description}</div>
    </div>
    """


def render_progress_bar(progress: Dict[str, int]) -> str:
    """Render a progress bar."""
    total = progress["total"]
    if total == 0:
        return ""
    
    completed = progress["completed"] + progress["skipped"]
    percentage = (completed / total) * 100
    
    return f"""
    <div class="progress-container">
        <div class="progress-bar" style="width: {percentage}%"></div>
    </div>
    <div style="text-align: center; color: #6b7280; font-size: 0.875rem;">
        {completed}/{total} tasks completed ({percentage:.0f}%)
    </div>
    """


def main():
    """Main application entry point."""
    init_session_state()
    
    # Header
    st.markdown('<div class="main-header">🤖 Task Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Intelligent task execution with AI-powered planning</div>', unsafe_allow_html=True)
    
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
        sessions = agent.task_manager.list_sessions()
        
        if sessions:
            session_options = {s["id"]: f"{s['id']} - {s['preview'][:30]}..." for s in sessions}
            selected_session = st.selectbox(
                "Load existing session",
                options=[""] + list(session_options.keys()),
                format_func=lambda x: "Select..." if x == "" else session_options.get(x, x)
            )
            
            if selected_session and st.button("Load Session"):
                session = agent.task_manager.load_session(selected_session)
                if session:
                    st.session_state.current_session = session
                    st.session_state.input_text = session.original_text
                    # Restore conversation context for the agent
                    agent.restore_session_context()
                    st.rerun()
        else:
            st.caption("No saved sessions")
        
        st.divider()
        
        # Legend
        st.markdown("### 🎨 Legend")
        st.markdown("""
        <div style="font-size: 0.875rem;">
            <span class="span-completed">Completed</span><br><br>
            <span class="span-current">Current</span><br><br>
            <span class="span-pending">Pending</span><br><br>
            <span class="span-failed">Failed</span><br><br>
            <span class="span-skipped">Skipped</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Main content area
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("### 📝 Input & Visualization")
        
        # If no active session, show input
        if st.session_state.current_session is None:
            input_text = st.text_area(
                "Enter your tasks",
                value=st.session_state.input_text,
                height=200,
                placeholder="Enter the text containing tasks you want to execute...\n\nExample:\nI need to search for weather information for San Francisco, then calculate the average temperature for the week, and finally send a summary email to my team."
            )
            
            if st.button("🚀 Parse & Start", type="primary", use_container_width=True):
                if input_text.strip():
                    with st.spinner("Analyzing text and extracting tasks..."):
                        agent = get_agent()
                        session, tasks = agent.initialize_session(input_text)
                        st.session_state.current_session = session
                        st.session_state.input_text = input_text
                    st.rerun()
                else:
                    st.warning("Please enter some text first.")
        
        else:
            # Show highlighted text
            session = st.session_state.current_session
            tasks = agent.task_manager.get_all_tasks()
            
            st.markdown("#### Original Text (Highlighted)")
            highlighted_html = render_highlighted_text(session.original_text, tasks)
            st.markdown(highlighted_html, unsafe_allow_html=True)
            
            # Progress
            progress = session.get_progress()
            st.markdown(render_progress_bar(progress), unsafe_allow_html=True)
            
            # Reset button
            if st.button("🔄 New Session"):
                st.session_state.current_session = None
                st.session_state.current_task_info = None
                st.session_state.execution_log = []
                st.rerun()
    
    with col2:
        st.markdown("### 📋 Task List")
        
        if st.session_state.current_session:
            agent = get_agent()
            tasks = agent.task_manager.get_all_tasks()
            
            if tasks:
                for task in tasks:
                    is_current = task.status in [TaskStatus.IN_PROGRESS, TaskStatus.AWAITING_CONFIRMATION]
                    st.markdown(render_task_card(task, is_current), unsafe_allow_html=True)
            else:
                st.info("No tasks extracted yet.")
            
            st.divider()
            
            # Execution controls
            st.markdown("### 🎮 Execution")
            
            current_task_info = st.session_state.current_task_info
            
            # Get next task if we don't have one
            if current_task_info is None:
                next_task_info = agent.process_next_task()
                if next_task_info:
                    st.session_state.current_task_info = next_task_info
                    current_task_info = next_task_info
            
            if current_task_info:
                task = current_task_info["task"]
                plan = current_task_info["plan"]
                explanation = current_task_info["explanation"]
                
                st.markdown("#### Next Task")
                st.markdown(f'<div class="plan-card">{explanation}</div>', unsafe_allow_html=True)
                
                col_confirm, col_skip = st.columns(2)
                
                with col_confirm:
                    if st.button("✅ Confirm & Execute", type="primary", use_container_width=True):
                        with st.spinner("Executing..."):
                            result = agent.confirm_and_execute(task.id, plan)
                        
                        # Log the execution
                        st.session_state.execution_log.append({
                            "task": task.title,
                            "result": result
                        })
                        
                        # Clear current task info to get next
                        st.session_state.current_task_info = None
                        
                        # Refresh session data
                        st.session_state.current_session = agent.task_manager.current_session
                        st.rerun()
                
                with col_skip:
                    if st.button("⏭️ Skip", use_container_width=True):
                        agent.skip_task(task.id)
                        st.session_state.current_task_info = None
                        st.session_state.current_session = agent.task_manager.current_session
                        st.rerun()
            
            else:
                # Check if all tasks are done
                progress = agent.task_manager.current_session.get_progress()
                if progress["pending"] == 0 and progress["in_progress"] == 0:
                    st.success("🎉 All tasks completed!")
                else:
                    st.info("No pending tasks to execute.")
            
            # Execution log
            if st.session_state.execution_log:
                st.divider()
                st.markdown("### 📜 Execution Log")
                
                for i, log_entry in enumerate(reversed(st.session_state.execution_log[-5:])):
                    exec_result = log_entry["result"]["execution_result"]
                    status = "✅" if exec_result.get("success") else "❌"
                    st.markdown(f"**{status} {log_entry['task']}**")
                    
                    if exec_result.get("success"):
                        with st.expander("View Result"):
                            st.json(exec_result.get("result", {}))
                    else:
                        st.error(exec_result.get("error", "Unknown error"))
            
            # Agent notes
            if agent.task_manager.current_session.agent_notes:
                st.divider()
                st.markdown("### 🤖 Agent Notes")
                for note in agent.task_manager.current_session.agent_notes[-3:]:
                    st.markdown(f'<div class="agent-note">{note}</div>', unsafe_allow_html=True)
        
        else:
            st.info("Enter text and click 'Parse & Start' to begin.")


if __name__ == "__main__":
    main()

