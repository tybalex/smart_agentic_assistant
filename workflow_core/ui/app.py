"""
Smart Workflow Visualizer - Main Streamlit Application

Stage 1: View workflow structure and node details
Stage 2: Edit nodes through UI (coming soon)
Stage 3: Run individual nodes (coming soon)

Usage:
    streamlit run ui/app.py
"""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.utils.loader import find_workflow_files, load_workflow_file, get_workflow_summary
from ui.components.workflow_info import render_workflow_info
from ui.components.node_card import render_node_card


# Page configuration
st.set_page_config(
    page_title="Smart Workflow Visualizer",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)


def main():
    """Main application entry point"""
    
    # Header
    st.title("🔧 Smart Workflow Visualizer")
    st.markdown("*View, understand, and interact with your AI-powered workflows*")
    
    st.divider()
    
    # Sidebar - File selection and options
    with st.sidebar:
        st.header("📁 Workflow Files")
        
        # Directory selector
        workspace_dir = st.text_input(
            "Workspace Directory",
            value=".",
            help="Directory containing workflow YAML files"
        )
        
        # Find workflow files
        workflow_files = find_workflow_files(workspace_dir)
        
        if not workflow_files:
            st.warning("No workflow files (.yaml/.yml) found in this directory.")
            st.info("Create a workflow using the agent or place YAML files in this directory.")
            st.stop()
        
        # File selector
        selected_file = st.selectbox(
            "Select Workflow",
            options=workflow_files,
            format_func=lambda x: Path(x).name
        )
        
        # Reload button
        if st.button("↻ Reload Workflow", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        
        # Stage indicator
        st.markdown("### 🎯 Current Stage")
        st.success("**Stage 1:** View Mode ✅")
        st.info("**Stage 2:** Edit Mode 🚧")
        st.info("**Stage 3:** Run Nodes 🚧")
        
        st.divider()
        
        # Options
        st.markdown("### ⚙️ Display Options")
        show_execution_order = st.checkbox("Show Execution Order", value=True)
        show_node_index = st.checkbox("Show Node Numbers", value=True)
    
    # Main content area
    if selected_file:
        # Load workflow
        workflow = load_workflow_file(selected_file)
        
        if workflow is None:
            st.error(f"Failed to load workflow from {selected_file}")
            st.stop()
        
        # Display workflow information
        render_workflow_info(workflow)
        
        # Show execution order if requested
        if show_execution_order:
            try:
                sorted_nodes = workflow.topological_sort()
                execution_order = [node.id for node in sorted_nodes]
                
                st.markdown("### 🔀 Execution Order")
                order_str = " → ".join([f"`{node_id}`" for node_id in execution_order])
                st.markdown(order_str)
                st.divider()
            except ValueError as e:
                st.error(f"⚠️ Workflow validation error: {e}")
                st.warning("Showing nodes in definition order instead.")
                sorted_nodes = workflow.nodes
        else:
            sorted_nodes = workflow.nodes
        
        # Display nodes section
        st.markdown("### 📦 Workflow Nodes")
        st.markdown(f"*Displaying {len(sorted_nodes)} nodes*")
        
        # Render each node as a card
        total_nodes = len(sorted_nodes)
        for idx, node in enumerate(sorted_nodes, start=1):
            render_node_card(
                node=node,
                index=idx if show_node_index else 0,
                total=total_nodes if show_node_index else 0,
                mode="view"
            )
        
        # Footer
        st.divider()
        st.markdown("---")
        st.markdown(
            """
            <div style='text-align: center; color: gray;'>
            🤖 Smart Workflow Visualizer v0.1.0 | Stage 1: View Mode
            </div>
            """,
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()

