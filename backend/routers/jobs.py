from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.job import Job, JobType
from schemas.job import CreateJobRequest, JobResponse
from auth_utils import get_current_user

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
    return JobResponse.from_orm_manual(job)


@router.patch("/{job_id}/complete")
def complete_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    job.is_completed = True
    db.commit()
    db.refresh(job)
    return JobResponse.from_orm_manual(job)
