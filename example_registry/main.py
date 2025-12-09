"""
FastAPI application with auto-discovered, strongly-typed endpoints
No manual registry needed - functions are discovered automatically!
"""
from fastapi import FastAPI, HTTPException
from typing import Any, Dict
from function_discovery import (
    DISCOVERED_FUNCTIONS,
    get_all_functions,
    get_function_by_name,
    get_functions_by_category,
    get_all_categories,
    search_functions,
    format_type_name
)

app = FastAPI(
    title="Function Call Registry",
    description="Auto-discovered function registry with strongly-typed endpoints",
    version="2.0.0"
)


@app.get("/")
async def root():
    """API overview"""
    return {
        "message": "Function Call Registry API v2.0",
        "total_functions": len(DISCOVERED_FUNCTIONS),
        "total_categories": len(get_all_categories()),
        "features": [
            "Auto-discovered functions (no manual registry)",
            "Strongly-typed parameters",
            "Each function has its own endpoint",
            "Full OpenAPI documentation"
        ],
        "endpoints": {
            "list_all": "/functions",
            "get_function": "/functions/{function_name}",
            "by_category": "/functions/category/{category}",
            "categories": "/categories",
            "search": "/functions/search?q={query}",
            "execute": "/{category}/{function_name}"
        },
        "docs": "/docs"
    }


@app.get("/functions")
async def list_functions():
    """List all available functions"""
    return {
        "functions": get_all_functions(),
        "total": len(DISCOVERED_FUNCTIONS)
    }


@app.get("/search")
async def search_functions_endpoint(q: str):
    """Search functions by name or description"""
    results = search_functions(q)
    return {"results": results, "total": len(results), "query": q}


@app.get("/functions/category/{category}")
async def get_category_functions(category: str):
    """Get all functions in a category"""
    functions = get_functions_by_category(category)
    if not functions:
        raise HTTPException(404, f"No functions found in category '{category}'")
    return {"functions": functions, "total": len(functions)}


@app.get("/functions/{function_name}")
async def get_function_info(function_name: str):
    """Get detailed information about a specific function"""
    func_info = get_function_by_name(function_name)
    if not func_info:
        raise HTTPException(404, f"Function '{function_name}' not found")
    
    return {
        "name": func_info['name'],
        "description": func_info['description'],
        "category": func_info['category'],
        "parameters": {
            k: {
                'type': format_type_name(v['type']),
                'required': v['required'],
                'default': v['default']
            }
            for k, v in func_info['parameters'].items()
        }
    }


@app.get("/categories")
async def list_categories():
    """Get all function categories"""
    return {"categories": get_all_categories()}


# Auto-generate strongly-typed endpoints for each function
for func_name, func_info in DISCOVERED_FUNCTIONS.items():
    request_model = func_info['request_model']
    func = func_info['function']
    category = func_info['category']
    description = func_info['description']
    
    # Create endpoint path
    endpoint_path = f"/{category}/{func_name}"
    
    # Create the endpoint function with proper typing
    def create_endpoint(fn=func, fn_name=func_name, req_model=request_model):
        async def endpoint(request: req_model) -> Dict[str, Any]:
            """
            Execute the function with validated parameters
            """
            try:
                # Convert Pydantic model to dict and call function
                params = request.dict(exclude_none=True)
                result = fn(**params)
                
                # Try to parse result as JSON to check for inner success field
                try:
                    import json
                    result_dict = json.loads(result)
                    if isinstance(result_dict, dict) and "success" in result_dict:
                        # Use the inner success status
                        return {
                            "function_name": fn_name,
                            "result": result,
                            "success": result_dict["success"]
                        }
                except (json.JSONDecodeError, TypeError):
                    pass
                
                # Default to success if no inner success field
                return {
                    "function_name": fn_name,
                    "result": result,
                    "success": True
                }
            except Exception as e:
                return {
                    "function_name": fn_name,
                    "result": None,
                    "success": False,
                    "error": str(e)
                }
        
        # Set proper metadata
        endpoint.__name__ = fn_name
        endpoint.__doc__ = description
        return endpoint
    
    # Register the endpoint
    app.post(
        endpoint_path,
        summary=description,
        tags=[category],
        name=func_name
    )(create_endpoint())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9999)

