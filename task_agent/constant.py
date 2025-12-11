import os

# Tool Registry
DEFAULT_TOOL_REGISTRY_URL = os.environ.get("TOOL_REGISTRY_URL", "http://localhost:9999")

# Model Configuration
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
CLAUDE_MAX_OUTPUT_TOKENS = 8192  # Max tokens Claude can generate per response
SUMMARIZATION_TEMPERATURE = 0.2  # Lower temperature for more consistent summaries

# Token Budget Limits
CONTEXT_WINDOW_LIMIT = 200_000  # Max tokens for input context (Claude's limit)
DEFAULT_MAX_TOTAL_TOKENS = 10_000_000  # Default total token budget (cumulative spend)
DEFAULT_MAX_TURNS = 999  # High default for backward compatibility (not enforced)
TOKEN_ESTIMATION_DIVISOR = 4  # Rough estimate: chars / 4 ≈ tokens

# History Management
MAX_CLARIFICATIONS_IN_CONTEXT = 10  # Number of recent clarification Q&As to include
MAX_EXECUTION_HISTORY_IN_CONTEXT = 20  # Number of recent execution turns to include

# Tool Discovery Cache
MAX_CACHED_FUNCTION_DETAILS = 20  # LRU cache limit for detailed function specifications

# Batch Action Execution
MAX_BATCH_SIZE = 10  # Maximum number of actions in a single batch

