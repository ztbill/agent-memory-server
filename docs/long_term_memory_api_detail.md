# Long Term Memory REST API 详细实现分析

## 概述

本文档详细分析 `api.py` 中定义的 7 个 Long Term Memory REST API 的实现原理和函数调用链。

---

## API 一览

| 端点 | 方法 | 功能 |
|------|------|------|
| `/v1/long-term-memory/` | POST | 创建长期记忆 |
| `/v1/long-term-memory/search` | POST | 语义搜索长期记忆 |
| `/v1/long-term-memory/{memory_id}` | GET | 获取单条记忆 |
| `/v1/long-term-memory/{memory_id}` | PATCH | 更新记忆内容 |
| `/v1/long-term-memory` | DELETE | 删除记忆 |
| `/v1/long-term-memory/compact` | POST | 压缩/清理记忆 |
| `/v1/long-term-memory/forget` | POST | 选择性遗忘记忆 |

---

## API 1: 创建长期记忆

### 端点信息
- **路径**: `POST /v1/long-term-memory/`
- **文件**: `api.py:606-642`
- **响应模型**: `AckResponse`

### 请求参数

```python
class CreateMemoryRecordRequest(BaseModel):
    memories: list[MemoryRecord]  # 记忆列表
    deduplicate: bool = False     # 是否去重
```

### 实现原理

```python
@router.post("/v1/long-term-memory/", response_model=AckResponse)
async def create_long_term_memory(
    payload: CreateMemoryRecordRequest,
    background_tasks: HybridBackgroundTasks,
    current_user: UserInfo = Depends(get_current_user),
):
```

### 函数调用链

```
create_long_term_memory (api.py:606)
    │
    ├── [1] 功能开关检查
    │   └── settings.long_term_memory 必须为 True
    │
    ├── [2] 参数验证
    │   ├── 检查 memory.id 必填
    │   └── 清除 client 提供的 persisted_at (必须 server 分配)
    │
    └── [3] 提交后台任务 (非阻塞)
        └── background_tasks.add_task(
                long_term_memory.index_long_term_memories,
                memories=payload.memories,
                deduplicate=payload.deduplicate,
            )
```

### 核心函数: index_long_term_memories

**位置**: `long_term_memory.py:977-1106`

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
    │   └── 过滤 text="" 或 id="" 的记录
    │
    ├── [2] 去重处理 (当 deduplicate=True)
    │   ├── deduplicate_by_id (按 ID 去重 - 覆盖)
    │   ├── deduplicate_by_hash (按 hash 去重 - 跳过)
    │   └── deduplicate_by_semantic_search (语义去重 - 合并)
    │
    ├── [3] 向量索引
    │   └── get_memory_vector_db().add_memories(processed_memories)
    │       │
    │       ├── 生成 embedding (LiteLLMEmbeddings)
    │       └── 写入 Redis (AsyncSearchIndex.load_data)
    │
    └── [4] 后台任务
        ├── extract_memory_structure (提取 topic/entity)
        └── extract_memories_with_strategy (策略化提取)
```

### 函数说明

| 函数 | 作用 | 文件位置 |
|------|------|----------|
| `index_long_term_memories` | 索引记忆的核心函数 | long_term_memory.py:977 |
| `deduplicate_by_id` | 按 ID 去重，相同 ID 覆盖 | long_term_memory.py:1385 |
| `deduplicate_by_hash` | 按内容 hash 去重，完全相同跳过 | long_term_memory.py:1306 |
| `deduplicate_by_semantic_search` | 语义去重，相似内容合并 | long_term_memory.py:1536 |
| `get_memory_vector_db` | 获取向量数据库实例 | memory_vector_db_factory.py:236 |
| `add_memories` | 添加记忆到向量索引 | memory_vector_db.py:737 |

---

## API 2: 搜索长期记忆

### 端点信息
- **路径**: `POST /v1/long-term-memory/search`
- **文件**: `api.py:645-792`
- **响应模型**: `MemoryRecordResultsResponse`

### 请求参数

```python
class SearchRequest(BaseModel):
    text: str                           # 搜索文本
    search_mode: SearchModeEnum        # 搜索模式 (SEMANTIC/KEYWORD/HYBRID)
    hybrid_alpha: float = 0.7          # 混合搜索权重
    text_scorer: str = "BM25STD"       # 文本评分算法
    limit: int = 10                    # 返回数量
    offset: int = 0                    # 偏移量
    filters: dict                      # 过滤条件
    optimize_query: bool = False       # 是否优化查询
    recency_boost: bool = True          # 是否启用时间权重
    server_side_recency: bool = False  # 服务端重排序
    distance_threshold: float | None    # 相似度阈值 (仅 semantic)
```

### 实现原理

```python
@router.post("/v1/long-term-memory/search", response_model=MemoryRecordResultsResponse)
async def search_long_term_memory(
    payload: SearchRequest,
    background_tasks: HybridBackgroundTasks,
    optimize_query: bool = False,
    current_user: UserInfo = Depends(get_current_user),
):
```

### 函数调用链

```
search_long_term_memory (api.py:645)
    │
    ├── [1] 功能开关检查
    │   └── settings.long_term_memory 必须为 True
    │
    ├── [2] 参数验证
    │   └── distance_threshold 仅支持 SEMANTIC 模式
    │
    ├── [3] 构建过滤条件
    │   └── payload.get_filters() → 创建 Filter 对象
    │
    ├── [4] 调用核心搜索
    │   └── long_term_memory.search_long_term_memories(**kwargs)
    │
    ├── [5] 软过滤回退 (当 strict filters 无结果时)
    │   └── 将 filters 注入到查询文本作为提示
    │
    ├── [6] 时间权重重排序 (可选)
    │   └── long_term_memory.rerank_with_recency()
    │
    └── [7] 更新最后访问时间 (后台)
        └── background_tasks.add_task(update_last_accessed, ids)
```

### 核心函数: search_long_term_memories

**位置**: `long_term_memory.py:1108-1260`

```python
async def search_long_term_memories(
    text: str,
    search_mode: SearchModeEnum = SearchModeEnum.SEMANTIC,
    ...
) -> MemoryRecordResults:
```

**搜索流程**:

```
search_long_term_memories
    │
    ├── [1] 空查询处理 (text="" 时)
    │   └── db.list_memories(仅过滤条件)
    │
    ├── [2] 查询优化 (可选)
    │   └── optimize_query_for_vector_search(text)
    │
    ├── [3] 向量数据库搜索
    │   └── db.search_memories(...)
    │       │
    │       └── [根据 search_mode]
    │           ├── SEMANTIC: VectorQuery
    │           ├── KEYWORD: TextQuery
    │           └── HYBRID: AggregateHybridQuery
    │
    ├── [4] 容错处理
    │   └── 优化查询无结果 → 回退到原始查询
    │
    └── [5] 返回结果
```

### 搜索模式详解

| 模式 | 查询类型 | 说明 |
|------|----------|------|
| `SEMANTIC` | `VectorQuery` | 向量相似度搜索 |
| `KEYWORD` | `TextQuery` | BM25 全文搜索 |
| `HYBRID` | `AggregateHybridQuery` | 70% 向量 + 30% 文本 |

### 函数说明

| 函数 | 作用 | 文件位置 |
|------|------|----------|
| `search_long_term_memories` | 核心搜索函数 | long_term_memory.py:1108 |
| `rerank_with_recency` | 按时间权重重排序 | utils/recency.py |
| `update_last_accessed` | 更新最后访问时间 | long_term_memory.py:2139 |
| `optimize_query_for_vector_search` | AI 优化查询 | llm/client.py |

---

## API 3: 获取单条记忆

### 端点信息
- **路径**: `GET /v1/long-term-memory/{memory_id}`
- **文件**: `api.py:836-862`
- **响应模型**: `MemoryRecord`

### 实现原理

```python
@router.get("/v1/long-term-memory/{memory_id}", response_model=MemoryRecord)
async def get_long_term_memory(
    memory_id: str,
    current_user: UserInfo = Depends(get_current_user),
):
```

### 函数调用链

```
get_long_term_memory (api.py:836)
    │
    ├── [1] 功能开关检查
    │
    ├── [2] 调用核心函数
    │   └── long_term_memory.get_long_term_memory_by_id(memory_id)
    │
    └── [3] 返回结果 (或 404)
```

### 核心函数: get_long_term_memory_by_id

**位置**: `long_term_memory.py:1966-1988`

```python
async def get_long_term_memory_by_id(memory_id: str) -> MemoryRecord | None:
    """按 ID 获取单条记忆"""
    from agent_memory_server.filters import Id
    
    db = await get_memory_vector_db()
    
    # 使用 filter-only 查询 (无需 embedding)
    results = await db.list_memories(
        limit=1,
        id=Id(eq=memory_id),
    )
    
    return results.memories[0] if results.memories else None
```

---

## API 4: 更新记忆

### 端点信息
- **路径**: `PATCH /v1/long-term-memory/{memory_id}`
- **文件**: `api.py:865-900`
- **响应模型**: `MemoryRecord`

### 请求参数

```python
class EditMemoryRecordRequest(BaseModel):
    text: str | None                   # 更新文本
    topics: list[str] | None           # 更新主题
    entities: list[Entity] | None      # 更新实体
    memory_type: MemoryTypeEnum | None # 更新类型
    namespace: str | None             # 更新命名空间
    metadata: dict | None              # 更新元数据
    pinned: bool | None                # 更新置顶状态
```

### 实现原理

```python
@router.patch("/v1/long-term-memory/{memory_id}", response_model=MemoryRecord)
async def update_long_term_memory(
    memory_id: str,
    updates: EditMemoryRecordRequest,
    current_user: UserInfo = Depends(get_current_user),
):
```

### 函数调用链

```
update_long_term_memory (api.py:865)
    │
    ├── [1] 功能开关检查
    │
    ├── [2] 转换为字典 (排除 None)
    │   └── update_dict = {k: v for k, v in updates.model_dump() if v is not None}
    │
    ├── [3] 调用核心函数
    │   └── long_term_memory.update_long_term_memory(memory_id, update_dict)
    │
    └── [4] 返回更新后的记忆
```

### 核心函数: update_long_term_memory

**位置**: `long_term_memory.py:1991-2043`

```python
async def update_long_term_memory(
    memory_id: str,
    updates: dict[str, Any],
) -> MemoryRecord | None:
```

**处理流程**:

```
update_long_term_memory
    │
    ├── [1] 获取现有记忆
    │   └── get_long_term_memory_by_id(memory_id)
    │
    ├── [2] 验证可更新字段
    │   └── 允许的字段: text, topics, entities, memory_type, 
    │                   namespace, metadata, pinned
    │
    ├── [3] 应用更新
    │   └── setattr(existing, key, value)
    │
    ├── [4] 重新索引
    │   ├── db.delete_memories([memory_id])  # 删除旧的
    │   └── db.add_memories([existing])       # 添加新的
    │
    └── [5] 返回更新后的记忆
```

---

## API 5: 删除记忆

### 端点信息
- **路径**: `DELETE /v1/long-term-memory`
- **文件**: `api.py:795-810`
- **响应模型**: `AckResponse`

### 查询参数

```
DELETE /v1/long-term-memory?memory_ids=id1&memory_ids=id2&...
```

### 实现原理

```python
@router.delete("/v1/long-term-memory", response_model=AckResponse)
async def delete_long_term_memory(
    memory_ids: list[str] = Query(default=[], alias="memory_ids"),
    current_user: UserInfo = Depends(get_current_user),
):
```

### 函数调用链

```
delete_long_term_memory (api.py:795)
    │
    ├── [1] 功能开关检查
    │
    ├── [2] 调用核心函数
    │   └── long_term_memory.delete_long_term_memories(ids=memory_ids)
    │
    └── [3] 返回删除数量
```

### 核心函数: delete_long_term_memories

**位置**: `long_term_memory.py:1893-1900`

```python
async def delete_long_term_memories(ids: list[str]) -> int:
    """批量删除记忆"""
    db = await get_memory_vector_db()
    return await db.delete_memories(ids)
```

---

## API 6: 压缩/清理记忆

### 端点信息
- **路径**: `POST /v1/long-term-memory/compact`
- **文件**: `api.py:813-833`
- **响应模型**: `AckResponse`

### 查询参数

```
POST /v1/long-term-memory/compact?namespace=xxx&user_id=xxx
```

### 实现原理

```python
@router.post("/v1/long-term-memory/compact", response_model=AckResponse)
async def compact_long_term_memories_endpoint(
    namespace: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    current_user: UserInfo = Depends(get_current_user),
):
```

### 函数调用链

```
compact_long_term_memories_endpoint (api.py:813)
    │
    ├── [1] 功能开关检查
    │
    └── [2] 调用核心函数
        └── long_term_memory.compact_long_term_memories(
                namespace=namespace,
                user_id=user_id,
            )
```

### 核心函数: compact_long_term_memories

**位置**: `long_term_memory.py:665-973`

```python
async def compact_long_term_memories(
    namespace: str | None = None,
    user_id: str | None = None,
    memory_types: list[str] | None = None,
    max_memories_per_user: int | None = None,
    preserve_recent: int = 100,
    batch_size: int = 100,
) -> int:
```

**压缩流程**:

```
compact_long_term_memories
    │
    ├── [1] 构建过滤条件
    │   └── namespace, user_id, memory_types
    │
    ├── [2] 获取所有候选记忆
    │   └── db.list_memories(limit=大量)
    │
    ├── [3] 语义去重 (可选)
    │   └── deduplicate_by_semantic_search (批量)
    │
    ├── [4] 过期清理
    │   └── 删除超过保留限制的旧记忆
    │
    └── [5] 返回剩余记忆数量
```

---

## API 7: 选择性遗忘

### 端点信息
- **路径**: `POST /v1/long-term-memory/forget`
- **文件**: `api.py:61-84`
- **响应模型**: `dict`

### 请求体

```python
{
    "max_age_days": 90,              # 最大保留天数
    "max_inactive_days": 30,         # 最大不活跃天数
    "budget": 100,                   # 保留最新 N 条
    "memory_type_allowlist": ["semantic"],  # 只删除这些类型
    "hard_age_multiplier": 12.0      # 极端过期倍数
}
```

### 查询参数

```
POST /v1/long-term-memory/forget?namespace=xxx&user_id=xxx&limit=1000&dry_run=true&pinned_ids=xxx
```

### 实现原理

```python
@router.post("/v1/long-term-memory/forget")
async def forget_endpoint(
    policy: dict,
    namespace: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    limit: int = 1000,
    dry_run: bool = True,
    pinned_ids: list[str] | None = None,
    current_user: UserInfo = Depends(get_current_user),
):
```

### 函数调用链

```
forget_endpoint (api.py:61)
    │
    ├── [1] 参数传递
    │   └── policy, namespace, user_id, session_id, limit, dry_run, pinned_ids
    │
    └── [2] 调用核心函数
        └── long_term_memory.forget_long_term_memories(
                policy=policy,
                namespace=namespace,
                user_id=user_id,
                session_id=session_id,
                limit=limit,
                dry_run=dry_run,
                pinned_ids=pinned_ids,
            )
```

### 核心函数: forget_long_term_memories

**位置**: `long_term_memory.py:2185-2235`

```python
async def forget_long_term_memories(
    policy: dict,
    *,
    namespace: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    limit: int = 1000,
    dry_run: bool = True,
    pinned_ids: list[str] | None = None,
) -> dict:
```

**遗忘流程**:

```
forget_long_term_memories
    │
    ├── [1] 构建过滤条件
    │   └── namespace, user_id, session_id
    │
    ├── [2] 获取候选记忆
    │   └── db.list_memories(limit=limit)
    │
    ├── [3] 选择删除目标
    │   └── select_ids_for_forgetting(results, policy, now, pinned_ids)
    │       │
    │       └── [策略]
    │           ├── max_age_days: 超过此天数的删除
    │           ├── max_inactive_days: 超过此天数未访问的删除
    │           ├── budget: 只保留最新 N 条
    │           └── memory_type_allowlist: 只删除指定类型
    │
    ├── [4] 执行删除 (如果非 dry_run)
    │   └── db.delete_memories(to_delete_ids)
    │
    └── [5] 返回结果
        └── {scanned, deleted, deleted_ids, dry_run}
```

### 策略函数: select_ids_for_forgetting

**位置**: `long_term_memory.py:2050-2138`

```python
def select_ids_for_forgetting(
    results: Iterable[MemoryRecordResult],
    *,
    policy: dict,
    now: datetime,
    pinned_ids: set[str] | None = None,
) -> list[str]:
```

**策略说明**:

| 策略 | 说明 |
|------|------|
| `max_age_days` | 超过此天数的记忆标记为删除 |
| `max_inactive_days` | 超过此天数未被访问的记忆标记为删除 |
| `budget` | 只保留最新的 N 条记忆 |
| `memory_type_allowlist` | 只删除指定类型的记忆 |
| `hard_age_multiplier` | 极端过期天数 = max_age_days × multiplier |

---

## 完整函数调用关系图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          REST API Layer                                 │
│  api.py                                                                  │
│                                                                          │
│  POST /v1/long-term-memory/                                             │
│  └── create_long_term_memory → index_long_term_memories               │
│                                                                          │
│  POST /v1/long-term-memory/search                                      │
│  └── search_long_term_memory → search_long_term_memories               │
│      └── rerank_with_recency + update_last_accessed                     │
│                                                                          │
│  GET /v1/long-term-memory/{memory_id}                                  │
│  └── get_long_term_memory → get_long_term_memory_by_id                 │
│                                                                          │
│  PATCH /v1/long-term-memory/{memory_id}                                │
│  └── update_long_term_memory → update_long_term_memory                │
│                                                                          │
│  DELETE /v1/long-term-memory                                            │
│  └── delete_long_term_memory → delete_long_term_memories               │
│                                                                          │
│  POST /v1/long-term-memory/compact                                     │
│  └── compact_long_term_memories_endpoint → compact_long_term_memories │
│                                                                          │
│  POST /v1/long-term-memory/forget                                       │
│  └── forget_endpoint → forget_long_term_memories                       │
│      └── select_ids_for_forgetting                                      │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                                 │
│  long_term_memory.py                                                   │
│                                                                          │
│  index_long_term_memories ─────────────────────────────────────────┐  │
│  ├── deduplicate_by_id                                        │       │
│  ├── deduplicate_by_hash                                       │       │
│  ├── deduplicate_by_semantic_search                            │       │
│  │   └── merge_memories_with_llm                               │       │
│  ├── get_memory_vector_db().add_memories()                     │       │
│  └── extract_* (后台任务)                                        │       │
│                                                                      │
│  search_long_term_memories ─────────────────────────────────────┐   │
│  ├── optimize_query_for_vector_search                      │       │
│  ├── get_memory_vector_db().search_memories()               │       │
│  └── update_last_accessed                                 │       │
│                                                                      │
│  get_long_term_memory_by_id                                       │
│  └── get_memory_vector_db().list_memories()                       │
│                                                                      │
│  update_long_term_memory                                           │
│  ├── get_long_term_memory_by_id                                   │
│  └── db.delete_memories() + db.add_memories()                       │
│                                                                      │
│  delete_long_term_memories                                          │
│  └── get_memory_vector_db().delete_memories()                       │
│                                                                      │
│  compact_long_term_memories                                         │
│  └── deduplicate_by_semantic_search (批量)                          │
│                                                                      │
│  forget_long_term_memories                                          │
│  └── select_ids_for_forgetting                                      │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Vector Database Layer                               │
│  memory_vector_db_factory.py + memory_vector_db.py                    │
│                                                                          │
│  get_memory_vector_db() ──────────────────────────────────────────┐   │
│  │   ├── create_memory_vector_db()                            │       │
│  │   └── create_redis_memory_vector_db()                      │       │
│  │       └── _build_redis_schema()                            │       │
│  │                                                             │       │
│  └── create_embeddings() ─────────────────────────────────────┐     │
│      └── LiteLLMEmbeddings                                   │     │
│                                                              │     │
│  RedisVLMemoryVectorDatabase                                │     │
│  ├── add_memories() ─────────────────────────────────────┐   │     │
│  │   └── embeddings.aembed_documents() + index.load_data()│   │     │
│  │                                                     │   │     │
│  ├── search_memories() ───────────────────────────────┐  │   │     │
│  │   ├── VectorQuery (SEMANTIC)                    │  │   │     │
│  │   ├── TextQuery (KEYWORD)                       │  │   │     │
│  │   └── AggregateHybridQuery (HYBRID)             │  │   │     │
│  │                                                 │   │     │
│  ├── list_memories() (filter-only)                 │  │     │
│  │   └── FilterQuery                              │  │     │
│  │                                                 │   │     │
│  └── delete_memories()                             │  │     │
│      └── index.delete()                             │  │     │
│                                                      │   │     │
└──────────────────────────────────────────────────────┴───┴─────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         Redis Stack                                      │
│                                                                          │
│  Index: settings.redisvl_index_name                                     │
│                                                                          │
│  Schema Fields:                                                          │
│  ├── text (text) - 全文搜索                                              │
│  ├── vector (vector) - 向量搜索                                          │
│  ├── session_id, user_id, namespace (tag) - 过滤                        │
│  ├── topics, entities, memory_type (tag) - 过滤                         │
│  ├── created_at, last_accessed (numeric) - 时间过滤                       │
│  └── memory_hash (tag) - hash 过滤                                       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 总结

### API 与核心函数映射

| API | 核心函数 | 核心功能 |
|-----|----------|----------|
| CREATE | `index_long_term_memories` | 索引 + 去重 + 向量存储 |
| SEARCH | `search_long_term_memories` | 向量/关键词/混合搜索 |
| GET | `get_long_term_memory_by_id` | 按 ID 查询 |
| UPDATE | `update_long_term_memory` | 更新 + 重新索引 |
| DELETE | `delete_long_term_memories` | 批量删除 |
| COMPACT | `compact_long_term_memories` | 语义合并 + 过期清理 |
| FORGET | `forget_long_term_memories` | 策略性遗忘 |

### 关键设计模式

1. **异步处理**: 大部分操作通过 `background_tasks.add_task` 异步执行
2. **可插拔后端**: 通过 `get_memory_vector_db()` 工厂模式支持不同向量数据库
3. **三层去重**: ID → Hash → 语义，层层过滤重复数据
4. **多种搜索模式**: SEMANTIC / KEYWORD / HYBRID 满足不同场景
5. **软过滤回退**: 严格过滤无结果时，自动放松条件重试
