#!/usr/bin/env python3
"""
Example: How Main Agent discovers tools and gives them to Executor
"""

import asyncio
import json
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mcp_registry import create_registry_from_config, MCPToolExecutor


async def main_agent_discover_tools():
    """
    Step 1: Main Agent discovers all available tools from MCP servers
    """
    print("=" * 80)
    print("MAIN AGENT: Discovering available tools")
    print("=" * 80)
    print()
    
    # Create registry from config
    registry = await create_registry_from_config()
    
    # Discover tools from all servers
    tools_by_server = await registry.discover_all_tools()
    
    # Print summary
    print()
    print(registry.get_all_tools_summary())
    
    return registry, tools_by_server


async def main_agent_select_tools(registry, tools_by_server):
    """
    Step 2: Main Agent selects which tools to give to Executor
    (In real implementation, Main Agent LLM would decide this based on workflow)
    """
    print()
    print("=" * 80)
    print("MAIN AGENT: Selecting tools for workflow")
    print("=" * 80)
    print()
    
    # Example: Select first 3 tools from each server for demo
    selected_tools = []
    for server_name, tools in tools_by_server.items():
        for tool in tools[:3]:  # Pick first 3 from each server
            selected_tools.append((server_name, tool['tool']))
    
    if not selected_tools:
        print("⚠️  No tools available to select!")
        return []
    
    print("🤖 Main Agent selected tools for workflow (sample):")
    for server, tool in selected_tools:
        print(f"   - {server}/{tool}")
    print()
    
    # Filter to get full tool configs
    tool_configs = registry.filter_tools_by_names(selected_tools)
    
    # Create tools.json format
    tools_json = {
        "mcp_servers": list(set(t['server'] for t in tool_configs)),
        "tools": tool_configs,
        "version": "1.0"
    }
    
    # Save to file
    try:
        output_dir = Path(__file__).parent.parent / "workflows/dynamic_onboarding"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        tools_path = output_dir / "tools.json"
        with open(tools_path, 'w') as f:
            json.dump(tools_json, f, indent=2)
        
        print(f"✅ Saved selected tools to: {tools_path}")
    except Exception as e:
        print(f"⚠️  Could not save tools.json: {e}")
    
    print()
    return tool_configs


async def executor_agent_use_tools(registry, tool_configs):
    """
    Step 3: Executor Agent uses ONLY the selected tools
    """
    print()
    print("=" * 80)
    print("EXECUTOR AGENT: Using scoped tools")
    print("=" * 80)
    print()
    
    # Create scoped executor
    executor = MCPToolExecutor(registry, tool_configs)
    
    print("✅ Executor has access to these tools:")
    for tool in tool_configs:
        print(f"   - {tool['server']}/{tool['tool']}")
    print()
    
    print("📋 Note: Actual tool execution would reconnect to MCP servers.")
    print("   For now, we've just demonstrated tool discovery and selection!")
    print()


async def main():
    """Full workflow: Main Agent discovers → selects → Executor uses"""
    
    print("🚀 Claude Workflow Agent - Tool Discovery Demo")
    print()
    
    # Step 1: Main Agent discovers all tools
    registry, tools_by_server = await main_agent_discover_tools()
    
    # Step 2: Main Agent selects tools for specific workflow
    tool_configs = await main_agent_select_tools(registry, tools_by_server)
    
    if not tool_configs:
        print("\n⚠️  No tools selected - ending demo")
        return
    
    # Step 3: Executor Agent uses scoped tools
    await executor_agent_use_tools(registry, tool_configs)
    
    print()
    print("=" * 80)
    print("✅ Demo Complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
