"""
Node Handlers

Each node type (tool_call, transform, condition, etc.) has a handler
that knows how to execute that type of node.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio
import json

from ..schema import ExecutionContext


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
        """Execute a registered function via the functions registry at localhost:9999"""
        function_name = config.get("function_name")
        parameters = config.get("parameters", {})
        
        if not function_name:
            return {
                "error": "No function_name specified in config"
            }
        
        # Check if function_name is a TODO marker
        if function_name.startswith("TODO:"):
            return {
                "status": "todo",
                "message": f"Function not implemented: {function_name}",
                "action_required": "Implement this function or use http_request as fallback"
            }
        
        # First, try to call from WorkflowTools if available (for built-in workflow tools)
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
        
        # Call the function registry at localhost:9999
        # This is the main execution path for all external functions
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
            
            # Check if function is configured (not TODO or MOCK status)
            status = func_data.get('status', 'unknown')
            if status in ['todo', 'TODO']:
                return {
                    "error": f"Function '{function_name}' is not yet implemented",
                    "status": "todo",
                    "function": function_name,
                    "message": f"This function is registered but not implemented yet.",
                    "action_required": "Implement this function in the registry or use http_request as fallback"
                }
            
            if status in ['mock', 'MOCK']:
                return {
                    "error": f"Function '{function_name}' is not configured",
                    "status": "configuration_required",
                    "function": function_name,
                    "message": f"This function requires API credentials or configuration to work.",
                    "action_required": "Configure this function with proper API credentials/settings in the function registry"
                }
            
            # Make POST request to execute the function using /{category}/{function_name}
            response = httpx.post(
                f"http://localhost:9999/{category}/{function_name}",
                json=parameters,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            # Parse the result field if it's a JSON string
            # Function registry returns: {"result": "{\"key\": \"value\"}", "success": true}
            # We want to return the parsed result directly so {{node.field}} references work
            if isinstance(result, dict) and 'result' in result:
                result_value = result['result']
                # Try to parse if it's a JSON string
                if isinstance(result_value, str):
                    try:
                        parsed_result = json.loads(result_value)
                        print(f"  ✅ Function executed successfully")
                        return parsed_result
                    except json.JSONDecodeError:
                        # Not valid JSON, return as-is
                        print(f"  ✅ Function executed successfully")
                        return result
                else:
                    # result is already parsed
                    print(f"  ✅ Function executed successfully")
                    return result_value
            
            print(f"  ✅ Function executed successfully")
            return result
            
        except httpx.ConnectError as e:
            print(f"  ❌ Cannot connect to function registry at localhost:9999: {e}")
            return {
                "error": f"Function registry not available at localhost:9999",
                "message": "Cannot connect to the function registry service. Please ensure it's running.",
                "function": function_name,
                "action_required": "Start the function registry service at localhost:9999 or use http_request for direct API calls"
            }
        
        except httpx.HTTPStatusError as e:
            print(f"  ❌ HTTP error calling function registry: {e.response.status_code}")
            error_detail = e.response.text
            return {
                "error": f"Function '{function_name}' execution failed",
                "status_code": e.response.status_code,
                "detail": error_detail,
                "function": function_name
            }
        
        except Exception as e:
            print(f"  ❌ Error calling function registry: {e}")
            return {
                "error": f"Function '{function_name}' execution failed: {str(e)}",
                "function": function_name
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
            # If evaluation fails, raise the error - don't use mock data
            print(f"  ❌ Transform expression evaluation failed: {type(e).__name__}: {str(e)}")
            raise RuntimeError(f"Transform expression evaluation failed: {str(e)}. Please check your expression syntax and ensure all variables are available.")


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

