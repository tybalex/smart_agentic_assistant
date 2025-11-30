"""
Base Runtime Interface

This abstraction allows us to plug in different execution engines:
- SimpleWorkflowExecutor (our basic implementation)
- LangGraphExecutor (future)
- TemporalExecutor (future)
- PrefectExecutor (future)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..schema import WorkflowDefinition, WorkflowExecutionResult, ExecutionContext


class WorkflowRuntime(ABC):
    """
    Abstract base class for workflow execution engines.
    
    Any runtime (simple, LangGraph, Temporal, etc.) must implement this interface.
    """
    
    @abstractmethod
    async def execute(
        self,
        workflow: WorkflowDefinition,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> WorkflowExecutionResult:
        """
        Execute a workflow from start to finish.
        
        Args:
            workflow: The workflow definition to execute
            initial_context: Initial variables/data for execution
            
        Returns:
            WorkflowExecutionResult with status and outputs
        """
        pass
    
    @abstractmethod
    async def execute_node(
        self,
        workflow: WorkflowDefinition,
        node_id: str,
        context: ExecutionContext
    ) -> Any:
        """
        Execute a single node in the workflow.
        
        Args:
            workflow: The workflow definition
            node_id: ID of the node to execute
            context: Current execution context
            
        Returns:
            Result of node execution
        """
        pass
    
    @abstractmethod
    async def validate(self, workflow: WorkflowDefinition) -> Dict[str, Any]:
        """
        Validate a workflow without executing it.
        
        Returns:
            Dictionary with validation results (is_valid, errors, warnings)
        """
        pass
    
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Return capabilities of this runtime.
        
        Useful for knowing what features are supported.
        """
        return {
            "parallel_execution": False,
            "conditional_branching": False,
            "human_in_the_loop": False,
            "checkpointing": False,
            "streaming": False,
            "retry": False,
        }

