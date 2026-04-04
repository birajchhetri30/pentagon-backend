from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from dotenv import load_dotenv
import os
import requests

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
AWS_REGION = os.getenv("AWS_REGION")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_APP_CLIENT_ID = os.getenv("COGNITO_APP_CLIENT_ID")

USE_COGNITO = (
    COGNITO_USER_POOL_ID
    and COGNITO_APP_CLIENT_ID
    and COGNITO_USER_POOL_ID != "your_user_pool_id_here"
    and COGNITO_APP_CLIENT_ID != "your_app_client_id_here"
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Cache Cognito JWKS keys
_jwks_cache: dict | None = None


def _get_cognito_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is None:
        url = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        resp = requests.get(url)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


def _verify_cognito_token(token: str) -> dict:
    jwks = _get_cognito_jwks()
    headers = jwt.get_unverified_headers(token)
    kid = headers.get("kid")

    key = None
    for k in jwks["keys"]:
        if k["kid"] == kid:
            key = k
            break

    if key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token key")

    issuer = f"https://cognito-idp.{AWS_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"

    # Cognito ID tokens have "aud" = client_id, access tokens have "client_id" instead
    # We use ID tokens, so verify with audience
    try:
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=COGNITO_APP_CLIENT_ID,
            issuer=issuer,
        )
    except JWTError:
        # Fallback: try without audience check (for access tokens)
        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"verify_aud": False},
        )
        # Manually verify client_id for access tokens
        if payload.get("client_id") != COGNITO_APP_CLIENT_ID:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience")

    return payload


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if USE_COGNITO:
        return _get_user_from_cognito(token, db)
    else:
        return _get_user_from_local_jwt(token, db)


def _get_user_from_cognito(token: str, db: Session) -> User:
    try:
        payload = _verify_cognito_token(token)
        cognito_sub = payload.get("sub")
        email = payload.get("email")

        if not cognito_sub:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        # Find user by cognito_sub, or create if first login
        user = db.query(User).filter(User.cognito_sub == cognito_sub).first()
        if not user:
            user = db.query(User).filter(User.email == email).first()
            if user:
                user.cognito_sub = cognito_sub
                db.commit()
                db.refresh(user)
            else:
                user = User(email=email, cognito_sub=cognito_sub)
                db.add(user)
                db.commit()
                db.refresh(user)

        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def _get_user_from_local_jwt(token: str, db: Session) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user
