# 🤖 Continuous Planning Agent

An intelligent task execution system using **continuous re-planning**. Instead of parsing all tasks upfront, the agent evaluates the situation each turn, updates its plan based on results, and proposes one action at a time for user approval.

## Key Features

- **Continuous Re-planning**: Agent re-evaluates and updates the plan every turn based on actual results
- **Goal Tracking**: Original objective always visible, never forgotten
- **State Visualization**: See the agent's current understanding of the situation
- **Dynamic Plan Updates**: Plan adapts as execution progresses
- **Token Budget**: Prevents runaway execution with configurable token limits
- **History Summarization**: Manages context length for long-running sessions
- **Text Highlighting**: Visual mapping of plan steps to original goal text
- **Session Persistence**: Save and resume sessions

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GOAL (Immutable)                        │
│  Original user request - always visible, never forgotten        │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MAIN LOOP (while not done)                   │
│                                                                 │
│  1. EVALUATE & PLAN                                             │
│     → Assess current state                                      │
│     → Update plan based on results                              │
│     → Propose next action                                       │
│                                                                 │
│  2. USER APPROVAL                                               │
│     [Approve] [Skip] [Abort]                                    │
│                                                                 │
│  3. EXECUTE                                                     │
│     → Run action via tool API                                   │
│     → Update state with results                                 │
│     → Manage history & budget                                   │
│                                                                 │
│  4. CHECK COMPLETION                                            │
│     → Goal achieved? Budget exceeded?                           │
└─────────────────────────────────────────────────────────────────┘
```

## Core Components

```
task_agent/
├── app.py              # Streamlit UI with plan/state visualization
├── agent.py            # ContinuousPlanningAgent (Claude-powered)
├── session_manager.py  # Session state & persistence
├── tool_client.py      # Tool Registry API client
├── models.py           # Data models (Goal, Plan, State, Action, etc.)
├── pyproject.toml      # Project config & dependencies (uv)
└── task_data/          # Session storage (auto-created)
```

## Data Models

### Session
```python
Session:
  - goal: Goal                    # Original objective (immutable)
  - state: AgentState             # Agent's current understanding
  - plan: Plan                    # Current plan (updated each turn)
  - history: List[HistoryEntry]   # Execution history
  - budget: TokenBudget           # Token usage tracking
  - status: SessionStatus         # active/completed/aborted/budget_exceeded
```

### Plan & State
```python
Plan:
  - steps: List[PlanStep]    # Ordered steps with status
  - reasoning: str           # Why this plan
  - confidence: float        # 0-1

AgentState:
  - summary: str                    # Current situation understanding
  - completed_objectives: List[str] # What's done
  - blockers: List[str]             # Any issues
  - context: Dict                   # Relevant data
```

## Prerequisites

1. **Python 3.10+**
2. **uv**: Fast Python package manager - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
3. **Anthropic API Key**: Set the `ANTHROPIC_API_KEY` environment variable
4. **Tool Registry API**: Running at `localhost:9999` (or configure different URL)

## Installation

```bash
cd task_agent

# Install dependencies
uv sync

# Set your API key
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

### Start the Application

```bash
uv run streamlit run app.py
```

Opens at `http://localhost:8501`

### Workflow

1. **Enter Goal**: Describe what you want to accomplish
2. **Review Initial Plan**: Agent creates a plan with steps linked to your goal text
3. **Execute Turn by Turn**:
   - Click "Next Turn" to get the agent's proposed action
   - Review the action, reasoning, and updated plan
   - Click "Approve" to execute, "Skip" to skip, or "Abort" to stop
4. **Watch Progress**: 
   - Goal text highlights show which parts are completed
   - State summary shows agent's understanding
   - Token budget indicator shows remaining tokens

### Example Session

**Goal**: "Search for weather in Tokyo, calculate if I need an umbrella based on rain chance, and tell me what to wear"

**Turn 1**: 
- Agent proposes: `weather/search(city="Tokyo")`
- You approve → Gets weather data

**Turn 2**:
- Agent sees rain chance is 75%
- Updates plan: adds "recommend rain gear"
- Proposes: `calculation/evaluate(expression="75 > 50")`
- You approve → Returns true

**Turn 3**:
- Agent proposes final recommendation action
- Plan adapts based on actual weather data

## Configuration

### Budget Settings

In the UI sidebar:
- **Max Tokens**: 100K-10M (default: 10M)
  - The agent runs for as many turns as needed, only limited by token budget

### In-Code Configuration

```python
# agent.py
model = "claude-sonnet-4-5-20250929"  # Claude model
max_history_entries = 10              # Before summarization
summarize_after = 7                   # Trigger summarization

# session_manager.py
storage_dir = "./task_data"           # Session storage
```

## How It Differs from Traditional Agent Patterns

| Traditional | Continuous Planning |
|-------------|---------------------|
| Parse all tasks upfront | Re-evaluate each turn |
| Fixed task list | Dynamic plan updates |
| Tasks might become stale | Adapts to actual results |
| Error recovery is awkward | Natural plan adjustment |

## Tool Registry API

Expected endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/functions` | GET | List all functions |
| `/functions/{name}` | GET | Get function details |
| `/categories` | GET | List categories |
| `/{category}/{function}` | POST | Execute function |

## Development

### Adding Dependencies

```bash
uv add <package-name>
uv add --dev <package-name>
```

### Key Extension Points

1. **Custom evaluation logic**: Modify `_evaluate_and_plan()` in `agent.py`
2. **New UI components**: Add to `app.py`
3. **State persistence**: Extend `SessionManager`
4. **History management**: Customize summarization in `_summarize_history()`

## License

MIT License
