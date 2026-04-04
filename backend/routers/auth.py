from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from schemas.auth import RegisterRequest, LoginRequest, ConfirmRequest, ResendCodeRequest, TokenResponse
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import hmac
import hashlib
import base64
import boto3
from botocore.exceptions import ClientError

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
AWS_REGION = os.getenv("AWS_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")
COGNITO_APP_CLIENT_SECRET = os.getenv("COGNITO_APP_CLIENT_SECRET")

USE_COGNITO = (
    COGNITO_USER_POOL_ID
    and COGNITO_APP_CLIENT_ID
    and COGNITO_USER_POOL_ID != "your_user_pool_id_here"
    and COGNITO_APP_CLIENT_ID != "your_app_client_id_here"
)

if USE_COGNITO:
    cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)


def _compute_secret_hash(username: str) -> str:
    msg = username + COGNITO_APP_CLIENT_ID
    dig = hmac.new(
        COGNITO_APP_CLIENT_SECRET.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(dig).decode()


# ── Local auth helpers ──

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ── Register ──

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    if USE_COGNITO:
        return _cognito_register(request, db)
    return _local_register(request, db)


def _cognito_register(request: RegisterRequest, db: Session):
    try:
        params = {
            "ClientId": COGNITO_APP_CLIENT_ID,
            "Username": request.email,
            "Password": request.password,
            "UserAttributes": [{"Name": "email", "Value": request.email}],
        }
        if COGNITO_APP_CLIENT_SECRET:
            params["SecretHash"] = _compute_secret_hash(request.email)

        cognito_client.sign_up(**params)

        return {"message": "Verification code sent to your email"}
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        print(f"Cognito register error: {code} - {msg}")
        if code == "UsernameExistsException":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        if code == "InvalidPasswordException":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


def _local_register(request: RegisterRequest, db: Session):
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    new_user = User(email=request.email, hashed_password=hash_password(request.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User registered successfully"}


# ── Confirm (Cognito only) ──

@router.post("/confirm", status_code=status.HTTP_200_OK)
def confirm(request: ConfirmRequest):
    if not USE_COGNITO:
        return {"message": "Confirmation not required"}
    try:
        params = {
            "ClientId": COGNITO_APP_CLIENT_ID,
            "Username": request.email,
            "ConfirmationCode": request.code,
        }
        if COGNITO_APP_CLIENT_SECRET:
            params["SecretHash"] = _compute_secret_hash(request.email)

        cognito_client.confirm_sign_up(**params)
        return {"message": "Email verified successfully"}
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        print(f"Cognito confirm error: {code} - {msg}")
        if code == "CodeMismatchException":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
        if code == "ExpiredCodeException":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired. Request a new one.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


# ── Resend Code (Cognito only) ──

@router.post("/resend-code", status_code=status.HTTP_200_OK)
def resend_code(request: ResendCodeRequest):
    if not USE_COGNITO:
        return {"message": "Not applicable"}
    try:
        params = {
            "ClientId": COGNITO_APP_CLIENT_ID,
            "Username": request.email,
        }
        if COGNITO_APP_CLIENT_SECRET:
            params["SecretHash"] = _compute_secret_hash(request.email)

        cognito_client.resend_confirmation_code(**params)
        return {"message": "Verification code resent"}
    except ClientError as e:
        msg = e.response["Error"]["Message"]
        print(f"Cognito resend error: {msg}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


# ── Login ──

@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    if USE_COGNITO:
        return _cognito_login(request, db)
    return _local_login(request, db)


def _cognito_login(request: LoginRequest, db: Session):
    try:
        auth_params = {
            "USERNAME": request.email,
            "PASSWORD": request.password,
        }
        if COGNITO_APP_CLIENT_SECRET:
            auth_params["SECRET_HASH"] = _compute_secret_hash(request.email)

        resp = cognito_client.initiate_auth(
            ClientId=COGNITO_APP_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=auth_params,
        )
        id_token = resp["AuthenticationResult"]["IdToken"]
        return TokenResponse(access_token=id_token)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "UserNotConfirmedException":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your email first")
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.response["Error"]["Message"])


def _local_login(request: LoginRequest, db: Session):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not user.hashed_password or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)
