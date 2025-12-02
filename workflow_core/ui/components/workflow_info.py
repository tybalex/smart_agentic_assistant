"""
Workflow information display component
"""

import streamlit as st
from src.schema import WorkflowDefinition


def render_workflow_info(workflow: WorkflowDefinition):
    """
    Display workflow metadata and summary information.
    
    Args:
        workflow: WorkflowDefinition to display
    """
    # Header section with workflow name
    st.markdown(f"### 📋 {workflow.metadata.name}")
    
    # Description
    if workflow.metadata.description:
        st.markdown(f"*{workflow.metadata.description}*")
    
    # Metadata in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Version", workflow.metadata.version)
    
    with col2:
        st.metric("Total Nodes", len(workflow.nodes))
    
    with col3:
        node_types = set(node.type for node in workflow.nodes)
        st.metric("Node Types", len(node_types))
    
    # Variables section
    if workflow.variables:
        with st.expander("🔤 Global Variables (Editable in Sidebar)", expanded=True):
            st.caption("💡 You can edit these values in the sidebar under '🔤 Workflow Variables'")
            
            # Display in a nice table format
            cols = st.columns([2, 3])
            with cols[0]:
                st.markdown("**Variable**")
            with cols[1]:
                st.markdown("**Value**")
            
            st.divider()
            
            for key, value in workflow.variables.items():
                cols = st.columns([2, 3])
                with cols[0]:
                    st.markdown(f"`{key}`")
                with cols[1]:
                    # Show value with appropriate formatting
                    if isinstance(value, bool):
                        st.markdown(f"✅ `{value}`" if value else f"❌ `{value}`")
                    elif isinstance(value, (int, float)):
                        st.markdown(f"🔢 `{value}`")
                    else:
                        st.markdown(f"📝 `{value}`")
    
    # Additional metadata
    if workflow.metadata.author or workflow.metadata.tags:
        with st.expander("ℹ️ Additional Info", expanded=False):
            if workflow.metadata.author:
                st.write(f"**Author:** {workflow.metadata.author}")
            if workflow.metadata.tags:
                st.write(f"**Tags:** {', '.join(workflow.metadata.tags)}")
            if workflow.metadata.created_at:
                st.write(f"**Created:** {workflow.metadata.created_at}")
            if workflow.metadata.updated_at:
                st.write(f"**Updated:** {workflow.metadata.updated_at}")
    
    st.divider()

