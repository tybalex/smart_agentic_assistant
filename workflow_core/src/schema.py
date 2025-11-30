"""
Workflow Schema Definition

This is the AI-friendly schema that LLMs will read and write.
Keep it simple, intuitive, and easy to understand.
"""

from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field


class NodeConfig(BaseModel):
    """Configuration for a workflow node - intentionally flexible"""
    model_config = {"extra": "allow"}  # Allow arbitrary fields
    

class WorkflowNode(BaseModel):
    """
    A single step/node in the workflow.
    
    Example:
        {
            "id": "validate_email",
            "type": "api_call",
            "description": "Validate user email address",
            "config": {
                "url": "https://api.validator.com/email",
                "method": "POST",
                "input": "{{user.email}}"
            },
            "depends_on": [],
            "retry": {"max_attempts": 3, "backoff": "exponential"}
        }
    """
    id: str = Field(..., description="Unique identifier for this node")
    type: str = Field(..., description="Node type (api_call, transform, condition, human_review, etc)")
    description: Optional[str] = Field(None, description="Human-readable description")
    
    config: Dict[str, Any] = Field(default_factory=dict, description="Node-specific configuration")
    
    depends_on: List[str] = Field(default_factory=list, description="IDs of nodes that must complete before this one")
    condition: Optional[str] = Field(None, description="Expression to determine if node should execute")
    
    retry: Optional[Dict[str, Any]] = Field(None, description="Retry configuration")
    timeout: Optional[int] = Field(None, description="Timeout in seconds")
    
    on_error: Optional[str] = Field(None, description="Error handling strategy (fail, continue, retry)")


class WorkflowMetadata(BaseModel):
    """Metadata about the workflow"""
    name: str
    description: Optional[str] = None
    version: str = "1.0.0"
    author: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkflowDefinition(BaseModel):
    """
    Complete workflow definition.
    
    This is the main schema that LLMs will generate and modify.
    """
    metadata: WorkflowMetadata
    
    nodes: List[WorkflowNode] = Field(..., description="List of workflow nodes/steps")
    
    # Global configuration
    variables: Dict[str, Any] = Field(default_factory=dict, description="Global variables")
    environment: Optional[str] = Field(None, description="Environment (dev, staging, prod)")
    
    # Optional: initial and terminal nodes for clarity
    start_node: Optional[str] = Field(None, description="Entry point node ID")
    end_nodes: List[str] = Field(default_factory=list, description="Terminal node IDs")
    
    def get_node(self, node_id: str) -> Optional[WorkflowNode]:
        """Get a node by ID"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def validate_dependencies(self) -> List[str]:
        """Validate that all dependencies exist"""
        errors = []
        node_ids = {node.id for node in self.nodes}
        
        for node in self.nodes:
            for dep in node.depends_on:
                if dep not in node_ids:
                    errors.append(f"Node '{node.id}' depends on non-existent node '{dep}'")
        
        return errors
    
    def topological_sort(self) -> List[WorkflowNode]:
        """Return nodes in execution order (topological sort)"""
        # Build dependency graph
        in_degree = {node.id: len(node.depends_on) for node in self.nodes}
        node_map = {node.id: node for node in self.nodes}
        
        # Find nodes with no dependencies
        queue = [node for node in self.nodes if len(node.depends_on) == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            # Find nodes that depend on current
            for node in self.nodes:
                if current.id in node.depends_on:
                    in_degree[node.id] -= 1
                    if in_degree[node.id] == 0:
                        queue.append(node)
        
        if len(result) != len(self.nodes):
            raise ValueError("Circular dependency detected in workflow")
        
        return result


class ExecutionContext(BaseModel):
    """Context passed to nodes during execution"""
    workflow_id: str
    execution_id: str
    variables: Dict[str, Any] = Field(default_factory=dict)
    node_results: Dict[str, Any] = Field(default_factory=dict)  # Results from completed nodes
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NodeResult(BaseModel):
    """Result of executing a single node"""
    node_id: str
    status: Literal["success", "failed", "skipped"]
    output: Any = None
    error: Optional[str] = None
    execution_time: Optional[float] = None  # seconds
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorkflowExecutionResult(BaseModel):
    """Result of executing the entire workflow"""
    workflow_id: str
    execution_id: str
    status: Literal["success", "failed", "partial"]
    node_results: Dict[str, NodeResult]
    start_time: str
    end_time: str
    total_duration: float  # seconds
    error: Optional[str] = None

