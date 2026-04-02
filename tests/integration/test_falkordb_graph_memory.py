"""
Integration tests for FalkorDB graph memory operations.

Requires FalkorDB running on port 7379.
Run with: pytest tests/integration/test_falkordb_memory.py -v
"""

import asyncio

import pytest

from agent_memory_server.graph.impls.falkordb import FalkorDBMemory


class TestFalkorDBGraphMemory:
    """Test graph memory operations with FalkorDB."""

    @pytest.fixture(autouse=True)
    async def setup(self):
        """Set up test fixture - clean before each test."""
        self.graph = FalkorDBMemory(port=7379)
        await self._cleanup()
        yield
        await self._cleanup()

    async def _cleanup(self):
        """Clean up test data."""
        try:
            graph = self.graph._get_db()
            graph.query("MATCH (e) DETACH DELETE e")
        except Exception:
            pass

    async def test_add_single_entity(self):
        """Test adding a single entity."""
        ids = await self.graph.add_entities(
            [("person:alice", {"name": "Alice", "role": "engineer"})],
            user_id="test-user",
            namespace="test-ns",
        )
        assert len(ids) == 1
        assert ids[0] is not None

    async def test_add_multiple_entities(self):
        """Test adding multiple entities."""
        ids = await self.graph.add_entities(
            [
                ("person:alice", {"name": "Alice", "role": "engineer"}),
                ("person:bob", {"name": "Bob", "role": "designer"}),
                ("org:acme", {"name": "Acme Corp", "founded": "2020"}),
            ],
            user_id="test-user",
            namespace="test-ns",
        )
        assert len(ids) == 3

    async def test_add_single_relation(self):
        """Test adding a single relation."""
        await self.graph.add_entities(
            [
                ("person:alice", {"name": "Alice"}),
                ("person:bob", {"name": "Bob"}),
            ],
            user_id="test-user",
            namespace="test-ns",
        )

        rel_ids = await self.graph.add_relations(
            [("person:alice", "knows", "person:bob", {"since": "2024"})],
            user_id="test-user",
            namespace="test-ns",
        )
        assert len(rel_ids) == 1

    async def test_add_multiple_relations(self):
        """Test adding multiple relations."""
        await self.graph.add_entities(
            [
                ("person:alice", {"name": "Alice"}),
                ("person:bob", {"name": "Bob"}),
                ("person:charlie", {"name": "Charlie"}),
                ("org:acme", {"name": "Acme"}),
            ],
            user_id="test-user",
            namespace="test-ns",
        )

        rel_ids = await self.graph.add_relations(
            [
                ("person:alice", "knows", "person:bob", {"since": "2020"}),
                ("person:bob", "works_at", "org:acme", {"since": "2021"}),
                ("person:alice", "knows", "person:charlie", {"since": "2022"}),
            ],
            user_id="test-user",
            namespace="test-ns",
        )
        assert len(rel_ids) == 3

    async def test_search_finds_entity(self):
        """Test search finds entity by name."""
        await self.graph.add_entities(
            [("person:alice", {"name": "Alice", "role": "engineer"})],
            user_id="test-user",
            namespace="test-ns",
        )

        results = await self.graph.search(
            "Alice", user_id="test-user", namespace="test-ns", limit=5
        )
        assert len(results.results) > 0
        assert any(r.source == "person:alice" for r in results.results)

    async def test_search_with_relations(self):
        """Test search returns entities with their relations."""
        await self.graph.add_entities(
            [
                ("person:alice", {"name": "Alice"}),
                ("person:bob", {"name": "Bob"}),
            ],
            user_id="test-user",
            namespace="test-ns",
        )
        await self.graph.add_relations(
            [("person:alice", "knows", "person:bob", {"since": "2024"})],
            user_id="test-user",
            namespace="test-ns",
        )

        results = await self.graph.search(
            "Alice", user_id="test-user", namespace="test-ns", limit=5
        )
        assert len(results.results) > 0
        relation_found = any(r.relationship == "RELATION" for r in results.results)
        assert relation_found

    async def test_search_respects_user_isolation(self):
        """Test search only returns results for specified user."""
        await self.graph.add_entities(
            [("person:alice", {"name": "Alice"})],
            user_id="user1",
            namespace="test-ns",
        )
        await self.graph.add_entities(
            [("person:alice", {"name": "Alice"})],
            user_id="user2",
            namespace="test-ns",
        )

        results = await self.graph.search(
            "Alice", user_id="user1", namespace="test-ns", limit=5
        )
        assert len(results.results) == 1
        assert results.results[0].source == "person:alice"

    async def test_search_respects_namespace_isolation(self):
        """Test search respects namespace isolation."""
        await self.graph.add_entities(
            [("person:alice", {"name": "Alice"})],
            user_id="test-user",
            namespace="ns1",
        )
        await self.graph.add_entities(
            [("person:alice", {"name": "Alice"})],
            user_id="test-user",
            namespace="ns2",
        )

        results = await self.graph.search(
            "Alice", user_id="test-user", namespace="ns1", limit=5
        )
        assert len(results.results) == 1
        assert results.results[0].source == "person:alice"

    async def test_delete_entity(self):
        """Test deleting an entity."""
        ids = await self.graph.add_entities(
            [("person:alice", {"name": "Alice"})],
            user_id="test-user",
            namespace="test-ns",
        )

        deleted = await self.graph.delete_entity(ids[0])
        assert deleted is True

    async def test_delete_user_graph(self):
        """Test deleting all entities for a user."""
        await self.graph.add_entities(
            [
                ("person:alice", {"name": "Alice"}),
                ("person:bob", {"name": "Bob"}),
            ],
            user_id="test-user",
            namespace="test-ns",
        )

        count = await self.graph.delete_user_graph("test-user", "test-ns")
        assert count > 0

    async def test_mem0_compatible_relation(self):
        """Test relation structure is compatible with Mem0 format."""
        await self.graph.add_entities(
            [
                ("person:john", {"name": "John"}),
                ("org:apple", {"name": "Apple"}),
            ],
            user_id="test-user",
            namespace="test-ns",
        )

        rel_ids = await self.graph.add_relations(
            [
                (
                    "person:john",
                    "works_at",
                    "org:apple",
                    {"since": "2020", "role": "Engineer"},
                )
            ],
            user_id="test-user",
            namespace="test-ns",
        )
        assert len(rel_ids) == 1

        results = await self.graph.search(
            "John", user_id="test-user", namespace="test-ns", limit=5
        )
        assert len(results.results) > 0


if __name__ == "__main__":
    asyncio.run(pytest.main([__file__, "-v"]))
