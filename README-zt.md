#### API  接口使用

``` text
# ========================================
# 1. 写入工作记忆（自动触发长期记忆生成）
# ========================================
curl -X PUT "http://localhost:8000/v1/working-memory/session-cn-001" \
  -H "Content-Type: application/json" \
  -H "DISABLE_AUTH: true" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "你好，我叫张三，我喜欢机器学习和人工智能",
        "created_at": "2026-03-29T16:45:00Z"
      },
      {
        "role": "assistant",
        "content": "很高兴认识你张三！我会记住你对机器学习和人工智能的兴趣",
        "created_at": "2026-03-29T16:45:01Z"
      }
    ],
    "user_id": "user123",
    "namespace": "test",
    "long_term_memory_strategy": {
      "strategy": "discrete"
    }
  }'

# ========================================
# 2. 获取工作记忆
# ========================================
curl -X GET "http://localhost:8000/v1/working-memory/session-cn-001" \
  -H "DISABLE_AUTH: true"

# ========================================
# 3. 更新工作记忆（追加对话）
# ========================================
curl -X PUT "http://localhost:8000/v1/working-memory/session-cn-001" \
  -H "Content-Type: application/json" \
  -H "DISABLE_AUTH: true" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "我平时喜欢在早上工作，效率比较高",
        "created_at": "2026-03-29T16:46:00Z"
      },
      {
        "role": "assistant",
        "content": "明白了，你喜欢早起工作。我会记住你这个习惯",
        "created_at": "2026-03-29T16:46:01Z"
      }
    ]
  }'

# 等待5-10秒...

# ========================================
# 4. 搜索长期记忆
# ========================================
curl -X POST "http://localhost:8000/v1/long-term-memory/search" \
  -H "Content-Type: application/json" \
  -H "DISABLE_AUTH: true" \
  -d '{
    "text": "我的兴趣爱好是什么？我喜欢什么时候工作？",
    "user_id": "user123",
    "namespace": "test",
    "limit": 5
  }'

# ========================================
# 5. 直接写入长期记忆
# ========================================
curl -X POST "http://localhost:8000/v1/long-term-memory/" \
  -H "Content-Type: application/json" \
  -H "DISABLE_AUTH: true" \
  -d '{
    "memories": [
      {
        "id": "ltm-manual-001",
        "text": "用户张三喜欢在早上工作，因为早上效率更高",
        "memory_type": "preference",
        "user_id": "user123",
        "namespace": "test",
        "topics": ["工作习惯", "时间偏好"],
        "entities": [{"name": "张三", "type": "person"}]
      },
      {
        "id": "ltm-manual-002",
        "text": "用户张三对机器学习和人工智能非常感兴趣",
        "memory_type": "fact",
        "user_id": "user123",
        "namespace": "test",
        "topics": ["兴趣爱好", "AI"],
        "entities": [{"name": "张三", "type": "person"}, {"name": "机器学习", "type": "topic"}]
      }
    ],
    "deduplicate": true
  }'

```


模块	期望能力	当前实现	备注
session_manager.py	会话生命周期管理 — start/record/stop/end	部分支持	功能分散在 working_memory.py 中，通过 session_id/user_id/namespace 标识会话。无独立会话状态机。
context_injector.py	自动上下文注入 — 基于 token budget 注入历史记忆	支持	api.py 中 memory_prompt 端点 + summarization.py 自动摘要超出窗口的记忆
consolidation.py	记忆维护 — Decay/Merge/Prune	支持	- Prune: forget_long_term_memories() 按策略删除
- Merge: deduplication 基于 memory_hash 合并
- Decay: access_count + recency boost
collectors.py	事件收集 — 3层脱敏	部分支持	prompt_security.py 提供 prompt 注入防护，非用户数据脱敏。无"3层脱敏"机制。
hooks.py	生命周期钩子	不支持	无显式 hook 系统。内存提取策略可部分模拟（extraction 时机）。
storage_sqlite.py	持久化存储 — SQLite	不支持	使用 Redis 存储，非 SQLite。working memory 用 Redis hash/string，long-term 用 RedisVL 向量索引
storage_lancedb.py	向量检索 — 语义+关键词+结构化过滤	支持	使用 RedisVL 实现向量检索，支持 TextQuery、FilterQuery、VectorQuery 组合
orchestrator.py	顶层 Facade — 统一入口	不存在	功能分散在 working_memory.py、long_term_memory.py、api.py、mcp.py 中，无统一 Facade
api_http.py / api_mcp.py	外部接口 — REST + MCP	支持	api.py (REST) + mcp.py (MCP) 双协议支持

### agent-memory-server的原理介绍
#### 主项目结构
```text
agent-memory-server/
├── agent_memory_server/          # 核心服务器包
│   ├── main.py                   # FastAPI 应用入口
│   ├── api.py                    # REST API 端点 (1320+ 行)
│   ├── mcp.py                    # MCP 服务器实现 (1245+ 行)
│   ├── cli.py                    # CLI 命令行工具
│   ├── config.py                 # 配置管理 (650+ 行)
│   ├── auth.py                   # OAuth2/JWT 认证
│   ├── models.py                 # Pydantic 数据模型
│   │
│   ├── working_memory.py         # 工作内存 (会话级)
│   ├── long_term_memory.py       # 长期记忆 (持久化)
│   ├── memory_vector_db.py       # 向量数据库抽象
│   ├── memory_vector_db_factory.py # 可插拔后端工厂
│   │
│   ├── extraction.py              # 记忆提取
│   ├── summarization.py          # 对话摘要
│   ├── memory_strategies.py      # 记忆策略配置
│   ├── summary_views.py          # 摘要视图
│   ├── filters.py                # 搜索过滤
│   │
│   ├── docket_tasks.py           # 后台任务定义
│   ├── dependencies.py           # FastAPI 依赖注入
│   ├── migrations.py             # 数据库迁移
│   │
│   ├── llm/                      # LLM 客户端 (LiteLLM)
│   │   ├── client.py
│   │   ├── types.py
│   │   └── exceptions.py
│   │
│   ├── engines/simplemem/         # SimpleMem 引擎
│   │   ├── core/
│   │   └── adapters/
│   │
│   ├── _aws/                     # AWS Bedrock 支持
│   └── utils/                    # 工具模块
│
├── agent-memory-client/          # Python SDK
│   ├── agent_memory_client/
│   └── integrations/langchain.py  # LangChain 集成
│
├── tests/                        # 测试套件 (60+ 测试文件)
├── examples/                     # 示例代码
└── docker-compose.yml             # Docker 编排

核心命令
uv run agent-memory api              # REST API 服务
uv run agent-memory mcp              # MCP 服务 (stdio)
uv run agent-memory task-worker      # 后台任务处理
uv run agent-memory rebuild-index   # 重建搜索索引
uv run agent-memory migrate-memories # 记忆迁移
```

#### 双层记忆系统

##### Working Memory (工作记忆)：https://opncd.ai/share/ZgZdMuH2
- 会话级存储
- 消息存储与上下文管理
- 自动摘要生成
- 支持多种策略 (discrete, summary, preferences, custom)

###### API 接口
https://opncd.ai/share/N1P7w7v5

| Endpoint | Method | Handler | 功能 |
|----------|--------|---------|------|
| `/v1/working-memory/` | GET | `list_sessions` | 列出所有会话 |
| `/v1/working-memory/{session_id}` | GET | `get_working_memory` | 获取会话的 working memory |
| `/v1/working-memory/{session_id}` | PUT | `put_working_memory` | 设置/替换会话的 working memory |
| `/v1/working-memory/{session_id}` | DELETE | `delete_working_memory` | 删除会话的 working memory |

###### get_working_memory
```text
┌─────────────────────────────────────────────────────────────┐
│                    get_working_memory                        │
├─────────────────────────────────────────────────────────────┤
│  1. 构建 Redis key (Keys.working_memory_key)               │
│  2. 检查迁移状态 ────────────────────────────────────────→ │
│     ├── 已完成 → 直接 JSON.GET                              │
│     │    ↓                                                   │
│     └── 未完成 → 检查 key type                              │
│         ├── ReJSON-RL → JSON.GET                            │
│         └── string → 懒迁移到 JSON                          │
│  3. 索引回退 (如果 key 不存在)                              │
│     → 通过搜索索引解析实际 key                              │
│  4. 长期记忆重建 (如果仍不存在且启用)                       │
│     → 从 long-term memory 恢复 messages                    │
│  5. 反序列化 → 返回 WorkingMemory 对象                     │
└─────────────────────────────────────────────────────────────┘

```

###### put_working_memory
```text
┌─────────────────────────────────────────────────────────────┐
│              put_working_memory (REST API层)                │
├─────────────────────────────────────────────────────────────┤
│  1. 验证输入 (memories 有 id, messages 非空)               │
│  2. 转换为 WorkingMemory 对象                               │
│  3. Summarization (token 超过 context window 时)            │
│  4. set_working_memory → 写入 Redis JSON                   │
│  5. 后台任务: promote_working_memory_to_long_term          │
│     └── 从 working memory 提取并晋升到 long-term storage  │
│  6. 计算 context 使用百分比                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│              set_working_memory (core 函数)                 │
├─────────────────────────────────────────────────────────────┤
│  - 仅做存储：不包含 summarization / long-term 逻辑         │
└─────────────────────────────────────────────────────────────┘
```

##### Long-term Memory (长期记忆)：
持久化语义搜索
向量相似度检索
元数据过滤 (namespace, user_id, session_id, topics, entities)
去重机制 (content hash + 语义去重)
遗忘策略 (forgetting policies)

###### API 接口


| Endpoint | Method | Handler | 功能 |
|----------|--------|---------|------|
| `/v1/long-term-memory/` | POST | `create_long_term_memory` | 创建长期记忆 |
| `/v1/long-term-memory/search` | POST | `search_long_term_memory` | 语义搜索长期记忆 |
| `/v1/long-term-memory/{memory_id}` | GET | `get_long_term_memory` | 获取单条记忆 |
| `/v1/long-term-memory/{memory_id}` | PATCH | `update_long_term_memory` | 更新记忆内容 |
| `/v1/long-term-memory` | DELETE | `delete_long_term_memory` | 删除记忆 |
| `/v1/long-term-memory/compact` | POST | `compact_long_term_memories` | 压缩/清理记忆 |
| `/v1/long-term-memory/forget` | POST | `forget_long_term_memories` | 选择性遗忘记忆 |

参考
[长期记忆API原理](./docs/long_term_memory_api_impl.md)
[长期记忆API原理2](./docs/long_term_memory_api_detail.md)

核心模块函数 (long_term_memory.py)

函数	功能
index_long_term_memories	为记忆生成向量索引
search_long_term_memories	核心搜索实现
count_long_term_memories	统计记忆数量
deduplicate_by_hash	按 hash 去重
deduplicate_by_id	按 ID 去重
deduplicate_by_semantic_search	语义去重
promote_working_memory_to_long_term	将工作记忆提升为长期记忆
delete_long_term_memories	删除指定记忆
get_long_term_memory_by_id	按 ID 获取记忆
update_long_term_memory	更新记忆
compact_long_term_memories	压缩/清理
forget_long_term_memories	选择性遗忘
periodic_forget_long_term_memories	周期性遗忘任务

##### 摘要（summary）
[摘要机制](./docs/summarization-capabilities.md)

##### 异步任务管理
[任务管理机制](./docs/task-processing-principle.md)

### 不同产品间的对比

### TODO 待分析
- agent-memory-server整个项目结构
- 
- 长期记忆的压缩机制是如何实现的？
  - https://opncd.ai/share/eUvjD36Z
    - 识别agentmemory的压缩机制
    - 对比simplemem的压缩机制(https://opncd.ai/share/0yNC2slc)
- 长期记忆的遗忘机制是如何实现的
- 长期记忆的定时遗忘机制是如何实现的？