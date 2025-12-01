#!/bin/bash
#
# Launch the Smart Workflow Visualizer UI
#
# Usage:
#   ./run_ui.sh
#

echo "🔧 Starting Smart Workflow Visualizer..."
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "⚠️  Streamlit is not installed."
    echo "📦 Installing streamlit..."
    pip install streamlit
    echo ""
fi

# Run the UI
echo "🚀 Launching UI at http://localhost:8501"
echo "📂 Working directory: $(pwd)"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

streamlit run ui/app.py

