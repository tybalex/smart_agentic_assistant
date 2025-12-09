"""
Auto-discovery of functions from the functions module
No manual registry needed!
"""
import inspect
from typing import get_type_hints, Dict, Any, Callable, Optional, List, Union, get_origin, get_args
from pydantic import create_model, Field
from functions import FUNCTION_MAP


def format_type_name(type_obj) -> str:
    """Format a type object into a clean string representation"""
    if type_obj is Any:
        return "any"
    
    # Handle None type
    if type_obj is type(None):
        return "null"
    
    # Get origin for generic types (List, Dict, Optional, etc.)
    origin = get_origin(type_obj)
    
    if origin is Union:
        # Handle Optional[T] which is Union[T, None]
        args = get_args(type_obj)
        if len(args) == 2 and type(None) in args:
            # This is Optional[T]
            other_type = args[0] if args[1] is type(None) else args[1]
            return format_type_name(other_type)
        # Other unions
        return "union[" + ", ".join(format_type_name(arg) for arg in args) + "]"
    
    if origin is list or origin is List:
        args = get_args(type_obj)
        if args:
            return f"list[{format_type_name(args[0])}]"
        return "list"
    
    if origin is dict or origin is Dict:
        args = get_args(type_obj)
        if args and len(args) == 2:
            return f"dict[{format_type_name(args[0])}, {format_type_name(args[1])}]"
        return "dict"
    
    # Handle basic types
    if hasattr(type_obj, '__name__'):
        return type_obj.__name__
    
    # Fallback
    return str(type_obj).replace("<class '", "").replace("'>", "")


def get_function_metadata(func: Callable) -> Dict[str, Any]:
    """Extract metadata from a function"""
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    # Get category from module name
    module = func.__module__
    category = module.split('.')[-1] if '.' in module else 'general'
    
    # Get parameters
    parameters = {}
    required_params = []
    
    for param_name, param in sig.parameters.items():
        param_type = type_hints.get(param_name, Any)
        has_default = param.default != inspect.Parameter.empty
        
        parameters[param_name] = {
            'type': param_type,
            'required': not has_default,
            'default': param.default if has_default else None
        }
        
        if not has_default:
            required_params.append(param_name)
    
    # Get description from docstring
    doc = inspect.getdoc(func) or f"Execute {func.__name__}"
    
    # Extract everything before Args/Returns/etc sections
    lines = doc.split('\n')
    description_lines = []
    for line in lines:
        stripped = line.strip()
        # Stop at section headers (these start lines, often followed by :)
        if stripped and (
            stripped.upper().startswith(('ARGS:', 'ARGUMENTS:', 'PARAMETERS:', 'PARAMS:')) or
            stripped.upper().startswith(('RETURNS:', 'RETURN:', 'YIELDS:', 'YIELD:')) or
            stripped.upper().startswith(('RAISES:', 'RAISE:', 'EXCEPT:', 'EXCEPTIONS:')) or
            stripped.upper().startswith(('EXAMPLES:', 'EXAMPLE:', 'NOTE:', 'NOTES:', 'WARNING:', 'WARNINGS:'))
        ):
            break
        if stripped:  # Only add non-empty lines
            description_lines.append(stripped)
    
    description = ' '.join(description_lines) if description_lines else lines[0]
    
    return {
        'name': func.__name__,
        'description': description,
        'category': category,
        'parameters': parameters,
        'required_params': required_params,
        'function': func
    }


def create_pydantic_model_for_function(func_name: str, metadata: Dict[str, Any]):
    """Create a Pydantic model from function metadata"""
    fields = {}
    
    for param_name, param_info in metadata['parameters'].items():
        param_type = param_info['type']
        is_required = param_info['required']
        default_value = param_info['default']
        
        if is_required:
            # Required field
            fields[param_name] = (param_type, Field(..., description=f"Required parameter"))
        else:
            # Optional field with default
            if default_value is None:
                fields[param_name] = (Optional[param_type], None)
            else:
                fields[param_name] = (param_type, default_value)
    
    # Create model with proper name
    model_name = f"{func_name.title().replace('_', '')}Request"
    return create_model(model_name, **fields)


# Auto-discover all functions
DISCOVERED_FUNCTIONS = {}

for func_name, func in FUNCTION_MAP.items():
    metadata = get_function_metadata(func)
    pydantic_model = create_pydantic_model_for_function(func_name, metadata)
    
    DISCOVERED_FUNCTIONS[func_name] = {
        **metadata,
        'request_model': pydantic_model
    }


def get_all_functions() -> List[Dict[str, Any]]:
    """Get list of all discovered functions"""
    return [
        {
            'name': name,
            'description': info['description'],
            'category': info['category'],
            'parameters': {
                k: {
                    'type': format_type_name(v['type']),
                    'required': v['required'],
                    'default': v['default']
                }
                for k, v in info['parameters'].items()
            }
        }
        for name, info in DISCOVERED_FUNCTIONS.items()
    ]


def get_function_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Get function metadata by name"""
    return DISCOVERED_FUNCTIONS.get(name)


def get_functions_by_category(category: str) -> List[Dict[str, Any]]:
    """Get all functions in a category"""
    return [
        {
            'name': name,
            'description': info['description'],
            'category': info['category'],
            'parameters': {
                k: {
                    'type': format_type_name(v['type']),
                    'required': v['required'],
                    'default': v['default']
                }
                for k, v in info['parameters'].items()
            }
        }
        for name, info in DISCOVERED_FUNCTIONS.items()
        if info['category'] == category
    ]


def get_all_categories() -> List[str]:
    """Get all unique categories"""
    return sorted(set(info['category'] for info in DISCOVERED_FUNCTIONS.values()))


def search_functions(query: str) -> List[Dict[str, Any]]:
    """Search functions by name or description
    
    Splits query into words and matches if ALL words are found
    in either the function name or description.
    """
    # Split query into words and normalize
    query_words = query.lower().split()
    results = []
    
    for name, info in DISCOVERED_FUNCTIONS.items():
        # Create searchable text from name (replace underscores with spaces) and description
        name_text = name.lower().replace('_', ' ')
        desc_text = info['description'].lower()
        searchable = f"{name_text} {desc_text}"
        
        # Check if ALL query words are present
        if all(word in searchable for word in query_words):
            results.append({
                'name': name,
                'description': info['description'],
                'category': info['category'],
                'parameters': {
                    k: {
                        'type': format_type_name(v['type']),
                        'required': v['required'],
                        'default': v['default']
                    }
                    for k, v in info['parameters'].items()
                }
            })
    
    return results

