# Executor Agent

The Executor Agent runs workflow.md files step-by-step with validation. It operates with a **fixed, scoped set of tools** defined in tools.json - no dynamic tool discovery.

## Architecture

```
workflow.md    → Natural language workflow steps + validation criteria
tools.json     → Scoped list of allowed tools (server/tool pairs)
                ↓
         Executor Agent
                ↓
         Tool Registry API
                ↓
         Execution Trace (JSON)
```

## Key Features

1. **Natural Language Workflows** - Reads workflow.md as instructions
2. **Scoped Tool Access** - Only uses tools from tools.json
3. **Step-by-Step Execution** - Sequential execution with validation
4. **Validation** - Checks outputs against criteria in workflow
5. **JSON Trace** - Returns structured execution log

## Usage

```bash
# Execute a workflow
python -m executor.cli workflows/onboarding/workflow.md

# With custom tools.json path
python -m executor.cli workflows/onboarding/workflow.md workflows/onboarding/tools.json

# Save trace to file
python -m executor.cli workflows/onboarding/workflow.md --output trace.json
```

## Workflow Format

```markdown
# Workflow Title

## Goal
High-level description of what this workflow achieves

## Steps
1. First step description
2. Second step description
3. Third step description

## Validation
- Check that X exists
- Verify Y equals Z
- Ensure W contains V
```

## Tools Configuration

```json
{
  "mcp_servers": ["github", "slack"],
  "tools": [
    {
      "server": "github",
      "tool": "create_user",
      "description": "Create GitHub user"
    }
  ],
  "version": "1.0"
}
```

## Execution Trace

The executor returns a JSON trace with:

```json
{
  "workflow_path": "workflows/onboarding/workflow.md",
  "session_id": "exec_20231211_143022",
  "start_time": "2023-12-11T14:30:22Z",
  "end_time": "2023-12-11T14:31:45Z",
  "status": "completed",
  "steps": [
    {
      "step_number": 1,
      "description": "Create GitHub account",
      "status": "completed",
      "timestamp": "2023-12-11T14:30:25Z",
      "reasoning": "Creating account for new hire",
      "tool_calls": [{
        "server": "github",
        "tool": "create_user",
        "parameters": {"username": "john_doe", "email": "john@company.com"}
      }],
      "result": {"success": true, "user_id": "12345"},
      "error": null,
      "validation_results": [
        {"check": "GitHub account exists", "passed": true, "message": "User created"}
      ]
    }
  ],
  "clarification_requests": [],
  "final_summary": "All steps completed successfully"
}
```

## Status Codes

- `completed` - All steps executed successfully
- `failed` - Execution failed at some step
- `needs_clarification` - Executor needs user input to proceed
- `active` - Currently running (shouldn't see this in final trace)

## Design Philosophy

The Executor Agent is **intentionally simple**:
- No UI (returns JSON trace)
- No dynamic tool discovery (uses fixed tools.json)
- No planning/replanning (follows workflow.md sequentially)
- No user interaction during execution (except clarifications)

This simplicity makes it **predictable and debuggable** - the Main Agent can analyze its trace and improve the workflow.md to eliminate issues.
