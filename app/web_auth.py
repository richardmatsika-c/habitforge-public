# app/web_auth.py
from typing import Annotated, Optional
from fastapi import Depends, HTTPException, status, Request
from sqlmodel import Session
import os

from .db import SessionDep
from .models import User
from .api.auth import get_user_by_username, ALGORITHM, SECRET_KEY_STR
from jose import JWTError, jwt


# This is our new "getter" for the cookie
def get_token_from_cookie(request: Request) -> Optional[str]:
    """
    Parses the "Bearer <token>" string from the access_token cookie.
    """
    token_str = request.cookies.get("access_token")
    if not token_str or not token_str.startswith("Bearer "):
        return None
    return token_str.split(" ")[1]  # Return just the token part


async def get_current_user_from_cookie(
    token: Annotated[Optional[str], Depends(get_token_from_cookie)], session: SessionDep
) -> User:
    """
    A dependency that gets the current user from the
    'access_token' cookie.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        detail="Not authenticated",
        headers={"Location": "/web/login"},  # Redirect to login page
    )

    if token is None:
        raise credentials_exception

    try:
        payload = jwt.decode(token, SECRET_KEY_STR, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = get_user_by_username(session, username=username)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Inactive user",
            headers={"Location": "/web/login"},
        )

    return user
