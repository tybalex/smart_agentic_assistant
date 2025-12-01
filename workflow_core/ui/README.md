# 🔧 Smart Workflow Visualizer UI

A clean, interactive web interface for visualizing and working with workflow YAML files.

## 🚀 Quick Start

### Installation

Make sure Streamlit is installed:

```bash
pip install streamlit
# or
uv pip install streamlit
```

### Running the UI

From the `workflow_core` directory:

```bash
streamlit run ui/app.py
```

The UI will open in your browser at `http://localhost:8501`

## 📋 Features

### Stage 1: View Mode ✅

- **Load Workflows**: Select from any `.yaml` or `.yml` file in your workspace
- **View Metadata**: See workflow name, description, version, and variables
- **Node Cards**: Each node displayed as a card showing:
  - Node ID and type (with emoji icons)
  - Description
  - Dependencies
  - Configuration (formatted JSON)
  - Advanced settings (conditions, retries, timeouts)
- **Execution Order**: Visual display of topological execution order
- **Clean Layout**: Simple, readable interface with no clutter

### Stage 2: Edit Mode ✅ (Current)

- **Edit Node Properties**: Click "Edit" to modify any node inline
  - Change node ID, type, description
  - Edit configuration (JSON editor with syntax validation)
  - Modify dependencies with multiselect
  - Set advanced options (conditions, error handling, retries, timeouts)
- **Add New Nodes**: Create new nodes with one click
- **Delete Nodes**: Remove nodes (automatically updates dependencies)
- **Export to YAML**: Save your modified workflow to a file
- **Session Management**: Changes tracked in session, can be discarded
- **Validation**: JSON syntax validation before saving

### Stage 3: Run Nodes ✅

- **Execute Individual Nodes**: Click "▶️ Run" on any node (Jupyter-style!)
- **Real-time Results**: See execution output, errors, and timing
- **Dependency Handling**: Warns about missing dependencies
- **Execution Context**: Uses results from previously run nodes
- **Clear Results**: Reset all execution state with one click
- **Execution Stats**: Track success/failure counts in sidebar
- **Visual Feedback**: 
  - ✅ Success: Green indicator with output
  - ❌ Failed: Red indicator with error message
  - ⏱️ Timing: Execution time for each node

## 📁 File Structure

```
ui/
├── app.py                      # Main Streamlit application
├── components/
│   ├── workflow_info.py        # Workflow metadata display
│   └── node_card.py           # Individual node display
└── utils/
    └── loader.py              # YAML file loading utilities
```

## 🎨 Usage Tips

### Viewing Workflows

1. Place your workflow YAML files in the workspace directory
2. Select a workflow from the sidebar dropdown
3. Scroll through the node cards to understand the flow
4. Use "Show Execution Order" to see the topological sort

### Editing Workflows (Stage 2)

1. **Enable Edit Mode**: Check "Enable Edit Mode" in the sidebar
2. **Edit a Node**: Click the "✏️ Edit" button next to any node
3. **Make Changes**: 
   - Modify text fields (ID, type, description)
   - Edit JSON configuration (with syntax highlighting)
   - Select dependencies from dropdown
   - Set advanced options
4. **Save**: Click "💾 Save Changes" to apply
5. **Cancel**: Click "❌ Cancel" to discard changes
6. **Delete**: Click "🗑️ Delete" to remove the node

### Adding Nodes

1. Click "➕ Add New Node" in the sidebar
2. A new node is created and automatically opened in edit mode
3. Configure the node as needed
4. Save your changes

### Exporting Changes

1. After editing, you'll see "⚠️ You have unsaved changes" in the sidebar
2. Enter an export filename (defaults to current file name)
3. Click "💾 Export to YAML" to save
4. The modified workflow is written to the file

### Running Nodes (Stage 3)

1. **Enable Run Mode**: Check "Enable Run Mode" in sidebar
2. **Run a Node**: Click "▶️ Run" button on any node
3. **View Results**: 
   - Success: See output data below the node
   - Failure: See error message
   - Timing: Execution time displayed
4. **Dependencies**: 
   - If dependencies are missing, you'll see a warning
   - Run dependent nodes first for accurate results
5. **Clear Results**: Click "🗑️ Clear Results" to reset execution state

**Tips for Running Nodes:**
- Start from the top: Run nodes in execution order for best results
- Check dependencies: Nodes that depend on others will use their outputs
- Mock data: If dependencies aren't run, nodes may use default/mock values
- Iterate: Run, check output, edit config, run again!

### Display Options

- **Show Execution Order**: Displays nodes in execution order (topological sort)
- **Show Node Numbers**: Numbers each node (1/10, 2/10, etc.)
- **Enable Edit Mode**: Shows Edit buttons on all node cards
- **Enable Run Mode**: Shows Run buttons on all node cards (Stage 3)

### Keyboard Shortcuts

Streamlit provides several shortcuts:
- `R` - Rerun the app
- `C` - Clear cache
- `Ctrl/Cmd + K` - Open command palette

## 🔧 Customization

### Adding Custom Node Type Icons

Edit `node_card.py`:

```python
type_icons = {
    "function_call": "🔧",
    "api_call": "🌐",
    "your_custom_type": "🎯",  # Add here
}
```

### Changing Layout

The app uses Streamlit's layout system:
- Main content area: Wide layout
- Sidebar: File selection and options
- Columns: Used for metrics and compact displays

## 🐛 Troubleshooting

### No workflows found

- Ensure you have `.yaml` or `.yml` files in the workspace directory
- Check the workspace directory path in the sidebar

### Workflow loading fails

- Verify the YAML syntax is valid
- Ensure it matches the WorkflowDefinition schema
- Check for missing required fields (metadata.name, nodes)

### Import errors

- Make sure you're running from the `workflow_core` directory
- Verify the src modules are accessible

## 📚 Example Workflow

A sample workflow is provided: `sample_workflow.yaml`

This demonstrates:
- Multiple node types
- Dependencies
- Conditional execution
- Error handling
- Global variables

## 🛠️ Development

### Running in Development Mode

```bash
streamlit run ui/app.py --server.runOnSave true
```

This auto-reloads when you save changes to Python files.

### Adding New Components

1. Create a new file in `ui/components/`
2. Define a render function
3. Import and use in `app.py`

Example:

```python
# ui/components/my_component.py
def render_my_component(data):
    st.markdown("## My Component")
    st.write(data)

# ui/app.py
from ui.components.my_component import render_my_component
render_my_component(my_data)
```

## 📝 Notes

- **Stage 1** focuses on viewing only - no editing or execution
- Node cards are designed to be extended for Stages 2 & 3
- The codebase is intentionally simple and readable
- Future stages will add interactivity without major refactoring

## 🙏 Acknowledgments

Built with:
- [Streamlit](https://streamlit.io/) - The fastest way to build data apps
- [Pydantic](https://pydantic.dev/) - Data validation using Python type annotations
- [PyYAML](https://pyyaml.org/) - YAML parser for Python

---

**Stage 1: View Mode** | Built with ❤️ for the Smart Workflow project

