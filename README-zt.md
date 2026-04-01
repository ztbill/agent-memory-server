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

