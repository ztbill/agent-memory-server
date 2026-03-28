"""
SimpleMem Engine - Unified memory interface for agent-memory-server

This module provides a unified interface that combines:
- SimpleMem's memory extraction and hybrid retrieval (Sections 3.1-3.3)
- Agent-memory-server's native long-term memory operations

Architecture:
- MemoryBuilder: Stage 1 & 2 - Semantic Structured Compression
- HybridRetriever: Stage 3 - Intent-Aware Retrieval Planning
- AnswerGenerator: Final synthesis from retrieved contexts

The engine supports both SimpleMem-style operations and native agent-memory-server
operations through the same interface.
"""

from typing import Optional
from agent_memory_server.engines.simplemem.core import (
    MemoryBuilder,
    HybridRetriever,
    AnswerGenerator,
)
from agent_memory_server.engines.simplemem.adapters.memory_entry import (
    SimpleMemMemoryEntry as MemoryEntry,
    Dialogue,
)


class SimpleMemEngine:
    """Unified SimpleMem engine combining memory extraction and retrieval."""

    def __init__(
        self,
        namespace: str = "simplemem",
        user_id: str = None,
        window_size: int = None,
        enable_parallel_processing: bool = True,
        max_parallel_workers: int = 3,
        semantic_top_k: int = None,
        keyword_top_k: int = None,
        structured_top_k: int = None,
        enable_planning: bool = True,
        enable_reflection: bool = True,
        max_reflection_rounds: int = 2,
        enable_parallel_retrieval: bool = True,
        max_retrieval_workers: int = 3,
    ):
        self.namespace = namespace
        self.user_id = user_id

        self.memory_builder = MemoryBuilder(
            window_size=window_size,
            enable_parallel_processing=enable_parallel_processing,
            max_parallel_workers=max_parallel_workers,
            namespace=namespace,
            user_id=user_id,
        )

        self.hybrid_retriever = HybridRetriever(
            semantic_top_k=semantic_top_k,
            keyword_top_k=keyword_top_k,
            structured_top_k=structured_top_k,
            enable_planning=enable_planning,
            enable_reflection=enable_reflection,
            max_reflection_rounds=max_reflection_rounds,
            enable_parallel_retrieval=enable_parallel_retrieval,
            max_retrieval_workers=max_retrieval_workers,
            namespace=namespace,
            user_id=user_id,
        )

        self.answer_generator = AnswerGenerator()

    def add_dialogue(
        self,
        speaker: str,
        content: str,
        timestamp: Optional[str] = None,
        auto_process: bool = True,
    ):
        dialogue = Dialogue(
            dialogue_id=len(self.memory_builder.dialogue_buffer) + 1,
            speaker=speaker,
            content=content,
            timestamp=timestamp,
        )
        self.memory_builder.add_dialogue(dialogue, auto_process=auto_process)

    def add_dialogues(self, dialogues: list[Dialogue], auto_process: bool = True):
        self.memory_builder.add_dialogues(dialogues, auto_process=auto_process)

    def process_remaining(self):
        self.memory_builder.process_remaining()

    def retrieve(
        self, query: str, enable_reflection: Optional[bool] = None
    ) -> list[MemoryEntry]:
        return self.hybrid_retriever.retrieve(query, enable_reflection)

    def generate_answer(
        self, query: str, contexts: Optional[list[MemoryEntry]] = None
    ) -> str:
        if contexts is None:
            contexts = self.retrieve(query)
        return self.answer_generator.generate_answer(query, contexts)

    def search(
        self,
        query: str,
        search_mode: str = "semantic",
        top_k: int = 10,
    ) -> list[MemoryEntry]:
        if search_mode == "semantic":
            return self.hybrid_retriever.vector_store.semantic_search(
                query, top_k=top_k
            )
        elif search_mode == "keyword":
            keywords = query.split()
            return self.hybrid_retriever.vector_store.keyword_search(
                keywords, top_k=top_k
            )
        else:
            return self.hybrid_retriever.vector_store.semantic_search(
                query, top_k=top_k
            )

    async def search_native(
        self,
        query: str,
        search_mode: str = "semantic",
        namespace: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10,
    ):
        from agent_memory_server.long_term_memory import search_long_term_memory
        from agent_memory_server.models import SearchRequest, SearchModeEnum

        search_mode_enum = SearchModeEnum(search_mode)

        request = SearchRequest(
            text=query,
            search_mode=search_mode_enum,
            namespace=namespace or self.namespace,
            user_id=user_id or self.user_id,
            limit=limit,
        )

        return await search_long_term_memory(request)

    async def add_memory_native(
        self,
        text: str,
        memory_id: Optional[str] = None,
        namespace: Optional[str] = None,
        user_id: Optional[str] = None,
        topics: Optional[list[str]] = None,
        entities: Optional[list[str]] = None,
        memory_type: str = "semantic",
    ) -> str:
        from agent_memory_server.long_term_memory import (
            index_long_term_memories,
        )
        from agent_memory_server.models import (
            MemoryRecord,
            MemoryTypeEnum,
        )
        from ulid import ULID

        if memory_id is None:
            memory_id = str(ULID())

        memory = MemoryRecord(
            id=memory_id,
            text=text,
            namespace=namespace or self.namespace,
            user_id=user_id or self.user_id,
            topics=topics,
            entities=entities,
            memory_type=MemoryTypeEnum(memory_type),
        )

        await index_long_term_memories(memories=[memory])
        return memory_id


def create_simplemem_engine(
    namespace: str = "simplemem",
    user_id: str = None,
    **kwargs,
) -> SimpleMemEngine:
    return SimpleMemEngine(namespace=namespace, user_id=user_id, **kwargs)
