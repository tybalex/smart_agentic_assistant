"""
Node card component for displaying workflow nodes
"""

import streamlit as st
import json
from typing import Optional, List, Callable
from src.schema import WorkflowNode, NodeResult


def render_node_card(
    node: WorkflowNode,
    index: int,
    total: int,
    mode: str = "view",
    execution_result: Optional[NodeResult] = None,
    all_node_ids: Optional[List[str]] = None,
    on_save: Optional[Callable] = None,
    on_delete: Optional[Callable] = None,
    on_run: Optional[Callable] = None,
    enable_run: bool = False
):
    """
    Render a single workflow node as a card.
    
    Args:
        node: WorkflowNode to display
        index: Index of this node in the workflow (for numbering)
        total: Total number of nodes
        mode: Display mode - "view" or "edit"
        execution_result: Optional execution result to display
        all_node_ids: List of all node IDs in workflow (for dependency selection)
        on_save: Callback function when save is clicked (receives updated node)
        on_delete: Callback function when delete is clicked (receives node_id)
        on_run: Callback function when run is clicked (receives node_id)
        enable_run: Whether to show run button
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
    
    # Available node types
    node_types = ["function_call", "api_call", "transform", "condition", "log", "delay"]
    
    # Create a container with custom styling
    with st.container():
        # Choose rendering based on mode
        if mode == "edit":
            _render_node_edit_mode(
                node, index, total, icon, node_types, all_node_ids, on_save, on_delete
            )
        else:  # view mode
            _render_node_view_mode(
                node, index, total, icon, execution_result, on_run, enable_run
            )


def _render_node_view_mode(
    node: WorkflowNode,
    index: int,
    total: int,
    icon: str,
    execution_result: Optional[NodeResult],
    on_run: Optional[Callable] = None,
    enable_run: bool = False
):
    """Render node in view-only mode"""
    # Header with node number and title
    col1, col2 = st.columns([4, 1])
    
    with col1:
        st.markdown(f"#### {icon} Node {index}/{total}: `{node.id}`")
    
    with col2:
        # Run button if enabled
        if enable_run and on_run:
            if st.button("▶️ Run", key=f"run_{node.id}", use_container_width=True, type="secondary"):
                on_run(node.id)
    
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


def _render_node_edit_mode(
    node: WorkflowNode,
    index: int,
    total: int,
    icon: str,
    node_types: List[str],
    all_node_ids: Optional[List[str]],
    on_save: Optional[Callable],
    on_delete: Optional[Callable]
):
    """Render node in edit mode with inline editors"""
    
    st.markdown(f"### {icon} Editing Node {index}/{total}")
    
    # Use a form for batch editing
    with st.form(key=f"edit_form_{node.id}"):
        # Node ID
        new_id = st.text_input(
            "Node ID",
            value=node.id,
            help="Unique identifier for this node",
            key=f"id_{node.id}"
        )
        
        # Node Type
        type_index = node_types.index(node.type) if node.type in node_types else 0
        new_type = st.selectbox(
            "Node Type",
            options=node_types,
            index=type_index,
            help="Type of operation this node performs",
            key=f"type_{node.id}"
        )
        
        # Description
        new_description = st.text_area(
            "Description",
            value=node.description or "",
            height=60,
            help="Human-readable description of what this node does",
            key=f"desc_{node.id}"
        )
        
        # Configuration (JSON editor)
        st.markdown("**Configuration (JSON):**")
        config_str = json.dumps(node.config, indent=2) if node.config else "{}"
        new_config_str = st.text_area(
            "Config JSON",
            value=config_str,
            height=200,
            help="Node configuration in JSON format",
            key=f"config_{node.id}",
            label_visibility="collapsed"
        )
        
        # Dependencies
        if all_node_ids:
            # Filter out current node from dependencies list
            available_deps = [nid for nid in all_node_ids if nid != node.id]
            new_depends_on = st.multiselect(
                "Dependencies (Depends On)",
                options=available_deps,
                default=[dep for dep in node.depends_on if dep in available_deps],
                help="Nodes that must complete before this one",
                key=f"deps_{node.id}"
            )
        else:
            new_depends_on = node.depends_on
        
        # Advanced Settings (collapsible)
        with st.expander("🔧 Advanced Settings", expanded=False):
            # Condition
            new_condition = st.text_input(
                "Condition (optional)",
                value=node.condition or "",
                help="Expression to determine if node should execute",
                key=f"cond_{node.id}"
            )
            
            # Error handling
            error_strategies = ["fail", "continue", "retry"]
            error_index = error_strategies.index(node.on_error) if node.on_error in error_strategies else 0
            new_on_error = st.selectbox(
                "On Error",
                options=error_strategies,
                index=error_index,
                help="What to do when this node fails",
                key=f"error_{node.id}"
            )
            
            # Timeout
            new_timeout = st.number_input(
                "Timeout (seconds)",
                value=node.timeout if node.timeout else 0,
                min_value=0,
                help="Maximum execution time (0 = no timeout)",
                key=f"timeout_{node.id}"
            )
            
            # Retry config
            st.markdown("**Retry Configuration (JSON, optional):**")
            retry_str = json.dumps(node.retry, indent=2) if node.retry else ""
            new_retry_str = st.text_area(
                "Retry JSON",
                value=retry_str,
                height=80,
                help='e.g., {"max_attempts": 3, "backoff": "exponential"}',
                key=f"retry_{node.id}",
                label_visibility="collapsed"
            )
        
        # Action buttons
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            save_clicked = st.form_submit_button("💾 Save Changes", use_container_width=True, type="primary")
        
        with col2:
            cancel_clicked = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        with col3:
            delete_clicked = st.form_submit_button("🗑️ Delete", use_container_width=True)
        
        # Handle form submission
        if save_clicked and on_save:
            # Validate and parse JSON fields
            try:
                new_config = json.loads(new_config_str) if new_config_str.strip() else {}
                new_retry = json.loads(new_retry_str) if new_retry_str.strip() else None
                
                # Create updated node
                updated_node = WorkflowNode(
                    id=new_id,
                    type=new_type,
                    description=new_description if new_description else None,
                    config=new_config,
                    depends_on=new_depends_on,
                    condition=new_condition if new_condition else None,
                    on_error=new_on_error if new_on_error != "fail" else None,
                    timeout=new_timeout if new_timeout > 0 else None,
                    retry=new_retry
                )
                
                # Call the save callback
                on_save(node.id, updated_node)
                st.success(f"✅ Saved changes to node '{new_id}' (in session)")
                st.info("💡 **To save to file:** Go to sidebar → Enter filename → Click 'Export to YAML'")
                
            except json.JSONDecodeError as e:
                st.error(f"❌ Invalid JSON: {str(e)}")
            except Exception as e:
                st.error(f"❌ Error saving node: {str(e)}")
        
        elif cancel_clicked:
            st.info("Editing cancelled")
            # Will be handled by app.py to exit edit mode
            if "edit_mode_nodes" in st.session_state:
                st.session_state.edit_mode_nodes.discard(node.id)
                st.rerun()
        
        elif delete_clicked and on_delete:
            on_delete(node.id)
            st.warning(f"🗑️ Deleted node '{node.id}'")
    
    # Visual separator
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

