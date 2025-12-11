# Function Call Registry

A FastAPI-based function call registry system that provides a centralized catalog of available functions across multiple service categories.

## Features

- **Auto-Discovery**: Functions are automatically discovered from the codebase - no manual registry maintenance
- **Strongly-Typed APIs**: Each function exposed as a REST API endpoint with full type validation
- **RESTful API**: Clean FastAPI endpoints for querying and executing functions
- **Search & Filter**: Find functions by name, description, or category with pagination support
- **Mock Implementations**: In-memory mocks for Google Services, Salesforce, Slack, GitHub, and more
- **Docker Support**: Containerized deployment with docker-compose
- **Web Tools**: Firecrawl and Tavily integration for web scraping and search

## Prerequisites

- Python 3.13+
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer
- Docker (optional, for containerized deployment)

Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Installation

```bash
# Install dependencies with uv
uv sync

# Or with optional web tools (Firecrawl, Tavily)
uv sync --extra web
```

## Running the Server

### Local Development

```bash
# Using Python directly
uv run python main.py
```

Or using uvicorn with hot reload:

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 9999 --reload
```

### Docker

```bash
# Build and run with docker-compose
cd ..  # Go to parent directory
docker-compose up --build

# Or build and run manually
docker build -t function-registry .
docker run -p 9999:9999 function-registry
```

The API will be available at `http://localhost:9999`

## API Endpoints

### Function Execution

**Each function is exposed as a strongly-typed REST endpoint:**

```
POST /{category}/{function_name}
```

Execute any function by posting its parameters as JSON:

```bash
curl -X POST "http://localhost:9999/google_services/google_sheets_append" \
  -H "Content-Type: application/json" \
  -d '{
    "sheet_id": "abc123",
    "range": "Sheet1!A1",
    "values": [["Name", "Email"]]
  }'
```

Response format (standardized wrapper):
```json
{
  "function_name": "google_sheets_append",
  "result": "{\"success\": true, \"message\": \"Appended 1 rows...\", \"rows_added\": 1}",
  "success": true
}
```

All functions return JSON with a `"success"` field inside the `"result"` string.

**Response Structure:**
- **Outer wrapper** (API layer): `function_name`, `result` (JSON string), `success` (boolean)
- **Inner result** (function layer): Parsed from `result` string, always includes `"success": true/false`

The outer `success` field mirrors the inner one - if the function returns `"success": false`, the wrapper will also show `"success": false`.

### Discovery Endpoints

#### 1. List All Functions (with pagination)
```
GET /functions?limit={limit}&offset={offset}
```
Returns all available functions in the registry.

Examples:
```bash
# Get all functions
curl "http://localhost:9999/functions"

# Get first 10 functions
curl "http://localhost:9999/functions?limit=10"

# Get functions 11-20
curl "http://localhost:9999/functions?limit=10&offset=10"
```

#### 2. Get Function by Name
```
GET /functions/{function_name}
```
Get detailed information about a specific function including parameters and types.

Example: 
```bash
curl "http://localhost:9999/functions/google_sheets_append"
```

#### 3. Get Functions by Category (with pagination)
```
GET /functions/category/{category}?limit={limit}&offset={offset}
```
Get all functions in a specific category.

Example: 
```bash
curl "http://localhost:9999/functions/category/google_services?limit=5"
```

#### 4. Get All Categories
```
GET /categories
```
Returns a list of all available categories.

#### 5. Search Functions (with pagination)
```
GET /search?q={query}&limit={limit}&offset={offset}
```
Search functions by name or description.

Examples:
```bash
# Search for "google"
curl "http://localhost:9999/search?q=google"

# Search with limit
curl "http://localhost:9999/search?q=slack&limit=5"
```

## Available Categories

- `google_services` - Google Workspace (Sheets, Gmail, Groups, Membership emails)
- `salesforce` - Salesforce CRM (Query, Create, Schema discovery)
- `slack` - Slack workspace (Channels, Users, Messages, Invitations)
- `github` - GitHub repositories (Branches, Files, Commits, Pull Requests)
- `mailing_list` - Mailing list management (Multiple lists support)
- `member_desk` - Member Desk invitations and management
- `support` - Zendesk ticketing system
- `web` - Web scraping and search (Firecrawl, Tavily)

## Project Structure

```
example_registry/
├── main.py                  # FastAPI application with auto-generated endpoints
├── function_discovery.py    # Auto-discovery and endpoint generation logic
├── pyproject.toml           # Project configuration and dependencies
├── .python-version          # Python version (3.13)
├── Dockerfile               # Docker container configuration
├── .dockerignore            # Docker build exclusions
├── functions/               # Function implementations (all with in-memory mocks)
│   ├── __init__.py          # Exports all functions to FUNCTION_MAP
│   ├── google_services.py   # Google Sheets, Gmail, Groups, Membership emails
│   ├── salesforce.py        # Salesforce query, create, schema discovery
│   ├── slack.py             # Slack channels, users, messages, invitations
│   ├── github.py            # GitHub branches, files, commits, PRs
│   ├── mailing_list.py      # Multi-list mailing system
│   ├── member_desk.py       # Member Desk invitation management
│   ├── support.py           # Zendesk ticketing (in-memory mock)
│   └── web.py               # Firecrawl and Tavily web tools
└── README.md                # This file
```

Parent directory also contains:
```
../
└── docker-compose.yml       # Docker Compose orchestration
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:9999/docs`
- ReDoc: `http://localhost:9999/redoc`
- API Overview: `http://localhost:9999/`

## Example Usage

### Execute Functions via API

```python
import requests
import json

BASE_URL = "http://localhost:9999"

def call_function(category, function_name, **parameters):
    """Helper to call any function"""
    response = requests.post(
        f"{BASE_URL}/{category}/{function_name}",
        json=parameters
    )
    return response.json()

# Example 1: Append to Google Sheets
result = call_function(
    "google_services",
    "google_sheets_append",
    sheet_id="member-tracker",
    range="Sheet1!A1",
    values=[["Name", "Email"], ["John", "john@example.com"]]
)
print(result)
# {
#   "function_name": "google_sheets_append",
#   "result": '{"success": true, "message": "Appended 2 rows...", "rows_added": 2}',
#   "success": true
# }

# Parse the inner result
inner_result = json.loads(result["result"])
print(f"Success: {inner_result['success']}, Rows: {inner_result['rows_added']}")

# Example 2: Send Slack message
result = call_function(
    "slack",
    "slack_send_message",
    channel_id="C001",
    text="Hello from the API!"
)

# Example 3: Create GitHub PR
result = call_function(
    "github",
    "github_create_pr",
    owner="myorg",
    repo="main-app",
    title="New Feature",
    head="feature-branch",
    base="main",
    body="Description"
)

# Example 4: Query Salesforce
result = call_function(
    "salesforce",
    "salesforce_query",
    query="SELECT Id, Name, Email FROM Contact WHERE Email LIKE '%@acme.com%' LIMIT 5"
)
```

### Query the Registry

```python
# List all functions
response = requests.get(f"{BASE_URL}/functions")
data = response.json()
print(f"Total: {data['total']}, Returned: {data['returned']}")

# List with pagination
response = requests.get(f"{BASE_URL}/functions?limit=10&offset=0")
first_10 = response.json()

# Get a specific function
response = requests.get(f"{BASE_URL}/functions/google_sheets_append")
function = response.json()
print(function['name'], function['description'], function['parameters'])

# Search for functions
response = requests.get(f"{BASE_URL}/search?q=email")
results = response.json()
print(f"Found {results['total']} functions matching 'email'")

# Get functions by category
response = requests.get(f"{BASE_URL}/functions/category/google_services")
google_functions = response.json()

# Get all categories
response = requests.get(f"{BASE_URL}/categories")
categories = response.json()
```

## Function Implementations

All functions are implemented with **in-memory mocks** for development and testing. Each function returns a JSON string with a standardized `"success"` field.

### Using Functions Directly

```python
from functions import FUNCTION_MAP
import json

# Get a function from the map
func = FUNCTION_MAP["google_sheets_append"]
result_str = func(
    sheet_id="abc123",
    range="Sheet1!A1",
    values=[["Name", "Email"], ["John", "john@example.com"]]
)

# Parse the JSON result
result = json.loads(result_str)
print(result["success"])  # True
print(result["message"])  # "Appended 2 rows..."

# Direct import also works
from functions.slack import slack_send_message
result_str = slack_send_message(channel_id="C001", text="Hello, World!")
```

### Testing Functions

```bash
# Test with curl
curl -X POST "http://localhost:9999/google_services/google_sheets_read" \
  -H "Content-Type: application/json" \
  -d '{"sheet_id": "test-sheet", "range": "A1:B10"}'

# Test Salesforce query
curl -X POST "http://localhost:9999/salesforce/salesforce_query" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT Id, Name FROM Account LIMIT 5"}'

# Test search
curl "http://localhost:9999/search?q=google&limit=5"
```

## Environment Variables

Some functions require API keys via environment variables:

- `FIRECRAWL_API_KEY` - For Firecrawl web scraping/search
- `TAVILY_API_KEY` - For Tavily web search

Set them before running:
```bash
export FIRECRAWL_API_KEY="your-key"
export TAVILY_API_KEY="your-key"
uv run python main.py
```

Or with Docker:
```bash
# Set in docker-compose.yml or pass via command line
docker run -e FIRECRAWL_API_KEY=your-key -p 9999:9999 function-registry
```

## Mock Data

The in-memory mocks include sample data for:
- **Google Sheets**: Empty sheets that persist data during server runtime
- **Google Groups**: Pre-populated groups with members
- **Gmail**: Email history tracking
- **Salesforce**: Sample Accounts, Contacts, Opportunities, Leads
- **Slack**: Channels, users, and message history
- **GitHub**: Repositories with branches and files
- **Mailing Lists**: Multiple list support with member tracking
- **Member Desk**: Invitation tracking
- **Zendesk**: Sample support tickets

Data resets on server restart.

## Next Steps

To implement real integrations:

1. Replace in-memory mocks with actual API clients (Google API, Slack SDK, etc.)
2. Add authentication/credential management per function
3. Implement database persistence for state
4. Add rate limiting and API key rotation
5. Implement comprehensive logging and monitoring
6. Add webhook support for async operations
7. Implement retry logic and circuit breakers

