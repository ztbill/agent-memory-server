---
name: redis-agent-memory-cli
description: Redis Agent Memory CLI for managing persistent AI agent memory. Use when asked to 'remember this', 'save conversation', 'query memories', 'search long-term memory', 'manage working memory', 'add message to session', or any memory-related operations with the Redis-based agent memory server. Also use proactively to preserve important dialogue context and enable semantic search across conversations.
---

# Redis Agent Memory CLI Skill

Persistent conversational memory management using Redis-based agent memory server.

## Proactive Usage

Save memories when discovering valuable dialogue:
- Important decisions or commitments made in conversation
- Complex information that may be referenced later
- Context from long discussions worth preserving
- Solutions to problems that took effort to uncover

Check memories before:
- Answering questions about past conversations
- Resuming work from previous sessions
- Building on earlier discussion topics

## Quick Start

```bash
# Add a message to working memory
python scripts/cli_memory.py add-message --session-id "my-session" --role "user" --content "I prefer dark mode"

# Create a long-term memory
python scripts/cli_memory.py create-memory --id "mem-001" --text "User prefers dark mode in all applications"

# Search long-term memories
python scripts/cli_memory.py search --query "What are user preferences?"

# Get working memory
python scripts/cli_memory.py get-session --session-id "my-session"
```

## Configuration

The CLI uses environment variables or a config file for server connection:

```bash
# Option 1: Environment variables
export AGENT_MEMORY_BASE_URL=http://localhost:8000
export AGENT_MEMORY_API_KEY=your-api-key  # optional, for production

# Option 2: Config file (copy from config.py.example)
cp config.py.example config.py
# Edit config.py with your settings
```

## Operations

### Working Memory Operations

#### Add Message to Session

```bash
python scripts/cli_memory.py add-message \
  --session-id "my-session" \
  --role "user" \
  --content "I love pizza"
```

With additional options:
```bash
python scripts/cli_memory.py add-message \
  --session-id "my-session" \
  --role "assistant" \
  --content "Great, I'll remember that" \
  --user-id "user123" \
  --namespace "chat"
```

#### Set Working Memory (Batch)

```bash
python scripts/cli_memory.py set-working-memory \
  --session-id "my-session" \
  --messages '[{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there"}]'
```

#### Get Working Memory

```bash
python scripts/cli_memory.py get-session --session-id "my-session"
```

With filtering:
```bash
python scripts/cli_memory.py get-session \
  --session-id "my-session" \
  --user-id "user123" \
  --namespace "chat" \
  --model-name "gpt-4o-mini"
```

#### Delete Working Memory

```bash
python scripts/cli_memory.py delete-session --session-id "my-session"
```

#### List Sessions

```bash
python scripts/cli_memory.py list-sessions
```

### Long-term Memory Operations

#### Create Long-term Memory

```bash
python scripts/cli_memory.py create-memory \
  --id "mem-001" \
  --text "User prefers dark mode in all applications" \
  --user-id "user123"
```

With full options:
```bash
python scripts/cli_memory.py create-memory \
  --id "mem-002" \
  --text "User met with Bob on January 15th, 2024" \
  --memory-type "episodic" \
  --event-date "2024-01-15T00:00:00Z" \
  --topics "meeting,social" \
  --entities "Bob" \
  --namespace "work" \
  --user-id "user123" \
  --session-id "session-001"
```

#### Search Long-term Memory

```bash
python scripts/cli_memory.py search \
  --query "What are user preferences?" \
  --user-id "user123"
```

With filters:
```bash
python scripts/cli_memory.py search \
  --query "meeting notes" \
  --user-id "user123" \
  --namespace "work" \
  --memory-type "episodic" \
  --topics "meeting" \
  --limit 20 \
  --search-mode "hybrid"
```

#### Get Long-term Memory by ID

```bash
python scripts/cli_memory.py get-memory --memory-id "mem-001"
```

#### Update Long-term Memory

```bash
python scripts/cli_memory.py update-memory \
  --memory-id "mem-001" \
  --text "Updated text" \
  --topics "updated-topic"
```

#### Delete Long-term Memory

```bash
python scripts/cli_memory.py delete-memories --memory-ids "mem-001" "mem-002"
```

#### Compact Long-term Memories

```bash
python scripts/cli_memory.py compact-memories \
  --user-id "user123" \
  --namespace "chat"
```

### Memory Prompt Operations

#### Get Memory Context for Query

```bash
python scripts/cli_memory.py memory-prompt \
  --query "What did we discuss about meetings?" \
  --session-id "my-session" \
  --user-id "user123" \
  --namespace "chat"
```

With long-term search:
```bash
python scripts/cli_memory.py memory-prompt \
  --query "What's my preference for meetings?" \
  --session-id "my-session" \
  --long-term-search \
  --user-id "user123"
```

### Summary View Operations

#### Create Summary View

```bash
python scripts/cli_memory.py create-summary-view \
  --name "user-preferences" \
  --source "long_term" \
  --group-by "user_id" \
  --filters '{"memory_type": "semantic"}'
```

#### List Summary Views

```bash
python scripts/cli_memory.py list-summary-views
```

#### Run Summary View

```bash
python scripts/cli_memory.py run-summary-view --view-id "view-001"
```

### Task Operations

#### Get Task Status

```bash
python scripts/cli_memory.py get-task --task-id "task-001"
```

## Configuration Options

| Environment Variable | Config Key | Description | Default |
|---|---|---|---|
| `AGENT_MEMORY_BASE_URL` | `base_url` | Server base URL | `http://localhost:8000` |
| `AGENT_MEMORY_API_KEY` | `api_key` | API key for authentication | None (dev mode) |
| `AGENT_MEMORY_TIMEOUT` | `timeout` | Request timeout in seconds | 30 |

## Data Formats

### Memory Types

- `semantic`: User preferences, facts, general knowledge
- `episodic`: Specific events, experiences with time dimension
- `message`: Raw conversation messages

### Search Modes

- `semantic`: Vector-based similarity search (default)
- `keyword`: Full-text search using BM25
- `hybrid`: Combination of semantic and keyword

## Advanced Usage

For detailed information:
- **API Reference**: [references/api-reference.md](references/api-reference.md)
- **Architecture Details**: [references/architecture.md](references/architecture.md)
- **Configuration**: See `config.py.example`

## Setup

**Install dependencies** (if not already installed):

```bash
pip install requests ulid
```

**Configure the CLI**:

```bash
# Copy and edit config
cp config.py.example config.py
# Edit config.py with your server URL and optional API key
```

**Test the connection**:

```bash
python scripts/cli_memory.py list-sessions
```

## Development Notes

This skill uses direct HTTP API calls instead of the Python client library, providing:
- No dependency on the client package
- Direct control over API interactions
- Easy debugging and customization
- Lightweight integration for scripts and tools