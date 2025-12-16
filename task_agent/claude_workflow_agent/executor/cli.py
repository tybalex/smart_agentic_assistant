#!/usr/bin/env python3
"""
Executor Agent CLI
Usage: python -m executor.cli <workflow_path> [tools_path]
"""

import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path to import from task_agent
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tool_client import ToolRegistryClient
from constant import DEFAULT_TOOL_REGISTRY_URL
from executor import execute_workflow_from_files


def main():
    parser = argparse.ArgumentParser(
        description="Execute a workflow.md file with scoped tools"
    )
    parser.add_argument(
        "workflow",
        help="Path to workflow.md file"
    )
    parser.add_argument(
        "tools",
        nargs="?",
        help="Path to tools.json file (default: same directory as workflow)"
    )
    parser.add_argument(
        "--registry-url",
        default=DEFAULT_TOOL_REGISTRY_URL,
        help="Tool registry URL"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Save trace to JSON file"
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    workflow_path = Path(args.workflow).resolve()
    if not workflow_path.exists():
        print(f"Error: Workflow file not found: {workflow_path}")
        sys.exit(1)
    
    # Auto-detect tools.json in same directory if not specified
    if args.tools:
        tools_path = Path(args.tools).resolve()
    else:
        tools_path = workflow_path.parent / "tools.json"
    
    if not tools_path.exists():
        print(f"Error: Tools config not found: {tools_path}")
        print("Provide tools.json path or place it next to workflow.md")
        sys.exit(1)
    
    print(f"📋 Workflow: {workflow_path}")
    print(f"🔧 Tools: {tools_path}")
    print(f"🌐 Registry: {args.registry_url}")
    print()
    
    # Create tool client
    tool_client = ToolRegistryClient(args.registry_url)
    
    # Execute workflow
    print("🚀 Starting execution...")
    print()
    
    try:
        trace = execute_workflow_from_files(
            workflow_path=str(workflow_path),
            tools_path=str(tools_path),
            tool_executor=tool_client
        )
        
        # Print results
        print("=" * 80)
        print("EXECUTION TRACE")
        print("=" * 80)
        print(json.dumps(trace, indent=2))
        print()
        
        # Save if requested
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w') as f:
                json.dump(trace, f, indent=2)
            print(f"✅ Trace saved to: {output_path}")
        
        # Exit with appropriate code
        status = trace.get("status", "failed")
        if status == "completed":
            print("✅ Workflow completed successfully!")
            sys.exit(0)
        elif status == "needs_clarification":
            print("❓ Workflow needs clarification from user")
            sys.exit(2)
        else:
            print(f"❌ Workflow failed: {trace.get('final_summary', 'Unknown error')}")
            sys.exit(1)
    
    except Exception as e:
        print(f"❌ Execution error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
