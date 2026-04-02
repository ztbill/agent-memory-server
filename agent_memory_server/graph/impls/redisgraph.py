import logging

import redis
import ulid

from agent_memory_server.graph.base import MemoryGraph
from agent_memory_server.graph.models import (
    GraphEntity,
    GraphRelation,
    GraphSearchResult,
    GraphSearchResults,
)


logger = logging.getLogger(__name__)


class RedisGraphMemory(MemoryGraph):
    NODE_LABEL = "__Entity__"
    RELATION_LABEL = "__Relation__"

    def __init__(self, redis_url: str):
        self._client = redis.from_url(redis_url)
        self._graph = self._client.graph()

    async def add_entities(self, entities: list[GraphEntity]) -> list[str]:
        entity_ids = []
        for entity in entities:
            if not entity.id:
                entity.id = str(ulid.ULID())

            cypher = f"""
            MERGE (e:{self.NODE_LABEL} {{user_id: $user_id, name: $name}})
            SET e.entity_type = $entity_type,
                e.properties = $properties,
                e.updated_at = timestamp()
            RETURN id(e) as id
            """
            try:
                result = self._graph.query(
                    cypher,
                    {
                        "user_id": entity.user_id or "",
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "properties": entity.properties,
                    },
                )
                if result.result_set:
                    entity_ids.append(str(result.result_set[0][0]))
            except Exception as e:
                logger.error(f"Error adding entity {entity.name}: {e}")
                entity_ids.append(entity.id)

        return entity_ids

    async def add_relations(self, relations: list[GraphRelation]) -> list[str]:
        relation_ids = []
        for rel in relations:
            if not rel.id:
                rel.id = str(ulid.ULID())

            self._graph.query(
                f"MERGE (s:{self.NODE_LABEL} {{name: $source}})", {"source": rel.source}
            )
            self._graph.query(
                f"MERGE (t:{self.NODE_LABEL} {{name: $target}})", {"target": rel.target}
            )

            cypher = f"""
            MATCH (s:{self.NODE_LABEL} {{name: $source}})
            MATCH (t:{self.NODE_LABEL} {{name: $target}})
            MERGE (s)-[r:{self.RELATION_LABEL} {{relation_type: $rel_type}}]->(t)
            SET r.properties = $properties, r.user_id = $user_id
            RETURN id(r) as id
            """
            try:
                result = self._graph.query(
                    cypher,
                    {
                        "source": rel.source,
                        "target": rel.target,
                        "rel_type": rel.relation_type,
                        "properties": rel.properties,
                        "user_id": rel.user_id or "",
                    },
                )
                if result.result_set:
                    relation_ids.append(str(result.result_set[0][0]))
            except Exception as e:
                logger.error(f"Error adding relation: {e}")
                relation_ids.append(rel.id)

        return relation_ids

    async def search(
        self,
        query: str,
        user_id: str | None = None,
        namespace: str | None = None,
        limit: int = 10,
    ) -> GraphSearchResults:
        user_filter = f"e.user_id = '{user_id}'" if user_id else "true"

        cypher = f"""
        MATCH (e:{self.NODE_LABEL})
        WHERE {user_filter} AND e.name CONTAINS $query
        OPTIONAL MATCH (e)-[r:{self.RELATION_LABEL}]->(related)
        RETURN e.name as source, e.entity_type as source_type, 
               type(r) as relationship, related.name as target,
               related.entity_type as target_type
        LIMIT $limit
        """

        try:
            result = self._graph.query(cypher, {"query": query, "limit": limit})

            results = []
            for row in result.result_set:
                if row[2]:
                    results.append(
                        GraphSearchResult(
                            source=row[0] or "",
                            source_type=row[1] or "unknown",
                            relationship=row[2] or "related_to",
                            target=row[3] or "",
                            target_type=row[4] or "unknown",
                            score=1.0,
                        )
                    )

            return GraphSearchResults(results=results, total=len(results))
        except Exception as e:
            logger.error(f"Error searching graph: {e}")
            return GraphSearchResults(results=[], total=0)

    async def delete_entity(self, entity_id: str) -> bool:
        try:
            self._graph.query(
                f"MATCH (e:{self.NODE_LABEL}) WHERE id(e) = $id DETACH DELETE e",
                {"id": entity_id},
            )
            return True
        except Exception as e:
            logger.error(f"Error deleting entity: {e}")
            return False

    async def delete_user_graph(
        self, user_id: str, namespace: str | None = None
    ) -> int:
        try:
            self._graph.query(
                f"MATCH (e:{self.NODE_LABEL} {{user_id: $user_id}}) DETACH DELETE e",
                {"user_id": user_id},
            )
            return 1
        except Exception as e:
            logger.error(f"Error deleting user graph: {e}")
            return 0
