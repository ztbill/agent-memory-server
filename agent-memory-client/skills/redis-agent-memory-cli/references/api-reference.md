# Redis Agent Memory Server API Reference

This document provides a comprehensive reference for the Redis Agent Memory Server REST API.

## Base URL

```
http://localhost:8000
```

## Authentication

### Development Mode
Set `DISABLE_AUTH=true` to disable authentication for local development.

### Production Mode
Use JWT Bearer token authentication:
```bash
curl -H "Authorization: Bearer <your-token>" ...
```

## Endpoints Overview

| Category | Endpoint | Method | Description |
|---|---|---|---|
| Working Memory | `/v1/working-memory/` | GET | List all sessions |
| Working Memory | `/v1/working-memory/{session_id}` | GET | Get working memory |
| Working Memory | `/v1/working-memory/{session_id}` | PUT | Set working memory |
| Working Memory | `/v1/working-memory/{session_id}` | DELETE | Delete working memory |
| Long-term Memory | `/v1/long-term-memory/` | POST | Create memory |
| Long-term Memory | `/v1/long-term-memory/search` | POST | Search memories |
| Long-term Memory | `/v1/long-term-memory/{memory_id}` | GET | Get memory by ID |
| Long-term Memory | `/v1/long-term-memory/{memory_id}` | PATCH | Update memory |
| Long-term Memory | `/v1/long-term-memory` | DELETE | Delete memories |
| Long-term Memory | `/v1/long-term-memory/compact` | POST | Compact memories |
| Memory Prompt | `/v1/memory/prompt` | POST | Get hydrated prompt |
| Summary Views | `/v1/summary-views` | GET/POST | List/create summary views |
| Tasks | `/v1/tasks/{task_id}` | GET | Get task status |

---

## Working Memory API

### List Sessions

Get a list of session IDs with optional pagination and filtering.

**Endpoint:** `GET /v1/working-memory/`

**Query Parameters:**
| Parameter | Type | Description | Default |
|---|---|---|---|
| `limit` | int | Maximum results | 20 |
| `offset` | int | Pagination offset | 0 |
| `namespace` | string | Filter by namespace | None |
| `user_id` | string | Filter by user ID | None |

**Response:**
```json
{
  "sessions": ["session-1", "session-2"],
  "total": 2
}
```

---

### Get Working Memory

Retrieve working memory for a session including messages and context.

**Endpoint:** `GET /v1/working-memory/{session_id}`

**Query Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `user_id` | string | User ID for the session |
| `namespace` | string | Namespace for the session |
| `model_name` | string | LLM model name (determines context window) |
| `context_window_max` | int | Override context window max tokens |
| `recent_messages_limit` | int | Limit number of recent messages |

**Response:**
```json
{
  "session_id": "my-session",
  "messages": [
    {"id": "msg-1", "role": "user", "content": "Hello", "created_at": "..."}
  ],
  "memories": [],
  "context": null,
  "user_id": "user123",
  "namespace": "chat",
  "tokens": 10,
  "context_percentage_total_used": 0.05,
  "context_percentage_until_summarization": 0.2
}
```

---

### Set Working Memory

Set or update working memory for a session. Replaces existing memory.

**Endpoint:** `PUT /v1/working-memory/{session_id}`

**Request Body:**
```json
{
  "messages": [
    {
      "role": "user" | "assistant" | "system",
      "content": "Message content",
      "id": "optional-message-id",
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "memories": [
    {
      "id": "mem-001",
      "text": "Memory text",
      "topics": ["topic1"],
      "entities": ["entity1"],
      "memory_type": "semantic"
    }
  ],
  "user_id": "user123",
  "namespace": "chat",
  "data": {"key": "value"},
  "long_term_memory_strategy": {
    "strategy": "discrete" | "summary" | "preferences" | "custom",
    "config": {}
  }
}
```

**Response:** Returns updated working memory with context usage percentages.

---

### Delete Working Memory

Delete all working memory data for a session.

**Endpoint:** `DELETE /v1/working-memory/{session_id}`

**Query Parameters:**
| Parameter | Type | Description |
|---|---|---|
| `user_id` | string | User ID for the session |
| `namespace` | string | Namespace for the session |

**Response:**
```json
{"status": "ok"}
```

---

## Long-term Memory API

### Create Long-term Memory

Create persistent memory records for semantic search.

**Endpoint:** `POST /v1/long-term-memory/`

**Request Body:**
```json
{
  "memories": [
    {
      "id": "mem-001",
      "text": "User prefers dark mode in all applications",
      "memory_type": "semantic" | "episodic" | "message",
      "topics": ["preferences", "UI"],
      "entities": [],
      "namespace": "chat",
      "user_id": "user123",
      "session_id": "session-001",
      "event_date": "2024-01-15T00:00:00Z",
      "pinned": false,
      "extracted_from": ["msg-001"]
    }
  ],
  "deduplicate": true
}
```

**Response:**
```json
{"status": "ok"}
```

**Notes:**
- Memory indexing happens asynchronously in background
- `id` is required for each memory
- Set `deduplicate: false` to skip hash-based deduplication

---

### Search Long-term Memory

Search memories using semantic, keyword, or hybrid search.

**Endpoint:** `POST /v1/long-term-memory/search`

**Request Body:**
```json
{
  "text": "What are user preferences?",
  "search_mode": "semantic" | "keyword" | "hybrid",
  "hybrid_alpha": 0.7,
  "limit": 10,
  "offset": 0,
  "namespace": {"eq": "chat"},
  "user_id": {"eq": "user123"},
  "session_id": {"ne": "current-session"},
  "memory_type": {"eq": "semantic"},
  "topics": {"any": ["preferences", "UI"]},
  "entities": {"any": ["dark-mode"]},
  "distance_threshold": 0.5,
  "recency_boost": true,
  "recency_semantic_weight": 0.8,
  "recency_recency_weight": 0.2
}
```

**Filter Syntax:**
| Operator | Description | Example |
|---|---|---|
| `eq` | Equals | `{"eq": "value"}` |
| `ne` | Not equals | `{"ne": "value"}` |
| `any` | Contains any | `{"any": ["a", "b"]}` |
| `all` | Contains all | `{"all": ["a", "b"]}` |

**Response:**
```json
{
  "memories": [
    {
      "id": "mem-001",
      "text": "User prefers dark mode",
      "dist": 0.15,
      "score": 0.85,
      "score_type": "semantic",
      "topics": ["preferences"],
      "entities": [],
      "created_at": "2024-01-15T...",
      "last_accessed": "2024-01-15T...",
      "memory_type": "semantic"
    }
  ],
  "total": 1,
  "next_offset": null
}
```

---

### Get Long-term Memory by ID

Retrieve a specific memory record.

**Endpoint:** `GET /v1/long-term-memory/{memory_id}`

**Response:**
```json
{
  "id": "mem-001",
  "text": "User prefers dark mode",
  "memory_type": "semantic",
  "topics": ["preferences"],
  "entities": [],
  "namespace": "chat",
  "user_id": "user123",
  "session_id": "session-001",
  "created_at": "2024-01-15T...",
  "updated_at": "2024-01-15T...",
  "last_accessed": "2024-01-15T...",
  "pinned": false,
  "access_count": 5
}
```

---

### Update Long-term Memory

Update specific fields of a memory record.

**Endpoint:** `PATCH /v1/long-term-memory/{memory_id}`

**Request Body:**
```json
{
  "text": "Updated text",
  "topics": ["updated-topic"],
  "entities": ["new-entity"],
  "memory_type": "semantic",
  "namespace": "new-namespace",
  "user_id": "new-user",
  "session_id": "new-session",
  "pinned": true
}
```

**Response:** Returns updated memory record.

---

### Delete Long-term Memories

Delete memories by IDs.

**Endpoint:** `DELETE /v1/long-term-memory`

**Query Parameters:**
| Parameter | Description |
|---|---|
| `memory_ids` | Comma-separated list of memory IDs |

**Response:**
```json
{"status": "ok, deleted 5 memories"}
```

---

### Compact Long-term Memories

Merge duplicate memories based on content hash.

**Endpoint:** `POST /v1/long-term-memory/compact`

**Query Parameters:**
| Parameter | Description |
|---|---|
| `namespace` | Optional namespace filter |
| `user_id` | Optional user ID filter |

**Response:**
```json
{"status": "ok, 100 memories remaining after compaction"}
```

---

## Memory Prompt API

### Get Memory Context

Hydrate a query with working memory and/or long-term memory context for LLM consumption.

**Endpoint:** `POST /v1/memory/prompt`

**Request Body:**
```json
{
  "query": "What did we discuss about meetings?",
  "session": {
    "session_id": "my-session",
    "user_id": "user123",
    "namespace": "chat",
    "model_name": "gpt-4o-mini",
    "context_window_max": 100000
  },
  "long_term_search": {
    "text": "meeting notes",
    "limit": 20,
    "user_id": {"eq": "user123"},
    "namespace": {"eq": "chat"}
  }
}
```

**Notes:**
- Either `session` or `long_term_search` must be provided
- `long_term_search` can be `true` for default search settings

**Response:**
```json
{
  "messages": [
    {"role": "system", "content": "## A summary of the conversation so far:\n..."},
    {"role": "user", "content": "Previous message..."},
    {"role": "assistant", "content": "Previous response..."},
    {"role": "system", "content": "## Long term memories related to the user's query\n- Memory 1 (ID: mem-001)\n- Memory 2 (ID: mem-002)"},
    {"role": "user", "content": "What did we discuss about meetings?"}
  ],
  "long_term_memories": [...]
}
```

---

## Summary View API

### Create Summary View

Create a configuration for summarizing memories.

**Endpoint:** `POST /v1/summary-views`

**Request Body:**
```json
{
  "name": "user-preferences",
  "source": "long_term",
  "group_by": ["user_id", "namespace"],
  "filters": {"memory_type": "semantic"},
  "time_window_days": 30,
  "continuous": false,
  "prompt": "Summarize user preferences...",
  "model_name": "gpt-4o-mini"
}
```

**Supported `group_by` values:** `user_id`, `namespace`, `session_id`, `memory_type`

**Response:** Returns created summary view with server-assigned ID.

---

### List Summary Views

Get all registered summary views.

**Endpoint:** `GET /v1/summary-views`

**Response:** Array of summary view configurations.

---

### Get Summary View

Get a specific summary view by ID.

**Endpoint:** `GET /v1/summary-views/{view_id}`

---

### Delete Summary View

Delete a summary view configuration.

**Endpoint:** `DELETE /v1/summary-views/{view_id}`

---

### Run Summary View

Trigger asynchronous full recompute of a summary view.

**Endpoint:** `POST /v1/summary-views/{view_id}/run`

**Request Body:**
```json
{
  "task_id": "optional-custom-task-id"
}
```

**Response:** Returns task object for status tracking.

---

### Get Summary View Partitions

List materialized partition summaries.

**Endpoint:** `GET /v1/summary-views/{view_id}/partitions`

**Query Parameters:**
| Parameter | Description |
|---|---|
| `user_id` | Filter by user ID |
| `namespace` | Filter by namespace |
| `session_id` | Filter by session ID |
| `memory_type` | Filter by memory type |

---

## Task API

### Get Task Status

Get the status of a background task.

**Endpoint:** `GET /v1/tasks/{task_id}`

**Response:**
```json
{
  "id": "task-001",
  "type": "summary_view_full_run",
  "status": "pending" | "running" | "success" | "failed",
  "view_id": "view-001",
  "created_at": "2024-01-15T...",
  "started_at": "2024-01-15T...",
  "completed_at": "2024-01-15T...",
  "error_message": null
}
```

---

## Data Models

### MemoryMessage

```python
{
    "role": "user" | "assistant" | "system",
    "content": "Message content",
    "id": "message-id",
    "created_at": "2024-01-15T10:00:00Z"
}
```

### MemoryRecord

```python
{
    "id": "mem-001",
    "text": "Memory text content",
    "session_id": "session-001",
    "user_id": "user123",
    "namespace": "chat",
    "memory_type": "semantic" | "episodic" | "message",
    "topics": ["topic1", "topic2"],
    "entities": ["entity1", "entity2"],
    "event_date": "2024-01-15T00:00:00Z",
    "pinned": false,
    "created_at": "2024-01-15T...",
    "updated_at": "2024-01-15T...",
    "last_accessed": "2024-01-15T...",
    "access_count": 0
}
```

### SearchModeEnum

| Value | Description |
|---|---|
| `semantic` | Vector-based similarity search (default) |
| `keyword` | Full-text search using BM25 |
| `hybrid` | Combined semantic + keyword |

### MemoryTypeEnum

| Value | Description |
|---|---|
| `semantic` | User preferences, facts, general knowledge |
| `episodic` | Specific events with time dimension |
| `message` | Raw conversation messages |

---

## Error Responses

### 400 Bad Request
```json
{"detail": "Error message describing the issue"}
```

### 404 Not Found
```json
{"detail": "Session/Memory not found"}
```

### 401 Unauthorized
```json
{"detail": "Not authenticated"}
```

### 500 Internal Server Error
```json
{"detail": "Internal server error"}
```

---

## Rate Limits

Default rate limits (configurable):
- 1000 requests per minute for authenticated users
- 60 requests per minute for unauthenticated requests

---

## Example Usage

### Python with requests

```python
import requests

BASE_URL = "http://localhost:8000"
HEADERS = {"Content-Type": "application/json"}

# Create memory
response = requests.post(
    f"{BASE_URL}/v1/long-term-memory/",
    headers=HEADERS,
    json={
        "memories": [{
            "id": "mem-001",
            "text": "User prefers dark mode"
        }]
    }
)
print(response.json())
```

### cURL

```bash
# Create memory
curl -X POST http://localhost:8000/v1/long-term-memory/ \
  -H "Content-Type: application/json" \
  -d '{"memories": [{"id": "mem-001", "text": "User prefers dark mode"}]}'

# Search memories
curl -X POST http://localhost:8000/v1/long-term-memory/search \
  -H "Content-Type: application/json" \
  -d '{"text": "user preferences", "limit": 10}'
```