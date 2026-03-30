from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID
from models.session import ArchitectureType, TaskType, StatusType

class CreateSessionRequest(BaseModel):
    name: str
    architecture: ArchitectureType
    task: TaskType

class SessionResponse(BaseModel):
    id: UUID
    name: str
    architecture: ArchitectureType
    task: TaskType
    status: StatusType
    api_key: Optional[str] = Field(None, serialization_alias="apiKey")
    created_at: datetime = Field(serialization_alias="createdAt")

    class Config:
        from_attributes = True
        populate_by_name = True
