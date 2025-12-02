"""
Smart Workflow Visualizer - Main Streamlit Application

View, edit, and run workflows through an interactive UI.

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
from ui.components.chat_panel import render_chat_panel
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
    
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = None  # File pending deletion confirmation
    
    if "selected_file" not in st.session_state:
        st.session_state.selected_file = None  # Currently selected file
    
    if "variables_edit_mode" not in st.session_state:
        st.session_state.variables_edit_mode = False  # Whether variables are in edit mode


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


def create_new_workflow_file(filename: str, workspace_dir: str = ".") -> tuple[bool, str, WorkflowDefinition]:
    """Create a new workflow file with a basic template"""
    try:
        from src.schema import WorkflowMetadata
        
        # Create filepath
        filepath = Path(workspace_dir) / filename
        
        # Check if file already exists
        if filepath.exists():
            return False, f"File '{filename}' already exists!", None
        
        # Create a basic workflow template
        new_workflow = WorkflowDefinition(
            metadata=WorkflowMetadata(
                name=Path(filename).stem.replace('_', ' ').title(),
                description="A new workflow - edit me!",
                version="1.0.0",
                author="Smart Workflow UI"
            ),
            nodes=[
                WorkflowNode(
                    id="start_node",
                    type="log",
                    description="Starting point of the workflow",
                    config={
                        "message": "Workflow started",
                        "level": "info"
                    },
                    depends_on=[]
                )
            ],
            variables={}
        )
        
        # Save to file
        success, message = export_workflow_to_yaml(new_workflow, str(filepath))
        
        if success:
            return True, f"Created new workflow file: {filename}", new_workflow
        else:
            return False, message, None
            
    except Exception as e:
        return False, f"Error creating workflow: {str(e)}", None


def delete_workflow_file(filename: str) -> tuple[bool, str]:
    """Delete a workflow file"""
    try:
        filepath = Path(filename)
        
        if not filepath.exists():
            return False, f"File '{filename}' does not exist!"
        
        # Delete the file
        filepath.unlink()
        
        return True, f"Deleted workflow file: {filepath.name}"
        
    except Exception as e:
        return False, f"Error deleting workflow: {str(e)}"


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


def run_all_nodes(workflow: WorkflowDefinition):
    """Run the entire workflow using the proper executor (just like run_workflow.py)"""
    try:
        # Clear previous results
        st.session_state.execution_results = {}
        st.session_state.execution_context = None
        
        # Create progress placeholder
        progress_container = st.empty()
        
        with progress_container.container():
            st.info("🚀 Running workflow...")
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        # Execute the entire workflow using the proper executor
        executor = SimpleWorkflowExecutor()
        
        # Run async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # This is the proper way - uses all the built-in logic for conditions, dependencies, etc.
            result = loop.run_until_complete(
                executor.execute(workflow)
            )
            
            # Extract node results from the workflow execution result
            for node_id, node_result in result.node_results.items():
                st.session_state.execution_results[node_id] = node_result
            
            # Create an execution context for display purposes (matching what's in the result)
            st.session_state.execution_context = ExecutionContext(
                workflow_id=result.workflow_id,
                execution_id=result.execution_id,
                variables=workflow.variables.copy(),
                node_results={
                    node_id: node_result.output 
                    for node_id, node_result in result.node_results.items() 
                    if node_result.status == "success"
                }
            )
            
            progress_bar.progress(1.0)
            
            # Show summary based on actual execution
            total_nodes = len(result.node_results)
            successful = sum(1 for r in result.node_results.values() if r.status == "success")
            failed = sum(1 for r in result.node_results.values() if r.status == "failed")
            skipped = sum(1 for r in result.node_results.values() if r.status == "skipped")
            
            status_text.empty()
            
            if result.status == "success":
                st.success(f"✅ Workflow completed successfully!")
            elif result.status == "failed":
                st.error(f"❌ Workflow failed!")
            else:
                st.warning(f"⚠️ Workflow completed with issues")
            
            # Show detailed stats
            st.markdown(f"""
            **Execution Summary:**
            - ✅ Successful: {successful}
            - ❌ Failed: {failed}
            - ⏭️ Skipped: {skipped}
            - 📊 Total: {total_nodes}
            - ⏱️ Duration: {result.total_duration:.2f}s
            - 🆔 Execution ID: `{result.execution_id[:8]}...`
            """)
            
            # Show warnings if any
            if result.warnings:
                with st.expander(f"⚠️ Warnings ({len(result.warnings)})", expanded=True):
                    for warning in result.warnings:
                        st.warning(warning)
            
            # Show node execution details
            with st.expander("📝 Node Execution Details", expanded=False):
                for node_id, node_result in result.node_results.items():
                    status_icon = {"success": "✅", "failed": "❌", "skipped": "⏭️"}.get(node_result.status, "❓")
                    exec_time = f"{node_result.execution_time:.3f}s" if node_result.execution_time else "N/A"
                    
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"{status_icon} **{node_id}**")
                    with col2:
                        st.caption(node_result.status)
                    with col3:
                        st.caption(exec_time)
                    
                    # Show error details if failed
                    if node_result.status == "failed" and node_result.error:
                        st.error(f"Error: {node_result.error}")
                    
                    # Show output preview if successful
                    if node_result.status == "success" and node_result.output:
                        output_str = str(node_result.output)
                        if len(output_str) > 100:
                            output_str = output_str[:100] + "..."
                        st.caption(f"Output: {output_str}")
            
        finally:
            loop.close()
        
        # Rerun to show results in cards
        time.sleep(1)  # Brief pause to see the message
        st.rerun()
        
    except ValueError as e:
        st.error(f"❌ Cannot run workflow: {e}")
    except Exception as e:
        st.error(f"❌ Error running workflow: {str(e)}")


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
            st.info("👇 Create a new workflow file below to get started!")
        
        # File selector (only show if files exist)
        if workflow_files:
            # Determine default index
            default_index = 0
            if st.session_state.selected_file and st.session_state.selected_file in workflow_files:
                default_index = workflow_files.index(st.session_state.selected_file)
            
            selected_file = st.selectbox(
                "Select Workflow",
                options=workflow_files,
                format_func=lambda x: Path(x).name,
                index=default_index
            )
            
            # Update session state
            st.session_state.selected_file = selected_file
        else:
            selected_file = None
        
        # File management buttons (only show if a file is selected)
        if selected_file:
            col1, col2 = st.columns(2)
            
            with col1:
                # Reload button
                if st.button("↻ Reload", use_container_width=True):
                    st.session_state.modified_workflow = None
                    st.session_state.workflow_modified = False
                    st.session_state.edit_mode_nodes.clear()
                    st.session_state.variables_edit_mode = False
                    st.cache_data.clear()
                    st.rerun()
            
            with col2:
                # Delete button (with confirmation)
                if st.button("🗑️ Delete", use_container_width=True, type="secondary"):
                    st.session_state.confirm_delete = selected_file
            
            # Confirmation dialog for delete
            if st.session_state.confirm_delete == selected_file:
                st.warning(f"⚠️ Delete '{Path(selected_file).name}'?")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Yes, Delete", use_container_width=True, type="primary"):
                        success, message = delete_workflow_file(selected_file)
                        if success:
                            st.success(message)
                            # Clear session state
                            st.session_state.modified_workflow = None
                            st.session_state.workflow_modified = False
                            st.session_state.edit_mode_nodes.clear()
                            st.session_state.variables_edit_mode = False
                            st.session_state.confirm_delete = None
                            st.session_state.selected_file = None
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)
                            st.session_state.confirm_delete = None
                with col2:
                    if st.button("❌ Cancel", use_container_width=True):
                        st.session_state.confirm_delete = None
                        st.rerun()
        
        # Create new workflow
        st.markdown("**➕ New Workflow**")
        with st.expander("Create New File", expanded=False):
            new_filename = st.text_input(
                "Filename",
                value="new_workflow.yaml",
                help="Name for the new workflow file",
                key="new_workflow_filename"
            )
            
            if st.button("✨ Create File", use_container_width=True, type="primary"):
                if not new_filename.endswith(('.yaml', '.yml')):
                    st.error("Filename must end with .yaml or .yml")
                else:
                    success, message, new_workflow = create_new_workflow_file(new_filename, workspace_dir)
                    if success:
                        st.success(message)
                        # Set the new file as selected
                        new_filepath = str(Path(workspace_dir) / new_filename)
                        st.session_state.selected_file = new_filepath
                        # Load the new workflow
                        st.session_state.modified_workflow = new_workflow
                        st.session_state.workflow_modified = False
                        st.session_state.edit_mode_nodes.clear()
                        st.session_state.variables_edit_mode = False
                        st.cache_data.clear()
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(message)
        
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
                # Run all button
                if st.button("▶️ Run All", use_container_width=True,
                           help="Run all nodes in topological order"):
                    if st.session_state.modified_workflow:
                        run_all_nodes(st.session_state.modified_workflow)
            
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
        
        st.divider()
        
        # Chat panel toggle
        st.markdown("### 💬 AI Assistant")
        show_chat_panel = st.checkbox("Show Chat Panel", value=True,
                                      help="Show AI agent chat on the right side")
    
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
        
        # Split into two columns: workflow on left, chat on right
        if show_chat_panel:
            workflow_col, chat_col = st.columns([2, 1])
        else:
            workflow_col = st.container()
            chat_col = None
        
        # Workflow view
        with workflow_col:
            # Show unsaved changes banner if applicable
            if st.session_state.workflow_modified:
                st.warning("⚠️ **You have unsaved changes!** Go to sidebar → '💾 Save to File' section → Click 'Export to YAML File' to save.")
                
                # Show what changed
                with st.expander("🔍 View Changes", expanded=False):
                    # Load original workflow for comparison
                    original_workflow = load_workflow_file(selected_file)
                    modified_workflow = st.session_state.modified_workflow
                    
                    if original_workflow:
                        changes_found = False
                        
                        # Compare metadata
                        if original_workflow.metadata.name != modified_workflow.metadata.name:
                            st.markdown("**📝 Name changed:**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown(f"*Before:* `{original_workflow.metadata.name}`")
                            with col2:
                                st.markdown(f"*After:* `{modified_workflow.metadata.name}`")
                            changes_found = True
                        
                        if original_workflow.metadata.description != modified_workflow.metadata.description:
                            st.markdown("**📝 Description changed:**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.caption(f"*Before:* {original_workflow.metadata.description[:100]}...")
                            with col2:
                                st.caption(f"*After:* {modified_workflow.metadata.description[:100]}...")
                            changes_found = True
                        
                        # Compare variables
                        if original_workflow.variables != modified_workflow.variables:
                            st.markdown("**🔤 Variables changed:**")
                            orig_vars = set(original_workflow.variables.keys())
                            mod_vars = set(modified_workflow.variables.keys())
                            
                            added_vars = mod_vars - orig_vars
                            removed_vars = orig_vars - mod_vars
                            changed_vars = {k for k in orig_vars & mod_vars 
                                          if original_workflow.variables[k] != modified_workflow.variables[k]}
                            
                            if added_vars:
                                st.success(f"➕ Added: {', '.join(added_vars)}")
                            if removed_vars:
                                st.error(f"➖ Removed: {', '.join(removed_vars)}")
                            if changed_vars:
                                st.info(f"✏️ Modified: {', '.join(changed_vars)}")
                            changes_found = True
                        
                        # Compare nodes
                        orig_node_ids = {node.id for node in original_workflow.nodes}
                        mod_node_ids = {node.id for node in modified_workflow.nodes}
                        
                        added_nodes = mod_node_ids - orig_node_ids
                        removed_nodes = orig_node_ids - mod_node_ids
                        common_nodes = orig_node_ids & mod_node_ids
                        
                        if added_nodes:
                            st.markdown("**➕ Added Nodes:**")
                            for node_id in added_nodes:
                                node = next(n for n in modified_workflow.nodes if n.id == node_id)
                                st.success(f"• `{node_id}` ({node.type}): {node.description or 'No description'}")
                            changes_found = True
                        
                        if removed_nodes:
                            st.markdown("**➖ Removed Nodes:**")
                            for node_id in removed_nodes:
                                node = next(n for n in original_workflow.nodes if n.id == node_id)
                                st.error(f"• `{node_id}` ({node.type}): {node.description or 'No description'}")
                            changes_found = True
                        
                        # Check modified nodes
                        modified_nodes = []
                        for node_id in common_nodes:
                            orig_node = next(n for n in original_workflow.nodes if n.id == node_id)
                            mod_node = next(n for n in modified_workflow.nodes if n.id == node_id)
                            
                            # Simple comparison (could be more detailed)
                            if (orig_node.type != mod_node.type or
                                orig_node.description != mod_node.description or
                                orig_node.config != mod_node.config or
                                orig_node.depends_on != mod_node.depends_on or
                                orig_node.condition != mod_node.condition):
                                modified_nodes.append(node_id)
                        
                        if modified_nodes:
                            st.markdown("**✏️ Modified Nodes:**")
                            for node_id in modified_nodes:
                                orig_node = next(n for n in original_workflow.nodes if n.id == node_id)
                                mod_node = next(n for n in modified_workflow.nodes if n.id == node_id)
                                
                                with st.container():
                                    st.info(f"• `{node_id}` ({mod_node.type})")
                                    
                                    # Show specific changes
                                    if orig_node.description != mod_node.description:
                                        st.caption(f"  - Description: '{orig_node.description}' → '{mod_node.description}'")
                                    if orig_node.type != mod_node.type:
                                        st.caption(f"  - Type: {orig_node.type} → {mod_node.type}")
                                    if orig_node.config != mod_node.config:
                                        st.caption(f"  - Config modified")
                                    if orig_node.depends_on != mod_node.depends_on:
                                        st.caption(f"  - Dependencies: {orig_node.depends_on} → {mod_node.depends_on}")
                                    if orig_node.condition != mod_node.condition:
                                        st.caption(f"  - Condition: '{orig_node.condition}' → '{mod_node.condition}'")
                            changes_found = True
                        
                        if not changes_found:
                            st.info("No changes detected (this shouldn't happen!)")
                    else:
                        st.error("Could not load original workflow for comparison")
            
            # Display workflow information
            render_workflow_info(workflow)
            
            # Workflow Variables Editor (inline in main page)
            st.markdown("### 🔤 Workflow Variables")
            
            if workflow.variables:
                # Track if we're in edit mode
                if "variables_edit_mode" not in st.session_state:
                    st.session_state.variables_edit_mode = False
                
                # Edit toggle button
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.caption("Global variables accessible throughout the workflow")
                with col2:
                    if not st.session_state.variables_edit_mode:
                        if st.button("✏️ Edit", key="edit_vars_btn", use_container_width=True):
                            st.session_state.variables_edit_mode = True
                            st.rerun()
                    else:
                        if st.button("❌ Cancel", key="cancel_vars_btn", use_container_width=True):
                            st.session_state.variables_edit_mode = False
                            st.rerun()
                
                # Display/Edit variables
                if st.session_state.variables_edit_mode:
                    # Edit mode
                    st.info("💡 Edit the values below and click **Save Changes** to apply")
                    
                    new_variables = {}
                    variables_changed = False
                    parse_errors = []
                    
                    # Create a form-like layout
                    for var_name, var_value in workflow.variables.items():
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.markdown(f"**`{var_name}`**")
                        with col2:
                            # Determine input type based on current value
                            if isinstance(var_value, bool):
                                new_value = st.checkbox(
                                    f"Value for {var_name}",
                                    value=var_value,
                                    key=f"edit_var_{var_name}",
                                    label_visibility="collapsed"
                                )
                            elif isinstance(var_value, (int, float)):
                                new_value = st.number_input(
                                    f"Value for {var_name}",
                                    value=var_value,
                                    key=f"edit_var_{var_name}",
                                    label_visibility="collapsed"
                                )
                            elif isinstance(var_value, (dict, list)):
                                # For complex types (dict/list), use text area with YAML
                                st.caption("📝 Edit as YAML:")
                                yaml_str = yaml.dump(var_value, default_flow_style=False, sort_keys=False)
                                new_yaml_str = st.text_area(
                                    f"Value for {var_name}",
                                    value=yaml_str,
                                    key=f"edit_var_{var_name}",
                                    label_visibility="collapsed",
                                    height=100
                                )
                                # Parse the YAML back to dict/list
                                try:
                                    new_value = yaml.safe_load(new_yaml_str)
                                    if new_value is None:
                                        new_value = var_value  # Keep original if empty
                                except yaml.YAMLError as e:
                                    st.error(f"Invalid YAML: {e}")
                                    parse_errors.append(var_name)
                                    new_value = var_value  # Keep original on error
                            else:
                                # String types
                                new_value = st.text_input(
                                    f"Value for {var_name}",
                                    value=str(var_value),
                                    key=f"edit_var_{var_name}",
                                    label_visibility="collapsed"
                                )
                            
                            new_variables[var_name] = new_value
                            
                            if new_value != var_value:
                                variables_changed = True
                    
                    # Save/Reset buttons
                    col1, col2, col3 = st.columns([1, 1, 2])
                    with col1:
                        # Disable save if there are parse errors or no changes
                        save_disabled = not variables_changed or len(parse_errors) > 0
                        if st.button("✅ Save Changes", use_container_width=True, type="primary", disabled=save_disabled):
                            st.session_state.modified_workflow.variables = new_variables
                            st.session_state.workflow_modified = True
                            st.session_state.variables_edit_mode = False
                            # Clear execution results since variables changed
                            st.session_state.execution_results = {}
                            st.session_state.execution_context = None
                            st.success("✅ Variables updated!")
                            time.sleep(0.5)
                            st.rerun()
                    
                    # Show parse error warning
                    if parse_errors:
                        st.error(f"⚠️ Fix YAML errors in: {', '.join(parse_errors)} before saving")
                    
                    with col2:
                        if st.button("🔄 Reset to Original", use_container_width=True):
                            # Reload from original file
                            original = load_workflow_file(selected_file)
                            if original:
                                st.session_state.modified_workflow.variables = copy.deepcopy(original.variables)
                                st.session_state.variables_edit_mode = False
                                st.success("🔄 Variables reset!")
                                st.rerun()
                
                else:
                    # View mode - show as a clean table
                    vars_data = []
                    for var_name, var_value in workflow.variables.items():
                        # Format the value nicely based on type
                        if isinstance(var_value, dict):
                            # For dicts, show as compact YAML or summary
                            if len(var_value) <= 3:
                                display_value = ", ".join(f"{k}: {v}" for k, v in var_value.items())
                            else:
                                display_value = f"{{...}} ({len(var_value)} keys)"
                            var_type = "dict"
                        elif isinstance(var_value, list):
                            display_value = f"[...] ({len(var_value)} items)"
                            var_type = "list"
                        elif isinstance(var_value, str) and len(var_value) > 50:
                            display_value = var_value[:50] + "..."
                            var_type = "str"
                        else:
                            display_value = str(var_value)
                            var_type = type(var_value).__name__
                        
                        vars_data.append({
                            "Variable": f"`{var_name}`",
                            "Value": display_value,
                            "Type": var_type
                        })
                    
                    # Display as columns for better layout
                    for var_info in vars_data:
                        col1, col2, col3 = st.columns([2, 4, 1])
                        with col1:
                            st.markdown(var_info["Variable"])
                        with col2:
                            st.text(var_info["Value"])
                        with col3:
                            st.caption(var_info["Type"])
            else:
                st.info("No variables defined in this workflow")
            
            st.divider()
            
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
                🤖 Smart Workflow Visualizer v0.4.0 | With AI Chat
                </div>
                """,
                unsafe_allow_html=True
            )
        
        # Render chat panel in the right column
        if show_chat_panel and chat_col:
            with chat_col:
                render_chat_panel(workspace_dir)
    
    else:
        # No file selected
        st.info("👈 Select a workflow file from the sidebar, or create a new one!")
        
        st.markdown("### 🚀 Getting Started")
        st.markdown("""
        **Create your first workflow:**
        1. Click "**➕ New Workflow**" in the sidebar
        2. Enter a filename (e.g., `my_workflow.yaml`)
        3. Click "**✨ Create File**"
        
        The new workflow will be created with a basic template that you can edit!
        """)


if __name__ == "__main__":
    main()
