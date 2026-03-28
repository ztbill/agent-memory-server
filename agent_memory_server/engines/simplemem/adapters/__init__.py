"""
Adapters for integrating SimpleMem with agent-memory-server components.
"""

from .llm_client import LLMClientAdapter
from .memory_entry import Dialogue, SimpleMemMemoryEntry
from .vector_store import VectorStoreAdapter


__all__ = [
    "LLMClientAdapter",
    "VectorStoreAdapter",
    "SimpleMemMemoryEntry",
    "Dialogue",
]
