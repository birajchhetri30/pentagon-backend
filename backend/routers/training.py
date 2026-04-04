from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.session import Session as SessionModel
from models.session_run import SessionRun
from models.epoch_metric import EpochMetric
from models.orchestrator_log import OrchestratorLog
from models.training_report import TrainingReport
from auth_utils import get_current_user
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

router = APIRouter(prefix="/sessions", tags=["training"])


# ── Schemas ──

class CreateSessionBody(BaseModel):
    session_id: Optional[str] = None
    current_params: Optional[dict] = None

class PostMetricsBody(BaseModel):
    run_id: str
    epoch: int
    loss: Optional[float] = None
    val_loss: Optional[float] = None
    accuracy: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: Optional[float] = None

class UpdateStatusBody(BaseModel):
    status: str
    stop_reason: Optional[str] = None

class PostLogBody(BaseModel):
    run_id: str
    epoch: int
    decision: str
    agents_called: Optional[List[str]] = None
    rationale: Optional[str] = None
    hitl_proposal_id: Optional[str] = None
    duration_ms: Optional[int] = None

class PostReportBody(BaseModel):
    run_id: str
    run_number: int
    total_epochs: Optional[int] = None
    best_epoch: Optional[int] = None
    best_val_loss: Optional[float] = None
    best_val_accuracy: Optional[float] = None
    final_val_loss: Optional[float] = None
    final_val_accuracy: Optional[float] = None
    training_outcome: Optional[str] = None
    stop_reason: Optional[str] = None
    summary: Optional[str] = None
    loss_improvement: Optional[float] = None
    accuracy_improvement: Optional[float] = None
    alerts_sent: Optional[List[dict]] = None


# ── Helpers ──

def _get_session(session_id: str, user: User, db: Session) -> SessionModel:
    s = db.query(SessionModel).filter(SessionModel.id == session_id, SessionModel.user_id == user.id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s

def _serialize_uuid(obj):
    """Convert UUID fields to strings for JSON response."""
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, "hex"):
            d[k] = str(v)
    return d


# ── 2.1 Create Session (AgentCore bootstrap) ──

@router.post("/bootstrap", status_code=201)
def bootstrap_session(
    body: CreateSessionBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _get_session(body.session_id, current_user, db) if body.session_id else None
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Create via /sessions first.")

    session.status = "running"
    run = SessionRun(
        session_id=session.id,
        run_number=1,
        params=body.current_params,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {
        "session_id": str(session.id),
        "run_id": str(run.id),
        "run_number": run.run_number,
        "status": "running",
    }


# ── 2.3 Post Epoch Metrics ──

@router.post("/{session_id}/metrics", status_code=201)
def post_epoch_metrics(
    session_id: str,
    body: PostMetricsBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    metric = EpochMetric(
        session_id=session_id,
        run_id=body.run_id,
        epoch=body.epoch,
        loss=body.loss,
        val_loss=body.val_loss,
        accuracy=body.accuracy,
        val_accuracy=body.val_accuracy,
        learning_rate=body.learning_rate,
    )
    db.add(metric)
    db.commit()
    return {"session_id": session_id, "run_id": body.run_id, "epoch": body.epoch, "recorded": True}


# ── 2.4 Get Epoch Metrics ──

@router.get("/{session_id}/metrics")
def get_epoch_metrics(
    session_id: str,
    epoch: Optional[int] = Query(None),
    run_id: Optional[str] = Query(None),
    from_epoch: Optional[int] = Query(None, alias="from"),
    to_epoch: Optional[int] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    q = db.query(EpochMetric).filter(EpochMetric.session_id == session_id)

    if run_id:
        q = q.filter(EpochMetric.run_id == run_id)
    if epoch is not None:
        m = q.filter(EpochMetric.epoch == epoch).first()
        if not m:
            raise HTTPException(status_code=404, detail="Metric not found for this epoch")
        return _serialize_uuid(m)
    if from_epoch is not None:
        q = q.filter(EpochMetric.epoch >= from_epoch)
    if to_epoch is not None:
        q = q.filter(EpochMetric.epoch <= to_epoch)

    return [_serialize_uuid(m) for m in q.order_by(EpochMetric.epoch.asc()).all()]


# ── 2.5 Update Session Status ──

@router.patch("/{session_id}/agent-status")
def update_agent_status(
    session_id: str,
    body: UpdateStatusBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    valid = {"running", "hitl_paused", "stopped", "completed", "failed"}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")
    session = _get_session(session_id, current_user, db)
    session.status = body.status
    if body.stop_reason:
        session.stop_reason = body.stop_reason
    db.commit()
    db.refresh(session)
    return {"session_id": str(session.id), "status": session.status.value if hasattr(session.status, 'value') else session.status, "updated_at": session.updated_at.isoformat() if session.updated_at else None}


# ── 2.16 Get Current Run ──

@router.get("/{session_id}/current-run")
def get_current_run(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    run = db.query(SessionRun).filter(
        SessionRun.session_id == session_id,
        SessionRun.ended_at == None,
    ).order_by(SessionRun.run_number.desc()).first()
    if not run:
        raise HTTPException(status_code=404, detail="No active run found")
    return _serialize_uuid(run)


# ── 2.12 Post Orchestrator Log ──

@router.post("/{session_id}/orchestrator-log", status_code=201)
def post_orchestrator_log(
    session_id: str,
    body: PostLogBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    log = OrchestratorLog(
        session_id=session_id,
        run_id=body.run_id,
        epoch=body.epoch,
        decision=body.decision,
        agents_called=body.agents_called,
        rationale=body.rationale,
        hitl_proposal_id=body.hitl_proposal_id,
        duration_ms=body.duration_ms,
    )
    db.add(log)
    db.commit()
    return {"logged": True, "id": str(log.id)}


# ── 2.13 Get Orchestrator Log ──

@router.get("/{session_id}/orchestrator-log")
def get_orchestrator_log(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    logs = db.query(OrchestratorLog).filter(
        OrchestratorLog.session_id == session_id
    ).order_by(OrchestratorLog.created_at.desc()).all()
    return [_serialize_uuid(l) for l in logs]


# ── 2.14 Submit Training Report ──

@router.post("/{session_id}/training-report", status_code=201)
def post_training_report(
    session_id: str,
    body: PostReportBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    report = TrainingReport(
        session_id=session_id,
        run_id=body.run_id,
        run_number=body.run_number,
        total_epochs=body.total_epochs,
        best_epoch=body.best_epoch,
        best_val_loss=body.best_val_loss,
        best_val_accuracy=body.best_val_accuracy,
        final_val_loss=body.final_val_loss,
        final_val_accuracy=body.final_val_accuracy,
        loss_improvement=body.loss_improvement,
        accuracy_improvement=body.accuracy_improvement,
        training_outcome=body.training_outcome,
        stop_reason=body.stop_reason,
        summary=body.summary,
        alerts_sent=body.alerts_sent,
    )
    db.add(report)
    db.commit()
    return {"written": True, "id": str(report.id)}


# ── 2.15 Get Training Report ──

@router.get("/{session_id}/training-report")
def get_training_report(
    session_id: str,
    run_number: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    q = db.query(TrainingReport).filter(TrainingReport.session_id == session_id)
    if run_number is not None:
        q = q.filter(TrainingReport.run_number == run_number)
    report = q.order_by(TrainingReport.created_at.desc()).first()
    if not report:
        raise HTTPException(status_code=404, detail="No training report found")
    return _serialize_uuid(report)
