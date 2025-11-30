"""
Agent Tools

Tools that the workflow agent can use to manipulate and test workflows.
Each tool is a function the LLM can call.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio

from ..schema import WorkflowDefinition, WorkflowNode
from ..runtime import SimpleWorkflowExecutor


class WorkflowTools:
    """Collection of tools the agent can use"""
    
    def __init__(self, workspace_dir: str = "."):
        self.workspace_dir = Path(workspace_dir)
        self._executor = None  # Lazy initialization to avoid circular imports
        self.current_workflow: Optional[WorkflowDefinition] = None
        self.last_execution_result = None
    
    @property
    def executor(self):
        """Lazy initialization of executor to avoid circular imports"""
        if self._executor is None:
            self._executor = SimpleWorkflowExecutor()
        return self._executor
    
    # ==================== Workflow Management Tools ====================
    
    def write_workflow(self, workflow_data: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """
        Create or overwrite a workflow file.
        
        Args:
            workflow_data: The complete workflow definition as a dictionary
            filename: Name of the file to save (e.g., "my_workflow.yaml")
        
        Returns:
            Dictionary with status and path
        """
        try:
            # Validate the workflow
            workflow = WorkflowDefinition.model_validate(workflow_data)
            
            # Save to file
            filepath = self.workspace_dir / filename
            with open(filepath, 'w') as f:
                yaml.dump(workflow_data, f, default_flow_style=False, sort_keys=False)
            
            # Store as current workflow
            self.current_workflow = workflow
            
            return {
                "status": "success",
                "message": f"Workflow saved to {filename}",
                "path": str(filepath),
                "nodes": len(workflow.nodes)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def read_workflow(self, filename: str) -> Dict[str, Any]:
        """
        Read a workflow file and return its contents.
        
        Args:
            filename: Name of the workflow file
        
        Returns:
            Dictionary with workflow data or error
        """
        try:
            filepath = self.workspace_dir / filename
            with open(filepath, 'r') as f:
                if filename.endswith('.yaml') or filename.endswith('.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
            
            # Validate and store
            workflow = WorkflowDefinition.model_validate(data)
            self.current_workflow = workflow
            
            return {
                "status": "success",
                "workflow": data,
                "summary": {
                    "name": workflow.metadata.name,
                    "nodes": len(workflow.nodes),
                    "node_ids": [n.id for n in workflow.nodes]
                }
            }
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"File not found: {filename}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def update_node(self, node_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a specific node in the current workflow.
        
        Args:
            node_id: ID of the node to update
            updates: Dictionary of fields to update
        
        Returns:
            Status and updated node info
        """
        if not self.current_workflow:
            return {
                "status": "error",
                "message": "No workflow loaded. Use read_workflow or write_workflow first."
            }
        
        try:
            # Find the node
            node = self.current_workflow.get_node(node_id)
            if not node:
                return {
                    "status": "error",
                    "message": f"Node '{node_id}' not found in workflow"
                }
            
            # Update the node
            for key, value in updates.items():
                if hasattr(node, key):
                    setattr(node, key, value)
            
            return {
                "status": "success",
                "message": f"Updated node '{node_id}'",
                "node": node.model_dump()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def add_node(self, node_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new node to the current workflow.
        
        Args:
            node_data: Node definition as dictionary
        
        Returns:
            Status and node info
        """
        if not self.current_workflow:
            return {
                "status": "error",
                "message": "No workflow loaded. Use read_workflow or write_workflow first."
            }
        
        try:
            # Validate the node
            node = WorkflowNode.model_validate(node_data)
            
            # Check for duplicate ID
            if self.current_workflow.get_node(node.id):
                return {
                    "status": "error",
                    "message": f"Node with ID '{node.id}' already exists"
                }
            
            # Add the node
            self.current_workflow.nodes.append(node)
            
            return {
                "status": "success",
                "message": f"Added node '{node.id}'",
                "node": node.model_dump()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def remove_node(self, node_id: str) -> Dict[str, Any]:
        """
        Remove a node from the current workflow.
        
        Args:
            node_id: ID of the node to remove
        
        Returns:
            Status message
        """
        if not self.current_workflow:
            return {
                "status": "error",
                "message": "No workflow loaded."
            }
        
        # Find and remove the node
        original_count = len(self.current_workflow.nodes)
        self.current_workflow.nodes = [
            n for n in self.current_workflow.nodes if n.id != node_id
        ]
        
        if len(self.current_workflow.nodes) == original_count:
            return {
                "status": "error",
                "message": f"Node '{node_id}' not found"
            }
        
        return {
            "status": "success",
            "message": f"Removed node '{node_id}'"
        }
    
    def list_nodes(self) -> Dict[str, Any]:
        """
        List all nodes in the current workflow.
        
        Returns:
            List of nodes with their details
        """
        if not self.current_workflow:
            return {
                "status": "error",
                "message": "No workflow loaded."
            }
        
        nodes_info = []
        for node in self.current_workflow.nodes:
            nodes_info.append({
                "id": node.id,
                "type": node.type,
                "description": node.description,
                "depends_on": node.depends_on
            })
        
        return {
            "status": "success",
            "workflow_name": self.current_workflow.metadata.name,
            "nodes": nodes_info,
            "total": len(nodes_info)
        }
    
    # ==================== Execution & Testing Tools ====================
    
    def run_workflow(self, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the current workflow.
        
        Args:
            variables: Optional runtime variables
        
        Returns:
            Execution results
        """
        if not self.current_workflow:
            return {
                "status": "error",
                "message": "No workflow loaded."
            }
        
        try:
            # Run async execution
            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(
                self.executor.execute(self.current_workflow, variables)
            )
            
            # Store result
            self.last_execution_result = result
            
            # Format results for agent
            node_results = {}
            for node_id, node_result in result.node_results.items():
                node_results[node_id] = {
                    "status": node_result.status,
                    "execution_time": node_result.execution_time,
                    "error": node_result.error,
                    "output": str(node_result.output)[:500] if node_result.output else None  # Truncate long outputs
                }
            
            return {
                "status": "success",
                "workflow_status": result.status,
                "duration": result.total_duration,
                "node_results": node_results
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Execution failed: {str(e)}"
            }
    
    def validate_workflow(self) -> Dict[str, Any]:
        """
        Validate the current workflow without executing it.
        
        Returns:
            Validation results
        """
        if not self.current_workflow:
            return {
                "status": "error",
                "message": "No workflow loaded."
            }
        
        try:
            # Run validation
            loop = asyncio.get_event_loop()
            validation = loop.run_until_complete(
                self.executor.validate(self.current_workflow)
            )
            
            return {
                "status": "success",
                "is_valid": validation["is_valid"],
                "errors": validation["errors"],
                "warnings": validation["warnings"]
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current workflow.
        
        Returns:
            Workflow summary
        """
        if not self.current_workflow:
            return {
                "status": "error",
                "message": "No workflow loaded."
            }
        
        return {
            "status": "success",
            "name": self.current_workflow.metadata.name,
            "description": self.current_workflow.metadata.description,
            "version": self.current_workflow.metadata.version,
            "total_nodes": len(self.current_workflow.nodes),
            "node_types": list({node.type for node in self.current_workflow.nodes}),  # Convert set to list
            "variables": self.current_workflow.variables,
            "execution_order": [n.id for n in self.current_workflow.topological_sort()]
        }
    
    def get_last_execution_result(self) -> Dict[str, Any]:
        """
        Get the results from the last workflow execution.
        
        Returns:
            Last execution results or error if no execution yet
        """
        if not self.last_execution_result:
            return {
                "status": "error",
                "message": "No execution results available. Run the workflow first."
            }
        
        # Format results
        node_results = {}
        for node_id, node_result in self.last_execution_result.node_results.items():
            node_results[node_id] = {
                "status": node_result.status,
                "execution_time": node_result.execution_time,
                "error": node_result.error,
                "output": str(node_result.output)[:1000] if node_result.output else None
            }
        
        return {
            "status": "success",
            "workflow_status": self.last_execution_result.status,
            "duration": self.last_execution_result.total_duration,
            "node_results": node_results
        }
    
    # ==================== Function Registry Tools ====================
    
    def list_function_registry(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List available functions from the functions registry.
        
        Args:
            category: Filter by category (e.g., 'google', 'aws', 'notion')
            status: Filter by status ('implemented', 'mock', 'todo')
            search: Search term to filter functions by name or description
        
        Returns:
            List of functions with their details
        """
        import httpx
        
        try:
            # Build query parameters
            params = {}
            if category:
                params['category'] = category
            if status:
                params['status'] = status
            if search:
                params['search'] = search
            
            # Make request to localhost:9999
            response = httpx.get(
                "http://localhost:9999/functions",
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            
            # Parse the response
            data = response.json()
            
            return {
                "status": "success",
                "total_functions": data.get("total_functions", len(data.get("functions", []))),
                "available_categories": data.get("available_categories", []),
                "functions": data.get("functions", [])
            }
        except httpx.HTTPError as e:
            return {
                "status": "error",
                "message": f"HTTP error while fetching functions: {str(e)}"
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to list functions: {str(e)}"
            }


# Tool definitions for Anthropic API
TOOL_DEFINITIONS = [
    {
        "name": "write_workflow",
        "description": "Create or overwrite a complete workflow file. Use this when generating a new workflow from user requirements.",
        "input_schema": {
            "type": "object",
            "properties": {
                "workflow_data": {
                    "type": "object",
                    "description": "The complete workflow definition with metadata and nodes"
                },
                "filename": {
                    "type": "string",
                    "description": "Filename to save the workflow (e.g., 'customer_onboarding.yaml')"
                }
            },
            "required": ["workflow_data", "filename"]
        }
    },
    {
        "name": "read_workflow",
        "description": "Read an existing workflow file to see its current contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Name of the workflow file to read"
                }
            },
            "required": ["filename"]
        }
    },
    {
        "name": "update_node",
        "description": "Update a specific node in the current workflow. Use this to modify node configuration, dependencies, or other properties.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "ID of the node to update"
                },
                "updates": {
                    "type": "object",
                    "description": "Dictionary of fields to update (e.g., {'config': {...}, 'depends_on': [...]})"
                }
            },
            "required": ["node_id", "updates"]
        }
    },
    {
        "name": "add_node",
        "description": "Add a new node to the current workflow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_data": {
                    "type": "object",
                    "description": "Complete node definition with id, type, config, etc."
                }
            },
            "required": ["node_data"]
        }
    },
    {
        "name": "remove_node",
        "description": "Remove a node from the current workflow.",
        "input_schema": {
            "type": "object",
            "properties": {
                "node_id": {
                    "type": "string",
                    "description": "ID of the node to remove"
                }
            },
            "required": ["node_id"]
        }
    },
    {
        "name": "list_nodes",
        "description": "List all nodes in the current workflow to see what's there.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "run_workflow",
        "description": "Execute the current workflow and get results. Use this to test if the workflow works.",
        "input_schema": {
            "type": "object",
            "properties": {
                "variables": {
                    "type": "object",
                    "description": "Optional runtime variables to pass to the workflow"
                }
            },
            "required": []
        }
    },
    {
        "name": "validate_workflow",
        "description": "Validate the workflow structure without running it. Checks for dependency errors, circular dependencies, etc.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_workflow_summary",
        "description": "Get a high-level summary of the current workflow.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_last_execution_result",
        "description": "Get the results from the last workflow execution to see what succeeded or failed.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_function_registry",
        "description": "List available functions from the functions registry. Use this to discover what functions are available for use in workflows. You can filter by category, status, or search term.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Filter by category (e.g., 'google', 'aws', 'notion', 'slack', 'github')"
                },
                "status": {
                    "type": "string",
                    "description": "Filter by status: 'implemented', 'mock', or 'todo'",
                    "enum": ["implemented", "mock", "todo"]
                },
                "search": {
                    "type": "string",
                    "description": "Search term to filter functions by name or description"
                }
            },
            "required": []
        }
    }
]

