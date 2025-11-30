"""Tests for workflow schema"""

import pytest
from src.schema import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowMetadata,
)


def test_simple_workflow_creation():
    """Test creating a simple workflow"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test Workflow"),
        nodes=[
            WorkflowNode(
                id="node1",
                type="log",
                config={"message": "Hello"}
            ),
            WorkflowNode(
                id="node2",
                type="log",
                config={"message": "World"},
                depends_on=["node1"]
            )
        ]
    )
    
    assert workflow.metadata.name == "Test Workflow"
    assert len(workflow.nodes) == 2
    assert workflow.nodes[1].depends_on == ["node1"]


def test_workflow_validation_missing_dependency():
    """Test that validation catches missing dependencies"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        nodes=[
            WorkflowNode(
                id="node1",
                type="log",
                config={},
                depends_on=["nonexistent"]
            )
        ]
    )
    
    errors = workflow.validate_dependencies()
    assert len(errors) > 0
    assert "nonexistent" in errors[0]


def test_topological_sort():
    """Test topological sorting of nodes"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        nodes=[
            WorkflowNode(id="c", type="log", config={}, depends_on=["a", "b"]),
            WorkflowNode(id="b", type="log", config={}, depends_on=["a"]),
            WorkflowNode(id="a", type="log", config={}, depends_on=[]),
        ]
    )
    
    sorted_nodes = workflow.topological_sort()
    node_ids = [n.id for n in sorted_nodes]
    
    # 'a' must come before 'b' and 'c'
    assert node_ids.index("a") < node_ids.index("b")
    assert node_ids.index("a") < node_ids.index("c")
    assert node_ids.index("b") < node_ids.index("c")


def test_circular_dependency_detection():
    """Test that circular dependencies are detected"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        nodes=[
            WorkflowNode(id="a", type="log", config={}, depends_on=["b"]),
            WorkflowNode(id="b", type="log", config={}, depends_on=["a"]),
        ]
    )
    
    with pytest.raises(ValueError, match="Circular dependency"):
        workflow.topological_sort()


def test_get_node():
    """Test getting a node by ID"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        nodes=[
            WorkflowNode(id="test_node", type="log", config={}),
        ]
    )
    
    node = workflow.get_node("test_node")
    assert node is not None
    assert node.id == "test_node"
    
    missing = workflow.get_node("nonexistent")
    assert missing is None

