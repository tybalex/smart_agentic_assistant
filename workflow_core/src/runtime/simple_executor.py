"""
Simple Workflow Executor

A minimal but functional executor that can run workflows.
Good for getting started, can be replaced with LangGraph later.
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from .base import WorkflowRuntime
from ..schema import (
    WorkflowDefinition,
    WorkflowExecutionResult,
    ExecutionContext,
    NodeResult,
    WorkflowNode,
)
from .node_handlers import NodeHandlerRegistry


class SimpleWorkflowExecutor(WorkflowRuntime):
    """
    Simple sequential workflow executor.
    
    Executes nodes in topological order, respects dependencies,
    handles basic error cases.
    """
    
    def __init__(self):
        # Import WorkflowTools here to avoid circular import
        # (WorkflowTools imports SimpleWorkflowExecutor)
        workflow_tools = None
        try:
            from ..agent.tools import WorkflowTools
            workflow_tools = WorkflowTools()
        except ImportError as e:
            # WorkflowTools not available, continue without it
            pass
        except Exception as e:
            # Other error, log and continue
            print(f"Warning: Could not initialize WorkflowTools: {e}")
        
        self.handler_registry = NodeHandlerRegistry(workflow_tools)
    
    async def execute(
        self,
        workflow: WorkflowDefinition,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionResult:
        """Execute the workflow"""
        
        # Validate first and collect warnings
        validation = await self.validate(workflow)
        execution_warnings = validation.get("warnings", [])
        
        if not validation["is_valid"]:
            return WorkflowExecutionResult(
                workflow_id=workflow.metadata.name,
                execution_id=str(uuid.uuid4()),
                status="failed",
                node_results={},
                start_time=datetime.now().isoformat(),
                end_time=datetime.now().isoformat(),
                total_duration=0.0,
                error=f"Workflow validation failed: {validation['errors']}",
                warnings=execution_warnings
            )
        
        # Setup execution context
        execution_id = str(uuid.uuid4())
        context = ExecutionContext(
            workflow_id=workflow.metadata.name,
            execution_id=execution_id,
            variables={**workflow.variables, **(initial_context or {})},
            node_results={}
        )
        
        start_time = datetime.now()
        node_results = {}
        
        try:
            # Get execution order
            sorted_nodes = workflow.topological_sort()
            
            # Execute nodes in order
            for node in sorted_nodes:
                # Check if we should execute this node
                if not self._should_execute_node(node, context):
                    node_results[node.id] = NodeResult(
                        node_id=node.id,
                        status="skipped",
                        output=None
                    )
                    # Store None in context so other nodes can reference it without error
                    context.node_results[node.id] = None
                    continue
                
                # Execute the node
                node_start = time.time()
                try:
                    result = await self.execute_node(workflow, node.id, context)
                    node_results[node.id] = NodeResult(
                        node_id=node.id,
                        status="success",
                        output=result,
                        execution_time=time.time() - node_start
                    )
                    # Store result in context for dependent nodes
                    context.node_results[node.id] = result
                    
                except Exception as e:
                    node_results[node.id] = NodeResult(
                        node_id=node.id,
                        status="failed",
                        error=str(e),
                        execution_time=time.time() - node_start
                    )
                    
                    # Handle error based on node configuration
                    if node.on_error == "continue":
                        continue
                    else:
                        # Default: fail the workflow
                        break
            
            # Determine overall status
            has_failures = any(r.status == "failed" for r in node_results.values())
            all_success = all(r.status == "success" for r in node_results.values())
            
            if all_success:
                status = "success"
            elif has_failures:
                status = "failed"
            else:
                status = "partial"
            
            end_time = datetime.now()
            
            return WorkflowExecutionResult(
                workflow_id=workflow.metadata.name,
                execution_id=execution_id,
                status=status,
                node_results=node_results,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                total_duration=(end_time - start_time).total_seconds(),
                warnings=execution_warnings
            )
            
        except Exception as e:
            end_time = datetime.now()
            return WorkflowExecutionResult(
                workflow_id=workflow.metadata.name,
                execution_id=execution_id,
                status="failed",
                node_results=node_results,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                total_duration=(end_time - start_time).total_seconds(),
                error=str(e),
                warnings=execution_warnings
            )
    
    async def execute_node(
        self,
        workflow: WorkflowDefinition,
        node_id: str,
        context: ExecutionContext
    ) -> Any:
        """Execute a single node"""
        node = workflow.get_node(node_id)
        if not node:
            raise ValueError(f"Node '{node_id}' not found")
        
        # Get handler for this node type
        handler = self.handler_registry.get_handler(node.type)
        
        # Replace variable references in config
        resolved_config = self._resolve_variables(node.config, context)
        
        # Execute the handler
        result = await handler.execute(resolved_config, context)
        
        return result
    
    async def validate(self, workflow: WorkflowDefinition) -> Dict[str, Any]:
        """Validate the workflow"""
        import re
        errors = []
        warnings = []
        
        # Check for dependency errors
        dep_errors = workflow.validate_dependencies()
        errors.extend(dep_errors)
        
        # Check for circular dependencies (will raise if present)
        try:
            workflow.topological_sort()
        except ValueError as e:
            errors.append(str(e))
        
        # Check if all node types are supported
        for node in workflow.nodes:
            if not self.handler_registry.has_handler(node.type):
                warnings.append(f"Node type '{node.type}' may not be supported")
        
        # Check for variable reference issues
        node_ids = {node.id for node in workflow.nodes}
        conditional_nodes = {node.id for node in workflow.nodes if node.condition}
        
        for node in workflow.nodes:
            # Find all {{variable}} references in the node config
            config_str = str(node.config)
            var_pattern = r'\{\{([^}]+)\}\}'
            var_matches = re.findall(var_pattern, config_str)
            
            for var_ref in var_matches:
                var_ref = var_ref.strip()
                
                # Strip any filters (e.g., "customer_email | replace('@', '-')" -> "customer_email")
                if '|' in var_ref:
                    var_ref = var_ref.split('|')[0].strip()
                
                parts = var_ref.split('.')
                referenced_node = parts[0]
                
                # Check if referenced node exists
                if referenced_node not in workflow.variables and referenced_node not in node_ids:
                    errors.append(
                        f"Node '{node.id}' references undefined variable/node: {{{{'{var_ref}'}}}}"
                    )
                
                # Check if referenced node is conditional (might be skipped)
                elif referenced_node in conditional_nodes:
                    # Check if the current node depends on the conditional node
                    if referenced_node not in (node.depends_on or []):
                        warnings.append(
                            f"Node '{node.id}' references conditional node '{referenced_node}' without depending on it. "
                            f"If '{referenced_node}' is skipped, this variable will be undefined."
                        )
                    else:
                        warnings.append(
                            f"Node '{node.id}' references conditional node '{referenced_node}' which may be skipped. "
                            f"Consider handling the case where '{referenced_node}' doesn't execute."
                        )
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _should_execute_node(self, node: WorkflowNode, context: ExecutionContext) -> bool:
        """Determine if a node should execute based on conditions"""
        if not node.condition:
            return True
        
        # Simple condition evaluation (can be enhanced)
        # For now, just check if it's a simple boolean expression
        try:
            # Replace variables in condition
            condition = self._resolve_variables({"expr": node.condition}, context)["expr"]
            
            # Debug: print the resolved condition
            print(f"  🔍 Evaluating condition for '{node.id}': {condition}")
            
            result = bool(eval(condition))  # Warning: eval is dangerous, use safe evaluator in production
            
            print(f"  ➡️ Condition result: {result} → {'Execute' if result else 'Skip'}")
            return result
            
        except Exception as e:
            # Don't silently fail! Log the error
            print(f"  ⚠️ WARNING: Condition evaluation failed for '{node.id}': {e}")
            print(f"  ⚠️ Original condition: {node.condition}")
            print(f"  ⚠️ Defaulting to EXECUTE (this might not be what you want!)")
            return True  # If condition can't be evaluated, execute the node
    
    def _resolve_variables(self, config: Dict[str, Any], context: ExecutionContext) -> Dict[str, Any]:
        """Replace {{variable}} references with actual values"""
        import re
        
        # Track unresolved variables for warnings
        unresolved_vars = []
        
        def apply_filter(value, filter_name: str):
            """Apply a Jinja2-style filter to a value"""
            filter_name = filter_name.strip()
            
            # Common filters
            if filter_name == "length" or filter_name == "count":
                if value is None:
                    return 0
                try:
                    return len(value)
                except:
                    return 0
            
            elif filter_name == "upper":
                return str(value).upper() if value is not None else ""
            
            elif filter_name == "lower":
                return str(value).lower() if value is not None else ""
            
            elif filter_name == "trim" or filter_name == "strip":
                return str(value).strip() if value is not None else ""
            
            elif filter_name == "first":
                if value and hasattr(value, '__getitem__'):
                    return value[0] if len(value) > 0 else None
                return None
            
            elif filter_name == "last":
                if value and hasattr(value, '__getitem__'):
                    return value[-1] if len(value) > 0 else None
                return None
            
            elif filter_name.startswith("replace("):
                # Handle replace(old, new) filter
                # Example: replace('@', '-') or replace("@", "-")
                match = re.match(r'replace\(["\']([^"\']*)["\'],\s*["\']([^"\']*)["\']', filter_name)
                if match:
                    old_str = match.group(1)
                    new_str = match.group(2)
                    return str(value).replace(old_str, new_str) if value is not None else ""
                return str(value) if value is not None else ""
            
            elif filter_name == "default" or filter_name.startswith("default("):
                # Handle default(value) filter
                if value is not None and value != "":
                    return value
                # Extract default value from filter
                match = re.match(r'default\(["\']?([^"\']+)["\']?\)', filter_name)
                if match:
                    return match.group(1)
                return ""
            
            else:
                # Unknown filter, return value as-is
                return value
        
        def resolve_variable_path(var_path: str):
            """Resolve a dot-notated variable path to its value, with Jinja2 filter support"""
            # Check for pipe filters (e.g., "records | length")
            if "|" in var_path:
                parts = var_path.split("|", 1)
                base_path = parts[0].strip()
                filter_expr = parts[1].strip()
                
                # Resolve the base path first
                value = resolve_variable_path(base_path)
                
                # Apply filters (can be chained)
                for filter_part in filter_expr.split("|"):
                    value = apply_filter(value, filter_part)
                
                return value
            
            # Original logic for dot notation
            parts = var_path.split('.')
            
            # Check node results
            if parts[0] in context.node_results:
                value = context.node_results[parts[0]]
                for part in parts[1:]:
                    if value is None:
                        unresolved_vars.append(var_path)
                        return None
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = getattr(value, part, None)
                # Check if final value is None (couldn't fully resolve path)
                if value is None and len(parts) > 1:
                    unresolved_vars.append(var_path)
                return value
            
            # Check variables
            if parts[0] in context.variables:
                value = context.variables[parts[0]]
                for part in parts[1:]:
                    if value is None:
                        unresolved_vars.append(var_path)
                        return None
                    if isinstance(value, dict):
                        value = value.get(part)
                    else:
                        value = getattr(value, part, None)
                # Check if final value is None (couldn't fully resolve path)
                if value is None and len(parts) > 1:
                    unresolved_vars.append(var_path)
                return value
            
            # Variable not found
            unresolved_vars.append(var_path)
            return None
        
        def resolve_value(obj):
            """Recursively resolve variables in a config object"""
            if isinstance(obj, str):
                # Check if this is a variable reference
                pattern = r'\{\{([^}]+)\}\}'
                matches = list(re.finditer(pattern, obj))
                
                if not matches:
                    return obj  # No variables to resolve
                
                # If the entire string is a single variable, return the actual value (not as string)
                if len(matches) == 1 and matches[0].group(0) == obj:
                    var_path = matches[0].group(1).strip()
                    value = resolve_variable_path(var_path)
                    # If resolved, return the actual value; otherwise keep template
                    return value if value is not None else obj
                
                # Multiple variables or mixed content - do string replacement
                def replace_var(match):
                    var_path = match.group(1).strip()
                    value = resolve_variable_path(var_path)
                    if value is None:
                        return match.group(0)  # Keep template if not found
                    # Convert to string for inline replacement
                    import json
                    return json.dumps(value) if not isinstance(value, str) else value
                
                return re.sub(pattern, replace_var, obj)
            
            elif isinstance(obj, dict):
                return {k: resolve_value(v) for k, v in obj.items()}
            
            elif isinstance(obj, list):
                return [resolve_value(item) for item in obj]
            
            else:
                return obj
        
        try:
            resolved_config = resolve_value(config)
            
            # Error if variables can't be resolved (instead of just warning)
            if unresolved_vars:
                unique_unresolved = list(set(unresolved_vars))
                error_msg = f"Cannot resolve {len(unique_unresolved)} variable(s): {', '.join(unique_unresolved)}"
                print(f"  ❌ {error_msg}")
                raise ValueError(error_msg)
            
            return resolved_config
        except ValueError:
            # Re-raise ValueError (our unresolved variable error)
            raise
        except Exception as e:
            # If resolution fails for other reasons, return original config
            print(f"  ⚠️  Error resolving variables: {e}")
            return config
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Return capabilities of this runtime"""
        return {
            "parallel_execution": False,  # Sequential for now
            "conditional_branching": True,
            "human_in_the_loop": False,  # Not yet implemented
            "checkpointing": False,
            "streaming": False,
            "retry": False,  # Not yet implemented
        }

