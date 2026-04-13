# app/api/auth.py

from datetime import timedelta, datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from jose import JWTError, jwt
from sqlmodel import Session, select
import os

# --- FIX: Use relative imports ---
from ..db import SessionDep
from ..models import User, UserCreate, UserPublic, Token, TokenData
from .. import security  # <-- Import the new security module

# ---------------------------
# Security Configuration
# ---------------------------

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set")

SECRET_KEY_STR: str = SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="auth/token")
router = APIRouter(prefix="/auth", tags=["Authentication"])

# ---------------------------
# Utility Functions
# ---------------------------


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    """Get a user by username."""
    statement = select(User).where(User.username == username)
    return session.exec(statement).first()


def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    """Authenticate a user with username and password."""
    user = get_user_by_username(session, username)
    if not user:
        return None
    # --- FIX: Use the security module ---
    if not security.verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_STR, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_bearer)], session: SessionDep
) -> User:
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY_STR, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        user_id: Optional[int] = payload.get("user_id")

        if username is None or user_id is None:
            raise credentials_exception

        # Use the TokenData model from models.py if you have one,
        # otherwise, this inline check is fine.

    except JWTError:
        raise credentials_exception

    user = get_user_by_username(session, username=username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# ---------------------------
# Route Handlers
# ---------------------------


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register_user(session: SessionDep, user_data: UserCreate) -> UserPublic:
    """
    Register a new user.
    - **username**: must be unique and 3-50 characters
    - **password**: must be at least 8 characters
    - **email**: optional email address
    """
    existing_user = get_user_by_username(session, user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    hashed_password = security.get_password_hash(user_data.password)

    # Create the user object from the input, overriding with the hash
    user = User.model_validate(
        user_data, update={"hashed_password": hashed_password, "is_active": True}
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    # --- THIS IS THE FIX ---
    # Explicitly return a UserPublic model
    # FastAPI can also do this automatically if you return 'user',
    # but Pylance prefers this explicit return.
    return UserPublic.model_validate(user)


@router.post(
    "/token",
    response_model=Token,
    summary="Login for access token",
)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep
) -> Token:
    """
    OAuth2 compatible login, get an access token for future requests.
    """
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.id is None:  # Should not happen after auth
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User data integrity error",
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "user_id": user.id},
        expires_delta=access_token_expires,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get current user",
)
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserPublic:
    """Get current logged-in user."""

    # --- THIS IS THE FIX ---
    # Explicitly return a UserPublic model
    return UserPublic.model_validate(current_user)
