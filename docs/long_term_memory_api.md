# Long Term Memory API 文档

## 概述

Long Term Memory 是项目中的持久化内存管理组件，提供语义搜索和长期存储能力。支持 REST API 和 MCP 两种接口方式。

## REST API

### 端点列表

| Endpoint | Method | Handler | 功能 |
|----------|--------|---------|------|
| `/v1/long-term-memory/` | POST | `create_long_term_memory` | 创建长期记忆 |
| `/v1/long-term-memory/search` | POST | `search_long_term_memory` | 语义搜索长期记忆 |
| `/v1/long-term-memory/{memory_id}` | GET | `get_long_term_memory` | 获取单条记忆 |
| `/v1/long-term-memory/{memory_id}` | PATCH | `update_long_term_memory` | 更新记忆内容 |
| `/v1/long-term-memory` | DELETE | `delete_long_term_memory` | 删除记忆 |
| `/v1/long-term-memory/compact` | POST | `compact_long_term_memories` | 压缩/清理记忆 |
| `/v1/long-term-memory/forget` | POST | `forget_long_term_memories` | 选择性遗忘记忆 |


### 1. Create Long Term Memory

```
POST /v1/long-term-memory/
```

**请求体：**

```json
[
  {
    "text": "User prefers morning meetings",
    "user_id": "user123",
    "memory_type": "preference",
    "namespace": "default",
    "topics": ["meetings", "schedule"],
    "entities": [{"name": "Alice", "type": "person"}],
    "metadata": {"source": "chat"}
  }
]
```

**参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 是 | 记忆内容 |
| `user_id` | string | 否 | 用户 ID |
| `memory_type` | string | 否 | 记忆类型 (semantic/episodic) |
| `namespace` | string | 否 | 命名空间 |
| `topics` | array | 否 | 主题标签 |
| `entities` | array | 否 | 实体列表 |
| `metadata` | object | 否 | 自定义元数据 |

### 2. Search Long Term Memory

```
POST /v1/long-term-memory/search
```

**请求体：**

```json
{
  "text": "What time does the user like meetings?",
  "user_id": "user123",
  "limit": 10,
  "filters": {
    "memory_type": "preference",
    "namespace": "default"
  }
}
```

**参数说明：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `text` | string | 是 | 搜索文本 |
| `user_id` | string | 否 | 用户 ID 过滤 |
| `limit` | int | 否 | 返回数量限制，默认 10 |
| `offset` | int | 否 | 偏移量 |
| `filters` | object | 否 | 过滤条件 |
| `optimize_query` | bool | 否 | 是否优化查询 |
| `rank_by_recency` | bool | 否 | 是否按时间排序 |

### 3. Get Long Term Memory

```
GET /v1/long-term-memory/{memory_id}
```

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `memory_id` | string | 记忆 ID |

### 4. Update Long Term Memory

```
PATCH /v1/long-term-memory/{memory_id}
```

**请求体：**

```json
{
  "text": "Updated memory text",
  "topics": ["updated_topic"],
  "metadata": {"updated": true}
}
```

### 5. Delete Long Term Memory

```
DELETE /v1/long-term-memory
```

**请求体：**

```json
{
  "ids": ["memory_id_1", "memory_id_2"]
}
```

### 6. Compact Long Term Memory

```
POST /v1/long-term-memory/compact
```

清理重复和过期的记忆。

### 7. Forget Long Term Memory

```
POST /v1/long-term-memory/forget
```

选择性遗忘记忆，支持按条件删除。

---

## MCP Server Tools

### 工具列表

| Tool Name | 功能 |
|-----------|------|
| `create_long_term_memory` | 创建长期记忆 |
| `search_long_term_memory` | 语义搜索 + 可选 hydration |
| `get_long_term_memory` | 获取单条记忆 |
| `edit_long_term_memory` | 编辑记忆 |
| `delete_long_term_memory` | 删除记忆 |

### 1. create_long_term_memory

创建新的长期记忆。

**参数：**

```json
{
  "memories": [
    {
      "text": "User prefers morning meetings",
      "user_id": "user123",
      "memory_type": "preference"
    }
  ]
}
```

### 2. search_long_term_memory

语义搜索长期记忆，支持 hydration 生成上下文。

**参数：**

```json
{
  "text": "user's favorite color",
  "user_id": "user123",
  "limit": 5,
  "namespace": "default",
  "hydrate": true
}
```

### 3. get_long_term_memory

通过 ID 获取单条记忆。

**参数：**

```json
{
  "memory_id": "01HXE2B1234567890ABCDEF"
}
```

### 4. edit_long_term_memory

编辑/更新现有记忆。

**参数：**

```json
{
  "memory_id": "01HXE2B1234567890ABCDEF",
  "updates": {
    "text": "Updated text"
  }
}
```

### 5. delete_long_term_memory

删除指定的记忆。

**参数：**

```json
{
  "memory_ids": ["01HXE2B1234567890ABCDEF"]
}
```

---

## 搜索过滤条件

搜索 API 支持以下高级过滤参数：

| 过滤条件 | 类型 | 说明 |
|----------|------|------|
| `session_id` | string | 按会话过滤 |
| `namespace` | string | 按命名空间过滤 |
| `user_id` | string | 按用户过滤 |
| `topics` | array | 按主题过滤 |
| `entities` | array | 按实体过滤 |
| `memory_type` | string | 按记忆类型过滤 (semantic/episodic) |
| `created_at` | object | 按创建时间过滤 |
| `event_date` | object | 按事件时间过滤 |
| `last_accessed` | object | 按最后访问时间过滤 |
| `memory_hash` | string | 按内容 hash 过滤 |

---

## 核心模块函数

| 函数 | 功能 |
|------|------|
| `index_long_term_memories` | 为记忆生成向量索引 |
| `search_long_term_memories` | 核心搜索实现 |
| `count_long_term_memories` | 统计记忆数量 |
| `deduplicate_by_hash` | 按 hash 去重 |
| `deduplicate_by_id` | 按 ID 去重 |
| `deduplicate_by_semantic_search` | 语义去重 |
| `promote_working_memory_to_long_term` | 将工作记忆提升为长期记忆 |
| `delete_long_term_memories` | 删除指定记忆 |
| `get_long_term_memory_by_id` | 按 ID 获取记忆 |
| `update_long_term_memory` | 更新记忆 |
| `compact_long_term_memories` | 压缩/清理 |
| `forget_long_term_memories` | 选择性遗忘 |
| `periodic_forget_long_term_memories` | 周期性遗忘任务 |
