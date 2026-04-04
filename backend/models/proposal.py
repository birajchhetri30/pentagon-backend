from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base
from datetime import datetime, timedelta
import uuid


class HyperparameterProposal(Base):
    __tablename__ = "hyperparameter_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    run_id = Column(UUID(as_uuid=True), ForeignKey("session_runs.id"), nullable=False)
    proposed_params = Column(JSONB, nullable=False)
    final_params = Column(JSONB, nullable=True)
    rationale = Column(String, nullable=True)
    overfitting_severity = Column(String, nullable=True)
    trend = Column(String, nullable=True)
    confidence = Column(String, nullable=True)
    source_epoch = Column(Integer, nullable=True)
    applies_via = Column(String, default="checkpoint_restart")
    status = Column(String, default="pending")  # pending, approved, rejected, suggested, expired
    rejection_reason = Column(String, nullable=True)
    reviewer_suggestion = Column(String, nullable=True)
    decided_by = Column(String, nullable=True)
    decided_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(hours=24))
    created_at = Column(DateTime, default=datetime.utcnow)
