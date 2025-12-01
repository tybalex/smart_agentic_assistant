"""
Node card component for displaying workflow nodes
"""

import streamlit as st
import json
from typing import Optional
from src.schema import WorkflowNode, NodeResult


def render_node_card(
    node: WorkflowNode,
    index: int,
    total: int,
    mode: str = "view",
    execution_result: Optional[NodeResult] = None
):
    """
    Render a single workflow node as a card.
    
    Args:
        node: WorkflowNode to display
        index: Index of this node in the workflow (for numbering)
        total: Total number of nodes
        mode: Display mode - "view", "edit", or "run" (Stage 1: only "view" implemented)
        execution_result: Optional execution result to display
    """
    
    # Node type emoji mapping
    type_icons = {
        "function_call": "🔧",
        "api_call": "🌐",
        "transform": "🔄",
        "condition": "❓",
        "log": "📝",
        "delay": "⏰",
    }
    icon = type_icons.get(node.type, "📦")
    
    # Create a container with custom styling
    with st.container():
        # Header with node number and title
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.markdown(f"#### {icon} Node {index}/{total}: `{node.id}`")
        
        with col2:
            # Placeholder for action buttons (Stage 2 & 3)
            pass
        
        # Node type badge
        st.markdown(f"**Type:** `{node.type}`")
        
        # Description
        if node.description:
            st.markdown(f"*{node.description}*")
        
        # Dependencies
        if node.depends_on:
            deps_str = ", ".join([f"`{dep}`" for dep in node.depends_on])
            st.markdown(f"**Depends on:** {deps_str} ⬆️")
        else:
            st.markdown("**Depends on:** *None (root node)*")
        
        # Configuration section
        if node.config:
            with st.expander("⚙️ Configuration", expanded=True):
                # Pretty print the config
                st.json(node.config)
        
        # Optional fields
        optional_fields = []
        
        if node.condition:
            optional_fields.append(f"**Condition:** `{node.condition}`")
        
        if node.on_error:
            optional_fields.append(f"**On Error:** `{node.on_error}`")
        
        if node.timeout:
            optional_fields.append(f"**Timeout:** {node.timeout}s")
        
        if node.retry:
            optional_fields.append(f"**Retry:** {json.dumps(node.retry)}")
        
        if optional_fields:
            with st.expander("🔧 Advanced Settings", expanded=False):
                for field in optional_fields:
                    st.markdown(field)
        
        # Execution result (if available)
        if execution_result:
            _render_execution_result(execution_result)
        
        # Visual separator between nodes
        st.markdown("---")


def _render_execution_result(result: NodeResult):
    """
    Display execution result for a node.
    
    Args:
        result: NodeResult to display
    """
    status_colors = {
        "success": "🟢",
        "failed": "🔴",
        "skipped": "⚪",
    }
    
    status_icon = status_colors.get(result.status, "⚫")
    
    with st.expander(f"{status_icon} Execution Result: {result.status.upper()}", expanded=True):
        cols = st.columns(2)
        
        with cols[0]:
            st.metric("Status", result.status)
        
        with cols[1]:
            if result.execution_time:
                st.metric("Execution Time", f"{result.execution_time:.3f}s")
        
        # Output
        if result.output:
            st.markdown("**Output:**")
            # Try to format as JSON if possible
            try:
                if isinstance(result.output, (dict, list)):
                    st.json(result.output)
                else:
                    st.code(str(result.output))
            except:
                st.code(str(result.output))
        
        # Error
        if result.error:
            st.error(f"**Error:** {result.error}")
        
        # Metadata
        if result.metadata:
            with st.expander("Metadata", expanded=False):
                st.json(result.metadata)

