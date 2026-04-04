from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from database import Base
from datetime import datetime
import uuid


class EpochMetric(Base):
    __tablename__ = "epoch_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    run_id = Column(UUID(as_uuid=True), ForeignKey("session_runs.id"), nullable=False)
    epoch = Column(Integer, nullable=False)
    loss = Column(Float, nullable=True)
    val_loss = Column(Float, nullable=True)
    accuracy = Column(Float, nullable=True)
    val_accuracy = Column(Float, nullable=True)
    learning_rate = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
