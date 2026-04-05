from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.job import Job
from models.metric import Metric
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/training", tags=["training-callback"])


class TrainingMetricCallback(BaseModel):
    job_id: str
    epoch: int
    total_epochs: int
    train_loss: float
    val_miou: float
    best_miou: float
    current_lr: float
    checkpoint_saved: Optional[bool] = None


@router.post("/metrics-callback")
def receive_training_metrics(
    body: TrainingMetricCallback,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == body.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    metric = Metric(
        job_id=body.job_id,
        data={
            "epoch": body.epoch,
            "total_epochs": body.total_epochs,
            "train_loss": body.train_loss,
            "val_miou": body.val_miou,
            "best_miou": body.best_miou,
            "current_lr": body.current_lr,
            "checkpoint_saved": body.checkpoint_saved,
        },
    )
    db.add(metric)

    # Auto-complete job when last epoch is reached
    if body.epoch >= body.total_epochs:
        job.is_completed = True

    db.commit()
    return {"recorded": True, "epoch": body.epoch, "completed": job.is_completed}
