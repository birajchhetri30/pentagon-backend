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
import boto3
import json
from pydantic import BaseModel

router = APIRouter(prefix="/sessions", tags=["sessions"])


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
    new_session = SessionModel(
        name=request.name,
        architecture=request.architecture,
        task=request.task,
        user_id=current_user.id
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


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


class HyperparameterRequest(BaseModel):
    image_count: int
    image_size: int
    classes: List[str]


class HyperparameterResponse(BaseModel):
    acceptance_criteria: str
    epochs: str
    learning_rate: str
    from_claude: bool


@router.post("/suggest-hyperparameters", response_model=HyperparameterResponse)
def suggest_hyperparameters(
    request: HyperparameterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Use Claude to suggest training hyperparameters based on dataset characteristics.
    """
    try:
        # Initialize Bedrock client
        bedrock = boto3.client("bedrock-runtime")
        
        # Create prompt for Claude
        classes_str = ", ".join(request.classes)
        prompt = f"""Based on the following semantic segmentation training configuration, suggest appropriate hyperparameters:

Dataset Characteristics:
- Number of images: {request.image_count}
- Image size: {request.image_size}x{request.image_size} pixels
- Number of classes: {len(request.classes)}
- Classes: {classes_str}

Please provide ONLY the following values in the exact format below, one per line:
acceptance_criteria: [value]%
epochs: [value]
learning_rate: [value]

For example:
acceptance_criteria: 80%
epochs: 20
learning_rate: 1e-4

Respond with only these three lines, no other text."""

        # Call Claude via Bedrock
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-5-sonnet-20241022",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-06-01",
                "max_tokens": 200,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )
        
        # Parse response
        response_body = json.loads(response["body"].read())
        text_response = response_body["content"][0]["text"].strip()
        
        # Parse the returned values
        lines = text_response.strip().split("\n")
        acceptance_criteria = "80%"
        epochs = "10"
        learning_rate = "1e-4"
        
        for line in lines:
            line = line.strip()
            if "acceptance_criteria:" in line:
                acceptance_criteria = line.split(":", 1)[1].strip()
            elif "epochs:" in line:
                epochs = line.split(":", 1)[1].strip()
            elif "learning_rate:" in line:
                learning_rate = line.split(":", 1)[1].strip()
        
        return HyperparameterResponse(
            acceptance_criteria=acceptance_criteria,
            epochs=epochs,
            learning_rate=learning_rate,
            from_claude=True
        )
        
    except Exception as e:
        # Fall back to defaults if Claude call fails
        print(f"Error calling Claude: {e}")
        return HyperparameterResponse(
            acceptance_criteria="80%",
            epochs="10",
            learning_rate="1e-4",
            from_claude=False
        )


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