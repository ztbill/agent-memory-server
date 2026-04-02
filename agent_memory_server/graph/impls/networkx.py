import logging

import networkx as nx
import ulid

from agent_memory_server.graph.base import MemoryGraph
from agent_memory_server.graph.models import (
    GraphEntity,
    GraphRelation,
    GraphSearchResult,
    GraphSearchResults,
)


logger = logging.getLogger(__name__)


class NetworkXGraphMemory(MemoryGraph):
    def __init__(self):
        self._graph = nx.MultiDiGraph()

    async def add_entities(self, entities: list[GraphEntity]) -> list[str]:
        entity_ids = []
        for entity in entities:
            if not entity.id:
                entity.id = str(ulid.ULID())

            self._graph.add_node(
                entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                user_id=entity.user_id,
                namespace=entity.namespace,
                properties=entity.properties,
            )
            entity_ids.append(entity.id)

        return entity_ids

    async def add_relations(self, relations: list[GraphRelation]) -> list[str]:
        relation_ids = []
        for rel in relations:
            if not rel.id:
                rel.id = str(ulid.ULID())

            source_node = self._find_node_by_name(rel.source, rel.user_id)
            target_node = self._find_node_by_name(rel.target, rel.user_id)

            if source_node and target_node:
                self._graph.add_edge(
                    source_node,
                    target_node,
                    key=rel.id,
                    relation_type=rel.relation_type,
                    source_type=rel.source_type,
                    target_type=rel.target_type,
                    properties=rel.properties,
                    user_id=rel.user_id,
                )
                relation_ids.append(rel.id)
            else:
                logger.warning(
                    f"Source or target node not found: {rel.source} -> {rel.target}"
                )
                relation_ids.append(rel.id)

        return relation_ids

    def _find_node_by_name(self, name: str, user_id: str | None) -> str | None:
        for node_id, attrs in self._graph.nodes(data=True):
            if attrs.get("name") == name and attrs.get("user_id") == user_id:
                return node_id
        return None

    async def search(
        self,
        query: str,
        user_id: str | None = None,
        namespace: str | None = None,
        limit: int = 10,
    ) -> GraphSearchResults:
        results = []

        for node_id, attrs in self._graph.nodes(data=True):
            if user_id and attrs.get("user_id") != user_id:
                continue

            if query.lower() in attrs.get("name", "").lower():
                source = attrs.get("name", "")
                source_type = attrs.get("entity_type", "unknown")

                for source_node, target_node, edge_attrs in self._graph.edges(
                    data=True
                ):
                    if source_node == node_id:
                        results.append(
                            GraphSearchResult(
                                source=source,
                                source_type=source_type,
                                relationship=edge_attrs.get(
                                    "relation_type", "related_to"
                                ),
                                target=self._graph.nodes[target_node].get("name", ""),
                                target_type=edge_attrs.get("target_type", "unknown"),
                                score=1.0,
                            )
                        )

                if len(results) >= limit:
                    break

        return GraphSearchResults(results=results[:limit], total=len(results))

    async def delete_entity(self, entity_id: str) -> bool:
        try:
            if entity_id in self._graph:
                self._graph.remove_node(entity_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting entity: {e}")
            return False

    async def delete_user_graph(
        self, user_id: str, namespace: str | None = None
    ) -> int:
        try:
            nodes_to_remove = [
                node
                for node, attrs in self._graph.nodes(data=True)
                if attrs.get("user_id") == user_id
            ]
            for node in nodes_to_remove:
                self._graph.remove_node(node)
            return len(nodes_to_remove)
        except Exception as e:
            logger.error(f"Error deleting user graph: {e}")
            return 0
