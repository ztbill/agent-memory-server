# 图记忆模块设计文档

## 1. 概述

图记忆模块 (Graph Memory) 为 agent-memory-server 提供知识图谱存储和检索能力,支持实体和关系的管理,与现有向量存储系统互补。

### 1.1 设计目标

- 实现知识图谱存储,支持实体节点和关系边
- 通过工厂模式支持多种图数据库后端
- 提供图+向量+关键词的混合检索
- 与现有长期记忆系统同步写入

### 1.2 与 Mem0 Graph Memory 的区别

| 特性 | Mem0 Graph Memory | 本模块 |
|------|-------------------|--------|
| 写入时机 | 与memory.add()一起双写 | 索引长期记忆时同步写入 |
| 搜索方式 | 向量搜索 + 图增强 | 支持独立图搜索和混合检索 |
| 图后端 | Neo4j, Memgraph等 | NetworkX (当前), RedisGraph (待支持) |
| 返回格式 | results + relations | GraphSearchResults |

---

## 2. 架构

### 2.1 目录结构

```
agent_memory_server/graph/
├── __init__.py              # 公共接口导出
├── base.py                  # 抽象基类 MemoryGraph
├── models.py                # 数据模型
├── factory.py               # 工厂模式
├── extraction.py            # 实体/关系抽取
├── search.py                # RRF 混合检索
└── impls/
    ├── __init__.py
    ├── networkx.py         # NetworkX 实现
    └── redisgraph.py        # RedisGraph 实现 (待)
```

### 2.2 组件关系

```
┌─────────────────────────────────────────────────────────────┐
│                    调用方 (long_term_memory)                │
└────────────────────────────┬────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     graph.factory                            │
│                  get_memory_graph()                         │
└────────────────────────────┬────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                     MemoryGraph (ABC)                       │
│           add_entities / add_relations / search             │
└────────────────────────────┬────────────────────────────────┘
                            ▼
         ┌──────────────────┴──────────────────┐
         ▼                                     ▼
┌─────────────────────┐            ┌─────────────────────┐
│  NetworkXGraphMemory │            │  RedisGraphMemory   │
│   (当前使用)         │            │    (待支持)          │
└─────────────────────┘            └─────────────────────┘
```

---

## 3. 数据模型

### 3.1 GraphEntity (实体/节点)

```python
class GraphEntity(BaseModel):
    id: str                          # 唯一标识符 (ULID)
    name: str                        # 实体名称
    entity_type: str = "unknown"    # 实体类型 (person/organization/location)
    user_id: str | None             # 用户ID (隔离用)
    namespace: str | None            # 命名空间 (进一步隔离)
    session_id: str | None          # 会话范围
    properties: dict[str, Any]      # 额外属性
    created_at: datetime            # 创建时间
    updated_at: datetime            # 更新时间
```

### 3.2 GraphRelation (关系/边)

```python
class GraphRelation(BaseModel):
    id: str                          # 唯一标识符
    source: str                     # 源实体名称
    source_type: str = "unknown"    # 源实体类型
    target: str                      # 目标实体名称
    target_type: str = "unknown"    # 目标实体类型
    relation_type: str               # 关系类型
    properties: dict[str, Any]       # 关系属性
    user_id: str | None             # 用户ID
    namespace: str | None
    score: float = 1.0             # 置信度分数
    created_at: datetime
```

**关系类型**:

| 类型 | 描述 | 示例 |
|------|------|------|
| `knows` | 人物相互认识 | Alice knows Bob |
| `works_at` | 在组织工作 | John works_at Apple |
| `located_in` | 位于某地 | Apple located_in Cupertino |
| `interested_in` | 对某主题感兴趣 | Alice interested_in AI |
| `lives_in` | 居住在某地 | Joseph lives_in Seattle |
| `related_to` | 通用关系 | X related_to Y |

### 3.3 GraphSearchResult (搜索结果)

```python
class GraphSearchResult(BaseModel):
    source: str
    source_type: str = "unknown"
    relationship: str
    target: str
    target_type: str = "unknown"
    score: float = 1.0
```

---

## 4. 核心接口

### 4.1 MemoryGraph 抽象基类

```python
class MemoryGraph(ABC):
    @abstractmethod
    async def add_entities(self, entities: list[GraphEntity]) -> list[str]:
        """添加实体节点"""
        pass
    
    @abstractmethod
    async def add_relations(self, relations: list[GraphRelation]) -> list[str]:
        """添加关系边"""
        pass
    
    @abstractmethod
    async def search(
        self,
        query: str,
        user_id: str | None = None,
        namespace: str | None = None,
        limit: int = 10,
    ) -> GraphSearchResults:
        """搜索知识图谱"""
        pass
    
    @abstractmethod
    async def delete_entity(self, entity_id: str) -> bool:
        """删除实体及其关联关系"""
        pass
    
    @abstractmethod
    async def delete_user_graph(self, user_id: str, namespace: str | None = None) -> int:
        """删除用户的所有实体和关系"""
        pass
```

---

## 5. 实现详解

### 5.1 NetworkX 实现 (当前)

使用 `networkx.MultiDiGraph` 实现内存图存储。

**特点**:
- 内存存储,无需外部依赖
- 适合中小规模数据
- 单进程内共享

**核心逻辑**:

```python
class NetworkXGraphMemory(MemoryGraph):
    def __init__(self):
        self._graph = nx.MultiDiGraph()
    
    async def add_entities(self, entities: list[GraphEntity]) -> list[str]:
        # 将实体添加为图的节点
        for entity in entities:
            self._graph.add_node(
                entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                user_id=entity.user_id,
                namespace=entity.namespace,
                properties=entity.properties,
            )
        return [e.id for e in entities]
    
    async def add_relations(self, relations: list[GraphRelation]) -> list[str]:
        # 通过名称查找实体节点,添加边
        for rel in relations:
            source_node = self._find_node_by_name(rel.source, rel.user_id)
            target_node = self._find_node_by_name(rel.target, rel.user_id)
            if source_node and target_node:
                self._graph.add_edge(source_node, target_node, ...)
        return [r.id for r in relations]
    
    async def search(self, query: str, ...) -> GraphSearchResults:
        # 遍历节点,匹配名称包含query的实体
        # 返回该实体的所有出边作为关系结果
```

### 5.2 关系抽取 (LLM)

```python
async def extract_relations_llm(
    text: str,
    known_entities: list[str],
) -> list[dict]:
    """使用 LLM 从文本中抽取实体间关系"""
    
    prompt = """从文本中提取实体之间的关系。
    已知实体: {entities}
    文本: {text}
    
    返回JSON: {{"relations": [
        {"source": "源实体", "target": "目标实体", "relation_type": "关系类型"}
    ]}}"""
    
    response = await LLMClient.create_chat_completion(
        model=settings.fast_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    
    data = json.loads(response.content)
    # 过滤只保留涉及已知实体的关系
    return [r for r in data.get("relations", []) 
            if r.get("source") in known_set and r.get("target") in known_set]
```

### 5.3 图构建流程

```python
async def build_graph_from_memory(
    memory_text: str,
    user_id: str,
    namespace: str | None = None,
    existing_entities: list[str] | None = None,
) -> tuple[list[GraphEntity], list[GraphRelation]]:
    """从记忆记录构建图"""
    
    # 1. 使用 LLM 抽取关系
    relations_data = await extract_relations_llm(memory_text, existing_entities)
    
    # 2. 收集所有涉及的实体名称
    entity_names = set()
    for rel in relations_data:
        entity_names.add(rel["source"])
        entity_names.add(rel["target"])
    
    # 3. 构建 GraphEntity 列表
    entities = [
        GraphEntity(
            id=str(ulid.ULID()),
            name=name,
            user_id=user_id,
            namespace=namespace,
        )
        for name in entity_names
    ]
    
    # 4. 构建 GraphRelation 列表
    relations = [
        GraphRelation(
            id=str(ulid.ULID()),
            source=rel["source"],
            target=rel["target"],
            relation_type=rel["relation_type"],
            user_id=user_id,
            namespace=namespace,
        )
        for rel in relations_data
    ]
    
    return entities, relations
```

---

## 6. 混合检索 (RRF)

### 6.1 Reciprocal Rank Fusion

RRF 是一种融合多路检索结果的无参排序算法:

```python
def rrf_fusion(
    results_list: list[list[MemoryRecordResult]],
    k: int = 60,
) -> list[MemoryRecordResult]:
    """RRF 融合算法"""
    score_map = {}
    
    for results in results_list:
        for rank, result in enumerate(results):
            # RRF 分数: 1 / (k + rank + 1)
            score = 1.0 / (k + rank + 1)
            score_map[result.id] = score_map.get(result.id, 0) + score
    
    # 按融合分数降序排序
    return sorted(score_map.items(), key=lambda x: x[1], reverse=True)
```

### 6.2 搜索模式

扩展 `SearchModeEnum`:

```python
class SearchModeEnum(str, Enum):
    SEMANTIC = "semantic"        # 向量语义
    KEYWORD = "keyword"          # 关键词
    HYBRID = "hybrid"           # 向量+关键词
    GRAPH = "graph"             # 纯图检索
    GRAPH_SEMANTIC = "graph_semantic"   # 图+向量
    GRAPH_KEYWORD = "graph_keyword"     # 图+关键词
    GRAPH_HYBRID = "graph_hybrid"       # 全部混合
```

---

## 7. 配置

### 7.1 配置项

```python
# config.py
memory_graph_factory: str = (
    "agent_memory_server.graph.factory.create_networkx_memory"
)
enable_graph_memory: bool = False
```

### 7.2 使用方式

```python
# 启用图记忆
enable_graph_memory = True

# 切换图后端
memory_graph_factory = "agent_memory_server.graph.factory.create_redisgraph_memory"
```

---

## 8. 与长期记忆集成

### 8.1 同步写入流程

在 `index_long_term_memories` 中:

```python
if settings.enable_graph_memory:
    for memory in processed_memories:
        graph = await get_memory_graph()
        
        # 从 MemoryRecord 提取实体
        entities = memory.entities or []
        
        # 构建图 (抽取关系)
        graph_entities, graph_relations = await build_graph_from_memory(
            memory_text=memory.text,
            user_id=memory.user_id,
            existing_entities=entities,
        )
        
        # 写入图数据库
        await graph.add_entities(graph_entities)
        await graph.add_relations(graph_relations)
```

### 8.2 数据流

```
MemoryRecord (text, entities)
        │
        ▼
┌───────────────────────────────────────┐
│          extraction.py                 │
│  1. extract_relations_llm()            │
│  2. build_graph_from_memory()          │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│        MemoryGraph (ABC)              │
│  - add_entities()                     │
│  - add_relations()                    │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│     NetworkXGraphMemory               │
│  - 创建节点 (实体)                    │
│  - 创建边 (关系)                      │
└───────────────────────────────────────┘
```

---

## 9. 使用示例

### 9.1 基本使用

```python
from agent_memory_server.graph import get_memory_graph
from agent_memory_server.graph.models import GraphEntity, GraphRelation

async def example():
    graph = await get_memory_graph()
    
    # 添加实体
    entities = [
        GraphEntity(id="e1", name="Alice", entity_type="person", user_id="u1"),
        GraphEntity(id="e2", name="Bob", entity_type="person", user_id="u1"),
    ]
    await graph.add_entities(entities)
    
    # 添加关系
    relations = [
        GraphRelation(
            source="Alice", target="Bob", 
            relation_type="knows", user_id="u1"
        ),
    ]
    await graph.add_relations(relations)
    
    # 搜索
    results = await graph.search(query="Alice", user_id="u1")
    for r in results.results:
        print(f"{r.source} -{r.relationship}-> {r.target}")
```

### 9.2 从记忆构建图

```python
from agent_memory_server.graph.extraction import build_graph_from_memory

async def build_from_memory(memory_text: str, user_id: str):
    entities, relations = await build_graph_from_memory(
        memory_text=memory_text,
        user_id=user_id,
        existing_entities=["Alice", "Bob"],  # 可选
    )
    
    graph = await get_memory_graph()
    await graph.add_entities(entities)
    await graph.add_relations(relations)
```

---

## 10. 待完成项

1. [ ] 恢复 long_term_memory.py 中的图同步写入代码
2. [ ] 完成混合检索在 search_memories 中的集成
3. [ ] RedisGraph 实现 (需 Redis 加载 RedisGraph 模块)
4. [ ] 图搜索 API 端点
5. [ ] 集成测试

---

## 11. 依赖

- `networkx` - 图数据结构
- `redis` - Redis 客户端 (RedisGraph 待支持)
- `pydantic` - 数据验证
- `ulid` - 唯一ID生成
- `tenacity` - 重试逻辑

---

*文档版本: 1.0*
*更新时间: 2026-04-02*
