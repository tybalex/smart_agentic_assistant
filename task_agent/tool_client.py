"""
Client for the external Tool Registry API.
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

from constant import DEFAULT_TOOL_REGISTRY_URL

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
            
            # Validate and extract success field (default to False if missing)
            if "success" not in result_data:
                logger.warning(f"Response missing 'success' field: {result_data}")
                success_value = None
            else:
                success_value = result_data.get("success")
            if "result" in result_data:
                inner_result = result_data["result"]
                
                # If result is a JSON string, parse it
                if isinstance(inner_result, str):
                    try:
                        inner_result = json.loads(inner_result)
                    except json.JSONDecodeError:
                        # Not JSON, keep as string
                        pass
                
                # If inner result is a dict, merge it with success status
                if isinstance(inner_result, dict):
                    unwrapped = {"success": success_value}
                    unwrapped.update(inner_result)
                    logger.info(f"Function executed, success={success_value}, unwrapped nested result")
                    return unwrapped
                else:
                    # Inner result is not a dict (string, list, etc.), return as-is with success
                    logger.info(f"Function executed, success={success_value}, result is non-dict type")
                    return {
                        "success": success_value,
                        "result": inner_result
                    }
            
            # No nested result field, return response as-is (removing function_name if present)
            cleaned_result = {"success": success_value}
            for k, v in result_data.items():
                if k not in ("success", "function_name"):
                    cleaned_result[k] = v
            
            logger.info(f"Function executed, success={success_value}")
            return cleaned_result
            
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
        Get a HIGH-LEVEL summary of the tool registry.
        Does NOT include individual function details - agent should use
        registry discovery tools to find specific functions.
        """
        categories = self.list_categories()
        
        # Get total count without loading all details
        try:
            response = self.client.get(f"{self.base_url}/functions")
            response.raise_for_status()
            data = response.json()
            total_count = data.get("total", len(data.get("functions", [])))
        except Exception:
            total_count = "unknown"
        
        summary = f"""TOOL REGISTRY OVERVIEW:
Total Functions: {total_count}
Categories: {', '.join(categories) if categories else 'N/A'}

TO DISCOVER FUNCTIONS, use these registry tools:

[registry] - Meta-tools for discovering available functions
  - registry_search: Search functions by keyword
      Parameters: q: str (required) - search query
      Example: {{"q": "slack message"}} → finds slack_send_message, etc.
  
  - registry_list_category: List all functions in a category  
      Parameters: category: str (required)
      Example: {{"category": "salesforce"}} → lists all Salesforce functions
  
  - registry_get_function: Get full details of a specific function
      Parameters: function_name: str (required)
      Example: {{"function_name": "slack_send_message"}} → returns params, description

WORKFLOW:
1. Use registry_search or registry_list_category to find relevant functions
2. Use registry_get_function to get exact parameter names before calling
3. Then call the actual function with correct parameters"""
        
        return summary
    
    # ===================
    # Registry Discovery Tools (meta-tools for agent)
    # ===================
    
    def registry_search(self, q: str) -> Dict[str, Any]:
        """
        Search for functions by keyword.
        Returns matching functions with their details.
        """
        logger.info(f"Registry search: q={q}")
        try:
            response = self.client.get(f"{self.base_url}/search", params={"q": q})
            response.raise_for_status()
            data = response.json()
            logger.info(f"Search returned {data.get('total', 0)} results")
            return {
                "success": True,
                "result": data
            }
        except Exception as e:
            logger.error(f"Registry search failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def registry_list_category(self, category: str) -> Dict[str, Any]:
        """
        List all functions in a specific category.
        """
        logger.info(f"Registry list category: {category}")
        try:
            response = self.client.get(f"{self.base_url}/functions/category/{category}")
            response.raise_for_status()
            data = response.json()
            logger.info(f"Category {category} has {data.get('total', 0)} functions")
            return {
                "success": True,
                "result": data
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Category not found: {category}")
            return {
                "success": False,
                "error": f"Category '{category}' not found"
            }
        except Exception as e:
            logger.error(f"Registry list category failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def registry_get_function(self, function_name: str) -> Dict[str, Any]:
        """
        Get full details of a specific function including parameters.
        """
        logger.info(f"Registry get function: {function_name}")
        try:
            response = self.client.get(f"{self.base_url}/functions/{function_name}")
            response.raise_for_status()
            data = response.json()
            logger.info(f"Got details for function: {function_name}")
            return {
                "success": True,
                "result": data
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"Function not found: {function_name}")
            return {
                "success": False,
                "error": f"Function '{function_name}' not found"
            }
        except Exception as e:
            logger.error(f"Registry get function failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
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
def get_tool_client(base_url: str = DEFAULT_TOOL_REGISTRY_URL) -> ToolRegistryClient:
    """Create and return a tool registry client."""
    return ToolRegistryClient(base_url)


if __name__ == "__main__":
    # Quick test of the client
    client = ToolRegistryClient()
    print("Health Check:", client.health_check())
    print("\nCategories:", client.list_categories())
    print("\nTools Summary:")
    print(client.get_tools_summary())

