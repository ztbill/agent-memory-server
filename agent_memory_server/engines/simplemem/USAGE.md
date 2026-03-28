# SimpleMem Engine Integration Guide

This document explains how to use SimpleMem as the long-term memory engine for agent-memory-server.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        API Layer (api.py)                        │
│  /v1/long-term-memory/create, /search, /promote, etc.          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  long_term_memory.py                           │
│  - extract_memories_from_session_thread                         │
│  - search_long_term_memories                                    │
│  - create_long_term_memory                                      │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ SimpleMemEngine │  │ MemoryVectorDB │  │  Working Memory │
│                 │  │   (RedisVL)    │  │   (Redis)       │
│ - MemoryBuilder │  │                │  │                 │
│ - HybridRetriever│  │                │  │                 │
│ - AnswerGenerator│ │                │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Integration Points

### 1. Memory Extraction (Write Path)

Current flow:
```
Working Memory → extract_memories_from_session_thread → create_long_term_memory
```

With SimpleMem:
```
Working Memory → SimpleMemEngine.add_dialogue() → process → VectorStore (RedisVL)
                                              ↓
                                    MemoryRecord (via add_memory_native)
```

### 2. Memory Search (Read Path)

Current flow:
```
SearchRequest → search_long_term_memories → MemoryVectorDB.search_memories
```

With SimpleMem:
```
Query → SimpleMemEngine.retrieve() → HybridRetriever → VectorStore (RedisVL)
```

## Usage Patterns

### Pattern 1: Direct SimpleMem Engine Usage

```python
from agent_memory_server.engines.simplemem import SimpleMemEngine

# Create engine instance
engine = SimpleMemEngine(namespace="my_app", user_id="user123")

# === Memory Extraction (Write) ===

# Add dialogues for extraction
engine.add_dialogue(
    speaker="Alice",
    content="Let's meet at Starbucks tomorrow at 2pm to discuss the project",
    timestamp="2025-01-15T10:00:00"
)

engine.add_dialogue(
    speaker="Bob",
    content="Sure, I'll bring the design mockups",
    timestamp="2025-01-15T10:05:00"
)

# Process remaining dialogues
engine.process_remaining()

# === Memory Search (Read) ===

# Hybrid retrieval with reflection
results = engine.retrieve("When and where is the meeting?")

# Simple semantic search
results = engine.search("meeting", search_mode="semantic", top_k=5)

# Keyword search
results = engine.search("meeting", search_mode="keyword", top_k=5)

# === Generate Answer ===

answer = engine.generate_answer("When and where is the meeting?")
```

### Pattern 2: Mixed Usage (SimpleMem + Native)

```python
from agent_memory_server.engines.simplemem import SimpleMemEngine
import asyncio

engine = SimpleMemEngine(namespace="my_app", user_id="user123")

# Use SimpleMem for extraction
engine.add_dialogue(speaker="Alice", content="I prefer dark mode")
engine.process_remaining()

# Use native API for direct memory operations
async def search_memories():
    # Native search (returns MemoryRecordResults)
    native_results = await engine.search_native(
        query="preferences",
        search_mode="semantic",
        limit=10
    )
    return native_results

# Add memory directly via native method
async def add_memory():
    memory_id = await engine.add_memory_native(
        text="User likes coffee",
        topics=["preference", "drinks"],
        entities=[]
    )
    return memory_id
```

### Pattern 3: API Integration (Recommended for Production)

For production use, integrate SimpleMem into the API flow:

```python
# In your custom API endpoint
from agent_memory_server.engines.simplemem import SimpleMemEngine
from agent_memory_server.working_memory import get_working_memory

async def extract_session_with_simplemem(session_id: str, namespace: str = None):
    """Extract memories from session using SimpleMem."""
    
    # Get working memory
    working_memory = await get_working_memory(
        session_id=session_id, 
        namespace=namespace
    )
    
    # Create SimpleMem engine
    engine = SimpleMemEngine(namespace=namespace or "default")
    
    # Convert messages to dialogues
    for msg in working_memory.messages:
        engine.add_dialogue(
            speaker=msg.role,
            content=msg.content,
            timestamp=msg.created_at.isoformat() if msg.created_at else None,
            auto_process=False
        )
    
    # Process all dialogues
    engine.process_remaining()
    
    return {"status": "extracted", "count": engine.memory_builder.processed_count}
```

### Pattern 4: Custom Extraction with LLM Only

If you only want to use SimpleMem's extraction logic without storage:

```python
from agent_memory_server.engines.simplemem.adapters.llm_client import LLMClientAdapter
from agent_memory_server.engines.simplemem.adapters.memory_entry import Dialogue, SimpleMemMemoryEntry

# Use LLM adapter directly
llm = LLMClientAdapter()

# Build prompt for extraction
dialogue = Dialogue(
    dialogue_id=1,
    speaker="Alice",
    content="Meeting at 2pm tomorrow",
    timestamp="2025-01-15T10:00:00"
)

# Custom extraction logic using SimpleMem's prompt template
builder = SimpleMemEngine(namespace="test")
entries = builder.memory_builder._generate_memory_entries([dialogue])

print(entries[0].lossless_restatement)
```

## Configuration

### Engine Parameters

```python
SimpleMemEngine(
    namespace="my_app",           # Namespace for memory isolation
    user_id="user123",            # User ID for multi-tenant
    
    # Memory Builder settings
    window_size=10,               # Dialogues per window
    enable_parallel_processing=True,
    max_parallel_workers=3,
    
    # Hybrid Retriever settings
    semantic_top_k=5,
    keyword_top_k=3,
    structured_top_k=3,
    enable_planning=True,          # Query planning
    enable_reflection=True,       # Self-reflection for better results
    max_reflection_rounds=2,
    enable_parallel_retrieval=True,
    max_retrieval_workers=3,
)
```

### Environment Variables

SimpleMem uses these settings from `agent_memory_server.config`:

```bash
# LLM settings (used by SimpleMem)
GENERATION_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# SimpleMem-specific settings
WINDOW_SIZE=10
OVERLAP_SIZE=0
USE_JSON_FORMAT=false
ENABLE_PARALLEL_PROCESSING=true
MAX_PARALLEL_WORKERS=4
SEMANTIC_TOP_K=5
KEYWORD_TOP_K=3
STRUCTURED_TOP_K=3
ENABLE_PLANNING=true
ENABLE_REFLECTION=true
MAX_REFLECTION_ROUNDS=2
ENABLE_PARALLEL_RETRIEVAL=true
MAX_RETRIEVAL_WORKERS=3
```

## Storage

All SimpleMem memories are stored in the same RedisVL index as native agent-memory-server memories:

- **Namespace**: Configurable (default: "simplemem")
- **User ID**: Optional, for multi-tenant isolation
- **Topics**: Extracted from `topic` field
- **Entities**: Extracted from `entities` field

This means you can search across both SimpleMem-extracted and natively-created memories using either:
- `SimpleMemEngine.search()` - SimpleMem's hybrid retrieval
- `engine.search_native()` - Native agent-memory-server search

## Best Practices

1. **Use namespaces** to separate different applications or use cases
2. **Enable reflection** for complex queries that need multi-step reasoning
3. **Tune top_k** values based on your use case:
   - Higher for exploratory searches
   - Lower for precise fact retrieval
4. **Process in batches** for large dialogue histories using parallel processing
5. **Use both search methods** for comprehensive results - SimpleMem's hybrid + native semantic
