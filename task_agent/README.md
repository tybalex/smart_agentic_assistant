# 🤖 Task Agent

An intelligent task execution system that parses natural language text into actionable tasks, executes them step-by-step with user confirmation, and provides real-time visual feedback.

## Features

- **Natural Language Task Parsing**: Input free-form text and let AI extract actionable tasks
- **Visual Progress Tracking**: Color-coded highlighting shows execution progress on original text
- **Step-by-Step Execution**: Confirm each task before execution for full control
- **External Tool Integration**: Connects to a tool registry API for executing real actions
- **Dynamic Task Management**: AI reviews progress and can add/modify/remove tasks as needed
- **Session Persistence**: Save and resume task sessions

## Architecture

```
task_agent/
├── app.py              # Streamlit UI
├── agent.py            # AI Agent (Claude Sonnet 4.5)
├── tool_client.py      # Tool Registry API client
├── task_manager.py     # Task list management & persistence
├── models.py           # Data models
├── pyproject.toml      # Project config & dependencies (uv)
└── task_data/          # Session storage (auto-created)
```

## Prerequisites

1. **Python 3.10+**
2. **uv**: Fast Python package manager - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
3. **Anthropic API Key**: Set the `ANTHROPIC_API_KEY` environment variable
4. **Tool Registry API**: Running at `localhost:9999` (or configure a different URL)

## Installation

```bash
# Navigate to the project
cd task_agent

# Install dependencies with uv
uv sync

# Set your Anthropic API key
export ANTHROPIC_API_KEY="your-api-key-here"
```

## Usage

### Start the Application

```bash
# Run with uv
uv run streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

### Workflow

1. **Enter Text**: Type or paste text containing tasks you want to execute
2. **Parse Tasks**: Click "Parse & Start" to let AI extract tasks
3. **Review**: See tasks highlighted in the original text and listed in the sidebar
4. **Execute**: For each task:
   - Review the AI's execution plan
   - Click "Confirm & Execute" to proceed
   - Or "Skip" to move to the next task
5. **Monitor**: Watch the progress with color-coded highlighting:
   - 🟢 **Green**: Completed tasks
   - 🟡 **Yellow**: Current task (pulsing)
   - 🔵 **Blue**: Pending tasks
   - 🔴 **Red**: Failed tasks
   - ⬜ **Gray**: Skipped tasks

### Example Input

```
I need to check the current weather in San Francisco, then calculate 
the square root of 144, and finally list all available file operations.
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key | Required |

### In-Code Configuration

In `agent.py`:
- `model`: Change the Claude model (default: `claude-sonnet-4-5-20250929`)

In `app.py` or when creating the agent:
- `storage_dir`: Change session storage location (default: `./task_data`)
- `tool_api_url`: Change tool registry URL (default: `http://localhost:9999`)

## Tool Registry API

The agent expects a tool registry API with the following endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/functions` | GET | List all functions |
| `/functions/{name}` | GET | Get function details |
| `/functions/category/{category}` | GET | List functions by category |
| `/categories` | GET | List all categories |
| `/functions/search?q={query}` | GET | Search functions |
| `/{category}/{function_name}` | POST | Execute a function |

## Data Models

### Task

```python
Task:
  - id: str
  - title: str
  - description: str
  - status: TaskStatus (pending/in_progress/completed/failed/skipped)
  - text_span: TextSpan (start, end, text)
  - result: str (execution result)
  - tool_used: str
  - tool_params: dict
```

### TaskSession

```python
TaskSession:
  - id: str
  - original_text: str
  - tasks: List[Task]
  - agent_notes: List[str]
```

## Development

### Adding Dependencies

```bash
# Add a new dependency
uv add <package-name>

# Add a dev dependency
uv add --dev <package-name>
```

### Project Structure

- **models.py**: Data classes for Task, TaskSession, TextSpan, etc.
- **tool_client.py**: HTTP client for the tool registry API
- **task_manager.py**: Task CRUD operations and file persistence
- **agent.py**: AI agent with Claude integration for parsing, planning, and execution
- **app.py**: Streamlit UI

### Adding New Features

1. **New Task Operations**: Extend `TaskManager` class
2. **Custom Tool Handling**: Modify `ToolRegistryClient`
3. **AI Behavior**: Update prompts in `TaskAgent`
4. **UI Components**: Add to `app.py`

## Troubleshooting

### Tool API Connection Failed
- Ensure the tool registry is running at the configured URL
- Check network/firewall settings

### Tasks Not Parsing Correctly
- Ensure your text contains clear, actionable items
- The AI works best with explicit task descriptions

### API Key Issues
- Verify `ANTHROPIC_API_KEY` is set correctly
- Check API key permissions and quota

## License

MIT License
