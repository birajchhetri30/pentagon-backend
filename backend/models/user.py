from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY, ENUM as PgENUM
from database import Base
from datetime import datetime
import uuid
import enum

class PermissionType(str, enum.Enum):
    TRAIN = "TRAIN"
    LABEL = "LABEL"
    TRAIN_LABEL = "TRAIN_LABEL"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=True)
    cognito_sub = Column(String, unique=True, nullable=True, index=True)
    permissions = Column(ARRAY(PgENUM(PermissionType, name="permission_type", create_type=False)), nullable=False, server_default="{TRAIN_LABEL}")
    created_at = Column(DateTime, default=datetime.utcnow)