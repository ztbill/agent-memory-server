
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

##### 图存储
[图存储机制](./docs/graph-memory-design.md)

### 不同产品间的对比

[产品横向对比](./docs/memory-comparison.md)

#### 外部的记忆产品解决哪些问题？
| 痛点 | 描述 | 业务影响 |
|------|------|----------|
| **Context Window 限制** | LLM 本质是无状态的，每次 API 调用都从零开始，不记得之前说过什么 | 客户对话无法跨 session 积累，agent 行为碎片化 |
| **信息遗忘** | 对话历史超出 context window 后被截断或丢失 | 长期偏好、关键决策背景无法保留，服务质量下降 |
| **成本膨胀** | 每次请求都携带完整历史，token 费用随对话长度线性增长 | 规模化后成本不可控 |
| **上下文噪音** | 大量低价值的历史记录稀释了真正重要的信息 | agent 响应质量下降，决策效率低 |
| **碎片化记忆** | 没有结构化的记忆层，agent 无法主动检索"知道什么" | 智能化程度低，依赖人工注入 context |
| **多模态记忆管理** | 需要同时管理用户级、对话级、系统级记忆 | 工程复杂度高，难以维护 |


#### 内部的记忆产品解决哪些问题？
- 记忆的申请便捷度
- 记忆数据的准确性
- 记忆的便捷的维护
- 记忆的可定制化能力
- 本地化记忆存储问题
- 通过记忆解决LLM的Token消耗问题
- 通过记忆解决跨会话记忆共享问题
#### 当前产品怎么解决业务痛点



#### 当前产品的亮点在哪里？
核心反问：大家支持的记忆产品都一样，为什么是当前这一款Agent产品
- 通过redis的便捷申请的成熟优势，以及redis轻量化部署维护的优势，目前Agent建设初期对记忆能力的要求处于快速验证产品验证阶段的优势，作为`切入点`，引导业务可以通过插件的形式便捷开启并使用记忆能力
- 提供相关便捷记忆维护能力作为吸引用户的原始资本


#### 建设思路是什么
- 短期：不对外提供记忆类产品，核心视角还是以REDIS产品建设为主，将记忆类插件能力，作为REDIS的增值能力（核心是对存储数据、向量检索、key存储的二次封装）
- 长期：跟进社区优秀思想，逐步融合其他产品的思路，整合持续优化记忆准确度，观察记忆产品走向。争取演化出单独的产品（核心是整合现有的存储能力）
- 长期：内部技术储备，通过先探索解决内部记忆问题，建设通用的记忆能力
- 用什么长期记忆开源产品不重要，演化并消化社区产品演化出自己的产品更重要，（即走自研路线，借鉴开源思想并超越社区。）
- 重点建设可灵活拓展的能力

#### 核心事项
- 提供记忆的快速容器化部署能力
- 提供基于redis的记忆存储能力
- 提供页面以及记忆的可定制化能力
- 提供记忆快速导入迁移能力

#### 不确定性在哪里？
- 从技术和产品走向看，长期记忆是否会朝着云端部署的方式去使用，还是更多通过本地方式
- 长期记忆本身是否是伪命题
- redis以及ES相关的GPL问题

### TODO 待分析
- agent-memory-server整个项目结构
- 
- 长期记忆的压缩机制是如何实现的？
  - https://opncd.ai/share/eUvjD36Z
    - 识别agentmemory的压缩机制
    - 对比simplemem的压缩机制(https://opncd.ai/share/0yNC2slc)
- 长期记忆的遗忘机制是如何实现的
- 长期记忆的定时遗忘机制是如何实现的？

#### API  接口使用demo

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

