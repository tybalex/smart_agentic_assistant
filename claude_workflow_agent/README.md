# Claude Workflow Agent

> **Claude Code for Workflows** - Build complex automated workflows through natural conversation with AI

An AI-powered conversational assistant for creating sophisticated multi-step business process automations using Claude AI and the Model Context Protocol (MCP).

## What is This?

**Imagine describing your business process in plain English, and having AI turn it into a working automation.**

Claude Workflow Agent is like Claude Code, but for workflows instead of code:
- **Claude Code**: Chat with AI → Get working code → Run it
- **Workflow Agent**: Chat with AI → Get working workflow → Execute it

Have a natural conversation with Claude to design, refine, and test multi-step business processes that integrate with real APIs and services (Salesforce, Slack, Google Groups, and more).

### How It Works

- **Main Agent (The Focus)**: Your conversational partner for workflow development
  - Chat naturally to describe what you want to automate
  - Agent discovers available MCP tools (Salesforce, Slack, Google Groups, etc.)
  - Helps you write and refine workflow definitions in markdown
  - Validates your workflow structure and selects the right tools
  - Iteratively improves workflows based on your feedback

- **Executor (The Runtime)**: Background execution engine that runs your workflows
  - Takes the workflow the Main Agent created and executes it
  - Handles API authentication and tool execution
  - Provides execution traces and error handling

## Features

- 💬 **Conversational Workflow Design**: Build complex workflows through natural conversation with Claude
- 🔧 **MCP Tool Discovery**: Automatically discovers and connects to MCP servers (Salesforce, Slack, Google Groups, etc.)
- 📝 **Markdown Workflows**: Creates human-readable workflow definitions that are easy to understand and modify
- 🎯 **Smart Tool Selection**: Agent helps you choose exactly the right tools for your workflow
- 🔄 **Interactive Development**: Iteratively refine workflows based on feedback and requirements
- 🔐 **Built-in Authentication**: Handles OAuth flows automatically with persistent token storage
- 📊 **Execution Runtime**: Run your workflows with detailed tracing and error handling
- 💾 **Session Management**: Save and resume workflow development conversations

## Prerequisites

- Python 3.13 or higher
- Anthropic API key
- MCP servers configured (optional, depending on your workflows)

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd claude_workflow_agent
```

### 2. Install dependencies

Using uv (recommended):
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

Or using pip:
```bash
pip install -e .
```

### 3. Set up MCP Servers

**Step 3.1: Launch MCP servers**
1. Visit [https://main.acornlabs.com](https://main.acornlabs.com)
2. Launch the MCP servers you need (e.g., Salesforce, Slack, Google Groups)
3. Copy the server URLs provided

**Step 3.2: Configure `.env` file**

Create a `.env` file in the project root:
```bash
# Anthropic API Key (required)
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# MCP Server URLs (paste from acornlabs.com)
SALESFORCE=https://mcp.runmore.ai/salesforce
SLACK=https://mcp.runmore.ai/slack
GOOGLE_GROUPS=https://mcp.runmore.ai/google-groups
GOOGLE_SHEETS=https://mcp.runmore.ai/google-sheets

# Add any other MCP servers you need
# The variable name (converted to lowercase) becomes the server name
```

**How it works:**
- The system automatically discovers any HTTPS URL in the `.env` file as an MCP server
- The environment variable name becomes the server name (e.g., `SALESFORCE` → `salesforce`)
- You can add as many MCP servers as you need

## Quick Start

### Complete Setup-to-Execution Flow

**TL;DR: 4 steps to working workflows**
1. Visit [main.acornlabs.com](https://main.acornlabs.com) → Launch MCP servers → Copy URLs to `.env`
2. `python main_cli.py` → Authenticate via browser (one-time per server)
3. Chat with Agent to build your workflow
4. `cd executor && python cli.py run <workflow_name>` → Execute it

### First Time Setup

On your first run, the system will authenticate with your MCP servers:

```bash
python main_cli.py
```

**What to expect:**
1. System discovers MCP servers from your `.env` file
2. For each server, your browser opens for OAuth authentication
3. After authorizing, tokens are cached locally
4. Main Agent is ready - start describing your workflow!

### Start a Conversation to Build a Workflow

**Example conversation:**
```
You: I need to automate our new member onboarding process
Agent: I can help with that! What steps are involved?
You: We need to update Salesforce, add them to mailing lists, and send a welcome email
Agent: Great! Let me discover what tools are available...
     [Agent discovers MCP tools and helps you build the workflow]
```

**Dev mode** for verbose output (shows all tool calls and MCP interactions):
```bash
python main_cli.py --dev
```

### Run Your Workflow

Once you've created a workflow through conversation, execute it with the runtime:

```bash
cd executor
python cli.py run <workflow_name>
```

Example:
```bash
python cli.py run cncf_membership_onboarding
```

The executor runs in the background, handling all the API calls and tool executions your workflow needs.

## Project Structure

```
claude_workflow_agent/
├── main_agent/          # 🎯 Main Agent - The core conversational workflow builder
│   ├── agent.py         # Core agent logic and conversation handling
│   ├── cli.py           # CLI interface for interactive sessions
│   ├── prompts.py       # System prompts for workflow development
│   ├── session.py       # Session management and persistence
│   └── tools.py         # Tools available to the Main Agent
│
├── tools/               # MCP integration layer
│   ├── mcp_registry.py  # MCP server discovery and connection
│   ├── config.py        # MCP server configuration
│   └── example_usage.py # Usage examples
│
├── workflows/           # Your workflow definitions (created by Main Agent)
│   ├── cncf_membership_onboarding/
│   │   ├── workflow.md  # Human-readable workflow steps
│   │   └── tools.json   # Tool configuration
│   └── sample/
│       ├── workflow.md
│       └── tools.json
│
├── executor/            # Workflow runtime (executes what Main Agent creates)
│   ├── executor_agent.py # Execution engine
│   ├── cli.py           # CLI for running workflows
│   ├── models.py        # Execution data models
│   └── tool_executor.py # Tool execution layer
│
├── main_cli.py          # 🚀 Start here - Main entry point
└── constants.py         # Global configuration
```

## Workflow Structure

Each workflow consists of two files:

### 1. `workflow.md`

The workflow definition in markdown format:

```markdown
# Workflow Name

## Goal
What this workflow accomplishes

## Input Requirements
- Required input 1
- Required input 2

## Steps
### 1. Step Name
Detailed description of what to do

### 2. Next Step
More details...

## Validation
How to verify the workflow succeeded

## Error Handling
How to handle errors
```

### 2. `tools.json`

The tool configuration specifying MCP servers and tools:

```json
{
  "mcp_servers": ["salesforce", "slack"],
  "tools": [
    {
      "server": "salesforce",
      "tool": "query",
      "description": "Query Salesforce using SOQL",
      "input_schema": { ... }
    }
  ]
}
```

## Why Workflow Agent?

Traditional workflow automation requires:
- Learning specific automation platforms (Zapier, n8n, etc.)
- Understanding API documentation for each service
- Writing integration code or clicking through complex UIs
- Manually handling error cases and edge conditions

**With Workflow Agent:**
- Just describe what you want in conversation
- Agent discovers available integrations automatically
- Workflows are created in readable markdown
- Error handling and edge cases are built-in
- Easy to understand, modify, and maintain

## Example: CNCF Membership Onboarding

The included CNCF workflow demonstrates a complex, real-world automation that was built through conversation with the Main Agent:

**What it does:**
- Updates Salesforce opportunities and accounts
- Manages Google Groups mailing lists
- Sends Slack invitations
- Updates spreadsheets
- Sends welcome emails
- Handles regional variations (Chinese, Korean members)

**What it shows:**
- Integration with multiple external systems (Salesforce, Google, Slack)
- Conditional logic based on membership type
- Sophisticated error handling (critical vs. non-critical)
- Complex input processing and validation

This 250+ step workflow was created through conversation and is maintained as readable markdown.

## MCP Server Configuration

### Server Discovery

MCP servers are configured via the `.env` file (see Installation step 3). The system automatically:
1. Reads all URLs from your `.env` file
2. Connects to each MCP server
3. Discovers available tools through OAuth authentication
4. Makes those tools available to the Main Agent

Example `.env` entry:
```bash
SALESFORCE=https://mcp.runmore.ai/salesforce
```
This creates a server named `salesforce` that the Main Agent can discover and use.

### OAuth Authentication Flow

When you first use an MCP server:
1. The system opens your browser for OAuth authentication
2. You authorize the connection (one-time setup per server)
3. OAuth tokens are cached locally for future use

### OAuth Token Management

OAuth tokens are automatically managed and cached in `.mcp_tokens/` directory:
- **Persistent**: Tokens persist across sessions (no need to re-authenticate every time)
- **Per-server storage**: Each MCP server has its own token files:
  - `{server}_tokens.json` - Access and refresh tokens
  - `{server}_client.json` - OAuth client information
  - `{server}_metadata.json` - Token expiration and metadata
- **Security**: `.mcp_tokens/` is in `.gitignore` to prevent committing secrets

**If you encounter OAuth errors**, delete the cache to force re-authentication:
```bash
rm -rf .mcp_tokens/
```

## Development

### Main Agent Capabilities

The Main Agent is equipped with tools to:
- **Discover MCP servers**: Find available integration points
- **List available tools**: Browse what each MCP server offers
- **Read/Write workflows**: Create and modify workflow definitions
- **Manage sessions**: Save and resume development conversations
- **Validate workflows**: Ensure workflows are correctly structured
- **Select tools**: Help you choose the right tools for each workflow step

### Workflow Development Process

1. **Conversation**: Describe your automation needs in natural language
2. **Discovery**: Agent discovers relevant MCP tools
3. **Design**: Together, you build the workflow step-by-step
4. **Refinement**: Iterate based on feedback and requirements
5. **Validation**: Agent ensures the workflow is complete and correct
6. **Save**: Workflow is saved as `workflow.md` and `tools.json`

### Dev Mode

Enable verbose output to see the agent's thought process:

```bash
python main_cli.py --dev
```

This shows:
- All tool calls and parameters the agent makes
- MCP server responses
- Tool discovery process
- Session state changes
- API interactions and token usage

## Configuration

Key configuration options in `constants.py`:

- `CLAUDE_MODEL`: Claude model to use (default: "claude-sonnet-4-20250514")
- `MAX_ITERATIONS`: Maximum executor iterations (default: 100)
- `MAX_TOKEN_BUDGET`: Maximum tokens per execution (default: 300,000)
- `MAX_TOOL_ROUNDS`: Maximum tool rounds for Main Agent (default: 100)
- `MCP_TOKENS_DIR`: Directory for OAuth tokens (default: ".mcp_tokens")

## Error Handling

Workflows support two types of errors:

### Critical Errors (Stop Execution)
- Authentication failures
- Missing required resources
- Invalid input data
- Data integrity issues

### Non-Critical Errors (Continue Execution)
- Duplicate/already exists errors
- Individual operation failures
- Email bounces or delivery issues

Configure error handling in your `workflow.md` file.

## Contributing

When creating new workflows:

1. Start with clear goals and input requirements
2. Break down complex processes into discrete steps
3. Specify validation criteria
4. Document error handling strategies
5. Test thoroughly with the Executor Agent
6. Include example usage in comments

## Troubleshooting

### OAuth Authentication Issues

**Problem: "OAuthClient not found" or similar OAuth errors**

If you encounter errors like:
```
OAuthClient.obot.obot.ai "oc13555lcs6opdwzrhmlmzopy5jd7" not found
```

**Solution: Clear the OAuth token cache**
```bash
# Delete the token cache and restart
rm -rf .mcp_tokens/
python main_cli.py
```

This forces a fresh OAuth authentication flow. The issue typically occurs when:
- OAuth client credentials have changed on the server
- Cached tokens reference old/deleted OAuth clients
- Token files are corrupted or out of sync

After clearing the cache, the system will prompt you to re-authenticate with each MCP server.

### Other Authentication Issues
- Verify `ANTHROPIC_API_KEY` is set correctly
- Check that your MCP server OAuth credentials are valid
- Ensure OAuth callback URLs are properly configured

### Workflow Execution Fails
- Verify all required MCP servers are configured
- Check tool names match between workflow.md and tools.json
- Review execution trace for detailed error information
- Ensure input data meets requirements
- Try clearing `.mcp_tokens/` if you see authentication errors

### MCP Connection Issues
- Verify MCP server URLs are accessible
- Check OAuth client credentials haven't expired
- Review MCP server logs if available
- Clear token cache if authentication repeatedly fails

## License

[Add your license here]

## Support

[Add support information here]

---

Built with [Claude](https://www.anthropic.com/claude) and [Model Context Protocol](https://modelcontextprotocol.io/)

