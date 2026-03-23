from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.session import Session as SessionModel
from auth_utils import get_current_user
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/sessions", tags=["intervention"])


class InterventionSample(BaseModel):
    id: str
    imageUrl: str
    maskUrl: str
    sessionId: str


class InterventionDecision(BaseModel):
    decision: str


@router.get("/{session_id}/intervention", response_model=List[InterventionSample])
def get_intervention_samples(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    # This will be populated by the CLI when it sends samples for review
    # For now we return an empty list
    return []


@router.post("/{session_id}/intervention/{sample_id}")
def submit_intervention(
    session_id: str,
    sample_id: str,
    decision: InterventionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(SessionModel).filter(
        SessionModel.id == session_id,
        SessionModel.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    if decision.decision not in ["approve", "reject"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Decision must be approve or reject"
        )
    # This will forward the decision to the CLI via WebSocket
    # Full implementation comes when we wire up the WebSocket
    return {"message": f"Sample {sample_id} marked as {decision.decision}"}