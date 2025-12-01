"""
Workflow file loader utilities
"""

import yaml
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.schema import WorkflowDefinition


def find_workflow_files(directory: str = ".") -> List[str]:
    """
    Find all workflow YAML files in the given directory.
    
    Args:
        directory: Directory to search in
        
    Returns:
        List of workflow file paths
    """
    path = Path(directory)
    workflow_files = []
    
    # Look for .yaml and .yml files
    for pattern in ["*.yaml", "*.yml"]:
        workflow_files.extend(path.glob(pattern))
    
    return [str(f) for f in sorted(workflow_files)]


def load_workflow_file(filepath: str) -> Optional[WorkflowDefinition]:
    """
    Load and validate a workflow file.
    
    Args:
        filepath: Path to the workflow file
        
    Returns:
        WorkflowDefinition if successful, None if failed
    """
    try:
        with open(filepath, 'r') as f:
            if filepath.endswith('.json'):
                data = json.load(f)
            else:
                data = yaml.safe_load(f)
        
        # Validate with Pydantic
        workflow = WorkflowDefinition.model_validate(data)
        return workflow
        
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"Error loading workflow: {e}")
        return None


def get_workflow_summary(workflow: WorkflowDefinition) -> Dict[str, Any]:
    """
    Get a summary of workflow metadata.
    
    Args:
        workflow: WorkflowDefinition instance
        
    Returns:
        Dictionary with summary information
    """
    return {
        "name": workflow.metadata.name,
        "description": workflow.metadata.description or "No description",
        "version": workflow.metadata.version,
        "total_nodes": len(workflow.nodes),
        "node_types": list(set(node.type for node in workflow.nodes)),
        "has_variables": len(workflow.variables) > 0,
        "variable_count": len(workflow.variables),
    }

