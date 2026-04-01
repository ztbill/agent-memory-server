# Working Memory API 文档

## 概述

Working Memory 是项目中的会话级内存管理组件，提供基于 session 的上下文存储能力。支持 REST API 和 MCP 两种接口方式。

## REST API

### 端点列表

| Endpoint | Method | Handler | 功能 |
|----------|--------|---------|------|
| `/v1/working-memory/` | GET | `list_sessions` | 列出所有会话 |
| `/v1/working-memory/{session_id}` | GET | `get_working_memory` | 获取会话的 working memory |
| `/v1/working-memory/{session_id}` | PUT | `put_working_memory` | 设置/替换会话的 working memory |
| `/v1/working-memory/{session_id}` | DELETE | `delete_working_memory` | 删除会话的 working memory |

### 1. List Sessions

```
GET /v1/working-memory/
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `limit` | int | 否 | 返回数量限制 |
| `offset` | int | 否 | 偏移量 |
| `namespace` | string | 否 | 命名空间过滤 |
| `user_id` | string | 否 | 用户 ID 过滤 |

**响应示例：**

```json
{
  "total": 100,
  "sessions": ["sess_001", "sess_002"]
}
```

### 2. Get Working Memory

```
GET /v1/working-memory/{session_id}
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 否 | 用户 ID |
| `namespace` | string | 否 | 命名空间 |
| `model_name` | string | 否 | 模型名称（用于计算 token 使用） |
| `context_window_max` | int | 否 | 上下文窗口最大值 |
| `recent_messages_limit` | int | 否 | 最近消息数量限制 |

**响应字段（WorkingMemoryResponse）：**

```python
class WorkingMemoryResponse(BaseModel):
    messages: list[MemoryMessage]      # 对话消息
    memories: list[MemoryRecord]      # 结构化记忆
    data: dict | None                  # 任意 JSON 数据
    context: str | None                # 摘要（如果自动 summarization）
    user_id: str | None
    tokens: int                        # token 数量
    session_id: str
    namespace: str | None
    long_term_memory_strategy: MemoryStrategyConfig
    # 计算字段
    tokens_percentage: float | None    # token 使用百分比
    messages_count: int
    memories_count: int
```

### 3. Put Working Memory

```
PUT /v1/working-memory/{session_id}
```

**请求体（UpdateWorkingMemory）：**

```python
class UpdateWorkingMemory(BaseModel):
    messages: list[MemoryMessage] | None = None
    memories: list[MemoryRecord | ClientMemoryRecord] | None = None
    data: dict[str, JSONTypes] | None = None
    context: str | None = None
    user_id: str | None = None
    namespace: str | None = None
    long_term_memory_strategy: MemoryStrategyConfig | None = None
    ttl_seconds: int | None = None
```

**响应：** 返回更新后的 `WorkingMemoryResponse`

**说明：**
- 如果 session 不存在则创建
- 可能触发 summarization
- 可能 promote 内容到 long-term memory

### 4. Delete Working Memory

```
DELETE /v1/working-memory/{session_id}
```

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 否 | 用户 ID |
| `namespace` | string | 否 | 命名空间 |

**响应：** `AckResponse`（确认删除）

---

## MCP API

### Tools

| Tool | 对应 REST | 功能 |
|------|-----------|------|
| `set_working_memory` | PUT /v1/working-memory/{id} | 存储 working memory |
| `get_working_memory` | GET /v1/working-memory/{id} | 获取 working memory |
| `memory_prompt` | - | 将 session context + long-term memory 注入 prompt |
| `get_current_datetime` | - | 获取当前 UTC 时间 |

### set_working_memory

```python
# 参数
session_id: str                      # 会话 ID
memories: list[MemoryRecord] | None  # 结构化记忆
messages: list[MemoryMessage] | None # 对话消息
context: str | None                  # 摘要上下文
data: dict | None                    # 任意 JSON 数据
namespace: str | None                # 命名空间
user_id: str | None                  # 用户 ID
ttl_seconds: int | None             # TTL
long_term_memory_strategy: MemoryStrategyConfig | None  # 长期记忆策略
```

### get_working_memory

```python
# 参数
session_id: str
user_id: str | None
namespace: str | None
recent_messages_limit: int | None
```

### memory_prompt

用于将 session context 和长期记忆注入 prompt，支持语义搜索。

```python
# 参数
session_id: str
user_id: str | None
namespace: str | None
long_term_search: LongTermSearchConfig | None
topics: list[str] | None
entities: list[str] | None
# ... 其他参数
```

---

## 数据模型

### 核心模型

| 模型 | 文件 | 说明 |
|------|------|------|
| `WorkingMemory` | models.py | 主容器，包含 messages, memories, data, context 等 |
| `MemoryMessage` | models.py | 聊天消息 |
| `MemoryRecord` | models.py | 结构化记忆 |
| `MemoryStrategyConfig` | models.py | 记忆提取策略配置 |
| `UpdateWorkingMemory` | models.py | PUT 请求的输入模型 |

### MemoryMessage

```python
class MemoryMessage(BaseModel):
    role: str
    content: str
    id: str = Field(default_factory=lambda: str(ULID()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    persisted_at: datetime | None = None
    discrete_memory_extracted: Literal["t", "f"] = "f"
```

### MemoryRecord

```python
class MemoryRecord(BaseModel):
    id: str
    text: str
    session_id: str | None = None
    user_id: str | None = None
    namespace: str | None = None
    last_accessed: datetime
    created_at: datetime
    updated_at: datetime
    pinned: bool = False
    memory_type: MemoryTypeEnum = MemoryTypeEnum.MESSAGE
    # ... 更多字段
```

### WorkingMemory

```python
class WorkingMemory(BaseModel):
    messages: list[MemoryMessage] = Field(default_factory=list)
    memories: list[MemoryRecord | ClientMemoryRecord] = Field(default_factory=list)
    data: dict[str, JSONTypes] | None = None
    context: str | None = None
    user_id: str | None = None
    tokens: int = 0
    session_id: str
    namespace: str | None = None
    long_term_memory_strategy: MemoryStrategyConfig = Field(default_factory=MemoryStrategyConfig)
    ttl_seconds: int | None = None
    last_accessed: datetime
    created_at: datetime
    updated_at: datetime
```

---

## 核心实现

### 文件结构

| 文件 | 功能 |
|------|------|
| `working_memory.py` | 核心 CRUD 逻辑 |
| `working_memory_index.py` | RedisVL 索引管理（会话列表） |
| `models.py` | Pydantic 数据模型 |
| `utils/keys.py` | Redis key 构建工具 |

### 核心函数

```python
# 获取 working memory
async def get_working_memory(
    session_id: str,
    user_id: str | None = None,
    namespace: str | None = None,
    redis_client: Redis | None = None,
    recent_messages_limit: int | None = None
) -> WorkingMemory | None

# 设置 working memory
async def set_working_memory(
    working_memory: WorkingMemory,
    redis_client: Redis | None = None
) -> None

# 删除 working memory
async def delete_working_memory(
    session_id: str,
    user_id: str | None = None,
    namespace: str | None = None,
    redis_client: Redis | None = None
) -> None

# 列出会话
async def list_sessions(
    redis_client: Redis,
    namespace: str | None = None,
    user_id: str | None = None,
    limit: int = 100,
    offset: int = 0
) -> list[str]
```

### Redis 存储

Working Memory 以 JSON 形式存储在 Redis 中，key 格式：

```
working_memory:{session_id}
# 或带 namespace/user_id
working_memory:{namespace}:{user_id}:{session_id}
```

使用 `utils/keys.py` 中的 `working_memory_key()` 函数构建。

---

## 功能特性

### 自动摘要
当 messages 超过 context_window_max 时，自动触发 summarization 生成 context。

### 长期记忆晋升
支持配置 `long_term_memory_strategy`，自动将结构化记忆晋升到长期存储。

### TTL 支持
可设置 `ttl_seconds` 控制 working memory 的过期时间。

### 会话列表索引
使用 RedisVL 构建索引，支持按 namespace/user_id 过滤和分页。