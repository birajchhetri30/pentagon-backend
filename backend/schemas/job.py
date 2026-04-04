from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class CreateJobRequest(BaseModel):
    session_id: str
    job_type: str  # "training" or "inferencing"


class JobResponse(BaseModel):
    id: str
    user_id: str
    session_id: str
    job_type: str
    is_completed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_manual(cls, obj):
        return cls(
            id=str(obj.id),
            user_id=str(obj.user_id),
            session_id=str(obj.session_id),
            job_type=obj.job_type.value if hasattr(obj.job_type, "value") else obj.job_type,
            is_completed=obj.is_completed,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )
