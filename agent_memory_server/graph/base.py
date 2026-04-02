from abc import ABC, abstractmethod

from agent_memory_server.graph.models import (
    GraphEntity,
    GraphRelation,
    GraphSearchResults,
)


class MemoryGraph(ABC):
    @abstractmethod
    async def add_entities(self, entities: list[GraphEntity]) -> list[str]:
        pass

    @abstractmethod
    async def add_relations(self, relations: list[GraphRelation]) -> list[str]:
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        user_id: str | None = None,
        namespace: str | None = None,
        limit: int = 10,
    ) -> GraphSearchResults:
        pass

    @abstractmethod
    async def delete_entity(self, entity_id: str) -> bool:
        pass

    @abstractmethod
    async def delete_user_graph(
        self, user_id: str, namespace: str | None = None
    ) -> int:
        pass
