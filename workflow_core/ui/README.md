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

### Stage 1: View Mode ✅ (Current)

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

### Stage 2: Edit Mode 🚧 (Coming Soon)

- Edit node properties inline
- Add/remove nodes
- Modify dependencies
- Save changes back to YAML

### Stage 3: Run Nodes 🚧 (Coming Soon)

- Execute individual nodes
- See real-time results
- Debug with mock data
- Chain node executions

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

### Display Options

- **Show Execution Order**: Displays nodes in execution order (topological sort)
- **Show Node Numbers**: Numbers each node (1/10, 2/10, etc.)

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

