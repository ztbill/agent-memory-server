# Redis Agent Memory Server Architecture

This document describes the architecture of the Redis Agent Memory Server and how the CLI skill integrates with it.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Redis Agent Memory Server                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐    ┌──────────────────┐                 │
│  │   REST API       │    │   MCP Server     │                 │
│  │   (FastAPI)      │    │   (Model Context │                 │
│  │                  │    │    Protocol)     │                 │
│  └────────┬─────────┘    └────────┬─────────┘                 │
│           │                       │                             │
│           └───────────┬───────────┘                             │
│                       │                                          │
│           ┌───────────▼───────────┐                             │
│           │   Core Memory Logic   │                             │
│           └───────────┬───────────┘                             │
│                       │                                          │
│    ┌──────────────────┼──────────────────┐                     │
│    │                  │                  │                      │
│    ▼                  ▼                  ▼                      │
│ ┌──────────┐   ┌──────────┐    ┌──────────┐                   │
│ │ Working  │   │  Long    │    │  LLM     │                   │
│ │ Memory   │   │  Term    │    │  Client  │                   │
│ │ (Redis)  │   │  Memory  │    │ (LiteLLM)│                   │
│ └──────────┘   └──────────┘    └──────────┘                   │
│                                                                 │
│           ┌─────────────────────────────────────┐               │
│           │         Redis + RedisVL            │               │
│           │    (Vector Search & Storage)        │               │
│           └─────────────────────────────────────┘               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│              redis-agent-memory-cli (Skill)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │   SKILL.md      │    │   CLI Scripts   │                    │
│  │   (Instructions)│    │  (HTTP Client)  │                    │
│  └─────────────────┘    └────────┬────────┘                    │
│                                   │                             │
│                          ┌────────▼────────┐                    │
│                          │   REST API      │                    │
│                          │   (HTTP Calls)  │                    │
│                          └────────┬────────┘                    │
└──────────────────────────────────┼──────────────────────────────┘
                                   │
                                   ▼
                         Redis Agent Memory Server
```

## Two-Tier Memory Architecture

### Working Memory (Session-scoped)

Working memory stores session-specific data in Redis:

- **Messages**: Conversation history with role, content, timestamps
- **Structured Memories**: Memory records to be promoted to long-term storage
- **Context**: Auto-generated summaries when sessions exceed token limits
- **Metadata**: User ID, namespace, token counts, TTL

**Key Features:**
- Automatic summarization when token threshold exceeded
- Token-aware truncation based on LLM context window
- Background promotion of structured memories to long-term storage

**Redis Keys:**
```
working_memory:{session_id}
working_memory:{namespace}:{session_id}
working_memory:{user_id}:{session_id}
```

### Long-term Memory (Persistent)

Long-term memory provides persistent storage with semantic search:

- **Vector Storage**: Embeddings stored in Redis for semantic similarity
- **Metadata Index**: Topics, entities, timestamps, memory types
- **Deduplication**: Hash-based content deduplication
- **Compaction**: Merge similar memories

**Key Features:**
- Semantic, keyword, and hybrid search modes
- Advanced filtering (topics, entities, namespaces, memory types)
- Recency-aware re-ranking
- Automatic topic extraction and entity recognition

**Redis Data Structures:**
- Hash: Memory records with metadata
- Sorted Set: Vector embeddings for semantic search
- Index: RedisVL index for complex queries

## Memory Flow

### Adding a Message

```
CLI ──POST /v1/working-memory/{session_id}──► API ──► Redis
                                                      │
                                                      ▼
                                            ┌─────────────────┐
                                            │  Working Memory │
                                            │  (session data) │
                                            └─────────────────┘
```

### Creating Long-term Memory

```
CLI ──POST /v1/long-term-memory/──────────► API ──► Background Task
                                                      │
                                                      ▼
                                            ┌─────────────────┐
                                            │  Index Memory   │
                                            │  (async)        │
                                            └─────────────────┘
                                                      │
                                                      ▼
                                            ┌─────────────────┐
                                            │  Redis + RedisVL│
                                            │  (vectors)      │
                                            └─────────────────┘
```

### Searching Memories

```
CLI ──POST /v1/long-term-memory/search───► API ──► RedisVL
                                              │     │
                                              │     ▼
                                              │  Semantic/Keyword
                                              │  Search
                                              ▼     │
                                       ┌──────────────┐
                                       │  Search      │
                                       │  Results     │
                                       └──────────────┘
```

### Memory Prompt (Context Hydration)

```
CLI ──POST /v1/memory/prompt────────────► API ──┬─► Working Memory
                                                │     (Redis)
                                                │
                                                └─► Long-term Memory
                                                      (RedisVL)
                                                │
                                                ▼
                                       ┌──────────────┐
                                       │  Hydrated    │
                                       │  Prompt      │
                                       └──────────────┘
```

## CLI Integration Architecture

### Direct HTTP Approach

The CLI uses direct HTTP requests instead of the Python client library:

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Architecture                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  cli_memory.py                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Argument Parsing (argparse)                         │  │
│  │  - Command: add-message, create-memory, search, etc. │  │
│  │  - Options: session-id, user-id, query, etc.        │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                 │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Settings Manager                                    │  │
│  │  - BASE_URL (default: http://localhost:8000)        │  │
│  │  - API_KEY (optional)                               │  │
│  │  - TIMEOUT (default: 30s)                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                 │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  HTTP Client (requests)                               │  │
│  │  - make_request(method, path, data, params)         │  │
│  │  - Automatic JSON encoding/decoding                 │  │
│  │  - Error handling and status code checking          │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                 │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Response Processing                                  │  │
│  │  - JSON output with pretty printing                 │  │
│  │  - Error messages on failure                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Configuration Priority

1. Command-line arguments (highest priority)
2. Environment variables (`AGENT_MEMORY_BASE_URL`, etc.)
3. Config file (`config.py`)
4. Default values (lowest priority)

## Memory Extraction Strategies

The server supports different strategies for extracting memories from working memory:

| Strategy | Description | Use Case |
|---|---|---|
| `discrete` | Extract explicit memory records | General conversations |
| `summary` | Generate summary-focused memories | Long discussions |
| `preferences` | Focus on user preferences | User modeling |
| `custom` | Custom extraction logic | Specialized needs |

## Search Modes

### Semantic Search
- Vector-based similarity using embeddings
- Best for conceptual matches
- Configurable distance threshold

### Keyword Search
- Full-text search using BM25
- Best for exact term matching
- Redis full-text capabilities

### Hybrid Search
- Combines semantic and keyword
- Configurable alpha weight (semantic vs keyword)
- Best of both approaches

## Recency Re-ranking

The system supports recency-aware re-ranking of search results:

- **Freshness**: How recently created
- **Novelty**: Age component (inverse of freshness)
- **Access Frequency**: How often accessed

Configurable via:
- `recency_boost`: Enable/disable re-ranking
- `recency_*_weight`: Weights for each component
- `recency_*_half_life`: Decay parameters in days

## Background Tasks

Long-running operations are handled via background tasks:

- Memory indexing and embedding generation
- Memory compaction and deduplication
- Summary view refresh

Task Status: `pending` → `running` → `success` | `failed`

## Summary Views

Summary views provide aggregated insights over memory collections:

- **Group by**: user_id, namespace, session_id, memory_type
- **Filters**: Apply static filters to each run
- **Time windows**: Limit to recent memories
- **Continuous**: Periodic background refresh

## Security Considerations

### Authentication
- JWT/OAuth2 for production
- Configurable providers: Auth0, AWS Cognito, Okta, Azure AD

### Authorization
- Role-based access control via JWT claims
- Namespace isolation

### Development Mode
- `DISABLE_AUTH=true` for local development
- Never use in production

## Performance Optimization

### Caching
- Redis for fast in-memory access
- Configurable TTL for working memory

### Indexing
- RedisVL for vector search
- Optimized index structures

### Async Processing
- Background task queue (Docket)
- Non-blocking memory promotion

## Monitoring and Health

Health check endpoint: `GET /health`

Returns server status and timestamp.

## Dependencies

### Server
- FastAPI (REST API)
- Redis + RedisVL (Storage & Search)
- LiteLLM (LLM abstraction)
- Pydantic (Data validation)
- ULID (ID generation)

### CLI (Local)
- requests (HTTP client)
- ulid (ID generation)
- json (built-in)
- argparse (built-in)

## Extension Points

### Custom Memory Vector Databases
- Pluggable factory system
- Support for custom backends

### Custom LLM Providers
- LiteLLM supports 100+ providers
- Easy to add new providers

### Custom Extraction Strategies
- Strategy pattern for memory extraction
- Easy to implement custom strategies