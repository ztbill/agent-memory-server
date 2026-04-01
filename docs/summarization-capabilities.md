# 摘要能力概述

本文档介绍 Agent Memory Server 提供的两类摘要能力：会话摘要和分区摘要。

---

## 概述

系统提供两套独立的摘要机制：

| 类型 | 数据源 | 触发方式 | 用途 |
|------|--------|----------|------|
| 会话摘要 | Working Memory (会话消息) | 自动 (token 超阈值) | 压缩会话上下文，保持在 LLM context window 内 |
| 分区摘要 | Long-term Memory (持久记忆) | 手动或定时 | 按维度聚合长期记忆，生成可检索的知识摘要 |

---

## 会话摘要 (Working Memory Summarization)

### 什么是会话摘要

当单个会话的消息 token 数量超过阈值时，系统会自动将较早的消息压缩为一个摘要，保留最近的消息内容。这样可以：

- 防止会话内容超出 LLM 的 context window 限制
- 保持对话历史的"远期记忆"同时不丢失近期上下文

### 工作流程

```
用户发送消息 → 累计 token 数量 → 超过 70% 阈值 
→ _summarize_working_memory() → 旧消息压缩为 summary 
→ 写入 session context 字段 → 保留最近 40% 消息
```

### 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `enable_working_memory_summarization` | `true` | 是否启用会话摘要 |
| `summarization_threshold` | `0.7` | 触发摘要的 token 阈值 (70%) |
| `progressive_summarization_prompt` | (模板) | 增量摘要的提示词 |

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/working-memory/{session_id}` | PUT | 设置工作记忆，超过阈值时自动触发摘要 |
| `set_working_memory` (MCP) | - | MCP 版本的写入口，同样支持自动摘要 |

---

## 分区摘要 (SummaryView)

### 什么是分区摘要

分区摘要是按特定维度（如用户、项目、命名空间）对长期记忆进行聚合摘要的能力。通过配置 `SummaryView`，系统可以：

- 筛选符合条件的长期记忆
- 按指定维度分组
- 对每个分组生成摘要

### 典型场景

- 按用户生成"用户画像摘要"
- 按项目生成"项目知识汇总"
- 按命名空间生成"团队知识库"

### 配置字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 视图唯一标识 |
| `source` | string | 数据源，目前只支持 `long_term` |
| `group_by` | list[string] | 分组维度，可选 `user_id`, `namespace`, `session_id`, `memory_type` |
| `filters` | dict | 过滤条件 |
| `time_window_days` | int | 时间窗口，只处理最近 N 天的记忆 |
| `continuous` | bool | 是否开启定时刷新 |
| `prompt` | string | 自定义摘要提示词 |

### 触发方式

| 触发方式 | 配置 | 调用方式 |
|----------|------|----------|
| 手动触发 | `continuous=false` (默认) | POST `/v1/summary-views/{view_id}/run` |
| 单分区触发 | - | POST `/v1/summary-views/{view_id}/partitions/run` |
| 定时触发 | `continuous=true` | `periodic_refresh_summary_views` 每 60 分钟运行 |

> 定时任务通过 `summary_view_refresh_every_minutes` 配置间隔，默认 60 分钟。

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/summary-views` | POST | 创建 SummaryView |
| `/v1/summary-views` | GET | 列出所有视图 |
| `/v1/summary-views/{view_id}` | GET | 获取视图详情 |
| `/v1/summary-views/{view_id}` | DELETE | 删除视图 |
| `/v1/summary-views/{view_id}/run` | POST | 异步运行完整刷新 |
| `/v1/summary-views/{view_id}/partitions/run` | POST | 同步计算单个分区 |
| `/v1/summary-views/{view_id}/partitions` | GET | 列出已物化的分区摘要 |

### MCP 接口

| 工具 | 说明 |
|------|------|
| `compact_long_term_memories` | 长期记忆去重压缩 |

---

## CLI 命令

```bash
# 手动触发长期记忆压缩
uv run agent-memory schedule-task "agent_memory_server.long_term_memory.compact_long_term_memories"
```

---

## 对比总结

| 特性 | 会话摘要 | 分区摘要 |
|------|----------|----------|
| 数据源 | 单会话消息列表 | 长期记忆库 |
| 触发时机 | 自动 (token 超阈值) | 手动或定时 |
| 输出位置 | session.context | summary_view:...:summary:... |
| 摘要方式 | 增量累积 | 分组聚合 |
| 配置粒度 | 全局配置 | 按视图配置 |

---

## 长期记忆压缩 (Memory Compaction)

### 什么是长期记忆压缩

长期记忆压缩不是摘要能力，而是一种**去重/清理**操作。它会：

- **Hash 去重**: 找出内容完全相同的记忆，删除旧保留新
- **语义去重**: 找出语义相近的记忆，基于向量相似度合并或删除

### 与分区摘要的区别

| 维度 | 分区摘要 (SummaryView) | 长期记忆压缩 (compact) |
|------|----------------------|---------------------|
| **能力类型** | LLM 生成摘要 | 去重/清理 |
| **实现方式** | 调用 LLM 生成新文本 | 查找重复项并删除旧记录 |
| **数据变化** | 原记忆保留，新增摘要 | 原记忆被删除 |
| **输出** | `summary_view:...:summary:...` | 删除后的记录数量 |

### 简单比喻

- **分区摘要** = 把100页会议记录**读一遍**，提炼成5页摘要
- **压缩** = 发现有10页内容完全一样，**删掉9页**

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/v1/long-term-memory/compact` | POST | 长期记忆压缩 |
| `compact_long_term_memories` (MCP) | - | MCP 版本的压缩工具 |

### CLI 命令

```bash
# 手动触发长期记忆压缩
uv run agent-memory schedule-task "agent_memory_server.long_term_memory.compact_long_term_memories"
```

---

## 三种能力对比

| 能力 | 数据源 | 触发方式 | 目的 |
|------|--------|----------|------|
| 会话摘要 | Working Memory 消息 | 自动 (token 超阈值) | 压缩上下文，保持在 context window 内 |
| 分区摘要 | Long-term Memory | 手动或定时 | 按维度聚合，生成可检索的知识摘要 |
| 长期记忆压缩 | Long-term Memory | 手动或定时 | 去重/清理，优化存储空间 |

---

## 简单比喻

- **会话摘要** = 会议中实时做笔记，**太长就把之前的笔记压缩成一句话**
- **分区摘要** = 周末回顾所有会议记录，按**人**或**项目**生成汇总报告（把100页会议记录读一遍，提炼成5页摘要）
- **压缩** = 发现有10页内容完全一样，**删掉9页**
