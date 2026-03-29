import asyncio
import threading

from agent_memory_server.memory_vector_db_factory import (
    create_redis_memory_vector_db,
)
from agent_memory_server.models import MemoryRecord, MemoryTypeEnum


class VectorStoreAdapter:
    def __init__(self, namespace: str = "simplemem", user_id: str = None):
        self.namespace = namespace
        self.user_id = user_id
        self._local = threading.local()

    def _get_db(self):
        # Thread-local caching: each thread has its own db instance
        if not hasattr(self._local, "db") or self._local.db is None:
            from agent_memory_server.llm import LLMClient

            embeddings = LLMClient.create_embeddings()

            self._local.db = create_redis_memory_vector_db(embeddings)
        return self._local.db

    def _run_async(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def add_entries(self, entries: list):
        if not entries:
            return
        db = self._get_db()
        records = []
        for entry in entries:
            all_entities = list(entry.entities) if entry.entities else []
            if entry.persons:
                all_entities.extend(entry.persons)
            if entry.location:
                all_entities.append(entry.location)
            record = MemoryRecord(
                id=entry.entry_id,
                text=entry.lossless_restatement,
                namespace=self.namespace,
                user_id=self.user_id,
                topics=[entry.topic] if entry.topic else None,
                entities=all_entities if all_entities else None,
                memory_type=MemoryTypeEnum.SEMANTIC,
            )
            records.append(record)
        self._run_async(db.add_memories(records))

    def semantic_search(self, query: str, top_k: int = 5) -> list:
        from agent_memory_server.engines.simplemem.adapters.memory_entry import (
            SimpleMemMemoryEntry,
        )
        from agent_memory_server.filters import Namespace, UserId
        from agent_memory_server.models import SearchModeEnum

        db = self._get_db()
        search_kwargs = {
            "query": query,
            "search_mode": SearchModeEnum.SEMANTIC,
            "limit": top_k,
        }
        if self.namespace:
            search_kwargs["namespace"] = Namespace(eq=self.namespace)
        if self.user_id:
            search_kwargs["user_id"] = UserId(eq=self.user_id)

        results = self._run_async(db.search_memories(**search_kwargs))
        return [
            SimpleMemMemoryEntry(
                entry_id=r.id,
                lossless_restatement=r.text,
                keywords=r.topics or [],
                timestamp=r.event_date.isoformat() if r.event_date else None,
                location=None,
                persons=[],
                entities=r.entities or [],
                topic=r.topics[0] if r.topics else None,
            )
            for r in results.memories
        ]

    def keyword_search(self, keywords: list[str], top_k: int = 3) -> list:
        from agent_memory_server.engines.simplemem.adapters.memory_entry import (
            SimpleMemMemoryEntry,
        )
        from agent_memory_server.filters import Namespace, UserId
        from agent_memory_server.models import SearchModeEnum

        db = self._get_db()
        query = " ".join(keywords)
        search_kwargs = {
            "query": query,
            "search_mode": SearchModeEnum.KEYWORD,
            "limit": top_k,
        }
        if self.namespace:
            search_kwargs["namespace"] = Namespace(eq=self.namespace)
        if self.user_id:
            search_kwargs["user_id"] = UserId(eq=self.user_id)

        results = self._run_async(db.search_memories(**search_kwargs))
        return [
            SimpleMemMemoryEntry(
                entry_id=r.id,
                lossless_restatement=r.text,
                keywords=r.topics or [],
                timestamp=r.event_date.isoformat() if r.event_date else None,
                location=None,
                persons=[],
                entities=r.entities or [],
                topic=r.topics[0] if r.topics else None,
            )
            for r in results.memories
        ]

    def structured_search(
        self,
        persons: list[str] | None = None,
        timestamp_range: tuple | None = None,
        location: str | None = None,
        entities: list[str] | None = None,
        top_k: int | None = None,
    ) -> list:
        from agent_memory_server.engines.simplemem.adapters.memory_entry import (
            SimpleMemMemoryEntry,
        )
        from agent_memory_server.filters import Entities, EventDate, Namespace, UserId
        from agent_memory_server.models import SearchModeEnum

        db = self._get_db()
        search_kwargs = {
            "query": "*",
            "search_mode": SearchModeEnum.SEMANTIC,
            "limit": top_k or 10,
        }
        if self.namespace:
            search_kwargs["namespace"] = Namespace(eq=self.namespace)
        if self.user_id:
            search_kwargs["user_id"] = UserId(eq=self.user_id)

        all_filter_entities = list(entities) if entities else []
        if persons:
            all_filter_entities.extend(persons)
        if location:
            all_filter_entities.append(location)
        if all_filter_entities:
            search_kwargs["entities"] = Entities(any=all_filter_entities)

        if timestamp_range:
            start_time, end_time = timestamp_range
            search_kwargs["event_date"] = EventDate(between=[start_time, end_time])

        results = self._run_async(db.search_memories(**search_kwargs))
        return [
            SimpleMemMemoryEntry(
                entry_id=r.id,
                lossless_restatement=r.text,
                keywords=r.topics or [],
                timestamp=r.event_date.isoformat() if r.event_date else None,
                location=None,
                persons=[],
                entities=r.entities or [],
                topic=r.topics[0] if r.topics else None,
            )
            for r in results.memories
        ]
