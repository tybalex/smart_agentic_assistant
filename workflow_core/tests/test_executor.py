"""Tests for workflow executor"""

import pytest
import asyncio
from src.schema import (
    WorkflowDefinition,
    WorkflowNode,
    WorkflowMetadata,
)
from src.runtime import SimpleWorkflowExecutor


@pytest.mark.asyncio
async def test_simple_execution():
    """Test executing a simple workflow"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        nodes=[
            WorkflowNode(
                id="log1",
                type="log",
                config={"message": "Hello", "level": "info"}
            )
        ]
    )
    
    executor = SimpleWorkflowExecutor()
    result = await executor.execute(workflow)
    
    assert result.status == "success"
    assert "log1" in result.node_results
    assert result.node_results["log1"].status == "success"


@pytest.mark.asyncio
async def test_sequential_execution():
    """Test that nodes execute in order"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        nodes=[
            WorkflowNode(id="a", type="log", config={"message": "A"}),
            WorkflowNode(id="b", type="log", config={"message": "B"}, depends_on=["a"]),
            WorkflowNode(id="c", type="log", config={"message": "C"}, depends_on=["b"]),
        ]
    )
    
    executor = SimpleWorkflowExecutor()
    result = await executor.execute(workflow)
    
    assert result.status == "success"
    assert all(nr.status == "success" for nr in result.node_results.values())


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in workflow"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        nodes=[
            WorkflowNode(
                id="bad_api",
                type="api_call",
                config={"url": "http://invalid-domain-that-does-not-exist.com", "method": "GET"}
            ),
            WorkflowNode(
                id="after_error",
                type="log",
                config={"message": "Should not execute"},
                depends_on=["bad_api"]
            )
        ]
    )
    
    executor = SimpleWorkflowExecutor()
    result = await executor.execute(workflow)
    
    assert result.status == "failed"
    assert result.node_results["bad_api"].status == "failed"
    # Second node should not have executed due to dependency failure
    assert "after_error" not in result.node_results or \
           result.node_results["after_error"].status != "success"


@pytest.mark.asyncio
async def test_variable_substitution():
    """Test variable substitution in node config"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        variables={"greeting": "Hello", "name": "World"},
        nodes=[
            WorkflowNode(
                id="log_with_vars",
                type="log",
                config={"message": "{{greeting}} {{name}}!"}
            )
        ]
    )
    
    executor = SimpleWorkflowExecutor()
    result = await executor.execute(workflow)
    
    assert result.status == "success"


@pytest.mark.asyncio
async def test_validation():
    """Test workflow validation"""
    workflow = WorkflowDefinition(
        metadata=WorkflowMetadata(name="Test"),
        nodes=[
            WorkflowNode(id="a", type="log", config={}, depends_on=["nonexistent"])
        ]
    )
    
    executor = SimpleWorkflowExecutor()
    validation = await executor.validate(workflow)
    
    assert not validation["is_valid"]
    assert len(validation["errors"]) > 0

