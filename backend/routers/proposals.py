from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.session import Session as SessionModel
from models.session_run import SessionRun
from models.proposal import HyperparameterProposal
from auth_utils import get_current_user
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter(tags=["proposals"])


# ── Schemas ──

class SubmitProposalBody(BaseModel):
    run_id: str
    proposed_params: dict
    rationale: Optional[str] = None
    overfitting_severity: Optional[str] = None
    trend: Optional[str] = None
    confidence: Optional[str] = None
    source_epoch: Optional[int] = None
    applies_via: str = "checkpoint_restart"

class ReviewProposalBody(BaseModel):
    status: str  # accept, reject, suggestion
    final_params: Optional[dict] = None
    rejection_reason: Optional[str] = None
    reviewer_suggestion: Optional[str] = None
    decided_by: Optional[str] = None


# ── Helpers ──

def _serialize(obj):
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if hasattr(v, "hex"):
            d[k] = str(v)
        elif isinstance(v, datetime):
            d[k] = v.isoformat() + "Z"
    return d

def _get_session(session_id: str, user: User, db: Session) -> SessionModel:
    s = db.query(SessionModel).filter(SessionModel.id == session_id, SessionModel.user_id == user.id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


# ── 2.7 Submit HITL Proposal ──

@router.post("/sessions/{session_id}/hyperparameter-proposals", status_code=201)
def submit_proposal(
    session_id: str,
    body: SubmitProposalBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    proposal = HyperparameterProposal(
        session_id=session_id,
        run_id=body.run_id,
        proposed_params=body.proposed_params,
        rationale=body.rationale,
        overfitting_severity=body.overfitting_severity,
        trend=body.trend,
        confidence=body.confidence,
        source_epoch=body.source_epoch,
        applies_via=body.applies_via,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return {
        "proposal_id": str(proposal.id),
        "status": proposal.status,
        "expires_at": proposal.expires_at.isoformat() + "Z" if proposal.expires_at else None,
        "submitted": True,
    }


# ── 2.8 Poll Proposal Status ──

@router.get("/sessions/{session_id}/hyperparameter-proposals/{proposal_id}")
def get_proposal(
    session_id: str,
    proposal_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    p = db.query(HyperparameterProposal).filter(HyperparameterProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    result = _serialize(p)
    result["proposal_id"] = result.pop("id")
    result["human_decision_received"] = p.decided_at is not None
    result["human_decision_option"] = (
        "accept" if p.status == "approved" else
        "reject" if p.status == "rejected" else
        "suggestion" if p.status == "suggested" else None
    )
    return result


# ── 2.9 Review Proposal ──

@router.patch("/sessions/{session_id}/hyperparameter-proposals/{proposal_id}")
def review_proposal(
    session_id: str,
    proposal_id: str,
    body: ReviewProposalBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = _get_session(session_id, current_user, db)
    p = db.query(HyperparameterProposal).filter(HyperparameterProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")

    now = datetime.utcnow()

    if body.status == "accept":
        p.status = "approved"
        p.final_params = body.final_params or p.proposed_params
        p.decided_by = body.decided_by
        p.decided_at = now

        # End current run, create new one
        current_run = db.query(SessionRun).filter(
            SessionRun.session_id == session_id,
            SessionRun.ended_at == None,
        ).order_by(SessionRun.run_number.desc()).first()

        new_run_number = 1
        checkpoint_epoch = p.source_epoch
        if current_run:
            current_run.ended_at = now
            new_run_number = current_run.run_number + 1

        new_run = SessionRun(
            session_id=session_id,
            run_number=new_run_number,
            params=p.final_params,
        )
        db.add(new_run)
        session.status = "running"
        db.commit()
        db.refresh(new_run)

        return {
            "proposal_id": str(p.id),
            "status": "approved",
            "new_run_id": str(new_run.id),
            "new_run_number": new_run.run_number,
            "checkpoint_epoch": checkpoint_epoch,
            "human_decision_received": True,
            "human_decision_option": "accept",
        }

    elif body.status == "reject":
        p.status = "rejected"
        p.rejection_reason = body.rejection_reason
        p.decided_by = body.decided_by
        p.decided_at = now

        # Resume session if no other pending proposals
        pending = db.query(HyperparameterProposal).filter(
            HyperparameterProposal.session_id == session_id,
            HyperparameterProposal.status == "pending",
            HyperparameterProposal.id != proposal_id,
        ).count()
        if pending == 0 and session.status == "hitl_paused":
            session.status = "running"

        db.commit()
        return {
            "proposal_id": str(p.id),
            "status": "rejected",
            "human_decision_received": True,
            "human_decision_option": "reject",
        }

    elif body.status == "suggestion":
        p.status = "suggested"
        p.reviewer_suggestion = body.reviewer_suggestion
        p.decided_by = body.decided_by
        p.decided_at = now
        db.commit()
        return {
            "proposal_id": str(p.id),
            "status": "suggested",
            "human_decision_received": True,
            "human_decision_option": "suggestion",
        }

    else:
        raise HTTPException(status_code=400, detail="Invalid status. Must be accept, reject, or suggestion.")


# ── 2.10 Get Session Proposals ──

@router.get("/sessions/{session_id}/hyperparameter-proposals")
def get_session_proposals(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    proposals = db.query(HyperparameterProposal).filter(
        HyperparameterProposal.session_id == session_id
    ).order_by(HyperparameterProposal.created_at.desc()).all()
    return [_serialize(p) for p in proposals]


# ── 2.11 List Proposals Globally ──

@router.get("/hyperparameter-proposals")
def list_proposals(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(HyperparameterProposal).join(
        SessionModel, HyperparameterProposal.session_id == SessionModel.id
    ).filter(SessionModel.user_id == current_user.id)
    if status:
        q = q.filter(HyperparameterProposal.status == status)
    return [_serialize(p) for p in q.order_by(HyperparameterProposal.created_at.desc()).all()]


# ── 2.6 Get Hyperparameter History ──

@router.get("/sessions/{session_id}/hyperparameters")
def get_hyperparameter_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_session(session_id, current_user, db)
    current_run = db.query(SessionRun).filter(
        SessionRun.session_id == session_id,
        SessionRun.ended_at == None,
    ).order_by(SessionRun.run_number.desc()).first()

    runs = db.query(SessionRun).filter(
        SessionRun.session_id == session_id,
        SessionRun.ended_at != None,
    ).order_by(SessionRun.run_number.asc()).all()

    history = []
    for run in runs:
        # Find best val_accuracy for this run
        best = db.query(EpochMetric).filter(
            EpochMetric.run_id == run.id,
        ).order_by(EpochMetric.val_accuracy.desc().nullslast()).first()

        history.append({
            "run_id": str(run.id),
            "run_number": run.run_number,
            "params": run.params,
            "best_val_accuracy": best.val_accuracy if best else None,
        })

    return {
        "current_params": current_run.params if current_run else None,
        "history": history,
    }
