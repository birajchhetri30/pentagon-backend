from sqlalchemy import Column, String, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID
from database import Base
from datetime import datetime
import uuid
import enum

class TaskType(str, enum.Enum):
    medical = "medical"
    realtime = "realtime"

class ArchitectureType(str, enum.Enum):
    deeplabv3 = "deeplabv3+"
    unet_attention = "unet_attention"

class StatusType(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"

class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    architecture = Column(Enum(ArchitectureType), nullable=False)
    task = Column(Enum(TaskType), nullable=False)
    status = Column(Enum(StatusType), default=StatusType.pending)
    api_key = Column(String, unique=True, nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)