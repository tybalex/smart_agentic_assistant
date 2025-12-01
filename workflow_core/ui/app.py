"""
Smart Workflow Visualizer - Main Streamlit Application

Stage 1: View workflow structure and node details ✅
Stage 2: Edit nodes through UI ✅
Stage 3: Run individual nodes (coming soon)

Usage:
    streamlit run ui/app.py
"""

import streamlit as st
from pathlib import Path
import sys
import yaml
import copy

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from ui.utils.loader import find_workflow_files, load_workflow_file, get_workflow_summary
from ui.components.workflow_info import render_workflow_info
from ui.components.node_card import render_node_card
from src.schema import WorkflowNode, WorkflowDefinition, ExecutionContext, NodeResult
from src.runtime import SimpleWorkflowExecutor
import asyncio
import time
import uuid


# Page configuration
st.set_page_config(
    page_title="Smart Workflow Visualizer",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="expanded"
)


def initialize_session_state():
    """Initialize session state variables"""
    if "edit_mode_nodes" not in st.session_state:
        st.session_state.edit_mode_nodes = set()  # Set of node IDs currently in edit mode
    
    if "modified_workflow" not in st.session_state:
        st.session_state.modified_workflow = None
    
    if "workflow_modified" not in st.session_state:
        st.session_state.workflow_modified = False
    
    if "execution_results" not in st.session_state:
        st.session_state.execution_results = {}  # Dict of node_id -> NodeResult
    
    if "execution_context" not in st.session_state:
        st.session_state.execution_context = None  # Current execution context


def save_node_changes(old_node_id: str, updated_node: WorkflowNode):
    """Save changes to a node"""
    if st.session_state.modified_workflow is None:
        return
    
    # Find and update the node
    for i, node in enumerate(st.session_state.modified_workflow.nodes):
        if node.id == old_node_id:
            st.session_state.modified_workflow.nodes[i] = updated_node
            break
    
    # Mark as modified
    st.session_state.workflow_modified = True
    
    # Exit edit mode for this node
    if old_node_id in st.session_state.edit_mode_nodes:
        st.session_state.edit_mode_nodes.discard(old_node_id)
    
    # If node ID changed, update any dependencies that reference it
    if old_node_id != updated_node.id:
        for node in st.session_state.modified_workflow.nodes:
            if old_node_id in node.depends_on:
                node.depends_on = [
                    updated_node.id if dep == old_node_id else dep 
                    for dep in node.depends_on
                ]


def delete_node(node_id: str):
    """Delete a node from the workflow"""
    if st.session_state.modified_workflow is None:
        return
    
    # Remove the node
    st.session_state.modified_workflow.nodes = [
        node for node in st.session_state.modified_workflow.nodes 
        if node.id != node_id
    ]
    
    # Remove from dependencies of other nodes
    for node in st.session_state.modified_workflow.nodes:
        if node_id in node.depends_on:
            node.depends_on = [dep for dep in node.depends_on if dep != node_id]
    
    # Mark as modified
    st.session_state.workflow_modified = True
    
    # Exit edit mode
    if node_id in st.session_state.edit_mode_nodes:
        st.session_state.edit_mode_nodes.discard(node_id)


def add_new_node():
    """Add a new node to the workflow"""
    if st.session_state.modified_workflow is None:
        return
    
    # Generate a unique node ID
    base_id = "new_node"
    node_id = base_id
    counter = 1
    existing_ids = {node.id for node in st.session_state.modified_workflow.nodes}
    
    while node_id in existing_ids:
        node_id = f"{base_id}_{counter}"
        counter += 1
    
    # Create a new node
    new_node = WorkflowNode(
        id=node_id,
        type="function_call",
        description="New node - configure me!",
        config={},
        depends_on=[]
    )
    
    st.session_state.modified_workflow.nodes.append(new_node)
    st.session_state.workflow_modified = True
    
    # Enter edit mode for the new node
    st.session_state.edit_mode_nodes.add(node_id)


def export_workflow_to_yaml(workflow: WorkflowDefinition, filename: str):
    """Export workflow to YAML file"""
    try:
        # Convert to dict
        workflow_dict = workflow.model_dump()
        
        # Write to file
        with open(filename, 'w') as f:
            yaml.dump(workflow_dict, f, default_flow_style=False, sort_keys=False)
        
        return True, f"Successfully exported to {filename}"
    except Exception as e:
        return False, f"Error exporting workflow: {str(e)}"


def run_single_node(node_id: str):
    """Execute a single node and store the result"""
    if st.session_state.modified_workflow is None:
        st.error("No workflow loaded")
        return
    
    workflow = st.session_state.modified_workflow
    
    # Initialize execution context if needed
    if st.session_state.execution_context is None:
        st.session_state.execution_context = ExecutionContext(
            workflow_id=workflow.metadata.name,
            execution_id=str(uuid.uuid4()),
            variables={**workflow.variables},
            node_results={}
        )
    
    # Get the node
    node = workflow.get_node(node_id)
    if not node:
        st.error(f"Node '{node_id}' not found")
        return
    
    # Check dependencies
    missing_deps = []
    for dep in node.depends_on:
        if dep not in st.session_state.execution_results:
            missing_deps.append(dep)
    
    if missing_deps:
        st.warning(f"⚠️ Missing dependency results: {', '.join(missing_deps)}")
        st.info("💡 Run dependent nodes first, or results will use default values")
    
    # Update context with previous results
    for dep_id, result in st.session_state.execution_results.items():
        if result.status == "success":
            st.session_state.execution_context.node_results[dep_id] = result.output
    
    # Execute the node
    try:
        with st.spinner(f"Running node '{node_id}'..."):
            executor = SimpleWorkflowExecutor()
            
            start_time = time.time()
            
            # Run async execution
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                output = loop.run_until_complete(
                    executor.execute_node(workflow, node_id, st.session_state.execution_context)
                )
                
                execution_time = time.time() - start_time
                
                # Create result
                result = NodeResult(
                    node_id=node_id,
                    status="success",
                    output=output,
                    execution_time=execution_time
                )
                
                st.success(f"✅ Node '{node_id}' executed successfully in {execution_time:.3f}s")
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                result = NodeResult(
                    node_id=node_id,
                    status="failed",
                    error=str(e),
                    execution_time=execution_time
                )
                
                st.error(f"❌ Node '{node_id}' failed: {str(e)}")
            
            finally:
                loop.close()
            
            # Store result
            st.session_state.execution_results[node_id] = result
            
            # Rerun to show results
            st.rerun()
            
    except Exception as e:
        st.error(f"❌ Error executing node: {str(e)}")


def clear_execution_results():
    """Clear all execution results"""
    st.session_state.execution_results = {}
    st.session_state.execution_context = None
    st.success("🗑️ Cleared all execution results")


def main():
    """Main application entry point"""
    
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.title("🔧 Smart Workflow Visualizer")
    st.markdown("*View, edit, and interact with your AI-powered workflows*")
    
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
            st.session_state.modified_workflow = None
            st.session_state.workflow_modified = False
            st.session_state.edit_mode_nodes.clear()
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        
        # Stage indicator
        st.markdown("### 🎯 Current Stage")
        st.success("**Stage 1:** View Mode ✅")
        st.success("**Stage 2:** Edit Mode ✅")
        st.success("**Stage 3:** Run Nodes ✅")
        
        st.divider()
        
        # Edit Mode Actions
        st.markdown("### ✏️ Edit Actions")
        
        if st.button("➕ Add New Node", use_container_width=True):
            add_new_node()
            st.rerun()
        
        # Export section
        st.markdown("### 💾 Save to File")
        
        if st.session_state.modified_workflow and st.session_state.workflow_modified:
            st.error("⚠️ **You have unsaved changes!**")
            st.markdown("*Changes are only in session. Export to save to disk.*")
            
            export_filename = st.text_input(
                "📝 Export Filename",
                value=Path(selected_file).name,
                help="Filename to export modified workflow",
                placeholder="my_workflow.yaml"
            )
            
            if st.button("💾 Export to YAML File", use_container_width=True, type="primary"):
                success, message = export_workflow_to_yaml(
                    st.session_state.modified_workflow, 
                    export_filename
                )
                if success:
                    st.success(message)
                    st.balloons()  # Celebrate!
                    st.session_state.workflow_modified = False
                else:
                    st.error(message)
        else:
            st.success("✅ No pending changes")
            st.markdown("*Edit nodes to see changes tracked here.*")
        
        st.divider()
        
        # Run Controls
        st.markdown("### ▶️ Run Nodes")
        
        enable_run_mode = st.checkbox("Enable Run Mode", value=False,
                                      help="Show Run buttons on node cards")
        
        if enable_run_mode:
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🗑️ Clear Results", use_container_width=True):
                    clear_execution_results()
                    st.rerun()
            
            with col2:
                # Run all button (coming soon)
                st.button("▶️ Run All", use_container_width=True, disabled=True,
                         help="Coming soon: Run all nodes in order")
            
            # Show execution stats
            if st.session_state.execution_results:
                total_executed = len(st.session_state.execution_results)
                successful = sum(1 for r in st.session_state.execution_results.values() 
                               if r.status == "success")
                failed = sum(1 for r in st.session_state.execution_results.values() 
                           if r.status == "failed")
                
                st.markdown("**Execution Stats:**")
                st.markdown(f"- ✅ Success: {successful}")
                st.markdown(f"- ❌ Failed: {failed}")
                st.markdown(f"- 📊 Total: {total_executed}")
        
        st.divider()
        
        # Options
        st.markdown("### ⚙️ Display Options")
        show_execution_order = st.checkbox("Show Execution Order", value=True)
        show_node_index = st.checkbox("Show Node Numbers", value=True)
        enable_edit_mode = st.checkbox("Enable Edit Mode", value=False, 
                                       help="Show Edit buttons on node cards")
    
    # Main content area
    if selected_file:
        # Load workflow from file or use modified version
        if st.session_state.modified_workflow is None:
            workflow = load_workflow_file(selected_file)
            if workflow is None:
                st.error(f"Failed to load workflow from {selected_file}")
                st.stop()
            # Make a copy for editing
            st.session_state.modified_workflow = copy.deepcopy(workflow)
        else:
            workflow = st.session_state.modified_workflow
        
        # Show unsaved changes banner if applicable
        if st.session_state.workflow_modified:
            st.warning("⚠️ **You have unsaved changes!** Go to sidebar → '💾 Save to File' section → Click 'Export to YAML File' to save.")
        
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
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"*Displaying {len(sorted_nodes)} nodes*")
        with col2:
            if enable_edit_mode and st.button("📝 Edit All", use_container_width=True):
                # Toggle edit mode for all nodes
                if len(st.session_state.edit_mode_nodes) == len(sorted_nodes):
                    st.session_state.edit_mode_nodes.clear()
                else:
                    st.session_state.edit_mode_nodes = {node.id for node in sorted_nodes}
                st.rerun()
        
        # Get all node IDs for dependency selection
        all_node_ids = [node.id for node in workflow.nodes]
        
        # Render each node as a card
        total_nodes = len(sorted_nodes)
        for idx, node in enumerate(sorted_nodes, start=1):
            # Create a container for each node with edit button
            if enable_edit_mode:
                # Show edit button in header
                col1, col2 = st.columns([4, 1])
                with col1:
                    pass  # Node card will render here
                with col2:
                    # Check if this node is in edit mode
                    is_editing = node.id in st.session_state.edit_mode_nodes
                    
                    if not is_editing:
                        if st.button(f"✏️ Edit", key=f"edit_btn_{node.id}", use_container_width=True):
                            st.session_state.edit_mode_nodes.add(node.id)
                            st.rerun()
            
            # Determine mode
            mode = "edit" if node.id in st.session_state.edit_mode_nodes else "view"
            
            # Get execution result if available
            execution_result = st.session_state.execution_results.get(node.id)
            
            # Render the node card
            render_node_card(
                node=node,
                index=idx if show_node_index else 0,
                total=total_nodes if show_node_index else 0,
                mode=mode,
                execution_result=execution_result,
                all_node_ids=all_node_ids,
                on_save=save_node_changes,
                on_delete=delete_node,
                on_run=run_single_node,
                enable_run=enable_run_mode
            )
        
        # Footer
        st.divider()
        st.markdown("---")
        st.markdown(
            """
            <div style='text-align: center; color: gray;'>
            🤖 Smart Workflow Visualizer v0.3.0 | Stage 3: Run Nodes
            </div>
            """,
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()
