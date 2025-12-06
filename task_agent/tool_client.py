"""
Client for the external Tool Registry API at localhost:9999.
Provides methods to list, search, and execute tools.
"""

import os
import json
import logging
import httpx
from typing import List, Dict, Any, Optional
from models import ToolInfo

# Configure logging
logger = logging.getLogger(__name__)

# Default URL, can be overridden by environment variable (useful for Docker)
DEFAULT_TOOL_REGISTRY_URL = os.environ.get("TOOL_REGISTRY_URL", "http://localhost:9999")


class ToolRegistryClient:
    """
    Client for interacting with the Function Call Registry API.
    
    API Endpoints:
    - /functions - List all functions
    - /functions/{function_name} - Get specific function details
    - /functions/category/{category} - Get functions by category
    - /categories - List all categories
    - /functions/search?q={query} - Search functions
    - /{category}/{function_name} - Execute a function
    """
    
    def __init__(self, base_url: str = DEFAULT_TOOL_REGISTRY_URL):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=30.0)
    
    def health_check(self) -> Dict[str, Any]:
        """Check if the API is available and get basic info."""
        try:
            response = self.client.get(self.base_url)
            response.raise_for_status()
            return {"status": "healthy", "info": response.json()}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
    def list_all_functions(self, with_details: bool = False) -> List[Dict[str, Any]]:
        """
        List all available functions.
        
        Args:
            with_details: If True, fetch full details for each function.
                         If False, return basic info from /functions endpoint.
        """
        try:
            response = self.client.get(f"{self.base_url}/functions")
            response.raise_for_status()
            data = response.json()
            
            # Handle case where API returns list of names (strings)
            if data and isinstance(data, list) and isinstance(data[0], str):
                if with_details:
                    # Fetch details for each function
                    functions = []
                    for name in data:
                        func_details = self.get_function(name)
                        if func_details:
                            functions.append(func_details)
                    return functions
                else:
                    # Return basic structure with just names
                    return [{"name": name} for name in data]
            
            # Handle case where API returns dict with functions key
            if isinstance(data, dict):
                functions = data.get("functions", [])
                if functions and isinstance(functions[0], str):
                    return [{"name": name} for name in functions]
                return functions
            
            # Already a list of dicts
            return data
        except Exception as e:
            print(f"Error listing functions: {e}")
            return []
    
    def get_function(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Get details about a specific function."""
        try:
            response = self.client.get(f"{self.base_url}/functions/{function_name}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error getting function {function_name}: {e}")
            return None
    
    def list_categories(self) -> List[str]:
        """List all available categories."""
        try:
            response = self.client.get(f"{self.base_url}/categories")
            response.raise_for_status()
            data = response.json()
            # Handle both list response and dict with categories key
            if isinstance(data, list):
                return data
            return data.get("categories", [])
        except Exception as e:
            print(f"Error listing categories: {e}")
            return []
    
    def get_functions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all functions in a specific category."""
        try:
            response = self.client.get(f"{self.base_url}/functions/category/{category}")
            response.raise_for_status()
            data = response.json()
            
            # Handle dict response with functions key
            if isinstance(data, dict):
                data = data.get("functions", [])
            
            return data
        except Exception as e:
            print(f"Error getting functions for category {category}: {e}")
            return []
    
    def search_functions(self, query: str) -> List[Dict[str, Any]]:
        """Search for functions by query string."""
        try:
            response = self.client.get(
                f"{self.base_url}/functions/search",
                params={"q": query}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error searching functions: {e}")
            return []
    
    def execute_function(
        self, 
        category: str, 
        function_name: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a function with the given parameters.
        
        Args:
            category: The function's category
            function_name: The name of the function
            params: Parameters to pass to the function
            
        Returns:
            Dict containing the result or error.
            Success is determined by:
            - HTTP 200 response
            - Response is valid JSON
            - JSON has "success" field set to true
        """
        url = f"{self.base_url}/{category}/{function_name}"
        logger.info(f"Executing function: {category}/{function_name}")
        logger.info(f"Parameters: {json.dumps(params or {})}")
        
        try:
            # Always send a JSON body (API requires it even for no-param functions)
            response = self.client.post(url, json=params or {})
            
            # Log raw response
            logger.info(f"HTTP Status: {response.status_code}")
            logger.info(f"Raw response: {response.text[:1000]}")  # Limit to 1000 chars
            
            # Check HTTP status
            response.raise_for_status()
            
            # Try to parse JSON
            try:
                result_data = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Response is not valid JSON: {e}")
                return {
                    "success": False,
                    "error": f"Invalid JSON response: {response.text[:200]}",
                    "raw_response": response.text
                }
            
            # Check for "success" field in the response
            if "success" not in result_data:
                logger.warning(f"Response missing 'success' field: {result_data}")
                return {
                    "success": False,
                    "error": "Response missing 'success' field",
                    "result": result_data
                }
            
            # Check if success is true
            if not result_data.get("success"):
                error_msg = result_data.get("error", result_data.get("message", "Unknown error"))
                logger.error(f"Function returned success=false: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "result": result_data
                }
            
            # Success!
            logger.info(f"Function executed successfully")
            return {
                "success": True,
                "result": result_data
            }
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}"
            }
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_tools_summary(self) -> str:
        """
        Get a formatted summary of all available tools.
        Useful for providing context to the AI agent.
        Includes parameter details so the agent knows exact field names.
        """
        categories = self.list_categories()
        
        summary_parts = [
            "Available Tools Summary:",
            f"Categories: {', '.join(categories) if categories else 'N/A'}",
            "",
            "Functions by Category:"
        ]
        
        # Get functions by category for better organization
        total_count = 0
        for cat in categories:
            funcs = self.get_functions_by_category(cat)
            if funcs:
                summary_parts.append(f"\n[{cat}]")
                for func in funcs:
                    # Handle both dict and string responses
                    func_name = func if isinstance(func, str) else func.get("name", "unknown")
                    
                    # Fetch full details to get parameters
                    func_details = self.get_function(func_name)
                    
                    if func_details:
                        name = func_details.get("name", func_name)
                        desc = func_details.get("description", "No description")
                        params = func_details.get("parameters", {})
                        
                        # Truncate long descriptions
                        if len(desc) > 100:
                            desc = desc[:97] + "..."
                        
                        summary_parts.append(f"  - {name}: {desc}")
                        
                        # Add parameter details
                        if params:
                            param_strs = []
                            for param_name, param_info in params.items():
                                if isinstance(param_info, dict):
                                    param_type = param_info.get("type", "any")
                                    required = param_info.get("required", False)
                                    req_str = " (required)" if required else ""
                                    param_strs.append(f"{param_name}: {param_type}{req_str}")
                                else:
                                    param_strs.append(f"{param_name}")
                            if param_strs:
                                summary_parts.append(f"      Parameters: {', '.join(param_strs)}")
                    else:
                        summary_parts.append(f"  - {func_name}")
                    
                    total_count += 1
        
        # Insert total count at the beginning
        summary_parts.insert(1, f"Total Functions: {total_count}")
        
        return "\n".join(summary_parts)
    
    def get_tools_for_agent(self) -> List[ToolInfo]:
        """
        Get tools formatted for the AI agent to understand and use.
        """
        tools = []
        categories = self.list_categories()
        
        for cat in categories:
            funcs = self.get_functions_by_category(cat)
            for func in funcs:
                # Handle both dict and string responses
                if isinstance(func, str):
                    # Fetch full details
                    func_details = self.get_function(func)
                    if func_details:
                        func = func_details
                    else:
                        func = {"name": func, "category": cat}
                
                tool = ToolInfo(
                    name=func.get("name", "unknown"),
                    category=func.get("category", cat),
                    description=func.get("description", ""),
                    parameters=func.get("parameters", {})
                )
                tools.append(tool)
        
        return tools
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience function for quick tool lookup
def get_tool_client(base_url: str = "http://localhost:9999") -> ToolRegistryClient:
    """Create and return a tool registry client."""
    return ToolRegistryClient(base_url)


if __name__ == "__main__":
    # Quick test of the client
    client = ToolRegistryClient()
    print("Health Check:", client.health_check())
    print("\nCategories:", client.list_categories())
    print("\nTools Summary:")
    print(client.get_tools_summary())

