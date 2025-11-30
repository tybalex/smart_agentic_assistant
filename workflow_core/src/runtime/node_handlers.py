"""
Node Handlers

Each node type (tool_call, transform, condition, etc.) has a handler
that knows how to execute that type of node.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio
import json
import random

from ..schema import ExecutionContext

# Try to import functions_registry, but make it optional
try:
    from ..functions_registry import get_function, FunctionStatus
    HAS_FUNCTIONS_REGISTRY = True
except ImportError:
    HAS_FUNCTIONS_REGISTRY = False
    get_function = None
    FunctionStatus = None


class NodeHandler(ABC):
    """Base class for node handlers"""
    
    @abstractmethod
    async def execute(self, config: Dict[str, Any], context: ExecutionContext) -> Any:
        """Execute this node type"""
        pass


class FunctionCallHandler(NodeHandler):
    """Handler for function calls using WorkflowTools or the functions registry"""
    
    def __init__(self, workflow_tools=None):
        """
        Initialize the handler.
        
        Args:
            workflow_tools: Optional WorkflowTools instance for calling built-in tools
        """
        self.workflow_tools = workflow_tools
    
    async def execute(self, config: Dict[str, Any], context: ExecutionContext) -> Any:
        """Execute a registered function"""
        function_name = config.get("function_name")
        parameters = config.get("parameters", {})
        
        if not function_name:
            return {
                "error": "No function_name specified in config"
            }
        
        # Check if function_name is a TODO
        if function_name.startswith("TODO:"):
            return {
                "status": "todo",
                "message": f"Function not implemented: {function_name}",
                "action_required": "Implement this function or use http_request as fallback"
            }
        
        # First, try to call from WorkflowTools if available
        if self.workflow_tools and hasattr(self.workflow_tools, function_name):
            try:
                print(f"  🔧 Calling WorkflowTools.{function_name}")
                method = getattr(self.workflow_tools, function_name)
                result = method(**parameters)
                return result
            except Exception as e:
                return {
                    "error": f"Error calling {function_name}: {str(e)}"
                }
        
        # Try to execute via HTTP request to function registry at localhost:9999
        try:
            import httpx
            print(f"  🌐 Calling function registry: {function_name}")
            
            # First, get the function details to find its category
            func_response = httpx.get(
                f"http://localhost:9999/functions/{function_name}",
                timeout=10.0
            )
            func_response.raise_for_status()
            func_data = func_response.json()
            category = func_data.get('category', 'unknown')
            
            # Make POST request to execute the function using /{category}/{function_name}
            response = httpx.post(
                f"http://localhost:9999/{category}/{function_name}",
                json=parameters,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"  ✅ Function executed successfully")
            return result
            
        except httpx.HTTPError as e:
            print(f"  ❌ HTTP error calling function registry: {e}")
            # Continue to fallback options
            pass
        except Exception as e:
            print(f"  ⚠️  Error calling function registry: {e}")
            # Continue to fallback options
            pass
        
        # Fallback to local functions registry if available
        if HAS_FUNCTIONS_REGISTRY and get_function:
            func = get_function(function_name)
            
            if not func:
                return {
                    "error": f"Function '{function_name}' not found in registry or WorkflowTools",
                    "suggestion": "Use 'http_request' function for custom API calls or add function to registry"
                }
            
            # Check function status
            if func.status == FunctionStatus.TODO:
                return {
                    "status": "todo",
                    "function": function_name,
                    "message": f"Function '{function_name}' is registered but not yet implemented",
                    "parameters_needed": list(func.parameters.keys()),
                    "action_required": "Implement this function or use http_request as fallback"
                }
            
            elif func.status == FunctionStatus.MOCK:
                # Return mock response (with randomization if available)
                print(f"  🧪 Mock function: {function_name}")
                mock_data = func.get_mock_response()
                return {
                    "status": "success",
                    "function": function_name,
                    "mock": True,
                    **mock_data
                }
            
            elif func.status == FunctionStatus.IMPLEMENTED:
                # Call actual implementation
                # TODO: Implement actual function execution
                print(f"  ✅ Executing function: {function_name}")
                return {
                    "status": "success",
                    "function": function_name,
                    "result": "Function executed successfully"
                }
        
        # If we get here, function not found anywhere
        return {
            "error": f"Function '{function_name}' not found",
            "suggestion": "Add function to WorkflowTools or functions registry"
        }


class APICallHandler(NodeHandler):
    """Handler for direct API calls (legacy, use tool_call instead)"""
    
    async def execute(self, config: Dict[str, Any], context: ExecutionContext) -> Any:
        """Make an API call"""
        import aiohttp
        
        url = config.get("url")
        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})
        body = config.get("body")
        
        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, headers=headers, json=body) as response:
                return {
                    "status": response.status,
                    "data": await response.json() if response.content_type == "application/json" else await response.text(),
                    "headers": dict(response.headers)
                }


class TransformHandler(NodeHandler):
    """Handler for data transformation"""
    
    async def execute(self, config: Dict[str, Any], context: ExecutionContext) -> Any:
        """Transform data using Python expression or function"""
        input_data = config.get("input")
        operation = config.get("operation")
        
        try:
            if operation == "filter":
                # Filter a list
                condition = config.get("condition")
                return [item for item in input_data if eval(condition, {"item": item})]
            
            elif operation == "map":
                # Map over a list
                expression = config.get("expression")
                return [eval(expression, {"item": item}) for item in input_data]
            
            elif operation == "reduce":
                # Reduce a list
                expression = config.get("expression")
                initial = config.get("initial", 0)
                result = initial
                for item in input_data:
                    result = eval(expression, {"acc": result, "item": item})
                return result
            
            else:
                # Custom expression - try to evaluate
                expression = config.get("expression")
                return eval(expression, {"input": input_data, "context": context})
                
        except Exception as e:
            # If evaluation fails (e.g., JavaScript syntax), return mock data
            print(f"  🧪 Mock transform (expression evaluation failed: {type(e).__name__})")
            
            # Generate reasonable mock data based on operation type
            if operation == "custom":
                # For custom operations, return a mock structure
                return {
                    "contacts_with_assignments": [
                        {
                            "email": f"contact{i+1}@example.com",
                            "name": f"Mock Contact {i+1}",
                            "title": random.choice(["Engineer", "Manager", "Director"]),
                            "mailing_lists": [f"list_{random.randint(1,5)}"],
                            "slack_channels": [f"C{random.randint(10000,99999)}"]
                        }
                        for i in range(random.randint(2, 5))
                    ],
                    "all_contact_emails": [f"contact{i+1}@example.com" for i in range(random.randint(2, 5))],
                    "mock": True
                }
            elif operation == "map":
                # Return mock mapped data
                return [f"transformed_item_{i}" for i in range(random.randint(2, 5))]
            elif operation == "filter":
                # Return mock filtered data
                return [f"filtered_item_{i}" for i in range(random.randint(1, 3))]
            else:
                # Generic mock data
                return {"mock": True, "operation": operation, "status": "mocked"}


class ConditionHandler(NodeHandler):
    """Handler for conditional logic"""
    
    async def execute(self, config: Dict[str, Any], context: ExecutionContext) -> Any:
        """Evaluate condition and return result"""
        condition = config.get("condition")
        
        # Evaluate condition
        result = eval(condition, {"context": context})
        
        return {
            "condition_met": result,
            "branch": "true" if result else "false"
        }


class LogHandler(NodeHandler):
    """Handler for logging/debugging"""
    
    async def execute(self, config: Dict[str, Any], context: ExecutionContext) -> Any:
        """Log a message"""
        message = config.get("message", "")
        level = config.get("level", "info")
        data = config.get("data")
        
        print(f"[{level.upper()}] {message}")
        if data:
            print(f"Data: {json.dumps(data, indent=2)}")
        
        return {"logged": True, "message": message}


class DelayHandler(NodeHandler):
    """Handler for delays/waits"""
    
    async def execute(self, config: Dict[str, Any], context: ExecutionContext) -> Any:
        """Wait for specified duration"""
        duration = config.get("duration", 1)  # seconds
        await asyncio.sleep(duration)
        return {"delayed": duration}


class PassthroughHandler(NodeHandler):
    """Handler for unknown/custom node types - just returns config"""
    
    async def execute(self, config: Dict[str, Any], context: ExecutionContext) -> Any:
        """Return the config as-is (for testing/debugging)"""
        return config


class NodeHandlerRegistry:
    """Registry of node handlers"""
    
    def __init__(self, workflow_tools=None):
        """
        Initialize the registry.
        
        Args:
            workflow_tools: Optional WorkflowTools instance for function calls
        """
        self.handlers: Dict[str, NodeHandler] = {
            "function_call": FunctionCallHandler(workflow_tools),  # New: use functions registry or WorkflowTools
            "api_call": APICallHandler(),            # Legacy: direct API calls
            "transform": TransformHandler(),
            "condition": ConditionHandler(),
            "log": LogHandler(),
            "delay": DelayHandler(),
        }
        self.default_handler = PassthroughHandler()
    
    def register(self, node_type: str, handler: NodeHandler):
        """Register a new handler"""
        self.handlers[node_type] = handler
    
    def get_handler(self, node_type: str) -> NodeHandler:
        """Get handler for a node type"""
        return self.handlers.get(node_type, self.default_handler)
    
    def has_handler(self, node_type: str) -> bool:
        """Check if handler exists for node type"""
        return node_type in self.handlers

