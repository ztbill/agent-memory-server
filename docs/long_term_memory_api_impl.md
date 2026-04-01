# Long Term Memory API 详细实现原理分析

## 概述

Long Term Memory 模块是 Redis Agent Memory Server 的核心持久化存储组件，负责语义搜索和长期记忆管理。本文详细分析各个 API 的实现原理和函数调用关系。

---

## 一、核心架构

### 1.1 层次结构

```
┌─────────────────────────────────────────────────────────┐
│                    REST API / MCP                       │
│         (api.py / mcp.py - 端点定义和参数处理)           │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              long_term_memory.py                        │
│         (核心业务逻辑 - 去重、索引、搜索)                │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│         memory_vector_db_factory.py                     │
│              (向量数据库工厂)                            │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              memory_vector_db.py                        │
│      (RedisVL 实现 - 抽象层 + RedisVL 具体实现)         │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│                    Redis Stack                           │
│            (向量索引 + 全文索引 + Hash 存储)            │
└─────────────────────────────────────────────────────────┘
```

### 1.2 关键模块说明

| 模块 | 职责 |
|------|------|
| `long_term_memory.py` | 核心业务逻辑：去重、索引、搜索、提升、删除 |
| `memory_vector_db_factory.py` | 向量数据库工厂，创建 backend 实例 |
| `memory_vector_db.py` | RedisVL 抽象层和具体实现 |
| `filters.py` | 搜索过滤条件构建器 |
| `models.py` | 数据模型定义 |

---

## 二、创建记忆 API (Create)

### 2.1 REST API 端点

**端点**: `POST /v1/long-term-memory/`

**文件**: `api.py:606-642`

```python
@router.post("/v1/long-term-memory/", response_model=AckResponse)
async def create_long_term_memory(
    payload: CreateMemoryRecordRequest,
    background_tasks: HybridBackgroundTasks,
    current_user: UserInfo = Depends(get_current_user),
):
```

### 2.2 调用流程

```
create_long_term_memory (api.py:606)
    │
    ├── [1] 参数验证
    │   └── 检查 id 必填、清除 persisted_at
    │
    └── [2] 提交后台任务
        └── background_tasks.add_task(
            long_term_memory.index_long_term_memories,
            memories=payload.memories,
            deduplicate=payload.deduplicate,
        )
```

### 2.3 核心函数: index_long_term_memories

**文件**: `long_term_memory.py:977-1106`

```python
async def index_long_term_memories(
    memories: list[MemoryRecord | ExtractedMemoryRecord],
    redis_client: Redis | None = None,
    deduplicate: bool = False,
    vector_distance_threshold: float | None = None,
) -> None:
```

**处理流程**:

```
index_long_term_memories
    │
    ├── [1] 过滤无效记忆
    │   └── 过滤空 text 和空 id 的记忆
    │
    ├── [2] 去重处理 (当 deduplicate=True)
    │   ├── deduplicate_by_id - 按 ID 去重
    │   ├── deduplicate_by_hash - 按 hash 去重
    │   └── deduplicate_by_semantic_search - 语义去重
    │
    ├── [3] 向量索引
    │   └── db.add_memories(processed_memories)
    │       │
    │       └── get_memory_vector_db() → RedisVLMemoryVectorDatabase
    │
    └── [4] 后台任务
        ├── extract_memory_structure - 提取 topic/entity   
        └── extract_memories_with_strategy - 策略化提取
```
TODO extract_memory_structure原理解析

### 2.4 底层向量存储

**文件**: `memory_vector_db.py:737-778`

```python
async def add_memories(self, memories: list[MemoryRecord]) -> list[str]:
    # 1. 生成 embedding
    texts = [m.text for m in memories]
    embeddings = await self._embeddings.aembed_documents(texts)
    
    # 2. 准备数据
    data = []
    for memory, embedding in zip(memories, embeddings):
        item = {"id_": memory.id, "text": memory.text, "vector": embedding, ...}
        data.append(item)
    
    # 3. 批量写入 Redis
    await self.index.load_data(data)
    return [m.id for m in memories]
```

**Redis Schema** (`memory_vector_db_factory.py:129-173`):

| 字段 | 类型 | 用途 |
|------|------|------|
| `text` | text | 全文搜索 |
| `vector` | vector | 向量搜索 |
| `session_id` | tag | 会话过滤 |
| `user_id` | tag | 用户过滤 |
| `namespace` | tag | 命名空间过滤 |
| `topics` | tag | 主题过滤 |
| `entities` | tag | 实体过滤 |
| `memory_type` | tag | 记忆类型 |
| `created_at` | numeric | 时间过滤 |
| `last_accessed` | numeric | 时间过滤 |
| `memory_hash` | tag | hash 过滤 |

---

## 三、搜索记忆 API (Search)

### 3.1 REST API 端点

**端点**: `POST /v1/long-term-memory/search`

**文件**: `api.py:645-705`

### 3.2 调用流程

```
search_long_term_memory (api.py:645)
    │
    ├── [1] 参数验证
    │   └── distance_threshold 仅支持 semantic 模式
    │
    ├── [2] 构建过滤条件
    │   └── payload.get_filters() → 创建 Filter 对象
    │
    ├── [3] 调用核心搜索
    │   └── long_term_memory.search_long_term_memories(**kwargs)
    │
    └── [4] 后处理
        └── long_term_memory.update_last_accessed(ids)
```

### 3.3 核心函数: search_long_term_memories

**文件**: `long_term_memory.py:1108-1260`

```python
async def search_long_term_memories(
    text: str,
    search_mode: SearchModeEnum = SearchModeEnum.SEMANTIC,
    hybrid_alpha: float = 0.7,
    text_scorer: str = "BM25STD",
    session_id: SessionId | None = None,
    user_id: UserId | None = None,
    namespace: Namespace | None = None,
    created_at: CreatedAt | None = None,
    last_accessed: LastAccessed | None = None,
    topics: Topics | None = None,
    entities: Entities | None = None,
    distance_threshold: float | None = None,
    memory_type: MemoryType | None = None,
    event_date: EventDate | None = None,
    memory_hash: MemoryHash | None = None,
    server_side_recency: bool | None = None,
    recency_params: dict | None = None,
    limit: int = 10,
    offset: int = 0,
    optimize_query: bool = False,
) -> MemoryRecordResults:
```

**搜索流程**:

```
search_long_term_memories
    │
    ├── [1] 空查询处理 (text="" 时执行纯过滤查询)
    │   └── db.list_memories(过滤条件)
    │
    ├── [2] 查询优化 (可选)
    │   └── optimize_query_for_vector_search(text)
    │
    ├── [3] 向量数据库搜索
    │   └── db.search_memories(...)
    │       │
    │       └── [搜索模式]
    │           ├── SEMANTIC - 向量相似度搜索
    │           ├── KEYWORD - BM25 全文搜索
    │           └── HYBRID - 向量 + 全文混合搜索
    │
    ├── [4] 容错处理
    │   └── 如果优化查询无结果，回退到原始查询
    │
    └── [5] 返回结果
```

### 3.4 搜索模式详解

**文件**: `memory_vector_db.py:780-960`

#### 3.4.1 SEMANTIC (语义搜索)

```python
# 使用 RedisVL VectorQuery
query = VectorQuery(
    vector=embedding,
    vector_field_name="vector",
    filter_expression=filter_expr,
    return_fields=["text", "user_id", "session_id", ...],
)
```

#### 3.4.2 KEYWORD (关键词搜索)

```python
# 使用 RedisVL TextQuery
query = TextQuery(
    text=text,
    text_field="text",
    filter_expression=filter_expr,
    scorer=text_scorer,  # BM25STD
)
```

#### 3.4.3 HYBRID (混合搜索)

```python
# 使用 RedisVL AggregateHybridQuery
query = AggregateHybridQuery(
    text=text,
    vector=embedding,
    text_field="text",
    vector_field="vector",
    hybrid_alpha=hybrid_alpha,  # 0.7 = 70% 向量, 30% 文本
    filter_expression=filter_expr,
)
```

### 3.5 过滤条件构建

**文件**: `filters.py`

```python
# 示例：构建 user_id 过滤
user_id_filter = UserId(eq="user123")

# 示例：构建时间范围过滤
created_at_filter = CreatedAt(
    gte="2024-01-01T00:00:00Z",
    lt="2024-02-01T00:00:00Z",
)

# 示例：构建 topics 过滤
topics_filter = Topics(any=["preferences", "settings"])
```

---

## 四、去重机制 (Deduplication)

### 4.1 三层去重策略

**调用顺序** (`index_long_term_memories:1031-1068`):

```
[1] deduplicate_by_id
    │
    └── 按 ID 精确匹配，存在则覆盖

[2] deduplicate_by_hash  
    │
    └── 按 text + metadata 的 hash 匹配

[3] deduplicate_by_semantic_search
    │
    └── 向量相似度匹配 (threshold=0.35)
```

### 4.2 deduplicate_by_id

**文件**: `long_term_memory.py:1385-1440`

```python
async def deduplicate_by_id(
    memory: MemoryRecord,
    redis_client: Redis | None = None,
    namespace: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> tuple[MemoryRecord | None, bool]:
    """
    当两条记忆有相同 ID 时，较新的记忆会替换较旧的记忆。
    (不会合并)
    """
    # 1. 使用向量数据库查找相同 ID 的记忆
    results = await db.list_memories(id=Id(eq=memory.id), limit=1)
    
    # 2. 如果存在，更新并返回新记忆
    if results.memories:
        # 更新 last_accessed
        await redis_client.hset(existing_key, "last_accessed", timestamp)
        return memory, True  # was_overwrite
    
    return memory, False
```

### 4.3 deduplicate_by_hash

**文件**: `long_term_memory.py:1306-1382`

```python
async def deduplicate_by_hash(
    memory: MemoryRecord,
    redis_client: Redis | None = None,
    ...
) -> tuple[MemoryRecord | None, bool]:
    """
    根据 memory.text 和 metadata 生成 hash 进行去重。
    如果找到完全相同的内容，则跳过。
    """
    # 1. 生成 hash
    memory_hash = generate_memory_hash(memory)
    
    # 2. 查找相同 hash 的记忆
    results = await db.list_memories(memory_hash=MemoryHash(eq=memory_hash), limit=1)
    
    # 3. 如果存在，返回 None 表示重复
    if results.memories:
        return None, True
    
    return memory, False
```

### 4.4 deduplicate_by_semantic_search

**文件**: `long_term_memory.py:1536-1659`

```python
async def deduplicate_by_semantic_search(
    memory: MemoryRecord,
    redis_client: Redis | None = None,
    vector_distance_threshold: float | None = None,
) -> tuple[MemoryRecord | None, bool]:
    """
    使用向量相似度搜索找到语义相似的记忆。
    如果找到，合并为一个更完整的记忆。
    """
    # 1. 设置阈值 (默认 0.35)
    threshold = vector_distance_threshold or settings.deduplication_distance_threshold
    
    # 2. 语义搜索相似记忆
    results = await db.search_memories(
        query=memory.text,
        distance_threshold=threshold,
        limit=11,  # 多取一个避免自己匹配
    )
    
    # 3. 过滤掉自己
    similar_memories = [m for m in results.memories if m.id != memory.id][:10]
    
    # 4. 检查是否 cohesive (一组记忆是否足够相似)
    if not await _semantic_merge_group_is_cohesive(...):
        return memory, False
    
    # 5. 使用 LLM 合并记忆
    merged_memory = await merge_memories_with_llm([memory] + similar_memories)
    
    # 6. 删除相似记忆
    await db.delete_memories([m.id for m in similar_memories])
    
    return merged_memory, True
```

### 4.5 _semantic_merge_group_is_cohesive

**文件**: `long_term_memory.py:1473-1533`

```python
async def _semantic_merge_group_is_cohesive(
    db: MemoryVectorDatabase,
    memory: MemoryRecord,
    candidate_memories: list[MemoryRecord],
    vector_distance_threshold: float,
) -> bool:
    """
    检查一组记忆是否足够相似可以合并。
    检查所有记忆对之间的相似度都在阈值内。
    """
    all_memories = [memory] + candidate_memories
    n = len(all_memories)
    
    for i in range(n):
        for j in range(i + 1, n):
            # 两两检查相似度
            result = await db.search_memories(
                query=all_memories[i].text,
                distance_threshold=vector_distance_threshold,
                filter=Id(eq=all_memories[j].id),
            )
            if result.total == 0:
                return False
    
    return True
```

### 4.6 merge_memories_with_llm

**文件**: `long_term_memory.py:554-665`

```python
async def merge_memories_with_llm(
    memories: list[MemoryRecord],
) -> MemoryRecord:
    """
    使用 LLM 将多个相似的记忆合并为一个更完整的记忆。
    """
    # 1. 构建提示词
    prompt = f"""Merge these similar memories into one coherent memory.
    
Memories:
{memories_text}

Requirements:
- Keep all unique information
- Remove contradictions (prefer recent)
- Maintain consistent tone
- Output as JSON with 'text' field"""

    # 2. 调用 LLM
    response = await llm_client.chat(prompt=prompt, ...)
    
    # 3. 解析结果
    merged = parse_json_response(response)
    return MemoryRecord(text=merged["text"], ...)
```

---

## 五、MCP Server Tools

### 5.1 工具映射

| MCP Tool | 核心函数 | 功能 |
|----------|----------|------|
| `create_long_term_memory` | `core_create_long_term_memory` | 创建记忆 |
| `search_long_term_memory` | `core_search_long_term_memory` | 语义搜索 |
| `get_long_term_memory` | `core_get_long_term_memory` | 按 ID 获取 |
| `edit_long_term_memory` | `core_update_long_term_memory` | 更新记忆 |
| `delete_long_term_memory` | `core_delete_long_term_memory` | 删除记忆 |
| `memory_prompt` | `core_search_long_term_memory` | 搜索 + 水合 |

### 5.2 Hydration 特性

**文件**: `mcp.py:633-760`

MCP 的 `memory_prompt` 工具在搜索后会将结果格式化为可直接用于 LLM 上下文的格式：

```python
# 搜索相关记忆
results = await core_search_long_term_memory(...)

# 构建上下文
context = f"""Relevant memories:
{'- ' + '\\n- '.join([m.text for m in results.memories])}

User query: {query}

Based on the above memories, answer the user's query."""
```

---

## 六、其他 API

### 6.1 Get by ID

**文件**: `long_term_memory.py:1966-1988`

```python
async def get_long_term_memory_by_id(memory_id: str) -> MemoryRecord | None:
    """按 ID 获取单条记忆"""
    results = await db.list_memories(id=Id(eq=memory_id), limit=1)
    return results.memories[0] if results.memories else None
```

### 6.2 Update

**文件**: `long_term_memory.py:1991-2043`

```python
async def update_long_term_memory(
    memory_id: str,
    updates: dict[str, Any],
) -> MemoryRecord | None:
    """
    更新记忆，支持的字段:
    - text, topics, entities, memory_type, namespace, metadata
    """
    # 1. 获取现有记忆
    existing = await get_long_term_memory_by_id(memory_id)
    
    # 2. 应用更新
    for key, value in updates.items():
        setattr(existing, key, value)
    
    # 3. 重新索引 (删除旧的，添加新的)
    await db.delete_memories([memory_id])
    await db.add_memories([existing])
    
    return existing
```

### 6.3 Delete

**文件**: `long_term_memory.py:1893-1900`

```python
async def delete_long_term_memories(ids: list[str]) -> int:
    """批量删除记忆"""
    return await db.delete_memories(ids)
```

### 6.4 Compact

**文件**: `long_term_memory.py:665-973`

```python
async def compact_long_term_memories(...) -> int:
    """
    压缩/清理记忆:
    1. 语义合并相似记忆
    2. 清理过期记忆
    """
    # 1. 遍历所有记忆进行语义去重
    # 2. 删除超出保留限制的记忆
    # 3. 返回清理后的数量
```

### 6.5 Forget

**文件**: `long_term_memory.py:2185-2237`

```python
async def forget_long_term_memories(
    session_ids: list[str] | None = None,
    namespace: str | None = None,
    older_than_days: int | None = None,
    older_than_hours: int | None = None,
) -> int:
    """
    选择性遗忘:
    - 按 session 遗忘
    - 按时间遗忘
    - 按命名空间遗忘
    """
    # 构建过滤条件
    # 执行删除
    return deleted_count
```

### 6.6 Promote

**文件**: `long_term_memory.py:1662-1890`

```python
async def promote_working_memory_to_long_term(
    session_id: str,
    namespace: str | None = None,
    user_id: str | None = None,
) -> int:
    """
    将工作记忆提升为长期记忆:
    1. 从工作记忆获取待提升的记录
    2. 运行 extraction 生成语义/情景记忆
    3. 使用 ID 检测去重
    4. 持久化并标记 persisted_at
    """
```

---

## 七、函数调用关系图

```
┌──────────────────────────────────────────────────────────────────┐
│                         API 层                                    │
│  api.py:606 create_long_term_memory                              │
│  api.py:645 search_long_term_memory                              │
│  api.py:836 get_long_term_memory                                 │
│  api.py:866 update_long_term_memory                              │
│  api.py:795 delete_long_term_memory                              │
│  api.py:813 compact_long_term_memories                          │
│  api.py:61  forget_long_term_memories                            │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     long_term_memory.py                          │
│                                                                  │
│  index_long_term_memories ──────────────────────────────────┐   │
│  ├── deduplicate_by_id                                  │     │
│  ├── deduplicate_by_hash                                 │     │
│  ├── deduplicate_by_semantic_search                      │     │
│  │   ├── _semantic_merge_group_is_cohesive              │     │
│  │   └── merge_memories_with_llm                        │     │
│  ├── get_memory_vector_db().add_memories()               │     │
│  └── extract_* (后台任务)                                   │     │
│                                                                  │
│  search_long_term_memories ─────────────────────────────────┐   │
│  ├── optimize_query_for_vector_search                   │     │
│  ├── get_memory_vector_db().search_memories()           │     │
│  │   ├── VectorQuery (SEMANTIC)                         │     │
│  │   ├── TextQuery (KEYWORD)                           │     │
│  │   └── AggregateHybridQuery (HYBRID)                │     │
│  └── update_last_accessed (后台任务)                       │     │
│                                                                  │
│  promote_working_memory_to_long_term                          │
│  delete_long_term_memories                                    │
│  get_long_term_memory_by_id                                   │
│  update_long_term_memory                                       │
│  compact_long_term_memories                                   │
│  forget_long_term_memories                                     │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│               memory_vector_db_factory.py                       │
│                                                                  │
│  get_memory_vector_db() ───────────────────────────────────┐   │
│  │   ├── _get_lock() (double-checked locking)           │     │
│  │   ├── create_memory_vector_db()                      │     │
│  │   └── create_redis_memory_vector_db()                │     │
│  │       └── _build_redis_schema()                      │     │
│  └── create_embeddings()                                      │     │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     memory_vector_db.py                          │
│                                                                  │
│  MemoryVectorDatabase (抽象基类)                              │
│  └── RedisVLMemoryVectorDatabase (RedisVL 实现)                │
│      ├── add_memories()                                        │
│      │   └── embeddings.aembed_documents()                     │
│      │   └── index.load_data()                                │
│      ├── search_memories()                                    │
│      │   ├── VectorQuery (语义)                              │
│      │   ├── TextQuery (关键词)                              │
│      │   └── AggregateHybridQuery (混合)                     │
│      ├── list_memories()                                       │
│      │   └── FilterQuery                                      │
│      └── delete_memories()                                    │
│          └── index.delete()                                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 八、总结

### 8.1 核心特性

1. **三层去重**: ID → Hash → 语义，层层过滤重复记忆
2. **多种搜索模式**: 语义、关键词、混合搜索
3. **丰富的过滤条件**: 支持按 session/user/namespace/topics/entities/time 等过滤
4. **后台处理**: 记忆提取、索引、水合等异步执行
5. **可插拔架构**: 通过工厂模式支持不同的向量数据库后端

### 8.2 性能优化

1. **查询优化**: 可选的 query 优化提升搜索准确性
2. **容错机制**: 优化查询无结果时自动回退到原始查询
3. **双检查锁定**: 向量数据库实例的线程安全初始化
4. **批量操作**: 批量添加/删除记忆减少网络开销
