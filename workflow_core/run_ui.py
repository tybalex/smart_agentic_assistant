#!/usr/bin/env python3
"""
Launch the Smart Workflow Visualizer UI

Usage:
    python run_ui.py
"""

import subprocess
import sys
import os

def check_streamlit():
    """Check if streamlit is installed"""
    try:
        import streamlit
        return True
    except ImportError:
        return False

def install_streamlit():
    """Install streamlit using pip"""
    print("⚠️  Streamlit is not installed.")
    print("📦 Installing streamlit...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "streamlit"])
    print("✅ Streamlit installed successfully!")
    print()

def main():
    print("🔧 Starting Smart Workflow Visualizer...")
    print()
    
    # Check and install streamlit if needed
    if not check_streamlit():
        install_streamlit()
    
    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ui_app_path = os.path.join(script_dir, "ui", "app.py")
    
    print("🚀 Launching UI at http://localhost:8501")
    print(f"📂 Working directory: {script_dir}")
    print()
    print("Press Ctrl+C to stop the server")
    print()
    
    # Run streamlit
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", ui_app_path])
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        sys.exit(0)

if __name__ == "__main__":
    main()

