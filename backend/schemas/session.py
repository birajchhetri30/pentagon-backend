from pydantic import BaseModel
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
    api_key: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
