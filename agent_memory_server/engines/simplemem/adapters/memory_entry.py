import uuid

from pydantic import BaseModel, Field


class SimpleMemMemoryEntry(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lossless_restatement: str
    keywords: list[str] = Field(default_factory=list)
    timestamp: str | None = None
    location: str | None = None
    persons: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    topic: str | None = None


class Dialogue(BaseModel):
    dialogue_id: int
    speaker: str
    content: str
    timestamp: str | None = None

    def __str__(self) -> str:
        time_str = f"[{self.timestamp}] " if self.timestamp else ""
        return f"{time_str}{self.speaker}: {self.content}"
