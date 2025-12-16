# 🤖 Claude Workflow Agent

A two-agent system for **test-driven workflow development** - similar to how Claude Code helps write better code by running it, this system helps write better workflows by executing them.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Agent (Future)                      │
│                   Workflow Writer                           │
│  - Helps user write/improve workflow.md                    │
│  - Selects tools → tools.json                              │
│  - Calls Executor to validate → analyzes trace             │
│  - Iteratively refines workflow based on execution         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ execute_workflow(workflow.md, tools.json)
                     ↓
┌─────────────────────────────────────────────────────────────┐
│                    Executor Agent (✅ Complete)             │
│                   Workflow Runtime                          │
│  - Reads workflow.md as natural language instructions      │
│  - Uses ONLY tools from tools.json (scoped access)         │
│  - Executes step-by-step with validation                   │
│  - Returns JSON execution trace                            │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
claude_workflow_agent/
├── executor/              ✅ Simplified agent that runs workflows
│   ├── executor_agent.py  # Core execution logic
│   ├── tool_executor.py   # Scoped tool access control
│   ├── models.py          # Data models (trace, steps, etc.)
│   ├── cli.py             # Command line interface
│   └── README.md          # Executor documentation
│
├── main_agent/            🚧 TODO: Workflow writer agent
│   ├── main_agent.py      # Workflow writing logic
│   ├── tools/             # Tools for Main Agent
│   │   ├── edit_workflow.py
│   │   ├── select_tools.py
│   │   └── run_executor.py
│   └── cli.py             # Interactive CLI
│
├── shared/                # Shared utilities (if needed)
│
└── workflows/             # Example workflows
    └── example_onboarding/
        ├── workflow.md    # Natural language workflow
        └── tools.json     # Scoped tool configuration
```

## The Big Idea 💡

**Current Problem:** Writing workflows is hard. You don't know if they'll work until you run them, and debugging is painful.

**Solution:** Two-agent feedback loop:

1. **Main Agent** helps you write workflow.md
2. **Executor Agent** runs it like a test
3. Main Agent sees execution trace → improves workflow
4. Repeat until workflow runs perfectly

Just like test-driven development, but for **workflows**!

## Workflow Files

### workflow.md (Natural Language)

```markdown
# Onboard New Team Member

## Goal
Create accounts for new hire

## Steps
1. Get new hire's email
2. Create GitHub account
3. Create Slack account

## Validation
- GitHub account is active
- Slack invite sent
```

### tools.json (Scoped Access)

```json
{
  "mcp_servers": ["github", "slack"],
  "tools": [
    {"server": "github", "tool": "create_user", "description": "..."},
    {"server": "slack", "tool": "invite_user", "description": "..."}
  ]
}
```

## Development Loop

```
User: "Help me onboard new members"
       ↓
Main Agent: [Writes workflow.md draft]
            [Selects tools → tools.json]
            "Let me test this..."
            [Calls Executor]
       ↓
Executor: [Runs workflow.md]
          [Returns JSON trace with errors]
       ↓
Main Agent: "I see step 3 failed - email field was unclear.
             Let me improve the workflow..."
            [Edits workflow.md]
            [Runs again]
       ↓
Executor: [Success! All steps validated ✓]
       ↓
Main Agent: "Workflow is ready! ✅"
```

## Status

- ✅ **Executor Agent** - Complete and ready to use
- 🚧 **Main Agent** - Next phase of development
- 📝 **Workflow Format** - Defined and validated
- 🔧 **Tool Scoping** - Implemented via tools.json

## Quick Start (Executor Only)

```bash
cd task_agent/claude_workflow_agent

# Run example workflow
python -m executor.cli workflows/example_onboarding/workflow.md

# View trace
python -m executor.cli workflows/example_onboarding/workflow.md --output trace.json
cat trace.json
```

## Next Steps

1. Build Main Agent with tools:
   - `edit_workflow` - Modify workflow.md
   - `select_tools` - Choose tools → tools.json
   - `run_executor` - Execute workflow and get trace
   - `analyze_trace` - Parse execution results

2. Implement interactive CLI for Main Agent

3. Add workflow templates and best practices

---

**Philosophy:** Workflows are code. Code should be tested. Let's make workflow development iterative and testable! 🚀
