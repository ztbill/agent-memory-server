import pytest
from agent_memory_server.graph.models import (
    GraphEntity,
    GraphRelation,
    GraphSearchResult,
)


class TestGraphModels:
    def test_graph_entity_creation(self):
        entity = GraphEntity(
            id="test-1", name="John", entity_type="person", user_id="user1"
        )
        assert entity.name == "John"
        assert entity.entity_type == "person"

    def test_graph_entity_defaults(self):
        entity = GraphEntity(id="test-1", name="Test")
        assert entity.entity_type == "unknown"

    def test_graph_relation_compatible_with_mem0(self):
        relation = GraphRelation(
            id="rel-1",
            source="John",
            source_type="person",
            target="Apple",
            target_type="organization",
            relation_type="works_at",
            user_id="user1",
        )
        assert relation.source == "John"
        assert relation.relation_type == "works_at"

    def test_graph_relation_defaults(self):
        relation = GraphRelation(
            id="rel-1", source="A", target="B", relation_type="knows"
        )
        assert relation.source_type == "unknown"
        assert relation.target_type == "unknown"
        assert relation.score == 1.0

    def test_graph_search_result(self):
        result = GraphSearchResult(
            source="John",
            source_type="person",
            relationship="works_at",
            target="Apple",
            target_type="organization",
            score=0.95,
        )
        assert result.score == 0.95
        assert result.relationship == "works_at"
