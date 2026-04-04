from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base
from datetime import datetime
import uuid


class OrchestratorLog(Base):
    __tablename__ = "orchestrator_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    run_id = Column(UUID(as_uuid=True), ForeignKey("session_runs.id"), nullable=False)
    epoch = Column(Integer, nullable=False)
    decision = Column(String, nullable=False)  # continue, hitl_pause, approved, stop, report
    agents_called = Column(JSONB, nullable=True)
    rationale = Column(String, nullable=True)
    hitl_proposal_id = Column(UUID(as_uuid=True), ForeignKey("hyperparameter_proposals.id"), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
