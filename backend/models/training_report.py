from sqlalchemy import Column, Integer, Float, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base
from datetime import datetime
import uuid


class TrainingReport(Base):
    __tablename__ = "training_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    run_id = Column(UUID(as_uuid=True), ForeignKey("session_runs.id"), nullable=False)
    run_number = Column(Integer, nullable=False)
    total_epochs = Column(Integer, nullable=True)
    best_epoch = Column(Integer, nullable=True)
    best_val_loss = Column(Float, nullable=True)
    best_val_accuracy = Column(Float, nullable=True)
    final_val_loss = Column(Float, nullable=True)
    final_val_accuracy = Column(Float, nullable=True)
    loss_improvement = Column(Float, nullable=True)
    accuracy_improvement = Column(Float, nullable=True)
    training_outcome = Column(String, nullable=True)  # completed, stopped_early
    stop_reason = Column(String, nullable=True)
    alerts_sent = Column(JSONB, nullable=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
