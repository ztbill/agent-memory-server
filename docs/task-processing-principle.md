# Agent Memory Server - 任务处理实现原理详解

## 概述

本文档详细解释 Agent Memory Server 项目中后台任务处理的实现原理，包括任务定义、注册、入队、消费的全流程，以及任务数据在 Redis 中的存储结构。

---

## 一、整体架构

### 1.1 核心组件

| 组件 | 位置 | 作用 |
|------|------|------|
| **Task Collection** | `docket_tasks.py` | 定义所有可执行的后台任务 |
| **HybridBackgroundTasks** | `dependencies.py` | 任务入队的抽象层，支持两种模式 |
| **Docket** | pydocket 库 | Redis 任务队列框架 |
| **Worker** | CLI `task-worker` 命令 | 从 Redis 消费并执行任务 |

### 1.2 两种执行模式

```
┌─────────────────────────────────────────────────────────────────┐
│                      任务处理模式                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│    API/MCP Server                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────┐         ┌─────────────────┐              │
│  │ Docket 模式     │         │  Asyncio 模式   │              │
│  │ (生产环境)      │         │  (开发环境)      │              │
│  └────────┬────────┘         └────────┬────────┘              │
│           │                             │                      │
│           ▼                             ▼                      │
│  ┌─────────────────┐         ┌─────────────────┐              │
│  │ Redis Stream    │         │ asyncio.create_ │              │
│  │ (任务队列)      │         │ task()          │              │
│  └────────┬────────┘         │ (进程内执行)    │              │
│           │                   └────────┬────────┘              │
│           ▼                            │                       │
│  ┌─────────────────┐                   │                       │
│  │ task-worker     │                   │                       │
│  │ (独立进程消费)  │                   │                       │
│  └─────────────────┘                   │                       │
│                                         │                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、任务定义

### 2.1 定义位置

文件: `agent_memory_server/docket_tasks.py`

```python
task_collection = [
    extract_memory_structure,      # 提取记忆结构
    summarize_session,             # 会话摘要
    index_long_term_memories,      # 索引长期记忆
    compact_long_term_memories,    # 压缩长期记忆
    extract_memories_with_strategy,# 策略提取记忆
    promote_working_memory_to_long_term,  # 记忆晋升
    run_delayed_extraction,        # 延迟提取
    delete_long_term_memories,    # 删除记忆
    forget_long_term_memories,     # 遗忘记忆
    periodic_forget_long_term_memories,  # 周期性遗忘
    update_last_accessed,          # 更新访问时间
    refresh_summary_view,          # 刷新摘要视图
    periodic_refresh_summary_views, # 周期性刷新摘要
]
```

共 **13 个任务**，都是 async 函数。

### 2.2 任务函数示例

```python
# long_term_memory.py
async def index_long_term_memories(
    namespace: str | None = None,
    batch_size: int = 100,
    force: bool = False
) -> None:
    """索引长期记忆用于语义搜索"""
    ...
```

---

## 三、任务注册

### 3.1 注册时机

FastAPI 启动时 (lifespan)，文件: `agent_memory_server/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时执行
    if settings.use_docket:
        await register_tasks()  # 注册任务到 Docket
```

### 3.2 注册实现

文件: `agent_memory_server/docket_tasks.py`

```python
async def register_tasks() -> None:
    """Register all task functions with Docket."""
    if not settings.use_docket:
        return

    async with Docket(
        name=settings.docket_name,           # "memory-server"
        url=redis_url_for_docket(settings.redis_url),
    ) as docket:
        # 注册所有任务函数
        for task in task_collection:
            docket.register(task)
        
        logger.info(f"Registered {len(task_collection)} background tasks")
```

**作用**: 将任务函数注册到 Docket，使 Worker 能够发现和执行这些任务。

---

## 四、任务入队

### 4.1 两种触发方式

#### 方式 A: API/MCP 调用时自动入队

```python
# API 或 MCP 调用时
async def some_endpoint(...):
    background_tasks = get_background_tasks()
    
    # 添加后台任务
    background_tasks.add_task(
        index_long_term_memories,
        namespace=namespace,
        batch_size=batch_size
    )
```

#### 方式 B: CLI 手动调度

```bash
# 命令行调度任务
uv run agent-memory schedule-task \
    "agent_memory_server.long_term_memory.compact_long_term_memories" \
    -a batch_size=50
```

### 4.2 核心实现: HybridBackgroundTasks

文件: `agent_memory_server/dependencies.py`

```python
class HybridBackgroundTasks(BackgroundTasks):
    def add_task(self, func, *args, **kwargs):
        if settings.use_docket:
            # === Docket 模式 ===
            def run_in_thread():
                async def schedule_task():
                    async with Docket(
                        name=settings.docket_name,
                        url=redis_url_for_docket(settings.redis_url),
                    ) as docket:
                        # 将任务写入 Redis Stream
                        await docket.add(func)(*args, **kwargs)
                
                asyncio.run(schedule_task())

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                future.result()
        else:
            # === Asyncio 模式 ===
            asyncio.create_task(self._run_task(func, *args, **kwargs))
```

**关键点**:
- 使用 ThreadPoolExecutor 避免阻塞当前事件循环
- 创建新的 asyncio.run() 来执行 async Docket 操作
- `docket.add(func)(*args, **kwargs)` 将任务写入 Redis

---

## 五、任务消费 (Worker)

### 5.1 启动 Worker

```bash
# 命令行启动 Worker
uv run agent-memory task-worker --concurrency 10 --redelivery-timeout 120
```

### 5.2 Worker 实现

文件: `agent_memory_server/cli.py`

```python
async def _ensure_stream_and_group():
    """确保 Redis Stream 和 Consumer Group 存在"""
    redis = await get_redis_conn()
    stream_key = docket_stream_key(settings.docket_name, settings.redis_url)
    
    # 创建消费者组
    await redis.xgroup_create(
        name=stream_key,
        groupname="docket-workers",
        id="$",  # 从最新消息开始消费
        mkstream=True
    )

async def _run_worker():
    await _ensure_stream_and_group()
    
    await Worker.run(
        docket_name=settings.docket_name,
        url=redis_url_for_docket(settings.redis_url),
        concurrency=10,
        redelivery_timeout=timedelta(seconds=120),
        tasks=["agent_memory_server.docket_tasks:task_collection"],
    )
```

### 5.3 Worker 执行流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    Worker.run() 执行流程                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 连接 Redis                                                   │
│  2. 加入 Consumer Group: "docket-workers"                       │
│  3. XREADGROUP 阻塞等待新任务                                    │
│     │                                                          │
│     ▼                                                          │
│  4. 收到任务 → 反序列化                                          │
│     │                                                          │
│     ▼                                                          │
│  5. 从 task_collection 查找对应的执行函数                       │
│     │                                                          │
│     ▼                                                          │
│  6. 执行: await func(*args, **kwargs)                           │
│     │                                                          │
│     ├─ 成功 → XACK 确认删除                                     │
│     │                                                          │
│     └─ 失败 → 重投 (redelivery_timeout 后重新入队)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 六、Redis 中存储的任务内容

### 6.1 数据结构

| 存储类型 | Key 格式 | 用途 |
|----------|----------|------|
| **Stream** | `{docket}:stream` | 即时任务队列 |
| **Sorted Set** | `{docket}:queue` | 定时任务队列 |
| **Hash** | `{docket}:{execution_id}` | 任务执行状态 |

### 6.2 Stream 中的任务数据

当调用 `docket.add(task_func)(arg1=val1)` 时，Redis Stream 中存储:

```redis
# Stream: docket:memory-server:stream
1712000000000000-0 > {
    "task": "gAAAAABk...",        # cloudpickle 序列化数据
    "id": "exec_abc123",          # 执行 ID
    "created_at": "2025-04-01T12:00:00Z"
}
```

### 6.3 序列化机制: cloudpickle

> **重要安全提示**: 
> 
> Docket 使用 **cloudpickle** 序列化任务函数和参数。cloudpickle 可以序列化几乎任何 Python 对象（包括 lambda 和闭包），但反序列化时可以执行任意代码。**请确保只调度来自可信来源的任务。**

```python
# 序列化过程 (伪代码)
import cloudpickle

task_data = {
    "func": index_long_term_memories,
    "kwargs": {"namespace": "user123", "batch_size": 100}
}
serialized = cloudpickle.dumps(task_data)
# → "gAAAAABk..." (二进制数据)

# 写入 Redis
redis.xadd("docket:memory-server:stream", {"task": serialized})
```

### 6.4 任务状态 Hash

```
# Hash: docket:memory-server:exec_abc123
{
    "state": "COMPLETED",           # QUEUED / RUNNING / COMPLETED / FAILED
    "worker": "worker-1",
    "started_at": "2025-04-01T12:00:01Z",
    "completed_at": "2025-04-01T12:00:05Z",
    "result": "...",
    "error": null,
    "attempts": 1
}
```

---

## 七、完整数据流图

```
用户请求
    │
    ▼
┌─────────────────────────────────────────────────┐
│              API Endpoint                        │
│         (api.py / mcp.py)                       │
└────────────┬────────────────────────────────────┘
             │
             │ background_tasks.add_task(...)
             │
             ▼
┌─────────────────────────────────────────────────┐
│        HybridBackgroundTasks.add_task()          │
│                                                 │
│  if settings.use_docket:                        │
│      → docket.add() → Redis Stream             │
│  else:                                          │
│      → asyncio.create_task() → 进程内执行      │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
            ┌──────────────┐
            │ Redis Stream │
            │ (docket:     │
            │  memory-     │
            │  server:     │
            │  stream)     │
            └──────┬───────┘
                   │ XREADGROUP (阻塞)
                   ▼
            ┌──────────────┐
            │ task-worker  │
            │ (Worker.run) │
            └──────┬───────┘
                   │
                   ▼
            ┌──────────────────────────────────┐
            │ 查找 task_collection 中的函数    │
            │ await index_long_term_memories()│
            └────────────┬─────────────────────┘
                         │
                  ┌──────┴───────┐
                  │ 成功 / 失败   │
                  ▼              ▼
             XACK 删除      重投队列
```

---

## 八、常用命令

### 8.1 启动服务

```bash
# 开发模式 (asyncio, 无需 worker)
uv run agent-memory api --task-backend=asyncio

# 生产模式 (Docket, 需要 worker)
uv run agent-memory api --task-backend=docket

# 启动 Worker
uv run agent-memory task-worker --concurrency 10
```

### 8.2 手动调度任务

```bash
# 调度任务
uv run agent-memory schedule-task \
    "agent_memory_server.long_term_memory.compact_long_term_memories" \
    -a batch_size=50 -a dry_run=false

# 调度带时间的任务 (需要修改 CLI 支持)
```

### 8.3 查看 Redis 中的任务

```bash
# 查看 Stream 中的任务
redis-cli XREAD COUNT 10 STREAMS "docket:memory-server:stream" 0

# 查看任务状态
redis-cli HGETALL "docket:memory-server:exec_abc123"

# 查看所有相关 key
redis-cli KEYS "docket:*"
```

---

## 九、配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `docket_name` | "memory-server" | Docket 实例名称 |
| `use_docket` | True | 是否使用 Docket 模式 |
| `--concurrency` | 10 | Worker 并发数 |
| `--redelivery-timeout` | 2x LLM timeout | 任务重投超时时间 |

---

## 十、总结

1. **任务定义**: 在 `docket_tasks.py` 中定义 13 个 async 函数
2. **任务注册**: 启动时将任务函数注册到 Docket
3. **任务入队**: 通过 `HybridBackgroundTasks` 入队，写入 Redis Stream
4. **任务消费**: Worker 从 Redis 消费，反序列化后执行
5. **存储格式**: 使用 cloudpickle 序列化函数和参数，存入 Redis Stream
6. **两种模式**: 生产环境用 Docket (分布式)，开发环境用 asyncio (单进程)

这个架构设计清晰，通过 HybridBackgroundTasks 抽象了两种模式，可以根据部署需求灵活切换。