# Smart Workflow - AI-Driven Workflow Builder

> **"Cursor for Workflows"** - An intelligent workflow system where LLM agents can design, iterate, and improve workflows with human-in-the-loop feedback.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---
---

## 🌟 Vision

Just like Cursor helps developers write and improve code iteratively, **Smart Workflow** enables users to build and refine automation workflows through continuous AI assistance. The AI doesn't just generate a workflow once - it actively helps debug, optimize, and enhance it based on execution results and user feedback.

## ✨ Key Features

- **🤖 AI-Powered Generation**: Convert natural language requirements into executable workflows
- **🔄 Iterative Improvement**: Continuously refine workflows based on execution results
- **🎯 Targeted Editing**: Improve specific workflow steps without regenerating everything
- **🔌 Pluggable Runtime**: Start simple, upgrade to LangGraph/Temporal when needed
- **📝 Clean Schema**: Human and AI-friendly YAML/JSON workflow definitions
- **💬 Conversational Interface**: Chat with AI to build workflows naturally
- **🧪 Built-in Testing**: Execute and validate workflows immediately

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <your-repo>
cd smart-workflow

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up API key for AI features
export ANTHROPIC_API_KEY=your-key-here
```

### Run Your First Example

```bash
# Execute a predefined workflow (no API key needed)
python examples/basic_example.py

# NEW: Agentic workflow assistant (requires API key)
python examples/agentic_demo.py

# Interactive CLI - just chat with the agent!
python examples/interactive_cli.py

# NEW: Visual workflow editor (Stage 1: View Mode)
python run_ui.py
# or
streamlit run ui/app.py
```

### 🎨 Workflow Visualizer UI (NEW!)

A clean, interactive web interface for viewing and working with workflows:

```bash
# Install UI dependencies
pip install -e ".[ui]"

# Launch the visualizer
python run_ui.py
```

**Features:**
- 📋 Load and view workflow YAML files
- 🔍 Inspect node details, dependencies, and configuration
- 📊 See execution order (topological sort)
- 🎯 Clean card-based layout for each node
- ✏️ Edit nodes inline with JSON validation
- ➕ Add and remove nodes dynamically
- 💾 Export modified workflows to YAML
- ▶️ Run individual nodes (Jupyter-style!)
- ✅ See real-time execution results
- 🔗 Chain node executions with context
- 💬 **NEW:** AI chat assistant integrated in UI!
- 🤖 **NEW:** Modify workflows with natural language
- ✨ **NEW:** Agent-driven workflow editing

See [ui/README.md](ui/README.md) for detailed documentation.

## 📖 How It Works

### 1. **AI-Friendly Schema Layer**

Workflows are defined in simple, intuitive JSON/YAML that LLMs can easily read and write:

```yaml
metadata:
  name: "Customer Onboarding"
  description: "Automate new customer setup"

nodes:
  - id: validate_email
    type: api_call
    description: "Validate customer email"
    config:
      url: "https://api.validator.com/email"
      method: "POST"
      input: "{{user.email}}"
  
  - id: create_account
    type: database_insert
    depends_on: [validate_email]
    config:
      table: "customers"
```

### 2. **Pluggable Runtime Layer**

Execute workflows with different backends:

```python
from src.runtime import SimpleWorkflowExecutor  # Start here
# from src.runtime import LangGraphExecutor     # Upgrade later
# from src.runtime import TemporalExecutor      # For enterprise

executor = SimpleWorkflowExecutor()
result = await executor.execute(workflow)
```

### 3. **AI Agent Integration (New Agentic Approach!)**

The agent has tools and works autonomously - just chat with it:

```python
from src.agent import WorkflowAgent

agent = WorkflowAgent()

# Just describe what you want - agent figures out how to do it!
response = agent.chat("""
    Create a workflow that:
    1. Fetches user data from an API
    2. Validates it
    3. Sends notifications
    
    Test it and fix any issues.
""")

# Agent autonomously:
# - Creates the workflow using write_workflow tool
# - Tests it using run_workflow tool
# - Fixes any issues
# - Reports success!

print(response)  # "✅ Created and tested workflow. All nodes working!"
```

**That's it!** No separate methods for generate/improve/test. The agent has tools and decides what to do.

## 🎯 Use Cases

- **Data Pipelines**: ETL processes with AI-assisted optimization
- **API Orchestration**: Complex multi-API workflows
- **Business Automation**: Customer onboarding, approvals, notifications
- **DevOps Automation**: Deployment pipelines, infrastructure management
- **Testing Workflows**: Automated testing sequences
- **Monitoring**: Health checks, alerting, incident response

## 🏗️ Architecture

```
User Requirements
      ↓
AI Agent (generates/improves workflows)
      ↓
Workflow Schema (simple JSON/YAML)
      ↓
Runtime Abstraction (pluggable executors)
      ↓
Executor (Simple/LangGraph/Temporal)
      ↓
Execution Results → Feedback Loop
```

**Key Design Principles:**
- ✅ Two-layer architecture (schema + runtime)
- ✅ LLM works with clean, intuitive format
- ✅ Runtime complexity hidden from AI
- ✅ Easy to swap execution engines
- ✅ Version-controllable workflows

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## 📚 Documentation

- **[Quick Start Guide](QUICKSTART.md)** - Get up and running in 5 minutes
- **[Architecture Overview](ARCHITECTURE.md)** - Deep dive into system design
- **[Examples](examples/)** - Working examples and demos

## 🔧 Available Node Types

| Type | Description | Example Use |
|------|-------------|-------------|
| `api_call` | HTTP requests | REST API calls |
| `transform` | Data manipulation | Filter, map, reduce |
| `condition` | Branching logic | If/else workflows |
| `log` | Debugging output | Track execution |
| `delay` | Wait periods | Rate limiting |

**Extensible**: Add custom node types by implementing handlers.

## 🎨 Examples

### Generate a Workflow

```python
requirements = """
Automate our support ticket workflow:
1. Receive ticket via API
2. Classify ticket priority using AI
3. Route to appropriate team
4. Send confirmation email
5. Create calendar reminder for follow-up
"""

workflow = await agent.generate_workflow(requirements)
```

### Improve a Specific Node

```python
improved_node, explanation = await agent.improve_node(
    workflow,
    node_id="classify_priority",
    request="Use a more accurate classification model"
)
```

### Interactive Development

```bash
$ python examples/interactive_cli.py

> generate Create a workflow to monitor API health every minute
✅ Generated: API Health Monitor

> execute
✅ Execution: SUCCESS

> improve Add Slack notifications when API is down
✅ Workflow improved!

> save api_monitor.yaml
✅ Saved to api_monitor.yaml
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_schema.py

# Run with coverage
pytest --cov=src tests/
```

## 🛣️ Roadmap

### Phase 1: Core Foundation ✅ (Current)
- [x] Basic workflow schema
- [x] Simple executor
- [x] AI agent integration
- [x] Example workflows

### Phase 2: Enhanced Features
- [ ] Parallel execution
- [ ] Real-time monitoring
- [ ] Web UI for visualization
- [ ] More node types (database, file operations, etc.)
- [ ] Better error recovery

### Phase 3: Enterprise Features
- [ ] LangGraph runtime integration
- [ ] Temporal/Airflow backends
- [ ] Multi-tenancy
- [ ] API server mode
- [ ] Secrets management
- [ ] Audit logging

### Phase 4: Intelligence
- [ ] Automatic optimization suggestions
- [ ] Pattern detection across workflows
- [ ] Cost/performance analysis
- [ ] A/B testing workflows
- [ ] Learning from execution history

## 🤝 Contributing

Contributions are welcome! Areas we'd love help with:

- Additional node type handlers
- Runtime implementations (LangGraph, Temporal)
- UI/visualization tools
- Documentation and examples
- Testing and bug fixes

## ⚠️ Current Limitations

- **Sequential Execution**: Nodes run one at a time (parallel support planned)
- **No Persistence**: Workflows run in-memory (database backing planned)
- **Simple Security**: Using `eval()` for expressions (safe evaluator planned)
- **No Human-in-Loop UI**: CLI only for now (web UI planned)

## 🔒 Security Notes

**For Production Use:**
- Replace `eval()` with safe expression evaluator
- Add authentication and authorization
- Implement secret management
- Enable audit logging
- Use rate limiting

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 💡 Why This Matters

**Problem**: Workflow builders (n8n, Zapier, etc.) are great, but when something breaks or needs improvement, users are on their own. It's a one-shot generation.

**Solution**: Smart Workflow brings the "Cursor experience" to workflow automation:
- AI doesn't just create workflows - it maintains them
- Execution results feed back to improve the system
- Users can chat naturally to refine workflows
- Continuous iteration until perfection

**Just like Cursor transformed coding, Smart Workflow transforms workflow automation.**

## 🙏 Acknowledgments

Inspired by:
- [Cursor](https://cursor.com) - AI-powered code editor
- [LangGraph](https://github.com/langchain-ai/langgraph) - State machine framework
- [n8n](https://n8n.io) - Workflow automation platform
- [Temporal](https://temporal.io) - Workflow orchestration

---

**Built with ❤️ for the AI automation community**

[⭐ Star us on GitHub](https://github.com/your-repo) | [📖 Read the Docs](QUICKSTART.md) | [💬 Join Discussion](https://github.com/your-repo/discussions)
