#!/usr/bin/env python3
"""
Test the actual ExecutorAgent with mock tools
"""

import os
import sys
import json
from pathlib import Path

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from executor.executor_agent import ExecutorAgent
from executor.models import ToolConfig


# ==================== MOCK TOOL EXECUTOR ====================

class MockToolExecutor:
    """Mock tool executor that returns fake data"""
    
    def __init__(self):
        self.call_count = 0
    
    def execute_tool(self, server: str, tool: str, parameters: dict):
        """
        Mock tool execution - matches ScopedToolExecutor interface.
        Returns fake success data.
        """
        self.call_count += 1
        print(f"\n   🔧 Mock Call #{self.call_count}: {server}/{tool}")
        print(f"      Parameters: {json.dumps(parameters, indent=6)}")
        
        # Return mock success based on tool type
        if "create" in tool.lower():
            result = {
                "success": True,
                "id": f"mock_{tool}_{self.call_count}",
                "created": True
            }
        elif "get" in tool.lower():
            result = {
                "success": True,
                "data": {
                    "id": "mock_123",
                    "email": parameters.get("email", "test@company.com"),
                    "status": "active"
                }
            }
        elif "add" in tool.lower() or "invite" in tool.lower():
            result = {
                "success": True,
                "added": True,
                "user_id": "mock_user_123"
            }
        elif "send" in tool.lower():
            result = {
                "success": True,
                "sent": True,
                "message_id": f"msg_{self.call_count}"
            }
        else:
            result = {
                "success": True,
                "message": f"Mock {tool} completed"
            }
        
        print(f"      ✅ {result}")
        return result


# ==================== MAIN TEST ====================

def main():
    print("🧪 Testing Executor Agent")
    print("=" * 80)
    print()
    
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not set!")
        print("   Run: export ANTHROPIC_API_KEY='your-key-here'")
        return 1
    
    print("✅ API key found")
    print()
    
    # Load workflow and tools
    workflow_path = Path(__file__).parent / "workflows/example_onboarding/workflow.md"
    tools_path = Path(__file__).parent / "workflows/example_onboarding/tools.json"
    
    if not workflow_path.exists():
        print(f"❌ Workflow not found: {workflow_path}")
        return 1
    
    if not tools_path.exists():
        print(f"❌ Tools not found: {tools_path}")
        return 1
    
    # Load content
    with open(workflow_path, 'r') as f:
        workflow_content = f.read()
    
    with open(tools_path, 'r') as f:
        tools_data = json.load(f)
    
    tools_config = ToolConfig.from_json(tools_data)
    
    print(f"📋 Workflow: {workflow_path.name}")
    print(f"🔧 Tools: {len(tools_config.tools)} scoped tools from {len(tools_config.mcp_servers)} servers")
    print()
    print("📄 Workflow Preview:")
    print("-" * 80)
    print(workflow_content[:400])
    print("...")
    print("-" * 80)
    print()
    
    # Create mock tool executor
    print("🎭 Using MockToolExecutor (no real API calls)")
    mock_executor = MockToolExecutor()
    
    # Create the actual ExecutorAgent
    print("🤖 Creating ExecutorAgent...")
    executor = ExecutorAgent(tool_executor=mock_executor)
    
    # Execute workflow
    print("🚀 Starting execution...\n")
    
    try:
        trace = executor.execute_workflow(
            workflow_path=str(workflow_path),
            tools_config=tools_config,
            workflow_content=workflow_content
        )
        
        # Print trace
        print("\n" + "=" * 80)
        print("📊 EXECUTION TRACE (JSON)")
        print("=" * 80)
        print()
        trace_json = trace.to_json()
        print(json.dumps(trace_json, indent=2))
        print()
        
        # Summary
        print("=" * 80)
        print("📈 SUMMARY")
        print("=" * 80)
        print(f"Status: {trace.status.value}")
        print(f"Total Steps: {len(trace.steps)}")
        print(f"Completed: {sum(1 for s in trace.steps if s.status.value == 'completed')}")
        print(f"Failed: {sum(1 for s in trace.steps if s.status.value == 'failed')}")
        print(f"Clarifications: {len(trace.clarification_requests)}")
        print()
        
        if trace.status.value == "completed":
            print("🎉 Workflow completed successfully!")
            return 0
        elif trace.status.value == "needs_clarification":
            print("❓ Workflow needs user clarification")
            return 2
        else:
            print(f"❌ Workflow failed: {trace.final_summary}")
            return 1
    
    except Exception as e:
        print(f"\n❌ Execution error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
