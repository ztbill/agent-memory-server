# Memory Extraction Performance Issue

## 思路
- 获取前N条
- 注入已经总结过的上一轮记忆信息

## Issue: Full Conversation Re-processing in Trailing-edge Extraction

**Date:** 2026-04-05  
**Status:** Open  
**Priority:** Medium  
**Reference:** `extract_memories_from_session_thread` in `long_term_memory.py`

---

## Problem Description

When extracting memories using the trailing-edge extraction flow, the system processes the **entire conversation history** on every extraction trigger, even when only a few new messages need to be processed.

### Current Flow

```
User has 100 messages in working memory
    ↓
User sends new message (message 101)
    ↓
Trigger: run_delayed_extraction (debounce after user stops typing)
    ↓
1. get_working_memory() → fetches all 101 messages
2. Filter unextracted_messages → all 101 are "f" (first extraction)
3. Call extract_memories_from_session_thread()
       ↓
       4. get_working_memory() AGAIN → fetches all 101 messages
       5. Build full_conversation → "[USER]: msg1\n[ASSISTANT]: msg2\n...\n[USER]: msg101"
       6. Send to LLM → processes ALL 101 messages
```

### Issues Identified

| Issue | Description |
|-------|-------------|
| **Redundant fetch** | `run_delayed_extraction` and `extract_memories_from_session_thread` both call `get_working_memory()` |
| **Full context always sent** | Even 1 new message triggers sending all 100+ messages to LLM |
| **No upper limit** | `extract_memories_from_session_thread` accepts no `recent_messages_limit` parameter |
| **O(n) cost growth** | LLM token cost grows linearly with conversation length |

---

## Impact

1. **Token Cost**: Wasted tokens on re-processing historical messages
2. **Latency**: Longer extraction times as conversation grows
3. **LLM Context Overflow**: Potential context window overflow for very long conversations

---

## Expected Behavior

The extraction should:

1. **Pass only necessary context**: Recent N extracted messages (for grounding) + new unextracted messages
2. **Avoid redundant fetches**: Single fetch of working memory
3. **Have an upper bound**: Configurable limit on context size

### Ideal Flow

```python
# In run_delayed_extraction or extract_memories_from_session_thread:

# 1. Fetch working memory ONCE
working_memory = await get_working_memory(session_id=session_id, ...)

# 2. Separate messages by extraction status
unextracted = [msg for msg in working_memory.messages if msg.discrete_memory_extracted == "f"]
recent_extracted = [msg for msg in working_memory.messages if msg.discrete_memory_extracted == "t"][-10:]  # Last 10 for context

# 3. Build context from only necessary messages
context_messages = recent_extracted + unextracted

# 4. Pass to LLM for extraction
memories_data = await strategy.extract_memories(build_conversation(context_messages))
```

---

## Code Locations

### Primary Issue

**File:** `agent_memory_server/long_term_memory.py`  
**Function:** `extract_memories_from_session_thread` (line 419)

```python
# Line 440-443: Fetches ALL messages without limit
working_memory = await get_working_memory(
    session_id=session_id, namespace=namespace, user_id=user_id
)

# Line 449-458: Builds full conversation from ALL messages
for msg in working_memory.messages:  # No filtering!
    conversation_messages.append(f"{role_prefix}{msg.content}")
```

### Secondary Issue

**File:** `agent_memory_server/long_term_memory.py`  
**Function:** `run_delayed_extraction` (line 300)

```python
# Line 352-354: First fetch of all messages
working_memory = await get_working_memory(session_id=session_id, ...)

# Line 377-381: Calls extract_memories_from_session_thread which fetches AGAIN
extracted_memories = await extract_memories_from_session_thread(
    session_id=session_id, ...
)
```

---

## Related Documentation

- [Contextual Grounding](contextual-grounding.md) - Context resolution logic
- [Task Processing Principle](task-processing-principle.md) - Background task architecture
- [Memory Extraction Strategies](memory-extraction-strategies.md) - Strategy prompt design

---

## Potential Solutions

### Option 1: Sliding Window Context (Recommended)

Pass only:
- Last N extracted messages (for contextual grounding)
- All unextracted messages (for extraction)

### Option 2: Incremental Extraction

Process only unextracted messages, with recent extracted messages as context.

### Option 3: Configurable Limit

Add `max_context_messages` parameter to control context size.

---

## Notes

The contextual grounding logic itself is correct - LLM can properly resolve pronouns and temporal references when given full conversation. The issue is purely about efficiency and cost optimization.
