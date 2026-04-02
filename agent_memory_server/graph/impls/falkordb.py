import json
import logging

import ulid
from falkordb import FalkorDB

from agent_memory_server.graph.base import MemoryGraph
from agent_memory_server.graph.models import (
    GraphEntity,
    GraphRelation,
    GraphSearchResult,
    GraphSearchResults,
)


logger = logging.getLogger(__name__)


def _serialize_props(props: dict) -> str:
    return json.dumps(props) if props else "{}"


class FalkorDBMemory(MemoryGraph):
    GRAPH_NAME = "agent_memory"

    def __init__(self, host: str = "localhost", port: int = 6379):
        self._host = host
        self._port = port
        self._db = FalkorDB(host=host, port=port)
        self._graph = self._db.select_graph(self.GRAPH_NAME)

    def _get_db(self):
        if not hasattr(self, "_db") or self._db is None:
            self._db = FalkorDB(host=self._host, port=self._port)
            self._graph = self._db.select_graph(self.GRAPH_NAME)
        return self._graph

    async def add_entities(
        self,
        entities: list[GraphEntity],
        user_id: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        if entities and isinstance(entities[0], tuple):
            converted = []
            for name, props in entities:
                entity = GraphEntity(
                    id=str(ulid.ULID()),
                    name=name,
                    properties=props,
                    user_id=user_id,
                    namespace=namespace,
                )
                converted.append(entity)
            entities = converted

        entity_ids = []
        for entity in entities:
            if not entity.id:
                entity.id = str(ulid.ULID())

            cypher = """
            MERGE (e:Entity {user_id: $user_id, namespace: $namespace, name: $name})
            SET e.entity_type = $entity_type,
                e.properties = $properties,
                e.entity_id = $entity_id
            RETURN e.entity_id as id
            """
            try:
                graph = self._get_db()
                result = graph.query(
                    cypher,
                    {
                        "user_id": user_id or "",
                        "namespace": namespace or "",
                        "name": entity.name,
                        "entity_type": entity.entity_type,
                        "properties": _serialize_props(entity.properties),
                        "entity_id": entity.id,
                    },
                )
                if result.result_set:
                    entity_ids.append(str(result.result_set[0][0]))
            except Exception as e:
                logger.error(f"Error adding entity {entity.name}: {e}")
                entity_ids.append(entity.id)

        return entity_ids

    async def add_relations(
        self,
        relations: list[GraphRelation],
        user_id: str | None = None,
        namespace: str | None = None,
    ) -> list[str]:
        if relations and isinstance(relations[0], tuple):
            converted = []
            for src, rel_type, tgt, props in relations:
                rel = GraphRelation(
                    id=str(ulid.ULID()),
                    source=src,
                    relation_type=rel_type,
                    target=tgt,
                    properties=props or {},
                    user_id=user_id,
                    namespace=namespace,
                )
                converted.append(rel)
            relations = converted

        relation_ids = []
        for rel in relations:
            if not rel.id:
                rel.id = str(ulid.ULID())

            cypher = """
            MATCH (s:Entity {name: $source, user_id: $user_id, namespace: $namespace})
            MATCH (t:Entity {name: $target, user_id: $user_id, namespace: $namespace})
            MERGE (s)-[r:RELATION {relation_type: $rel_type}]->(t)
            SET r.properties = $properties, r.relation_id = $relation_id
            RETURN r.relation_id as id
            """
            try:
                graph = self._get_db()
                result = graph.query(
                    cypher,
                    {
                        "source": rel.source,
                        "target": rel.target,
                        "rel_type": rel.relation_type,
                        "properties": _serialize_props(rel.properties),
                        "user_id": user_id or "",
                        "namespace": namespace or "",
                        "relation_id": rel.id,
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
        conditions = ["1=1"]
        params = {}

        if user_id:
            conditions.append("e.user_id = $user_id")
            params["user_id"] = user_id
        if namespace:
            conditions.append("e.namespace = $namespace")
            params["namespace"] = namespace

        # Add case-insensitive name search
        conditions.append(f"toLower(e.name) CONTAINS toLower($query)")
        params["query"] = query

        where_clause = " AND ".join(conditions)

        cypher = f"""
        MATCH (e:Entity)
        WHERE {where_clause}
        OPTIONAL MATCH (e)-[r:RELATION]->(related:Entity)
        RETURN e.name as source, e.entity_type as source_type,
               type(r) as relationship, related.name as target,
               related.entity_type as target_type
        LIMIT {limit}
        """

        try:
            graph = self._get_db()
            result = graph.query(cypher, params)

            results = []
            for row in result.result_set:
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
            graph = self._get_db()
            graph.query(
                "MATCH (e:Entity {entity_id: $id}) DETACH DELETE e",
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
            graph = self._get_db()
            if namespace:
                result = graph.query(
                    "MATCH (e:Entity {user_id: $user_id, namespace: $namespace}) DETACH DELETE e RETURN count(e)",
                    {"user_id": user_id, "namespace": namespace},
                )
            else:
                result = graph.query(
                    "MATCH (e:Entity {user_id: $user_id}) DETACH DELETE e RETURN count(e)",
                    {"user_id": user_id},
                )
            if result.result_set:
                return result.result_set[0][0]
            return 0
        except Exception as e:
            logger.error(f"Error deleting user graph: {e}")
            return 0
