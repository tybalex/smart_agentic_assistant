# 🧠 Smart Workflow

An intelligent agent system that combines continuous planning, dynamic workflows, and a flexible tool registry to accomplish complex tasks.

## Components

### 🤖 [Task Agent](./task_agent/)
A continuous planning agent that breaks down goals into executable steps, proposes actions one at a time, and adapts its plan based on real-time results. Features user approval workflow, state tracking, and session persistence.

### 🔧 [Function Registry](./example_registry/)
A REST API service that exposes a catalog of tools and functions the agent can use. Provides dynamic discovery, parameter validation, and execution of operations across various platforms (GitHub, AWS, Airtable, Slack, etc.).

### ⚙️ [Workflow Core](./workflow_core/)
Workflow execution runtime supporting multiple execution strategies (LangGraph, simple sequential). Provides interactive CLI and web UI for designing and running multi-step workflows.

## Quick Start

```bash
# Start the function registry
cd example_registry
uv run uvicorn main:app --reload --port 9999

# Start the task agent UI
cd task_agent
uv run streamlit run app.py
```

## How It Works

1. **User provides a goal** → Task agent creates an initial plan
2. **Agent proposes an action** → User approves/skips/aborts
3. **Action executes via tool registry** → Results update the agent's state
4. **Plan adapts dynamically** → Process repeats until goal is achieved

The system handles token budgets, context management, and session persistence automatically.

## Key Features

- 🔄 **Continuous re-planning** - adapts to actual results, not fixed scripts
- 🎯 **Goal-oriented** - original objective always visible
- 🛠️ **Extensible** - easy to add new tools and functions
- 💾 **Persistent** - save and resume sessions
- 🎨 **Visual UI** - see plan, state, and execution in real-time

See individual component READMEs for detailed documentation.
