# Draft: SimpleMem Engine Integration

## Requirements (confirmed)
- [user request]: Add SimpleMem engine to agent-memory-server
- Location: `/Users/ztzt/work/code_rpo/agent-memory-server/agent_memory_server/engines/simplemem/`
- Copy from: `/Users/ztzt/work/code_rpo/SimpleMem/core`
- Use agent-memory-server's LLM client instead of SimpleMem's LLMClient
- Use agent-memory-server's MemoryRecord instead of SimpleMem's MemoryEntry
- Use agent-memory-server's RedisVL storage instead of LanceDB
- Minimize code modifications

## Technical Decisions
- [DECISION NEEDED]: What is the intended integration point?
  - Option A: Standalone engine that can be invoked directly
  - Option B: Memory extraction strategy (like DiscreteMemoryStrategy)
  - Option C: Complete replacement for long-term memory
- [DECISION NEEDED]: How should the existing simplemem code be handled?
  - There's already files in engines/simplemem/core/ with imports like:
    - `from models.memory_entry import MemoryEntry`
    - `from utils.llm_client import LLMClient`
    - `from database.vector_store import VectorStore`
  - These imports don't exist in agent-memory-server - needs mapping

## Research Findings
- **SimpleMem core files**:
  - `/Users/ztzt/work/code_rpo/SimpleMem/core/memory_builder.py` - MemoryBuilder class
  - `/Users/ztzt/work/code_rpo/SimpleMem/core/answer_generator.py` - AnswerGenerator class
  - `/Users/ztzt/work/code_rpo/SimpleMem/core/hybrid_retriever.py` - HybridRetriever class
  - Uses: `utils.llm_client.LLMClient`, `models.memory_entry.MemoryEntry`, `database.vector_store.VectorStore`

- **agent-memory-server equivalents**:
  - LLM: `agent_memory_server.llm.client.LLMClient` (async, LiteLLM-based)
  - Memory model: `agent_memory_server.models.MemoryRecord` (Pydantic model)
  - Storage: `agent_memory_server.memory_vector_db.RedisVLMemoryVectorDatabase` (RedisVL-based)

## Open Questions
1. What's the intended use case for this engine? Direct API usage? MCP tools?
2. Should the existing files in engines/simplemem/core/ be replaced or updated?
3. How should async/sync be handled? (SimpleMem is sync, agent-memory-server is async)
4. What configuration parameters should be exposed?

## Scope Boundaries
- INCLUDE: Copy SimpleMem core logic, adapt to use agent-memory-server components
- EXCLUDE: [to be determined based on user input]
