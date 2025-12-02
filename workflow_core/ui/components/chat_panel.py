"""
Chat panel component for workflow agent interaction
"""

import streamlit as st
from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from src.agent import WorkflowAgent
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False


def render_chat_panel(workspace_dir: str = "."):
    """
    Render chat panel in the right column.
    
    Args:
        workspace_dir: Directory where workflow files are saved
    """
    
    # Simple header
    st.markdown("## 🤖 AI Assistant")
    st.caption("Chat with the workflow agent")
    
    # Check if agent is available
    if not AGENT_AVAILABLE:
        st.error("❌ WorkflowAgent not available")
        st.info("Install dependencies: `pip install anthropic`")
        return
    
    # Check for API key
    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("⚠️ ANTHROPIC_API_KEY not set")
        st.info("Set it with: `export ANTHROPIC_API_KEY=your-key`")
        return
    
    # Initialize agent in session state
    if "workflow_agent" not in st.session_state:
        try:
            st.session_state.workflow_agent = WorkflowAgent(workspace_dir=workspace_dir)
            st.session_state.agent_initialized = True
        except Exception as e:
            st.error(f"Failed to initialize agent: {e}")
            st.session_state.agent_initialized = False
            return
    
    # Initialize chat history in session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    st.divider()
    
    # Create a scrollable container for chat messages
    chat_container = st.container(height=500, border=True)
    with chat_container:
        if not st.session_state.chat_history:
            st.info("👋 Start chatting!\n\nAsk me to modify your workflow.")
        else:
            for message in st.session_state.chat_history:
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.markdown(message["content"])
                else:
                    with st.chat_message("assistant"):
                        # Show tool calls if available
                        tool_calls = message.get("tool_calls", [])
                        if tool_calls:
                            with st.expander(f"🔧 Agent Actions ({len(tool_calls)} tools)", expanded=False):
                                for idx, tool_name in enumerate(tool_calls, 1):
                                    st.caption(f"{idx}. `{tool_name}`")
                        
                        # Show response
                        st.markdown(message["content"])
    
    # Chat input
    user_input = st.chat_input("Ask me anything...")
    
    if user_input:
        # Add user message to history
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input,
            "tool_calls": []
        })
        
        # Show user message
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Get agent response
        with st.chat_message("assistant"):
            with st.spinner("Agent thinking..."):
                try:
                    response = st.session_state.workflow_agent.chat(user_input)
                    
                    # Get tool calls from the agent
                    tool_calls = st.session_state.workflow_agent.get_last_tool_calls()
                    
                    # Show tool calls if any
                    if tool_calls:
                        with st.expander(f"🔧 Agent Actions ({len(tool_calls)} tools used)", expanded=False):
                            for idx, tool_name in enumerate(tool_calls, 1):
                                st.caption(f"{idx}. `{tool_name}`")
                    
                    # Show response
                    st.markdown(response)
                    
                    # Add assistant response to history with tool calls
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response,
                        "tool_calls": tool_calls
                    })
                    
                    # Check if workflow was modified
                    current_workflow = st.session_state.workflow_agent.get_current_workflow()
                    if current_workflow:
                        # Update the main workflow view
                        st.session_state.modified_workflow = current_workflow
                        st.session_state.workflow_modified = True
                        st.success("✨ Workflow updated by agent!")
                    
                    # Rerun to show updates
                    st.rerun()
                    
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": error_msg,
                        "tool_calls": []
                    })
    
    # Actions
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.chat_history = []
            if "workflow_agent" in st.session_state:
                st.session_state.workflow_agent.reset_conversation()
            st.rerun()
    
    with col2:
        msg_count = len(st.session_state.chat_history)
        st.metric("Messages", msg_count)
    
    # Help
    with st.expander("💡 Examples"):
        st.markdown("""
        - "Add error handling to create_account"
        - "Create a new Slack notification node"
        - "Add retry logic to all API calls"
        """)

