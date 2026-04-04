from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.session import Session as SessionModel
from schemas.session import CreateSessionRequest, SessionResponse
from auth_utils import get_current_user
from typing import List
import secrets
from models.session import StatusType
import shutil
import os
import json
from pydantic import BaseModel
import requests
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/sessions", tags=["sessions"])

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
AWS_REGION = os.getenv("AWS_REGION")

USE_S3 = S3_BUCKET_NAME and S3_BUCKET_NAME != "your_s3_bucket_name_here"

if USE_S3:
    s3_client = boto3.client("s3", region_name=AWS_REGION)


@router.get("", response_model=List[SessionResponse])
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sessions = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id
    ).all()
    return sessions


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(SessionModel).filter(
        SessionModel.user_id == current_user.id,
        SessionModel.name == request.name,
        SessionModel.task == request.task
    ).first()
    if existing:
        if request.classes and not existing.classes:
            existing.classes = request.classes
            db.commit()
            db.refresh(existing)
        return existing
    new_session = SessionModel(
        name=request.name,
        architecture=request.architecture,
        task=request.task,
        classes=request.classes,
        user_id=current_user.id
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


class HyperparameterRequest(BaseModel):
    image_count: int
    image_size: int
    classes: List[str]


class HyperparameterResponse(BaseModel):
    acceptance_criteria: str
    epochs: str
    learning_rate: str
    batch_size: str
    val_split: str
    momentum: str
    weight_decay: str
    aux_loss_weight: str
    from_claude: bool

def float_to_learning_rate_option(value: float) -> str:
    mapping = {
        0.01: "1e-2",
        0.001: "1e-3",
        0.0001: "1e-4",
        0.00001: "1e-5",
        0.000001: "1e-6",
    }
    # Find the closest match in the mapping
    closest = min(mapping.keys(), key=lambda x: abs(x - float(value)))
    return mapping[closest]

@router.post("/suggest-hyperparameters", response_model=HyperparameterResponse)
def suggest_hyperparameters(
    request: HyperparameterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Use Claude via AWS Lambda to suggest training hyperparameters.
    """
    try:
        lambda_url = os.getenv("AWS_LAMBDA_URL")
        if not lambda_url:
            print("NOT LAMBDA URL")
            return HyperparameterResponse(
                acceptance_criteria="80%",
                epochs="10",
                learning_rate="1e-4",
                batch_size="8",
                val_split="0.2",
                momentum="0.9",
                weight_decay="1e-4",
                aux_loss_weight="1.0",
                from_claude=False
            )
        
        # Create question string for Claude
        classes_str = ", ".join(request.classes)
        question = f"""I am training a DeepLabV3+ semantic segmentation model. Suggest optimal hyperparameters as JSON only, no explanation.
Dataset: {request.image_count} images, {request.image_size}x{request.image_size} pixels.
Classes: {classes_str} ({len(request.classes)} classes).
Return exactly this JSON format:
{{"Epochs": <int>, "Learning Rate": <float>, "Batch Size": <int>, "Val Split": <float>, "Momentum": <float>, "Weight Decay": <float>, "Aux Loss Weight": <float>}}"""

        # Call Lambda function with GET request (URL-encoded parameters)
        lambda_response = requests.get(
            lambda_url,
            params={"question": question},
            timeout=30
        )
        lambda_response.raise_for_status()
        
        # Parse response
        result = lambda_response.json()
        response_text = result.get("response", "")
        
        # Extract epochs and learning_rate from response
        # Response format:
        # - Epochs: <value>
        # - Learning Rate: <value>
        
        print("RESPONSE: ", response_text)

        epochs = "10"
        learning_rate = "1e-4"
        acceptance_criteria = "80%"
        batch_size = "8"
        val_split = "0.2"
        momentum = "0.9"
        weight_decay = "1e-4"
        aux_loss_weight = "1.0"

        if response_text.strip()[0] != "{":
            data = json.loads(response_text[7:-3])
            print(data)
        else:
            data = json.loads(response_text)
            print(data)

        epochs = str(data.get("Epochs", 10))
        learning_rate = float_to_learning_rate_option(data.get("Learning Rate", 0.0001))
        batch_size = str(data.get("Batch Size", 8))
        val_split = str(data.get("Val Split", 0.2))
        momentum = str(data.get("Momentum", 0.9))
        weight_decay = str(data.get("Weight Decay", 0.0001))
        aux_loss_weight = str(data.get("Aux Loss Weight", 1.0))

        return HyperparameterResponse(
            acceptance_criteria=acceptance_criteria,
            epochs=epochs,
            learning_rate=learning_rate,
            batch_size=batch_size,
            val_split=val_split,
            momentum=momentum,
            weight_decay=weight_decay,
            aux_loss_weight=aux_loss_weight,
            from_claude=True
        )
        
    except Exception as e:
        # Fall back to defaults if Lambda call fails
        print(f"Error calling Claude via Lambda: {e}")
        return HyperparameterResponse(
            acceptance_criteria="80%",
            epochs="10",
            learning_rate="1e-4",
            batch_size="8",
            val_split="0.2",
            momentum="0.9",
            weight_decay="1e-4",
            aux_loss_weight="1.0",
            from_claude=False
        )

class PresignedUrlRequest(BaseModel):
    filenames: List[str]
    content_types: List[str]
    session_id: str


@router.post("/presigned-urls")
def get_presigned_urls(
    request: PresignedUrlRequest,
    current_user: User = Depends(get_current_user)
):
    if not USE_S3:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="S3 not configured")
    try:
        urls = []
        for filename, content_type in zip(request.filenames, request.content_types):
            key = f"datasets/{current_user.id}/{request.session_id}/{filename}"
            url = s3_client.generate_presigned_url(
                "put_object",
                Params={"Bucket": S3_BUCKET_NAME, "Key": key, "ContentType": content_type},
                ExpiresIn=3600,
            )
            urls.append({"filename": filename, "url": url, "key": key, "content_type": content_type})
        return {"urls": urls}
    except ClientError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
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
    db.delete(session)
    db.commit()


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
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
    return session


@router.post("/{session_id}/apikey", response_model=SessionResponse)
def generate_api_key(
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
    session.api_key = secrets.token_hex(32)
    db.commit()
    db.refresh(session)
    return session


@router.patch("/{session_id}/status")
def update_session_status(
    session_id: str,
    status: str,
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
    if status not in ["pending", "running", "completed", "failed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid status"
        )
    session.status = status
    db.commit()
    db.refresh(session)
    return session


# @router.post("/{session_id}/upload")
# async def upload_dataset(
#     session_id: str,
#     files: list[UploadFile] = File(...),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     session = db.query(SessionModel).filter(
#         SessionModel.id == session_id,
#         SessionModel.user_id == current_user.id
#     ).first()
#     if not session:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Session not found"
#         )
#     upload_dir = f"uploads/{session_id}"
#     os.makedirs(upload_dir, exist_ok=True)
#     saved_files = []
#     for file in files:
#         file_path = f"{upload_dir}/{file.filename}"
#         with open(file_path, "wb") as buffer:
#             shutil.copyfileobj(file.file, buffer)
#         saved_files.append(file.filename)
#     return {"uploaded": saved_files, "count": len(saved_files)}

@router.post("/{session_id}/upload")
def upload_dataset_info(
    session_id: str,
    image_count: int,
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
    return {"message": f"Dataset registered with {image_count} images", "image_count": image_count}


@router.get("/{session_id}/model/download")
def download_model(
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
    model_path = f"models/{session_id}/model.pt"
    if not os.path.exists(model_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not ready yet"
        )
    return FileResponse(
        path=model_path,
        filename=f"pentagon_model_{session_id}.pt",
        media_type="application/octet-stream"
    )