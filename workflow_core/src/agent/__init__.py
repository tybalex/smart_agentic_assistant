"""LLM Agent Integration"""

# Import tools first (they don't require external dependencies)
from .tools import WorkflowTools, TOOL_DEFINITIONS
from .prompts import AGENT_SYSTEM_PROMPT

# Try to import WorkflowAgent (requires anthropic)
try:
    from .workflow_agent import WorkflowAgent
    __all__ = ["WorkflowAgent", "WorkflowTools", "TOOL_DEFINITIONS", "AGENT_SYSTEM_PROMPT"]
except ImportError:
    # anthropic not installed, skip WorkflowAgent
    __all__ = ["WorkflowTools", "TOOL_DEFINITIONS", "AGENT_SYSTEM_PROMPT"]

