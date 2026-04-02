from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GraphEntity(BaseModel):
    id: str = Field(description="Unique entity identifier")
    name: str = Field(description="Entity name")
    entity_type: str = Field(default="unknown", description="Entity type")
    user_id: str | None = Field(default=None, description="User ID for isolation")
    namespace: str | None = Field(default=None, description="Namespace")
    session_id: str | None = Field(default=None, description="Session scope")
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GraphRelation(BaseModel):
    id: str = Field(description="Unique relation identifier")
    source: str = Field(description="Source entity name")
    source_type: str = Field(default="unknown")
    target: str = Field(description="Target entity name")
    target_type: str = Field(default="unknown")
    relation_type: str = Field(description="Relation type")
    properties: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = Field(default=None)
    namespace: str | None = Field(default=None)
    score: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GraphSearchResult(BaseModel):
    source: str
    source_type: str = "unknown"
    relationship: str
    target: str
    target_type: str = "unknown"
    score: float = 1.0


class GraphSearchResults(BaseModel):
    results: list[GraphSearchResult]
    total: int
