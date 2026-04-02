import json
import logging

from tenacity.asyncio import AsyncRetrying
from tenacity.stop import stop_after_attempt

from agent_memory_server.config import settings
from agent_memory_server.llm import LLMClient


logger = logging.getLogger(__name__)

EXTRACT_RELATIONS_PROMPT = """你是一位知识图谱构建专家。
你的任务是从给定的文本中提取实体之间的关系。

文本:
{text}

已知实体: {entities}

提取已知实体之间或新提及实体之间的所有关系。
返回一个包含 "relations" 数组的 JSON 对象。每个关系应包含:
- "source": 源实体名称
- "source_type": 源实体类型 (person/organization/location/other)
- "target": 目标实体名称
- "target_type": 目标实体类型 (person/organization/location/other)
- "relation_type": 关系类型 (knows/works_at/located_in/interested_in/lives_in/related_to)

示例: {{"relations": [{{"source": "John", "source_type": "person", "target": "Apple", "target_type": "organization", "relation_type": "works_at"}}]}}
"""


async def extract_relations_llm(
    text: str,
    known_entities: list[str],
) -> list[dict]:
    if not known_entities:
        return []

    prompt = EXTRACT_RELATIONS_PROMPT.format(
        text=text, entities=", ".join(known_entities)
    )

    try:
        async for attempt in AsyncRetrying(stop=stop_after_attempt(3)):
            with attempt:
                response = await LLMClient.create_chat_completion(
                    model=settings.fast_model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )

                data = json.loads(response.content)
                relations = data.get("relations", [])

                known_set = set(known_entities)
                return [
                    r
                    for r in relations
                    if r.get("source") in known_set and r.get("target") in known_set
                ]
    except Exception as e:
        logger.error(f"Error extracting relations: {e}")
        return []


async def build_graph_from_memory(
    memory_text: str,
    user_id: str,
    namespace: str | None = None,
    existing_entities: list[str] | None = None,
) -> tuple[list, list]:
    import ulid

    from agent_memory_server.graph.models import GraphEntity, GraphRelation

    entities_to_use = existing_entities if existing_entities else []

    relations_data = await extract_relations_llm(memory_text, entities_to_use)

    entities = []
    relations = []

    entity_names = set()
    for rel in relations_data:
        entity_names.add(rel.get("source"))
        entity_names.add(rel.get("target"))

    for name in entity_names:
        entities.append(
            GraphEntity(
                id=str(ulid.ULID()),
                name=name,
                entity_type="unknown",
                user_id=user_id,
                namespace=namespace,
            )
        )

    for rel in relations_data:
        relations.append(
            GraphRelation(
                id=str(ulid.ULID()),
                source=rel.get("source"),
                source_type=rel.get("source_type", "unknown"),
                target=rel.get("target"),
                target_type=rel.get("target_type", "unknown"),
                relation_type=rel.get("relation_type", "related_to"),
                user_id=user_id,
                namespace=namespace,
            )
        )

    return entities, relations
