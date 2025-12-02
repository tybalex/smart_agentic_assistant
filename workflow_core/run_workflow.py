"""
Run Workflow Manually

Execute any workflow YAML file and see detailed output of each step.
This is useful for testing and debugging workflows.

Usage:
    python run_workflow.py workflow.yaml
    python run_workflow.py member_onboarding.yaml
"""

import sys
import asyncio
import yaml
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.schema import WorkflowDefinition
from src.runtime import SimpleWorkflowExecutor


def resolve_variables_for_display(config, variables, node_results, current_node_id):
    """Resolve {{variable}} references for display purposes"""
    import re
    import json
    
    def resolve_variable_path(var_path):
        """Resolve a dot-notated variable path to its value"""
        parts = var_path.split('.')
        
        # Check node results (but not current node to avoid circular refs)
        if parts[0] in node_results and parts[0] != current_node_id:
            # Get the NodeResult object and extract its output
            node_result_obj = node_results[parts[0]]
            value = node_result_obj.output if hasattr(node_result_obj, 'output') else node_result_obj
            # Navigate through remaining path parts
            for part in parts[1:]:
                if value is None:
                    return None
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)
            return value
        
        # Check variables
        full_var = '.'.join(parts)
        if full_var in variables:
            return variables[full_var]
        
        if parts[0] in variables:
            value = variables[parts[0]]
            for part in parts[1:]:
                if value is None:
                    return None
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)
            return value
        
        return None
    
    def resolve_value(obj):
        """Recursively resolve variables in a config object"""
        if isinstance(obj, str):
            # Check if this is a variable reference
            pattern = r'\{\{([^}]+)\}\}'
            matches = list(re.finditer(pattern, obj))
            
            if not matches:
                return obj  # No variables to resolve
            
            # If the entire string is a single variable, return the actual value
            if len(matches) == 1 and matches[0].group(0) == obj:
                var_path = matches[0].group(1).strip()
                value = resolve_variable_path(var_path)
                return value if value is not None else obj
            
            # Multiple variables or mixed content - do string replacement
            def replace_var(match):
                var_path = match.group(1).strip()
                value = resolve_variable_path(var_path)
                if value is None:
                    return match.group(0)
                # Convert to string for inline replacement
                return json.dumps(value) if not isinstance(value, str) else value
            
            return re.sub(pattern, replace_var, obj)
        
        elif isinstance(obj, dict):
            return {k: resolve_value(v) for k, v in obj.items()}
        
        elif isinstance(obj, list):
            return [resolve_value(item) for item in obj]
        
        else:
            return obj
    
    try:
        return resolve_value(config)
    except Exception as e:
        # If resolution fails, return original
        return config


def print_section(title: str, char: str = "="):
    """Print a section header"""
    print(f"\n{char * 70}")
    print(f"{title}")
    print(f"{char * 70}")


def print_node_result(node_id: str, result, node_config, index: int, total: int):
    """Print a node execution result"""
    status_icons = {
        "success": "✅",
        "failed": "❌",
        "skipped": "⏭️"
    }
    
    icon = status_icons.get(result.status, "❓")
    print(f"\n[{index}/{total}] {icon} {node_id}")
    print(f"  Status: {result.status}")
    print(f"  Execution Time: {result.execution_time:.3f}s" if result.execution_time else "  Execution Time: N/A")
    
    # Show input/config
    if node_config:
        print(f"  Input:")
        try:
            import json
            if isinstance(node_config, dict):
                # Show key parameters (limit to avoid clutter)
                shown = 0
                max_show = 5
                for key, value in node_config.items():
                    if shown >= max_show:
                        remaining = len(node_config) - max_show
                        print(f"    ... ({remaining} more parameters)")
                        break
                    value_str = str(value)
                    if len(value_str) > 80:
                        value_str = value_str[:80] + "..."
                    print(f"    {key}: {value_str}")
                    shown += 1
            else:
                config_str = str(node_config)
                if len(config_str) > 200:
                    config_str = config_str[:200] + "..."
                print(f"    {config_str}")
        except:
            pass
    
    if result.error:
        print(f"  Error: {result.error}")
    
    if result.output:
        print(f"  Output:")
        output_str = str(result.output)
        # Pretty print output, truncate if too long
        if len(output_str) > 500:
            print(f"    {output_str[:500]}...")
        else:
            # Try to format as YAML for better readability
            try:
                import json
                if isinstance(result.output, dict):
                    for key, value in result.output.items():
                        value_str = str(value)
                        if len(value_str) > 100:
                            value_str = value_str[:100] + "..."
                        print(f"    {key}: {value_str}")
                else:
                    print(f"    {output_str}")
            except:
                print(f"    {output_str}")


async def run_workflow(workflow_file: str, variables: dict = None):
    """Run a workflow and display detailed output"""
    
    # Load workflow
    print_section("🚀 Loading Workflow", "=")
    print(f"File: {workflow_file}")
    
    try:
        with open(workflow_file, 'r') as f:
            workflow_data = yaml.safe_load(f)
        
        workflow = WorkflowDefinition.model_validate(workflow_data)
        print(f"✅ Loaded: {workflow.metadata.name}")
        print(f"   Description: {workflow.metadata.description or 'N/A'}")
        print(f"   Version: {workflow.metadata.version}")
        print(f"   Nodes: {len(workflow.nodes)}")
    except FileNotFoundError:
        print(f"❌ Error: Workflow file not found: {workflow_file}")
        return
    except Exception as e:
        print(f"❌ Error loading workflow: {e}")
        return
    
    # Show workflow variables
    if workflow.variables:
        print(f"\n📋 Workflow Variables:")
        for key, value in workflow.variables.items():
            print(f"   {key}: {value}")
    
    if variables:
        print(f"\n📋 Runtime Variables:")
        for key, value in variables.items():
            print(f"   {key}: {value}")
    
    # Execute workflow
    print_section("⚙️  Executing Workflow", "=")
    start_time = datetime.now()
    
    executor = SimpleWorkflowExecutor()
    result = await executor.execute(workflow, variables)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Show execution results
    print_section("📊 Execution Results", "=")
    
    # Overall status
    status_icon = "✅" if result.status == "success" else "❌"
    print(f"\n{status_icon} Overall Status: {result.status}")
    print(f"⏱️  Total Duration: {duration:.2f}s")
    print(f"🆔 Execution ID: {result.execution_id}")
    
    if result.error:
        print(f"❌ Error: {result.error}")
    
    # Show warnings if any
    if result.warnings:
        print(f"\n⚠️  Warnings ({len(result.warnings)}):")
        for warning in result.warnings:
            print(f"   - {warning}")
    
    # Node results
    print_section("📝 Node Execution Details", "-")
    total = len(result.node_results)
    
    # Merge workflow variables and runtime variables for display resolution
    all_variables = {**workflow.variables, **(variables or {})}
    
    for i, (node_id, node_result) in enumerate(result.node_results.items(), 1):
        # Get the node config from the workflow and resolve variables
        node = next((n for n in workflow.nodes if n.id == node_id), None)
        if node:
            # Resolve variables in the config for display
            node_config = resolve_variables_for_display(node.config, all_variables, result.node_results, node_id)
        else:
            node_config = None
        print_node_result(node_id, node_result, node_config, i, total)
    
    # Summary
    print_section("📈 Summary", "=")
    success_count = sum(1 for r in result.node_results.values() if r.status == "success")
    failed_count = sum(1 for r in result.node_results.values() if r.status == "failed")
    skipped_count = sum(1 for r in result.node_results.values() if r.status == "skipped")
    
    print(f"\n✅ Success: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"⏭️  Skipped: {skipped_count}")
    print(f"📊 Total: {total}")
    print(f"⏱️  Duration: {duration:.2f}s")
    
    # Return status for scripting
    return result.status == "success"


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python run_workflow.py <workflow.yaml> [OPTIONS]")
        print("\nOptions:")
        print("  var1=value1 var2=value2    Set variables via command line")
        print("  --config <file.json>       Load variables from JSON/YAML config file")
        print("\nExamples:")
        print("  python run_workflow.py member_onboarding.yaml")
        print("  python run_workflow.py member_onboarding.yaml member_name='Acme Corp'")
        print("  python run_workflow.py member_onboarding.yaml --config config.json")
        sys.exit(1)
    
    workflow_file = sys.argv[1]
    
    # Parse runtime variables from command line or config file
    variables = {}
    config_file = None
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        
        if arg == "--config" and i + 1 < len(sys.argv):
            config_file = sys.argv[i + 1]
            i += 2
        elif "=" in arg:
            key, value = arg.split("=", 1)
            variables[key] = value
            i += 1
        else:
            i += 1
    
    # Load config file if specified
    if config_file:
        try:
            with open(config_file, 'r') as f:
                if config_file.endswith('.json'):
                    import json
                    config_vars = json.load(f)
                else:
                    config_vars = yaml.safe_load(f)
                
                # Merge with command line vars (command line takes precedence)
                for key, value in config_vars.items():
                    if key not in variables:
                        variables[key] = value
                
                print(f"📝 Loaded {len(config_vars)} variables from {config_file}")
        except Exception as e:
            print(f"❌ Error loading config file: {e}")
            sys.exit(1)
    
    # Run workflow
    try:
        success = asyncio.run(run_workflow(workflow_file, variables))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

