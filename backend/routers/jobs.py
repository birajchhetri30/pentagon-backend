from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.job import Job, JobType
from models.metric import Metric
from schemas.job import CreateJobRequest, JobResponse
from auth_utils import get_current_user
from ssm_utils import get_job_status_ssm
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_job(
    request: CreateJobRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.job_type not in ("training", "inferencing"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job type")

    job = Job(
        user_id=current_user.id,
        session_id=request.session_id,
        job_type=JobType(request.job_type),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return JobResponse.from_orm_manual(job)


@router.get("/{job_id}")
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Check SSM if not already completed
    if not job.is_completed:
        ssm_status = get_job_status_ssm(job_id)
        if ssm_status == "d":
            job.is_completed = True
            db.commit()
            db.refresh(job)

    return JobResponse.from_orm_manual(job)


class CreateMetricRequest(BaseModel):
    job_id: str
    data: dict[str, Any]


@router.post("/metrics", status_code=status.HTTP_201_CREATED)
def create_metric(
    request: CreateMetricRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == request.job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    metric = Metric(job_id=request.job_id, data=request.data)
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return {"id": str(metric.id), "job_id": str(metric.job_id), "data": metric.data, "created_at": metric.created_at}


@router.get("/{job_id}/metrics/latest")
def get_latest_metric(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    metric = db.query(Metric).filter(Metric.job_id == job_id).order_by(Metric.created_at.desc()).limit(1).first()
    if not metric:
        return None
    return {"id": str(metric.id), "job_id": str(metric.job_id), "data": metric.data, "created_at": metric.created_at}


@router.patch("/{job_id}/complete")
def complete_job(
    job_id: str,
    db
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    job.is_completed = True
    db.commit()
    db.refresh(job)
    return JobResponse.from_orm_manual(job)
